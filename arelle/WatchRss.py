"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import regex as re
import threading
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.ModelXbrl import ModelXbrl, load as ModelXbrlLoad
from arelle.ModelDocument import load as ModelDocumentLoad
from arelle.XmlUtil import datetimeValue
from arelle.formula import ValidateFormula
from arelle.FileSource import openFileSource
from arelle.utils.EntryPointDetection import filesourceEntrypointFiles
from arelle.typing import TypeGetText

_: TypeGetText


def initializeWatcher(modelXbrl: ModelXbrl) -> WatchRss:
    return WatchRss(modelXbrl)


def hasWatchAction(cntlr: Any, rssWatchOptions: dict[str, Any]) -> bool:
    # True if the RSS Watch options configured on cntlr have anything checked that makes
    # watchCycle load and process each new filing (validate, alert-on-match, or a plugin
    # action) rather than just refreshing the feed listing.
    return bool(
        rssWatchOptions.get("validateDisclosureSystemRules") or
        rssWatchOptions.get("validateXbrlRules") or
        rssWatchOptions.get("validateCalcs") or
        rssWatchOptions.get("validateFormulaAssertions") or
        rssWatchOptions.get("alertMatchedFactText") or
        any(pluginXbrlMethod(rssWatchOptions)
            for pluginXbrlMethod in cntlr.plugins.hooks("RssWatch.HasWatchAction"))
    )


class ValidationException(Exception):
    def __init__(self, message: str, severity: str, code: str) -> None:
        self.message = message
        self.severity = severity
        self.code = code
        self.messageLog: list[str] = []
    def __repr__(self) -> str:
        return "{0}({1})={2}".format(self.code, self.severity, self.message)


class WatchRss:
    def __init__(self, rssModelXbrl: ModelXbrl) -> None:
        self.rssModelXbrl = rssModelXbrl
        self.cntlr = rssModelXbrl.modelManager.cntlr
        self.thread: threading.Thread | None = None
        self.stopRequested: bool = False
        rssModelXbrl.watchRss = self
        # cache modelManager options which dialog overrides
        self.priorValidateCalcs: int | None = None
        self.priorFormulaRunIDs: str | None = None
        self.instValidator: ValidateXbrl | None = None
        self.priorValidateCalcLB: str | None = None

    def start(self) -> None:
        if self.cntlr.webCache.workOffline:
            self.rssModelXbrl.error("arelle.rssError",
                _("RSS feed is not accessible in work offline mode."),
                modelXbrl=self.rssModelXbrl)
            return
        if not self.thread or not self.thread.is_alive():
            self.stopRequested = False
            self.priorValidateCalcLB = self.priorFormulaRunIDs = None
            rssWatchOptions = self.rssModelXbrl.modelManager.rssWatchOptions
            if rssWatchOptions.get("validateCalcs") != self.rssModelXbrl.modelManager.validateCalcs:
                self.priorValidateCalcs = self.rssModelXbrl.modelManager.validateCalcs
                self.rssModelXbrl.modelManager.validateCalcs = rssWatchOptions.get("validateCalcs")  # type: ignore[assignment]
            if (rssWatchOptions.get("validateFormulaAssertions") in (False,True) and
                self.rssModelXbrl.modelManager.formulaOptions is not None):
                self.priorFormulaRunIDs = self.rssModelXbrl.modelManager.formulaOptions.runIDs  # type: ignore[assignment]
                self.rssModelXbrl.modelManager.formulaOptions.runIDs = "" if rssWatchOptions.get("validateFormulaAssertions") else "**FakeIdToBlockFormulas**"
            self.thread = threading.Thread(target=lambda: self.watchCycle())
            self.thread.daemon = True
            self.thread.start()
            return

    def stop(self) -> None:
        if self.thread and self.thread.is_alive():
            self.stopRequested = True

    def _closeRssItemModelXbrl(self, modelXbrl: ModelXbrl | None) -> None:
        # A watched item that is an inline filing with separate IXDS targets (e.g. an EX-FILING
        # FEES exhibit) causes inlineXbrlDocumentSet to publish secondary-target modelXbrls into
        # modelManager.loadedModelXbrls, sharing this item's parsed html elements. Close and
        # unregister those together with the item so a later loadedModelXbrls sweep (such as the
        # GUI's Validate command) does not process a model whose parser points at this now-closed
        # item (which would raise AttributeError on qnameConcepts and similar).
        if modelXbrl is None:
            return
        loadedModelXbrls = self.rssModelXbrl.modelManager.loadedModelXbrls
        for supplementalModelXbrl in getattr(modelXbrl, "supplementalModelXbrls", ()):
            try:
                while supplementalModelXbrl in loadedModelXbrls:
                    loadedModelXbrls.remove(supplementalModelXbrl)
                supplementalModelXbrl.close()
            except Exception:
                pass
        modelXbrl.close()

    def watchCycle(self) -> None:
        logFile = self.rssModelXbrl.modelManager.rssWatchOptions.get("logFileUri")
        if logFile:
            self.cntlr.startLogging(logFileName=logFile,
                                    logFileMode = "a",
                                    logFormat="[%(messageCode)s] %(message)s - %(file)s",
                                    logLevel="DEBUG")

        while not self.stopRequested:
            rssWatchOptions = self.rssModelXbrl.modelManager.rssWatchOptions

            # check rss expiration
            reloadNow = True

            # reload rss feed
            self.rssModelXbrl.reload("checking RSS items", reloadCache=reloadNow)
            if self.stopRequested: break
            # setup validator
            postLoadActions = []
            if (rssWatchOptions.get("validateDisclosureSystemRules") or
                rssWatchOptions.get("validateXbrlRules") or
                rssWatchOptions.get("validateFormulaAssertions")):
                self.instValidator = ValidateXbrl(self.rssModelXbrl)
                postLoadActions.append(_("validating"))
                if (rssWatchOptions.get("validateFormulaAssertions")):
                    postLoadActions.append(_("running formulas"))
            else:
                self.instValidator = None

            matchTextExpr = rssWatchOptions.get("matchTextExpr")
            if matchTextExpr:
                matchPattern = re.compile(matchTextExpr)
                postLoadActions.append(_("matching text"))
            else:
                matchPattern= None
            postLoadAction = ", ".join(postLoadActions)

            # anything to check new filings for
            if hasWatchAction(self.cntlr, rssWatchOptions):
                # form keys in ascending order of pubdate
                pubDateRssItems = []
                for rssItem in self.rssModelXbrl.modelDocument.rssItems:  # type: ignore[union-attr]
                    pubDateRssItems.append((rssItem.pubDate, rssItem.objectId()))

                # sort by pubDate ascending; items whose pubDate failed to parse (None) sort first
                # via the leading flag so None is never compared against a datetime, which would
                # otherwise raise and abort the whole watch cycle
                validatedSinceViewRefresh = 0
                for pubDate, rssItemObjectId in sorted(
                        pubDateRssItems,
                        key=lambda i: (i[0] is not None, i[0] if i[0] is not None else "", i[1])):
                    rssItem = self.rssModelXbrl.modelObject(rssItemObjectId)
                    # update ui thread via modelManager (running in background here)
                    self.rssModelXbrl.modelManager.viewModelObject(self.rssModelXbrl, rssItem.objectId())  # type: ignore[union-attr]
                    if self.stopRequested:
                        break
                    latestPubDate = datetimeValue(rssWatchOptions.get("latestPubDate"))
                    if (latestPubDate and
                        rssItem.pubDate < latestPubDate):  # type: ignore[union-attr]
                        continue
                    modelXbrl = None
                    try:
                        # try zipped URL if possible, else expanded instance document
                        filesource = openFileSource(rssItem.zippedUrl, self.cntlr)  # type: ignore[union-attr]
                        if filesource and not filesource.selection and filesource.isArchive:
                            # a filing zip usually holds multiple files (instance, schema,
                            # linkbases, htm docs, ...); without selecting the actual entry
                            # point document here, ModelDocument.load would try to parse the
                            # raw zip bytes as XML and fail with a UnicodeDecodeError
                            entrypoints = filesourceEntrypointFiles(filesource)
                            if entrypoints:
                                for pluginXbrlMethod in self.cntlr.plugins.hooks("ModelTestcaseVariation.ArchiveIxds"):
                                    pluginXbrlMethod(self.rssModelXbrl, filesource, entrypoints)
                                filesource.select(entrypoints[0].get("file", None))
                        modelXbrl = ModelXbrlLoad(self.rssModelXbrl.modelManager, filesource, postLoadAction)
                        if self.stopRequested:
                            self._closeRssItemModelXbrl(modelXbrl)
                            break

                        emailAlert = False
                        emailMsgs = []
                        if modelXbrl.modelDocument is None:
                            modelXbrl.error("arelle.rssWatch",
                                            _("RSS item %(company)s %(form)s document not loaded: %(date)s"),
                                            modelXbrl=modelXbrl, company=rssItem.companyName,  # type: ignore[union-attr]
                                            form=rssItem.formType, date=rssItem.filingDate)  # type: ignore[union-attr]
                            rssItem.status = "not loadable"  # type: ignore[union-attr]
                        else:
                            for pluginXbrlMethod in self.cntlr.plugins.hooks("RssItem.Xbrl.Loaded"):
                                pluginXbrlMethod(modelXbrl, rssWatchOptions, rssItem)
                            # validate schema, linkbase, or instance
                            if self.stopRequested:
                                self._closeRssItemModelXbrl(modelXbrl)
                                break
                            if self.instValidator:
                                self.instValidator.validate(modelXbrl, modelXbrl.modelManager.formulaOptions.typedParameters(modelXbrl.prefixedNamespaces))
                                if modelXbrl.errors and rssWatchOptions.get("alertValiditionError"):
                                    emailAlert = True
                            for pluginXbrlMethod in self.cntlr.plugins.hooks("RssWatch.DoWatchAction"):
                                pluginXbrlMethod(modelXbrl, rssWatchOptions, rssItem)
                            # check match expression
                            if matchPattern:
                                for fact in modelXbrl.factsInInstance:
                                    v = fact.value
                                    if v is not None:
                                        m = matchPattern.search(v)
                                        if m:
                                            fr, to = m.span()
                                            msg = _("Fact Variable {0}\n context {1}\n matched text: {2}").format(
                                                    fact.qname, fact.contextID, v[max(0,fr-20):to+20])
                                            modelXbrl.info("arelle.rssInfo",
                                                           msg,
                                                           modelXbrl=modelXbrl) # msg as code passes it through to the status
                                            if rssWatchOptions.get("alertMatchedFactText"):
                                                emailAlert = True
                                                emailMsgs.append(msg)

                            if (rssWatchOptions.get("formulaFileUri") and rssWatchOptions.get("validateFormulaAssertions") and
                                self.instValidator):
                                # attach formulas
                                ModelDocumentLoad(modelXbrl, rssWatchOptions["formulaFileUri"])
                                ValidateFormula.validate(self.instValidator)

                        rssItem.setResults(modelXbrl)  # type: ignore[union-attr]
                        self._closeRssItemModelXbrl(modelXbrl)
                        del modelXbrl  # completely dereference
                        # Refresh the feed views periodically so statuses appear as the run
                        # progresses. The targeted viewModelObject update below is unreliable once
                        # the feed has been reloaded (its tree nodes are rebuilt from fresh element
                        # proxies), so a full rebuild - which reads each item's persisted result -
                        # is the dependable path; throttle it to keep the UI thread responsive.
                        validatedSinceViewRefresh += 1
                        if validatedSinceViewRefresh >= 5:
                            validatedSinceViewRefresh = 0
                            self.rssModelXbrl.modelManager.reloadViews(self.rssModelXbrl)
                        self.rssModelXbrl.modelManager.viewModelObject(self.rssModelXbrl, rssItem.objectId())  # type: ignore[union-attr]
                        if rssItem.assertionUnsuccessful and rssWatchOptions.get("alertAssertionUnsuccessful"):  # type: ignore[union-attr]
                            emailAlert = True

                        if logFile:
                            self.cntlr.logHandler.flush()  # write entries out

                        msg = _("Filing CIK {0}\n "
                                 "company {1}\n "
                                 "published {2}\n "
                                 "form type {3}\n "
                                 "filing date {4}\n "
                                 "period {5}\n "
                                 "year end {6}\n "
                                 "results: {7}").format(
                                 rssItem.cikNumber,  # type: ignore[union-attr]
                                 rssItem.companyName,  # type: ignore[union-attr]
                                 rssItem.pubDate,  # type: ignore[union-attr]
                                 rssItem.formType,  # type: ignore[union-attr]
                                 rssItem.filingDate,  # type: ignore[union-attr]
                                 rssItem.period,  # type: ignore[union-attr]
                                 rssItem.fiscalYearEnd,  # type: ignore[union-attr]
                                 rssItem.status)  # type: ignore[union-attr]
                        self.rssModelXbrl.info("arelle:rssWatch", msg, modelXbrl=self.rssModelXbrl)
                        smtpEmailSettings = rssWatchOptions.get("smtpEmailSettings")
                        emailAddress = rssWatchOptions.get("emailAddress")
                        if emailAlert and emailAddress and smtpEmailSettings and len(smtpEmailSettings) == 4:
                            smtpAddr, smtpPort, smtpUser, smtpPassword = smtpEmailSettings
                            portNum = int(smtpPort) if smtpPort else 0
                            self.rssModelXbrl.modelManager.showStatus(_("sending e-mail alert"))
                            import smtplib
                            from email.mime.text import MIMEText
                            emailMsg = MIMEText(msg + "\n" + "\n".join(emailMsgs))
                            emailMsg["Subject"] = _("Arelle RSS Watch alert on {0}").format(rssItem.companyName)  # type: ignore[union-attr]
                            emailMsg["From"] = emailAddress
                            emailMsg["To"] = emailAddress
                            if portNum < 125:
                                smtp = smtplib.SMTP(smtpAddr, portNum)
                            else:
                                smtp = smtplib.SMTP_SSL(smtpAddr, portNum)
                            if smtpUser or smtpPassword:
                                smtp.login(smtpUser, smtpPassword)
                            smtp.sendmail(emailAddress, [emailAddress], emailMsg.as_string())
                            smtp.quit()
                        self.rssModelXbrl.modelManager.showStatus(_("RSS item {0}, {1} completed, status {2}").format(rssItem.companyName, rssItem.formType, rssItem.status), 3500)  # type: ignore[union-attr]
                        self.rssModelXbrl.modelManager.cntlr.rssWatchUpdateOption(rssItem.pubDate.strftime("%Y-%m-%dT%H:%M:%S"))  # type: ignore[union-attr,call-arg]
                    except Exception as err:
                        self.rssModelXbrl.error("arelle.rssError",
                                                _("RSS item %(company)s, %(form)s, %(date)s, exception: %(error)s"),
                                                modelXbrl=self.rssModelXbrl, company=rssItem.companyName,  # type: ignore[union-attr]
                                                form=rssItem.formType, date=rssItem.filingDate, error=err,  # type: ignore[union-attr]
                                                exc_info=True)
                        try:
                            self._closeRssItemModelXbrl(modelXbrl)
                        except Exception:
                            pass
                    if self.stopRequested: break
                # rebuild the feed views so this cycle's freshly validated items show their status
                # now, rather than only after the next poll reloads the feed
                if not self.stopRequested:
                    self.rssModelXbrl.modelManager.reloadViews(self.rssModelXbrl)
            if self.stopRequested:
                self.cntlr.showStatus(_("RSS watch, stop requested"), 10000)
                # reset prior options for calc and formula running
                if self.priorValidateCalcs is not None:
                    self.rssModelXbrl.modelManager.validateCalcs = self.priorValidateCalcs
                if self.priorFormulaRunIDs is not None:
                    self.rssModelXbrl.modelManager.formulaOptions.runIDs = self.priorFormulaRunIDs
            else:
                import time
                time.sleep(600)

        if logFile:
            self.cntlr.logHandler.close()
        self.thread = None  # close thread
        self.stopRequested = False
