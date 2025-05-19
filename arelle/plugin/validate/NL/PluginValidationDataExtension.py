"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, cast

import regex as re
from lxml.etree import _Comment, _ElementTree, _Entity, _ProcessingInstruction

from arelle.FunctionIxt import ixtNamespaces
from arelle.ModelInstanceObject import ModelContext, ModelFact, ModelInlineFootnote, ModelUnit
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.PluginData import PluginData
from arelle.utils.validate.ValidationUtil import etreeIterWithDepth
from arelle.XmlValidate import lexicalPatterns

XBRLI_IDENTIFIER_PATTERN = re.compile(r"^(?!00)\d{8}$")
XBRLI_IDENTIFIER_SCHEMA = 'http://www.kvk.nl/kvk-id'

DISALLOWED_IXT_NAMESPACES = frozenset((
    ixtNamespaces["ixt v1"],
    ixtNamespaces["ixt v2"],
    ixtNamespaces["ixt v3"],
))

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
class FootnoteData:
    noMatchLangFootnotes: set[ModelInlineFootnote]
    orphanedFootnotes: set[ModelInlineFootnote]
    factLangFootnotes: dict[ModelInlineFootnote, set[str]]

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
    def checkFootnotes(self, modelXbrl: ModelXbrl) -> FootnoteData:
        factLangs = self.factLangs(modelXbrl)
        footnotesRelationshipSet = modelXbrl.relationshipSet("XBRL-footnotes")
        orphanedFootnotes = set()
        noMatchLangFootnotes = set()
        factLangFootnotes = defaultdict(set)
        for elts in modelXbrl.ixdsEltById.values():   # type: ignore[attr-defined]
            for elt in elts:
                if isinstance(elt, ModelInlineFootnote):
                    if elt.textValue is not None:
                        if not any(isinstance(rel.fromModelObject, ModelFact)
                                   for rel in footnotesRelationshipSet.toModelObject(elt)):
                            orphanedFootnotes.add(elt)
                        if elt.xmlLang not in factLangs:
                            noMatchLangFootnotes.add(elt)
                        for rel in footnotesRelationshipSet.toModelObject(elt):
                            if rel.fromModelObject is not None:
                                factLangFootnotes[rel.fromModelObject].add(elt.xmlLang)
        factLangFootnotes.default_factory = None
        return FootnoteData(
            noMatchLangFootnotes=noMatchLangFootnotes,
            orphanedFootnotes=orphanedFootnotes,
            factLangFootnotes=dict(factLangFootnotes),
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

    def getContextsWithImproperContent(self, modelXbrl: ModelXbrl) -> list[ModelContext | None]:
        return self.checkContexts(modelXbrl).contextsWithImproperContent

    def getContextsWithPeriodTime(self, modelXbrl: ModelXbrl) -> list[ModelContext | None]:
        return self.checkContexts(modelXbrl).contextsWithPeriodTime

    def getContextsWithPeriodTimeZone(self, modelXbrl: ModelXbrl) -> list[ModelContext | None]:
        return self.checkContexts(modelXbrl).contextsWithPeriodTimeZone

    def getContextsWithSegments(self, modelXbrl: ModelXbrl) -> list[ModelContext | None]:
        return self.checkContexts(modelXbrl).contextsWithSegments

    def getNoMatchLangFootnotes(self, modelXbrl: ModelXbrl) -> set[ModelInlineFootnote]:
        return self.checkFootnotes(modelXbrl).noMatchLangFootnotes

    def getOrphanedFootnotes(self, modelXbrl: ModelXbrl) -> set[ModelInlineFootnote]:
        return self.checkFootnotes(modelXbrl).orphanedFootnotes

    def getFactLangFootnotes(self, modelXbrl: ModelXbrl) -> dict[ModelInlineFootnote, set[str]]:
        return self.checkFootnotes(modelXbrl).factLangFootnotes

    @lru_cache(1)
    def getReportXmlLang(self, modelXbrl: ModelXbrl) -> str | None:
        firstIxdsDoc = True
        reportXmlLang = None
        firstRootmostXmlLangDepth = 9999999
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
            for uncast_elt, depth in etreeIterWithDepth(ixdsHtmlRootElt):
                elt = cast(Any, uncast_elt)
                if isinstance(elt, (_Comment, _ElementTree, _Entity, _ProcessingInstruction)):
                    continue
                if firstIxdsDoc and (not reportXmlLang or depth < firstRootmostXmlLangDepth):
                    xmlLang = elt.get("{http://www.w3.org/XML/1998/namespace}lang")
                    if xmlLang:
                        reportXmlLang = xmlLang
                        firstRootmostXmlLangDepth = depth
            firstIxdsDoc = False
        return reportXmlLang

    @lru_cache(1)
    def unitsByDocument(self, modelXbrl: ModelXbrl) -> dict[str, list[ModelUnit]]:
        unitsByDocument = defaultdict(list)
        for unit in modelXbrl.units.values():
            unitsByDocument[unit.modelDocument.filepath].append(unit)
        unitsByDocument.default_factory = None
        return unitsByDocument
