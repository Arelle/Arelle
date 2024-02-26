'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from dataclasses import InitVar, dataclass
from typing import Any, Optional, Union

from arelle.FileSource import FileNamedStringIO
from arelle.SystemInfo import hasWebServer
from arelle.typing import TypeGetText
from arelle.ValidateDuplicateFacts import DeduplicationType

_: TypeGetText

RuntimeOptionValue = Union[bool, int, str, None]


class RuntimeOptionsException(Exception):
    pass


@dataclass(eq=False, repr=False)
class RuntimeOptions:
    """
        This class contains the runtime options for Arelle. The base options are defined as member
        variables and are passed directly to the constructor. Plugin options are dynamic and passed
        using the pluginOptions InitVar and applied to the class using setattr() in __post_init
        RuntimeOptionsException is raised if an improper combination of options are specified.
    """
    pluginOptions: InitVar[Optional[dict[str, RuntimeOptionValue]]] = None

    abortOnMajorError: Optional[bool] = None
    about: Optional[str] = None
    anchFile: Optional[str] = None
    arcroleTypesFile: Optional[str] = None
    betaObjectModel: Optional[bool] = False
    calFile: Optional[str] = None
    calcDecimals: Optional[int] = None
    calcDeduplicate: Optional[bool] = None
    calcPrecision: Optional[int] = None
    calcs: Optional[str] = None
    collectProfileStats: Optional[bool] = None
    conceptsFile: Optional[str] = None
    deduplicateFacts: Optional[DeduplicationType] = None
    diagnostics: Optional[bool] = None
    diffFile: Optional[str] = None
    dimFile: Optional[str] = None
    disablePersistentConfig: Optional[bool] = None
    disableRtl: Optional[bool] = None
    disclosureSystemName: Optional[str] = None
    DTSFile: Optional[str] = None
    entrypointFile: Optional[str] = None
    factListCols: Optional[int] = None
    factTableCols: Optional[int] = None
    factTableFile: Optional[str] = None
    factsFile: Optional[str | FileNamedStringIO] = None
    formulaAction: Optional[str] = None
    formulaAsserResultCounts: Optional[bool] = None
    formulaCacheSize: Optional[int] = None
    formulaCallExprCode: Optional[bool] = None
    formulaCallExprEval: Optional[bool] = None
    formulaCallExprResult: Optional[bool] = None
    formulaCallExprSource: Optional[bool] = None
    formulaCompileOnly: Optional[bool] = None
    formulaFormulaRules: Optional[bool] = None
    formulaParamExprResult: Optional[bool] = None
    formulaParamInputValue: Optional[bool] = None
    formulaRunIDs: Optional[int] = None
    formulaSatisfiedAsser: Optional[bool] = None
    formulaUnmessagedUnsatisfiedAsser: Optional[bool] = None
    formulaUnsatisfiedAsser: Optional[bool] = None
    formulaUnsatisfiedAsserError: Optional[bool] = None
    formulaVarExpressionCode: Optional[bool] = None
    formulaVarExpressionEvaluation: Optional[bool] = None
    formulaVarExpressionResult: Optional[bool] = None
    formulaVarExpressionSource: Optional[bool] = None
    formulaVarFilterWinnowing: Optional[bool] = None
    formulaVarFiltersResult: Optional[bool] = None
    formulaVarSetExprEval: Optional[bool] = None
    formulaVarSetExprResult: Optional[bool] = None
    formulaVarsOrder: Optional[bool] = None
    formulaeFile: Optional[str] = None
    httpUserAgent: Optional[str] = None
    httpsRedirectCache: Optional[bool] = None
    importFiles: Optional[str] = None
    infosetValidate: Optional[bool] = None
    internetConnectivity: Optional[str] = None
    internetLogDownloads: Optional[bool] = None
    internetRecheck: Optional[str] = None
    internetTimeout: Optional[int] = None
    keepOpen: Optional[bool] = None
    labelLang: Optional[str] = None
    labelRole: Optional[str] = None
    logCodeFilter: Optional[str] = None
    logFile: Optional[str] = None
    logFileMode: Optional[str] = None
    logFormat: Optional[str] = None
    logLevel: Optional[str] = None
    logLevelFilter: Optional[str] = None
    logRefObjectProperties: Optional[str] = None
    logTextMaxLength: Optional[int] = None
    monitorParentProcess: Optional[bool] = None
    noCertificateCheck: Optional[bool] = None
    outputAttribution: Optional[str] = None
    packageManifestName: Optional[str] = None
    packages: Optional[list[str]] = None
    parameterSeparator: Optional[str] = None
    parameters: Optional[str] = None
    password: Optional[str] = None
    plugins: Optional[str] = None
    preFile: Optional[str] = None
    proxy: Optional[str] = None
    relationshipCols: Optional[int] = None
    roleTypesFile: Optional[str] = None
    rssReport: Optional[str] = None
    rssReportCols: Optional[int] = None
    saveDeduplicatedInstance: Optional[bool] = None
    showEnvironment: Optional[bool] = None
    showOptions: Optional[bool] = None
    skipDTS: Optional[bool] = None
    skipLoading: Optional[bool] = None
    statusPipe: Optional[str] = None
    tableFile: Optional[str] = None
    testReport: Optional[str] = None
    testReportCols: Optional[int] = None
    testcaseResultOptions: Optional[str] = None
    testcaseResultsCaptureWarnings: Optional[bool] = None
    timeVariableSetEvaluation: Optional[bool] = None
    uiLang: Optional[str] = None
    username: Optional[str] = None
    utrUrl: Optional[str] = None
    utrValidate: Optional[bool] = None
    validate: Optional[bool] = None
    validateDuplicateFacts: Optional[str] = None
    validateEFM: Optional[bool] = None
    validateEFMCalcTree: Optional[bool] = None
    validateHMRC: Optional[bool] = None
    validateTestcaseSchema: Optional[bool] = None
    versReportFile: Optional[str | FileNamedStringIO] = None
    viewArcrole: Optional[bool] = None
    viewFile: Optional[str | FileNamedStringIO] = None
    webserver: Optional[str] = None
    xdgConfigHome: Optional[str] = None

    def __eq__(self, other: Any) -> bool:
        """ Default dataclass implementation doesn't consider plugin applied options. """
        if isinstance(other, RuntimeOptions):
            return vars(self) == vars(other)
        return NotImplemented

    def __repr__(self) -> str:
        """ Default dataclass implementation doesn't consider plugin applied options. """
        r = ", ".join(
            f"{name}={option}"
            for name, option in sorted(vars(self).items())
        )
        return f"{self.__class__.__name__}({r})"

    def __post_init__(self, pluginOptions: Optional[dict[str, RuntimeOptionValue]]) -> None:
        """
        This runs through the options object, verifies that the arguments are expected and sets the options appropriately
        :param pluginOptions: Options that are introduced via plugins
        :return: Nothing
        """
        if pluginOptions:
            existingBaseOptions = sorted(
                optionName
                for optionName in pluginOptions.keys()
                if hasattr(self, optionName)
            )
            if existingBaseOptions:
                raise RuntimeOptionsException(_('Provided plugin options already exist as base options {}').format(existingBaseOptions))
            for optionName, optionValue in pluginOptions.items():
                setattr(self, optionName, optionValue)
        if (self.entrypointFile is None and
                not self.proxy and
                not self.plugins and
                not pluginOptions and
                not self.webserver):
            raise RuntimeOptionsException(_('Incorrect arguments'))
        if self.webserver and not hasWebServer():
            raise RuntimeOptionsException(_("Webserver option requires webserver module"))
        if self.webserver and any((
                self.entrypointFile, self.importFiles, self.diffFile, self.versReportFile,
                self.factsFile, self.factListCols, self.factTableFile, self.factTableCols,
                self.relationshipCols, self.conceptsFile, self.preFile, self.tableFile, self.calFile,
                self.dimFile, self.anchFile, self.formulaeFile, self.viewArcrole, self.viewFile,
                self.roleTypesFile, self.arcroleTypesFile
        )):
            raise RuntimeOptionsException(_('Incorrect arguments with webserver'))
