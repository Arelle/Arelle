'''
Created on Oct 3, 2010

This module is Arelle's controller in command line non-interactive mode

(This module can be a pattern for custom integration of Arelle into an application.)

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from __future__ import print_function
from arelle import PythonUtil # define 2.x or 3.x string types
import gettext, time, datetime, os, shlex, sys, traceback
from optparse import OptionParser, SUPPRESS_HELP
from arelle import (Cntlr, FileSource, ModelDocument, XmlUtil, Version,
                    ViewFileDTS, ViewFileFactList, ViewFileFactTable, ViewFileConcepts, 
                    ViewFileFormulae, ViewFileRelationshipSet, ViewFileTests)
from arelle.ModelValue import qname
from arelle.Locale import format_string
from arelle.ModelFormulaObject import FormulaOptions
from arelle.PluginManager import pluginClassMethods
import logging

def main():
    try:
        from arelle import webserver
        hasWebServer = True
    except ImportError:
        hasWebServer = False
    gettext.install("arelle") # needed for options messages
    cntlr = CntlrCmdLine()  # need controller for plug ins to be loaded
    usage = "usage: %prog [options]"
    parser = OptionParser(usage, version="Arelle(r) {0}".format(Version.version))
    parser.add_option("-f", "--file", dest="entrypointFile",
                      help=_("FILENAME is an entry point, which may be "
                             "an XBRL instance, schema, linkbase file, "
                             "inline XBRL instance, testcase file, "
                             "testcase index file.  FILENAME may be "
                             "a local file or a URI to a web located file."))
    # special option for web interfaces to suppress closing an opened modelXbrl
    parser.add_option("--keepOpen", dest="keepOpen", action="store_true", help=SUPPRESS_HELP)
    parser.add_option("-i", "--import", dest="importFiles",
                      help=_("FILENAME is a list of files to import to the DTS, such as "
                             "additional formula or label linkbases.  "
                             "Multiple file names are separated by a '|' character. "))
    parser.add_option("-d", "--diff", dest="diffFile",
                      help=_("FILENAME is a second entry point when "
                             "comparing (diffing) two DTSes producing a versioning report."))
    parser.add_option("-r", "--report", dest="versReportFile",
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
    parser.add_option("--hmrc", action="store_true", dest="validateHMRC",
                      help=_("Select U.K. HMRC disclosure system validation."))
    parser.add_option("--utr", action="store_true", dest="utrValidate",
                      help=_("Select validation with respect to Unit Type Registry."))
    parser.add_option("--labelLang", action="store", dest="labelLang",
                      help=_("Language for labels in following file options (override system settings)"))
    parser.add_option("--labelRole", action="store", dest="labelRole",
                      help=_("Label role for labels in following file options (instead of standard label)"))
    parser.add_option("--DTS", "--csvDTS", action="store", dest="DTSFile",
                      help=_("Write DTS tree into FILE (may be .csv or .html)"))
    parser.add_option("--facts", "--csvFacts", action="store", dest="factsFile",
                      help=_("Write fact list into FILE"))
    parser.add_option("--factListCols", action="store", dest="factListCols",
                      help=_("Columns for fact list file"))
    parser.add_option("--factTable", "--csvFactTable", action="store", dest="factTableFile",
                      help=_("Write fact table into FILE"))
    parser.add_option("--concepts", "--csvConcepts", action="store", dest="conceptsFile",
                      help=_("Write concepts into FILE"))
    parser.add_option("--pre", "--csvPre", action="store", dest="preFile",
                      help=_("Write presentation linkbase into FILE"))
    parser.add_option("--cal", "--csvCal", action="store", dest="calFile",
                      help=_("Write calculation linkbase into FILE"))
    parser.add_option("--dim", "--csvDim", action="store", dest="dimFile",
                      help=_("Write dimensions (of definition) linkbase into FILE"))
    parser.add_option("--formulae", "--htmlFormulae", action="store", dest="formulaeFile",
                      help=_("Write formulae linkbase into FILE"))
    parser.add_option("--testReport", "--csvTestReport", action="store", dest="testReport",
                      help=_("Write test report of validation (of test cases) into FILE"))
    parser.add_option("--logFile", action="store", dest="logFile",
                      help=_("Write log messages into file, otherwise they go to standard output.  " 
                             "If file ends in .xml it is xml-formatted, otherwise it is text. "))
    parser.add_option("--parameters", action="store", dest="parameters", help=_("Specify parameters for formula and validation (name=value[,name=value])."))
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
    parser.add_option("--formulaVarFilterWinnowing", action="store_true", dest="formulaVarFilterWinnowing", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarFiltersResult", action="store_true", dest="formulaVarFiltersResult", help=_("Specify formula tracing."))
    if hasWebServer:
        parser.add_option("--webserver", action="store", dest="webserver",
                          help=_("start web server on host:port for REST and web access, e.g., --webserver locahost:8080."))
    for optionsExtender in pluginClassMethods("CntlrCmdLine.Options"):
        optionsExtender(parser)
    parser.add_option("-a", "--about",
                      action="store_true", dest="about",
                      help=_("Show product version, copyright, and license."))
    
    envArgs = os.getenv("ARELLE_ARGS")
    if envArgs:
        argvFromEnv = shlex.split(envArgs)
        (options, args) = parser.parse_args(argvFromEnv)
    else:
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
                "{1}"
                ).format(Version.version,
                         _("\n   Bottle (c) 2011 Marcel Hellkamp") if hasWebServer else ""))
    elif len(args) != 0 or (options.entrypointFile is None and (not hasWebServer or options.webserver is None)):
        parser.error(_("incorrect arguments, please try\n  python CntlrCmdLine.pyw --help"))
    elif hasWebServer and options.webserver:
        if any((options.entrypointFile, options.importFiles, options.diffFile, options.versReportFile,
                options.validate, options.calcDecimals, options.calcPrecision, options.validateEFM, options.validateHMRC, options.gfmName,
                options.utrValidate, options.DTSFile, options.factsFile, options.factListCols, options.factTableFile,
                options.conceptsFile, options.preFile, options.calFile, options.dimFile, options.formulaeFile,
                options.logFile, options.formulaParamExprResult, options.formulaParamInputValue,
                options.formulaCallExprSource, options.formulaCallExprCode, options.formulaCallExprEval,
                options.formulaCallExprResult, options.formulaVarSetExprEval, options.formulaVarSetExprResult,
                options.formulaAsserResultCounts, options.formulaFormulaRules, options.formulaVarsOrder,
                options.formulaVarExpressionSource, options.formulaVarExpressionCode, options.formulaVarExpressionEvaluation,
                options.formulaVarExpressionResult, options.formulaVarFiltersResult)):
            parser.error(_("incorrect arguments with --webserver, please try\n  python CntlrCmdLine.pyw --help"))
        else:
            from arelle import CntlrWebMain
            cntlr.startLogging(logFileName='logToBuffer')
            CntlrWebMain.startWebserver(cntlr, options)
    else:
        # parse and run the FILENAME
        cntlr.startLogging(logFileName=options.logFile if options.logFile else "logToPrint",
                           logFormat="[%(messageCode)s] %(message)s - %(file)s")
        cntlr.run(options)
        
class CntlrCmdLine(Cntlr.Cntlr):

    def __init__(self, logFileName=None):
        super(CntlrCmdLine, self).__init__()
        
    def run(self, options, sourceZipStream=None):
        self.entrypointFile = options.entrypointFile
        filesource = FileSource.openFileSource(self.entrypointFile, self, sourceZipStream)
        if options.validateEFM:
            if options.gfmName:
                self.addToLog(_("both --efm and --gfm validation are requested, proceeding with --efm only"),
                              messageCode="info", file=self.entrypointFile)
            self.modelManager.validateDisclosureSystem = True
            self.modelManager.disclosureSystem.select("efm")
        elif options.gfmName:
            self.modelManager.validateDisclosureSystem = True
            self.modelManager.disclosureSystem.select(options.gfmName)
        elif options.validateHMRC:
            self.modelManager.validateDisclosureSystem = True
            self.modelManager.disclosureSystem.select("hmrc")
        else:
            self.modelManager.disclosureSystem.select(None) # just load ordinary mappings
        if options.calcDecimals:
            if options.calcPrecision:
                self.addToLog(_("both --calcDecimals and --calcPrecision validation are requested, proceeding with --calcDecimals only"),
                              messageCode="info", file=self.entrypointFile)
            self.modelManager.validateInferDecimals = True
            self.modelManager.validateCalcLB = True
        elif options.calcPrecision:
            self.modelManager.validateInferDecimals = False
            self.modelManager.validateCalcLB = True
        if options.utrValidate:
            self.modelManager.validateUtr = True
        fo = FormulaOptions()
        if options.parameters:
            fo.parameterValues = dict(((qname(key, noPrefixIsNoNamespace=True),(None,value)) 
                                       for param in options.parameters.split(',') 
                                       for key,sep,value in (param.partition('='),) ) )   
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
        if options.formulaVarFilterWinnowing:
            fo.traceVariableFilterWinnowing = True
        if options.formulaVarFiltersResult:
            fo.traceVariableFiltersResult = True
        self.modelManager.formulaOptions = fo
        timeNow = XmlUtil.dateunionValue(datetime.datetime.now())
        startedAt = time.time()
        modelDiffReport = None
        success = True
        modelXbrl = None
        try:
            modelXbrl = self.modelManager.load(filesource, _("views loading"))
        except Exception as err:
            self.addToLog(_("[Exception] Failed to complete request: \n{0} \n{1}").format(
                        err,
                        traceback.format_tb(sys.exc_info()[2])))
            success = False    # loading errors, don't attempt to utilize loaded DTS
        if modelXbrl and modelXbrl.modelDocument:
            self.addToLog(format_string(self.modelManager.locale, 
                                        _("loaded in %.2f secs at %s"), 
                                        (time.time() - startedAt, timeNow)), 
                                        messageCode="info", file=self.entrypointFile)
            if options.importFiles:
                for importFile in options.importFiles.split("|"):
                    ModelDocument.load(modelXbrl, importFile.strip())
                    self.addToLog(format_string(self.modelManager.locale, 
                                                _("imported in %.2f secs at %s"), 
                                                (time.time() - startedAt, timeNow)), 
                                                messageCode="info", file=importFile)
                if modelXbrl.errors:
                    success = False    # loading errors, don't attempt to utilize loaded DTS
        else:
            success = False
        if success and options.diffFile and options.versReportFile:
            diffFilesource = FileSource.FileSource(options.diffFile,self)
            startedAt = time.time()
            modelXbrl2 = self.modelManager.load(diffFilesource, _("views loading"))
            if modelXbrl2.errors:
                if not options.keepOpen:
                    modelXbrl2.close()
                success = False
            else:
                self.addToLog(format_string(self.modelManager.locale, 
                                            _("diff comparison DTS loaded in %.2f secs"), 
                                            time.time() - startedAt), 
                                            messageCode="info", file=self.entrypointFile)
                startedAt = time.time()
                modelDiffReport = self.modelManager.compareDTSes(options.versReportFile)
                self.addToLog(format_string(self.modelManager.locale, 
                                            _("compared in %.2f secs"), 
                                            time.time() - startedAt), 
                                            messageCode="info", file=self.entrypointFile)
        if success:
            try:
                if options.validate:
                    startedAt = time.time()
                    self.modelManager.validate()
                    self.addToLog(format_string(self.modelManager.locale, 
                                                _("validated in %.2f secs"), 
                                                time.time() - startedAt),
                                                messageCode="info", file=self.entrypointFile)
                    if (options.testReport and 
                        self.modelManager.modelXbrl.modelDocument.type in 
                            (ModelDocument.Type.TESTCASESINDEX, 
                             ModelDocument.Type.TESTCASE, 
                             ModelDocument.Type.REGISTRY)):
                        ViewFileTests.viewTests(self.modelManager.modelXbrl, options.testReport)
                    
                if options.DTSFile:
                    ViewFileDTS.viewDTS(modelXbrl, options.DTSFile)
                if options.factsFile:
                    ViewFileFactList.viewFacts(modelXbrl, options.factsFile, labelrole=options.labelRole, lang=options.labelLang, cols=options.factListCols)
                if options.factTableFile:
                    ViewFileFactTable.viewFacts(modelXbrl, options.factTableFile, labelrole=options.labelRole, lang=options.labelLang)
                if options.conceptsFile:
                    ViewFileConcepts.viewConcepts(modelXbrl, options.conceptsFile, labelrole=options.labelRole, lang=options.labelLang)
                if options.preFile:
                    ViewFileRelationshipSet.viewRelationshipSet(modelXbrl, options.preFile, "Presentation Linkbase", "http://www.xbrl.org/2003/arcrole/parent-child", labelrole=options.labelRole, lang=options.labelLang)
                if options.calFile:
                    ViewFileRelationshipSet.viewRelationshipSet(modelXbrl, options.calFile, "Calculation Linkbase", "http://www.xbrl.org/2003/arcrole/summation-item", labelrole=options.labelRole, lang=options.labelLang)
                if options.dimFile:
                    ViewFileRelationshipSet.viewRelationshipSet(modelXbrl, options.dimFile, "Dimensions", "XBRL-dimensions", labelrole=options.labelRole, lang=options.labelLang)
                if options.formulaeFile:
                    ViewFileFormulae.viewFormulae(modelXbrl, options.formulaeFile, "Formulae", lang=options.labelLang)
                for pluginXbrlMethod in pluginClassMethods("CntlrCmdLine.Xbrl.Run"):
                    pluginXbrlMethod(self, options, modelXbrl)
                                        
            except (IOError, EnvironmentError) as err:
                self.addToLog(_("[IOError] Failed to save output:\n {0}").format(err))
                success = False
            except Exception as err:
                self.addToLog(_("[Exception] Failed to complete request: \n{0} \n{1}").format(
                            err,
                            traceback.format_tb(sys.exc_info()[2])))
                success = False
        if not options.keepOpen:
            if modelDiffReport:
                modelDiffReport.close()
            elif modelXbrl:
                modelXbrl.close()
        return success

if __name__ == "__main__":
    '''
    if '--COMserver' in sys.argv:
        from arelle import CntlrComServer
        CntlrComServer.main()
    else:
        main()
    '''
    main()

