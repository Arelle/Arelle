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
from .Constants import xhtmlDtdExtension, PROHIBITED_HTML_TAGS, PROHIBITED_HTML_ATTRIBUTES
from .ControllerPluginData import ControllerPluginData
from .CoverPageRequirements import CoverPageRequirements, COVER_PAGE_ITEM_LOCAL_NAMES
from .FilingFormat import FilingFormat, FILING_FORMATS
from .FormType import FormType
from .ManifestInstance import ManifestInstance
from .Statement import Statement, STATEMENTS, BalanceSheet, StatementInstance, StatementType
from .UploadContents import UploadContents

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
    jpcrpEsrNamespace: str
    jpcrpFilingDateCoverPageQn: QName
    jpcrpNamespace: str
    jpdeiNamespace: str
    jpigpNamespace: str
    jppfsNamespace: str
    jpspsFilingDateCoverPageQn: QName
    jpspsNamespace: str
    nonConsolidatedMemberQn: QName
    ratioOfFemaleDirectorsAndOtherOfficersQn: QName

    contextIdPattern: regex.Pattern[str]
    coverPageItems: tuple[QName, ...]
    coverPageRequirementsPath: Path
    coverPageTitleQns: tuple[QName, ...]

    _uriReferences: list[UriReference]

    def __init__(self, name: str, validateXbrl: ValidateXbrl):
        super().__init__(name)

        # Namespaces
        self.jpcrpEsrNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp-esr/2024-11-01/jpcrp-esr_cor"
        self.jpcrpNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2024-11-01/jpcrp_cor'
        self.jpdeiNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor'
        self.jpigpNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2024-11-01/jpigp_cor"
        self.jppfsNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor"
        self.jpspsNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps/2024-11-01/jpsps_cor'

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

        self.contextIdPattern = regex.compile(r'(Prior[1-9]Year|CurrentYear|Prior[1-9]Interim|Interim)(Duration|Instant)')
        self.coverPageItems = tuple(
            qname(self.jpdeiNamespace, localName)
            for localName in COVER_PAGE_ITEM_LOCAL_NAMES
        )
        self.coverPageRequirementsPath = Path(__file__).parent / "resources" / "cover-page-requirements.csv"
        self.coverPageTitleQns = (
            qname(self.jpspsNamespace, "DocumentTitleAnnualSecuritiesReportCoverPage"),
            qname(self.jpcrpNamespace, "DocumentTitleCoverPage"),
            qname(self.jpcrpEsrNamespace, "DocumentTitleCoverPage"),
            qname(self.jpspsNamespace, "DocumentTitleCoverPage"),
        )

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
        formTypes = self.getFormTypes(modelXbrl)
        return any(
            formType.isCorporateForm
            for formType in formTypes
        )

    def isCorporateReport(self, modelXbrl: ModelXbrl) -> bool:
        return self.jpcrpNamespace in modelXbrl.namespaceDocs

    @lru_cache(1)
    def isStockForm(self, modelXbrl: ModelXbrl) -> bool:
        formTypes = self.getFormTypes(modelXbrl)
        return any(
            formType.isStockReport
            for formType in formTypes
        )

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

    def getCoverPageRequirements(self, modelXbrl: ModelXbrl) -> CoverPageRequirements:
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        return controllerPluginData.getCoverPageRequirements(self.coverPageRequirementsPath)

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
                formTypes=formTypes,
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

    def getUploadContents(self, modelXbrl: ModelXbrl) -> UploadContents | None:
        controllerPluginData = ControllerPluginData.get(modelXbrl.modelManager.cntlr, self.name)
        return controllerPluginData.getUploadContents()

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
