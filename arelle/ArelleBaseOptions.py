from typing import Optional
from arelle.SystemInfo import get_system_info

systemInfo = get_system_info()


class ArelleBaseOptions:
    def __init__(self,
                 abortOnMajorError: Optional[bool] = None,
                 about: Optional[str] = None,
                 anchFile: Optional[str] = None,
                 arcroleTypesFile: Optional[str] = None,
                 betaObjectModel: Optional[bool] = False,
                 calFile: Optional[str] = None,
                 calcDecimals: Optional[int] = None,
                 calcDeduplicate: Optional[bool] = None,
                 calcPrecision: Optional[int] = None,
                 calcs: Optional[str] = None,
                 collectProfileStats: Optional[bool] = None,
                 conceptsFile: Optional[str] = None,
                 diagnostics: Optional[bool] = None,
                 diffFile: Optional[str] = None,
                 dimFile: Optional[str] = None,
                 disablePersistentConfig: Optional[bool] = None,
                 disableRtl: Optional[bool] = None,
                 disclosureSystemName: Optional[str] = None,
                 DTSFile: Optional[str] = None,
                 encodeSavedXmlChars: Optional[bool] = None,
                 entrypointFile: Optional[str] = None,
                 factListCols: Optional[int] = None,
                 factTableCols: Optional[int] = None,
                 factTableFile: Optional[str] = None,
                 factsFile: Optional[str] = None,
                 formulaAction: Optional[str] = None,
                 formulaAsserResultCounts: Optional[bool] = None,
                 formulaCacheSize: Optional[int] = None,
                 formulaCallExprCode: Optional[bool] = None,
                 formulaCallExprEval: Optional[bool] = None,
                 formulaCallExprResult: Optional[bool] = None,
                 formulaCallExprSource: Optional[bool] = None,
                 formulaCompileOnly: Optional[bool] = None,
                 formulaFormulaRules: Optional[bool] = None,
                 formulaParamExprResult: Optional[bool] = None,
                 formulaParamInputValue: Optional[bool] = None,
                 formulaRunIDs: Optional[int] = None,
                 formulaSatisfiedAsser: Optional[bool] = None,
                 formulaUnmessagedUnsatisfiedAsser: Optional[bool] = None,
                 formulaUnsatisfiedAsser: Optional[bool] = None,
                 formulaUnsatisfiedAsserError: Optional[bool] = None,
                 formulaVarExpressionCode: Optional[bool] = None,
                 formulaVarExpressionEvaluation: Optional[bool] = None,
                 formulaVarExpressionResult: Optional[bool] = None,
                 formulaVarExpressionSource: Optional[bool] = None,
                 formulaVarFilterWinnowing: Optional[bool] = None,
                 formulaVarFiltersResult: Optional[bool] = None,
                 formulaVarSetExprEval: Optional[bool] = None,
                 formulaVarSetExprResult: Optional[bool] = None,
                 formulaVarsOrder: Optional[bool] = None,
                 formulaeFile: Optional[str] = None,
                 httpUserAgent: Optional[str] = None,
                 httpsRedirectCache: Optional[bool] = None,
                 importFiles: Optional[str] = None,
                 infosetValidate: Optional[bool] = None,
                 internetConnectivity: Optional[str] = None,
                 internetLogDownloads: Optional[bool] = None,
                 internetRecheck: Optional[str] = None,
                 internetTimeout: Optional[int] = None,
                 keepOpen: Optional[bool] = None,
                 labelLang: Optional[str] = None,
                 labelRole: Optional[str] = None,
                 logCodeFilter: Optional[str] = None,
                 logFile: Optional[str] = None,
                 logFormat: Optional[str] = None,
                 logLevel: Optional[str] = None,
                 logLevelFilter: Optional[str] = None,
                 logRefObjectProperties: Optional[str] = None,
                 logTextMaxLength: Optional[int] = None,
                 monitorParentProcess: Optional[bool] = None,
                 noCertificateCheck: Optional[bool] = None,
                 outputAttribution: Optional[str] = None,
                 packageManifestName: Optional[str] = None,
                 packages: Optional[str] = None,
                 parameterSeparator: Optional[str] = None,
                 parameters: Optional[str] = None,
                 password: Optional[str] = None,
                 plugins: Optional[str] = None,
                 preFile: Optional[str] = None,
                 proxy: Optional[str] = None,
                 relationshipCols: Optional[int] = None,
                 roleTypesFile: Optional[str] = None,
                 rssReport: Optional[str] = None,
                 rssReportCols: Optional[int] = None,
                 saveTargetFiling: Optional[bool] = None,
                 saveTargetInstance: Optional[bool] = None,
                 showEnvironment: Optional[bool] = None,
                 showOptions: Optional[bool] = None,
                 skipDTS: Optional[bool] = None,
                 skipExpectedInstanceComparison: Optional[bool] = None,
                 skipLoading: Optional[bool] = None,
                 statusPipe: Optional[str] = None,
                 tableFile: Optional[str] = None,
                 testReport: Optional[str] = None,
                 testReportCols: Optional[int] = None,
                 testcaseResultOptions: Optional[str] = None,
                 testcaseResultsCaptureWarnings: Optional[bool] = None,
                 timeVariableSetEvaluation: Optional[bool] = None,
                 uiLang: Optional[str] = None,
                 username: Optional[str] = None,
                 utrUrl: Optional[str] = None,
                 utrValidate: Optional[bool] = None,
                 validate: Optional[bool] = None,
                 validateEFM: Optional[bool] = None,
                 validateEFMCalcTree: Optional[bool] = None,
                 validateHMRC: Optional[bool] = None,
                 validateTestcaseSchema: Optional[bool] = None,
                 versReportFile: Optional[str] = None,
                 viewArcrole: Optional[bool] = None,
                 viewFile: Optional[str] = None,
                 webserver: Optional[str] = None,
                 xdgConfigHome: Optional[str] = None,
                 **kwargs):
        self.DTSFile = DTSFile
        self.abortOnMajorError = abortOnMajorError
        self.about = about
        self.anchFile = anchFile
        self.arcroleTypesFile = arcroleTypesFile
        self.betaObjectModel = betaObjectModel
        self.calFile = calFile
        self.calcDecimals = calcDecimals
        self.calcDeduplicate = calcDeduplicate
        self.calcPrecision = calcPrecision
        self.calcs = calcs
        self.collectProfileStats = collectProfileStats
        self.conceptsFile = conceptsFile
        self.diagnostics = diagnostics
        self.diffFile = diffFile
        self.dimFile = dimFile
        self.disablePersistentConfig = disablePersistentConfig
        self.disableRtl = disableRtl
        self.disclosureSystemName = disclosureSystemName
        self.encodeSavedXmlChars = encodeSavedXmlChars
        self.entrypointFile = entrypointFile
        self.factListCols = factListCols
        self.factTableCols = factTableCols
        self.factTableFile = factTableFile
        self.factsFile = factsFile
        self.formulaAction = formulaAction
        self.formulaAsserResultCounts = formulaAsserResultCounts
        self.formulaCacheSize = formulaCacheSize
        self.formulaCallExprCode = formulaCallExprCode
        self.formulaCallExprEval = formulaCallExprEval
        self.formulaCallExprResult = formulaCallExprResult
        self.formulaCallExprSource = formulaCallExprSource
        self.formulaCompileOnly = formulaCompileOnly
        self.formulaFormulaRules = formulaFormulaRules
        self.formulaParamExprResult = formulaParamExprResult
        self.formulaParamInputValue = formulaParamInputValue
        self.formulaRunIDs = formulaRunIDs
        self.formulaSatisfiedAsser = formulaSatisfiedAsser
        self.formulaUnmessagedUnsatisfiedAsser = formulaUnmessagedUnsatisfiedAsser
        self.formulaUnsatisfiedAsser = formulaUnsatisfiedAsser
        self.formulaUnsatisfiedAsserError = formulaUnsatisfiedAsserError
        self.formulaVarExpressionCode = formulaVarExpressionCode
        self.formulaVarExpressionEvaluation = formulaVarExpressionEvaluation
        self.formulaVarExpressionResult = formulaVarExpressionResult
        self.formulaVarExpressionSource = formulaVarExpressionSource
        self.formulaVarFilterWinnowing = formulaVarFilterWinnowing
        self.formulaVarFiltersResult = formulaVarFiltersResult
        self.formulaVarSetExprEval = formulaVarSetExprEval
        self.formulaVarSetExprResult = formulaVarSetExprResult
        self.formulaVarsOrder = formulaVarsOrder
        self.formulaeFile = formulaeFile
        self.httpUserAgent = httpUserAgent
        self.httpsRedirectCache = httpsRedirectCache
        self.importFiles = importFiles
        self.infosetValidate = infosetValidate
        self.internetConnectivity = internetConnectivity
        self.internetLogDownloads = internetLogDownloads
        self.internetRecheck = internetRecheck
        self.internetTimeout = internetTimeout
        self.keepOpen = keepOpen
        self.labelLang = labelLang
        self.labelRole = labelRole
        self.logCodeFilter = logCodeFilter
        self.logFile = logFile
        self.logFormat = logFormat
        self.logLevel = logLevel
        self.logLevelFilter = logLevelFilter
        self.logRefObjectProperties = logRefObjectProperties
        self.logTextMaxLength = logTextMaxLength
        self.monitorParentProcess = monitorParentProcess
        self.noCertificateCheck = noCertificateCheck
        self.outputAttribution = outputAttribution
        self.packageManifestName = packageManifestName
        self.packages = packages
        self.parameterSeparator = parameterSeparator
        self.parameters = parameters
        self.password = password
        self.plugins = plugins
        self.preFile = preFile
        self.proxy = proxy
        self.relationshipCols = relationshipCols
        self.roleTypesFile = roleTypesFile
        self.rssReport = rssReport
        self.rssReportCols = rssReportCols
        self.saveTargetFiling = saveTargetFiling
        self.saveTargetInstance = saveTargetInstance
        self.showEnvironment = showEnvironment
        self.showOptions = showOptions
        self.skipDTS = skipDTS
        self.skipExpectedInstanceComparison = skipExpectedInstanceComparison
        self.skipLoading = skipLoading
        self.statusPipe = statusPipe
        self.tableFile = tableFile
        self.testReport = testReport
        self.testReportCols = testReportCols
        self.testcaseResultOptions = testcaseResultOptions
        self.testcaseResultsCaptureWarnings = testcaseResultsCaptureWarnings
        self.timeVariableSetEvaluation = timeVariableSetEvaluation
        self.uiLang = uiLang
        self.username = username
        self.utrUrl = utrUrl
        self.utrValidate = utrValidate
        self.validate = validate
        self.validateEFM = validateEFM
        self.validateEFMCalcTree = validateEFMCalcTree
        self.validateHMRC = validateHMRC
        self.validateTestcaseSchema = validateTestcaseSchema
        self.versReportFile = versReportFile
        self.viewArcrole = viewArcrole
        self.viewFile = viewFile
        self.webserver = webserver
        self.xdgConfigHome = xdgConfigHome
        for option, value in kwargs.items():
            setattr(self, option, value)


def buildOptionsObject(options, extra_modules):
    options_object = ArelleBaseOptions(options.DTSFile,
                                       options.abortOnMajorError,
                                       options.about,
                                       options.anchFile,
                                       options.arcroleTypesFile,
                                       options.betaObjectModel,
                                       options.calFile,
                                       options.calcDecimals,
                                       options.calcDeduplicate,
                                       options.calcPrecision,
                                       options.calcs,
                                       options.collectProfileStats,
                                       options.conceptsFile,
                                       options.diagnostics,
                                       options.diffFile,
                                       options.dimFile,
                                       options.disablePersistentConfig,
                                       options.disableRtl,
                                       options.disclosureSystemName,
                                       options.encodeSavedXmlChars,
                                       options.entrypointFile,
                                       options.factListCols,
                                       options.factTableCols,
                                       options.factTableFile,
                                       options.factsFile,
                                       options.formulaAction,
                                       options.formulaAsserResultCounts,
                                       options.formulaCacheSize,
                                       options.formulaCallExprCode,
                                       options.formulaCallExprEval,
                                       options.formulaCallExprResult,
                                       options.formulaCallExprSource,
                                       options.formulaCompileOnly,
                                       options.formulaFormulaRules,
                                       options.formulaParamExprResult,
                                       options.formulaParamInputValue,
                                       options.formulaRunIDs,
                                       options.formulaSatisfiedAsser,
                                       options.formulaUnmessagedUnsatisfiedAsser,
                                       options.formulaUnsatisfiedAsser,
                                       options.formulaUnsatisfiedAsserError,
                                       options.formulaVarExpressionCode,
                                       options.formulaVarExpressionEvaluation,
                                       options.formulaVarExpressionResult,
                                       options.formulaVarExpressionSource,
                                       options.formulaVarFilterWinnowing,
                                       options.formulaVarFiltersResult,
                                       options.formulaVarSetExprEval,
                                       options.formulaVarSetExprResult,
                                       options.formulaVarsOrder,
                                       options.formulaeFile,
                                       options.httpUserAgent,
                                       options.httpsRedirectCache,
                                       options.importFiles,
                                       options.infosetValidate,
                                       options.internetConnectivity,
                                       options.internetLogDownloads,
                                       options.internetRecheck,
                                       options.internetTimeout,
                                       options.keepOpen,
                                       options.labelLang,
                                       options.labelRole,
                                       options.logCodeFilter,
                                       options.logFile,
                                       options.logFormat,
                                       options.logLevel,
                                       options.logLevelFilter,
                                       options.logRefObjectProperties,
                                       options.logTextMaxLength,
                                       options.monitorParentProcess,
                                       options.noCertificateCheck,
                                       options.outputAttribution,
                                       options.packageManifestName,
                                       options.packages,
                                       options.parameterSeparator,
                                       options.parameters,
                                       options.password,
                                       options.plugins,
                                       options.preFile,
                                       options.proxy,
                                       options.relationshipCols,
                                       options.roleTypesFile,
                                       options.rssReport,
                                       options.rssReportCols,
                                       options.saveTargetFiling,
                                       options.saveTargetInstance,
                                       options.showEnvironment,
                                       options.showOptions,
                                       options.skipDTS,
                                       options.skipExpectedInstanceComparison,
                                       options.skipLoading,
                                       options.statusPipe,
                                       options.tableFile,
                                       options.testReport,
                                       options.testReportCols,
                                       options.testcaseResultOptions,
                                       options.testcaseResultsCaptureWarnings,
                                       options.timeVariableSetEvaluation,
                                       options.uiLang,
                                       options.username,
                                       options.utrUrl,
                                       options.utrValidate,
                                       options.validate,
                                       options.validateEFM,
                                       options.validateEFMCalcTree,
                                       options.validateHMRC,
                                       options.validateTestcaseSchema,
                                       options.versReportFile,
                                       options.viewArcrole,
                                       options.viewFile,
                                       options.xdgConfigHome)
    assert not (options.entrypointFile is None and
            ((not options.proxy) and (not options.plugins) and
             (not any(pluginOption for pluginOption in extra_modules)) and
             (not systemInfo["webserver"] or options.webserver is None))), 'Incorrect arguments, please try\n  python CntlrCmdLine.py --help'
    if systemInfo["webserver"] and options.webserver:
        # webserver incompatible with file operations
        assert not any((options.entrypointFile, options.importFiles, options.diffFile, options.versReportFile,
                        options.factsFile, options.factListCols, options.factTableFile, options.factTableCols, options.relationshipCols,
                        options.conceptsFile, options.preFile, options.tableFile, options.calFile, options.dimFile, options.anchFile, options.formulaeFile, options.viewArcrole, options.viewFile,
                        options.roleTypesFile, options.arcroleTypesFile
                        )), 'incorrect arguments with --webserver, please try\n  python CntlrCmdLine.py --help'
    return options_object
