'''
Filer Guidelines:
  RTS: https://eur-lex.europa.eu/legal-content/EN/TXT/?qid=1563538104990&uri=CELEX:32019R0815
  ESEF Filer Manual https://www.esma.europa.eu/sites/default/files/library/esma32-60-254_esef_reporting_manual.pdf

Taxonomy Architecture:

Taxonomy package expected to be installed:

See COPYRIGHT.md for copyright information.

GUI operation

   install plugin validate/ESEF and optionally applicable taxonomy packages

   Under tools->formula add parameters eps_threshold and optionally authority

Command line operation:

   arelleCmdLine.exe --plugins validate/ESEF --packages {my-package-directory}/esef_taxonomy_2019.zip
     --disclosureSystem esef -v -f {my-report-package-zip-file}
   Adding checks for formulas not automatically included:
     --parameters "eps_threshold=.01"
   Dimensional validations required by some auditors may require
    --import http://www.esma.europa.eu/taxonomy/2020-03-16/esef_all-for.xml
    and likely --skipLoading *esef_all-cal.xml
    because the esef_all-cal.xml calculations are reported to be problematical for some filings

Authority specific validations are enabled by formula parameter authority, e.g. for Denmark or UKSEF and eps_threshold specify:
     --parameters "eps_threshold=.01,authority=DK"
     --parameters "eps_threshold=.01,authority=UK"

Using arelle as a web server:

   arelleCmdLine.exe --webserver localhost:8080:cheroot --plugins validate/ESEF --packages {my-package-directory}/esef_taxonomy_2019.zip

Client with curl:

   curl -X POST "-HContent-type: application/zip" -T TC1_valid.zip "http://localhost:8080/rest/xbrl/validation?disclosureSystem=esef&media=text"

'''
from __future__ import annotations
from pathlib import Path

import regex as re
from lxml.etree import parse, XMLSyntaxError, XMLParser
from arelle import ModelDocument, XhtmlValidate
from arelle.FileSource import FileSource
from arelle.ModelValue import qname
from arelle.PackageManager import validateTaxonomyPackage
from arelle.Version import authorLabel, copyrightLabel

from arelle.XbrlConst import xhtml
from .ESEF_2021.ValidateXbrlFinally import validateXbrlFinally
from .Util import loadAuthorityValidations
from arelle.typing import TypeGetText
from arelle.DisclosureSystem import DisclosureSystem
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.formula.XPathContext import XPathContext
from typing import Any, Dict, cast

_: TypeGetText  # Handle gettext

ixErrorPattern = re.compile(r"ix11[.]|xmlSchema[:]|(?!xbrl.5.2.5.2|xbrl.5.2.6.2)xbrl[.]|xbrld[ti]e[:]|utre[:]")


def is2021DisclosureSystem(modelXbrl: ModelXbrl) -> bool:
    return any("2021" in name for name in modelXbrl.modelManager.disclosureSystem.names)


def dislosureSystemTypes(disclosureSystem: DisclosureSystem, *args: Any, **kwargs: Any) -> tuple[tuple[str, str]]:
    # return ((disclosure system name, variable name), ...)
    return (("ESEF", "ESEFplugin"),)


def disclosureSystemConfigURL(disclosureSystem: DisclosureSystem, *args: Any, **kwargs: Any) -> str:
    return str(Path(__file__).parent / "resources" / "config.xml")


def modelXbrlBeforeLoading(modelXbrl: ModelXbrl, normalizedUri: str, filepath: str, isEntry: bool=False, **kwargs: Any) -> ModelDocument.LoadingException | None:
    if getattr(modelXbrl.modelManager.disclosureSystem, "ESEFplugin", False):
        if isEntry:
            if any("unconsolidated" in n for n in modelXbrl.modelManager.disclosureSystem.names):
                if not is2021DisclosureSystem(modelXbrl) and re.match(r'.*[.](7z|rar|tar|jar)', normalizedUri):
                    modelXbrl.error("ESEF.Arelle.InvalidSubmissionFormat",
                                    _("Unrecognized submission format."),
                                    modelObject=modelXbrl)
                    return ModelDocument.LoadingException("Invalid submission format")
            else:
                if modelXbrl.fileSource.isArchive:
                    if (not isinstance(modelXbrl.fileSource.selection, list) and
                        modelXbrl.fileSource.selection is not None and
                        modelXbrl.fileSource.selection.endswith(".xml") and
                        ModelDocument.Type.identify(modelXbrl.fileSource, cast(str, modelXbrl.fileSource.url)) in (
                            ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.TESTCASE)):
                        return None  # allow zipped test case to load normally
                    if not validateTaxonomyPackage(modelXbrl.modelManager.cntlr, modelXbrl.fileSource):
                        modelXbrl.error("ESEF.RTS.Annex.III.3.missingOrInvalidTaxonomyPackage",
                            _("Single reporting package with issuer's XBRL extension taxonomy files and Inline XBRL instance document must be compliant with the latest recommended version of the Taxonomy Packages specification (1.0)"),
                            modelObject=modelXbrl)
                        return ModelDocument.LoadingException("Invalid taxonomy package")
    return None


def modelXbrlLoadComplete(modelXbrl: ModelXbrl) -> None:
    if (getattr(modelXbrl.modelManager.disclosureSystem, "ESEFplugin", False) and
        (modelXbrl.modelDocument is None or modelXbrl.modelDocument.type not in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRY, ModelDocument.Type.RSSFEED))):
        if any("unconsolidated" in n for n in modelXbrl.modelManager.disclosureSystem.names):

            if modelXbrl.modelDocument is None:
                modelXbrl.error("arelle-ESEF.InvalidSubmissionFormat",
                    _("Unable to identify submission."))
                return

            htmlElement = modelXbrl.modelDocument.xmlRootElement
            if htmlElement.namespaceURI == xhtml:
                # xhtml is validated by ModelDocument inine, plain xhtml still needs validating
                XhtmlValidate.xhtmlValidate(modelXbrl, htmlElement)
            if modelXbrl.facts:
                modelXbrl.warning("arelle-ESEF:unconsolidatedContainsInline",
                                _("Inline XBRL not expected in unconsolidated xhtml document."),
                                modelObject=modelXbrl)
            return
        if modelXbrl.modelDocument is None:
            modelXbrl.error("ESEF.3.1.3.missingOrInvalidTaxonomyPackage",
                            _("RTS Annex III Par 3 and ESEF 3.1.3 requires an XBRL Report Package but one could not be loaded."),
                            modelObject=modelXbrl)
        if (modelXbrl.modelDocument is None or
            not modelXbrl.facts and "ESEF.RTS.Art.6.a.noInlineXbrlTags" not in modelXbrl.errors):
            modelXbrl.error("ESEF.RTS.Art.6.a.noInlineXbrlTags",
                            _("RTS on ESEF requires inline XBRL, no facts were reported."),
                            modelObject=modelXbrl)
        if not is2021DisclosureSystem(modelXbrl):
            if modelXbrl.fileSource.isArchive:
                if modelXbrl.fileSource.dir is not None:
                    for filename in modelXbrl.fileSource.dir:
                        validateEntity(modelXbrl, filename, modelXbrl.fileSource)
            else:
                if isinstance(modelXbrl.fileSource.url, str):
                    ixdsDocUrls = getattr(modelXbrl, "ixdsDocUrls", None)
                    if ixdsDocUrls:
                        for url in ixdsDocUrls:
                            validateEntity(modelXbrl, url, modelXbrl.fileSource)
                    else:
                        validateEntity(modelXbrl, modelXbrl.fileSource.url, modelXbrl.fileSource)
                elif isinstance(modelXbrl.fileSource.url, list):
                    for filename in modelXbrl.fileSource.url:
                        validateEntity(modelXbrl, filename, modelXbrl.fileSource)
                if modelXbrl.modelDocument:
                    # search for the zip of the taxonomy extension
                    entrypointDocs = [referencedDoc for referencedDoc in modelXbrl.modelDocument.referencesDocument.keys() if referencedDoc.type == ModelDocument.Type.SCHEMA]
                    for entrypointDoc in entrypointDocs: # usually only one
                        for filesource in modelXbrl.fileSource.referencedFileSources.values():
                            if filesource.exists(entrypointDoc.filepath) and filesource.dir is not None:
                                for filename in filesource.dir:
                                    validateEntity(modelXbrl, filename, filesource)


def validateEntity(modelXbrl: ModelXbrl, filename:str, filesource: FileSource) -> None:
    consolidated = not any("unconsolidated" in n for n in modelXbrl.modelManager.disclosureSystem.names)
    contentOtherThanXHTMLGuidance = 'ESEF.2.5.1' if consolidated else 'ESEF.4.1.3'
    fullname = filesource.basedUrl(filename)
    file = filesource.file(fullname)
    try:
        parser = XMLParser(load_dtd=True, resolve_entities=False)
        root = parse(file[0], parser=parser)
        if root.docinfo.internalDTD:
            for entity in root.docinfo.internalDTD.iterentities():  # type: ignore[attr-defined]
                modelXbrl.error(f"{contentOtherThanXHTMLGuidance}.maliciousCodePresent",
                                _("Documents MUST NOT contain any malicious content. Dangerous XML entity found: %(element)s."),
                                modelObject=filename, element=entity.name)
    except (UnicodeDecodeError, XMLSyntaxError) as e:
        # probably a image or a directory
        pass


def validateXbrlStart(val: ValidateXbrl, parameters: dict[Any, Any] | None=None, *args: Any, **kwargs: Any) -> None:
    val.validateESEFplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "ESEFplugin", False)
    if not (val.validateESEFplugin):
        return
    modelXbrl = val.modelXbrl
    val.extensionImportedUrls = set()
    val.unconsolidated = any("unconsolidated" in n for n in val.disclosureSystem.names)
    val.consolidated = not val.unconsolidated
    val.authority = None
    if parameters:
        p = parameters.get(qname("authority",noPrefixIsNoNamespace=True))
        if p and len(p) == 2 and p[1] not in ("null", "None", None):
            v = p[1] # formula dialog and cmd line formula parameters may need type conversion
            val.authority = v

    authorityValidations = loadAuthorityValidations(val.modelXbrl)
    # loadAuthorityValidations returns either a list or a dict but in this context, we expect a dict.
    # By using cast, we let mypy know that a list is _not_ expected here.
    authorityValidations = cast(Dict[Any, Any], authorityValidations)

    val.authParam = authorityValidations["default"]
    for name in val.disclosureSystem.names:
        val.authParam.update(authorityValidations.get(name, {}))
    val.authParam.update(authorityValidations.get(val.authority, {}))
    if parameters:
        overwiteParams = {}
        for key, value in parameters.items():
            if str(key) in val.authParam and len(value) == 2 and value[1] not in ("null", "None", None):
                if isinstance(val.authParam[str(key)], int):
                    try:
                        overwiteParams[str(key)] = int(value[1])
                    except ValueError:
                        modelXbrl.error("Invalid Parameter", _("%(key)s should be a int, got (value)"), key=key, value=value)
                else:
                    overwiteParams[str(key)] = value[1]
        val.authParam.update(overwiteParams)
    for convertListIntoSet in ("outdatedTaxonomyURLs", "effectiveTaxonomyURLs", "standardTaxonomyURIs", "additionalMandatoryTags"):
        if convertListIntoSet in val.authParam:
            val.authParam[convertListIntoSet] = set(val.authParam[convertListIntoSet])

    # add in formula messages if not loaded
    formulaMsgsUrls = val.authParam.get("formulaMessagesAdditionalURLs", ())
    _reCacheRelationships = False
    for docUrl in modelXbrl.urlDocs.copy():
        if docUrl in formulaMsgsUrls:
            for msgsUrl in formulaMsgsUrls[docUrl]:
                if msgsUrl not in modelXbrl.urlDocs:
                    priorValidateDisclosureSystem = modelXbrl.modelManager.validateDisclosureSystem
                    modelXbrl.modelManager.validateDisclosureSystem = False
                    ModelDocument.load(modelXbrl,msgsUrl,isSupplemental=True)
                    modelXbrl.modelManager.validateDisclosureSystem = priorValidateDisclosureSystem
                    _reCacheRelationships = True
    if _reCacheRelationships:
        modelXbrl.relationshipSets.clear() # relationships have to be re-cached

    formulaOptions = val.modelXbrl.modelManager.formulaOptions
    # skip formula IDs as needed per authority if no formula runIDs provided by environment
    val.priorFormulaOptionsRunIDs = formulaOptions.runIDs
    if not formulaOptions.runIDs and val.authParam["formulaRunIDs"]:
        formulaOptions.runIDs = val.authParam["formulaRunIDs"]


def validateFinally(val: ValidateXbrl, *args: Any, **kwargs: Any) -> None: # runs all inline checks
    if not (val.validateESEFplugin):
        return

    if val.unconsolidated:
        return

    modelXbrl = val.modelXbrl
    modelDocument = getattr(modelXbrl, "modelDocument")
    if (modelDocument is None or not modelXbrl.facts) and "ESEF.RTS.Art.6.a.noInlineXbrlTags" not in modelXbrl.errors:
        modelXbrl.error("ESEF.RTS.Art.6.a.noInlineXbrlTags",
                        _("RTS on ESEF requires inline XBRL, no facts were reported."),
                        modelObject=modelXbrl)
        return # never loaded properly

    numXbrlErrors = sum(ixErrorPattern.match(e) is not None for e in modelXbrl.errors if isinstance(e,str))
    if numXbrlErrors:
        modelXbrl.error("ESEF.RTS.Annex.III.Par.1.invalidInlineXBRL",
                        _("RTS on ESEF requires valid XBRL instances, %(numXbrlErrors)s errors were reported."),
                        modelObject=modelXbrl, numXbrlErrors=numXbrlErrors)

    # force reporting of unsatisfied assertions for which there are no messages
    traceUnmessagedUnsatisfiedAssertions = True


def validateFormulaCompiled(modelXbrl: ModelXbrl, xpathContext: XPathContext) -> None:
    # request unsatisfied assertions without a message to print a trace
    # this is not conditional on validateESEFplugin so the flag is set even if DisclosureSystemChecks not requested upon compiling but set later in workflow
    xpathContext.formulaOptions.traceUnmessagedUnsatisfiedAssertions = True


def validateFormulaFinished(val: ValidateXbrl, *args: Any, **kwargs: Any) -> None: # runs *after* formula (which is different for test suite from other operation
    if not getattr(val, 'validateESEFplugin', False):
        return

    modelXbrl = val.modelXbrl
    if hasattr(val, 'priorFormulaOptionsRunIDs'):  # reset environment formula run IDs if they were saved
        modelXbrl.modelManager.formulaOptions.runIDs = val.priorFormulaOptionsRunIDs
    sumWrnMsgs = sumErrMsgs = 0
    for e in modelXbrl.errors:
        if isinstance(e,dict):
            for id, (numSat, numUnsat, numOkMsgs, numWrnMsgs, numErrMsgs) in e.items():
                sumWrnMsgs += numWrnMsgs
                sumErrMsgs += numErrMsgs
    if sumErrMsgs:
        modelXbrl.error("ESEF.2.7.1.targetXBRLDocumentWithFormulaErrors",
                        _("Target XBRL document MUST be valid against the assertions specified in ESEF taxonomy, %(numUnsatisfied)s with errors."),
                        modelObject=modelXbrl, numUnsatisfied=sumErrMsgs)
    if sumWrnMsgs:
        modelXbrl.warning("ESEF.2.7.1.targetXBRLDocumentWithFormulaWarnings",
                        _("Target XBRL document SHOULD be valid against the assertions specified in ESEF taxonomy, %(numUnsatisfied)s with warnings."),
                        modelObject=modelXbrl, numUnsatisfied=sumWrnMsgs)


def testcaseVariationReportPackageIxdsOptions(validate: ValidateXbrl, rptPkgIxdsOptions: dict[str, bool]) -> None:
    if getattr(validate.modelXbrl.modelManager.disclosureSystem, "ESEFplugin", False):
        rptPkgIxdsOptions["lookOutsideReportsDirectory"] = True
        rptPkgIxdsOptions["combineIntoSingleIxds"] = True


__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate ESMA ESEF',
    'version': '1.2023.00',
    'description': '''ESMA ESEF Filer Manual and RTS Validations.''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    'ModelDocument.PullLoader': modelXbrlBeforeLoading,
    'import': ('inlineXbrlDocumentSet', ), # import dependent modules
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'ModelXbrl.LoadComplete': modelXbrlLoadComplete,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally, # before formula processing
    'ValidateFormula.Compiled': validateFormulaCompiled,
    'ValidateFormula.Finished': validateFormulaFinished, # after formula processing
    'Validate.Finally': validateFinally, # run *after* formula processing
    'ModelTestcaseVariation.ReportPackageIxdsOptions': testcaseVariationReportPackageIxdsOptions,
}
