"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import cast, Any

import regex as re
from collections import defaultdict
from dataclasses import dataclass

from arelle.FunctionIxt import ixtNamespaces
from arelle.ModelInstanceObject import ModelUnit, ModelContext, ModelFact, ModelInlineFootnote
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.PluginData import PluginData
from arelle.XmlValidate import lexicalPatterns

XBRLI_IDENTIFIER_PATTERN = re.compile(r"^(?!00)\d{8}$")
XBRLI_IDENTIFIER_SCHEMA = 'http://www.kvk.nl/kvk-id'

DISALLOWED_IXT_NAMESPACES = frozenset((
    ixtNamespaces["ixt v1"],
    ixtNamespaces["ixt v2"],
    ixtNamespaces["ixt v3"],
))

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

    _contextsByDocument: dict[str, list[ModelContext]] | None = None
    _contextsWithImproperContent: list[ModelContext | None] | None = None
    _contextsWithPeriodTime: list[ModelContext | None] | None = None
    _contextsWithPeriodTimeZone: list[ModelContext | None] | None = None
    _contextsWithSegments: list[ModelContext | None] | None = None
    _entityIdentifiers: set[tuple[str, str]] | None = None
    _factsByDocument: dict[str, list[ModelFact]] | None = None
    _factLangs: set[str] | None = None
    _noMatchLangFootnotes: set[ModelInlineFootnote] | None = None
    _orphanedFootnotes: set[ModelInlineFootnote] | None = None
    _unitsByDocument: dict[str, list[ModelUnit]] | None = None

    def contextsByDocument(self, modelXbrl: ModelXbrl) -> dict[str, list[ModelContext]]:
        if self._contextsByDocument is not None:
            return self._contextsByDocument
        contextsByDocument = defaultdict(list)
        for context in modelXbrl.contexts.values():
            contextsByDocument[context.modelDocument.filepath].append(context)
        self._contextsByDocument = dict(contextsByDocument)
        return self._contextsByDocument

    def checkContexts(self, allContexts: dict[str, list[ModelContext]]) -> None:
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
        self._contextsWithImproperContent = contextsWithImproperContent
        self._contextsWithPeriodTime = contextsWithPeriodTime
        self._contextsWithPeriodTimeZone = contextsWithPeriodTimeZone
        self._contextsWithSegments = contextsWithSegments

    def checkFootnote(self, modelXbrl: ModelXbrl) -> None:
        factLangs = self.factLangs(modelXbrl)
        footnotesRelationshipSet = modelXbrl.relationshipSet("XBRL-footnotes")
        orphanedFootnotes = set()
        noMatchLangFootnotes = set()
        for elts in modelXbrl.ixdsEltById.values():   # type: ignore[attr-defined]
            for elt in elts:
                if isinstance(elt, ModelInlineFootnote):
                    if elt.textValue is not None:
                        if not any(isinstance(rel.fromModelObject, ModelFact)
                                   for rel in footnotesRelationshipSet.toModelObject(elt)):
                            orphanedFootnotes.add(elt)
                        if not elt.xmlLang in factLangs:
                            noMatchLangFootnotes.add(elt)
        self._noMatchLangFootnotes = noMatchLangFootnotes
        self._orphanedFootnotes = orphanedFootnotes

    def entityIdentifiersInDocument(self, modelXbrl: ModelXbrl) -> set[tuple[str, str]]:
        if self._entityIdentifiers is not None:
            return self._entityIdentifiers
        self._entityIdentifiers = {context.entityIdentifier for context in modelXbrl.contexts.values()}
        return self._entityIdentifiers

    def factsByDocument(self, modelXbrl: ModelXbrl) -> dict[str, list[ModelFact]]:
        if self._factsByDocument is not None:
            return self._factsByDocument
        factsByDocument = defaultdict(list)
        for fact in modelXbrl.facts:
            factsByDocument[fact.modelDocument.filepath].append(fact)
        self._factsByDocument = dict(factsByDocument)
        return self._factsByDocument

    def factLangs(self, modelXbrl: ModelXbrl) -> set[str]:
        if self._factLangs is not None:
                return self._factLangs
        factLangs = set()
        for fact in modelXbrl.facts:
            if fact is not None:
                factLangs.add(fact.xmlLang)
        self._factLangs = factLangs
        return self._factLangs

    def getContextsWithImproperContent(self, modelXbrl: ModelXbrl) -> list[ModelContext | None]:
        if self._contextsWithImproperContent is None:
            self.checkContexts(self.contextsByDocument(modelXbrl))
        assert(self._contextsWithImproperContent is not None)
        return self._contextsWithImproperContent

    def getContextsWithPeriodTime(self, modelXbrl: ModelXbrl) -> list[ModelContext | None]:
        if self._contextsWithPeriodTime is None:
            self.checkContexts(self.contextsByDocument(modelXbrl))
        assert(self._contextsWithPeriodTime is not None)
        return self._contextsWithPeriodTime

    def getContextsWithPeriodTimeZone(self, modelXbrl: ModelXbrl) -> list[ModelContext | None]:
        if self._contextsWithPeriodTimeZone is None:
            self.checkContexts(self.contextsByDocument(modelXbrl))
        assert (self._contextsWithPeriodTimeZone is not None)
        return self._contextsWithPeriodTimeZone

    def getContextsWithSegments(self, modelXbrl: ModelXbrl) -> list[ModelContext | None]:
        if self._contextsWithSegments is None:
            self.checkContexts(self.contextsByDocument(modelXbrl))
        assert(self._contextsWithSegments is not None)
        return self._contextsWithSegments

    def getNoMatchLangFootnotes(self, modelXbrl: ModelXbrl) -> set[ModelInlineFootnote]:
        if self._noMatchLangFootnotes is None:
            self.checkFootnote(modelXbrl)
        assert(self._noMatchLangFootnotes is not None)
        return self._noMatchLangFootnotes

    def getOrphanedFootnotes(self, modelXbrl: ModelXbrl) -> set[ModelInlineFootnote]:
        if self._orphanedFootnotes is None:
            self.checkFootnote(modelXbrl)
        assert(self._orphanedFootnotes is not None)
        return self._orphanedFootnotes

    def unitsByDocument(self, modelXbrl: ModelXbrl) -> dict[str, list[ModelUnit]]:
        if self._unitsByDocument is not None:
            return self._unitsByDocument
        unitsByDocument = defaultdict(list)
        for unit in modelXbrl.units.values():
            unitsByDocument[unit.modelDocument.filepath].append(unit)
        self._unitsByDocument = dict(unitsByDocument)
        return self._unitsByDocument
