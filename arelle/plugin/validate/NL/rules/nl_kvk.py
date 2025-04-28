"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from datetime import date, timedelta

from arelle.XmlValidateConst import VALID
from dateutil import relativedelta
from collections.abc import Iterable
from typing import Any, cast, TYPE_CHECKING

from regex import regex

from arelle import XmlUtil, XbrlConst
from arelle.ModelObject import ModelObject
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XmlValidate import INVALID
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (
    DISCLOSURE_SYSTEM_INLINE_NT19
)
from ..PluginValidationDataExtension import PluginValidationDataExtension, XBRLI_IDENTIFIER_PATTERN, XBRLI_IDENTIFIER_SCHEMA

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelValue import QName

_: TypeGetText


def _getReportingPeriodDateValue(modelXbrl: ModelXbrl, qname: QName) -> date | None:
    facts = modelXbrl.factsByQname.get(qname)
    if facts and len(facts) == 1:
        datetimeValue = XmlUtil.datetimeValue(next(iter(facts)))
        if datetimeValue:
            return datetimeValue.date()
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_INLINE_NT19
    ],
)
def rule_nl_kvk_3_1_1_1(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.1.1.1: xbrli:identifier content to match KVK number format that must consist of 8 consecutive digits;
    first two digits must not be '00'.
    """
    entityIdentifierValues = pluginData.entityIdentifiersInDocument(val.modelXbrl)
    for entityId in entityIdentifierValues:
        if not XBRLI_IDENTIFIER_PATTERN.match(entityId[1]):
            yield Validation.error(
                codes='NL.NL-KVK-3.1.1.1',
                msg=_('xbrli:identifier content to match KVK number format that must consist of 8 consecutive digits.'
                      'Additionally the first two digits must not be "00".'),
                modelObject = val.modelXbrl
            )
            return


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_INLINE_NT19
    ],
)
def rule_nl_kvk_3_1_1_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.1.1.2: Scheme attribute of xbrli:identifier must be http://www.kvk.nl/kvk-id.
    """
    entityIdentifierValues = pluginData.entityIdentifiersInDocument(val.modelXbrl)
    for entityId in entityIdentifierValues:
        if XBRLI_IDENTIFIER_SCHEMA != entityId[0]:
            yield Validation.error(
                codes='NL.NL-KVK-3.1.1.2',
                msg=_('The scheme attribute of the xbrli:identifier does not match the required content.'
                      'This should be "http://www.kvk.nl/kvk-id".'),
                modelObject = val.modelXbrl
            )
            return


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_INLINE_NT19
    ],
)
def rule_nl_kvk_3_1_2_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.1.2.1: xbrli:startDate, xbrli:endDate, xbrli:instant formatted as yyyy-mm-dd without time.
    """
    contextsWithPeriodTime = pluginData.getContextsWithPeriodTime(val.modelXbrl)
    if len(contextsWithPeriodTime) !=0:
        yield Validation.error(
            codes='NL.NL-KVK-3.1.2.1',
            msg=_('xbrli:startDate, xbrli:endDate, xbrli:instant must be formatted as yyyy-mm-dd without time'),
            modelObject = contextsWithPeriodTime
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_INLINE_NT19
    ],
)
def rule_nl_kvk_3_1_2_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.1.2.1: xbrli:startDate, xbrli:endDate, xbrli:instant format to be formatted as yyyy-mm-dd without time zone.
    """
    contextsWithPeriodTimeZone = pluginData.getContextsWithPeriodTimeZone(val.modelXbrl)
    if len(contextsWithPeriodTimeZone) !=0:
            yield Validation.error(
                codes='NL.NL-KVK-3.1.2.2',
                msg=_('xbrli:startDate, xbrli:endDate, xbrli:instant must be formatted as yyyy-mm-dd without time zone'),
                modelObject = contextsWithPeriodTimeZone
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_INLINE_NT19
    ],
)
def rule_nl_kvk_3_1_3_1 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.1.3.1: xbrli:segment must not be used in contexts.
    """
    contextsWithSegments = pluginData.getContextsWithSegments(val.modelXbrl)
    if len(contextsWithSegments) !=0:
        yield Validation.error(
            codes='NL.NL-KVK-3.1.3.1',
            msg=_('xbrli:segment must not be used in contexts.'),
            modelObject = contextsWithSegments
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_INLINE_NT19
    ],
)
def rule_nl_kvk_3_1_3_2 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.1.3.2: xbrli:scenario must only contain content defined in XBRL Dimensions specification.
    """
    contextsWithImproperContent = pluginData.getContextsWithImproperContent(val.modelXbrl)
    if len(contextsWithImproperContent) !=0:
        yield Validation.error(
            codes='NL.NL-KVK-3.1.3.2',
            msg=_('xbrli:scenario must only contain content defined in XBRL Dimensions specification.'),
            modelObject = contextsWithImproperContent
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_INLINE_NT19
    ],
)
def rule_nl_kvk_3_1_4_1 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
     NL-KVK.3.1.4.1: All entity identifiers and schemes must have identical content.
    """
    entityIdentifierValues = pluginData.entityIdentifiersInDocument(val.modelXbrl)
    if len(entityIdentifierValues) >1:
        yield Validation.error(
            codes='NL.NL-KVK-3.1.4.1',
            msg=_('All entity identifiers and schemes must have identical content.'),
            modelObject = entityIdentifierValues
        )



@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_INLINE_NT19
    ],
)
def rule_nl_kvk_3_1_4_2 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.1.4.2: xbrli:identifier value must be identical to bw2-titel9:ChamberOfCommerceRegistrationNumber fact value.
    """
    registrationNumberFacts = val.modelXbrl.factsByQname.get(pluginData.chamberOfCommerceRegistrationNumberQn, set())
    if len(registrationNumberFacts) > 0:
        regFact = next(iter(registrationNumberFacts))
        if regFact.xValid >= VALID and regFact.xValue != regFact.context.entityIdentifier[1]:
            yield Validation.error(
                codes='NL-KVK.3.1.4.2',
                msg=_("xbrli:identifier value must be identical to bw2-titel9:ChamberOfCommerceRegistrationNumber fact value.").format(
                    regFact.xValue,
                    regFact.context.entityIdentifier[1]
                ),
                modelObject=regFact
            )
