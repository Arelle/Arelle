"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from datetime import date
import zipfile

from arelle.ModelInstanceObject import ModelInlineFact
from arelle.ValidateDuplicateFacts import getDuplicateFactSets
from arelle.XmlValidateConst import VALID
from collections.abc import Iterable
from typing import Any, cast, TYPE_CHECKING

from arelle import XmlUtil
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateDuplicateFacts import getHashEquivalentFactGroups, getAspectEqualFacts
from arelle.utils.validate.ValidationUtil import etreeIterWithDepth
from ..DisclosureSystems import DISCLOSURE_SYSTEM_NL_INLINE_2024
from ..LinkbaseType import LinkbaseType
from ..PluginValidationDataExtension import (PluginValidationDataExtension, ALLOWABLE_LANGUAGES,
                                             DISALLOWED_IXT_NAMESPACES, EFFECTIVE_KVK_GAAP_IFRS_ENTRYPOINT_FILES,
                                             MAX_REPORT_PACKAGE_SIZE_MBS, TAXONOMY_URLS_BY_YEAR,
                                             XBRLI_IDENTIFIER_PATTERN, XBRLI_IDENTIFIER_SCHEMA)

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
                codes='NL.NL-KVK-RTS_Annex_IV_Par_2_G3-1-1_1.invalidIdentifierFormat',
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
                codes='NL.NL-KVK-RTS_Annex_IV_Par_2_G3-1-1_2.invalidIdentifier',
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
            codes='NL.NL-KVK-RTS_Annex_IV_Par_1_G3-1-4_1.multipleIdentifiers',
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
                codes='NL.NL-KVK-RTS_Annex_IV_Par_1_G3-1-4_2.nonIdenticalIdentifier',
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
def rule_nl_kvk_3_2_4_1 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.2.4.1: Inconsistent numeric facts are prohibited.
    """
    problematicFacts= []
    numericFacts = [fact for fact in val.modelXbrl.facts if fact is not None and fact.isNumeric]
    if len(numericFacts) > 0:
        for duplicateFactSet in getDuplicateFactSets(numericFacts, False):
            if duplicateFactSet.areAnyInconsistent:
                for fact in duplicateFactSet:
                    problematicFacts.append(fact)
    if len(problematicFacts) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.2.4.1.inconsistentDuplicateNumericFactInInlineXbrlDocument',
            msg=_('Inconsistent numeric facts are prohibited.'),
            modelObject = problematicFacts
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_2_4_2 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.2.4.2: Inconsistent non-numeric facts are prohibited.
    """
    problematicFacts = []
    nonNumericFacts = [fact for fact in val.modelXbrl.facts if fact is not None and not fact.isNumeric]
    if len(nonNumericFacts) > 0:
        for duplicateFactSet in getDuplicateFactSets(nonNumericFacts, False):
            if duplicateFactSet.areAnyInconsistent:
                for fact in duplicateFactSet:
                    problematicFacts.append(fact)
    if len(problematicFacts) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.2.4.2.inconsistentDuplicateNonnumericFactInInlineXbrlDocument',
            msg=_('Inconsistent non-numeric facts are prohibited.'),
            modelObject = problematicFacts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_2_7_1 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.2.7.1: Ensure that any block-tagged facts of type textBlockItemType are assigned @escape="true",
    while other data types (e.g., xbrli:stringItemType) are assigned @escape="false".
    """
    improperlyEscapedFacts = []
    for fact in val.modelXbrl.facts:
        if isinstance(fact, ModelInlineFact) and  fact.concept is not None and fact.isEscaped != fact.concept.isTextBlock:
            improperlyEscapedFacts.append(fact)
    if len(improperlyEscapedFacts) >0:
        yield Validation.error(
            codes='NL.NL-KVK.3.2.7.1.improperApplicationOfEscapeAttribute',
            msg=_('Ensure that any block-tagged facts of type textBlockItemType are assigned @escape="true",'
                  'while other data types (e.g., xbrli:stringItemType) are assigned @escape="false".'),
            modelObject = improperlyEscapedFacts
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


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_3_1_3 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.3.1.3: At least one footnote in the footnote relationship is in the language of the report.
    """
    factLangFootnotes = pluginData.getFactLangFootnotes(val.modelXbrl)
    reportXmlLang = pluginData.getReportXmlLang(val.modelXbrl)
    nonDefLangFtFacts = set(f for f,langs in factLangFootnotes.items() if reportXmlLang not in langs)
    if len(nonDefLangFtFacts) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.3.1.3.footnoteOnlyInLanguagesOtherThanLanguageOfAReport',
            msg=_('At least one footnote must have the same language as the report\'s language.'),
            modelObject=nonDefLangFtFacts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_4_1_1 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.4.1.1: ix:tuple element should not be used in the Inline XBRL document.
    """
    tuples = pluginData.getTupleElements(val.modelXbrl)
    if len(tuples) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.4.1.1.tupleElementUsed',
            msg=_('ix:tuple element should not be used in the Inline XBRL document.'),
            modelObject=tuples
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_4_1_2 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.4.1.2: ix:fraction element should not be used in the Inline XBRL document.
    """
    fractions = pluginData.getFractionElements(val.modelXbrl)
    if len(fractions) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.4.1.2.fractionElementUsed',
            msg=_('ix:fraction element should not be used in the Inline XBRL document.'),
            modelObject=fractions
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_4_1_3 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.4.1.3: The ix:hidden section should not include elements that are eligible for transformation
    according to the latest recommended Transformation Rules Registry.
    """
    facts = pluginData.getEligibleForTransformHiddenFacts(val.modelXbrl)
    if len(facts) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.4.1.3.transformableElementIncludedInHiddenSection',
            msg=_('The ix:hidden section should not include elements that are eligible for transformation '
                  'according to the latest recommended Transformation Rules Registry.'),
            modelObject=facts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_4_1_4 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.4.1.4: ix:hidden section should not contain a fact whose @id attribute is not applied on any ix-hidden style.
    """
    facts = pluginData.getRequiredToDisplayFacts(val.modelXbrl)
    if len(facts) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.4.1.4.factInHiddenSectionNotInReport',
            msg=_('ix:hidden section should not contain a fact whose @id attribute is not applied on any -ix-hidden style.'),
            modelObject=facts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_4_1_5 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.4.1.5: ix:hidden section should not contain a fact whose @id attribute is not applied on any ix-hidden style.
    """
    facts = pluginData.getHiddenFactsOutsideHiddenSection(val.modelXbrl)
    if len(facts) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.4.1.5.kvkIxHiddenStyleNotLinkingFactInHiddenSection',
            msg=_('Review for -ix-hidden style identifies @id attribute of a fact that is not in ix:hidden section'),
            modelObject=facts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_4_2_1 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.4.2.1: Review if xml:base and <base> elements are present in the Inline XBRL document.
    """
    baseElements = pluginData.getBaseElements(val.modelXbrl)
    if len(baseElements) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.4.2.1.htmlOrXmlBaseUsed',
            msg=_('The HTML <base> elements and xml:base attributes MUST NOT be used in the Inline XBRL document'),
            modelObject=baseElements
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_5_2_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.5.2.1: Each tagged text fact MUST have the ‘xml:lang’ attribute assigned or inherited.
    """
    factsWithoutLang = []
    for fact in val.modelXbrl.facts:
        if (fact is not None and
                fact.concept is not None and
                fact.concept.type is not None and
                fact.concept.type.isOimTextFactType and
                not fact.xmlLang):
            factsWithoutLang.append(fact)
    if len(factsWithoutLang) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.5.2.1.undefinedLanguageForTextFact',
            msg=_('Each tagged text fact MUST have the ‘xml:lang’ attribute assigned or inherited.'),
            modelObject=factsWithoutLang
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_5_2_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.5.2.2: All tagged text facts MUST be provided in at least the language of the report.
    """
    reportXmlLang = pluginData.getReportXmlLang(val.modelXbrl)
    filtered_facts = [f for f in val.modelXbrl.facts if f.concept is not None and
                      f.concept.type is not None and
                      f.concept.type.isOimTextFactType and
                      f.context is not None]
    factGroups = getHashEquivalentFactGroups(filtered_facts)
    for fgroup in factGroups:
        for flist in getAspectEqualFacts(fgroup, includeSingles=True, useLang=False):
            if not any(f.xmlLang == reportXmlLang for f in flist):
                yield Validation.error(
                    codes='NL.NL-KVK.3.5.2.2.taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport',
                    msg=_('Tagged text facts MUST be provided in the language of the report.'),
                    modelObject=fgroup
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_5_2_3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.5.2.3: The value of the @xml:lang attribute SHOULD be 'nl' or 'en' or 'de' or 'fr'.
    """
    badLangsUsed = set()
    for ixdsHtmlRootElt in val.modelXbrl.ixdsHtmlElements:
        for uncast_elt, depth in etreeIterWithDepth(ixdsHtmlRootElt):
            elt = cast(Any, uncast_elt)
            xmlLang = elt.get("{http://www.w3.org/XML/1998/namespace}lang")
            if xmlLang and xmlLang not in ALLOWABLE_LANGUAGES:
                badLangsUsed.add(xmlLang)
    if len(badLangsUsed) > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.3.5.2.3.invalidLanguageAttribute',
            badLangsUsed=', '.join(badLangsUsed),
            msg=_('The lang attribute should use one of the following: \'nl\' or \'en\' or \'de\' or \'fr\'. '
                  'The following languages are used incorrectly: %(badLangsUsed)s'),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_5_3_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.5.3.1: The default target attribute MUST be used for the annual report content.
    """
    targetElements = pluginData.getTargetElements(val.modelXbrl)
    if targetElements:
        yield Validation.error(
            codes='NL.NL-KVK.3.5.3.1.defaultTargetAttributeNotUsed',
            msg=_('Target attribute must not be used for the annual report content.'),
            modelObject=targetElements
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_5_4_1 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.5.4.1: Where CSS is used to format the reports, transformations MUST NOT be used to hide information by making it not visible
    e.g. by applying display:none style on any tagged facts.
    """
    facts = pluginData.getCssHiddenFacts(val.modelXbrl)
    if len(facts) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.5.4.1.displayNoneUsedToHideTaggedFacts',
            msg=_('Display:none has been used to hide tagged facts. This is not allowed.'),
            modelObject=facts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_6_3_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.6.3.1: The report filename will have the form `{base}-{date}-{lang}.{extension}`.
    The `{base}` component of the filename SHOULD not exceed twenty characters.
    """
    invalidBasenames = []
    for basename in pluginData.getIxdsDocBasenames(val.modelXbrl):
        filenameParts = pluginData.getFilenameParts(basename, pluginData.getFilenameFormatPattern())
        if not filenameParts:
            continue  # Filename is not formatted correctly enough to determine {base}
        if len(filenameParts.get('base', '')) > 20:
            invalidBasenames.append(basename)
    if len(invalidBasenames) > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.3.6.3.1.baseComponentInDocumentNameExceedsTwentyCharacters',
            invalidBasenames=', '.join(invalidBasenames),
            msg=_('The {base} component of the filename is greater than twenty characters. '
                  'The {base} component can either be the KVK number or the legal entity\'s name. '
                  'If the legal entity\'s name has been utilized, review to shorten the name to twenty characters or less. '
                  'Invalid filenames: %(invalidBasenames)s'))


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_6_3_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.6.3.2: Report filename SHOULD match the {base}-{date}-{lang}.{extension} pattern.
    {extension} MUST be one of the following: html, htm, xhtml.
    """
    invalidBasenames = []
    for basename in pluginData.getIxdsDocBasenames(val.modelXbrl):
        filenameParts = pluginData.getFilenameParts(basename, pluginData.getFilenameFormatPattern())
        if not filenameParts:
            invalidBasenames.append(basename)
    if len(invalidBasenames) > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.3.6.3.2.documentNameDoesNotFollowNamingConvention',
            invalidBasenames=', '.join(invalidBasenames),
            msg=_('The filename does not match the naming convention outlined by the KVK. '
                  'It is recommended to be in the {base}-{date}-{lang}.{extension} format. '
                  '{extension} must be one of the following: html, htm, xhtml. '
                  'Review formatting and update as appropriate. '
                  'Invalid filenames: %(invalidBasenames)s'))


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_6_3_3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.6.3.3: Report filename MUST only contain allowed characters.
    Filenames can include the following characters: A-Z, a-z, 0-9, underscore ( _ ), period ( . ), hyphen ( - ).
    """
    invalidBasenames = []
    for basename in pluginData.getIxdsDocBasenames(val.modelXbrl):
        if not pluginData.isFilenameValidCharacters(basename):
            invalidBasenames.append(basename)
    if len(invalidBasenames) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.6.3.3.documentFileNameIncludesCharactersNotAllowed',
            invalidBasenames=', '.join(invalidBasenames),
            msg=_('The file name includes characters that are now allowed. '
                  'Allowed characters include: A-Z, a-z, 0-9, underscore ( _ ), period ( . ), and hyphen ( - ). '
                  'Update filing naming to review unallowed characters. '
                  'Invalid filenames: %(invalidBasenames)s'))


@validation(
    hook=ValidationHook.FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_7_1_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.7.1.1: The filing MUST be valid against the formula linkbase assertions with error severity.
    """
    modelXbrl = val.modelXbrl
    sumErrMsgs = 0
    for e in modelXbrl.errors:
        if isinstance(e,dict):
            for id, (numSat, numUnsat, numOkMsgs, numWrnMsgs, numErrMsgs) in e.items():
                sumErrMsgs += numErrMsgs
    if sumErrMsgs > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.7.1.1.targetXBRLDocumentWithFormulaErrors',
            msg=_("The filing is not valid against the formula linkbase assertions with error severity.  Address the %(numUnsatisfied)s unresolved formula linkbase validation errors."),
            modelObject=modelXbrl,
            numUnsatisfied=sumErrMsgs
        )


@validation(
    hook=ValidationHook.FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_3_7_1_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.7.1.2: The filing MUST be valid against the formula linkbase assertions with error warning.
    """
    modelXbrl = val.modelXbrl
    sumWrnMsgs = 0
    for e in modelXbrl.errors:
        if isinstance(e,dict):
            for id, (numSat, numUnsat, numOkMsgs, numWrnMsgs, numErrMsgs) in e.items():
                sumWrnMsgs += numWrnMsgs
    if sumWrnMsgs > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.3.7.1.2.targetXBRLDocumentWithFormulaWarnings',
            msg=_("The filing is not valid against the formula linkbase assertions with warning severity.  Address the %(numUnsatisfied)s unresolved formula linkbase validation warnings."),
            modelObject=modelXbrl,
            numUnsatisfied=sumWrnMsgs
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_4_1_1_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.1.1.1: Extension taxonomies MUST consist of at least a schema file and presentation,
                                                                                   calculation and definition linkbases.
    A label linkbase is also required if extension elements are present.
    """
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    linkbaseIsMissing = {
        LinkbaseType.CALCULATION: True,
        LinkbaseType.DEFINITION: True,
        LinkbaseType.LABEL: len(extensionData.extensionConcepts) > 0,
        LinkbaseType.PRESENTATION: True,
    }
    for modelDocument, extensionDocumentData in extensionData.extensionDocuments.items():
        hasArcs = False
        linkbaseType = LinkbaseType.fromRefUri(extensionDocumentData.hrefXlinkRole)
        for linkbaseData in extensionDocumentData.linkbases:
            if linkbaseType is not None:
                if linkbaseType == linkbaseData.linkbaseType:
                    if linkbaseData.hasArcs:
                        hasArcs = True
                        break
            elif linkbaseData.hasArcs:
                linkbaseType = linkbaseData.linkbaseType
                hasArcs = True
                break
        if linkbaseType is None:
            continue
        if hasArcs and linkbaseIsMissing.get(linkbaseType, False):
            linkbaseIsMissing[linkbaseType] = False
    missingFiles = set(linkbaseType.getLowerName() for linkbaseType, isMissing in linkbaseIsMissing.items() if isMissing)
    if len(missingFiles) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.4.1.1.1.extensionTaxonomyWrongFilesStructure',
            msg=_('The extension taxonomy is missing one or more required components: %(missingFiles)s '
                  'Review to ensure that the schema file, presentation, calculation, '
                  'and definition linkbases are included and not empty. '
                  'A label linkbase is also required if extension elements are present.'),
            modelObject=val.modelXbrl, missingFiles=", ".join(missingFiles)
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_4_1_1_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.1.1.2: Each linkbase type MUST be provided in a separate linkbase file.
    """
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    errors = []
    for modelDocument, extensionDocumentData in extensionData.extensionDocuments.items():
        linkbasesFound = set(
            linkbase.linkbaseType.getLowerName()
            for linkbase in extensionDocumentData.linkbases
            if linkbase.linkbaseType is not None
        )
        if len(linkbasesFound) > 1:
            errors.append((modelDocument, linkbasesFound))
    for modelDocument, linkbasesFound in errors:
        yield Validation.error(
            codes='NL.NL-KVK.4.1.1.2.linkbasesNotSeparateFiles',
            msg=_('Linkbase types are not stored in separate files. '
                  'Review linkbase files and ensure they are provided as individual files. '
                  'Found: %(linkbasesFound)s. in %(basename)s.'),
            modelObject=modelDocument.xmlRootElement,
            basename=modelDocument.basename,
            linkbasesFound=", ".join(sorted(linkbasesFound))
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_4_1_2_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.1.2.1: Validate that the imported taxonomy matches the KVK-specified entry point.
        - https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-nlgaap-ext.xsd
        - https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-ifrs-ext.xsd
    """
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    matches = extensionData.extensionImportedUrls & EFFECTIVE_KVK_GAAP_IFRS_ENTRYPOINT_FILES
    if not matches:
        yield Validation.error(
            codes='NL.NL-KVK.4.1.2.1.requiredEntryPointNotImported',
            msg=_('The extension taxonomy must import the entry point of the taxonomy files prepared by KVK.'),
            modelObject=val.modelXbrl.modelDocument
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_4_1_2_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.1.2.2: The legal entity’s extension taxonomy MUST import the applicable version of
                    the taxonomy files prepared by KVK.
    """
    reportingPeriod = pluginData.getReportingPeriod(val.modelXbrl)
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    matches = extensionData.extensionImportedUrls & TAXONOMY_URLS_BY_YEAR.get(reportingPeriod or '', set())
    if not reportingPeriod or not matches:
        yield Validation.error(
            codes='NL.NL-KVK.4.1.2.2.incorrectKvkTaxonomyVersionUsed',
            msg=_('The extension taxonomy MUST import the applicable version of the taxonomy files prepared by KVK '
                  'for the reported financial reporting period of %(reportingPeriod)s.'),
            modelObject=val.modelXbrl.modelDocument
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_4_1_5_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.1.5.1: The `{base}` component of the extension document filename SHOULD not exceed twenty characters.
    """
    invalidBasenames = []
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for extensionDocument in extensionData.extensionDocuments.values():
        basename = extensionDocument.basename
        filenameParts = pluginData.getFilenameParts(basename, pluginData.getExtensionFilenameFormatPattern())
        if not filenameParts:
            continue  # Filename is not formatted correctly enough to determine {base}
        if len(filenameParts.get('base', '')) > 20:
            invalidBasenames.append(basename)
    if len(invalidBasenames) > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.4.1.5.1.baseComponentInNameOfTaxonomyFileExceedsTwentyCharacters',
            invalidBasenames=', '.join(invalidBasenames),
            msg=_('The {base} component of the extension document filename is greater than twenty characters. '
                  'The {base} component can either be the KVK number or the legal entity\'s name. '
                  'If the legal entity\'s name has been utilized, review to shorten the name to twenty characters or less. '
                  'Invalid filenames: %(invalidBasenames)s'))


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_4_1_5_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.1.5.2: Extension document filename SHOULD match the {base}-{date}_{suffix}-{lang}.{extension} pattern.
    """
    invalidBasenames = []
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for extensionDocument in extensionData.extensionDocuments.values():
        basename = extensionDocument.basename
        filenameParts = pluginData.getFilenameParts(basename, pluginData.getExtensionFilenameFormatPattern())
        if not filenameParts:
            invalidBasenames.append(basename)
    if len(invalidBasenames) > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.4.1.5.2.extensionTaxonomyDocumentNameDoesNotFollowNamingConvention',
            invalidBasenames=', '.join(invalidBasenames),
            msg=_('The extension document filename does not match the naming convention outlined by the KVK. '
                  'It is recommended to be in the {base}-{date}_{suffix}-{lang}.{extension} format. '
                  '{extension} must be one of the following: html, htm, xhtml. '
                  'Review formatting and update as appropriate. '
                  'Invalid filenames: %(invalidBasenames)s'))


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_4_2_0_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.2.0.1: Tuples MUST NOT be defined in extension taxonomy.
    """
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    tupleConcepts = [
        concept for concept in extensionData.extensionConcepts if concept.isTuple
    ]
    if len(tupleConcepts) > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.4.2.0.1.tupleElementUsed',
            modelObject=tupleConcepts,
            msg=_('The extension taxonomy must not define tuple concepts.'))


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_4_2_0_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.2.0.2: Items with xbrli:fractionItemType data type MUST NOT be defined in extension taxonomy
    """
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    fractionConcepts = [
        concept for concept in extensionData.extensionConcepts if concept.isFraction
    ]
    if len(fractionConcepts) > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.4.2.0.2.fractionElementUsed',
            modelObject=fractionConcepts,
            msg=_('The extension taxonomy must not define fraction concepts.'))


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NL_INLINE_2024
    ],
)
def rule_nl_kvk_6_1_1_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.6.1.1.1: The size of the report package MUST NOT exceed 100 MB.
    """
    if val.modelXbrl.fileSource.fs and isinstance(val.modelXbrl.fileSource.fs, zipfile.ZipFile):
        maxMB = float(MAX_REPORT_PACKAGE_SIZE_MBS)
        # The following code computes report package size by adding the compressed file sizes within the package.
        # This method of computation is over 99% accurate and gets more accurate the larger the filesize is.
        _size = sum(zi.compress_size for zi in val.modelXbrl.fileSource.fs.infolist())
        if _size > maxMB * 1000000:
            yield Validation.error(
                codes='NL.NL-KVK.6.1.1.1.reportPackageMaximumSizeExceeded',
                msg=_('The size of the report package must not exceed %(maxSize)s MBs, size is %(size)s MBs.'),
                modelObject=val.modelXbrl, maxSize=MAX_REPORT_PACKAGE_SIZE_MBS, size=int(_size/1000000)
            )
