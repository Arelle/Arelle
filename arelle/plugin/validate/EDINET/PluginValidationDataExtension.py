"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from lxml.etree import DTD, XML
from operator import attrgetter
from typing import cast

import os

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
from .DeiRequirements import DeiRequirements, DEI_LOCAL_NAMES
from .FilingFormat import FilingFormat, FILING_FORMATS, DocumentType, Ordinance
from .FormType import FormType
from .ManifestInstance import ManifestInstance
from .NamespaceConfig import NamespaceConfig
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


@dataclass(frozen=True)
class UriReference:
    attributeName: str
    attributeValue: str
    document: ModelDocument
    element: ModelObject


@dataclass
class PluginValidationDataExtension(PluginData):
    namespaces: NamespaceConfig

    accountingStandardsDeiQn: QName
    assetsIfrsQn: QName
    categoriesOfDirectorsAndOtherOfficersAxisQn: QName
    consolidatedOrNonConsolidatedAxisQn: QName
    corporateGovernanceCompanyWithAuditAndSupervisoryCommitteeTextBlockQn: QName
    corporateGovernanceCompanyWithCorporateAuditorsTextBlockQn: QName
    corporateGovernanceCompanyWithNominatingAndOtherCommitteesTextBlockQn: QName
    documentTypeDeiQn: QName
    executiveOfficersMemberQn: QName
    jpcrpEsrFilingDateCoverPageQn: QName
    jpcrpFilingDateCoverPageQn: QName
    jpspsFilingDateCoverPageQn: QName
    issuedSharesTotalNumberOfSharesEtcQn: QName
    nonConsolidatedMemberQn: QName
    ratioOfFemaleDirectorsAndOtherOfficersQn: QName

    coverItemRequirementsPath: Path
    coverPageTitleQns: tuple[QName, ...]
    deiItems: tuple[QName, ...]
    deiRequirementsPath: Path

    _uriReferences: list[UriReference]

    def __init__(self, name: str, validateXbrl: ValidateXbrl):
        super().__init__(name)

        self.namespaces = NamespaceConfig()

        # QNames
        self.accountingStandardsDeiQn = qname(self.namespaces.jpdei, 'AccountingStandardsDEI')
        self.assetsIfrsQn = qname(self.namespaces.jpigp, 'AssetsIFRS')
        self.categoriesOfDirectorsAndOtherOfficersAxisQn = qname(self.namespaces.jpcrp, 'CategoriesOfDirectorsAndOtherOfficersAxis')
        self.consolidatedOrNonConsolidatedAxisQn = qname(self.namespaces.jppfs, 'ConsolidatedOrNonConsolidatedAxis')
        self.corporateGovernanceCompanyWithAuditAndSupervisoryCommitteeTextBlockQn = qname(self.namespaces.jpcrp, 'CorporateGovernanceCompanyWithAuditAndSupervisoryCommitteeTextBlock')
        self.corporateGovernanceCompanyWithCorporateAuditorsTextBlockQn = qname(self.namespaces.jpcrp, 'CorporateGovernanceCompanyWithCorporateAuditorsTextBlock')
        self.corporateGovernanceCompanyWithNominatingAndOtherCommitteesTextBlockQn = qname(self.namespaces.jpcrp, 'CorporateGovernanceCompanyWithNominatingAndOtherCommitteesTextBlock')
        self.documentTypeDeiQn = qname(self.namespaces.jpdei, 'DocumentTypeDEI')
        self.executiveOfficersMemberQn = qname(self.namespaces.jpcrp, 'ExecutiveOfficersMember')
        self.issuedSharesTotalNumberOfSharesEtcQn = qname(self.namespaces.jpcrp, 'IssuedSharesTotalNumberOfSharesEtcTextBlock')
        self.jpcrpEsrFilingDateCoverPageQn = qname(self.namespaces.jpcrpEsr, 'FilingDateCoverPage')
        self.jpcrpFilingDateCoverPageQn = qname(self.namespaces.jpcrp, 'FilingDateCoverPage')
        self.jpspsFilingDateCoverPageQn = qname(self.namespaces.jpsps, 'FilingDateCoverPage')
        self.nonConsolidatedMemberQn = qname(self.namespaces.jppfs, "NonConsolidatedMember")
        self.ratioOfFemaleDirectorsAndOtherOfficersQn = qname(self.namespaces.jpcrp, "RatioOfFemaleDirectorsAndOtherOfficers")

        self.coverItemRequirementsPath = Path(__file__).parent / "resources" / "cover-item-requirements.json"
        self.coverPageTitleQns = (
            qname(self.namespaces.jpsps, "DocumentTitleAnnualSecuritiesReportCoverPage"),
            qname(self.namespaces.jpcrp, "DocumentTitleCoverPage"),
            qname(self.namespaces.jpcrpEsr, "DocumentTitleCoverPage"),
            qname(self.namespaces.jpsps, "DocumentTitleCoverPage"),
        )
        self.deiItems = tuple(
            qname(self.namespaces.jpdei, localName)
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
        ns = self.namespaces.get(prefix)
        assert ns is not None, f"Unknown namespace prefix: {prefix}"
        return qname(ns, localName)

    @lru_cache(1)
    def isCorporateForm(self, modelXbrl: ModelXbrl) -> bool:
        formType = self.getFormType(modelXbrl)
        if formType is None:
            return False
        return formType.isCorporateForm

    def isCorporateReport(self, modelXbrl: ModelXbrl) -> bool:
        return self.namespaces.jpcrp in modelXbrl.namespaceDocs

    def isExtensionUri(self, uri: str, modelXbrl: ModelXbrl) -> bool:
        if uri.startswith(modelXbrl.uriDir):
            return True
        return not any(uri.startswith(taxonomyUri) for taxonomyUri in STANDARD_TAXONOMY_URL_PREFIXES)

    @lru_cache(1)
    def isStockForm(self, modelXbrl: ModelXbrl) -> bool:
        formType = self.getFormType(modelXbrl)
        if formType is None:
            return False
        return formType.isStockReport

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

    @lru_cache(1)
    def getDocumentType(self, modelXbrl: ModelXbrl) -> DocumentType | None:
        """
        Retrieves document type value from the instance.
        :param modelXbrl: Instance to get document type from.
        :return: document type parsed from filename.
        """
        filingFormat = self.getFilingFormat(modelXbrl)
        if filingFormat is None:
            return None
        return filingFormat.documentType

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
        manifestInstance = self.getManifestInstance(modelXbrl)
        if manifestInstance is None:
            return None
        return manifestInstance.filingFormat

    @lru_cache(1)
    def getFormType(self, modelXbrl: ModelXbrl) -> FormType | None:
        """
        Retrieves form type value from the instance.
        :param modelXbrl: Instance to get form type from.
        :return: Form type parsed from filename.
        """
        filingFormat = self.getFilingFormat(modelXbrl)
        if filingFormat is None:
            return None
        return filingFormat.formType

    @lru_cache(1)
    def getManifestInstance(self, modelXbrl: ModelXbrl) -> ManifestInstance | None:
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        return controllerPluginData.getManifestInstance(modelXbrl)

    @lru_cache(1)
    def getOrdinance(self, modelXbrl: ModelXbrl) -> Ordinance | None:
        """
        Retrieves ordinance value from the instance.
        :param modelXbrl: Instance to get ordinance from.
        :return: Ordinance parsed from filename.
        """
        filingFormat = self.getFilingFormat(modelXbrl)
        if filingFormat is None:
            return None
        return filingFormat.ordinance

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
            if not isinstance(elt, ModelObject):
                continue
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
