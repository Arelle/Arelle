"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from datetime import date

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
from ..PluginValidationDataExtension import (PluginValidationDataExtension, XBRLI_IDENTIFIER_PATTERN,
                                             XBRLI_IDENTIFIER_SCHEMA, DISALLOWED_IXT_NAMESPACES, ALLOWABLE_LANGUAGES)

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
def rule_nl_kvk_3_5_2_3 (
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
            msg=_('The lang attribute should use one of the following: \'nl\' or \'en\' or \'de\' or \'fr\'. '
                  'The following languages are used incorrectly: {}'.format(badLangsUsed)),
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
        filenameParts = pluginData.getFilenameParts(basename)
        if not filenameParts:
            continue  # Filename pattern not matched
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
        match = pluginData.getFilenameAllowedCharactersPattern().match(basename)
        if not match:
            continue  # Let NL-KVK.3.6.3.3 handle this
        filenameParts = pluginData.getFilenameParts(basename)
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
        match = pluginData.getFilenameAllowedCharactersPattern().match(basename)
        if not match:
            invalidBasenames.append(basename)
    if len(invalidBasenames) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.3.6.3.3.documentFileNameIncludesCharactersNotAllowed',
            invalidBasenames=', '.join(invalidBasenames),
            msg=_('The file name includes characters that are now allowed. '
                  'Allowed characters include: A-Z, a-z, 0-9, underscore ( _ ), period ( . ), and hyphen ( - ). '
                  'Update filing naming to review unallowed characters. '
                  'Invalid filenames: %(invalidBasenames)s'))
