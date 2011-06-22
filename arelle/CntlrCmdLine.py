'''
Created on Oct 3, 2010

This module is Arelle's controller in command line non-interactive mode

(This module can be a pattern for custom integration of Arelle into an application.)

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import gettext, time, datetime
from optparse import OptionParser
from arelle import (Cntlr, FileSource, ModelDocument, XmlUtil, Version,
               ViewCsvDTS, ViewCsvFactList, ViewCsvConcepts, ViewCsvRelationshipSet, ViewCsvTests)
from arelle.Locale import format_string
from arelle.ModelFormulaObject import FormulaOptions

def main():
    gettext.install("arelle")
    usage = "usage: %prog [options]"
    parser = OptionParser(usage, version="Arelle(r) {0}".format(Version.version))
    parser.add_option("-f", "--file", dest="filename",
                      help=_("FILENAME is an entry point, which may be"
                             "an XBRL instance, schema, linkbase file, "
                             "inline XBRL instance, testcase file, "
                             "testcase index file.  FILENAME may be "
                             "a local file or a URI to a web located file."))
    parser.add_option("-d", "--diff", dest="diffFilename",
                      help=_("FILENAME is a second entry point when "
                             "comparing (diffing) two DTSes producing a versioning report."))
    parser.add_option("-r", "--report", dest="versReportFilename",
                      help=_("FILENAME is the filename to save as the versioning report."))
    parser.add_option("-v", "--validate",
                      action="store_true", dest="validate",
                      help=_("Validate the file according to the entry "
                             "file type.  If an XBRL file, it is validated "
                             "according to XBRL validation 2.1, calculation linkbase validation "
                             "if either --calcDecimals or --calcPrecision are specified, and "
                             "SEC Edgar Filing Manual (if --efm selected) or Global Filer Manual "
                             "disclosure system validation (if --gfm=XXX selected). "
                             "If a test suite or testcase, the test case variations "
                             "are individually so validated."))
    parser.add_option("--calcDecimals", action="store_true", dest="calcDecimals",
                      help=_("Specify calculation linkbase validation inferring decimals."))
    parser.add_option("--calcPrecision", action="store_true", dest="calcPrecision",
                      help=_("Specify calculation linkbase validation inferring precision."))
    parser.add_option("--efm", action="store_true", dest="validateEFM",
                      help=_("Select Edgar Filer Manual (U.S. SEC) disclosure system validation."))
    parser.add_option("--gfm", action="store", dest="gfmName",
                      help=_("Specify a Global Filer Manual disclosure system name and"
                             " select disclosure system validation."))
    parser.add_option("--utr", action="store_true", dest="utrValidate",
                      help=_("Select validation with respect to Unit Type Registry."))
    parser.add_option("--csvDTS", action="store", dest="csvDTS",
                      help=_("Write DTS tree into CSVFILE"))
    parser.add_option("--csvFacts", action="store", dest="csvFactList",
                      help=_("Write fact list into CSVFILE"))
    parser.add_option("--csvConcepts", action="store", dest="csvConcepts",
                      help=_("Write concepts into CSVFILE"))
    parser.add_option("--csvPre", action="store", dest="csvPre",
                      help=_("Write presentation linkbase into CSVFILE"))
    parser.add_option("--csvCal", action="store", dest="csvCal",
                      help=_("Write calculation linkbase into CSVFILE"))
    parser.add_option("--csvDim", action="store", dest="csvDim",
                      help=_("Write dimensions (of definition) linkbase into CSVFILE"))
    parser.add_option("--csvTestReport", action="store", dest="csvTestReport",
                      help=_("Write test report of validation (of test cases) into CSVFILE"))
    parser.add_option("--logFile", action="store", dest="logFile",
                      help=_("Write log messages into file, otherwise they go to standard output"))
    parser.add_option("--formulaParamExprResult", action="store_true", dest="formulaParamExprResult", help=_("Specify formula tracing."))
    parser.add_option("--formulaParamInputValue", action="store_true", dest="formulaParamInputValue", help=_("Specify formula tracing."))
    parser.add_option("--formulaCallExprSource", action="store_true", dest="formulaCallExprSource", help=_("Specify formula tracing."))
    parser.add_option("--formulaCallExprCode", action="store_true", dest="formulaCallExprCode", help=_("Specify formula tracing."))
    parser.add_option("--formulaCallExprEval", action="store_true", dest="formulaCallExprEval", help=_("Specify formula tracing."))
    parser.add_option("--formulaCallExprResult", action="store_true", dest="formulaCallExprResult", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarSetExprEval", action="store_true", dest="formulaVarSetExprEval", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarSetExprResult", action="store_true", dest="formulaVarSetExprResult", help=_("Specify formula tracing."))
    parser.add_option("--formulaAsserResultCounts", action="store_true", dest="formulaAsserResultCounts", help=_("Specify formula tracing."))
    parser.add_option("--formulaFormulaRules", action="store_true", dest="formulaFormulaRules", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarsOrder", action="store_true", dest="formulaVarsOrder", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarExpressionSource", action="store_true", dest="formulaVarExpressionSource", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarExpressionCode", action="store_true", dest="formulaVarExpressionCode", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarExpressionEvaluation", action="store_true", dest="formulaVarExpressionEvaluation", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarExpressionResult", action="store_true", dest="formulaVarExpressionResult", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarFiltersResult", action="store_true", dest="formulaVarFiltersResult", help=_("Specify formula tracing."))
    parser.add_option("-a", "--about",
                      action="store_true", dest="about",
                      help=_("Show product version, copyright, and license."))
    
    (options, args) = parser.parse_args()
    if options.about:
        print(_("\narelle(r) {0}\n\n"
                "An open source XBRL platform\n"
                "(c) 2010-2011 Mark V Systems Limited\n"
                "All rights reserved\nhttp://www.arelle.org\nsupport@arelle.org\n\n"
                "Licensed under the Apache License, Version 2.0 (the \"License\"); "
                "you may not \nuse this file except in compliance with the License.  "
                "You may obtain a copy \nof the License at "
                "'http://www.apache.org/licenses/LICENSE-2.0'\n\n"
                "Unless required by applicable law or agreed to in writing, software \n"
                "distributed under the License is distributed on an \"AS IS\" BASIS, \n"
                "WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  \n"
                "See the License for the specific language governing permissions and \n"
                "limitations under the License."
                "\n\nIncludes:"
                "\n   Python(r) (c) 2001-2010 Python Software Foundation"
                "\n   PyParsing (c) 2003-2010 Paul T. McGuire"
                "\n   lxml (c) 2004 Infrae, ElementTree (c) 1999-2004 by Fredrik Lundh"
                "\n   xlrd (c) 2005-2009 Stephen J. Machin, Lingfo Pty Ltd, (c) 2001 D. Giffin, (c) 2000 A. Khan"
                "\n   xlwt (c) 2007 Stephen J. Machin, Lingfo Pty Ltd, (c) 2005 R. V. Kiseliov"
                ).format(Version.version))
    elif len(args) != 0 or options.filename is None:
        parser.error(_("incorrect arguments, please try\n  python CntlrCmdLine.pyw --help"))
    else:
        # parse and run the FILENAME
        CntlrCmdLine().run(options)
        
class CntlrCmdLine(Cntlr.Cntlr):

    def __init__(self):
        super().__init__()
        
    def run(self, options):
        if options.logFile:
            self.messages = []
        else:
            self.messages = None
        
        self.filename = options.filename
        filesource = FileSource.FileSource(self.filename,self)
        if options.validateEFM:
            if options.gfmName:
                self.addToLog(_("[info] both --efm and --gfm validation are requested, proceeding with --efm only"))
            self.modelManager.validateDisclosureSystem = True
            self.modelManager.disclosureSystem.select("efm")
        elif options.gfmName:
            self.modelManager.validateDisclosureSystem = True
            self.modelManager.disclosureSystem.select(options.gfmName)
        else:
            self.modelManager.disclosureSystem.select(None) # just load ordinary mappings
        if options.calcDecimals:
            if options.calcPrecision:
                self.addToLog(_("[info] both --calcDecimals and --calcPrecision validation are requested, proceeding with --calcDecimals only"))
            self.modelManager.validateInferDecimals = True
            self.modelManager.validateCalcLB = True
        elif options.calcPrecision:
            self.modelManager.validateInferDecimals = False
            self.modelManager.validateCalcLB = True
        if options.utrValidate:
            self.modelManager.validateUtr = True
        fo = FormulaOptions()
        if options.formulaParamExprResult:
            fo.traceParameterExpressionResult = True
        if options.formulaParamInputValue:
            fo.traceParameterInputValue = True
        if options.formulaCallExprSource:
            fo.traceCallExpressionSource = True
        if options.formulaCallExprCode:
            fo.traceCallExpressionCode = True
        if options.formulaCallExprEval:
            fo.traceCallExpressionEvaluation = True
        if options.formulaCallExprResult:
            fo.traceCallExpressionResult = True
        if options.formulaVarSetExprEval:
            fo.traceVariableSetExpressionEvaluation = True
        if options.formulaVarSetExprResult:
            fo.traceVariableSetExpressionResult = True
        if options.formulaAsserResultCounts:
            fo.traceAssertionResultCounts = True
        if options.formulaFormulaRules:
            fo.traceFormulaRules = True
        if options.formulaVarsOrder:
            fo.traceVariablesOrder = True
        if options.formulaVarExpressionSource:
            fo.traceVariableExpressionSource = True
        if options.formulaVarExpressionCode:
            fo.traceVariableExpressionCode = True
        if options.formulaVarExpressionEvaluation:
            fo.traceVariableExpressionEvaluation = True
        if options.formulaVarExpressionResult:
            fo.traceVariableExpressionResult = True
        if options.formulaVarFiltersResult:
            fo.traceVariableFiltersResult = True
        self.modelManager.formulaOptions = fo
        timeNow = XmlUtil.dateunionValue(datetime.datetime.now())
        startedAt = time.time()
        modelXbrl = self.modelManager.load(filesource, _("views loading"))
        self.addToLog(format_string(self.modelManager.locale, 
                                    _("[info] loaded in %.2f secs at %s"), 
                                    (time.time() - startedAt, timeNow)))
        
        if options.diffFilename and options.versReportFilename:
            diffFilesource = FileSource.FileSource(self.diffFilename,self)
            startedAt = time.time()
            modelXbrl = self.modelManager.load(diffFilesource, _("views loading"))
            self.addToLog(format_string(self.modelManager.locale, 
                                        _("[info] diff comparison DTS loaded in %.2f secs"), 
                                        time.time() - startedAt))
            startedAt = time.time()
            self.modelManager.compareDTSes(options.versReportFilename)
            self.addToLog(format_string(self.modelManager.locale, 
                                        _("[info] compared in %.2f secs"), 
                                        time.time() - startedAt))
        try:
            if options.validate:
                startedAt = time.time()
                self.modelManager.validate()
                self.addToLog(format_string(self.modelManager.locale, 
                                            _("[info] validated in %.2f secs"), 
                                            time.time() - startedAt))
                if (options.csvTestReport and 
                    self.modelManager.modelXbrl.modelDocument.type in 
                        (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY)):
                    ViewCsvTests.viewTests(self.modelManager.modelXbrl, options.csvTestReport)
                
            if options.csvDTS:
                ViewCsvDTS.viewDTS(modelXbrl, options.csvDTS)
            if options.csvFactList:
                ViewCsvFactList.viewFacts(modelXbrl, options.csvFactList)
            if options.csvConcepts:
                ViewCsvConcepts.viewConcepts(modelXbrl, options.csvConcepts)
            if options.csvPre:
                ViewCsvRelationshipSet.viewRelationshipSet(modelXbrl, options.csvPre, "Presentation", "http://www.xbrl.org/2003/arcrole/parent-child")
            if options.csvCal:
                ViewCsvRelationshipSet.viewRelationshipSet(modelXbrl, options.csvCal, "Calculation", "http://www.xbrl.org/2003/arcrole/summation-item")
            if options.csvDim:
                ViewCsvRelationshipSet.viewRelationshipSet(modelXbrl, options.csvDim, "Dimension", "XBRL-dimensions")
        except (IOError, EnvironmentError) as err:
            self.addToLog(_("[IOError] Failed to save output:\n {0}").format(err))


        if self.messages:
            try:
                with open(options.logFile, "w", encoding="utf-8") as fh:
                    fh.writelines(self.messages)
            except (IOError, EnvironmentError) as err:
                print("Unable to save log to file: " + err)
            
    def addToLog(self, message):
        if self.messages is not None:
            self.messages.append(message + '\n')
        else:
            print(message) # allows printing on standard out
    
    def showStatus(self, message, clearAfter=None):
        pass
    
if __name__ == "__main__":
    main()
