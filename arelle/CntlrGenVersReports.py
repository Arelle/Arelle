'''
Created on Dec 14, 2010

Use this module to start Arelle in command line non-interactive mode

(This module can be a pattern for custom use of Arelle in an application.)

In this example a versioning report production file is read and used to generate
versioning reports, per Roland Hommes 2010-12-10

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.

'''
import time, datetime, os, gettext, io
from lxml import etree
from optparse import OptionParser
from arelle import (Cntlr, ModelXbrl, ModelDocument, ModelVersReport, FileSource, XmlUtil, Version)
from arelle import xlrd

conformanceNS = "http://xbrl.org/2008/conformance"

def main():
    gettext.install("arelle")
    usage = "usage: %prog [options]"
    parser = OptionParser(usage, version="Arelle(r) {0}".format(Version.version))
    parser.add_option("--excelfile", dest="excelfilename",
                      help=_("FILENAME is an excel 95-2003 index file containing columns: \n"
                             "Dir is a test directory, \n"
                             "fromURI is the fromDTS URI relative to test director, \n"
                             "toURI is the toDTS URI relative to test director, \n"
                             "Intention is the goal of the test for testcase description, \n"
                             "Reason is the business, technical, or errata classification, \n"
                             "Expected event is an event localName that is expected \n\n"
                             "Output files and testcases are located in filename's directory, \n"
                             "report files are generated in '/report' under fromURI's directory."))
    parser.add_option("--testfiledate", dest="testfiledate",
                      help=_("Date if desired to use (instead of today) in generated testcase elements."))
    (options, args) = parser.parse_args()
    CntlrGenVersReports().runFromExcel(options)
        
class CntlrGenVersReports(Cntlr.Cntlr):

    def __init__(self):
        super().__init__()
        
    def runFromExcel(self, options):
        #testGenFileName = options.excelfilename
        testGenFileName = r"C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-versioning\trunk\versioningReport\conf\0000-2000-index.xls"
        testGenDir = os.path.dirname(testGenFileName)
        timeNow = XmlUtil.dateunionValue(datetime.datetime.now())
        if options.testfiledate:
            today = options.testfiledate
        else:
            today = XmlUtil.dateunionValue(datetime.date.today())
        startedAt = time.time()
        
        self.logMessages = []
        logMessagesFile = testGenDir + os.sep + 'logGenerationMessages.txt'

        modelTestcases = ModelXbrl.create(self.modelManager)
        testcaseIndexBook = xlrd.open_workbook(testGenFileName)
        testcaseIndexSheet = testcaseIndexBook.sheet_by_index(0)
        self.addToLog(_("[info] xls loaded in {0:.2} secs at {1}").format(time.time() - startedAt, timeNow))
        
        # start index file
        indexFiles = [testGenDir + os.sep + 'creationTestcasesIndex.xml',
                      testGenDir + os.sep + 'consumptionTestcasesIndex.xml']
        indexDocs = []
        testcasesElements = []
        for purpose in ("Creation","Consumption"):
            file = io.StringIO(
                #'<?xml version="1.0" encoding="UTF-8"?>'
                '<!-- XBRL Versioning 1.0 {0} Tests -->'
                '<!-- Copyright 2011 XBRL International.  All Rights Reserved. -->'
                '<?xml-stylesheet type="text/xsl" href="infrastructure/testcases-index.xsl"?>'
                '<testcases name="XBRL Versioning 1.0 {0} Tests" '
                ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
                ' xsi:noNamespaceSchemaLocation="infrastructure/testcases-index.xsd">'
                '</testcases>'.format(purpose, today)
                )
            doc = etree.parse(file)
            file.close()
            indexDocs.append(doc)
            for elt in doc.iter(tag="testcases"):
                testcasesElements.append(elt)
                break
        priorTestcasesDir = None
        testcaseFiles = None
        testcaseDocs = None
        for iRow in range(1, testcaseIndexSheet.nrows):
            row = testcaseIndexSheet.row(iRow)
            if row[0].ctype == xlrd.XL_CELL_EMPTY or row[1].ctype == xlrd.XL_CELL_EMPTY or row[2].ctype == xlrd.XL_CELL_EMPTY:
                continue
            testDir = row[0].value
            uriFrom = row[1].value
            uriTo = row[2].value
            intention = row[3].value
            if intention is None or len(intention) == 0:
                continue # test not ready to run
            reason = row[4].value
            expectedEvent = row[5].value
            base = os.path.join(os.path.dirname(testGenFileName),testDir) + os.sep
            self.addToLog(_("[info] testcase uriFrom {0}").format(uriFrom))
            if uriFrom and uriTo and reason.lower() not in ("n.a.", "error") and expectedEvent != "N.A.":
                for URIs, msg, isFrom in ((uriFrom, _("loading from DTS"), True), (uriTo, _("loading to DTS"), False)):
                    if ',' not in URIs:
                        modelDTS = ModelXbrl.load(self.modelManager, URIs, msg, base=base)
                    else:
                        modelDTS = ModelXbrl.create(self.modelManager, 
                                     ModelDocument.Type.DTSENTRIES,
                                     self.webCache.normalizeUrl(URIs.replace(", ","_") + ".dts", 
                                                                base),
                                     isEntry=True)
                        DTSdoc = modelDTS.modelDocument
                        DTSdoc.inDTS = True
                        for uri in URIs.split(','):
                            doc = ModelDocument.load(modelDTS, uri.strip(), base=base)
                            DTSdoc.referencesDocument[doc] = "import"  #fake import
                            doc.inDTS = True
                    if isFrom: modelDTSfrom = modelDTS
                    else: modelDTSto = modelDTS
                if modelDTSfrom and modelDTSto:
                    # generate differences report
                    reportUri = uriFrom.partition(',')[0]  # first file
                    reportDir = os.path.dirname(reportUri)
                    if reportDir: reportDir += os.sep
                    reportName = os.path.basename(reportUri).replace("from.xsd","report.xml")
                    reportFile = reportDir + "out" + os.sep + reportName
                    #reportFile = reportDir + "report" + os.sep + reportName
                    reportFullPath = self.webCache.normalizeUrl(
                                        reportFile, 
                                        base)
                    testcasesDir = os.path.dirname(os.path.dirname(reportFullPath))
                    if testcasesDir != priorTestcasesDir:
                        # close prior report
                        if priorTestcasesDir:
                            for i,testcaseFile in enumerate(testcaseFiles):
                                with open(testcaseFile, "w", encoding="utf-8") as fh:
                                    XmlUtil.writexml(fh, testcaseDocs[i], encoding="utf-8")
                        testcaseName = os.path.basename(testcasesDir)
                        testcaseFiles = [testcasesDir + os.sep + testcaseName + "-creation-testcase.xml",
                                         testcasesDir + os.sep + testcaseName + "-consumption-testcase.xml"]
                        for i,testcaseFile in enumerate(testcaseFiles):
                            etree.SubElement(testcasesElements[i], "testcase", 
                                             attrib={"uri": 
                                                     testcaseFile[len(testGenDir)+1:].replace("\\","/")} )
                        
                        # start testcase file
                        testcaseDocs = []
                        testcaseElements = []
                        for purpose in ("Creation","Consumption"):
                            file = io.StringIO(
                                #'<?xml version="1.0" encoding="UTF-8"?>'
                                '<!-- Copyright 2011 XBRL International.  All Rights Reserved. -->'
                                '<?xml-stylesheet type="text/xsl" href="../../../infrastructure/test.xsl"?>'
                                '<testcase name="XBRL Versioning 1.0 {1} Tests" date="{2}" '
                                ' xmlns="http://xbrl.org/2008/conformance"'
                                ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
                                ' xsi:schemaLocation="http://xbrl.org/2008/conformance ../../../infrastructure/test.xsd">'
                                '<creator>'
                                '<name>Roland Hommes</name>'
                                '<email>roland@rhocon.nl</email>'
                                '</creator>'
                                '<name>{0}</name>'
                                '<description>{0}</description>'
                                '</testcase>'.format(testcaseName,purpose,today)
                                )
                            doc = etree.parse(file)
                            file.close()
                            testcaseDocs.append(doc)
                            for elt in doc.iter(tag="testcase"):
                                testcaseElements.append(elt)
                                break
                        priorTestcasesDir = testcasesDir
                        variationID = 1
                    try:
                        os.makedirs(os.path.dirname(reportFullPath))
                    except WindowsError:
                        pass # dir already exists
                    modelVersReport = ModelVersReport.ModelVersReport(modelTestcases)
                    modelVersReport.diffDTSes(reportFullPath,modelDTSfrom, modelDTSto)
                    
                    # check for expected elements
                    if expectedEvent and expectedEvent not in (
                           "No change", "N.A."):
                        if len(modelVersReport.xmlDocument.findall('//{*}' + expectedEvent)) == 0:
                            modelTestcases.error(
                                "Generated test case {0} missing expected event {1}".format(
                                           reportName, 
                                           expectedEvent), 
                                "wrn", "missingEvent")
                    
                    modelVersReport.close([])
                    for i,testcaseElt in enumerate(testcaseElements):
                        variationElement = etree.SubElement(testcaseElt, "{http://xbrl.org/2008/conformance}variation", 
                                                            attrib={"id": "_{0:02n}".format(variationID)})
                        nameElement = etree.SubElement(variationElement, "{http://xbrl.org/2008/conformance}name")
                        nameElement.text = intention
                        dataElement = etree.SubElement(variationElement, "{http://xbrl.org/2008/conformance}data")
                        for schemaURIs, dtsAttr in ((uriFrom,"from"), (uriTo,"to")):
                            for schemaURI in schemaURIs.split(","): 
                                schemaElement = etree.SubElement(dataElement, "{http://xbrl.org/2008/conformance}schema")
                                schemaElement.set("dts",dtsAttr)
                                if i == 0:
                                    schemaElement.set("readMeFirst","true")
                                schemaElement.text=os.path.basename(schemaURI.strip())
                        resultElement = etree.SubElement(variationElement, "{http://xbrl.org/2008/conformance}result")
                        reportElement = etree.SubElement(resultElement if i == 0 else dataElement, 
                                         "{http://xbrl.org/2008/conformance}versioningReport")
                        if 1 == 1:
                            reportElement.set("readMeFirst","true")
                            reportElement.text = "report/" + reportName
                    variationID += 1
        
        with open(logMessagesFile, "w") as fh:
            fh.writelines(self.logMessages)

        if priorTestcasesDir:
            for i,testcaseFile in enumerate(testcaseFiles):
                with open(testcaseFile, "w", encoding="utf-8") as fh:
                    XmlUtil.writexml(fh, testcaseDocs[i], encoding="utf-8")
        for i,indexFile in enumerate(indexFiles):
            with open(indexFile, "w", encoding="utf-8") as fh:
                XmlUtil.writexml(fh, indexDocs[i], encoding="utf-8")
    
    def runFromXml(self):
        testGenFileName = r"C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\roland test cases\1000-Concepts\index.xml"
        filesource = FileSource.FileSource(testGenFileName)
        startedAt = time.time()
        modelTestcases = self.modelManager.load(filesource, _("views loading"))
        self.addToLog(_("[info] loaded in {0:.2} secs").format(time.time() - startedAt))
        if modelTestcases.modelDocument.type == ModelDocument.Type.TESTCASESINDEX:
            for testcasesElement in modelTestcases.modelDocument.iter(tag="testcases"):
                rootAttr = testcasesElement.get("root")
                title = testcasesElement.get("title")
                self.addToLog(_("[info] testcases {0}").format(title))
                if rootAttr is not None:
                    base = os.path.join(os.path.dirname(modelTestcases.modelDocument.filepath),rootAttr) + os.sep
                else:
                    base = self.filepath
                for testcaseElement in testcasesElement.iterchildren(tag="testcase"):
                    uriFrom = testcaseElement.get("uriFrom")
                    uriTo = testcaseElement.get("uriTo")
                    self.addToLog(_("[info] testcase uriFrom {0}").format(uriFrom))
                    if uriFrom is not None and uriTo is not None:
                        modelDTSfrom = ModelXbrl.load(modelTestcases.modelManager, 
                                                   uriFrom,
                                                   _("loading from DTS"), 
                                                   base=base)
                        modelDTSto = ModelXbrl.load(modelTestcases.modelManager, 
                                                   uriTo,
                                                   _("loading to DTS"), 
                                                   base=base)
                        if modelDTSfrom and modelDTSto:
                            # generate differences report
                            reportName = os.path.basename(uriFrom).replace("from.xsd","report.xml")
                            reportFile = os.path.dirname(uriFrom) + "\\report\\" + reportName
                            reportFullPath = self.webCache.normalizeUrl(
                                                reportFile, 
                                                base)
                            try:
                                os.makedirs(os.path.dirname(reportFullPath))
                            except WindowsError:
                                pass # dir already exists
                            ModelVersReport.ModelVersReport(modelTestcases).diffDTSes(
                                          reportFullPath,
                                          modelDTSfrom, modelDTSto)

    def addToLog(self, message):
        self.logMessages.append(message + '\n')
        print(message)
    
    def showStatus(self, message, clearAfter=None):
        pass

if __name__ == "__main__":
    main()
