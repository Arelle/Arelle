'''
This module is Arelle's controller in command line non-interactive mode

(This module can be a pattern for custom integration of Arelle into an application.)

See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
from arelle import PythonUtil, ValidateDuplicateFacts  # define 2.x or 3.x string types
import gettext, time, datetime, os, shlex, sys, traceback, fnmatch, threading, json, logging, platform
from optparse import OptionGroup, OptionParser, SUPPRESS_HELP
import regex as re
from arelle import (Cntlr, FileSource, ModelDocument, RenderingEvaluator, XmlUtil, XbrlConst, Version,
                    ViewFileDTS, ViewFileFactList, ViewFileFactTable, ViewFileConcepts,
                    ViewFileFormulae, ViewFileRelationshipSet, ViewFileTests, ViewFileRssFeed,
                    ViewFileRoleTypes,
                    ModelManager)
from arelle.RuntimeOptions import RuntimeOptions, RuntimeOptionsException
from arelle.BetaFeatures import BETA_FEATURES_AND_DESCRIPTIONS
from arelle.ModelValue import qname
from arelle.Locale import format_string, setApplicationLocale, setDisableRTL
from arelle.ModelFormulaObject import FormulaOptions
from arelle import PluginManager
from arelle.PluginManager import pluginClassMethods
from arelle.SocketUtils import INTERNET_CONNECTIVITY, OFFLINE
from arelle.typing import TypeGetText
from arelle.UrlUtil import isHttpUrl
from arelle.Version import copyrightLabel
from arelle.WebCache import proxyTuple
from arelle.SystemInfo import getSystemInfo, getSystemWordSize, hasWebServer, isCGI, isGAE, PlatformOS
from pprint import pprint
import logging
from lxml import etree
import glob
win32file = win32api = win32process = pywintypes = None
STILL_ACTIVE = 259 # MS Windows process status constants
PROCESS_QUERY_INFORMATION = 0x400
DISABLE_PERSISTENT_CONFIG_OPTION = "--disablePersistentConfig"
UILANG_OPTION = '--uiLang'
_: TypeGetText


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
        args = sys.argv[1:]
    setApplicationLocale()
    gettext.install("arelle")
    parseAndRun(args)


def wsgiApplication(extraArgs=[]): # for example call wsgiApplication(["--plugins=EdgarRenderer"])
    return parseAndRun( ["--webserver=::wsgi"] + extraArgs )


def parseAndRun(args):
    """interface used by Main program and py.test (arelle_test.py)
    """

    runtimeOptions, arellePluginModules = parseArgs(args)
    cntlr = configAndRunCntlr(runtimeOptions, arellePluginModules)
    return cntlr


def parseArgs(args):
    """
    Parses the command line arguments and generates runtimeOptions and arellePluginModules
    :param args: Command Line arguments
    :return: runtimeOptions which is an object of options specified
    and
    arellePluginModules which is a dictionary of commands and moduleInfos
    """
    uiLang = None
    # Check if there is UI language override to use the selected language
    # for help and error messages...
    for _i, _arg in enumerate(args):
        if _arg.startswith((f'{UILANG_OPTION}=', f'{UILANG_OPTION.lower()}=')):
            uiLang = _arg[9:]
            break
        elif _arg in (UILANG_OPTION, UILANG_OPTION.lower()) and _i + 1 < len(args):
            uiLang = args[_i+1]
            break
    # Check if the config cache needs to be disabled prior to initializing the cntlr
    disable_persistent_config = bool({DISABLE_PERSISTENT_CONFIG_OPTION, DISABLE_PERSISTENT_CONFIG_OPTION.lower()} & set(args))
    cntlr = createCntlrAndPreloadPlugins(uiLang, disable_persistent_config, {})  # This Cntlr is needed for translations and to enable the web cache.  The cntlr is not used outside the parse function
    usage = "usage: %prog [options]"
    parser = OptionParser(usage,
                          version="Arelle(r) {0} ({1}bit)".format(Version.__version__, getSystemWordSize()),
                          conflict_handler="resolve") # allow reloading plug-in options without errors
    parser.add_option("-f", "--file", dest="entrypointFile",
                      help=_("FILENAME is an entry point, which may be "
                             "an XBRL instance, schema, linkbase file, "
                             "inline XBRL instance, testcase file, "
                             "testcase index file.  FILENAME may be "
                             "a local file or a URI to a web located file.  "
                             "For multiple instance filings may be | separated file names or JSON list "
                             "of file/parameter dicts [{\"file\":\"filepath\"}, {\"file\":\"file2path\"} ...]."))
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
                             "SEC EDGAR Filing Manual (if --efm selected) or Global Filer Manual "
                             "disclosure system validation (if --gfm=XXX selected). "
                             "If a test suite or testcase, the test case variations "
                             "are individually so validated. "
                             "If formulae are present they will be validated and run unless --formula=none is specified. "
                             ))
    parser.add_option("--validateDuplicateFacts", "--validateduplicatefacts",
                      choices=[a.value for a in ValidateDuplicateFacts.DUPLICATE_TYPE_ARG_MAP],
                      dest="validateDuplicateFacts",
                      help=_("Select which types of duplicates should trigger warnings."))
    parser.add_option("--deduplicateFacts", "--deduplicatefacts",
                      choices=[a.value for a in ValidateDuplicateFacts.DeduplicationType],
                      dest="deduplicateFacts",
                      help=_("When using '--saveDeduplicatedInstance' to save a deduplicated instance, check for duplicates of this type. "
                             "Defaults to 'complete'."))
    parser.add_option("--saveDeduplicatedInstance", "--savededuplicatedinstance",
                      dest="saveDeduplicatedInstance",
                      help=_("Save an instance document with duplicates of the provided type ('--deduplicateFacts') deduplicated."))
    parser.add_option("--noValidateTestcaseSchema", "--novalidatetestcaseschema", action="store_false", dest="validateTestcaseSchema", default=True,
                      help=_("Validate testcases against their schemas."))
    betaGroup = OptionGroup(parser, "Beta Features",
                        "Caution: these are beta features, use these options at your own risk.")
    for featureName, featureDescription in BETA_FEATURES_AND_DESCRIPTIONS.items():
        assert featureName.startswith('beta'), 'All beta options must start with "beta"'
        betaGroup.add_option(f'--{featureName}', f'--{featureName.lower()}', action="store_true", default=False, help=featureDescription)
    parser.add_option_group(betaGroup)
    parser.add_option("--calc", action="store", dest="calcs",
                      help=_("Specify calculations validations: "
                             "none - no calculations validation, "
                             #"xbrl21precision - pre-2010 xbrl v2.1 calculations linkbase inferring precision, "
                             "c10 or xbrl21 - Calc 1.0 (XBRL 2.1) calculations, "
                             "c10d or xbrl21-dedup - Calc 1.0 (XBRL 2.1) calculations with de-duplication, "
                             "c11r or round-to-nearest - Calc 1.1 round-to-nearest mode, "
                             "c11t or truncation - Calc 1.1 truncation mode"
                             ))
    parser.add_option("--calcDecimals", "--calcdecimals", action="store_true", dest="calcDecimals",
                      help=_("Deprecated - XBRL v2.1 calculation linkbase validation inferring decimals."))
    parser.add_option("--calcPrecision", "--calcprecision", action="store_true", dest="calcPrecision",
                      help=_("Deprecated - pre-2010 XBRL v2.1 calculation linkbase validation inferring precision."))
    parser.add_option("--calcDeduplicate", "--calcdeduplicate", action="store_true", dest="calcDeduplicate",
                      help=_("Deprecaated -  de-duplication of consistent facts when performing calculation validation, chooses most accurate fact."))
    parser.add_option("--efm", action="store_true", dest="validateEFM",
                      help=_("Select Edgar Filer Manual (U.S. SEC) disclosure system validation (strict)."))
    parser.add_option("--efm-skip-calc-tree", action="store_false", default=True, dest="validateEFMCalcTree",
                      help=_("Skip walking of calculation tree during EFM validation."))
    parser.add_option("--gfm", action="store", dest="disclosureSystemName", help=SUPPRESS_HELP)
    parser.add_option("--disclosureSystem", "--disclosuresystem", action="store", dest="disclosureSystemName",
                      help=_("Specify a disclosure system name and"
                             " select disclosure system validation.  "
                             "Enter --disclosureSystem=help for list of names or help-verbose for list of names and descriptions. "))
    parser.add_option("--hmrc", action="store_true", dest="validateHMRC",
                      help=_("Select U.K. HMRC disclosure system validation."))
    parser.add_option("--utr", action="store_true", dest="utrValidate",
                      help=_("Select validation with respect to Unit Type Registry."))
    parser.add_option("--utrUrl", "--utrurl", action="store", dest="utrUrl",
                      help=_("Override disclosure systems Unit Type Registry location (URL or file path)."))
    parser.add_option("--infoset", action="store_true", dest="infosetValidate",
                      help=_("Select validation with respect testcase infosets."))
    parser.add_option("--labelLang", "--labellang", action="store", dest="labelLang",
                      help=_("Language for labels in following file options (override system settings)"))
    parser.add_option("--disableRtl", action="store_true", dest="disableRtl", default=False,
                       help=_("Flag to disable reversing string read order for right to left languages, useful for some locale settings"))
    parser.add_option("--labelRole", "--labelrole", action="store", dest="labelRole",
                      help=_("Label role for labels in following file options (instead of standard label)"))
    parser.add_option("--DTS", "--csvDTS", action="store", dest="DTSFile",
                      help=_("Write DTS tree into FILE (may be .csv or .html)"))
    parser.add_option("--facts", "--csvFacts", action="store", dest="factsFile",
                      help=_("Write fact list into FILE"))
    parser.add_option("--factListCols", action="store", dest="factListCols",
                      help=_("Columns for fact list file"))
    parser.add_option("--factTable", "--csvFactTable", action="store", dest="factTableFile",
                      help=_("Write fact table into FILE"))
    parser.add_option("--factTableCols", action="store", dest="factTableCols",
                      help=_("Columns for fact table file"))
    parser.add_option("--concepts", "--csvConcepts", action="store", dest="conceptsFile",
                      help=_("Write concepts into FILE"))
    parser.add_option("--pre", "--csvPre", action="store", dest="preFile",
                      help=_("Write presentation linkbase into FILE"))
    parser.add_option("--table", "--csvTable", action="store", dest="tableFile",
                      help=_("Write table linkbase into FILE"))
    parser.add_option("--cal", "--csvCal", action="store", dest="calFile",
                      help=_("Write calculation linkbase into FILE"))
    parser.add_option("--dim", "--csvDim", action="store", dest="dimFile",
                      help=_("Write dimensions (of definition) linkbase into FILE"))
    parser.add_option("--anch", action="store", dest="anchFile",
                      help=_("Write anchoring relationships (of definition) linkbase into FILE"))
    parser.add_option("--formulae", "--htmlFormulae", action="store", dest="formulaeFile",
                      help=_("Write formulae linkbase into FILE"))
    parser.add_option("--viewArcrole", "--viewarcrole", action="store", dest="viewArcrole",
                      help=_("Write linkbase relationships for viewArcrole into viewFile"))
    parser.add_option("--viewFile", "--viewfile", action="store", dest="viewFile",
                      help=_("Write linkbase relationships for viewArcrole into viewFile"))
    parser.add_option("--relationshipCols", "--relationshipcols", action="store", dest="relationshipCols",
                      help=_("Extra columns for relationship file (comma or space separated: Name, Namespace, LocalName, Documentation and References)"))
    parser.add_option("--roleTypes", "--roletypes", action="store", dest="roleTypesFile",
                      help=_("Write defined role types into FILE"))
    parser.add_option("--arcroleTypes", "--arcroletypes", action="store", dest="arcroleTypesFile",
                      help=_("Write defined arcrole types into FILE"))
    parser.add_option("--testReport", "--csvTestReport", "--testreport", "--csvtestreport", action="store", dest="testReport",
                      help=_("Write test report of validation (of test cases) into FILE"))
    parser.add_option("--testReportCols", "--testreportcols", action="store", dest="testReportCols",
                      help=_("Columns for test report file"))
    parser.add_option("--rssReport", "--rssreport", action="store", dest="rssReport",
                      help=_("Write RSS report into FILE"))
    parser.add_option("--rssReportCols", "--rssreportcols", action="store", dest="rssReportCols",
                      help=_("Columns for RSS report file"))
    parser.add_option("--skipDTS", "--skipdts", action="store_true", dest="skipDTS",
                      help=_("Skip DTS activities (loading, discovery, validation), useful when an instance needs only to be parsed."))
    parser.add_option("--skipLoading", "--skiploading", action="store", dest="skipLoading",
                      help=_("Skip loading discovered or schemaLocated files matching pattern (unix-style file name patterns separated by '|'), useful when not all linkbases are needed."))
    parser.add_option("--logFile", "--logfile", action="store", dest="logFile",
                      help=_("Write log messages into file, otherwise they go to standard output.  "
                             "If file ends in .xml it is xml-formatted, otherwise it is text. "))
    parser.add_option("--logFileMode", "--logfilemode", action="store", dest="logFileMode",
                      help=_("Write log file mode, a=append if existing (default), w=overwrite if existing. "))
    parser.add_option("--logFormat", "--logformat", action="store", dest="logFormat",
                      help=_("Logging format for messages capture, otherwise default is \"[%(messageCode)s] %(message)s - %(file)s\"."))
    parser.add_option("--logLevel", "--loglevel", action="store", dest="logLevel",
                      help=_("Minimum level for messages capture, otherwise the message is ignored.  "
                             "Current order of levels are debug, info, info-semantic, warning, warning-semantic, warning, assertion-satisfied, inconsistency, error-semantic, assertion-not-satisfied, and error. "))
    parser.add_option("--logLevelFilter", "--loglevelfilter", action="store", dest="logLevelFilter",
                      help=_("Regular expression filter for logLevel.  "
                             "(E.g., to not match *-semantic levels, logLevelFilter=(?!^.*-semantic$)(.+). "))
    parser.add_option("--logCodeFilter", "--logcodefilter", action="store", dest="logCodeFilter",
                      help=_("Regular expression filter for log message code."))
    parser.add_option("--logTextMaxLength", "--logtextmaxlength", action="store", dest="logTextMaxLength", type="int",
                      help=_("Log file text field max length override."))
    parser.add_option("--logRefObjectProperties", "--logrefobjectproperties", action="store_true", dest="logRefObjectProperties",
                      help=_("Log reference object properties (default)."), default=True)
    parser.add_option("--logNoRefObjectProperties", "--lognorefobjectproperties", action="store_false", dest="logRefObjectProperties",
                      help=_("Do not log reference object properties."))
    parser.add_option("--statusPipe", action="store", dest="statusPipe", help=SUPPRESS_HELP)
    parser.add_option("--monitorParentProcess", action="store", dest="monitorParentProcess", help=SUPPRESS_HELP)
    parser.add_option("--outputAttribution", "--outputattribution", action="store", dest="outputAttribution", help=SUPPRESS_HELP)
    parser.add_option("--showOptions", action="store_true", dest="showOptions", help=SUPPRESS_HELP)
    parser.add_option("--parameters", action="store", dest="parameters", help=_("Specify parameters for formula and validation (name=value[,name=value])."))
    parser.add_option("--parameterSeparator", "--parameterseparator", action="store", dest="parameterSeparator", help=_("Specify parameters separator string (if other than comma)."))
    parser.add_option("--formula", choices=("validate", "run", "none"), dest="formulaAction",
                      help=_("Specify formula action: "
                             "validate - validate only, without running, "
                             "run - validate and run, or "
                             "none - prevent formula validation or running when also specifying -v or --validate.  "
                             "if this option is not specified, -v or --validate will validate and run formulas if present"))
    parser.add_option("--formulaParamExprResult", "--formulaparamexprresult", action="store_true", dest="formulaParamExprResult", help=_("Specify formula tracing."))
    parser.add_option("--formulaParamInputValue", "--formulaparaminputvalue", action="store_true", dest="formulaParamInputValue", help=_("Specify formula tracing."))
    parser.add_option("--formulaCallExprSource", "--formulacallexprsource", action="store_true", dest="formulaCallExprSource", help=_("Specify formula tracing."))
    parser.add_option("--formulaCallExprCode", "--formulacallexprcode", action="store_true", dest="formulaCallExprCode", help=_("Specify formula tracing."))
    parser.add_option("--formulaCallExprEval", "--formulacallexpreval", action="store_true", dest="formulaCallExprEval", help=_("Specify formula tracing."))
    parser.add_option("--formulaCallExprResult", "--formulacallexprtesult", action="store_true", dest="formulaCallExprResult", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarSetExprEval", "--formulavarsetexpreval", action="store_true", dest="formulaVarSetExprEval", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarSetExprResult", "--formulavarsetexprresult", action="store_true", dest="formulaVarSetExprResult", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarSetTiming", "--formulavarsettiming", action="store_true", dest="timeVariableSetEvaluation", help=_("Specify showing times of variable set evaluation."))
    parser.add_option("--formulaAsserResultCounts", "--formulaasserresultcounts", action="store_true", dest="formulaAsserResultCounts", help=_("Specify formula tracing."))
    parser.add_option("--formulaSatisfiedAsser", "--formulasatisfiedasser", action="store_true", dest="formulaSatisfiedAsser", help=_("Specify formula tracing."))
    parser.add_option("--formulaUnsatisfiedAsser", "--formulaunsatisfiedasser", action="store_true", dest="formulaUnsatisfiedAsser", help=_("Specify formula tracing."))
    parser.add_option("--formulaUnsatisfiedAsserError", "--formulaunsatisfiedassererror", action="store_true", dest="formulaUnsatisfiedAsserError", help=_("Specify formula tracing."))
    parser.add_option("--formulaUnmessagedUnsatisfiedAsser", "--formulaunmessagedunsatisfiedasser", action="store_true", dest="formulaUnmessagedUnsatisfiedAsser", help=_("Specify trace messages for unsatisfied assertions with no formula messages."))
    parser.add_option("--formulaFormulaRules", "--formulaformularules", action="store_true", dest="formulaFormulaRules", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarsOrder", "--formulavarsorder", action="store_true", dest="formulaVarsOrder", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarExpressionSource", "--formulavarexpressionsource", action="store_true", dest="formulaVarExpressionSource", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarExpressionCode", "--formulavarexpressioncode", action="store_true", dest="formulaVarExpressionCode", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarExpressionEvaluation", "--formulavarexpressionevaluation", action="store_true", dest="formulaVarExpressionEvaluation", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarExpressionResult", "--formulavarexpressionresult", action="store_true", dest="formulaVarExpressionResult", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarFilterWinnowing", "--formulavarfilterwinnowing", action="store_true", dest="formulaVarFilterWinnowing", help=_("Specify formula tracing."))
    parser.add_option("--formulaVarFiltersResult", "--formulavarfiltersresult", action="store_true", dest="formulaVarFiltersResult", help=_("Specify formula tracing."))
    parser.add_option("--testcaseResultsCaptureWarnings", "--testcaseresultscapturewarnings", action="store_true", dest="testcaseResultsCaptureWarnings",
                      help=_("For testcase variations capture warning results, default is inconsistency or warning if there is any warning expected result.  "))
    parser.add_option("--testcaseResultOptions", choices=("match-any", "match-all"), action="store", dest="testcaseResultOptions",
                      help=_("For testcase results, default is match any expected result, options to match any or match all expected result(s).  "))
    parser.add_option("--formulaRunIDs", "--formularunids", action="store", dest="formulaRunIDs", help=_("Specify formula/assertion IDs to run, separated by a '|' character, or a regex expression."))
    parser.add_option("--formulaCompileOnly", "--formulacompileonly", action="store_true", dest="formulaCompileOnly", help=_("Specify formula are to be compiled but not executed."))
    parser.add_option("--formulaCacheSize", "--formulacachesize", action="store", dest="formulaCacheSize", help=_("Specify the number of fact aspect combinations to cache during formula evaluations. Negative numbers have no limit. (10_000_000 is default)"))
    parser.add_option(UILANG_OPTION, UILANG_OPTION.lower(), action="store", dest="uiLang",
                      help=_("Language for user interface (override system settings, such as program messages).  Does not save setting.  Requires locale country code, e.g. en-GB or en-US."))
    parser.add_option("--proxy", action="store", dest="proxy",
                      help=_("Modify and re-save proxy settings configuration.  "
                             "Enter 'system' to use system proxy setting, 'none' to use no proxy, "
                             "'http://[user[:password]@]host[:port]' "
                             " (e.g., http://192.168.1.253, http://example.com:8080, http://joe:secret@example.com:8080), "
                             " or 'show' to show current setting, ." ))
    parser.add_option(f"--{INTERNET_CONNECTIVITY}", f"--{INTERNET_CONNECTIVITY.lower()}", choices=("online", OFFLINE), dest="internetConnectivity",
                      help=_("Specify internet connectivity: online or offline"))
    parser.add_option("--internetTimeout", "--internettimeout", type="int", dest="internetTimeout",
                      help=_("Specify internet connection timeout in seconds (0 means unlimited)."))
    parser.add_option("--internetRecheck", "--internetrecheck", choices=("weekly", "daily", "never", "hourly", "quarter-hourly"), action="store", dest="internetRecheck",
                      help=_("Specify rechecking for newer cache files 'daily', 'weekly', 'monthly' or 'never' ('weekly' is default)"))
    parser.add_option("--internetLogDownloads", "--internetlogdownloads", action="store_true", dest="internetLogDownloads",
                      help=_("Log info message for downloads to web cache."))
    parser.add_option("--noCertificateCheck", "--nocertificatecheck", action="store_true", dest="noCertificateCheck",
                      help=_("Specify no checking of internet secure connection certificate"))
    parser.add_option("--httpsRedirectCache", "--httpsredirectcache", action="store_true", dest="httpsRedirectCache",
                      help=_("Treat http and https schemes interchangeably when looking up files from the webcache"))
    parser.add_option("--httpUserAgent", "--httpuseragent", action="store", dest="httpUserAgent",
                      help=_("Specify non-standard http header User-Agent value"))
    parser.add_option(DISABLE_PERSISTENT_CONFIG_OPTION, DISABLE_PERSISTENT_CONFIG_OPTION.lower(), action="store_true", dest="disablePersistentConfig", help=_("Prohibits Arelle from reading and writing a config to the local cache."))
    parser.add_option("--xdgConfigHome", action="store", dest="xdgConfigHome",
                      help=_("Specify non-standard location for configuration and cache files (overrides environment parameter XDG_CONFIG_HOME)."))
    parser.add_option("--plugins", action="store", dest="plugins",
                      help=_("Specify plug-in configuration for this invocation.  "
                             "Enter 'show' to confirm plug-in configuration.  "
                             "Commands show, and module urls are '|' separated: "
                             "url specifies a plug-in by its url or filename, "
                             "relative URLs are relative to installation plug-in directory, "
                             R" (e.g., 'http://arelle.org/files/hello_web.py', 'C:\Program Files\Arelle\examples\plugin\hello_dolly.py' to load, "
                             "or ../examples/plugin/hello_dolly.py for relative use of examples directory) "
                             "Local python files do not require .py suffix, e.g., hello_dolly without .py is sufficient, "
                             "Packaged plug-in urls are their directory's url (e.g., --plugins EdgarRenderer or --plugins xbrlDB).  " ))
    parser.add_option("--packages", "--package", action="append", dest="packages",
                      help=_("Load taxonomy packages. Option can be repeated for multiple files. "
                             "If a directory is specified, all .zip files in the directory will be loaded. "
                             "(Package settings from GUI are no longer shared with cmd line operation. "
                             "Cmd line package settings are not persistent.)  " ))
    parser.add_option("--packageManifestName", action="store", dest="packageManifestName",
                      help=_("Provide non-standard archive manifest file name pattern (e.g., *taxonomyPackage.xml).  "
                             "Uses unix file name pattern matching.  "
                             "Multiple manifest files are supported in archive (such as oasis catalogs).  "
                             "(Replaces search for either .taxonomyPackage.xml or catalog.xml).  " ))
    parser.add_option("--abortOnMajorError", action="store_true", dest="abortOnMajorError", help=_("Abort process on major error, such as when load is unable to find an entry or discovered file."))
    parser.add_option("--showEnvironment", "--showenvironment", action="store_true", dest="showEnvironment", help=_("Show Arelle's config and cache directory and host OS environment parameters."))
    parser.add_option("--collectProfileStats", action="store_true", dest="collectProfileStats", help=_("Collect profile statistics, such as timing of validation activities and formulae."))
    if hasWebServer():
        parser.add_option("--webserver", action="store", dest="webserver",
                          help=_("start web server on host:port[:server] for REST and web access, e.g., --webserver locahost:8080, "
                                 "or specify nondefault a server name, such as cherrypy, --webserver locahost:8080:cherrypy. "
                                 "(It is possible to specify options to be defaults for the web server, such as disclosureSystem and validations, but not including file names.) "))
    pluginOptionsIndex = len(parser.option_list)
    pluginOptionsGroupIndex = len(parser.option_groups)

    # install any dynamic plugins so their command line options can be parsed if present
    arellePluginModules = {}
    for i, arg in enumerate(args):
        if arg.startswith('--plugin'): # allow singular or plural (option must simply be non-ambiguous
            if len(arg) > 9 and arg[9] == '=':
                preloadPlugins = arg[10:]
            elif i < len(args) - 1:
                preloadPlugins = args[i+1]
            else:
                preloadPlugins = ""
            for pluginCmd in preloadPlugins.split('|'):
                cmd = pluginCmd.strip()
                if cmd not in ("show", "temp") and len(cmd) > 0 and cmd[0] not in ('-', '~', '+'):
                    moduleInfo = PluginManager.addPluginModule(cmd)
                    if moduleInfo:
                        arellePluginModules[cmd] = moduleInfo
                        PluginManager.reset()
            break
    # add plug-in options
    for optionsExtender in pluginClassMethods("CntlrCmdLine.Options"):
        optionsExtender(parser)
    pluginLastOptionIndex = len(parser.option_list)
    pluginLastOptionsGroupIndex = len(parser.option_groups)
    parser.add_option("-a", "--about",
                      action="store_true", dest="about",
                      help=_("Show product version, copyright, and license."))
    parser.add_option("--diagnostics", action="store_true", dest="diagnostics",
                      help=_("output system diagnostics information"))

    if not args and isGAE():
        args = ["--webserver=::gae"]
    elif isCGI():
        args = ["--webserver=::cgi"]
    elif PlatformOS.getPlatformOS() == PlatformOS.WINDOWS:
        # if called from java on Windows any empty-string arguments are lost, see:
        # http://bugs.java.com/view_bug.do?bug_id=6518827
        # insert needed arguments
        sourceArgs = args
        args = []
        namedOptions = set()
        optionsWithArg = set()
        for option in parser.option_list:
            names = str(option).split('/')
            namedOptions.update(names)
            if option.action == "store":
                optionsWithArg.update(names)
        priorArg = None
        for arg in sourceArgs:
            if priorArg in optionsWithArg and arg in namedOptions:
                # probable java/MSFT interface bug 6518827
                args.append('')  # add empty string argument
            # remove quoting if arguments quoted according to http://bugs.java.com/view_bug.do?bug_id=6518827
            if r'\"' in arg:  # e.g., [{\"foo\":\"bar\"}] -> [{"foo":"bar"}]
                arg = arg.replace(r'\"', '"')
            args.append(arg)
            priorArg = arg

    (options, leftoverArgs) = parser.parse_args(args)
    if options.about:
        print(_("\narelle(r) {version} ({wordSize}bit {platform})\n\n"
                          "An open source XBRL platform\n"
                          "{copyrightLabel}\n"
                          "http://www.arelle.org\nsupport@arelle.org\n\n"
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
                          "\n   Python(r) {pythonVersion} (c) 2001-2013 Python Software Foundation"
                          "\n   PyParsing (c) 2003-2013 Paul T. McGuire"
                          "\n   lxml {lxmlVersion} (c) 2004 Infrae, ElementTree (c) 1999-2004 by Fredrik Lundh"
                          "{bottleCopyright}"
                          "\n   May include installable plug-in modules with author-specific license terms").format(
            version=Version.__version__,
            wordSize=getSystemWordSize(),
            platform=platform.machine(),
            copyrightLabel=copyrightLabel,
            pythonVersion=f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}',
            lxmlVersion=f'{etree.LXML_VERSION[0]}.{etree.LXML_VERSION[1]}.{etree.LXML_VERSION[2]}',
            bottleCopyright="\n   Bottle (c) 2011-2013 Marcel Hellkamp" if hasWebServer() else ""
        ))
        parser.exit()  # Printing the message in parser.exit sends it to stderr NOT stdout
    elif options.diagnostics:
        pprint(getSystemInfo())
        parser.exit()
    elif options.disclosureSystemName in ("help", "help-verbose"):
        text = _("Disclosure system choices: \n{0}").format(' \n'.join(cntlr.modelManager.disclosureSystem.dirlist(options.disclosureSystemName)))
        try:
            print(text)
            parser.exit()
        except UnicodeEncodeError:
            print(text.encode("ascii", "replace").decode("ascii"))
            parser.exit()
    elif len(leftoverArgs) != 0 and (not hasWebServer() or options.webserver is None):
        parser.error(_("unrecognized arguments: {}").format(', '.join(leftoverArgs)))
    pluginOptionDestinations = {
        option.dest
        for option in parser.option_list[pluginOptionsIndex:pluginLastOptionIndex]
    }
    for optGroup in parser.option_groups[pluginOptionsGroupIndex:pluginLastOptionsGroupIndex]:
        for groupOption in optGroup.option_list:
            pluginOptionDestinations.add(groupOption.dest)
    baseOptions = {}
    pluginOptions = {}
    for optionName, optionValue in vars(options).items():
        if optionName in pluginOptionDestinations:
            pluginOptions[optionName] = optionValue
        else:
            baseOptions[optionName] = optionValue
    try:
        runtimeOptions = RuntimeOptions(pluginOptions=pluginOptions, **baseOptions)
    except RuntimeOptionsException as e:
        parser.error(f"{e}, please try\n python CntlrCmdLine.py --help")
    return runtimeOptions, arellePluginModules


def createCntlrAndPreloadPlugins(uiLang, disablePersistentConfig, arellePluginModules):
    """
    This function creates a cntlr and preloads all the necessary plugins.
    :param uiLang: The UI Language
    :param disablePersistentConfig: flag to determine if persistent configs should be ignored
    :param arellePluginModules: a dictionary of commands and moduleInfos
    :return: cntlr
    """
    cntlr = CntlrCmdLine(uiLang=uiLang, disable_persistent_config=disablePersistentConfig)
    if arellePluginModules:
        for cmd, moduleInfo in arellePluginModules.items():
            cntlr.preloadedPlugins[cmd] = moduleInfo
    return cntlr


def configAndRunCntlr(options, arellePluginModules):
    """
    This function creates and configures a controller based off an options dataclass and
    :param options: RuntimeOptions dataclass
    :param arellePluginModules: a dictionary of commands and moduleInfos
    :return: cntlr
    """
    cntlr = createCntlrAndPreloadPlugins(options.uiLang, options.disablePersistentConfig, arellePluginModules)
    if options.webserver:
        cntlr.startLogging(logFileName='logToBuffer',
                           logTextMaxLength=options.logTextMaxLength,
                           logRefObjectProperties=options.logRefObjectProperties)
        cntlr.postLoggingInit()
        from arelle import CntlrWebMain
        app = CntlrWebMain.startWebserver(cntlr, options)
        if options.webserver == '::wsgi':
            return app
    else:
        cntlr.startLogging(logFileName=(options.logFile or "logToPrint"),
                           logFileMode=options.logFileMode,
                           logFormat=(options.logFormat or "[%(messageCode)s] %(message)s - %(file)s"),
                           logLevel=(options.logLevel or "DEBUG"),
                           logToBuffer=getattr(options, "logToBuffer", False),
                           logTextMaxLength=options.logTextMaxLength,  # e.g., used by EdgarRenderer to require buffered logging
                           logRefObjectProperties=options.logRefObjectProperties)
        cntlr.postLoggingInit()  # Cntlr options after logging is started
        cntlr.run(options)
        return cntlr


def filesourceEntrypointFiles(filesource, entrypointFiles=[], inlineOnly=False):
    if filesource.isArchive:
        if filesource.isTaxonomyPackage:  # if archive is also a taxonomy package, activate mappings
            filesource.loadTaxonomyPackageMappings()
        del entrypointFiles[:] # clear out archive from entrypointFiles
        # attempt to find inline XBRL files before instance files, .xhtml before probing others (ESMA)
        for _archiveFile in (filesource.dir or ()): # .dir might be none if IOerror
            if _archiveFile.endswith(".xhtml") or _archiveFile.endswith(".html"):
                filesource.select(_archiveFile)
                if ModelDocument.Type.identify(filesource, filesource.url) in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):
                    entrypointFiles.append({"file":filesource.url})
        urlsByType = {}
        if not entrypointFiles:
            for _archiveFile in (filesource.dir or ()): # .dir might be none if IOerror
                filesource.select(_archiveFile)
                identifiedType = ModelDocument.Type.identify(filesource, filesource.url)
                if identifiedType in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.HTML):
                    urlsByType.setdefault(identifiedType, []).append(filesource.url)
        # use inline instances, if any, else non-inline instances
        for identifiedType in ((ModelDocument.Type.INLINEXBRL,) if inlineOnly else (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INSTANCE)):
            for url in urlsByType.get(identifiedType, []):
                entrypointFiles.append({"file":url})
            if entrypointFiles:
                if identifiedType == ModelDocument.Type.INLINEXBRL:
                    for pluginXbrlMethod in pluginClassMethods("InlineDocumentSet.Discovery"):
                        pluginXbrlMethod(filesource, entrypointFiles) # group into IXDS if plugin feature is available
                break # found inline (or non-inline) entrypoint files, don't look for any other type
        # for ESEF non-consolidated xhtml documents accept an xhtml entry point
        if not entrypointFiles and not inlineOnly:
            for url in urlsByType.get(ModelDocument.Type.HTML, []):
                entrypointFiles.append({"file":url})


    elif os.path.isdir(filesource.url):
        del entrypointFiles[:] # clear list
        for _file in os.listdir(filesource.url):
            _path = os.path.join(filesource.url, _file)
            if os.path.isfile(_path) and ModelDocument.Type.identify(filesource, _path) in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):
                entrypointFiles.append({"file":_path})
    return entrypointFiles

class ParserForDynamicPlugins:
    def __init__(self, options):
        self.options = options
    def add_option(self, *args, **kwargs):
        if 'dest' in kwargs:
            _dest = kwargs['dest']
            if not hasattr(self.options, _dest):
                setattr(self.options, _dest, kwargs.get('default',None))

class CntlrCmdLine(Cntlr.Cntlr):
    """
    .. class:: CntlrCmdLin()

    Initialization sets up for platform via Cntlr.Cntlr.
    """

    def __init__(self, logFileName=None, uiLang=None, disable_persistent_config=False):
        super(CntlrCmdLine, self).__init__(hasGui=False, uiLang=uiLang, disable_persistent_config=disable_persistent_config)
        self.preloadedPlugins =  {}

    def run(self, options, sourceZipStream=None, responseZipStream=None) -> bool:
        """Process command line arguments or web service request, such as to load and validate an XBRL document, or start web server.

        When a web server has been requested, this method may be called multiple times, once for each web service (REST) request that requires processing.
        Otherwise (when called for a command line request) this method is called only once for the command line arguments request.

        :param options: OptionParser options from parse_args of main argv arguments (when called from command line) or corresponding arguments from web service (REST) request.
        :type options: optparse.Values
        """
        for b in BETA_FEATURES_AND_DESCRIPTIONS.keys():
            self.betaFeatures[b] = getattr(options, b)
        if options.statusPipe or options.monitorParentProcess:
            try:
                global win32file, win32api, win32process, pywintypes
                import win32file, win32api, win32process, pywintypes
            except ImportError: # win32 not installed
                self.addToLog("--statusPipe {} cannot be installed, packages for win32 missing".format(options.statusPipe))
                options.statusPipe = options.monitorParentProcess = None
        if options.statusPipe:
            try:
                self.statusPipe = win32file.CreateFile("\\\\.\\pipe\\{}".format(options.statusPipe),
                                                       win32file.GENERIC_READ | win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, win32file.FILE_FLAG_NO_BUFFERING, None)
                self.showStatus = self.showStatusOnPipe
                self.lastStatusTime = 0.0
                self.parentProcessHandle = None
            except pywintypes.error: # named pipe doesn't exist
                self.addToLog("--statusPipe {} has not been created by calling program".format(options.statusPipe))
        if options.monitorParentProcess:
            try:
                self.parentProcessHandle = win32api.OpenProcess(PROCESS_QUERY_INFORMATION, False, int(options.monitorParentProcess))
                def monitorParentProcess():
                    if win32process.GetExitCodeProcess(self.parentProcessHandle) != STILL_ACTIVE:
                        sys.exit()
                    _t = threading.Timer(10.0, monitorParentProcess)
                    _t.daemon = True
                    _t.start()
                monitorParentProcess()
            except ImportError: # win32 not installed
                self.addToLog("--monitorParentProcess {} cannot be installed, packages for win32api and win32process missing".format(options.monitorParentProcess))
            except (ValueError, pywintypes.error): # parent process doesn't exist
                self.addToLog("--monitorParentProcess Process {} Id is invalid".format(options.monitorParentProcess))
                sys.exit()
        if options.showOptions: # debug options
            for optName, optValue in sorted(options.__dict__.items(), key=lambda optItem: optItem[0]):
                self.addToLog("Option {0}={1}".format(optName, optValue), messageCode="info")
            self.addToLog("sys.argv {0}".format(sys.argv), messageCode="info")

        setDisableRTL(options.disableRtl) # not saved to config

        # Some options below (e.g. `packages`) may trigger web requests,
        # so the `workOffline` flag needs to be set early on.
        if options.internetConnectivity == "offline":
            self.webCache.workOffline = True
        elif options.internetConnectivity == "online":
            self.webCache.workOffline = False

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
        if options.noCertificateCheck:
            self.webCache.noCertificateCheck = True # also resets proxy handler stack
        if options.httpsRedirectCache:
            self.webCache.httpsRedirect = options.httpsRedirectCache
        if options.httpUserAgent:
            self.webCache.httpUserAgent = options.httpUserAgent
        if options.plugins:
            resetPlugins = False
            savePluginChanges = True
            showPluginModules = False
            for pluginCmd in options.plugins.split('|'):
                cmd = pluginCmd.strip()
                if cmd == "show":
                    showPluginModules = True
                elif cmd == "temp":
                    savePluginChanges = False
                elif cmd.startswith("+"):
                    moduleInfo = PluginManager.addPluginModule(cmd[1:])
                    if moduleInfo:
                        self.addToLog(_("Addition of plug-in {0} successful.").format(moduleInfo.get("name")),
                                      messageCode="info", file=moduleInfo.get("moduleURL"))
                        resetPlugins = True
                        if "CntlrCmdLine.Options" in moduleInfo["classMethods"]:
                            addedPluginWithCntlrCmdLineOptions = True
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
                else: # assume it is a module or package (may also have been loaded before for option parsing)
                    savePluginChanges = False
                    if cmd in self.preloadedPlugins:
                        moduleInfo =  self.preloadedPlugins[cmd] # already loaded, add activation message to log below
                    else:
                        moduleInfo = PluginManager.addPluginModule(cmd)
                        if moduleInfo:
                            resetPlugins = True
                    if moduleInfo:
                        self.addToLog(_("Activation of plug-in {0} successful, version {1}.").format(moduleInfo.get("name"), moduleInfo.get("version")),
                                      messageCode="info", file=moduleInfo.get("moduleURL"))
                    else:
                        self.addToLog(_("Unable to load \"%(name)s\" as a plug-in or \"%(name)s\" is not recognized as a plugin command. "),
                                      messageCode="arelle:pluginParameterError",
                                      messageArgs={"name": cmd, "file": cmd}, level=logging.ERROR)
                if resetPlugins:
                    PluginManager.reset()
                    if savePluginChanges:
                        PluginManager.save(self)
                    if options.webserver: # options may need reparsing dynamically
                        _optionsParser = ParserForDynamicPlugins(options)
                        # add plug-in options
                        for optionsExtender in pluginClassMethods("CntlrCmdLine.Options"):
                            optionsExtender(_optionsParser)

            if showPluginModules:
                self.addToLog(_("Plug-in modules:"), messageCode="info")
                for i, moduleItem in enumerate(sorted(PluginManager.pluginConfig.get("modules", {}).items())):
                    moduleInfo = moduleItem[1]
                    self.addToLog(_("Plug-in: {0}; author: {1}; version: {2}; status: {3}; date: {4}; description: {5}; license {6}.").format(
                                  moduleItem[0], moduleInfo.get("author"), moduleInfo.get("version"), moduleInfo.get("status"),
                                  moduleInfo.get("fileDate"), moduleInfo.get("description"), moduleInfo.get("license")),
                                  messageCode="info", file=moduleInfo.get("moduleURL"))

        if options.packages:
            self.loadPackages(options.packages, options.packageManifestName)

        if options.showEnvironment:
            self.addToLog(_("Config directory: {0}").format(self.configDir))
            self.addToLog(_("Cache directory: {0}").format(self.userAppDir))
            for envVar in ("XDG_CONFIG_HOME",):
                if envVar in os.environ:
                    self.addToLog(_("XDG_CONFIG_HOME={0}").format(os.environ[envVar]))
            return True

        self.modelManager.customTransforms = None # clear out prior custom transforms
        self.modelManager.loadCustomTransforms()

        self.username = options.username
        self.password = options.password
        if options.disclosureSystemName:
            self.modelManager.validateDisclosureSystem = True
            self.modelManager.disclosureSystem.select(options.disclosureSystemName)
            if options.validateEFM:
                self.addToLog(_("both --efm and --disclosureSystem validation are requested, ignoring --efm only"),
                              messageCode="info", file=options.entrypointFile)
        elif options.validateEFM:
            self.modelManager.validateDisclosureSystem = True
            self.modelManager.disclosureSystem.select("efm")
        elif options.validateHMRC:
            self.modelManager.validateDisclosureSystem = True
            self.modelManager.disclosureSystem.select("hmrc")
        else:
            self.modelManager.disclosureSystem.select(None) # just load ordinary mappings
            self.modelManager.validateDisclosureSystem = False
        if options.validateDuplicateFacts:
            duplicateTypeArg = ValidateDuplicateFacts.DuplicateTypeArg(options.validateDuplicateFacts)
            duplicateType = duplicateTypeArg.duplicateType()
            self.modelManager.validateDuplicateFacts = duplicateType
        if options.utrUrl:  # override disclosureSystem utrUrl
            self.modelManager.disclosureSystem.utrUrl = [options.utrUrl]
            # can be set now because the utr is first loaded at validation time
        if options.skipDTS: # skip DTS loading, discovery, etc
            self.modelManager.skipDTS = True
        if options.skipLoading: # skip loading matching files (list of unix patterns)
            self.modelManager.skipLoading = re.compile(
                '|'.join(fnmatch.translate(f) for f in options.skipLoading.split('|')))

        # disclosure system sets logging filters, override disclosure filters, if specified by command line
        if options.logLevelFilter:
            self.setLogLevelFilter(options.logLevelFilter)
        if options.logCodeFilter:
            self.setLogCodeFilter(options.logCodeFilter)
        from arelle.ValidateXbrlCalcs import ValidateCalcsMode as CalcsMode
        if options.calcDecimals:
            if options.calcPrecision:
                self.addToLog(_("both --calcDecimals and --calcPrecision validation are requested, proceeding with --calcDecimals only"),
                              messageCode="info", file=options.entrypointFile)
            if options.calcs:
                self.addToLog(_("both --calcDecimals and --calcs validation are requested, proceeding with --calcDecimals only"),
                              messageCode="info", file=options.entrypointFile)
            self.modelManager.validateCalcs = CalcsMode.XBRL_v2_1 + (options.calcDeduplicate or 0)
        elif options.calcPrecision:
            self.modelManager.validateCalcs = CalcsMode.XBRL_v2_1_INFER_PRECISION
        else:
            try:
                self.modelManager.validateCalcs = {
                     None: CalcsMode.NONE,
                     "none": CalcsMode.NONE,
                     "xbrl21precision": CalcsMode.XBRL_v2_1_INFER_PRECISION,
                     "xbrl21": CalcsMode.XBRL_v2_1,
                     "c10": CalcsMode.XBRL_v2_1,
                     "xbrl21-dedup": CalcsMode.XBRL_v2_1_DEDUPLICATE,
                     "c10d": CalcsMode.XBRL_v2_1_DEDUPLICATE,
                     "round-to-nearest": CalcsMode.ROUND_TO_NEAREST,
                     "c11r": CalcsMode.ROUND_TO_NEAREST,
                     "truncation": CalcsMode.TRUNCATION,
                     "c11t": CalcsMode.TRUNCATION
                    }[options.calcs]
            except KeyError:
                self.addToLog(_("--calc parameter value invalid, parameter ignored"),
                              messageCode="info", file=options.entrypointFile)
        if options.utrValidate:
            self.modelManager.validateUtr = True
        if options.infosetValidate:
            self.modelManager.validateInfoset = True
        if options.abortOnMajorError:
            self.modelManager.abortOnMajorError = True
        if options.collectProfileStats:
            self.modelManager.collectProfileStats = True
        if options.outputAttribution:
            self.modelManager.outputAttribution = options.outputAttribution
        self.modelManager.validateTestcaseSchema = options.validateTestcaseSchema
        if options.internetTimeout is not None:
            self.webCache.timeout = (options.internetTimeout or None)  # use None if zero specified to disable timeout
        if options.internetLogDownloads:
            self.webCache.logDownloads = True
        if options.internetRecheck:
            self.webCache.recheck = options.internetRecheck
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
        if options.formulaSatisfiedAsser:
            fo.traceSatisfiedAssertions = True
        if options.formulaUnsatisfiedAsser:
            fo.traceUnsatisfiedAssertions = True
        if options.formulaUnsatisfiedAsserError:
            fo.errorUnsatisfiedAssertions = True
        if options.formulaUnmessagedUnsatisfiedAsser:
            fo.traceUnmessagedUnsatisfiedAssertions = True
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
        if options.testcaseResultsCaptureWarnings:
            fo.testcaseResultsCaptureWarnings = True
        if options.testcaseResultOptions:
            fo.testcaseResultOptions = options.testcaseResultOptions
        if options.formulaRunIDs:
            fo.runIDs = options.formulaRunIDs
        if options.formulaCompileOnly:
            fo.compileOnly = True
        if options.formulaAction:
            fo.formulaAction = options.formulaAction
        if options.formulaCacheSize:
            fo.cacheSize = options.formulaCacheSize
        self.modelManager.formulaOptions = fo

        # run utility command line options that don't depend on entrypoint Files
        hasUtilityPlugin = False
        for pluginXbrlMethod in pluginClassMethods("CntlrCmdLine.Utility.Run"):
            hasUtilityPlugin = True
            try:
                pluginXbrlMethod(self, options, sourceZipStream=sourceZipStream, responseZipStream=responseZipStream)
            except SystemExit: # terminate operation, plug in has terminated all processing
                return True # success

        # if no entrypointFile is applicable, quit now
        if options.proxy or options.plugins or hasUtilityPlugin:
            if not (options.entrypointFile or sourceZipStream):
                return True # success

        success = True
        # entrypointFile may be absent (if input is a POSTED zip or file name ending in .zip)
        #    or may be a | separated set of file names
        _entryPoints = []
        _checkIfXmlIsEis = self.modelManager.disclosureSystem and self.modelManager.disclosureSystem.validationType == "EFM"
        if options.entrypointFile:
            _f = options.entrypointFile
            try: # may be a json list
                _entryPoints = json.loads(_f)
                _checkIfXmlIsEis = False # json entry objects never specify an xml EIS archive
            except ValueError as e:
                # is it malformed json?
                if _f.startswith("[{") or _f.endswith("]}") or '"file:"' in _f:
                    self.addToLog(_("File name parameter appears to be malformed JSON: {0}\n{1}".format(e, _f)),
                                  messageCode="FileNameFormatError",
                                  level=logging.ERROR)
                    success = False
                else: # try as file names separated by '|'
                    for f in (_f or '').split('|'):
                        if not sourceZipStream and not isHttpUrl(f) and not os.path.isabs(f):
                            f = os.path.normpath(os.path.join(os.getcwd(), f)) # make absolute normed path
                        _entryPoints.append({"file":f})
        filesource = None # file source for all instances if not None
        if sourceZipStream:
            filesource = FileSource.openFileSource(None, self, sourceZipStream)
        elif len(_entryPoints) == 1 and "file" in _entryPoints[0]: # check if an archive and need to discover entry points (and not IXDS)
            filesource = FileSource.openFileSource(_entryPoints[0].get("file",None), self, checkIfXmlIsEis=_checkIfXmlIsEis)
        _entrypointFiles = _entryPoints
        if filesource and not filesource.selection:
            if not (sourceZipStream and len(_entrypointFiles) > 0):
                filesourceEntrypointFiles(filesource, _entrypointFiles)

        for pluginXbrlMethod in pluginClassMethods("CntlrCmdLine.Filing.Start"):
            pluginXbrlMethod(self, options, filesource, _entrypointFiles, sourceZipStream=sourceZipStream, responseZipStream=responseZipStream)
        for _entrypoint in _entrypointFiles:
            _entrypointFile = _entrypoint.get("file", None) if isinstance(_entrypoint,dict) else _entrypoint
            if filesource and filesource.isArchive:
                filesource.select(_entrypointFile)
            else:
                filesource = FileSource.openFileSource(_entrypointFile, self, sourceZipStream)
            self.entrypointFile = _entrypointFile
            timeNow = XmlUtil.dateunionValue(datetime.datetime.now())
            firstStartedAt = startedAt = time.time()
            modelDiffReport = None
            modelXbrl = None
            try:
                if filesource:
                    modelXbrl = self.modelManager.load(filesource, _("views loading"), entrypoint=_entrypoint)
            except ModelDocument.LoadingException:
                pass
            except Exception as err:
                self.addToLog(_("Entry point loading Failed to complete request: \n{0} \n{1}").format(
                            err,
                            traceback.format_tb(sys.exc_info()[2])),
                              messageCode="Exception",
                              level=logging.ERROR)
                success = False    # loading errors, don't attempt to utilize loaded DTS
            if modelXbrl and modelXbrl.modelDocument:
                loadTime = time.time() - startedAt
                modelXbrl.profileStat(_("load"), loadTime)
                self.addToLog(format_string(self.modelManager.locale,
                                            _("loaded in %.2f secs at %s"),
                                            (loadTime, timeNow)),
                                            messageCode="info", file=self.entrypointFile)
                if modelXbrl.hasTableRendering:
                    RenderingEvaluator.init(modelXbrl)
                if options.importFiles:
                    for importFile in options.importFiles.split("|"):
                        fileName = importFile.strip()
                        if sourceZipStream is not None and not (fileName.startswith('http://') or os.path.isabs(fileName)):
                            fileName = os.path.dirname(modelXbrl.uri) + os.sep + fileName # make relative to sourceZipStream
                        ModelDocument.load(modelXbrl, fileName, isSupplemental=True)
                        loadTime = time.time() - startedAt
                        self.addToLog(format_string(self.modelManager.locale,
                                                    _("import in %.2f secs at %s"),
                                                    (loadTime, timeNow)),
                                                    messageCode="info", file=importFile)
                        modelXbrl.profileStat(_("import"), loadTime)
                    if modelXbrl.errors:
                        success = False    # loading errors, don't attempt to utilize loaded DTS
                if modelXbrl.modelDocument.type in ModelDocument.Type.TESTCASETYPES:
                    for pluginXbrlMethod in pluginClassMethods("Testcases.Start"):
                        pluginXbrlMethod(self, options, modelXbrl)
                else: # not a test case, probably instance or DTS
                    for pluginXbrlMethod in pluginClassMethods("CntlrCmdLine.Xbrl.Loaded"):
                        pluginXbrlMethod(self, options, modelXbrl, _entrypoint, responseZipStream=responseZipStream)
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
                    for modelXbrl in [self.modelManager.modelXbrl] + getattr(self.modelManager.modelXbrl, "supplementalModelXbrls", []):
                        hasFormulae = modelXbrl.hasFormulae
                        isAlreadyValidated = False
                        for pluginXbrlMethod in pluginClassMethods("ModelDocument.IsValidated"):
                            if pluginXbrlMethod(modelXbrl): # e.g., streaming extensions already has validated
                                isAlreadyValidated = True
                        if options.validate and not isAlreadyValidated:
                            startedAt = time.time()
                            if options.formulaAction: # don't automatically run formulas
                                modelXbrl.hasFormulae = False
                            from arelle import Validate
                            Validate.validate(modelXbrl)
                            if options.formulaAction: # restore setting
                                modelXbrl.hasFormulae = hasFormulae
                            self.addToLog(format_string(self.modelManager.locale,
                                                        _("validated in %.2f secs"),
                                                        time.time() - startedAt),
                                                        messageCode="info", file=self.entrypointFile)
                        if (modelXbrl.modelDocument.type not in ModelDocument.Type.TESTCASETYPES and
                                options.formulaAction in ("validate", "run") and  # do nothing here if "none"
                                not isAlreadyValidated):  # formulas can't run if streaming has validated the instance
                            from arelle import ValidateXbrlDimensions
                            from arelle.formula import ValidateFormula
                            startedAt = time.time()
                            if not options.validate:
                                ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl)
                            # setup fresh parameters from formula optoins
                            modelXbrl.parameters = fo.typedParameters(modelXbrl.prefixedNamespaces)
                            ValidateFormula.validate(modelXbrl, compileOnly=(options.formulaAction != "run"))
                            self.addToLog(format_string(self.modelManager.locale,
                                                        _("formula validation and execution in %.2f secs")
                                                        if options.formulaAction == "run"
                                                        else _("formula validation only in %.2f secs"),
                                                        time.time() - startedAt),
                                                        messageCode="info", file=self.entrypointFile)

                        if options.testReport:
                            ViewFileTests.viewTests(self.modelManager.modelXbrl, options.testReport, options.testReportCols)

                        if options.rssReport:
                            ViewFileRssFeed.viewRssFeed(self.modelManager.modelXbrl, options.rssReport, options.rssReportCols)

                        if options.DTSFile:
                            ViewFileDTS.viewDTS(modelXbrl, options.DTSFile)
                        if options.factsFile:
                            ViewFileFactList.viewFacts(modelXbrl, options.factsFile, labelrole=options.labelRole, lang=options.labelLang, cols=options.factListCols)
                        if options.factTableFile:
                            ViewFileFactTable.viewFacts(modelXbrl, options.factTableFile, labelrole=options.labelRole, lang=options.labelLang, cols=options.factTableCols)
                        if options.conceptsFile:
                            ViewFileConcepts.viewConcepts(modelXbrl, options.conceptsFile, labelrole=options.labelRole, lang=options.labelLang)
                        if options.preFile:
                            ViewFileRelationshipSet.viewRelationshipSet(modelXbrl, options.preFile, "Presentation Linkbase", XbrlConst.parentChild, labelrole=options.labelRole, lang=options.labelLang, cols=options.relationshipCols)
                        if options.tableFile:
                            ViewFileRelationshipSet.viewRelationshipSet(modelXbrl, options.tableFile, "Table Linkbase", "Table-rendering", labelrole=options.labelRole, lang=options.labelLang)
                        if options.calFile:
                            ViewFileRelationshipSet.viewRelationshipSet(modelXbrl, options.calFile, "Calculation Linkbase", XbrlConst.summationItem, labelrole=options.labelRole, lang=options.labelLang, cols=options.relationshipCols)
                        if options.dimFile:
                            ViewFileRelationshipSet.viewRelationshipSet(modelXbrl, options.dimFile, "Dimensions", "XBRL-dimensions", labelrole=options.labelRole, lang=options.labelLang, cols=options.relationshipCols)
                        if options.anchFile:
                            ViewFileRelationshipSet.viewRelationshipSet(modelXbrl, options.anchFile, "Anchoring", XbrlConst.widerNarrower, labelrole=options.labelRole, lang=options.labelLang, cols=options.relationshipCols)
                        if options.formulaeFile:
                            ViewFileFormulae.viewFormulae(modelXbrl, options.formulaeFile, "Formulae", lang=options.labelLang)
                        if options.viewArcrole and options.viewFile:
                            ViewFileRelationshipSet.viewRelationshipSet(modelXbrl, options.viewFile, os.path.basename(options.viewArcrole), options.viewArcrole, labelrole=options.labelRole, lang=options.labelLang, cols=options.relationshipCols)
                        if options.roleTypesFile:
                            ViewFileRoleTypes.viewRoleTypes(modelXbrl, options.roleTypesFile, "Role Types", isArcrole=False, lang=options.labelLang)
                        if options.arcroleTypesFile:
                            ViewFileRoleTypes.viewRoleTypes(modelXbrl, options.arcroleTypesFile, "Arcrole Types", isArcrole=True, lang=options.labelLang)

                        for pluginXbrlMethod in pluginClassMethods("CntlrCmdLine.Xbrl.Run"):
                            pluginXbrlMethod(self, options, modelXbrl, _entrypoint, responseZipStream=responseZipStream)

                except (IOError, EnvironmentError) as err:
                    self.addToLog(_("[IOError] Failed to save output:\n {0}").format(err),
                                  messageCode="IOError",
                                  file=options.entrypointFile,
                                  level=logging.CRITICAL)
                    success = False
                except Exception as err:
                    self.addToLog(_("[Exception] Failed to complete request: \n{0} \n{1}").format(
                                    err,
                                    traceback.format_tb(sys.exc_info()[2])),
                                  messageCode=err.__class__.__name__,
                                  file=options.entrypointFile,
                                  level=logging.CRITICAL)
                    success = False
            if modelXbrl:
                if success:
                    if options.saveDeduplicatedInstance:
                        if options.deduplicateFacts:
                            deduplicateFactsArg = ValidateDuplicateFacts.DeduplicationType(options.deduplicateFacts)
                        else:
                            deduplicateFactsArg = ValidateDuplicateFacts.DeduplicationType.COMPLETE
                        if modelXbrl.modelDocument.type != ModelDocument.Type.INSTANCE:
                            self.addToLog(_("Provided file must be a traditional XBRL instance document to save a deduplicated instance."),
                                          messageCode="error", file=modelXbrl.modelDocument.uri)
                        else:
                            # Deduplication modifies the underlying lxml tree and leaves the model in an undefined state.
                            # Anything depending on the ModelXbrl that runs after this may encounter unexpected behavior,
                            # so we'll run it as a final step in the CLI controller flow.
                            ValidateDuplicateFacts.saveDeduplicatedInstance(modelXbrl, deduplicateFactsArg, options.saveDeduplicatedInstance)
                            if options.keepOpen:
                                success = False
                                self.addToLog(_("Attempted to keep model connection open after saving deduplicated instance. "
                                                "Deduplication modifies the model in ways that can cause unexpected behavior on subsequent use."),
                                              messageCode="error", level=logging.CRITICAL)
                    elif options.deduplicateFacts:
                        success = False
                        self.addToLog(_("'deduplicateFacts' can only be used with 'saveDeduplicatedInstance'"),
                                      messageCode="error", level=logging.CRITICAL)

                modelXbrl.profileStat(_("total"), time.time() - firstStartedAt)
                if options.collectProfileStats and modelXbrl:
                    modelXbrl.logProfileStats()
                if not options.keepOpen:
                    if modelDiffReport:
                        self.modelManager.close(modelDiffReport)
                    elif modelXbrl:
                        self.modelManager.close(modelXbrl)
        if success:
            if options.validate:
                for pluginXbrlMethod in pluginClassMethods("CntlrCmdLine.Filing.Validate"):
                    pluginXbrlMethod(self, options, filesource, _entrypointFiles, sourceZipStream=sourceZipStream, responseZipStream=responseZipStream)
            for pluginXbrlMethod in pluginClassMethods("CntlrCmdLine.Filing.End"):
                pluginXbrlMethod(self, options, filesource, _entrypointFiles, sourceZipStream=sourceZipStream, responseZipStream=responseZipStream)
        self.username = self.password = None #dereference password

        if options.statusPipe and getattr(self, "statusPipe", None) is not None:
            win32file.WriteFile(self.statusPipe, b" ")  # clear status
            win32file.FlushFileBuffers(self.statusPipe)
            win32file.SetFilePointer(self.statusPipe, 0, win32file.FILE_BEGIN) # hangs on close without this
            win32file.CloseHandle(self.statusPipe)
            self.statusPipe = None # dereference

        return success

    # default web authentication password
    def internet_user_password(self, host, realm):
        return (self.username, self.password)

    # special show status for named pipes
    def showStatusOnPipe(self, message, clearAfter=None):
        # now = time.time() # seems ok without time-limiting writes to the pipe
        if self.statusPipe is not None:  # max status updates 3 per second now - 0.3 > self.lastStatusTime and
            # self.lastStatusTime = now
            try:
                if self.parentProcessHandle is not None:
                    if win32process.GetExitCodeProcess(self.parentProcessHandle) != STILL_ACTIVE:
                        sys.exit()
                win32file.WriteFile(self.statusPipe, (message or "").encode("utf8"))
                win32file.FlushFileBuffers(self.statusPipe)
                win32file.SetFilePointer(self.statusPipe, 0, win32file.FILE_BEGIN)  # hangs on close without this
            except Exception as ex:
                #with open("Z:\\temp\\trace.log", "at", encoding="utf-8") as fh:
                #    fh.write("Status pipe exception {} {}\n".format(type(ex), ex))
                system.exit()

    def loadPackage(self, package: str, packageManifestName: str):
        from arelle import PackageManager
        packageInfo = PackageManager.addPackage(self, package, packageManifestName)
        if packageInfo:
            self.addToLog(_("Activation of package {0} successful.").format(packageInfo.get("name")),
                          messageCode="info", file=packageInfo.get("URL"))
        else:
            self.addToLog(_("Unable to load package \"%(name)s\". "),
                          messageCode="arelle:packageLoadingError",
                          messageArgs={"name": package, "file": package}, level=logging.ERROR)

    def loadPackages(self, packages: list[str], packageManifestName: str):
        """
        Loads specified packages.

        :param packages: Pipe-separated list of options. See CLI documentation for 'packages'.
        :param packageManifestName: Unix shell style pattern used to find package manifest.
        """
        from arelle import PackageManager
        savePackagesChanges = True
        showPackages = False
        # For backwards compatibility, we allow '|' separated filenames/URLs
        # within a single --packages option.
        for packageCmd in [cmd for p in packages for cmd in p.split('|')]:
            cmd = packageCmd.strip()
            if cmd == "show":
                showPackages = True
            elif cmd == "temp":
                savePackagesChanges = False
            elif cmd.startswith("+"):
                packageInfo = PackageManager.addPackage(self, cmd[1:], packageManifestName)
                if packageInfo:
                    self.addToLog(_("Addition of package {0} successful.").format(packageInfo.get("name")),
                                  messageCode="info", file=packageInfo.get("URL"))
                else:
                    self.addToLog(_("Unable to load package."), messageCode="info", file=cmd[1:])
            elif cmd.startswith("~"):
                if PackageManager.reloadPackageModule(self, cmd[1:]):
                    self.addToLog(_("Reload of package successful."), messageCode="info", file=cmd[1:])
                else:
                    self.addToLog(_("Unable to reload package."), messageCode="info", file=cmd[1:])
            elif cmd.startswith("-"):
                if PackageManager.removePackageModule(self, cmd[1:]):
                    self.addToLog(_("Deletion of package successful."), messageCode="info", file=cmd[1:])
                else:
                    self.addToLog(_("Unable to delete package."), messageCode="info", file=cmd[1:])
            elif os.path.isdir(cmd): # load all package files in a directory
                savePackagesChanges = False
                for package in glob.glob(os.path.join(cmd, "*.zip")):
                    self.loadPackage(package, packageManifestName)
            else: # assume it is a module or package
                savePackagesChanges = False
                self.loadPackage(cmd, packageManifestName)
        if PackageManager.packagesConfigChanged:
            PackageManager.rebuildRemappings(self)
        if savePackagesChanges:
            PackageManager.save(self)
        else:
            PackageManager.packagesConfigChanged = False
        if showPackages:
            self.addToLog(_("Taxonomy packages:"), messageCode="info")
            for packageInfo in PackageManager.orderedPackagesConfig()["packages"]:
                self.addToLog(_("Package: {0}; version: {1}; status: {2}; date: {3}; description: {4}.").format(
                    packageInfo.get("name"), packageInfo.get("version"), packageInfo.get("status"),
                    packageInfo.get("fileDate"), packageInfo.get("description")),
                    messageCode="info", file=packageInfo.get("URL"))

if __name__ == "__main__":
    '''
    if '--COMserver' in sys.argv:
        from arelle import CntlrComServer
        CntlrComServer.main()
    else:
        main()
    '''
    main()
