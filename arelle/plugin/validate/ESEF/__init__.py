"""
See COPYRIGHT.md for copyright information.

Filer Guidelines:
- [RTS](https://eur-lex.europa.eu/legal-content/EN/TXT/?qid=1563538104990&uri=CELEX:32019R0815)
- [ESEF Filer Manual](https://www.esma.europa.eu/sites/default/files/library/esma32-60-254_esef_reporting_manual.pdf)

GUI operation:
- Enable the validate/ESEF plugin and optionally install ESEF taxonomy packages.
- From the `Tools` menu > `Formula` > `Parameters` set the eps_threshold and optionally the authority.

Command line operation:
`python arelleCmdLine.py --plugins validate/ESEF --packages {my-package-directory}/esef_taxonomy.zip --disclosureSystem esef --validate --file {my-report-package-zip-file}`

Adding checks for formulas not automatically included:
`--parameters "eps_threshold=.01"`
Dimensional validations required by some auditors may require
`--import http://www.esma.europa.eu/taxonomy/2020-03-16/esef_all-for.xml`
and likely `--skipLoading *esef_all-cal.xml` because the esef_all-cal.xml calculations are reported to be problematic for some filings.

Authority specific validations are enabled by formula parameter authority, e.g. for Denmark or UKSEF and eps_threshold specify:
- `--parameters "eps_threshold=.01,authority=DK"`
- `--parameters "eps_threshold=.01,authority=UK"`

Using arelle as a web server:

```bash
python arelleCmdLine.py --webserver localhost:8080:cheroot --plugins validate/ESEF --packages {my-package-directory}/esef_taxonomy.zip
```

Client with curl:

```bash
curl -X POST "-HContent-type: application/zip" -T TC1_valid.zip "http://localhost:8080/rest/xbrl/validation?disclosureSystem=esef&media=text"
```
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, cast

import regex as re
from lxml.etree import XMLParser, XMLSyntaxError, parse

from arelle import ModelDocument, XhtmlValidate
from arelle.DisclosureSystem import DisclosureSystem
from arelle.FileSource import FileSource
from arelle.ModelDocument import LoadingException, ModelDocument as ModelDocumentClass
from arelle.ModelValue import qname
from arelle.ModelXbrl import ModelXbrl
from arelle.PackageManager import validateTaxonomyPackage
from arelle.ValidateXbrl import ValidateXbrl
from arelle.Version import authorLabel, copyrightLabel
from arelle.XbrlConst import xhtml
from arelle.formula.XPathContext import XPathContext
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import PluginHooks
from .ESEF_2021.ValidateXbrlFinally import validateXbrlFinally as validateXbrlFinally2021
from .ESEF_Current.ValidateXbrlFinally import validateXbrlFinally as validateXbrlFinallyCurrent
from .Util import getDisclosureSystemYear, loadAuthorityValidations

_: TypeGetText

ESEF_DISCLOSURE_SYSTEM_TEST_PROPERTY = "ESEFplugin"

ixErrorPattern = re.compile(r"ix11[.]|xmlSchema[:]|(?!xbrl.5.2.5.2|xbrl.5.2.6.2)xbrl[.]|xbrld[ti]e[:]|utre[:]")


def validateEntity(modelXbrl: ModelXbrl, filename:str, filesource: FileSource) -> None:
    consolidated = not any("unconsolidated" in n for n in modelXbrl.modelManager.disclosureSystem.names)
    contentOtherThanXHTMLGuidance = 'ESEF.2.5.1' if consolidated else 'ESEF.4.1.3'
    fullname = filesource.basedUrl(filename)
    file = filesource.file(fullname)
    try:
        parser = XMLParser(load_dtd=True, resolve_entities=False)
        root = parse(file[0], parser=parser)
        if root.docinfo.internalDTD:
            for entity in root.docinfo.internalDTD.iterentities():  # type: ignore[union-attr]
                modelXbrl.error(f"{contentOtherThanXHTMLGuidance}.maliciousCodePresent",
                                _("Documents MUST NOT contain any malicious content. Dangerous XML entity found: %(element)s."),
                                modelObject=filename, element=entity.name)
    except (UnicodeDecodeError, XMLSyntaxError) as e:
        # probably a image or a directory
        pass


def esefDisclosureSystemSelected(modelXbrl: ModelXbrl) -> bool:
    return getattr(modelXbrl.modelManager.disclosureSystem, ESEF_DISCLOSURE_SYSTEM_TEST_PROPERTY, False)


class ESEFPlugin(PluginHooks):
    @staticmethod
    def disclosureSystemTypes(
        disclosureSystem: DisclosureSystem,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[tuple[str, str], ...]:
        return (("ESEF", ESEF_DISCLOSURE_SYSTEM_TEST_PROPERTY),)

    @staticmethod
    def disclosureSystemConfigURL(
        disclosureSystem: DisclosureSystem,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        return str(Path(__file__).parent / "resources" / "config.xml")

    @staticmethod
    def modelDocumentPullLoader(
        modelXbrl: ModelXbrl,
        normalizedUri: str,
        filepath: str,
        isEntry: bool,
        namespace: str | None,
        *args: Any,
        **kwargs: Any,
    ) -> ModelDocumentClass | LoadingException | None:
        if not esefDisclosureSystemSelected(modelXbrl):
            return None
        disclosureSystemYear = getDisclosureSystemYear(modelXbrl)
        if isEntry:
            if any("unconsolidated" in n for n in modelXbrl.modelManager.disclosureSystem.names):
                if disclosureSystemYear > 2021 and re.match(r'.*[.](7z|rar|tar|jar)', normalizedUri):
                    modelXbrl.error("ESEF.Arelle.InvalidSubmissionFormat",
                                    _("Unrecognized submission format."),
                                    modelObject=modelXbrl)
                    return LoadingException("Invalid submission format")
            else:
                if isinstance(modelXbrl.fileSource.url, str) and modelXbrl.fileSource.url.endswith(".xml"):
                    documentType = ModelDocument.Type.identify(modelXbrl.fileSource, modelXbrl.fileSource.url)
                    if documentType in {ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.TESTCASE}:
                        return None  # allow zipped test case to load normally

                if disclosureSystemYear >= 2023 and not modelXbrl.fileSource.isZip:
                    modelXbrl.error("ESEF.2.6.1.disallowedReportPackageFileExtension",
                                    _("A report package MUST conform to the .ZIP File Format Specification and MUST have a .zip extension."),
                                    fileSourceType=modelXbrl.fileSource.type,
                                    modelObject=modelXbrl)
                    return LoadingException("ESEF Report Package must be .ZIP File Format")
                if modelXbrl.fileSource.isArchive:
                    if not validateTaxonomyPackage(modelXbrl.modelManager.cntlr, modelXbrl.fileSource):
                        modelXbrl.error("ESEF.RTS.Annex.III.3.missingOrInvalidTaxonomyPackage",
                            _("Single reporting package with issuer's XBRL extension taxonomy files and Inline XBRL instance document must be compliant with the latest recommended version of the Taxonomy Packages specification (1.0)"),
                            modelObject=modelXbrl)
                        return LoadingException("Invalid taxonomy package")
        return None

    @staticmethod
    def modelXbrlLoadComplete(
            modelXbrl: ModelXbrl,
            *args: Any,
            **kwargs: Any,
    ) -> None:
        if not esefDisclosureSystemSelected(modelXbrl):
            return None
        disclosureSystemYear = getDisclosureSystemYear(modelXbrl)
        if modelXbrl.modelDocument is None or modelXbrl.modelDocument.type not in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRY, ModelDocument.Type.RSSFEED):
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
            if disclosureSystemYear > 2021:
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

    @staticmethod
    def validateXbrlStart(
        val: ValidateXbrl,
        parameters: dict[Any, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if not esefDisclosureSystemSelected(val.modelXbrl) and val.validateDisclosureSystem:
            return None
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

    @staticmethod
    def validateXbrlFinally(
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if not esefDisclosureSystemSelected(val.modelXbrl) and val.validateDisclosureSystem:
            return None
        disclosureSystemYear = getDisclosureSystemYear(val.modelXbrl)
        if disclosureSystemYear == 2021:
            return validateXbrlFinally2021(val, *args, **kwargs)
        return validateXbrlFinallyCurrent(val, *args, **kwargs)

    @staticmethod
    def validateFinally(
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if not esefDisclosureSystemSelected(val.modelXbrl) and val.validateDisclosureSystem:
            return None
        if val.unconsolidated:
            return None
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

    @staticmethod
    def validateFormulaCompiled(
        modelXbrl: ModelXbrl,
        xpathContext: XPathContext,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        # request unsatisfied assertions without a message to print a trace
        # this is not conditional on validateESEFplugin so the flag is set even if DisclosureSystemChecks not requested upon compiling but set later in workflow
        xpathContext.formulaOptions.traceUnmessagedUnsatisfiedAssertions = True

    @staticmethod
    def validateFormulaFinished(
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if not esefDisclosureSystemSelected(val.modelXbrl) and val.validateDisclosureSystem:
            return None
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

    @staticmethod
    def modelTestcaseVariationReportPackageIxdsOptions(
        val: ValidateXbrl,
        rptPkgIxdsOptions: dict[str, bool],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if not esefDisclosureSystemSelected(val.modelXbrl):
            return None
        rptPkgIxdsOptions["lookOutsideReportsDirectory"] = True
        rptPkgIxdsOptions["combineIntoSingleIxds"] = True


__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    "name": "Validate ESMA ESEF",
    "aliases": [
        # Aliases for when ESEF validation was handled by multiple plugins.
        "Validate ESMA ESEF-2022",
        "validate/ESEF_2022",
    ],
    "version": "1.2023.00",
    "description": """ESMA ESEF Filer Manual and RTS Validations.""",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "ModelDocument.PullLoader": ESEFPlugin.modelDocumentPullLoader,
    "import": ("inlineXbrlDocumentSet",),  # import dependent modules
    # classes of mount points (required)
    "DisclosureSystem.Types": ESEFPlugin.disclosureSystemTypes,
    "DisclosureSystem.ConfigURL": ESEFPlugin.disclosureSystemConfigURL,
    "ModelXbrl.LoadComplete": ESEFPlugin.modelXbrlLoadComplete,
    "Validate.XBRL.Start": ESEFPlugin.validateXbrlStart,
    "Validate.XBRL.Finally": ESEFPlugin.validateXbrlFinally,  # before formula processing
    "ValidateFormula.Compiled": ESEFPlugin.validateFormulaCompiled,
    "ValidateFormula.Finished": ESEFPlugin.validateFormulaFinished,  # after formula processing
    "Validate.Finally": ESEFPlugin.validateFinally,  # run *after* formula processing
    "ModelTestcaseVariation.ReportPackageIxdsOptions": ESEFPlugin.modelTestcaseVariationReportPackageIxdsOptions,
}
