"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any, Iterable, cast

from arelle.ValidateXbrl import ValidateXbrl
from arelle.XmlValidate import VALID
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import DISCLOSURE_SYSTEM_2022, DISCLOSURE_SYSTEM_2023
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


# rule 01.01 (2022)
@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=DISCLOSURE_SYSTEM_2022,
)
def rule01_01_2022(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation] | None:
    if "Cash" not in val.modelXbrl.factsByLocalName:
        yield Validation.error(
            codes="XYZ.01.01",
            msg=_("Cash must be reported."),
            modelObject=val.modelXbrl,
        )


# rule 01.01 (2023)
@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=DISCLOSURE_SYSTEM_2023,
)
def rule01_01_2023(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation] | None:
    conceptLocalNamesWithPositiveFactValues = pretendExpensiveOperation(pluginData, val)
    if "Cash" not in conceptLocalNamesWithPositiveFactValues:
        yield Validation.warning(
            codes="XYZ.01.01",
            msg=_("Cash should be reported."),
            modelObject=val.modelXbrl,
        )


@validation(hook=ValidationHook.FINALLY)
def rule01_02(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation] | None:
    numXbrlErrors = len(val.modelXbrl.errors)
    if numXbrlErrors > 0:
        yield Validation.error(
            codes="XYZ.01.02",
            msg=_("Invalid report %(numXbrlErrors)s errors detected."),
            modelObject=val.modelXbrl,
            numXbrlErrors=numXbrlErrors,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=DISCLOSURE_SYSTEM_2023,
)
def rule01_03(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation] | None:
    conceptLocalNamesWithPositiveFactValues = pretendExpensiveOperation(pluginData, val)
    if "UnitsSold" not in conceptLocalNamesWithPositiveFactValues:
        yield Validation.error(
            codes="XYZ.01.03",
            msg=_("UnitsSold must be reported."),
            modelObject=val.modelXbrl,
        )


def pretendExpensiveOperation(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
) -> set[str]:
    positiveFactConcepts = pluginData.positiveFactConcepts
    if positiveFactConcepts is None:
        positiveFactConcepts = {
            fact.concept.name
            for fact in val.modelXbrl.facts
            if fact.isNumeric
            and getattr(fact, "xValid", 0) >= VALID
            and cast(int, fact.xValue) > 0
        }
        pluginData.positiveFactConcepts = positiveFactConcepts
    return positiveFactConcepts
