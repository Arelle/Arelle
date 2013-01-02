'''
Created on Oct 3, 2010

This module is Arelle's controller in command line non-interactive mode

(This module can be a pattern for custom integration of Arelle into an application.)

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import PythonUtil # define 2.x or 3.x string types
import gettext, time, datetime, os, shlex, sys, traceback
from optparse import OptionParser, SUPPRESS_HELP
from arelle import (Cntlr, FileSource, ModelDocument, XmlUtil, Version,
                    ViewFileDTS, ViewFileFactList, ViewFileFactTable, ViewFileConcepts, 
                    ViewFileFormulae, ViewFileRelationshipSet, ViewFileTests, ModelManager)
from arelle.ModelValue import qname
from arelle.Locale import format_string
from arelle.ModelFormulaObject import FormulaOptions
from arelle.PluginManager import pluginClassMethods
from arelle.WebCache import proxyTuple
import logging

def main():
    """Main program to initiate application from command line or as a separate process (e.g, java Runtime.getRuntime().exec).  May perform
    a command line request, or initiate a web server on specified local port.
       
       :param argv: Command line arguments.  (Currently supported arguments can be displayed by the parameter *--help*.)
       :type message: [str]
       """
    envArgs = os.getenv("ARELLE_ARGS")
    if envArgs:
        args = shlex.split(envArgs)
    else:
        args = None # defaults to sys.argv[1:]
        
    gettext.install("arelle") # needed for options messages
    parseAndRun(args)
       
def parseAndRun(args):
    """interface used by Main program and py.test (arelle_test.py)
    """
    try:
        from arelle import webserver
        hasWebServer = True
    except ImportError:
        hasWebServer = False
    cntlr = CntlrCmdLine()  # need controller for plug ins to be loaded
    usage = "usage: %prog [options]"
    
    parser = OptionParser(usage, version="Arelle(r) {0}".format(Version.version))
    parser.add_option("-f", "--file", dest="entrypointFile",
                      help=_("FILENAME is an entry point, which may be "
                             "an XBRL instance, schema, linkbase file, "
                             "inline XBRL instance, testcase file, "
                             "testcase index file.  FILENAME may be "
                             "a local file or a URI to a web located file."))
    parser.add_option("--username", dest="username",
                      help=_("user name if needed (with password) for web file retrieval"))
    parser.add_option("--password", dest="password",
                      help=_("password if needed (with user name) for web retrieval"))
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
                             "are individually so validated. "
                             "If formulae are present they will be validated and run unless --formula=none is specified. "
                             ))
    parser.add_option("--calcDecimals", action="store_true", dest="calcDecimals",
                      help=_("Specify calculation linkbase validation inferring decimals."))
    parser.add_option("--calcdecimals", action="store_true", dest="calcDecimals", help=SUPPRESS_HELP)
    parser.add_option("--calcPrecision", action="store_true", dest="calcPrecision",
                      help=_("Specify calculation linkbase validation inferring precision."))
    parser.add_option("--calcprecision", action="store_true", dest="calcPrecision", help=SUPPRESS_HELP)
    parser.add_option("--efm", action="store_true", dest="validateEFM",
                      help=_("Select Edgar Filer Manual (U.S. SEC) disclosure system validation."))
    parser.add_option("--gfm", action="store", dest="gfmName",
                      help=_("Specify a Global Filer Manual disclosure system name and"
                             " select disclosure system validation."))
    parser.add_option("--disclosureSystem", action="store", dest="gfmName",
                      help=_("Specify a disclosure system name and"
                             " select disclosure system validation."))
    parser.add_option("--hmrc", action="store_true", dest="validateHMRC",
                      help=_("Select U.K. HMRC disclosure system validation."))
    parser.add_option("--utr", action="store_true", dest="utrValidate",
                      help=_("Select validation with respect to Unit Type Registry."))
    parser.add_option("--infoset", action="store_true", dest="infosetValidate",
                      help=_("Select validation with respect testcase infosets."))
    parser.add_option("--labelLang", action="store", dest="labelLang",
                      help=_("Language for labels in following file options (override system settings)"))
    parser.add_option("--labellang", action="store", dest="labelLang", help=SUPPRESS_HELP)
    parser.add_option("--labelRole", action="store", dest="labelRole",
                      help=_("Label role for labels in following file options (instead of standard label)"))
    parser.add_option("--labelrole", action="store", dest="labelRole", help=SUPPRESS_HELP)
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
    parser.add_option("--testreport", "--csvtestreport", action="store", dest="testReport", help=SUPPRESS_HELP)
    parser.add_option("--testReportCols", action="store", dest="testReportCols",
                      help=_("Columns for test report file"))
    parser.add_option("--testreportcols", action="store", dest="testReportCols", help=SUPPRESS_HELP)
    parser.add_option("--logFile", action="store", dest="logFile",
                      help=_("Write log messages into file, otherwise they go to standard output.  " 
                             "If file ends in .xml it is xml-formatted, otherwise it is text. "))
    parser.add_option("--logfile", action="store", dest="logFile", help=SUPPRESS_HELP)
    parser.add_option("--logFormat", action="store", dest="logFormat",
                      help=_("Logging format for messages capture, otherwise default is \"[%(messageCode)s] %(message)s - %(file)s\"."))
    parser.add_option("--logformat", action="store", dest="logFormat", help=SUPPRESS_HELP)
    parser.add_option("--logLevel", action="store", dest="logLevel",
                      help=_("Minimum level for messages capture, otherwise the message is ignored.  " 
                             "Current order of levels are debug, info, info-semantic, warning, warning-semantic, warning, assertion-satisfied, inconsistency, error-semantic, assertion-not-satisfied, and error. "))
    parser.add_option("--loglevel", action="store", dest="logLevel", help=SUPPRESS_HELP)
    parser.add_option("--logLevelFilter", action="store", dest="logLevelFilter",
                      help=_("Regular expression filter for logLevel.  " 
                             "(E.g., to not match *-semantic levels, logLevelFilter=(?!^.*-semantic$)(.+). "))
    parser.add_option("--loglevelfilter", action="store", dest="logLevelFilter", help=SUPPRESS_HELP)
    parser.add_option("--logCodeFilter", action="store", dest="logCodeFilter",
                      help=_("Regular expression filter for log message code."))
    parser.add_option("--logcodefilter", action="store", dest="logCodeFilter", help=SUPPRESS_HELP)
    parser.add_option("--parameters", action="store", dest="parameters", help=_("Specify parameters for formula and validation (name=value[,name=value])."))
    parser.add_option("--parameterSeparator", action="store", dest="parameterSeparator", help=_("Specify parameters separator string (if other than comma)."))
    parser.add_option("--parameterseparator", action="store", dest="parameterSeparator", help=SUPPRESS_HELP)
    parser.add_option("--formula", choices=("validate", "run", "none"), dest="formulaAction", 
                      help=_("Specify formula action: "
                             "validate - validate only, without running, "
                             "run - validate and run, or "
                             "none - prevent formula validation or running when also specifying -v or --validate.  "
                             "if this option is not specified, -v or --validate will validate and run formulas if present"))
    parser.add_option("--formulaParamExprResult", action="store_true", dest="formulaParamExprResult", help=_("Specify formula tracing."))
    parser.add_option("--formulaParamInputValue", action="store_true", dest="formulaParamInputValue", help=_("Specify formula tracing."))
    parser.add_option("--formulaCallExprSource", action="store_true", dest="formulaCallExprSource", help=_("Specify formula tracing."))
    parser.add_option("--formulaCallExprCode", action="store_true", dest="formulaCallExprCode", help=_("Specify formula tracing."))
    parser.add_option("--formulaCallExprEval", action="store_true", dest="formulaCallExprEval", help=_("Specify formula tracing."))
    parser.add_option("--formulaCallExprResult", action="store_true", dest="formulaCallExprResult", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarSetExprEval", action="store_true", dest="formulaVarSetExprEval", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarSetExprResult", action="store_true", dest="formulaVarSetExprResult", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarSetTiming", action="store_true", dest="timeVariableSetEvaluation", help=_("Specify showing times of variable set evaluation."))
    parser.add_option("--formulaAsserResultCounts", action="store_true", dest="formulaAsserResultCounts", help=_("Specify formula tracing."))
    parser.add_option("--formulaFormulaRules", action="store_true", dest="formulaFormulaRules", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarsOrder", action="store_true", dest="formulaVarsOrder", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarExpressionSource", action="store_true", dest="formulaVarExpressionSource", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarExpressionCode", action="store_true", dest="formulaVarExpressionCode", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarExpressionEvaluation", action="store_true", dest="formulaVarExpressionEvaluation", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarExpressionResult", action="store_true", dest="formulaVarExpressionResult", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarFilterWinnowing", action="store_true", dest="formulaVarFilterWinnowing", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarFiltersResult", action="store_true", dest="formulaVarFiltersResult", help=_("Specify formula tracing."))
    parser.add_option("--uiLang", action="store", dest="uiLang",
                      help=_("Language for user interface (override system settings, such as program messages).  Does not save setting."))
    parser.add_option("--uilang", action="store", dest="uiLang", help=SUPPRESS_HELP)
    parser.add_option("--proxy", action="store", dest="proxy",
                      help=_("Modify and re-save proxy settings configuration.  " 
                             "Enter 'system' to use system proxy setting, 'none' to use no proxy, "
                             "'http://[user[:password]@]host[:port]' "
                             " (e.g., http://192.168.1.253, http://example.com:8080, http://joe:secret@example.com:8080), "
                             " or 'show' to show current setting, ." ))
    parser.add_option("--internetConnectivity", choices=("online", "offline"), dest="internetConnectivity", 
                      help=_("Specify internet connectivity: online or offline"))
    parser.add_option("--internetconnectivity", action="store", dest="internetConnectivity", help=SUPPRESS_HELP)
    parser.add_option("--internetTimeout", type="int", dest="internetTimeout", 
                      help=_("Specify internet connection timeout in seconds (0 means unlimited)."))
    parser.add_option("--internettimeout", type="int", action="store", dest="internetTimeout", help=SUPPRESS_HELP)
    parser.add_option("--plugins", action="store", dest="plugins",
                      help=_("Modify and re-save plug-in configuration.  " 
                             "Enter 'show' to show current plug-in configuration, or '|' separated modules: "
                             "+url to add plug-in by its url or filename, ~name to reload a plug-in by its name, -name to remove a plug-in by its name, "
                             " (e.g., '+http://arelle.org/files/hello_web.py', '+C:\Program Files\Arelle\examples\plugin\hello_dolly.py' to load, "
                             "~Hello Dolly to reload, -Hello Dolly to remove)" ))
    parser.add_option("--abortOnMajorError", action="store_true", dest="abortOnMajorError", help=_("Abort process on major error, such as when load is unable to find an entry or discovered file."))
    parser.add_option("--collectProfileStats", action="store_true", dest="collectProfileStats", help=_("Collect profile statistics, such as timing of validation activities and formulae."))
    if hasWebServer:
        parser.add_option("--webserver", action="store", dest="webserver",
                          help=_("start web server on host:port[:server] for REST and web access, e.g., --webserver locahost:8080, "
                                 "or specify nondefault a server name, such as cherrypy, --webserver locahost:8080:cherrypy"))
    for optionsExtender in pluginClassMethods("CntlrCmdLine.Options"):
        optionsExtender(parser)
    parser.add_option("-a", "--about",
                      action="store_true", dest="about",
                      help=_("Show product version, copyright, and license."))
    
    (options, leftoverArgs) = parser.parse_args(args)
    if options.about:
        print(_("\narelle(r) {0}\n\n"
                "An open source XBRL platform\n"
                "(c) 2010-2013 Mark V Systems Limited\n"
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
                "\n   Python(r) (c) 2001-2012 Python Software Foundation"
                "\n   PyParsing (c) 2003-2012 Paul T. McGuire"
                "\n   lxml (c) 2004 Infrae, ElementTree (c) 1999-2004 by Fredrik Lundh"
                "\n   xlrd (c) 2005-2009 Stephen J. Machin, Lingfo Pty Ltd, (c) 2001 D. Giffin, (c) 2000 A. Khan"
                "\n   xlwt (c) 2007 Stephen J. Machin, Lingfo Pty Ltd, (c) 2005 R. V. Kiseliov"
                "{1}"
                ).format(Version.version,
                         _("\n   Bottle (c) 2011 Marcel Hellkamp") if hasWebServer else ""))
    elif len(leftoverArgs) != 0 or (options.entrypointFile is None and 
                                    ((not options.proxy) and (not options.plugins)
                                     and (not hasWebServer or options.webserver is None))):
        parser.error(_("incorrect arguments, please try\n  python CntlrCmdLine.pyw --help"))
    elif hasWebServer and options.webserver:
        if any((options.entrypointFile, options.importFiles, options.diffFile, options.versReportFile,
                options.validate, options.calcDecimals, options.calcPrecision, options.validateEFM, options.validateHMRC, options.gfmName,
                options.utrValidate, options.infosetValidate, options.DTSFile, options.factsFile, options.factListCols, options.factTableFile,
                options.conceptsFile, options.preFile, options.calFile, options.dimFile, options.formulaeFile,
                options.logFile, options.logFormat, options.logLevel, options.logLevelFilter, options.logCodeFilter, options.formulaParamExprResult, options.formulaParamInputValue,
                options.formulaCallExprSource, options.formulaCallExprCode, options.formulaCallExprEval,
                options.formulaCallExprResult, options.formulaVarSetExprEval, options.formulaVarSetExprResult,
                options.formulaAsserResultCounts, options.formulaFormulaRules, options.formulaVarsOrder,
                options.formulaVarExpressionSource, options.formulaVarExpressionCode, options.formulaVarExpressionEvaluation,
                options.formulaVarExpressionResult, options.formulaVarFiltersResult,
                options.proxy, options.plugins)):
            parser.error(_("incorrect arguments with --webserver, please try\n  python CntlrCmdLine.pyw --help"))
        else:
            cntlr.startLogging(logFileName='logToBuffer')
            from arelle import CntlrWebMain
            CntlrWebMain.startWebserver(cntlr, options)
    else:
        # parse and run the FILENAME
        cntlr.startLogging(logFileName=(options.logFile or "logToPrint"),
                           logFormat=(options.logFormat or "[%(messageCode)s] %(message)s - %(file)s"),
                           logLevel=(options.logLevel or "DEBUG"),
                           logLevelFilter=options.logLevelFilter,
                           logCodeFilter=options.logCodeFilter)
        cntlr.run(options)
        
        return cntlr
        
class CntlrCmdLine(Cntlr.Cntlr):
    """
    .. class:: CntlrCmdLin()
    
    Initialization sets up for platform via Cntlr.Cntlr.
    """

    def __init__(self, logFileName=None):
        super(CntlrCmdLine, self).__init__()
        
    def run(self, options, sourceZipStream=None):
        """Process command line arguments or web service request, such as to load and validate an XBRL document, or start web server.
        
        When a web server has been requested, this method may be called multiple times, once for each web service (REST) request that requires processing.
        Otherwise (when called for a command line request) this method is called only once for the command line arguments request.
           
        :param options: OptionParser options from parse_args of main argv arguments (when called from command line) or corresponding arguments from web service (REST) request.
        :type options: optparse.Values
        """
        if options.uiLang: # set current UI Lang (but not config setting)
            self.setUiLanguage(options.uiLang)
        if options.proxy:
            if options.proxy != "show":
                proxySettings = proxyTuple(options.proxy)
                self.webCache.resetProxies(proxySettings)
                self.config["proxySettings"] = proxySettings
                self.saveConfig()
                self.addToLog(_("Proxy configuration has been set."), messageCode="info")
            useOsProxy, urlAddr, urlPort, user, password = self.config.get("proxySettings", proxyTuple("none"))
            if useOsProxy:
                self.addToLog(_("Proxy configured to use {0}.").format(
                    _('Microsoft Windows Internet Settings') if sys.platform.startswith("win")
                    else (_('Mac OS X System Configuration') if sys.platform in ("darwin", "macos")
                          else _('environment variables'))), messageCode="info")
            elif urlAddr:
                self.addToLog(_("Proxy setting: http://{0}{1}{2}{3}{4}").format(
                    user if user else "",
                    ":****" if password else "",
                    "@" if (user or password) else "",
                    urlAddr,
                    ":{0}".format(urlPort) if urlPort else ""), messageCode="info")
            else:
                self.addToLog(_("Proxy is disabled."), messageCode="info")
        if options.plugins:
            from arelle import PluginManager
            resetPlugins = False
            for pluginCmd in options.plugins.split('|'):
                cmd = pluginCmd.strip()
                if cmd != "show":
                    if cmd.startswith("+"):
                        moduleInfo = PluginManager.addPluginModule(cmd[1:])
                        if moduleInfo:
                            self.addToLog(_("Addition of plug-in {0} successful.").format(moduleInfo.get("name")), 
                                          messageCode="info", file=moduleInfo.get("moduleURL"))
                            resetPlugins = True
                        else:
                            self.addToLog(_("Unable to load plug-in."), messageCode="info", file=cmd[1:])
                    elif cmd.startswith("~"):
                        if PluginManager.reloadPluginModule(cmd[1:]):
                            self.addToLog(_("Reload of plug-in successful."), messageCode="info", file=cmd[1:])
                            resetPlugins = True
                        else:
                            self.addToLog(_("Unable to reload plug-in."), messageCode="info", file=cmd[1:])
                    elif cmd.startswith("-"):
                        if PluginManager.removePluginModule(cmd[1:]):
                            self.addToLog(_("Deletion of plug-in successful."), messageCode="info", file=cmd[1:])
                            resetPlugins = True
                        else:
                            self.addToLog(_("Unable to delete plug-in."), messageCode="info", file=cmd[1:])
                    else:
                        self.addToLog(_("Plug-in action not recognized (may need +uri or [~-]module."), messageCode="info", file=cmd)
                if resetPlugins:
                    PluginManager.reset()
                    PluginManager.save(self)
            self.addToLog(_("Plug-in modules:"), messageCode="info")
            for i, moduleItem in enumerate(sorted(PluginManager.pluginConfig.get("modules", {}).items())):
                moduleInfo = moduleItem[1]
                self.addToLog(_("Plug-in: {0}; author: {1}; version: {2}; status: {3}; date: {4}; description: {5}; license {6}.").format(
                              moduleItem[0], moduleInfo.get("author"), moduleInfo.get("version"), moduleInfo.get("status"),
                              moduleInfo.get("fileDate"), moduleInfo.get("description"), moduleInfo.get("license")),
                              messageCode="info", file=moduleInfo.get("moduleURL"))
        if options.proxy or options.plugins:
            if not options.entrypointFile:
                return True # success
        self.username = options.username
        self.password = options.password
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
        if options.infosetValidate:
            self.modelManager.validateInfoset = True
        if options.abortOnMajorError:
            self.modelManager.abortOnMajorError = True
        if options.collectProfileStats:
            self.modelManager.collectProfileStats = True
        if options.internetConnectivity == "offline":
            self.webCache.workOffline = True
        elif options.internetConnectivity == "online":
            self.webCache.workOffline = False
        if options.internetTimeout is not None:
            self.webCache.timeout = (options.internetTimeout or None)  # use None if zero specified to disable timeout
        fo = FormulaOptions()
        if options.parameters:
            parameterSeparator = (options.parameterSeparator or ',')
            fo.parameterValues = dict(((qname(key, noPrefixIsNoNamespace=True),(None,value)) 
                                       for param in options.parameters.split(parameterSeparator) 
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
        if options.timeVariableSetEvaluation:
            fo.timeVariableSetEvaluation = True
        if options.formulaVarFilterWinnowing:
            fo.traceVariableFilterWinnowing = True
        if options.formulaVarFiltersResult:
            fo.traceVariableFiltersResult = True
        if options.formulaVarFiltersResult:
            fo.traceVariableFiltersResult = True
        self.modelManager.formulaOptions = fo
        timeNow = XmlUtil.dateunionValue(datetime.datetime.now())
        firstStartedAt = startedAt = time.time()
        modelDiffReport = None
        success = True
        modelXbrl = None
        try:
            modelXbrl = self.modelManager.load(filesource, _("views loading"))
        except ModelDocument.LoadingException:
            pass
        except Exception as err:
            self.addToLog(_("[Exception] Failed to complete request: \n{0} \n{1}").format(
                        err,
                        traceback.format_tb(sys.exc_info()[2])))
            success = False    # loading errors, don't attempt to utilize loaded DTS
        if modelXbrl and modelXbrl.modelDocument:
            loadTime = time.time() - startedAt
            modelXbrl.profileStat(_("load"), loadTime)
            self.addToLog(format_string(self.modelManager.locale, 
                                        _("loaded in %.2f secs at %s"), 
                                        (loadTime, timeNow)), 
                                        messageCode="info", file=self.entrypointFile)
            for pluginXbrlMethod in pluginClassMethods("CntlrCmdLine.Xbrl.Loaded"):
                pluginXbrlMethod(self, options, modelXbrl)
            if options.importFiles:
                for importFile in options.importFiles.split("|"):
                    fileName = importFile.strip()
                    if sourceZipStream is not None and not (fileName.startswith('http://') or os.path.isabs(fileName)):
                        fileName = os.path.dirname(modelXbrl.uri) + os.sep + fileName # make relative to sourceZipStream
                    ModelDocument.load(modelXbrl, fileName)
                    loadTime = time.time() - startedAt
                    self.addToLog(format_string(self.modelManager.locale, 
                                                _("import in %.2f secs at %s"), 
                                                (loadTime, timeNow)), 
                                                messageCode="info", file=importFile)
                    modelXbrl.profileStat(_("import"), loadTime)
                if modelXbrl.errors:
                    success = False    # loading errors, don't attempt to utilize loaded DTS
        else:
            success = False
        if success and options.diffFile and options.versReportFile:
            try:
                diffFilesource = FileSource.FileSource(options.diffFile,self)
                startedAt = time.time()
                modelXbrl2 = self.modelManager.load(diffFilesource, _("views loading"))
                if modelXbrl2.errors:
                    if not options.keepOpen:
                        modelXbrl2.close()
                    success = False
                else:
                    loadTime = time.time() - startedAt
                    modelXbrl.profileStat(_("load"), loadTime)
                    self.addToLog(format_string(self.modelManager.locale, 
                                                _("diff comparison DTS loaded in %.2f secs"), 
                                                loadTime), 
                                                messageCode="info", file=self.entrypointFile)
                    startedAt = time.time()
                    modelDiffReport = self.modelManager.compareDTSes(options.versReportFile)
                    diffTime = time.time() - startedAt
                    modelXbrl.profileStat(_("diff"), diffTime)
                    self.addToLog(format_string(self.modelManager.locale, 
                                                _("compared in %.2f secs"), 
                                                diffTime), 
                                                messageCode="info", file=self.entrypointFile)
            except ModelDocument.LoadingException:
                success = False
            except Exception as err:
                success = False
                self.addToLog(_("[Exception] Failed to doad diff file: \n{0} \n{1}").format(
                            err,
                            traceback.format_tb(sys.exc_info()[2])))
        if success:
            try:
                modelXbrl = self.modelManager.modelXbrl
                hasFormulae = modelXbrl.hasFormulae
                if options.validate:
                    startedAt = time.time()
                    if options.formulaAction: # don't automatically run formulas
                        modelXbrl.hasFormulae = False
                    self.modelManager.validate()
                    if options.formulaAction: # restore setting
                        modelXbrl.hasFormulae = hasFormulae
                    self.addToLog(format_string(self.modelManager.locale, 
                                                _("validated in %.2f secs"), 
                                                time.time() - startedAt),
                                                messageCode="info", file=self.entrypointFile)
                if options.formulaAction in ("validate", "run"):  # do nothing here if "none"
                    from arelle import ValidateXbrlDimensions, ValidateFormula
                    startedAt = time.time()
                    if not options.validate:
                        ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl)
                    # setup fresh parameters from formula optoins
                    modelXbrl.parameters = fo.typedParameters()
                    ValidateFormula.validate(modelXbrl, compileOnly=(options.formulaAction != "run"))
                    self.addToLog(format_string(self.modelManager.locale, 
                                                _("formula validation and execution in %.2f secs")
                                                if options.formulaAction == "run"
                                                else _("formula validation only in %.2f secs"), 
                                                time.time() - startedAt),
                                                messageCode="info", file=self.entrypointFile)
                    

                if (options.testReport and 
                    self.modelManager.modelXbrl.modelDocument.type in 
                        (ModelDocument.Type.TESTCASESINDEX, 
                         ModelDocument.Type.TESTCASE, 
                         ModelDocument.Type.REGISTRY)):
                    ViewFileTests.viewTests(self.modelManager.modelXbrl, options.testReport, options.testReportCols)
                    
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
        modelXbrl.profileStat(_("total"), time.time() - firstStartedAt)
        if options.collectProfileStats and modelXbrl:
            modelXbrl.logProfileStats()
        if not options.keepOpen:
            if modelDiffReport:
                self.modelManager.close(modelDiffReport)
            elif modelXbrl:
                self.modelManager.close(modelXbrl)
        self.username = self.password = None #dereference password
        return success

    # default web authentication password
    def internet_user_password(self, host, realm):
        return (self.username, self.password)

if __name__ == "__main__":
    '''
    if '--COMserver' in sys.argv:
        from arelle import CntlrComServer
        CntlrComServer.main()
    else:
        main()
    '''
    main()

