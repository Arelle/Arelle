"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from lxml.etree import DTD, XML
from operator import attrgetter
from typing import Callable, Hashable, Iterable, cast

import os
import regex

from arelle import XbrlConst
from arelle.LinkbaseType import LinkbaseType
from arelle.ModelDocument import Type as ModelDocumentType, ModelDocument, load as modelDocumentLoad
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelInstanceObject import ModelFact, ModelUnit, ModelContext, ModelInlineFact
from arelle.ModelObject import ModelObject
from arelle.ModelValue import QName, qname
from arelle.ModelXbrl import ModelXbrl
from arelle.PrototypeDtsObject import LinkPrototype
from arelle.ValidateDuplicateFacts import getDeduplicatedFacts, DeduplicationType
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XhtmlValidate import htmlEltUriAttrs
from arelle.XmlValidate import VALID
from arelle.typing import TypeGetText
from arelle.utils.PluginData import PluginData
from .Constants import xhtmlDtdExtension, PROHIBITED_HTML_TAGS, PROHIBITED_HTML_ATTRIBUTES
from .ControllerPluginData import ControllerPluginData
from .CoverItemRequirements import CoverItemRequirements
from .DeiRequirements import DeiRequirements, DEI_LOCAL_NAMES
from .FilingFormat import FilingFormat, FILING_FORMATS
from .FormType import FormType
from .ManifestInstance import ManifestInstance
from .ReportFolderType import HTML_EXTENSIONS
from .Statement import Statement, STATEMENTS, BalanceSheet, StatementInstance, StatementType
from .UploadContents import UploadContents, UploadPathInfo

_: TypeGetText


STANDARD_TAXONOMY_URL_PREFIXES = frozenset((
    'http://disclosure.edinet-fsa.go.jp/taxonomy/',
    'https://disclosure.edinet-fsa.go.jp/taxonomy/',
    'http://www.xbrl.org/20',
    'https://www.xbrl.org/20',
    'http://www.xbrl.org/lrr/',
    'https://www.xbrl.org/lrr/',
    'http://xbrl.org/20',
    'https://xbrl.org/20',
    'http://www.xbrl.org/dtr/',
    'https://www.xbrl.org/dtr/',
    'http://www.w3.org/1999/xlink',
    'https://www.w3.org/1999/xlink'
))

LANG_ATTRIBUTE_VALUES = frozenset({'ja', 'jp', 'ja-jp', 'JA', 'JP', 'JA-JP'})

@dataclass(frozen=True)
class UriReference:
    attributeName: str
    attributeValue: str
    document: ModelDocument
    element: ModelObject


@dataclass
class PluginValidationDataExtension(PluginData):
    # Namespaces
    jpcrpEsrNamespace: str
    jpcrpNamespace: str
    jpctlNamespace: str
    jpcrpSbrNamespace: str
    jpdeiNamespace: str
    jpigpNamespace: str
    jplvhNamespace: str
    jppfsNamespace: str
    jpspsEsrNamespace: str
    jpspsSbrNamespace: str
    jpspsNamespace: str
    jptoiNamespace: str
    jptooPstNamespace: str
    jptooToaNamespace: str
    jptooTonNamespace: str
    jptooTorNamespace: str
    jptooWtoNamespace: str

    accountingStandardsDeiQn: QName
    assetsIfrsQn: QName
    consolidatedOrNonConsolidatedAxisQn: QName
    documentTypeDeiQn: QName
    jpcrpEsrFilingDateCoverPageQn: QName
    jpcrpFilingDateCoverPageQn: QName
    jpspsFilingDateCoverPageQn: QName
    nonConsolidatedMemberQn: QName
    ratioOfFemaleDirectorsAndOtherOfficersQn: QName

    coverItemRequirementsPath: Path
    coverPageTitleQns: tuple[QName, ...]
    deiItems: tuple[QName, ...]
    deiRequirementsPath: Path

    _namespaceMap: dict[str, str]
    _uriReferences: list[UriReference]

    def __init__(self, name: str, validateXbrl: ValidateXbrl):
        super().__init__(name)

        # Namespaces
        self.jpcrpEsrNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp-esr/2024-11-01/jpcrp-esr_cor"
        self.jpcrpNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2024-11-01/jpcrp_cor'
        self.jpcrpSbrNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp-sbr/2024-11-01/jpcrp-sbr_cor"
        self.jpctlNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpctl/2024-11-01/jpctl_cor'
        self.jpdeiNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor'
        self.jpigpNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2024-11-01/jpigp_cor"
        self.jplvhNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jplvh/2024-11-01/jplvh_cor"
        self.jppfsNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor"
        self.jpspsEsrNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps-esr/2024-11-01/jpsps-esr_cor'
        self.jpspsSbrNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps-sbr/2024-11-01/jpsps-sbr_cor'
        self.jpspsNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps/2024-11-01/jpsps_cor'
        self.jptoiNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jptoi/2024-11-01/jptoi_cor'
        self.jptooPstNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-pst/2024-11-01/jptoo-pst_cor'
        self.jptooToaNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-toa/2024-11-01/jptoo-toa_cor'
        self.jptooTonNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-ton/2024-11-01/jptoo-ton_cor'
        self.jptooTorNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-tor/2024-11-01/jptoo-tor_cor'
        self.jptooWtoNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jptoo-wto/2024-11-01/jptoo-wto_cor'
        self._namespaceMap = {
            "jpcrp-esr_cor": self.jpcrpEsrNamespace,
            "jpcrp-sbr_cor": self.jpcrpSbrNamespace,
            "jpcrp_cor": self.jpcrpNamespace,
            "jpctl_cor": self.jpctlNamespace,
            "jpdei_cor": self.jpdeiNamespace,
            "jpigp_cor": self.jpigpNamespace,
            "jplvh_cor": self.jplvhNamespace,
            "jppfs_cor": self.jppfsNamespace,
            "jpsps_cor": self.jpspsNamespace,
            "jpsps-esr_cor": self.jpspsEsrNamespace,
            "jpsps-sbr_cor": self.jpspsSbrNamespace,
            "jptoi_cor": self.jptoiNamespace,
            "jptoo-pst_cor": self.jptooPstNamespace,
            "jptoo-toa_cor": self.jptooToaNamespace,
            "jptoo-ton_cor": self.jptooTonNamespace,
            "jptoo-tor_cor": self.jptooPstNamespace,
            "jptoo-wto_cor": self.jptooWtoNamespace,
        }

        # QNames
        self.accountingStandardsDeiQn = qname(self.jpdeiNamespace, 'AccountingStandardsDEI')
        self.assetsIfrsQn = qname(self.jpigpNamespace, 'AssetsIFRS')
        self.consolidatedOrNonConsolidatedAxisQn = qname(self.jppfsNamespace, 'ConsolidatedOrNonConsolidatedAxis')
        self.documentTypeDeiQn = qname(self.jpdeiNamespace, 'DocumentTypeDEI')
        self.issuedSharesTotalNumberOfSharesEtcQn = qname(self.jpcrpNamespace, 'IssuedSharesTotalNumberOfSharesEtcTextBlock')
        self.jpcrpEsrFilingDateCoverPageQn = qname(self.jpcrpEsrNamespace, 'FilingDateCoverPage')
        self.jpcrpFilingDateCoverPageQn = qname(self.jpcrpNamespace, 'FilingDateCoverPage')
        self.jpspsFilingDateCoverPageQn = qname(self.jpspsNamespace, 'FilingDateCoverPage')
        self.nonConsolidatedMemberQn = qname(self.jppfsNamespace, "NonConsolidatedMember")
        self.ratioOfFemaleDirectorsAndOtherOfficersQn = qname(self.jpcrpNamespace, "RatioOfFemaleDirectorsAndOtherOfficers")

        self.coverItemRequirementsPath = Path(__file__).parent / "resources" / "cover-item-requirements.json"
        self.coverPageTitleQns = (
            qname(self.jpspsNamespace, "DocumentTitleAnnualSecuritiesReportCoverPage"),
            qname(self.jpcrpNamespace, "DocumentTitleCoverPage"),
            qname(self.jpcrpEsrNamespace, "DocumentTitleCoverPage"),
            qname(self.jpspsNamespace, "DocumentTitleCoverPage"),
        )
        self.deiItems = tuple(
            qname(self.jpdeiNamespace, localName)
            for localName in DEI_LOCAL_NAMES
        )
        self.deiRequirementsPath = Path(__file__).parent / "resources" / "dei-requirements.csv"

        self._uriReferences = []
        self._initialize(validateXbrl.modelXbrl)

    # Identity hash for caching.
    def __hash__(self) -> int:
        return id(self)

    @lru_cache(1)
    def _contextMatchesStatement(self, modelXbrl: ModelXbrl, contextId: str, statement: Statement) -> bool:
        """
        :return: Whether the context's facts are applicable to the given statement.
        """
        if 'Interim' in contextId:
            # valid06.zip suggests "interim"" contexts are not considered for balance sheets.
            return False
        context = modelXbrl.contexts[contextId]
        if not all(dimQn == self.consolidatedOrNonConsolidatedAxisQn for dimQn in context.qnameDims):
            return False
        memberValue = context.dimMemberQname(self.consolidatedOrNonConsolidatedAxisQn, includeDefaults=True)
        contextIsConsolidated = memberValue != self.nonConsolidatedMemberQn
        return bool(statement.isConsolidated == contextIsConsolidated)

    def _initializeDocument(self, uri: str, modelDocument: ModelDocument, modelXbrl: ModelXbrl) -> None:
        docPath = Path(uri)
        basePath = Path(str(modelXbrl.fileSource.basefile))
        if not docPath.is_relative_to(basePath):
            return
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        controllerPluginData.addUsedFilepath(docPath.relative_to(basePath))
        for elt, name, value in self.getUriAttributeValues(modelDocument):
            self._uriReferences.append(UriReference(
                attributeName=name,
                attributeValue=value,
                document=modelDocument,
                element=elt,
            ))
            fullPath = (Path(modelDocument.uri).parent / value).resolve()
            if fullPath.is_relative_to(basePath):
                fileSourcePath = fullPath.relative_to(basePath)
                controllerPluginData.addUsedFilepath(fileSourcePath)
            referenceUri = str(fullPath)
            if (
                    fullPath.suffix in HTML_EXTENSIONS and
                    referenceUri not in modelXbrl.urlDocs and
                    modelXbrl.fileSource.exists(referenceUri)
            ):
                referenceModelDocument = modelDocumentLoad(
                    modelXbrl,
                    referenceUri,
                    referringElement=elt
                )
                if referenceModelDocument is not None:
                    self._initializeDocument(referenceUri, referenceModelDocument, modelXbrl)

    def _initialize(self, modelXbrl: ModelXbrl) -> None:
        if not isinstance(modelXbrl.fileSource.basefile, str):
            return
        # Additional documents may be loaded, so make a copy to iterate over.
        urlDocs = list(modelXbrl.urlDocs.items())
        for uri, modelDocument in urlDocs:
            self._initializeDocument(uri, modelDocument, modelXbrl)

    def addToTableOfContents(self, modelXbrl: ModelXbrl) -> None:
        uploadContents = self.getUploadContents(modelXbrl)
        if uploadContents is None:
            return
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        tocBuilder = controllerPluginData.getTableOfContentsBuilder()
        for modelDocument in modelXbrl.urlDocs.values():
            path = Path(modelDocument.uri)
            if modelDocument.type != ModelDocumentType.INLINEXBRL:
                continue
            pathInfo = uploadContents.uploadPathsByFullPath.get(path)
            if pathInfo is not None and not pathInfo.isCoverPage:
                tocBuilder.addDocument(modelDocument)

    def qname(self, prefix: str, localName: str) -> QName:
        return qname(self._namespaceMap[prefix], localName)

    @lru_cache(1)
    def isCorporateForm(self, modelXbrl: ModelXbrl) -> bool:
        formTypes = self.getFormTypes(modelXbrl)
        return any(
            formType.isCorporateForm
            for formType in formTypes
        )

    def isCorporateReport(self, modelXbrl: ModelXbrl) -> bool:
        return self.jpcrpNamespace in modelXbrl.namespaceDocs

    def isExtensionUri(self, uri: str, modelXbrl: ModelXbrl) -> bool:
        if uri.startswith(modelXbrl.uriDir):
            return True
        return not any(uri.startswith(taxonomyUri) for taxonomyUri in STANDARD_TAXONOMY_URL_PREFIXES)

    @lru_cache(1)
    def isStockForm(self, modelXbrl: ModelXbrl) -> bool:
        formTypes = self.getFormTypes(modelXbrl)
        return any(
            formType.isStockReport
            for formType in formTypes
        )

    @lru_cache(1)
    def getExtensionConcepts(self, modelXbrl: ModelXbrl) -> list[ModelConcept]:
        """
        Returns a list of extension concepts in the DTS.
        """
        extensionConcepts = []
        for concepts in modelXbrl.nameConcepts.values():
            for concept in concepts:
                if self.isExtensionUri(concept.document.uri, modelXbrl):
                    extensionConcepts.append(concept)
        return extensionConcepts

    @lru_cache(1)
    def getUsedConcepts(self, modelXbrl: ModelXbrl) -> set[ModelConcept]:
        """
        Returns a set of concepts used on facts and in explicit dimensions
        """
        usedConcepts = {fact.concept for fact in modelXbrl.facts if fact.concept is not None}
        for context in modelXbrl.contextsInUse:
            for dim in context.scenDimValues.values():
                if dim.isExplicit:
                    usedConcepts.update([dim.dimension, dim.member])
        return usedConcepts

    def getBalanceSheets(self, modelXbrl: ModelXbrl, statement: Statement) -> list[BalanceSheet]:
        """
        :return: Balance sheet data for each context/unit pairing the given statement.
        """
        balanceSheets: list[BalanceSheet] = []
        if statement.roleUri not in modelXbrl.roleTypes:
            return balanceSheets
        if statement.statementType not in (
                StatementType.BALANCE_SHEET,
                StatementType.STATEMENT_OF_FINANCIAL_POSITION
        ):
            return balanceSheets

        relSet = modelXbrl.relationshipSet(
            tuple(LinkbaseType.CALCULATION.getArcroles()),
            linkrole=statement.roleUri
        )
        rootConcepts = relSet.rootConcepts
        if len(rootConcepts) == 0:
            return balanceSheets

        # GFM 1.2.7 and 1.2.10 asserts no duplicate contexts and units, respectively,
        # so context and unit IDs can be used as a key.
        factsByContextIdAndUnitId = self.getFactsByContextAndUnit(
            modelXbrl,
            attrgetter("id"),
            attrgetter("id"),
            tuple(concept.qname for concept in rootConcepts)
        )

        for (contextId, unitId), facts in factsByContextIdAndUnitId.items():
            if not self._contextMatchesStatement(modelXbrl, contextId, statement):
                continue
            creditSum = Decimal(0)
            debitSum = Decimal(0)
            for fact in facts:
                if isinstance(fact.xValue, float):
                    value = Decimal(fact.xValue)
                else:
                    value = cast(Decimal, fact.xValue)
                if fact.concept.balance == "debit":
                    debitSum += value
                elif fact.concept.balance == "credit":
                    creditSum += value
            balanceSheets.append(
                BalanceSheet(
                    creditSum=creditSum,
                    contextId=str(contextId),
                    facts=facts,
                    debitSum=debitSum,
                    unitId=str(unitId),
                )
            )
        return balanceSheets

    @lru_cache(1)
    def getCoverItemRequirements(self, modelXbrl: ModelXbrl) -> list[QName] | None:
        manifestInstance = self.getManifestInstance(modelXbrl)
        if manifestInstance is None:
            return None
        if any(e is not None and e.startswith('EDINET.EC5800E') for e in modelXbrl.errors):
            # Manifest TOC parsing failed, so cannot determine cover items.
            return None
        assert len(manifestInstance.tocItems) == 1, _("Only one TOC item should be associated with this instance.")
        roleUri = manifestInstance.tocItems[0].extrole
        roleUri = roleUri.replace("_std_", "_")
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        coverItemRequirements = controllerPluginData.getCoverItemRequirements(self.coverItemRequirementsPath)
        coverItems = coverItemRequirements.get(roleUri)
        return [
            self.qname(prefix, localName)
            for prefix, localName in
            [name.split(':') for name in coverItems]
        ]

    @lru_cache(1)
    def getCoverItems(self, modelXbrl: ModelXbrl) -> frozenset[QName]:
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        coverItemRequirements = controllerPluginData.getCoverItemRequirements(self.coverItemRequirementsPath)
        coverItems = coverItemRequirements.all()
        return frozenset(
            self.qname(prefix, localName)
            for prefix, localName in
            [name.split(':') for name in coverItems]
        )

    def getDeiRequirements(self, modelXbrl: ModelXbrl) -> DeiRequirements:
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        return controllerPluginData.getDeiRequirements(self.deiRequirementsPath, self.deiItems, FILING_FORMATS)

    @lru_cache(1)
    def getExtensionSchemas(self, modelXbrl: ModelXbrl) -> dict[str, UploadPathInfo]:
        namespacePathInfos: dict[str, UploadPathInfo] = {}
        uploadContents = self.getUploadContents(modelXbrl)
        if uploadContents is None:
            return namespacePathInfos
        for modelDocument in modelXbrl.urlDocs.values():
            if modelDocument.type != ModelDocumentType.SCHEMA:
                continue # Not a schema
            if modelDocument.targetNamespace is None:
                continue # No target namespace
            if not self.isExtensionUri(modelDocument.uri, modelXbrl):
                continue # Not an extension schema
            path = Path(modelDocument.uri)
            pathInfo = uploadContents.uploadPathsByFullPath.get(path)
            if pathInfo is None or pathInfo.reportFolderType is None:
                continue # Not part of the filing, error will be caught elsewhere
            namespacePathInfos[modelDocument.targetNamespace] = pathInfo
        return namespacePathInfos

    def getProblematicTextBlocks(self, modelXbrl: ModelXbrl) -> list[ModelInlineFact]:
        problematicTextBlocks: list[ModelInlineFact] = []
        dtd = DTD(os.path.join(modelXbrl.modelManager.cntlr.configDir, xhtmlDtdExtension))
        htmlBodyTemplate = "<body><div>\n{0}\n</div></body>\n"
        for fact in modelXbrl.facts:
            concept = fact.concept
            if isinstance(fact, ModelInlineFact) and not fact.isNil and concept is not None and concept.isTextBlock and not fact.isEscaped:
                xmlBody = htmlBodyTemplate.format(fact.value)
                try:
                    textblockXml = XML(xmlBody)
                    if not dtd.validate(textblockXml):
                        problematicTextBlocks.append(fact)
                except Exception:
                    problematicTextBlocks.append(fact)
        return problematicTextBlocks

    @lru_cache(1)
    def getStatementInstance(self, modelXbrl: ModelXbrl, statement: Statement) -> StatementInstance | None:
        if statement.roleUri not in modelXbrl.roleTypes:
            return None
        return StatementInstance(
            balanceSheets=self.getBalanceSheets(modelXbrl, statement),
            statement=statement,
        )

    @lru_cache(1)
    def getStatementInstances(self, modelXbrl: ModelXbrl) -> list[StatementInstance]:
        return [
            statementInstance
            for statement in STATEMENTS
            if (statementInstance := self.getStatementInstance(modelXbrl, statement)) is not None
        ]

    @property
    def uriReferences(self) -> list[UriReference]:
        return self._uriReferences

    @lru_cache(1)
    def getDeduplicatedFacts(self, modelXbrl: ModelXbrl) -> list[ModelFact]:
        return getDeduplicatedFacts(modelXbrl, DeduplicationType.CONSISTENT_PAIRS)

    def getFactsByContextAndUnit(
            self, modelXbrl: ModelXbrl,
            getContextKey: Callable[[ModelContext], Hashable],
            getUnitKey: Callable[[ModelUnit], Hashable],
            qnames: tuple[QName, ...] | None = None,
    ) -> dict[tuple[Hashable, Hashable], list[ModelFact]]:
        deduplicatedFacts = self.getDeduplicatedFacts(modelXbrl)
        getFactsByContextAndUnit = defaultdict(list)
        for fact in deduplicatedFacts:
            if qnames is not None and fact.qname not in qnames:
                continue
            if fact.context is None or fact.unit is None:
                continue
            contextKey = getContextKey(fact.context)
            unitKey = getUnitKey(fact.unit)
            getFactsByContextAndUnit[(contextKey, unitKey)].append(fact)
        return dict(getFactsByContextAndUnit)

    @lru_cache(1)
    def getFootnoteLinkElements(self, modelXbrl: ModelXbrl) -> list[ModelObject | LinkPrototype]:
        # TODO: Consolidate with similar implementations in EDGAR and FERC
        doc = modelXbrl.modelDocument
        if doc is None:
            return []
        if doc.type in (ModelDocumentType.INLINEXBRL, ModelDocumentType.INLINEXBRLDOCUMENTSET):
            elts = (linkPrototype
                            for linkKey, links in modelXbrl.baseSets.items()
                            for linkPrototype in links
                            if linkPrototype.modelDocument.type in (ModelDocumentType.INLINEXBRL, ModelDocumentType.INLINEXBRLDOCUMENTSET)
                            and linkKey[1] and linkKey[2] and linkKey[3]  # fully specified roles
                            and linkKey[0] != "XBRL-footnotes")
        else:
            rootElt = doc.xmlDocument.getroot()
            elts = rootElt.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}footnoteLink")
        return [
            elt
            for elt in elts
            if isinstance(elt, (ModelObject, LinkPrototype))
        ]

    @lru_cache(1)
    def getFilingFormat(self, modelXbrl: ModelXbrl) ->  FilingFormat | None:
        # This function attempts to identify the filing format based on form number and title concepts.
        # The provided form number value directly informs the format.
        # However, the document title is not necessarily an explicit setting of the format's
        # document type. In the samples available to us and in a handful of public filings,
        # it is effective to match the first segment of the title value against document type
        # values assigned to the various FilingFormats. This may only be by coincidence or convention.
        # If it doesn't end up being reliable, we may need to find another way to identify the form.
        # For example, by disclosure system selection or CLI argument.
        documentTitleFacts = []
        for qname in self.coverPageTitleQns:
            for fact in self.iterValidNonNilFacts(modelXbrl, qname):
                documentTitleFacts.append(fact)
        formTypes = self.getFormTypes(modelXbrl)
        filingFormats = []
        for filingFormatIndex, filingFormat in enumerate(FILING_FORMATS):
            if filingFormat.formType not in formTypes:
                continue
            prefixes = {taxonomy.value for taxonomy in filingFormat.taxonomies}
            if not any(
                str(fact.xValue).startswith(filingFormat.documentType.value) and
                fact.concept.qname.prefix.split('_')[0] in prefixes
                for fact in documentTitleFacts
            ):
                continue
            filingFormats.append((filingFormat, filingFormatIndex))
        if len(filingFormats) == 0:
            modelXbrl.error(
                "arelle:NoMatchingEdinetFormat",
                _("No matching EDINET filing formats could be identified based on form "
                  "type (%(formTypes)s) and title."),
                formTypes=", ".join(t.value for t in formTypes),
                modelObject=documentTitleFacts,
            )
            return None
        if len(filingFormats) > 1:
            formatIndexes = [str(idx + 1) for _, idx in filingFormats]
            modelXbrl.error(
                "arelle:MultipleMatchingEdinetFormats",
                _("Multiple EDINET filing formats (%(formatIndexes)s) matched based on form "
                  "type %(formTypes)s and title."),
                formatIndexes=formatIndexes,
                formTypes=formTypes,
                modelObject=documentTitleFacts,
            )
            return None
        filingFormat, filingFormatIndex = filingFormats[0]
        modelXbrl.modelManager.cntlr.addToLog("Identified filing format: #{}, {}, {}, {}, {}".format(
            filingFormatIndex + 1,
            filingFormat.ordinance.value,
            filingFormat.documentType.value,
            filingFormat.formType.value,
            ', '.join(taxonomy.value for taxonomy in filingFormat.taxonomies)
        ), messageCode="info")
        return filingFormat

    @lru_cache(1)
    def getFormTypes(self, modelXbrl: ModelXbrl) -> set[FormType]:
        """
        Retrieves form type values from the instance.
        Note that the underlying concept is labeled "DocumentTypeDEI",
        but "Document Type" refers to something else in EDINET documentation.
        In practice, the value of this field is the form number / form type.
        :param modelXbrl: Instance to get form types from.
        :return: Set of discovered form types.
        """
        formTypes = set()
        for fact in self.iterValidNonNilFacts(modelXbrl, self.documentTypeDeiQn):
            formType = FormType.parse(fact.textValue)
            if formType is not None:
                formTypes.add(formType)
        return formTypes

    @lru_cache(1)
    def getManifestInstance(self, modelXbrl: ModelXbrl) -> ManifestInstance | None:
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        return controllerPluginData.matchManifestInstance(modelXbrl.ixdsDocUrls)

    @lru_cache(1)
    def getProhibitedAttributeElements(self, modelDocument: ModelDocument) -> list[tuple[ModelObject, str]]:
        results: list[tuple[ModelObject, str]] = []
        if modelDocument.type not in (ModelDocumentType.INLINEXBRL, ModelDocumentType.HTML):
            return results
        for elt in modelDocument.xmlRootElement.iter():
            if not isinstance(elt, ModelObject):
                continue
            for attributeName in elt.attrib:
                if attributeName in PROHIBITED_HTML_ATTRIBUTES:
                    results.append((elt, str(attributeName)))
        return results

    @lru_cache(1)
    def getProhibitedTagElements(self, modelDocument: ModelDocument) -> list[ModelObject]:
        elts: list[ModelObject] = []
        if modelDocument.type not in (ModelDocumentType.INLINEXBRL, ModelDocumentType.HTML):
            return elts
        for elt in modelDocument.xmlRootElement.iter():
            if not isinstance(elt, ModelObject):
                continue
            tag = elt.qname.localName
            if tag in PROHIBITED_HTML_TAGS:
                elts.append(elt)
        return elts

    def getStandardTaxonomyExtensionLinks(self, linkbaseType: LinkbaseType, modelXbrl: ModelXbrl) -> list[ModelObject]:
        elts: list[ModelObject] = []
        for modelDocument in modelXbrl.urlDocs.values():
            if self.isStandardTaxonomyUrl(modelDocument.uri, modelXbrl) or not modelDocument.type == ModelDocumentType.SCHEMA:
                continue
            rootElt = modelDocument.xmlRootElement
            for elt in rootElt.iterdescendants(XbrlConst.qnLinkLinkbaseRef.clarkNotation):
                uri = elt.attrib.get(XbrlConst.qnXlinkHref.clarkNotation)
                role = elt.attrib.get(XbrlConst.qnXlinkRole.clarkNotation)
                if not role == linkbaseType.getRefUri() or self.isExtensionUri(uri, modelXbrl):
                    continue
                elts.append(elt)
        return elts

    def getUploadContents(self, modelXbrl: ModelXbrl) -> UploadContents | None:
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        return controllerPluginData.getUploadContents()

    @lru_cache(1)
    def getUriAttributeValues(self, modelDocument: ModelDocument) -> list[tuple[ModelObject, str, str]]:
        results: list[tuple[ModelObject, str, str]] = []
        modelDocumentType = modelDocument.type
        # Normal document parsing does not assign the HTML type to HTML files.
        # Use ModelDocumentType.identify to check for HTML files.
        if modelDocumentType == ModelDocumentType.UnknownXML:
            modelDocumentType = ModelDocumentType.identify(modelDocument.modelXbrl.fileSource, modelDocument.uri)
        if modelDocumentType not in (ModelDocumentType.INLINEXBRL, ModelDocumentType.HTML):
            return results
        for elt in modelDocument.xmlRootElement.iter():
            for name in htmlEltUriAttrs.get(elt.localName, ()):
                value = elt.get(name)
                if value is not None:
                    results.append((elt, name, value))
        return results

    def hasValidNonNilFact(self, modelXbrl: ModelXbrl, qname: QName) -> bool:
        return any(True for fact in self.iterValidNonNilFacts(modelXbrl, qname))

    def isStandardTaxonomyUrl(self, uri: str, modelXbrl: ModelXbrl) -> bool:
        return modelXbrl.modelManager.disclosureSystem.hrefValidForDisclosureSystem(uri)

    def iterCoverPages(self, modelXbrl: ModelXbrl) -> Iterable[ModelDocument]:
        uploadContents = self.getUploadContents(modelXbrl)
        if uploadContents is None:
            return
        for url, doc in modelXbrl.urlDocs.items():
            path = Path(url)
            pathInfo = uploadContents.uploadPathsByFullPath.get(path)
            if pathInfo is None or not pathInfo.isCoverPage:
                continue
            yield doc

    def iterFacts(self, modelXbrl: ModelXbrl, qname: QName) -> Iterable[ModelFact]:
        yield from modelXbrl.factsByQname.get(qname, set())

    def iterValidFacts(self, modelXbrl: ModelXbrl, qname: QName) -> Iterable[ModelFact]:
        for fact in self.iterFacts(modelXbrl, qname):
            if fact.xValid >= VALID:
                yield fact

    def iterValidNonNilFacts(self, modelXbrl: ModelXbrl, qname: QName) -> Iterable[ModelFact]:
        for fact in self.iterValidFacts(modelXbrl, qname):
            if not fact.isNil:
                yield fact

    def addUsedFilepath(self, modelXbrl: ModelXbrl, path: Path) -> None:
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        controllerPluginData.addUsedFilepath(path)
