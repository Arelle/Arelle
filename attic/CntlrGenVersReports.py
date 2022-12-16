'''
Use this module to start Arelle in command line non-interactive mode

(This module can be a pattern for custom use of Arelle in an application.)

In this example a versioning report production file is read and used to generate
versioning reports, per Roland Hommes 2010-12-10

See COPYRIGHT.md for copyright information.

'''
from arelle import PythonUtil # define 2.x or 3.x string types
import time, datetime, os, gettext, io, sys, traceback
from lxml import etree
from optparse import OptionParser
from arelle import (Cntlr, ModelXbrl, ModelDocument, ModelVersReport, FileSource, 
                    XmlUtil, XbrlConst, Version)
from arelle import xlrd
import logging

conformanceNS = "http://xbrl.org/2008/conformance"

def main():
    gettext.install("arelle") # needed for options messages
    usage = "usage: %prog [options]"
    parser = OptionParser(usage, version="Arelle(r) {0}".format(Version.version))
    parser.add_option("--excelfile", dest="excelfilename",
                      help=_("FILENAME is an excel 95-2003 index file containing columns: \n"
                             "Dir is a test directory, \n"
                             "fromURI is the fromDTS URI relative to test director, \n"
                             "toURI is the toDTS URI relative to test director, \n"
                             "Description is the goal of the test for testcase description, \n"
                             "Assignment is the business, technical, or errata classification, \n"
                             "Expected event is an event localName that is expected \n\n"
                             "Output files and testcases are located in filename's directory, \n"
                             "report files are generated in '/report' under fromURI's directory."))
    parser.add_option("--testfiledate", dest="testfiledate",
                      help=_("Date if desired to use (instead of today) in generated testcase elements."))
    (options, args) = parser.parse_args()
    try:
        CntlrGenVersReports().runFromExcel(options)
    except Exception as ex:
        print (ex, traceback.format_tb(sys.exc_info()[2]))
        
class CntlrGenVersReports(Cntlr.Cntlr):

    def __init__(self):
        super(CntlrGenVersReports, self).__init__()
        
    def runFromExcel(self, options):
        #testGenFileName = options.excelfilename
        testGenFileName = r"C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-versioning\trunk\versioningReport\conf\creation-index.xls"
        testGenDir = os.path.dirname(testGenFileName)
        schemaDir = os.path.dirname(testGenDir) + os.sep + "schema"
        timeNow = XmlUtil.dateunionValue(datetime.datetime.now())
        if options.testfiledate:
            today = options.testfiledate
        else:
            today = XmlUtil.dateunionValue(datetime.date.today())
        startedAt = time.time()
        
        LogHandler(self) # start logger

        self.logMessages = []
        logMessagesFile = testGenDir + os.sep + 'log-generation-messages.txt'

        modelTestcases = ModelXbrl.create(self.modelManager, url=testGenFileName, isEntry=True)
        testcaseIndexBook = xlrd.open_workbook(testGenFileName)
        testcaseIndexSheet = testcaseIndexBook.sheet_by_index(0)
        self.addToLog(_("[info] xls loaded in {0:.2} secs at {1}").format(time.time() - startedAt, timeNow))
        
        # start index file
        indexFiles = [testGenDir + os.sep + 'creation-testcases-index.xml',
                      testGenDir + os.sep + 'consumption-testcases-index.xml']
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
            testcasesElements.append(doc.getroot())
        priorTestcasesDir = None
        testcaseFiles = None
        testcaseDocs = None
        for iRow in range(1, testcaseIndexSheet.nrows):
            try:
                row = testcaseIndexSheet.row(iRow)
                if (row[0].ctype == xlrd.XL_CELL_EMPTY or # must have directory
                    row[1].ctype == xlrd.XL_CELL_EMPTY or # from
                    row[2].ctype == xlrd.XL_CELL_EMPTY):  # to
                    continue
                testDir = row[0].value
                uriFrom = row[1].value
                uriTo = row[2].value
                overrideReport = row[3].value
                description = row[4].value
                if description is None or len(description) == 0:
                    continue # test not ready to run
                assignment = row[5].value
                expectedEvents = row[6].value # comma space separated if multiple
                note = row[7].value
                useCase = row[8].value
                base = os.path.join(os.path.dirname(testGenFileName),testDir) + os.sep
                self.addToLog(_("[info] testcase uriFrom {0}").format(uriFrom))
                if uriFrom and uriTo and assignment.lower() not in ("n.a.", "error") and expectedEvents != "N.A.":
                    modelDTSfrom = modelDTSto = None
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
                                if doc is not None:
                                    DTSdoc.referencesDocument[doc] = "import"  #fake import
                                    doc.inDTS = True
                        if isFrom: modelDTSfrom = modelDTS
                        else: modelDTSto = modelDTS
                    if modelDTSfrom is not None and modelDTSto is not None:
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
                            testcaseNumber = testcaseName[0:4]
                            if testcaseNumber.isnumeric():
                                testcaseNumberElement = "<number>{0}</number>".format(testcaseNumber)
                                testcaseName = testcaseName[5:]
                            else:
                                testcaseNumberElement = ""
                            testDirSegments = testDir.split('/')
                            if len(testDirSegments) >= 2 and '-' in testDirSegments[1]:
                                testedModule = testDirSegments[1][testDirSegments[1].index('-') + 1:]
                            else:
                                testedModule = ''
                            for purpose in ("Creation","Consumption"):
                                file = io.StringIO(
                                    #'<?xml version="1.0" encoding="UTF-8"?>'
                                    '<!-- Copyright 2011 XBRL International.  All Rights Reserved. -->'
                                    '<?xml-stylesheet type="text/xsl" href="../../../infrastructure/test.xsl"?>'
                                    '<testcase '
                                    ' xmlns="http://xbrl.org/2008/conformance"'
                                    ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
                                    ' xsi:schemaLocation="http://xbrl.org/2008/conformance ../../../infrastructure/test.xsd">'
                                    '<creator>'
                                    '<name>Roland Hommes</name>'
                                    '<email>roland@rhocon.nl</email>'
                                    '</creator>'
                                    '{0}'
                                    '<name>{1}</name>'
                                    # '<description>{0}</description>'
                                    '<reference>'
                                    '{2}'
                                    '{3}'
                                    '</reference>'
                                    '</testcase>'.format(testcaseNumberElement,
                                                         testcaseName,
                                                         '<name>{0}</name>'.format(testedModule) if testedModule else '',
                                                         '<id>{0}</id>'.format(useCase) if useCase else '')
                                    
                                    )
                                doc = etree.parse(file)
                                file.close()
                                testcaseDocs.append(doc)
                                testcaseElements.append(doc.getroot())
                            priorTestcasesDir = testcasesDir
                            variationSeq = 1
                        try:
                            os.makedirs(os.path.dirname(reportFullPath))
                        except WindowsError:
                            pass # dir already exists
                        modelVersReport = ModelVersReport.ModelVersReport(modelTestcases)
                        modelVersReport.diffDTSes(reportFullPath,modelDTSfrom, modelDTSto, 
                                                  assignment=assignment,
                                                  schemaDir=schemaDir)
                        
                        # check for expected elements
                        if expectedEvents:
                            for expectedEvent in expectedEvents.split(","):
                                if expectedEvent not in ("No change", "N.A."):
                                    prefix, sep, localName = expectedEvent.partition(':')
                                    if sep and len(modelVersReport.xmlDocument.findall(
                                                        '//{{{0}}}{1}'.format(
                                                            XbrlConst.verPrefixNS.get(prefix),
                                                            localName))) == 0:
                                        modelTestcases.warning("warning",
                                            "Generated test case %(reportName)s missing expected event %(event)s",
                                            reportName=reportName, 
                                            event=expectedEvent)
                        
                        modelVersReport.close()
                        uriFromParts = uriFrom.split('_')
                        if len(uriFromParts) >= 2:
                            variationId = uriFromParts[1]
                        else:
                            variationId = "_{0:02}".format(variationSeq)
                        for i,testcaseElt in enumerate(testcaseElements):
                            variationElement = etree.SubElement(testcaseElt, "{http://xbrl.org/2008/conformance}variation", 
                                                                attrib={"id": variationId})
                            nameElement = etree.SubElement(variationElement, "{http://xbrl.org/2008/conformance}description")
                            nameElement.text = description
                            ''' (removed per RH 2011/10/04
                            if note:
                                paramElement = etree.SubElement(variationElement, "{http://xbrl.org/2008/conformance}description")
                                paramElement.text = "Note: " + note
                            if useCase:
                                paramElement = etree.SubElement(variationElement, "{http://xbrl.org/2008/conformance}reference")
                                paramElement.set("specification", "versioning-requirements")
                                paramElement.set("useCase", useCase)
                            '''
                            dataElement = etree.SubElement(variationElement, "{http://xbrl.org/2008/conformance}data")
                            if i == 0:  # result is report
                                if expectedEvents:
                                    paramElement = etree.SubElement(dataElement, "{http://xbrl.org/2008/conformance}parameter",
                                                                    attrib={"name":"expectedEvent",
                                                                            "value":expectedEvents.replace(',',' ')},
                                                                    nsmap={"conf":"http://xbrl.org/2008/conformance",
                                                                           None:""})
                                if assignment:
                                    paramElement = etree.SubElement(dataElement, "{http://xbrl.org/2008/conformance}parameter",
                                                                    attrib={"name":"assignment",
                                                                            "value":assignment},
                                                                    nsmap={"conf":"http://xbrl.org/2008/conformance",
                                                                           None:""})
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
                            if i == 1:
                                reportElement.set("readMeFirst","true")
                            reportElement.text = "report/" + reportName
                        variationSeq += 1
            except Exception as err:
                modelTestcases.error("exception",
                    _("Exception: %(error)s, Excel row: %(excelRow)s"),
                    error=err,
                    excelRow=iRow, 
                    exc_info=True)
        
        # add tests-error-code index files to consumption
        for testcaseFile in self.testcaseFiles(testGenDir + os.sep + "tests-error-code"):
            etree.SubElement(testcasesElements[1], "testcase", 
                             attrib={"uri": 
                             testcaseFile[len(testGenDir)+1:].replace("\\","/")} )

        with open(logMessagesFile, "w") as fh:
            fh.writelines(self.logMessages)

        if priorTestcasesDir:
            for i,testcaseFile in enumerate(testcaseFiles):
                with open(testcaseFile, "w", encoding="utf-8") as fh:
                    XmlUtil.writexml(fh, testcaseDocs[i], encoding="utf-8")
        for i,indexFile in enumerate(indexFiles):
            with open(indexFile, "w", encoding="utf-8") as fh:
                XmlUtil.writexml(fh, indexDocs[i], encoding="utf-8")
                
    def testcaseFiles(self, dir, files=None):
        if files is None: files = []
        for file in os.listdir(dir):
            path = dir + os.sep + file
            if path.endswith(".svn"):
                continue
            if path.endswith("-testcase.xml"):
                files.append(path)
            elif os.path.isdir(path): 
                self.testcaseFiles(path, files)
        return files
    
    def runFromXml(self):
        testGenFileName = r"C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\roland test cases\1000-Concepts\index.xml"
        filesource = FileSource.FileSource(testGenFileName)
        startedAt = time.time()
        LogHandler(self) # start logger
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
                    modelDTSfrom = modelDTSto = None
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
                        if modelDTSfrom is not None and modelDTSto is not None:
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

class LogHandler(logging.Handler):
    def __init__(self, cntlr):
        super(LogHandler, self).__init__()
        self.cntlr = cntlr
        self.level = logging.DEBUG
        formatter = logging.Formatter("[%(messageCode)s] %(message)s - %(file)s %(sourceLine)s")
        self.setFormatter(formatter)
        logging.getLogger("arelle").addHandler(self)
    def flush(self):
        ''' Nothing to flush '''
    def emit(self, logRecord):
        self.cntlr.addToLog(self.format(logRecord))      

if __name__ == "__main__":
    main()
