"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast, Iterable

import regex as re
from lxml.etree import _Comment, _ElementTree, _Entity, _ProcessingInstruction, _Element

from arelle import XbrlConst
from arelle.FunctionIxt import ixtNamespaces
from arelle.LinkbaseType import LinkbaseType
from arelle.ModelDocument import ModelDocument, Type as ModelDocumentType
from arelle.ModelDtsObject import ModelConcept, ModelRelationship
from arelle.ModelInstanceObject import ModelContext, ModelFact, ModelInlineFootnote, ModelUnit, ModelInlineFact
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelObject import ModelObject
from arelle.ModelValue import QName, qname
from arelle.ModelXbrl import ModelXbrl
from arelle.typing import assert_type
from arelle.utils.PluginData import PluginData
from arelle.utils.validate.ValidationUtil import etreeIterWithDepth
from arelle.XbrlConst import ixbrl11, xhtmlBaseIdentifier, xmlBaseIdentifier
from arelle.XmlValidate import lexicalPatterns
from arelle.XmlValidateConst import VALID

DEFAULT_MEMBER_ROLE_URI = 'https://www.nltaxonomie.nl/kvk/role/axis-defaults'
XBRLI_IDENTIFIER_PATTERN = re.compile(r"^(?!00)\d{8}$")
XBRLI_IDENTIFIER_SCHEMA = 'http://www.kvk.nl/kvk-id'
MAX_REPORT_PACKAGE_SIZE_MBS = 100

DISALLOWED_IXT_NAMESPACES = frozenset((
    ixtNamespaces["ixt v1"],
    ixtNamespaces["ixt v2"],
    ixtNamespaces["ixt v3"],
))
UNTRANSFORMABLE_TYPES = frozenset((
"anyURI",
"base64Binary",
"duration",
"hexBinary",
"NOTATION",
"QName",
"time",
"token",
"language",
))
STYLE_IX_HIDDEN_PATTERN = re.compile(r"(.*[^\w]|^)ix-hidden\s*:\s*([\w.-]+).*")
STYLE_CSS_HIDDEN_PATTERN = re.compile(r"(.*[^\w]|^)display\s*:\s*none([^\w].*|$)")

ALLOWABLE_LANGUAGES = frozenset((
    'nl',
    'en',
    'de',
    'fr'
))

EFFECTIVE_KVK_GAAP_IFRS_ENTRYPOINT_FILES = frozenset((
    'https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-nlgaap-ext.xsd',
    'https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-ifrs-ext.xsd',
))

EFFECTIVE_KVK_GAAP_OTHER_ENTRYPOINT_FILES = frozenset((
    'https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-other-gaap.xsd',
))

NON_DIMENSIONALIZED_LINE_ITEM_LINKROLES = frozenset((
    'https://www.nltaxonomie.nl/kvk/role/lineitems-nondimensional-usage',
))

TAXONOMY_URLS_BY_YEAR = {
    '2024': {
        'https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-nlgaap-ext.xsd',
        'https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-ifrs-ext.xsd',
        'https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-other-gaap.xsd',
    }
}

STANDARD_TAXONOMY_URLS = frozenset((
    'http://www.nltaxonomie.nl/ifrs/20',
    'https://www.nltaxonomie.nl/ifrs/20',
    'http://www.nltaxonomie.nl/',
    'https://www.nltaxonomie.nl/',
    'http://www.xbrl.org/taxonomy/int/lei/',
    'https://www.xbrl.org/taxonomy/int/lei/',
    'http://www.xbrl.org/20',
    'https://www.xbrl.org/20',
    'http://www.xbrl.org/lrr/',
    'https://www.xbrl.org/lrr/',
    'http://xbrl.org/20',
    'https://xbrl.org/20',
    'http://xbrl.ifrs.org/',
    'https://xbrl.ifrs.org/',
    'http://www.xbrl.org/dtr/',
    'https://www.xbrl.org/dtr/',
    'http://xbrl.org/2020/extensible-enumerations-2.0',
    'https://xbrl.org/2020/extensible-enumerations-2.0',
    'http://www.w3.org/1999/xlink',
    'https://www.w3.org/1999/xlink'
))

QN_DOMAIN_ITEM_TYPES = frozenset((
    qname("{http://www.xbrl.org/dtr/type/2022-03-31}nonnum:domainItemType"),
))

SUPPORTED_IMAGE_TYPES_BY_IS_FILE = {
    True: ('gif', 'jpg', 'jpeg', 'png'),
    False: ('gif', 'jpeg', 'png'),
}


@dataclass(frozen=True)
class AnchorData:
    anchorsInDimensionalElrs: dict[str, frozenset[ModelRelationship]]
    anchorsNotInBase: frozenset[ModelRelationship]
    anchorsWithDimensionItem: frozenset[ModelRelationship]
    anchorsWithDomainItem: frozenset[ModelRelationship]
    extLineItemsNotAnchored: frozenset[ModelConcept]
    extLineItemsWronglyAnchored: frozenset[ModelConcept]


@dataclass(frozen=True)
class ContextData:
    contextsWithImproperContent: list[ModelContext | None]
    contextsWithPeriodTime: list[ModelContext | None]
    contextsWithPeriodTimeZone: list[ModelContext | None]
    contextsWithSegments: list[ModelContext | None]


@dataclass(frozen=True)
class DimensionalData:
    domainMembers: frozenset[ModelConcept]
    elrPrimaryItems: dict[str, set[ModelConcept]]
    primaryItems: frozenset[ModelConcept]


@dataclass(frozen=True)
class ExtensionData:
    extensionConcepts: list[ModelConcept]
    extensionDocuments: dict[ModelDocument, ExtensionDocumentData]
    extensionImportedUrls: frozenset[str]


@dataclass(frozen=True)
class ExtensionDocumentData:
    basename: str
    hrefXlinkRole: str | None
    linkbases: list[LinkbaseData]

    def iterArcsByType(
            self,
            linkbaseType: LinkbaseType,
            includeArcroles: set[str] | None = None,
            excludeArcroles: set[str] | None = None,
    ) -> Iterable[_Element]:
        """
        Returns a list of LinkbaseData objects for the specified LinkbaseType.
        """
        for linkbase in self.iterLinkbasesByType(linkbaseType):
            for arc in linkbase.arcs:
                if includeArcroles is not None:
                    if arc.get(XbrlConst.qnXlinkArcRole.clarkNotation) not in includeArcroles:
                        continue
                if excludeArcroles is not None:
                    if arc.get(XbrlConst.qnXlinkArcRole.clarkNotation) in excludeArcroles:
                        continue
                yield arc

    def iterLinkbasesByType(self, linkbaseType: LinkbaseType) -> Iterable[LinkbaseData]:
        """
        Returns a list of LinkbaseData objects for the specified LinkbaseType.
        """
        for linkbase in self.linkbases:
            if linkbase.linkbaseType == linkbaseType:
                yield linkbase


@dataclass(frozen=True)
class HiddenElementsData:
    cssHiddenFacts: set[ModelInlineFact]
    eligibleForTransformHiddenFacts: set[ModelInlineFact]
    hiddenFactsOutsideHiddenSection: set[ModelInlineFact]
    requiredToDisplayFacts: set[ModelInlineFact]


@dataclass(frozen=True)
class InlineHTMLData:
    baseElements: set[Any]
    noMatchLangFootnotes: set[ModelInlineFootnote]
    orphanedFootnotes: set[ModelInlineFootnote]
    tupleElements: set[tuple[Any]]
    factLangFootnotes: dict[ModelInlineFootnote, set[str]]
    fractionElements: set[Any]


@dataclass(frozen=True)
class LinkbaseData:
    arcs: list[_Element]
    basename: str
    element: _Element
    linkbaseType: LinkbaseType | None
    prohibitedBaseConcepts: list[ModelConcept]
    prohibitingLabelElements: list[_Element]

    @property
    def hasArcs(self) -> bool:
        return len(self.arcs) > 0


@dataclass
class PluginValidationDataExtension(PluginData):
    chamberOfCommerceRegistrationNumberQn: QName
    documentAdoptionDateQn: QName
    documentAdoptionStatusQn: QName
    documentResubmissionUnsurmountableInaccuraciesQn: QName
    entrypointRoot: str
    entrypoints: set[str]
    financialReportingPeriodQn: QName
    financialReportingPeriodCurrentStartDateQn: QName
    financialReportingPeriodCurrentEndDateQn: QName
    financialReportingPeriodPreviousStartDateQn: QName
    financialReportingPeriodPreviousEndDateQn: QName
    formattedExplanationItemTypeQn: QName | None
    ifrsIdentifier: str
    permissibleGAAPRootAbstracts: frozenset[QName]
    permissibleIFRSRootAbstracts: frozenset[QName]
    textFormattingSchemaPath: str
    textFormattingWrapper: str

    # Identity hash for caching.
    def __hash__(self) -> int:
        return id(self)

    def addDomMbrs(self, modelXbrl: ModelXbrl, sourceDomMbr: ModelConcept, ELR: str, membersSet: set[ModelConcept]) -> None:
        if isinstance(sourceDomMbr, ModelConcept) and sourceDomMbr not in membersSet:
            membersSet.add(sourceDomMbr)
            for domMbrRel in modelXbrl.relationshipSet(XbrlConst.domainMember, ELR).fromModelObject(sourceDomMbr):
                self.addDomMbrs(modelXbrl, domMbrRel.toModelObject, domMbrRel.consecutiveLinkrole, membersSet)


    @lru_cache(1)
    def checkContexts(self, modelXbrl: ModelXbrl) -> ContextData:
        allContexts = modelXbrl.contextsByDocument()
        contextsWithImproperContent: list[ModelContext | None] = []
        contextsWithPeriodTime: list[ModelContext | None] = []
        contextsWithPeriodTimeZone: list[ModelContext | None] = []
        contextsWithSegments: list[ModelContext | None] = []
        datetimePattern = lexicalPatterns["XBRLI_DATEUNION"]
        for contexts in allContexts.values():
            for context in contexts:
                for uncastElt in context.iterdescendants("{http://www.xbrl.org/2003/instance}startDate",
                                                          "{http://www.xbrl.org/2003/instance}endDate",
                                                          "{http://www.xbrl.org/2003/instance}instant"):
                    elt = cast(Any, uncastElt)
                    m = datetimePattern.match(elt.stringValue)
                    if m:
                        if m.group(1):
                            contextsWithPeriodTime.append(context)
                        if m.group(3):
                            contextsWithPeriodTimeZone.append(context)
                if context.hasSegment:
                    contextsWithSegments.append(context)
                if context.nonDimValues("scenario"):
                    contextsWithImproperContent.append(context)
        return ContextData(
            contextsWithImproperContent=contextsWithImproperContent,
            contextsWithPeriodTime=contextsWithPeriodTime,
            contextsWithPeriodTimeZone=contextsWithPeriodTimeZone,
            contextsWithSegments=contextsWithSegments,
        )

    def checkLabels(self, issues: set[ModelConcept| None], modelXbrl: ModelXbrl, parent: ModelConcept, relSet: ModelRelationshipSet, labelrole: str | None, visited: set[ModelConcept]) -> set[ModelConcept| None]:
        visited.add(parent)
        conceptRels = defaultdict(list) # counts for concepts without preferred label role
        for rel in relSet.fromModelObject(parent):
            child = rel.toModelObject
            if child is not None:
                labelrole = rel.preferredLabel
                if not labelrole:
                    conceptRels[child].append(rel)
                if child not in visited:
                    self.checkLabels(issues, modelXbrl, child, relSet, labelrole, visited)
        for concept, rels in conceptRels.items():
            if len(rels) > 1:
                issues.add(concept)
        visited.remove(parent)
        return issues

    @lru_cache(1)
    def checkHiddenElements(self, modelXbrl: ModelXbrl) -> HiddenElementsData:
        cssHiddenFacts = set()
        eligibleForTransformHiddenFacts = set()
        hiddenEltIds = {}
        hiddenFactsOutsideHiddenSection = set()
        ixHiddenFacts = set()
        presentedHiddenEltIds = defaultdict(list)
        requiredToDisplayFacts = set()
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
            ixNStag = str(getattr(ixdsHtmlRootElt.modelDocument, "ixNStag", ixbrl11))
            for ixHiddenElt in ixdsHtmlRootElt.iterdescendants(tag=ixNStag + "hidden"):
                for tag in (ixNStag + "nonNumeric", ixNStag+"nonFraction"):
                    for ixElt in ixHiddenElt.iterdescendants(tag=tag):
                        if getattr(ixElt, "xValid", 0) >= VALID:
                            if ixElt.concept.baseXsdType not in UNTRANSFORMABLE_TYPES and not ixElt.isNil:
                                eligibleForTransformHiddenFacts.add(ixElt)
                        if ixElt.id:
                            hiddenEltIds[ixElt.id] = ixElt
                        ixHiddenFacts.add(ixElt)
            for cssHiddenElt in ixdsHtmlRootElt.getroottree().iterfind(".//{http://www.w3.org/1999/xhtml}*[@style]"):
                if STYLE_CSS_HIDDEN_PATTERN.match(cssHiddenElt.get("style","")):
                    for tag in (ixNStag + "nonNumeric", ixNStag+"nonFraction"):
                        for ixElt in cssHiddenElt.iterdescendants(tag=tag):
                            if ixElt not in ixHiddenFacts:
                                cssHiddenFacts.add(ixElt)
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
            for ixElt in ixdsHtmlRootElt.getroottree().iterfind(".//{http://www.w3.org/1999/xhtml}*[@style]"):
                styleValue = ixElt.get("style","")
                hiddenFactRefMatch = STYLE_IX_HIDDEN_PATTERN.match(styleValue)
                if hiddenFactRefMatch:
                    hiddenFactRef = hiddenFactRefMatch.group(2)
                    if hiddenFactRef not in hiddenEltIds:
                        hiddenFactsOutsideHiddenSection.add(ixElt)
                    else:
                        presentedHiddenEltIds[hiddenFactRef].append(ixElt)
        for hiddenEltId, ixElt in hiddenEltIds.items():
            if (hiddenEltId not in presentedHiddenEltIds and
                    getattr(ixElt, "xValid", 0) >= VALID and # may not be validated
                    (ixElt.concept.baseXsdType in UNTRANSFORMABLE_TYPES or ixElt.isNil)):
                requiredToDisplayFacts.add(ixElt)
        return HiddenElementsData(
            cssHiddenFacts=cssHiddenFacts,
            eligibleForTransformHiddenFacts=eligibleForTransformHiddenFacts,
            hiddenFactsOutsideHiddenSection=hiddenFactsOutsideHiddenSection,
            requiredToDisplayFacts=requiredToDisplayFacts,
        )

    @lru_cache(1)
    def checkInlineHTMLElements(self, modelXbrl: ModelXbrl) -> InlineHTMLData:
        baseElements = set()
        factLangs = self.factLangs(modelXbrl)
        footnotesRelationshipSet = modelXbrl.relationshipSet("XBRL-footnotes")
        factLangFootnotes = defaultdict(set)
        fractionElements = set()
        noMatchLangFootnotes = set()
        tupleElements = set()
        orphanedFootnotes = set()
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
            ixNStag = str(getattr(ixdsHtmlRootElt.modelDocument, "ixNStag", ixbrl11))
            ixTupleTag = ixNStag + "tuple"
            ixFractionTag = ixNStag + "fraction"
            for elts in modelXbrl.ixdsEltById.values():   # type: ignore[attr-defined]
                for elt in elts:
                    if isinstance(elt, ModelInlineFootnote):
                        if elt.textValue is not None:
                            if not any(isinstance(rel.fromModelObject, ModelFact)
                                       for rel in footnotesRelationshipSet.toModelObject(elt)):
                                orphanedFootnotes.add(elt)
                            if elt.xmlLang not in factLangs:
                                noMatchLangFootnotes.add(elt)
                            if elt.xmlLang is not None:
                                for rel in footnotesRelationshipSet.toModelObject(elt):
                                    if rel.fromModelObject is not None:
                                        fromObj = cast(ModelObject, rel.fromModelObject)
                                        lang = cast(str, elt.xmlLang)
                                        factLangFootnotes[fromObj].add(lang)
                    if elt.tag == ixTupleTag:
                        tupleElements.add(elt)
                    if elt.tag == ixFractionTag:
                        fractionElements.add(elt)
            for elt, depth in etreeIterWithDepth(ixdsHtmlRootElt):
                if elt.get(xmlBaseIdentifier) is not None:
                    baseElements.add(elt)
                if elt.tag == xhtmlBaseIdentifier:
                    baseElements.add(elt)
        factLangFootnotes.default_factory = None
        assert_type(factLangFootnotes, defaultdict[ModelObject, set[str]])
        return InlineHTMLData(
            baseElements=baseElements,
            factLangFootnotes=cast(dict[ModelInlineFootnote, set[str]], factLangFootnotes),
            fractionElements=fractionElements,
            noMatchLangFootnotes=noMatchLangFootnotes,
            orphanedFootnotes=orphanedFootnotes,
            tupleElements=tupleElements,
        )


    @lru_cache(1)
    def factsByDocument(self, modelXbrl: ModelXbrl) -> dict[str, list[ModelFact]]:
        factsByDocument = defaultdict(list)
        for fact in modelXbrl.facts:
            factsByDocument[fact.modelDocument.filepath].append(fact)
        factsByDocument.default_factory = None
        return factsByDocument

    @lru_cache(1)
    def factLangs(self, modelXbrl: ModelXbrl) -> set[str]:
        factLangs = set()
        for fact in modelXbrl.facts:
            if fact is not None:
                factLangs.add(fact.xmlLang)
        return factLangs

    @lru_cache(1)
    def getAnchorData(self, modelXbrl: ModelXbrl) -> AnchorData:
        extLineItemsNotAnchored = set()
        extLineItemsWronglyAnchored = set()
        widerNarrowerRelSet = modelXbrl.relationshipSet(XbrlConst.widerNarrower)
        generalSpecialRelSet = modelXbrl.relationshipSet(XbrlConst.generalSpecial)
        calcRelSet = modelXbrl.relationshipSet(XbrlConst.summationItems)
        dimensionalData = self.getDimensionalData(modelXbrl)
        primaryItems = dimensionalData.primaryItems
        extensionData = self.getExtensionData(modelXbrl)
        for concept in extensionData.extensionConcepts:
            if concept.isPrimaryItem and \
                    not concept.isAbstract and \
                    concept in primaryItems and \
                    not widerNarrowerRelSet.contains(concept) and \
                    not calcRelSet.fromModelObject(concept):
                if not generalSpecialRelSet.contains(concept):
                    extLineItemsNotAnchored.add(concept)
                else:
                    extLineItemsWronglyAnchored.add(concept)
        elrsContainingDimensionalRelationships = set(
            ELR
            for arcrole, ELR, linkqname, arcqname in modelXbrl.baseSets.keys()
            if arcrole == "XBRL-dimensions" and ELR is not None)
        anchorsNotInBase = set()
        anchorsWithDomainItem = set()
        anchorsWithDimensionItem = set()
        anchorsInDimensionalElrs = defaultdict(set)
        for anchoringRel in widerNarrowerRelSet.modelRelationships:
            elr = anchoringRel.linkrole
            fromObj = anchoringRel.fromModelObject
            toObj = anchoringRel.toModelObject
            if fromObj is not None and toObj is not None and fromObj.type is not None and toObj.type is not None:
                if not ((not self.isExtensionUri(fromObj.modelDocument.uri, modelXbrl)) ^ (not self.isExtensionUri(toObj.modelDocument.uri, modelXbrl))):
                    anchorsNotInBase.add(anchoringRel)
                if fromObj.type.isDomainItemType or toObj.type.isDomainItemType:
                    anchorsWithDomainItem.add(anchoringRel)
                elif fromObj.isDimensionItem or toObj.isDimensionItem:
                    anchorsWithDimensionItem.add(anchoringRel)
                else:
                    if elr in elrsContainingDimensionalRelationships:
                        anchorsInDimensionalElrs[elr].add(anchoringRel)
        return AnchorData(
            anchorsInDimensionalElrs={x: frozenset(y) for x, y in anchorsInDimensionalElrs.items()},
            anchorsNotInBase=frozenset(anchorsNotInBase),
            anchorsWithDimensionItem=frozenset(anchorsWithDimensionItem),
            anchorsWithDomainItem=frozenset(anchorsWithDomainItem),
            extLineItemsNotAnchored=frozenset(extLineItemsNotAnchored),
            extLineItemsWronglyAnchored=frozenset(extLineItemsWronglyAnchored),
        )


    def getBaseElements(self, modelXbrl: ModelXbrl) -> set[Any | None]:
        return self.checkInlineHTMLElements(modelXbrl).baseElements

    def getContextsWithImproperContent(self, modelXbrl: ModelXbrl) -> list[ModelContext | None]:
        return self.checkContexts(modelXbrl).contextsWithImproperContent

    def getContextsWithPeriodTime(self, modelXbrl: ModelXbrl) -> list[ModelContext | None]:
        return self.checkContexts(modelXbrl).contextsWithPeriodTime

    def getContextsWithPeriodTimeZone(self, modelXbrl: ModelXbrl) -> list[ModelContext | None]:
        return self.checkContexts(modelXbrl).contextsWithPeriodTimeZone

    def getContextsWithSegments(self, modelXbrl: ModelXbrl) -> list[ModelContext | None]:
        return self.checkContexts(modelXbrl).contextsWithSegments

    @lru_cache(1)
    def getDocumentsInDts(self, modelXbrl: ModelXbrl) -> dict[ModelDocument, str | None]:
        modelDocuments: dict[ModelDocument, str | None] = {}
        if modelXbrl.modelDocument is None:
            return modelDocuments

        def _getDocumentsInDts(modelDocument: ModelDocument) -> None:
            for referencedDocument, modelDocumentReference in modelDocument.referencesDocument.items():
                if referencedDocument in modelDocuments:
                    continue
                if referencedDocument.inDTS:
                    modelDocuments[referencedDocument] = modelDocumentReference.referringXlinkRole
                    _getDocumentsInDts(referencedDocument)

        modelDocuments[modelXbrl.modelDocument] = None
        _getDocumentsInDts(modelXbrl.modelDocument)
        return modelDocuments

    @lru_cache(1)
    def getDimensionalData(self, modelXbrl: ModelXbrl) -> DimensionalData:
        domainMembers = set()  # concepts which are dimension domain members
        elrPrimaryItems = defaultdict(set)
        hcPrimaryItems: set[ModelConcept] = set()
        hcMembers: set[Any] = set()
        primaryItems: set[ModelConcept] = set()
        for hasHypercubeArcrole in (XbrlConst.all, XbrlConst.notAll):
            hasHypercubeRelationships = modelXbrl.relationshipSet(hasHypercubeArcrole).fromModelObjects()
            for hasHcRels in hasHypercubeRelationships.values():
                for hasHcRel in hasHcRels:
                    sourceConcept: ModelConcept = hasHcRel.fromModelObject
                    hcPrimaryItems.add(sourceConcept)
                    # find associated primary items to source concept
                    for domMbrRel in modelXbrl.relationshipSet(XbrlConst.domainMember).fromModelObject(sourceConcept):
                        if domMbrRel.consecutiveLinkrole == hasHcRel.linkrole: # only those related to this hc
                            self.addDomMbrs(modelXbrl, domMbrRel.toModelObject, domMbrRel.consecutiveLinkrole, hcPrimaryItems)
                    primaryItems.update(hcPrimaryItems)
                    hc = hasHcRel.toModelObject
                    for hcDimRel in modelXbrl.relationshipSet(XbrlConst.hypercubeDimension, hasHcRel.consecutiveLinkrole).fromModelObject(hc):
                        dim = hcDimRel.toModelObject
                        if isinstance(dim, ModelConcept):
                            for dimDomRel in modelXbrl.relationshipSet(XbrlConst.dimensionDomain, hcDimRel.consecutiveLinkrole).fromModelObject(dim):
                                dom = dimDomRel.toModelObject
                                if isinstance(dom, ModelConcept):
                                    self.addDomMbrs(modelXbrl, dom, dimDomRel.consecutiveLinkrole, hcMembers)
                    domainMembers.update(hcMembers)
                    if hasHcRel.linkrole in NON_DIMENSIONALIZED_LINE_ITEM_LINKROLES or hcMembers:
                        for hcPrimaryItem in hcPrimaryItems:
                            if not hcPrimaryItem.isAbstract:
                                elrPrimaryItems[hasHcRel.linkrole].add(hcPrimaryItem)
                                elrPrimaryItems["*"].add(hcPrimaryItem) # members of any ELR
                    hcPrimaryItems.clear()
                    hcMembers.clear()
        return DimensionalData(
            domainMembers=frozenset(domainMembers),
            elrPrimaryItems=elrPrimaryItems,
            primaryItems=frozenset(primaryItems),
        )

    def getEligibleForTransformHiddenFacts(self, modelXbrl: ModelXbrl) -> set[ModelInlineFact]:
        return self.checkHiddenElements(modelXbrl).eligibleForTransformHiddenFacts

    def getFactLangFootnotes(self, modelXbrl: ModelXbrl) -> dict[ModelInlineFootnote, set[str]]:
        return self.checkInlineHTMLElements(modelXbrl).factLangFootnotes

    def getFractionElements(self, modelXbrl: ModelXbrl) -> set[Any]:
        return self.checkInlineHTMLElements(modelXbrl).fractionElements

    def getHiddenFactsOutsideHiddenSection(self, modelXbrl: ModelXbrl) -> set[ModelInlineFact]:
        return self.checkHiddenElements(modelXbrl).hiddenFactsOutsideHiddenSection

    @lru_cache(1)
    def getFilenameAllowedCharactersPattern(self) -> re.Pattern[str]:
        return re.compile(
            r"^[\w\.-]*$",
            flags=re.ASCII
        )

    @lru_cache(1)
    def getFilenameFormatPattern(self) -> re.Pattern[str]:
        return re.compile(
            r"^(?<base>[^-]*)"
            r"-(?<year>\d{4})-(?<month>0[1-9]|1[012])-(?<day>0?[1-9]|[12][0-9]|3[01])"
            r"-(?<lang>[^-]*)"
            r"\.(?<extension>html|htm|xhtml)$",
            flags=re.ASCII
        )

    @lru_cache(1)
    def getExtensionFilenameFormatPattern(self) -> re.Pattern[str]:
        return re.compile(
            r"^(?<base>[^-]*)"
            r"-(?<year>\d{4})-(?<month>0[1-9]|1[012])-(?<day>0?[1-9]|[12][0-9]|3[01])"
            r"(?<suffix>[_pre|_cal|_lab|_def]*)"
            r"(?<lang>-*[^-]*)"
            r"\.(?<extension>xsd|xml)$",
            flags=re.ASCII
        )

    @lru_cache(1)
    def getFilenameParts(self, filename: str, filenamePattern: re.Pattern[str]) -> dict[str, Any] | None:
        match = filenamePattern.match(filename)
        if match:
            return match.groupdict()
        return None

    @lru_cache(1)
    def getIxdsDocBasenames(self, modelXbrl: ModelXbrl) -> set[str]:
        return set(Path(url).name for url in getattr(modelXbrl, "ixdsDocUrls", []))

    @lru_cache(1)
    def getExtensionConcepts(self, modelXbrl: ModelXbrl) -> list[ModelConcept]:
        """
        Returns a list of extension concepts in the DTS.
        """
        extensionConcepts = []
        for concepts in modelXbrl.nameConcepts.values():
            for concept in concepts:
                if self.isExtensionUri(concept.qname.namespaceURI, modelXbrl):
                    extensionConcepts.append(concept)
        return extensionConcepts

    @lru_cache(1)
    def getExtensionData(self, modelXbrl: ModelXbrl) -> ExtensionData:
        extensionDocuments = {}
        extensionImportedUrls = set()
        documentsInDts = self.getDocumentsInDts(modelXbrl)
        for modelDocument, hrefXlinkRole in documentsInDts.items():
            if not self.isExtensionUri(modelDocument.uri, modelDocument.modelXbrl):
                # Skip non-extension documents
                continue
            if modelDocument.type in (ModelDocumentType.LINKBASE, ModelDocumentType.SCHEMA):
                extensionDocuments[modelDocument] = ExtensionDocumentData(
                    basename=modelDocument.basename,
                    hrefXlinkRole=hrefXlinkRole,
                    linkbases=self.getLinkbaseData(modelDocument),
                )
            if modelDocument.type == ModelDocumentType.SCHEMA:
                for doc, docRef in modelDocument.referencesDocument.items():
                    if "import" in docRef.referenceTypes:
                        extensionImportedUrls.add(doc.uri)
        return ExtensionData(
            extensionConcepts=self.getExtensionConcepts(modelXbrl),
            extensionDocuments=extensionDocuments,
            extensionImportedUrls=frozenset(sorted(extensionImportedUrls)),
        )

    def getLinkbaseData(self, modelDocument: ModelDocument) -> list[LinkbaseData]:
        linkbases = []
        for linkbaseType in LinkbaseType:
            for linkElt in modelDocument.xmlRootElement.iterdescendants(tag=linkbaseType.getLinkQn().clarkNotation):
                arcQn = linkbaseType.getArcQn()
                arcs = list(linkElt.iterdescendants(tag=arcQn.clarkNotation))
                prohibitingLabelElements = []
                prohibitedBaseConcepts = []
                if linkbaseType in (LinkbaseType.LABEL, LinkbaseType.REFERENCE):
                    prohibitedArcFroms = defaultdict(list)
                    prohibitedArcTos = defaultdict(list)
                    for arcElt in linkElt.iterchildren(
                            LinkbaseType.LABEL.getArcQn().clarkNotation,
                            LinkbaseType.REFERENCE.getArcQn().clarkNotation,
                    ):
                        if arcElt.get("use") == "prohibited":
                            prohibitedArcFroms[arcElt.get(XbrlConst.qnXlinkFrom.clarkNotation)].append(arcElt)
                            prohibitedArcTos[arcElt.get(XbrlConst.qnXlinkTo.clarkNotation)].append(arcElt)
                    for locElt in linkElt.iterchildren(XbrlConst.qnLinkLoc.clarkNotation):
                        if self.isExtensionUri(locElt.get(XbrlConst.qnXlinkHref.clarkNotation), modelDocument.modelXbrl):
                            continue
                        prohibitingArcs = prohibitedArcTos.get(locElt.get(XbrlConst.qnXlinkLabel.clarkNotation))
                        if prohibitingArcs:
                            prohibitingLabelElements.extend(prohibitingArcs)
                        prohibitingArcs = prohibitedArcFroms.get(locElt.get(XbrlConst.qnXlinkLabel.clarkNotation))
                        if prohibitingArcs:
                            prohibitingLabelElements.extend(prohibitingArcs)
                            prohibitedBaseConcepts.append(locElt.dereference())

                linkbases.append(LinkbaseData(
                    arcs=arcs,
                    basename=modelDocument.basename,
                    element=linkElt,
                    linkbaseType=linkbaseType,
                    prohibitedBaseConcepts=prohibitedBaseConcepts,
                    prohibitingLabelElements=prohibitingLabelElements,
                ))
        return linkbases

    def getNoMatchLangFootnotes(self, modelXbrl: ModelXbrl) -> set[ModelInlineFootnote]:
        return self.checkInlineHTMLElements(modelXbrl).noMatchLangFootnotes

    def getOrphanedFootnotes(self, modelXbrl: ModelXbrl) -> set[ModelInlineFootnote]:
        return self.checkInlineHTMLElements(modelXbrl).orphanedFootnotes

    def getCssHiddenFacts(self, modelXbrl: ModelXbrl) -> set[ModelInlineFact]:
        return self.checkHiddenElements(modelXbrl).cssHiddenFacts

    def getRequiredToDisplayFacts(self, modelXbrl: ModelXbrl) -> set[ModelInlineFact]:
        return self.checkHiddenElements(modelXbrl).requiredToDisplayFacts

    def getTupleElements(self, modelXbrl: ModelXbrl) -> set[tuple[Any]]:
        return self.checkInlineHTMLElements(modelXbrl).tupleElements

    @lru_cache(1)
    def getReportingPeriod(self, modelXbrl: ModelXbrl) -> str | None:
        reportingPeriodFacts = modelXbrl.factsByQname.get(self.financialReportingPeriodQn, set())
        for fact in reportingPeriodFacts:
            if fact.xValid >= VALID:
                return cast(str, fact.xValue)
        return None

    @lru_cache(1)
    def getReportXmlLang(self, modelXbrl: ModelXbrl) -> str | None:
        reportXmlLang = None
        firstRootmostXmlLangDepth = 9999999
        if modelXbrl.ixdsHtmlElements:
            ixdsHtmlRootElt = modelXbrl.ixdsHtmlElements[0]
            for elt, depth in etreeIterWithDepth(ixdsHtmlRootElt):
                if isinstance(elt, (_Comment, _ElementTree, _Entity, _ProcessingInstruction)):
                    continue
                if not reportXmlLang or depth < firstRootmostXmlLangDepth:
                    if xmlLang := elt.get("{http://www.w3.org/XML/1998/namespace}lang"):
                        reportXmlLang = xmlLang
                        firstRootmostXmlLangDepth = depth
        return reportXmlLang

    @lru_cache(1)
    def getTargetElements(self, modelXbrl: ModelXbrl) -> list[Any]:
        targetElements = []
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
            ixNStag = str(getattr(ixdsHtmlRootElt.modelDocument, "ixNStag", ixbrl11))
            ixTags = set(ixNStag + ln for ln in ("nonNumeric", "nonFraction", "references", "relationship"))
            for elt, depth in etreeIterWithDepth(ixdsHtmlRootElt):
                if elt.tag in ixTags and elt.get("target"):
                    targetElements.append(elt)
        return targetElements

    def isExtensionUri(self, uri: str, modelXbrl: ModelXbrl) -> bool:
        if uri.startswith(modelXbrl.uriDir):
            return True
        if not any(uri.startswith(taxonomyUri) for taxonomyUri in STANDARD_TAXONOMY_URLS):
            return True
        return False

    @lru_cache(1)
    def isFilenameValidCharacters(self, filename: str) -> bool:
        match = self.getFilenameAllowedCharactersPattern().match(filename)
        return match is not None

    @lru_cache(1)
    def unitsByDocument(self, modelXbrl: ModelXbrl) -> dict[str, list[ModelUnit]]:
        unitsByDocument = defaultdict(list)
        for unit in modelXbrl.units.values():
            unitsByDocument[unit.modelDocument.filepath].append(unit)
        unitsByDocument.default_factory = None
        return unitsByDocument
