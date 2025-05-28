"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, TYPE_CHECKING, cast

import regex as re
from lxml.etree import _Comment, _ElementTree, _Entity, _ProcessingInstruction

from arelle.FunctionIxt import ixtNamespaces
from arelle.ModelInstanceObject import ModelContext, ModelFact, ModelInlineFootnote, ModelUnit, ModelInlineFact
from arelle.ModelObject import ModelObject
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.typing import assert_type
from arelle.utils.PluginData import PluginData
from arelle.utils.validate.ValidationUtil import etreeIterWithDepth
from arelle.XbrlConst import ixbrl11, xhtmlBaseIdentifier, xmlBaseIdentifier
from arelle.XmlValidate import lexicalPatterns
from arelle.XmlValidateConst import VALID

XBRLI_IDENTIFIER_PATTERN = re.compile(r"^(?!00)\d{8}$")
XBRLI_IDENTIFIER_SCHEMA = 'http://www.kvk.nl/kvk-id'


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

@dataclass(frozen=True)
class ContextData:
    contextsWithImproperContent: list[ModelContext | None]
    contextsWithPeriodTime: list[ModelContext | None]
    contextsWithPeriodTimeZone: list[ModelContext | None]
    contextsWithSegments: list[ModelContext | None]

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

@dataclass
class PluginValidationDataExtension(PluginData):
    chamberOfCommerceRegistrationNumberQn: QName
    documentAdoptionDateQn: QName
    documentAdoptionStatusQn: QName
    documentResubmissionUnsurmountableInaccuraciesQn: QName
    entrypointRoot: str
    entrypoints: set[str]
    financialReportingPeriodCurrentStartDateQn: QName
    financialReportingPeriodCurrentEndDateQn: QName
    financialReportingPeriodPreviousStartDateQn: QName
    financialReportingPeriodPreviousEndDateQn: QName
    formattedExplanationItemTypeQn: QName
    textFormattingSchemaPath: str
    textFormattingWrapper: str

    # Identity hash for caching.
    def __hash__(self) -> int:
        return id(self)

    @lru_cache(1)
    def contextsByDocument(self, modelXbrl: ModelXbrl) -> dict[str, list[ModelContext]]:
        contextsByDocument = defaultdict(list)
        for context in modelXbrl.contexts.values():
            contextsByDocument[context.modelDocument.filepath].append(context)
        contextsByDocument.default_factory = None
        return contextsByDocument

    @lru_cache(1)
    def checkContexts(self, modelXbrl: ModelXbrl) -> ContextData:
        allContexts = self.contextsByDocument(modelXbrl)
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
                if context.nonDimValues("scenario"):  # type: ignore[no-untyped-call]
                    contextsWithImproperContent.append(context)
        return ContextData(
            contextsWithImproperContent=contextsWithImproperContent,
            contextsWithPeriodTime=contextsWithPeriodTime,
            contextsWithPeriodTimeZone=contextsWithPeriodTimeZone,
            contextsWithSegments=contextsWithSegments,
        )

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
            ixNStag = getattr(ixdsHtmlRootElt.modelDocument, "ixNStag", ixbrl11)
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
            ixNStag = getattr(ixdsHtmlRootElt.modelDocument, "ixNStag", ixbrl11)
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
    def entityIdentifiersInDocument(self, modelXbrl: ModelXbrl) -> set[tuple[str, str]]:
        return {context.entityIdentifier for context in modelXbrl.contexts.values()}

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
    def getFilenameParts(self, filename: str) -> dict[str, Any] | None:
        match = self.getFilenameFormatPattern().match(filename)
        if match:
            return match.groupdict()
        return None

    @lru_cache(1)
    def getIxdsDocBasenames(self, modelXbrl: ModelXbrl) -> set[str]:
        return set(Path(url).name for url in modelXbrl.ixdsDocUrls)

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
