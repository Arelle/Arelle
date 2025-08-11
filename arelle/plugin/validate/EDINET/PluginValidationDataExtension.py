"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import regex

from arelle.ModelDocument import Type as ModelDocumentType
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelObject import ModelObject
from arelle.ModelValue import QName, qname
from arelle.ModelXbrl import ModelXbrl
from arelle.PrototypeDtsObject import LinkPrototype
from arelle.ValidateDuplicateFacts import getDeduplicatedFacts, DeduplicationType
from arelle.XmlValidate import VALID
from arelle.typing import TypeGetText
from arelle.utils.PluginData import PluginData
from .Constants import CORPORATE_FORMS
from .ControllerPluginData import ControllerPluginData
from .ManifestInstance import ManifestInstance

_: TypeGetText


@dataclass
class PluginValidationDataExtension(PluginData):
    assetsIfrsQn: QName
    documentTypeDeiQn: QName
    jpcrpEsrFilingDateCoverPageQn: QName
    jpcrpFilingDateCoverPageQn: QName
    jpspsFilingDateCoverPageQn: QName
    liabilitiesAndEquityIfrsQn: QName
    nonConsolidatedMemberQn: QName
    ratioOfFemaleDirectorsAndOtherOfficersQn: QName

    contextIdPattern: regex.Pattern[str]

    _primaryModelXbrl: ModelXbrl | None = None

    def __init__(self, name: str):
        super().__init__(name)
        jpcrpEsrNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp-esr/2024-11-01/jpcrp-esr_cor"
        jpcrpNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2024-11-01/jpcrp_cor'
        jpdeiNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor'
        jpigpNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2024-11-01/jpigp_cor"
        jppfsNamespace = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor"
        jpspsNamespace = 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps/2024-11-01/jpsps_cor'
        self.assetsIfrsQn = qname(jpigpNamespace, 'AssetsIFRS')
        self.documentTypeDeiQn = qname(jpdeiNamespace, 'DocumentTypeDEI')
        self.jpcrpEsrFilingDateCoverPageQn = qname(jpcrpEsrNamespace, 'FilingDateCoverPage')
        self.jpcrpFilingDateCoverPageQn = qname(jpcrpNamespace, 'FilingDateCoverPage')
        self.jpspsFilingDateCoverPageQn = qname(jpspsNamespace, 'FilingDateCoverPage')
        self.liabilitiesAndEquityIfrsQn = qname(jpigpNamespace, "LiabilitiesAndEquityIFRS")
        self.nonConsolidatedMemberQn = qname(jppfsNamespace, "NonConsolidatedMember")
        self.ratioOfFemaleDirectorsAndOtherOfficersQn = qname(jpcrpNamespace, "RatioOfFemaleDirectorsAndOtherOfficers")

        self.contextIdPattern = regex.compile(r'(Prior[1-9]Year|CurrentYear|Prior[1-9]Interim|Interim)(Duration|Instant)')

    # Identity hash for caching.
    def __hash__(self) -> int:
        return id(self)

    @lru_cache(1)
    def isCorporateForm(self, modelXbrl: ModelXbrl) -> bool:
        documentTypes = self.getDocumentTypes(modelXbrl)
        if any(documentType == form.value for form in CORPORATE_FORMS for documentType in documentTypes):
            return True
        return False

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

    def hasValidNonNilFact(self, modelXbrl: ModelXbrl, qname: QName) -> bool:
        requiredFacts = modelXbrl.factsByQname.get(qname, set())
        return any(fact.xValid >= VALID and not fact.isNil for fact in requiredFacts)

    def isStandardTaxonomyUrl(self, uri: str, modelXbrl: ModelXbrl) -> bool:
        return modelXbrl.modelManager.disclosureSystem.hrefValidForDisclosureSystem(uri)
