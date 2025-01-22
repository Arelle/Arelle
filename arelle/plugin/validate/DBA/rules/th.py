"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.typing import TypeGetText
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.XmlValidateConst import VALID
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_th05 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TH05: Contexts should not contain segments or unclosed periods
    """
    contexts = val.modelXbrl.contexts.values()
    for context in contexts:
        if context.hasSegment:
            yield Validation.error(
                'DBA.TH05',
                _('Contexts should not contain segments.'),
                modelObject=context,
            )

@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_th06 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TH06: CVR (gsd:IdentificationNumberCvrOfReportingEntity) context period cannot be forever.
    """
    facts = val.modelXbrl.factsByQname.get(pluginData.identificationNumberCvrOfReportingEntityQn, set())
    for fact in facts:
        if fact is not None and fact.context is not None:
            if fact.context.isForeverPeriod:
                yield Validation.error(
                    'DBA.TH06',
                    _('The CVR (gsd:IdentificationNumberCvrOfReportingEntity) context period cannot be forever.'),
                    modelObject=fact,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_th14 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TH14: gsd:InformationOnTypeOfSubmittedReport MUST NOT use the following enumerations:
        Selskabsselvangivelse
        Erklæring om undtagelse fra aflæggelse årsrapport
        ESG-rapport
        ESG report
    """
    facts = val.modelXbrl.factsByQname.get(pluginData.informationOnTypeOfSubmittedReportQn, set())
    for fact in facts:
        if fact is not None and fact.xValid >= VALID:
            if fact.xValue in pluginData.forbiddenTypeOfSubmittedReportEnumerations:
                yield Validation.error(
                    'DBA.TH14',
                    _('gsd:InformationOnTypeOfSubmittedReport MUST NOT use the following enumerations:'
                      '"Selskabsselvangivelse", "Erklæring om undtagelse fra aflæggelse årsrapport", "ESG-rapport", "ESG report"'
                      'InformationOnTypeOfSubmittedReport is reported as "{}".').format(
                    fact.xValue),
                    modelObject=fact,

                )
