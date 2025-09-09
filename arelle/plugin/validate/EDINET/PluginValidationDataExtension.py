"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from lxml.etree import DTD, XML, _ElementTree, _Comment, _ProcessingInstruction
from operator import attrgetter
from typing import Callable, Hashable, Iterable, cast

import os
import regex

from arelle import UrlUtil
from arelle.LinkbaseType import LinkbaseType
from arelle.ModelDocument import Type as ModelDocumentType, ModelDocument
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
from .Constants import CORPORATE_FORMS, FormType, xhtmlDtdExtension, PROHIBITED_HTML_TAGS
from .ControllerPluginData import ControllerPluginData
from .ManifestInstance import ManifestInstance
from .Statement import Statement, STATEMENTS, BalanceSheet, StatementInstance, StatementType

_: TypeGetText


_DEBIT_QNAME_PATTERN = regex.compile('.*(Liability|Liabilities|Equity)')


@dataclass(frozen=True)
class UriReference:
    attributeName: str
    attributeValue: str
    document: ModelDocument
    element: ModelObject


@dataclass
class PluginValidationDataExtension(PluginData):
    accountingStandardsDeiQn: QName
    assetsIfrsQn: QName
    consolidatedOrNonConsolidatedAxisQn: QName
    documentTypeDeiQn: QName
    jpcrpEsrFilingDateCoverPageQn: QName
    jpcrpFilingDateCoverPageQn: QName
    jpspsFilingDateCoverPageQn: QName
    nonConsolidatedMemberQn: QName
    ratioOfFemaleDirectorsAndOtherOfficersQn: QName

    contextIdPattern: regex.Pattern[str]

    _uriReferences: list[UriReference]

    def __init__(self, name: str, validateXbrl: ValidateXbrl):
        super().__init__(name)
        jpcrpEsrNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp-esr/2024-11-01/jpcrp-esr_cor"
        self.jpcrpNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2024-11-01/jpcrp_cor'
        jpdeiNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor'
        jpigpNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2024-11-01/jpigp_cor"
        jppfsNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor"
        jpspsNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps/2024-11-01/jpsps_cor'
        self.accountingStandardsDeiQn = qname(jpdeiNamespace, 'AccountingStandardsDEI')
        self.assetsIfrsQn = qname(jpigpNamespace, 'AssetsIFRS')
        self.consolidatedOrNonConsolidatedAxisQn = qname(jppfsNamespace, 'ConsolidatedOrNonConsolidatedAxis')
        self.documentTypeDeiQn = qname(jpdeiNamespace, 'DocumentTypeDEI')
        self.issuedSharesTotalNumberOfSharesEtcQn = qname(self.jpcrpNamespace, 'IssuedSharesTotalNumberOfSharesEtcTextBlock')
        self.jpcrpEsrFilingDateCoverPageQn = qname(jpcrpEsrNamespace, 'FilingDateCoverPage')
        self.jpcrpFilingDateCoverPageQn = qname(self.jpcrpNamespace, 'FilingDateCoverPage')
        self.jpspsFilingDateCoverPageQn = qname(jpspsNamespace, 'FilingDateCoverPage')
        self.nonConsolidatedMemberQn = qname(jppfsNamespace, "NonConsolidatedMember")
        self.ratioOfFemaleDirectorsAndOtherOfficersQn = qname(self.jpcrpNamespace, "RatioOfFemaleDirectorsAndOtherOfficers")

        self.contextIdPattern = regex.compile(r'(Prior[1-9]Year|CurrentYear|Prior[1-9]Interim|Interim)(Duration|Instant)')

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

    def _initialize(self, modelXbrl: ModelXbrl) -> None:
        if not isinstance(modelXbrl.fileSource.basefile, str):
            return
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        basePath = Path(modelXbrl.fileSource.basefile)
        for uri, doc in modelXbrl.urlDocs.items():
            docPath = Path(uri)
            if not docPath.is_relative_to(basePath):
                continue
            controllerPluginData.addUsedFilepath(docPath.relative_to(basePath))
            for elt, name, value in self.getUriAttributeValues(doc):
                self._uriReferences.append(UriReference(
                    attributeName=name,
                    attributeValue=value,
                    document=doc,
                    element=elt,
                ))
                fullPath = Path(doc.uri).parent / value
                if fullPath.is_relative_to(basePath):
                    fileSourcePath = fullPath.relative_to(basePath)
                    controllerPluginData.addUsedFilepath(fileSourcePath)

    def _isDebitConcept(self, concept: ModelConcept) -> bool:
        """
        :return: Whether the given concept is a debit concept.
        """
        return bool(_DEBIT_QNAME_PATTERN.match(concept.qname.localName))

    @lru_cache(1)
    def isCorporateForm(self, modelXbrl: ModelXbrl) -> bool:
        documentTypes = self.getDocumentTypes(modelXbrl)
        if any(documentType == form.value for form in CORPORATE_FORMS for documentType in documentTypes):
            return True
        return False

    def isCorporateReport(self, modelXbrl: ModelXbrl) -> bool:
        return self.jpcrpNamespace in modelXbrl.namespaceDocs

    def isStockForm(self, modelXbrl: ModelXbrl) -> bool:
        documentTypes = self.getDocumentTypes(modelXbrl)
        return any(documentType == form.value for form in FormType if form.isStockReport for documentType in documentTypes)

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
            assetSum = Decimal(0)
            liabilitiesAndEquitySum = Decimal(0)
            for fact in facts:
                if isinstance(fact.xValue, float):
                    value = Decimal(fact.xValue)
                else:
                    value = cast(Decimal, fact.xValue)
                if self._isDebitConcept(fact.concept):
                    liabilitiesAndEquitySum += value
                else:
                    assetSum += value
            balanceSheets.append(
                BalanceSheet(
                    assetsTotal=assetSum,
                    contextId=str(contextId),
                    facts=facts,
                    liabilitiesAndEquityTotal=liabilitiesAndEquitySum,
                    unitId=str(unitId),
                )
            )
        return balanceSheets

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
    def getDocumentTypes(self, modelXbrl: ModelXbrl) -> set[str]:
        documentFacts = modelXbrl.factsByQname.get(self.documentTypeDeiQn, set())
        documentTypes = set()
        for fact in documentFacts:
            if fact.xValid >= VALID:
                documentTypes.add(fact.textValue)
        return documentTypes

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
    def getManifestInstance(self, modelXbrl: ModelXbrl) -> ManifestInstance | None:
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        return controllerPluginData.matchManifestInstance(modelXbrl.ixdsDocUrls)

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

    @lru_cache(1)
    def getUriAttributeValues(self, modelDocument: ModelDocument) -> list[tuple[ModelObject, str, str]]:
        results: list[tuple[ModelObject, str, str]] = []
        if modelDocument.type not in (ModelDocumentType.INLINEXBRL, ModelDocumentType.HTML):
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

    def iterValidNonNilFacts(self, modelXbrl: ModelXbrl, qname: QName) -> Iterable[ModelFact]:
        facts = modelXbrl.factsByQname.get(qname, set())
        for fact in facts:
            if fact.xValid >= VALID and not fact.isNil:
                yield fact

    def addUsedFilepath(self, modelXbrl: ModelXbrl, path: Path) -> None:
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        controllerPluginData.addUsedFilepath(path)
