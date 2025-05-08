"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from datetime import date, timedelta

from arelle.ModelInstanceObject import ModelInlineFact
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
from ..DisclosureSystems import DISCLOSURE_SYSTEM_NL_INLINE_2024
from ..PluginValidationDataExtension import PluginValidationDataExtension, XBRLI_IDENTIFIER_PATTERN, XBRLI_IDENTIFIER_SCHEMA, DISALLOWED_IXT_NAMESPACES

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
        DISCLOSURE_SYSTEM_NL_INLINE_2024
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
        DISCLOSURE_SYSTEM_NL_INLINE_2024
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
        DISCLOSURE_SYSTEM_NL_INLINE_2024
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
            codes='NL.NL-KVK-3.1.2.1.periodWithTimeContent',
            msg=_('xbrli:startDate, xbrli:endDate, xbrli:instant must be formatted as yyyy-mm-dd without time'),
            modelObject = contextsWithPeriodTime
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
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
                codes='NL.NL-KVK-3.1.2.2.periodWithTimeZone',
                msg=_('xbrli:startDate, xbrli:endDate, xbrli:instant must be formatted as yyyy-mm-dd without time zone'),
                modelObject = contextsWithPeriodTimeZone
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
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
            codes='NL.NL-KVK-3.1.3.1.segmentUsed',
            msg=_('xbrli:segment must not be used in contexts.'),
            modelObject = contextsWithSegments
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
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
            codes='NL.NL-KVK-3.1.3.2.scenarioContainsNotAllowedContent',
            msg=_('xbrli:scenario must only contain content defined in XBRL Dimensions specification.'),
            modelObject = contextsWithImproperContent
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
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
        DISCLOSURE_SYSTEM_NL_INLINE_2024
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


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_2_1_1 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.2.1.1: precision should not be used on numeric facts.
    """
    factsWithPrecision = []
    for fact in val.modelXbrl.facts:
        if fact is not None and fact.isNumeric and fact.precision:
            factsWithPrecision.append(fact)
    if len(factsWithPrecision) >0:
        yield Validation.error(
            codes='NL.NL-KVK-3.2.1.1.precisionAttributeUsed',
            msg=_('Precision should not be used on numeric facts.'),
            modelObject = factsWithPrecision
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_2_3_1 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.2.3.1: Transformation Registry 4 or newer are allowed. Everything else is prohibited.
    """
    transformRegistryErrors = []
    for fact in val.modelXbrl.facts:
        if isinstance(fact, ModelInlineFact):
            if fact.format is not None and fact.format.namespaceURI in DISALLOWED_IXT_NAMESPACES:
                transformRegistryErrors.append(fact)
    if len(transformRegistryErrors) >0:
        yield Validation.error(
            codes='NL.NL-KVK.3.2.3.1.incorrectTransformationRuleApplied',
            msg=_('Transformation Registry 4 or newer are allowed. Everything else is prohibited.'),
            modelObject = transformRegistryErrors
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_3_1_1 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.3.1.1: Ensure that every nonempty <link:footnote> element is associated with at least one fact in the XBRL document.
    """
    orphanedFootnotes = pluginData.getOrphanedFootnotes(val.modelXbrl)
    if len(orphanedFootnotes) >0:
        yield Validation.error(
            codes='NL.NL-KVK.3.3.1.1.unusedFootnote',
            msg=_('Ensure that every nonempty <link:footnote> element is associated with at least one fact in the XBRL document.'),
            modelObject = orphanedFootnotes
        )

@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_3_1_2 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.3.1.2: The xml:lang attribute of each footnote matches the language of at least one textual fact.
    """
    noMatchLangFootnotes = pluginData.getNoMatchLangFootnotes(val.modelXbrl)
    if len(noMatchLangFootnotes) >0:
        yield Validation.error(
            codes='NL.NL-KVK.3.3.1.2.footnoteInLanguagesOtherThanLanguageOfContentOfAnyTextualFact',
            msg=_('The xml:lang attribute of each footnote matches the language of at least one textual fact.'),
            modelObject = noMatchLangFootnotes
        )
