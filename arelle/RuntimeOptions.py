from arelle.typing import TypeGetText
from arelle.SystemInfo import hasWebServer
from dataclasses import InitVar, dataclass
from typing import Optional, Union

_: TypeGetText

RuntimeOptionValue = Union[bool, int, str, None]


class RuntimeOptionsException(Exception):
    pass


@dataclass()
class RuntimeOptions:
    pluginOptions: InitVar[Optional[dict[str, RuntimeOptionValue]]] = None,
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
    showEnvironment: Optional[bool] = None,
    showOptions: Optional[bool] = None,
    skipDTS: Optional[bool] = None,
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
    viewer_feature_review: Optional[bool] = False,
    viewFile: Optional[str] = None,
    webserver: Optional[str] = None,
    xdgConfigHome: Optional[str] = None

    def __post_init__(self, pluginOptions: Optional[dict[str, RuntimeOptionValue]]) -> None:
        if pluginOptions:
            existingBaseOptions = sorted(
                optionName
                for optionName in pluginOptions.keys()
                if hasattr(self, optionName)
            )
            if existingBaseOptions:
                raise RuntimeOptionsException(_('Provided plugin options already exist as base options {}'.format(existingBaseOptions)))
            for optionName, optionValue in pluginOptions.items():
                setattr(self, optionName, optionValue)
        if (self.entrypointFile is None and ((not self.proxy) and (not self.plugins) and
                                             (not any(pluginOption for pluginOption in pluginOptions.keys())) and
                                             (not hasWebServer or self.webserver is None))):
            raise RuntimeOptionsException(_('Incorrect arguments'))
        if hasWebServer and self.webserver and any((
                self.entrypointFile, self.importFiles, self.diffFile, self.versReportFile,
                self.factsFile, self.factListCols, self.factTableFile, self.factTableCols, self.relationshipCols,
                self.conceptsFile, self.preFile, self.tableFile, self.calFile, self.dimFile, self.anchFile, self.formulaeFile, self.viewArcrole, self.viewFile,
                self.roleTypesFile, self.arcroleTypesFile
                )):
            raise RuntimeOptionsException(_('Incorrect arguments with webserver'))
