'''
See COPYRIGHT.md for copyright information.
'''
import os, sys, traceback, re
from arelle import (ModelXbrl, XmlUtil, ModelVersReport, XbrlConst, ModelDocument,
               ValidateXbrl, ValidateFormula)
from arelle.FileSource import openFileSource
from arelle.ModelValue import (qname, QName)
from arelle.PluginManager import pluginClassMethods
from arelle.UrlUtil import parseRfcDatetime
import datetime

def initializeWatcher(modelXbrl):
    return WatchRss(modelXbrl)

class ValidationException(Exception):
    def __init__(self, message, severity, code):
        self.message = message
        self.severity = severity
        self.code = code
        self.messageLog = []
    def __repr__(self):
        return "{0}({1})={2}".format(self.code,self.severity,self.message)

class WatchRss:
    def __init__(self, rssModelXbrl):
        self.rssModelXbrl = rssModelXbrl
        self.cntlr = rssModelXbrl.modelManager.cntlr
        self.thread = None
        self.stopRequested = False
        rssModelXbrl.watchRss = self
        # cache modelManager options which dialog overrides
        self.priorValidateCalcLB = self.priorFormulaRunIDs = None

    def start(self):
        import threading
        if not self.thread or not self.thread.is_alive():
            self.stopRequested = False
            self.priorValidateCalcLB = self.priorFormulaRunIDs = None
            rssWatchOptions = self.rssModelXbrl.modelManager.rssWatchOptions
            if rssWatchOptions.get("validateCalcLinkbase") != self.rssModelXbrl.modelManager.validateCalcLB:
                self.priorValidateCalcLB = self.rssModelXbrl.modelManager.validateCalcLB
                self.rssModelXbrl.modelManager.validateCalcLB = rssWatchOptions.get("validateCalcLinkbase")
            if (rssWatchOptions.get("validateFormulaAssertions") in (False,True) and
                self.rssModelXbrl.modelManager.formulaOptions is not None):
                self.priorFormulaRunIDs = self.rssModelXbrl.modelManager.formulaOptions.runIDs
                self.rssModelXbrl.modelManager.formulaOptions.runIDs = "" if rssWatchOptions.get("validateFormulaAssertions") else "**FakeIdToBlockFormulas**"
            self.thread = threading.Thread(target=lambda: self.watchCycle())
            self.thread.daemon = True
            self.thread.start()
            return
        # load
        # validate



    def stop(self):
        if self.thread and self.thread.is_alive():
            self.stopRequested = True

    def watchCycle(self):
        logFile = self.rssModelXbrl.modelManager.rssWatchOptions.get("logFileUri")
        if logFile:
            self.cntlr.startLogging(logFileName=logFile,
                                    logFileMode = "a",
                                    logFormat="[%(messageCode)s] %(message)s - %(file)s",
                                    logLevel="DEBUG")

        while not self.stopRequested:
            rssWatchOptions = self.rssModelXbrl.modelManager.rssWatchOptions

            # check rss expiration
            rssHeaders = self.cntlr.webCache.getheaders(self.rssModelXbrl.modelManager.rssWatchOptions.get("feedSourceUri"))
            expires = parseRfcDatetime(rssHeaders.get("expires"))
            reloadNow = True # texpires and expires > datetime.datetime.now()

            # reload rss feed
            self.rssModelXbrl.reload('checking RSS items', reloadCache=reloadNow)
            if self.stopRequested: break
            # setup validator
            postLoadActions = []
            if (rssWatchOptions.get("validateDisclosureSystemRules") or
                rssWatchOptions.get("validateXbrlRules") or
                rssWatchOptions.get("validateFormulaAssertions")):
                self.instValidator = ValidateXbrl.ValidateXbrl(self.rssModelXbrl)
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
                rssWatchOptions.get("validateCalcLinkbase") or
                rssWatchOptions.get("validateFormulaAssertions") or
                rssWatchOptions.get("alertMatchedFactText") or
                any(pluginXbrlMethod(rssWatchOptions)
                    for pluginXbrlMethod in pluginClassMethods("RssWatch.HasWatchAction"))
                ):
                # form keys in ascending order of pubdate
                pubDateRssItems = []
                for rssItem in self.rssModelXbrl.modelDocument.rssItems:
                    pubDateRssItems.append((rssItem.pubDate,rssItem.objectId()))

                for pubDate, rssItemObjectId in sorted(pubDateRssItems):
                    rssItem = self.rssModelXbrl.modelObject(rssItemObjectId)
                    # update ui thread via modelManager (running in background here)
                    self.rssModelXbrl.modelManager.viewModelObject(self.rssModelXbrl, rssItem.objectId())
                    if self.stopRequested:
                        break
                    latestPubDate = XmlUtil.datetimeValue(rssWatchOptions.get("latestPubDate"))
                    if (latestPubDate and
                        rssItem.pubDate < latestPubDate):
                        continue
                    try:
                        # try zipped URL if possible, else expanded instance document
                        modelXbrl = ModelXbrl.load(self.rssModelXbrl.modelManager,
                                                   openFileSource(rssItem.zippedUrl, self.cntlr),
                                                   postLoadAction)
                        if self.stopRequested:
                            modelXbrl.close()
                            break

                        emailAlert = False
                        emailMsgs = []
                        if modelXbrl.modelDocument is None:
                            modelXbrl.error("arelle.rssWatch",
                                            _("RSS item %(company)s %(form)s document not loaded: %(date)s"),
                                            modelXbrl=modelXbrl, company=rssItem.companyName,
                                            form=rssItem.formType, date=rssItem.filingDate)
                            rssItem.status = "not loadable"
                        else:
                            for pluginXbrlMethod in pluginClassMethods("RssItem.Xbrl.Loaded"):
                                pluginXbrlMethod(modelXbrl, rssWatchOptions, rssItem)
                            # validate schema, linkbase, or instance
                            if self.stopRequested:
                                modelXbrl.close()
                                break
                            if self.instValidator:
                                self.instValidator.validate(modelXbrl, modelXbrl.modelManager.formulaOptions.typedParameters(modelXbrl.prefixedNamespaces))
                                if modelXbrl.errors and rssWatchOptions.get("alertValiditionError"):
                                    emailAlert = True
                            for pluginXbrlMethod in pluginClassMethods("RssWatch.DoWatchAction"):
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
                                ModelDocument.load(modelXbrl, rssWatchOptions["formulaFileUri"])
                                ValidateFormula.validate(self.instValidator)

                        rssItem.setResults(modelXbrl)
                        modelXbrl.close()
                        del modelXbrl  # completely dereference
                        self.rssModelXbrl.modelManager.viewModelObject(self.rssModelXbrl, rssItem.objectId())
                        if rssItem.assertionUnsuccessful and rssWatchOptions.get("alertAssertionUnsuccessful"):
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
                                 rssItem.cikNumber,
                                 rssItem.companyName,
                                 rssItem.pubDate,
                                 rssItem.formType,
                                 rssItem.filingDate,
                                 rssItem.period,
                                 rssItem.fiscalYearEnd,
                                 rssItem.status)
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
                            emailMsg["Subject"] = _("Arelle RSS Watch alert on {0}").format(rssItem.companyName)
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
                        self.rssModelXbrl.modelManager.showStatus(_("RSS item {0}, {1} completed, status {2}").format(rssItem.companyName, rssItem.formType, rssItem.status), 3500)
                        self.rssModelXbrl.modelManager.cntlr.rssWatchUpdateOption(rssItem.pubDate.strftime('%Y-%m-%dT%H:%M:%S'))
                    except Exception as err:
                        self.rssModelXbrl.error("arelle.rssError",
                                                _("RSS item %(company)s, %(form)s, %(date)s, exception: %(error)s"),
                                                modelXbrl=self.rssModelXbrl, company=rssItem.companyName,
                                                form=rssItem.formType, date=rssItem.filingDate, error=err,
                                                exc_info=True)
                    if self.stopRequested: break
            if self.stopRequested:
                self.cntlr.showStatus(_("RSS watch, stop requested"), 10000)
                # reset prior options for calc and formula running
                if self.priorValidateCalcLB is not None:
                    self.rssModelXbrl.modelManager.validateCalcLB = self.priorValidateCalcLB
                if self.priorFormulaRunIDs is not None:
                    self.rssModelXbrl.modelManager.formulaOptions.runIDs = self.priorFormulaRunIDs
            else:
                import time
                time.sleep(600)

        if logFile:
            self.cntlr.logHandler.close()
        self.thread = None  # close thread
        self.stopRequested = False
