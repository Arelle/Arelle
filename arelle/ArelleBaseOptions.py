from typing import Optional

OPTIONS_LIST: [
    'DTSFile', 'abortOnMajorError', 'about', 'anchFile', 'arcroleTypesFile', 'betaObjectModel', 'calFile', 'calcDecimals',
    'calcDeduplicate', 'calcPrecision', 'calcs', 'collectProfileStats', 'conceptsFile', 'diagnostics', 'diffFile',
    'dimFile', 'disablePersistentConfig', 'disableRtl', 'disclosureSystemName', 'encodeSavedXmlChars', 'entrypointFile',
    'factListCols', 'factTableCols', 'factTableFile', 'factsFile', 'formulaAction', 'formulaAsserResultCounts',
    'formulaCacheSize', 'formulaCallExprCode', 'formulaCallExprEval', 'formulaCallExprResult', 'formulaCallExprSource',
    'formulaCompileOnly', 'formulaFormulaRules', 'formulaParamExprResult', 'formulaParamInputValue', 'formulaRunIDs',
    'formulaSatisfiedAsser', 'formulaUnmessagedUnsatisfiedAsser', 'formulaUnsatisfiedAsser', 'formulaUnsatisfiedAsserError',
    'formulaVarExpressionCode', 'formulaVarExpressionEvaluation', 'formulaVarExpressionResult', 'formulaVarExpressionSource',
    'formulaVarFilterWinnowing', 'formulaVarFiltersResult', 'formulaVarSetExprEval', 'formulaVarSetExprResult', 'formulaVarsOrder',
    'formulaeFile', 'httpUserAgent', 'httpsRedirectCache', 'importFiles', 'infosetValidate', 'internetConnectivity',
    'internetLogDownloads', 'internetRecheck', 'internetTimeout', 'keepOpen', 'labelLang', 'labelRole', 'logCodeFilter', 'logFile',
    'logFormat', 'logLevel', 'logLevelFilter', 'logRefObjectProperties', 'logTextMaxLength', 'monitorParentProcess',
    'noCertificateCheck', 'outputAttribution', 'packageManifestName', 'packages', 'parameterSeparator', 'parameters', 'password',
    'plugins', 'preFile', 'proxy', 'relationshipCols', 'roleTypesFile', 'rssReport', 'rssReportCols', 'saveTargetFiling',
    'saveTargetInstance', 'showEnvironment', 'showOptions', 'skipDTS', 'skipExpectedInstanceComparison', 'skipLoading', 'statusPipe',
    'tableFile', 'testReport', 'testReportCols', 'testcaseResultOptions', 'testcaseResultsCaptureWarnings',
    'timeVariableSetEvaluation', 'uiLang', 'username', 'utrUrl', 'utrValidate', 'validate', 'validateEFM', 'validateEFMCalcTree',
    'validateHMRC', 'validateTestcaseSchema', 'versReportFile', 'viewArcrole', 'viewFile', 'xdgConfigHome'
]


class ArelleBaseOptions:
    def __init__(self, DTSFile: Optional[str],
                 abortOnMajorError: Optional[bool],
                 about: Optional[str],
                 anchFile: Optional[str],
                 arcroleTypesFile: Optional[str],
                 betaObjectModel: bool,
                 calFile: Optional[str],
                 calcDecimals: Optional[int],
                 calcDeduplicate: Optional[bool],
                 calcPrecision: Optional[int],
                 calcs: Optional[str],
                 collectProfileStats: Optional[bool],
                 conceptsFile: Optional[str],
                 diagnostics: Optional[bool],
                 diffFile: Optional[str],
                 dimFile: Optional[str],
                 disablePersistentConfig: Optional[bool],
                 disableRtl: bool,
                 disclosureSystemName: str,
                 encodeSavedXmlChars: Optional[bool],
                 entrypointFile: str,
                 factListCols: Optional[int],
                 factTableCols: Optional[int],
                 factTableFile: Optional[str],
                 factsFile: Optional[str],
                 formulaAction: Optional[str],
                 formulaAsserResultCounts: Optional[bool],
                 formulaCacheSize: Optional[int],
                 formulaCallExprCode: Optional[bool],
                 formulaCallExprEval: Optional[bool],
                 formulaCallExprResult: Optional[bool],
                 formulaCallExprSource: Optional[bool],
                 formulaCompileOnly: Optional[bool],
                 formulaFormulaRules: Optional[bool],
                 formulaParamExprResult: Optional[bool],
                 formulaParamInputValue: Optional[bool],
                 formulaRunIDs: Optional[int],
                 formulaSatisfiedAsser: Optional[bool],
                 formulaUnmessagedUnsatisfiedAsser: Optional[bool],
                 formulaUnsatisfiedAsser: Optional[bool],
                 formulaUnsatisfiedAsserError: Optional[bool],
                 formulaVarExpressionCode: Optional[bool],
                 formulaVarExpressionEvaluation: Optional[bool],
                 formulaVarExpressionResult: Optional[bool],
                 formulaVarExpressionSource: Optional[bool],
                 formulaVarFilterWinnowing: Optional[bool],
                 formulaVarFiltersResult: Optional[bool],
                 formulaVarSetExprEval: Optional[bool],
                 formulaVarSetExprResult: Optional[bool],
                 formulaVarsOrder: Optional[bool],
                 formulaeFile: Optional[str],
                 httpUserAgent: Optional[str],
                 httpsRedirectCache: Optional[bool],
                 importFiles: Optional[str],
                 infosetValidate: Optional[bool],
                 internetConnectivity: Optional[str],
                 internetLogDownloads: Optional[bool],
                 internetRecheck: Optional[str],
                 internetTimeout: Optional[int],
                 keepOpen: Optional[bool],
                 labelLang: Optional[str],
                 labelRole: Optional[str],
                 logCodeFilter: Optional[str],
                 logFile: Optional[str],
                 logFormat: Optional[str],
                 logLevel: Optional[str],
                 logLevelFilter: Optional[str],
                 logRefObjectProperties: bool,
                 logTextMaxLength: Optional[int],
                 monitorParentProcess: Optional[bool],
                 noCertificateCheck: Optional[bool],
                 outputAttribution: Optional[str],
                 packageManifestName: Optional[str],
                 packages: str,
                 parameterSeparator: Optional[str],
                 parameters: Optional[str],
                 password: Optional[str],
                 plugins: str,
                 preFile: Optional[str],
                 proxy: Optional[str],
                 relationshipCols: Optional[int],
                 roleTypesFile: Optional[str],
                 rssReport: Optional[str],
                 rssReportCols: Optional[int],
                 saveTargetFiling: Optional[bool],
                 saveTargetInstance: Optional[bool],
                 showEnvironment: Optional[bool],
                 showOptions: Optional[bool],
                 skipDTS: Optional[bool],
                 skipExpectedInstanceComparison: Optional[bool],
                 skipLoading: Optional[bool],
                 statusPipe: Optional[str],
                 tableFile: Optional[str],
                 testReport: Optional[str],
                 testReportCols: Optional[int],
                 testcaseResultOptions: Optional[str],
                 testcaseResultsCaptureWarnings: Optional[bool],
                 timeVariableSetEvaluation: Optional[bool],
                 uiLang: Optional[str],
                 username: Optional[str],
                 utrUrl: Optional[str],
                 utrValidate: Optional[bool],
                 validate: Optional[bool],
                 validateEFM: Optional[bool],
                 validateEFMCalcTree: Optional[bool],
                 validateHMRC: Optional[bool],
                 validateTestcaseSchema: Optional[bool],
                 versReportFile: Optional[str],
                 viewArcrole: Optional[bool],
                 viewFile: Optional[str],
                 xdgConfigHome: Optional[str]):
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
        self.xdgConfigHome = xdgConfigHome


def buildOptionsObject(options):
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
    # for option_name in options:
    # if option_name not in OPTIONS_LIST: options_object.add(option_name)
    return options_object
