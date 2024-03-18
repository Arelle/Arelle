"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from arelle.ModelInstanceObject import ModelUnit, ModelContext, ModelFact
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.validate.PluginValidationData import PluginValidationData


@dataclass
class PluginValidationDataExtension(PluginValidationData):
    financialReportingPeriodCurrentStartDateQn: QName
    financialReportingPeriodCurrentEndDateQn: QName
    financialReportingPeriodPreviousStartDateQn: QName
    financialReportingPeriodPreviousEndDateQn: QName
    formattedExplanationItemTypeQn: QName
    documentAdoptionDateQn: QName
    documentAdoptionStatusQn: QName
    documentResubmissionUnsurmountableInaccuraciesQn: QName
    entrypointRoot: str
    entrypoints: set[str]
    textFormattingSchemaPath: str
    textFormattingWrapper: str

    _contextsByDocument: dict[str, list[ModelContext]] | None = None
    _factsByDocument: dict[str, list[ModelFact]] | None = None
    _unitsByDocument: dict[str, list[ModelUnit]] | None = None

    def contextsByDocument(self, modelXbrl: ModelXbrl) -> dict[str, list[ModelContext]]:
        if self._contextsByDocument is not None:
            return self._contextsByDocument
        contextsByDocument = defaultdict(list)
        for context in modelXbrl.contexts.values():
            contextsByDocument[context.modelDocument.filepath].append(context)
        self._contextsByDocument = dict(contextsByDocument)
        return self._contextsByDocument

    def factsByDocument(self, modelXbrl: ModelXbrl) -> dict[str, list[ModelFact]]:
        if self._factsByDocument is not None:
            return self._factsByDocument
        factsByDocument = defaultdict(list)
        for fact in modelXbrl.facts:
            factsByDocument[fact.modelDocument.filepath].append(fact)
        self._factsByDocument = dict(factsByDocument)
        return self._factsByDocument

    def unitsByDocument(self, modelXbrl: ModelXbrl) -> dict[str, list[ModelUnit]]:
        if self._unitsByDocument is not None:
            return self._unitsByDocument
        unitsByDocument = defaultdict(list)
        for unit in modelXbrl.units.values():
            unitsByDocument[unit.modelDocument.filepath].append(unit)
        self._unitsByDocument = dict(unitsByDocument)
        return self._unitsByDocument
