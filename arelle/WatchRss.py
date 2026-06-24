'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

import regex as re
import threading

from arelle.ValidateXbrl import ValidateXbrl
from arelle.ModelXbrl import ModelXbrl, load as ModelXbrlLoad
from arelle.ModelDocument import load as ModelDocumentLoad
from arelle.XmlUtil import datetimeValue
from arelle.formula import ValidateFormula
from arelle.FileSource import openFileSource
from arelle.typing import TypeGetText

_: TypeGetText


def initializeWatcher(modelXbrl: ModelXbrl) -> WatchRss:
    return WatchRss(modelXbrl)


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
            self.rssModelXbrl.reload('checking RSS items', reloadCache=reloadNow)
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
            postLoadAction = ', '.join(postLoadActions)

            # anything to check new filings for
            if (rssWatchOptions.get("validateDisclosureSystemRules") or
                rssWatchOptions.get("validateXbrlRules") or
                rssWatchOptions.get("validateCalcs") or
                rssWatchOptions.get("validateFormulaAssertions") or
                rssWatchOptions.get("alertMatchedFactText") or
                any(pluginXbrlMethod(rssWatchOptions)
                    for pluginXbrlMethod in self.cntlr.plugins.hooks("RssWatch.HasWatchAction"))
                ):
                # form keys in ascending order of pubdate
                pubDateRssItems = []
                for rssItem in self.rssModelXbrl.modelDocument.rssItems:  # type: ignore[union-attr]
                    pubDateRssItems.append((rssItem.pubDate, rssItem.objectId()))

                for pubDate, rssItemObjectId in sorted(pubDateRssItems):
                    rssItem = self.rssModelXbrl.modelObject(rssItemObjectId)
                    # update ui thread via modelManager (running in background here)
                    self.rssModelXbrl.modelManager.viewModelObject(self.rssModelXbrl, rssItem.objectId())  # type: ignore[union-attr]
                    if self.stopRequested:
                        break
                    latestPubDate = datetimeValue(rssWatchOptions.get("latestPubDate"))
                    if (latestPubDate and
                        rssItem.pubDate < latestPubDate):  # type: ignore[union-attr]
                        continue
                    try:
                        # try zipped URL if possible, else expanded instance document
                        modelXbrl = ModelXbrlLoad(self.rssModelXbrl.modelManager,
                                                   openFileSource(rssItem.zippedUrl, self.cntlr),  # type: ignore[union-attr]
                                                   postLoadAction)
                        if self.stopRequested:
                            modelXbrl.close()
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
                                modelXbrl.close()
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
                        modelXbrl.close()
                        del modelXbrl  # completely dereference
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
                        self.rssModelXbrl.modelManager.cntlr.rssWatchUpdateOption(rssItem.pubDate.strftime('%Y-%m-%dT%H:%M:%S'))  # type: ignore[union-attr,call-arg]
                    except Exception as err:
                        self.rssModelXbrl.error("arelle.rssError",
                                                _("RSS item %(company)s, %(form)s, %(date)s, exception: %(error)s"),
                                                modelXbrl=self.rssModelXbrl, company=rssItem.companyName,  # type: ignore[union-attr]
                                                form=rssItem.formType, date=rssItem.filingDate, error=err,  # type: ignore[union-attr]
                                                exc_info=True)
                    if self.stopRequested: break
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
