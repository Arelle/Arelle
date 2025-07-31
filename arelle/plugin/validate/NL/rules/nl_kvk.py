"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from typing import Any, cast, TYPE_CHECKING

from lxml.etree import Element

from arelle.LinkbaseType import LinkbaseType
from arelle.ModelDtsObject import ModelConcept, ModelLink, ModelResource, ModelType
from arelle.ModelInstanceObject import ModelInlineFact
from arelle.ModelObject import ModelObject
from arelle.PrototypeDtsObject import PrototypeObject
from arelle.ValidateDuplicateFacts import getDuplicateFactSets
from arelle.XbrlConst import parentChild, standardLabel
from arelle.XmlValidateConst import VALID

from arelle import XbrlConst, XmlUtil, ModelDocument
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.DetectScriptsInXhtml import containsScriptMarkers
from arelle.utils.validate.ESEFImage import ImageValidationParameters, validateImage
from arelle.utils.validate.Validation import Validation
from arelle.ValidateDuplicateFacts import getHashEquivalentFactGroups, getAspectEqualFacts
from arelle.utils.validate.ValidationUtil import etreeIterWithDepth
from ..DisclosureSystems import (ALL_NL_INLINE_DISCLOSURE_SYSTEMS, NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
                                 NL_INLINE_GAAP_OTHER_DISCLOSURE_SYSTEMS)
from ..PluginValidationDataExtension import (
    PluginValidationDataExtension,
    ALLOWABLE_LANGUAGES,
    DEFAULT_MEMBER_ROLE_URI,
    DISALLOWED_IXT_NAMESPACES,
    EFFECTIVE_KVK_GAAP_IFRS_ENTRYPOINT_FILES,
    EFFECTIVE_KVK_GAAP_OTHER_ENTRYPOINT_FILES,
    MAX_REPORT_PACKAGE_SIZE_MBS,
    NON_DIMENSIONALIZED_LINE_ITEM_LINKROLES,
    QN_DOMAIN_ITEM_TYPES,
    SUPPORTED_IMAGE_TYPES_BY_IS_FILE,
    TAXONOMY_URLS_BY_YEAR,
    XBRLI_IDENTIFIER_PATTERN,
    XBRLI_IDENTIFIER_SCHEMA,
)

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelValue import QName

_: TypeGetText

DOCTYPE_XHTML_PATTERN = re.compile(r"^<!(?:DOCTYPE\s+)\s*html(?:PUBLIC\s+)?(?:.*-//W3C//DTD\s+(X?HTML)\s)?.*>$", re.IGNORECASE)


def _getReportingPeriodDateValue(modelXbrl: ModelXbrl, qname: QName) -> date | None:
    facts = modelXbrl.factsByQname.get(qname)
    if facts and len(facts) == 1:
        datetimeValue = XmlUtil.datetimeValue(next(iter(facts)))
        if datetimeValue:
            return datetimeValue.date()
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    entityIdentifierValues = val.modelXbrl.entityIdentifiersInDocument()
    for entityId in entityIdentifierValues:
        if not XBRLI_IDENTIFIER_PATTERN.match(entityId[1]):
            yield Validation.error(
                codes='NL.NL-KVK-RTS_Annex_IV_Par_2_G3-1-1_1.invalidIdentifierFormat',
                msg=_('xbrli:identifier content to match KVK number format that must consist of 8 consecutive digits. '
                      'Additionally the first two digits must not be "00".'),
                modelObject = val.modelXbrl
            )
            return


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    entityIdentifierValues = val.modelXbrl.entityIdentifiersInDocument()
    for entityId in entityIdentifierValues:
        if XBRLI_IDENTIFIER_SCHEMA != entityId[0]:
            yield Validation.error(
                codes='NL.NL-KVK-RTS_Annex_IV_Par_2_G3-1-1_2.invalidIdentifier',
                msg=_('The scheme attribute of the xbrli:identifier does not match the required content. '
                      'This should be "http://www.kvk.nl/kvk-id".'),
                modelObject = val.modelXbrl
            )
            return


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    entityIdentifierValues = val.modelXbrl.entityIdentifiersInDocument()
    if len(entityIdentifierValues) >1:
        yield Validation.error(
            codes='NL.NL-KVK-RTS_Annex_IV_Par_1_G3-1-4_1.multipleIdentifiers',
            msg=_('All entity identifiers and schemes must have identical content.'),
            modelObject = entityIdentifierValues
        )



@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
            msg=_('Ensure that any block-tagged facts of type textBlockItemType are assigned @escape="true", '
                  'while other data types (e.g., xbrli:stringItemType) are assigned @escape="false".'),
            modelObject = improperlyEscapedFacts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_3_2_8_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.2.8.1: Include unique @id attribute for each tagged fact
    """
    errors = {fact for fact in val.modelXbrl.facts if not fact.id}
    if len(errors) > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.3.2.8.1',
            msg=_('All facts should include an id attribute'),
            modelObject=errors
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_3_5_1_1_non_img (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.5.1.1: Resources embedded or referenced by the XHTML document and its inline XBRL MUST NOT contain executable code.
    """

    executableElements = []
    for ixdsHtmlRootElt in val.modelXbrl.ixdsHtmlElements:
        for elt in ixdsHtmlRootElt.iter(Element):
            if containsScriptMarkers(elt):
                executableElements.append(elt)
    if executableElements:
        yield Validation.error(
            codes='NL.NL-KVK.3.5.1.1.executableCodePresent',
            msg=_("Resources embedded or referenced by the XHTML document and its inline XBRL MUST NOT contain executable code."),
            modelObject=executableElements,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_3_5_1_img (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.5.1.1: Inline XBRL images MUST NOT contain executable code.
    NL-KVK.3.5.1.2: Images included in the XHTML document MUST be saved with MIME type specifying PNG, GIF, SVG or JPG/JPEG formats.
    NL-KVK.3.5.1.3: File type inferred from file signature does not match the data URL media subtype (MIME subtype).
    NL-KVK.3.5.1.4: File type inferred from file signature does not match the file extension.
    NL-KVK.3.5.1.5: Images included in the XHTML document MUST be saved in PNG, GIF, SVG or JPG/JPEG formats.
    """

    imageValidationParameters = ImageValidationParameters.from_non_esef(
        checkMinExternalResourceSize=False,
        missingMimeTypeIsIncorrect=False,
        recommendBase64EncodingEmbeddedImages=False,
        supportedImgTypes=SUPPORTED_IMAGE_TYPES_BY_IS_FILE,
    )
    for ixdsHtmlRootElt in val.modelXbrl.ixdsHtmlElements:
        for elt in ixdsHtmlRootElt.iter((f'{{{XbrlConst.xhtml}}}img', '{http://www.w3.org/2000/svg}svg')):
            src = elt.get('src', '').strip()
            evaluatedMsg = _('On line {line}, "alt" attribute value: "{alt}"').format(line=elt.sourceline, alt=elt.get('alt'))
            yield from validateImage(
                elt.modelDocument.baseForElement(elt),
                src,
                val.modelXbrl,
                val,
                elt,
                evaluatedMsg,
                imageValidationParameters,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_3_5_2_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.3.5.2.1: Each tagged text fact MUST have the 'xml:lang' attribute assigned or inherited.
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
            msg=_("Each tagged text fact MUST have the 'xml:lang' attribute assigned or inherited."),
            modelObject=factsWithoutLang
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_1_2_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.1.2.2: The legal entity's extension taxonomy MUST import the applicable version of
                    the taxonomy files prepared by KVK.
    """
    reportingPeriod = pluginData.getReportingPeriod(val.modelXbrl)
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    matches = extensionData.extensionImportedUrls & TAXONOMY_URLS_BY_YEAR.get(reportingPeriod or '', set())
    if not reportingPeriod or not matches:
        yield Validation.error(
            codes='NL.NL-KVK.4.1.2.2.incorrectKvkTaxonomyVersionUsed',
            msg=_('The extension taxonomy MUST import the applicable version of the taxonomy files prepared by KVK '
                  'for the reported financial reporting period. Verify the taxonomy version and make sure '
                  'that FinancialReportingPeriod are tagged correctly.'),
            modelObject=val.modelXbrl.modelDocument
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
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
        yield Validation.error(
            codes='NL.NL-KVK.4.2.0.1.tupleElementUsed',
            modelObject=tupleConcepts,
            msg=_('The extension taxonomy must not define tuple concepts.'))


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
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
        yield Validation.error(
            codes='NL.NL-KVK.4.2.0.2.fractionElementUsed',
            modelObject=fractionConcepts,
            msg=_('The extension taxonomy must not define fraction concepts.'))


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_2_1_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.2.1.1: Extension taxonomy MUST set xbrli:scenario as context element on definition arcs with
    http://xbrl.org/int/dim/arcrole/all and http://xbrl.org/int/dim/arcrole/notAll arcroles.
    """
    errors = []
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for modelDocument, extensionDocumentData in extensionData.extensionDocuments.items():
        for arc in extensionDocumentData.iterArcsByType(LinkbaseType.DEFINITION, includeArcroles={XbrlConst.all, XbrlConst.notAll}):
            if arc.get(XbrlConst.qnXbrldtContextElement.clarkNotation) != "scenario":
                errors.append(arc)
    if len(errors) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.4.2.1.1.scenarioNotUsedInExtensionTaxonomy',
            modelObject=errors,
            msg=_('The definition linkbase is missing xbrli:scenario in extension taxonomy. '
                  'Review definition linkbase and update as appropriate.'),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_2_2_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.2.2.2: Domain members MUST have domainItemType data type as defined in https://www.xbrl.org/dtr/type/2022-03-31/types.xsd.
    """
    domainMembersWrongType = []
    domainMembers = pluginData.getDimensionalData(val.modelXbrl).domainMembers
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for concept in extensionData.extensionConcepts:
        if concept.isDomainMember and concept in domainMembers and concept.typeQname not in QN_DOMAIN_ITEM_TYPES:
            domainMembersWrongType.append(concept)
    if len(domainMembersWrongType) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.4.2.2.2.domainMemberWrongDataType',
            modelObject=domainMembersWrongType,
            msg=_('Domain members must have domainItemType data type as defined in "https://www.xbrl.org/dtr/type/2022-03-31/types.xsd".'
                  'Update to follow appropriate Data Type Registry.  '))


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_2_3_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.2.3.1: Extension taxonomy MUST NOT define typed dimensions.
    """
    typedDims = []
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for concept in extensionData.extensionConcepts:
        if concept.isTypedDimension:
            typedDims.append(concept)
    if len(typedDims) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.4.2.3.1.typedDimensionDefinitionInExtensionTaxonomy',
            modelObject=typedDims,
            msg=_('Typed dimensions are not allowed in the extension taxonomy.  Update to remove the typed dimension.'))


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_3_1_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.3.1.1: Anchoring relationships for elements other than concepts MUST not
    use 'http://www.esma.europa.eu/xbrl/esef/arcrole/wider-narrower' arcrole
    """
    anchorData = pluginData.getAnchorData(val.modelXbrl)
    if len(anchorData.extLineItemsWronglyAnchored) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.4.3.1.1.unexpectedAnchoringRelationshipsDefinedUsingWiderNarrowerArcrole',
            modelObject=anchorData.extLineItemsWronglyAnchored,
            msg=_('A custom element that is not a line item concept is using the wider-narrower arcrole. '
                  'Only line item concepts should use this arcrole. '
                  'Update the extension to no longer include this arcole.')
        )
    for anchor in anchorData.anchorsWithDomainItem:
        yield Validation.error(
            codes="NL.NL-KVK.4.3.1.1.unexpectedAnchoringRelationshipsDefinedUsingWiderNarrowerArcrole",
            msg=_("Anchoring relationships MUST be from and to concepts, from %(qname1)s to %(qname2)s"),
            modelObject=(anchor, anchor.fromModelObject, anchor.toModelObject),
            qname1=anchor.fromModelObject.qname,
            qname2=anchor.toModelObject.qname
        )
    for anchor in anchorData.anchorsWithDimensionItem:
        yield Validation.error(
            codes="NL.NL-KVK.4.3.1.1.unexpectedAnchoringRelationshipsDefinedUsingWiderNarrowerArcrole",
            msg=_("Anchoring relationships MUST be from and to concepts, from %(qname1)s to %(qname2)s"),
            modelObject=(anchor, anchor.fromModelObject, anchor.toModelObject),
            qname1=anchor.fromModelObject.qname,
            qname2=anchor.toModelObject.qname
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_3_2_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.3.2.1: Anchoring relationships for concepts MUST be defined in a dedicated
    extended link role (or roles if needed to properly represent the relationships),
    e.g. http://{default pattern for roles}/Anchoring.
    """
    anchorData = pluginData.getAnchorData(val.modelXbrl)
    for elr, rels in anchorData.anchorsInDimensionalElrs.items():
        yield Validation.error(
            codes="NL.NL-KVK.4.3.2.1.anchoringRelationshipsForConceptsDefinedInElrContainingDimensionalRelationships",
            msg=_("Anchoring relationships for concepts MUST be defined in a dedicated extended link role "
                  "(or roles if needed to properly represent the relationships), e.g. "
                  "http://{issuer default pattern for roles}/Anchoring. %(anchoringDimensionalELR)s"),
            modelObject=rels,
            anchoringDimensionalELR=elr
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_4_1_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.4.1.1: Arithmetical relationships defined in the calculation linkbase of an extension taxonomy
    MUST use the https://xbrl.org/2023/arcrole/summation-item arcrole as defined in Calculation 1.1 specification.
    """
    errors = []
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for modelDocument, extensionDocumentData in extensionData.extensionDocuments.items():
        for arc in extensionDocumentData.iterArcsByType(LinkbaseType.CALCULATION, excludeArcroles={XbrlConst.summationItem11}):
            errors.append(arc)
    if len(errors) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.4.4.1.1.incorrectSummationItemArcroleUsed',
            modelObject=errors,
            msg=_('Calculation relationships should follow the requirements of the Calculation 1.1 specification. '
                  'Update to ensure use of summation-item arcrole in the calculation linkbase.'),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_4_2_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.4.2.1: Extension taxonomies MUST NOT define definition arcs
    with http://xbrl.org/int/dim/arcrole/notAll arcrole.
    """
    errors = []
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for modelDocument, extensionDocumentData in extensionData.extensionDocuments.items():
        for arc in extensionDocumentData.iterArcsByType(LinkbaseType.DEFINITION, includeArcroles={XbrlConst.notAll}):
            errors.append(arc)
    if len(errors) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.4.4.2.1.notAllArcroleUsedInDefinitionLinkbase',
            modelObject=errors,
            msg=_('Incorrect hypercube settings are found.  Ensure that positive hypercubes are in use.'),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_4_2_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.4.2.2: Hypercubes appearing as target of definition arc with
    http://xbrl.org/int/dim/arcrole/all arcrole MUST have xbrldt:closed attribute set to "true".
    """
    errors = []
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for modelDocument, extensionDocumentData in extensionData.extensionDocuments.items():
        for arc in extensionDocumentData.iterArcsByType(LinkbaseType.DEFINITION, includeArcroles={XbrlConst.all}):
            if arc.get(XbrlConst.qnXbrldtClosed.clarkNotation, "false") != "true":
                errors.append(arc)
    if len(errors) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.4.4.2.2.openPositiveHypercubeInDefinitionLinkbase',
            modelObject=errors,
            msg=_('Incorrect hypercube settings are found.  Ensure that positive hypercubes are closed.'),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_4_2_3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.4.2.3: Hypercubes appearing as target of definition arc with
    http://xbrl.org/int/dim/arcrole/notAll arcrole MUST have xbrldt:closed attribute set to "false".
    """
    errors = []
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for modelDocument, extensionDocumentData in extensionData.extensionDocuments.items():
        for arc in extensionDocumentData.iterArcsByType(LinkbaseType.DEFINITION, includeArcroles={XbrlConst.notAll}):
            if arc.get(XbrlConst.qnXbrldtClosed.clarkNotation, "true") != "false":
                errors.append(arc)
    if len(errors) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.4.4.2.3.closedNegativeHypercubeInDefinitionLinkbase',
            modelObject=errors,
            msg=_('Incorrect hypercube settings are found.  Ensure that negative hypercubes are not closed.'),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_4_2_4(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.4.2.4: Line items that do not require any dimensional information to tag data MUST be linked to the hypercube in the dedicated
    extended link role
    """
    elrPrimaryItems = pluginData.getDimensionalData(val.modelXbrl).elrPrimaryItems
    errors = set()
    for concept in val.modelXbrl.qnameConcepts.values():
        if concept.qname not in val.modelXbrl.factsByQname:
            continue
        if any(
                concept in elrPrimaryItems.get(lr, set())
                for lr in NON_DIMENSIONALIZED_LINE_ITEM_LINKROLES
        ):
            continue
        if concept in elrPrimaryItems.get("*", set()):
            continue
        errors.add(concept)
    for error in errors:
        yield Validation.error(
            codes='NL.NL-KVK.4.4.2.4.extensionTaxonomyLineItemNotLinkedToAnyHypercube',
            modelObject=error,
            msg=_('A non-dimensional concept was not associated to a hypercube.  Update relationship so concept is linked to a hypercube.'),
        )

@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_4_3_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.4.3.1: The extension taxonomy MUST not modify (prohibit and/or override) default members assigned to dimensions by the KVK taxonomy
    """
    for modelLink in cast(list[ModelLink], val.modelXbrl.baseSets[XbrlConst.dimensionDefault, None, None, None]):
        if not pluginData.isExtensionUri(modelLink.modelDocument.uri, val.modelXbrl):
            continue
        for linkChild in modelLink:
            if (
                    isinstance(linkChild,(ModelObject,PrototypeObject))
                    and linkChild.get(XbrlConst.qnXlinkType.clarkNotation) == "arc"
                    and linkChild.get(XbrlConst.qnXlinkArcRole.clarkNotation) == XbrlConst.dimensionDefault
            ):
                fromLabel = linkChild.get(XbrlConst.qnXlinkFrom.clarkNotation)
                for fromResource in modelLink.labeledResources[fromLabel]:
                    if not pluginData.isExtensionUri(fromResource.modelDocument.uri, val.modelXbrl):
                        yield Validation.error(
                            codes='NL.NL-KVK.4.4.3.1.extensionTaxonomyOverridesDefaultMembers',
                             msg=_('A default member does not match the default member settings of the taxonomy. '
                                   'Update the default member to taxonomy defaults.'
                                   ),
                            modelObject=linkChild
                        )
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for modelDocument, extensionDocumentData in extensionData.extensionDocuments.items():
        for arc in extensionDocumentData.iterArcsByType(LinkbaseType.DEFINITION, includeArcroles={XbrlConst.dimensionDefault}):
            if arc.get("use") == "prohibited":
                yield Validation.error(
                    codes='NL.NL-KVK.4.4.3.1.extensionTaxonomyOverridesDefaultMembers',
                    msg=_('A default member is forbidden in the extension taxonomy. '
                          'Update the default member to taxonomy defaults.'
                          ),
                    modelObject=arc
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_4_3_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.4.3.2: Each dimension in an extension taxonomy MUST be assigned to a default member in the ELR with role URI https://www.nltaxonomie.nl/kvk/role/axis-defaults.
    """
    dimensionDefaults =val.modelXbrl.relationshipSet(XbrlConst.dimensionDefault, DEFAULT_MEMBER_ROLE_URI)
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for modelConcept in extensionData.extensionConcepts:
        if modelConcept.isExplicitDimension and not dimensionDefaults.fromModelObject(modelConcept):
            yield Validation.error(
                codes='NL.NL-KVK.4.4.2.3.extensionTaxonomyDimensionNotAssignedDefaultMemberInDedicatedPlaceholder',
                modelObject=modelConcept,
                msg=_('Axis is missing a default member or the default member does not match the taxonomy defaults. '
                      'Update to set default member based on taxonomy defaults.'
                      ),
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_4_4_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.4.4.1: Duplicated line items in the presentation tree of extension taxonomy SHOULD use preferred labels on presentation links.
    """
    warnings = set()
    for ELR in val.modelXbrl.relationshipSet(XbrlConst.parentChild).linkRoleUris:
        relSet = val.modelXbrl.relationshipSet(XbrlConst.parentChild, ELR)
        for rootConcept in relSet.rootConcepts:
            warnings = pluginData.checkLabels(set(), val.modelXbrl , rootConcept, relSet, None, set())
        if len(warnings) > 0:
            yield Validation.warning(
                codes='NL.NL-KVK.4.4.4.1.missingPreferredLabelRole',
                modelObject=warnings,
                msg=_('Multiple concepts exist in the presentation with the same label role. '
                      'Review presentation if duplicate concepts should exist or separate preferred label roles should be set.'),
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_4_5_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.4.5.1: Custom labels roles SHOULD NOT be used.
    """
    warnings = []
    labelsRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    if not labelsRelationshipSet:
        return
    for labelRels in labelsRelationshipSet.fromModelObjects().values():
        for labelRel in labelRels:
            label = cast(ModelResource, labelRel.toModelObject)
            if label.role in XbrlConst.standardLabelRoles:
                continue
            roleType = val.modelXbrl.roleTypes.get(label.role)
            if roleType is not None and \
                    roleType[0].modelDocument.uri.startswith("http://www.xbrl.org/lrr"):
                continue
            warnings.append(label)
    if len(warnings) > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.4.4.5.1.taxonomyElementLabelCustomRole',
            modelObject=warnings,
            msg=_('A custom label role has been used.  Update to label role to non-custom.'),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_4_5_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.4.5.2: Extension taxonomy elements SHOULD be assigned with at most one label for any combination of role and language.
    Additionally, extension taxonomies shall not override or replace standard labels of elements referenced in the KVK taxonomy.
    """
    labelsRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    extensionConcepts = extensionData.extensionConcepts
    for concept in val.modelXbrl.qnameConcepts.values():
        conceptLangRoleLabels = defaultdict(list)
        labelRels = labelsRelationshipSet.fromModelObject(concept)
        for labelRel in labelRels:
            label = cast(ModelResource, labelRel.toModelObject)
            conceptLangRoleLabels[(label.xmlLang, label.role)].append(labelRel.toModelObject)
        for (lang, labelRole), labels in conceptLangRoleLabels.items():
            if concept in extensionConcepts and len(labels) > 1:
                yield Validation.error(
                    codes='NL.NL-KVK.4.4.5.2.taxonomyElementDuplicateLabels',
                    msg=_('A concept was found with more than one label role for related language. '
                          'Update to only one combination. Language: %(lang)s, Role: %(labelRole)s, Concept: %(concept)s.'),
                    modelObject=[concept]+labels, concept=concept.qname, lang=lang, labelRole=labelRole,
                )
            elif labelRole == XbrlConst.standardLabel:
                hasCoreLabel = False
                hasExtensionLabel = False
                for label in labels:
                    if pluginData.isExtensionUri(label.modelDocument.uri, val.modelXbrl):
                        hasExtensionLabel = True
                    else:
                        hasCoreLabel = True
                if hasCoreLabel and hasExtensionLabel:
                    labels_files = ['"%s": %s' % (l.text, l.modelDocument.basename) for l in labels]
                    yield Validation.error(
                        codes='NL.NL-KVK.4.4.5.2.taxonomyElementDuplicateLabels',
                        msg=_("An extension taxonomy defines a standard label for a concept "
                              "already labeled by the base taxonomy. Language: %(lang)s, "
                              "Role: %(labelRole)s, Concept: %(concept)s, Labels: %(labels)s"),
                        modelObject=[concept]+labels, concept=concept.qname, lang=lang,
                        labelRole=labelRole, labels=", ".join(labels_files),
                    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_4_4_6_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.4.4.6.1: All usable concepts in extension taxonomy relationships SHOULD be applied by tagged facts.
    """
    conceptsUsed = {f.concept for f in val.modelXbrl.facts}
    unreportedLbLocs = set()
    for arcrole in (XbrlConst.parentChild, XbrlConst.summationItems, XbrlConst.all, XbrlConst.dimensionDomain, XbrlConst.domainMember):
        for rel in val.modelXbrl.relationshipSet(arcrole).modelRelationships:
            for object in (rel.fromModelObject, rel.toModelObject):
                if (object is None or
                        object.isAbstract or
                        object in conceptsUsed or
                        not pluginData.isExtensionUri(rel.modelDocument.uri, val.modelXbrl)):
                    continue
                if arcrole in (XbrlConst.parentChild, XbrlConst.summationItems):
                    unreportedLbLocs.add(rel.fromLocator)
                elif object.type is not None and rel.isUsable and not object.type.isDomainItemType:
                    unreportedLbLocs.add(rel.fromLocator)
    if len(unreportedLbLocs) > 0:
        yield Validation.warning(
            # Subtitle is capitalized inconsistently here because it matches the conformance suite. This may change in the future.
            codes='NL.NL-KVK.4.4.6.1.UsableConceptsNotAppliedByTaggedFacts',
            modelObject=unreportedLbLocs,
            msg=_('Concept was found but not reported on any facts. '
                  'Remove any unused concepts or ensure concept is applied to applicable facts.'),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_OTHER_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_5_1_3_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.5.1.3.1: Validate that the imported taxonomy matches the KVK-specified entry point.
        - https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-other-gaap.xsd
    """
    uris = {doc[0].uri for doc in val.modelXbrl.namespaceDocs.values()}
    matches = uris & EFFECTIVE_KVK_GAAP_OTHER_ENTRYPOINT_FILES
    if not matches:
        yield Validation.error(
            codes='NL.NL-KVK.5.1.3.1.requiredEntryPointOtherGaapNotReferenced',
            msg=_('The extension taxonomy must import the entry point of the taxonomy files prepared by KVK.'),
            modelObject=val.modelXbrl.modelDocument
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_OTHER_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_5_1_3_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.5.1.3.2: The legal entity's report MUST import the applicable version of
                    the taxonomy files prepared by KVK.
    """
    reportingPeriod = pluginData.getReportingPeriod(val.modelXbrl)
    uris = {doc[0].uri for doc in val.modelXbrl.namespaceDocs.values()}
    matches = uris & TAXONOMY_URLS_BY_YEAR.get(reportingPeriod or '', set())
    if not reportingPeriod or not matches:
        yield Validation.error(
            codes='NL.NL-KVK.5.1.3.2.incorrectVersionEntryPointOtherGaapReferenced',
            msg=_('The report MUST import the applicable version of the taxonomy files prepared by KVK '
                  'for the reported financial reporting period. Verify the taxonomy version and make sure '
                  'that FinancialReportingPeriod are tagged correctly.'),
            modelObject=val.modelXbrl.modelDocument
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
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
    size = val.modelXbrl.fileSource.getBytesSize()
    if size is None:
        return  # File size is not available, cannot validate
    if size > MAX_REPORT_PACKAGE_SIZE_MBS * 1_000_000:  # Interpretting MB as megabytes (1,000,000 bytes)
        yield Validation.error(
            codes='NL.NL-KVK.6.1.1.1.reportPackageMaximumSizeExceeded',
            msg=_('The size of the report package must not exceed %(maxSize)s MBs, size is %(size)s MBs.'),
            modelObject=val.modelXbrl, maxSize=MAX_REPORT_PACKAGE_SIZE_MBS, size=int(size/1000000)
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_RTS_Annex_II_Par_1_RTS_Annex_IV_par_7(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.RTS_Annex_II_Par_1_RTS_Annex_IV_par_7: Legal entities should mark all amounts in a designated currency included in a. the balance sheet, income statement, cash flow statement,
    statement of comprehensive income and statement of changes in equity of the (consolidated) financial statements based on NL-GAAP; or b. the statement of financial position,
    the income statement (separately or as part of the statement of comprehensive income), the statement of comprehensive income, the statement of changes in equity and
    the statement of cash flows of the (consolidated) financial statements based on IFRS.
    """
    warnings = []
    permissibleAbstracts = pluginData.permissibleGAAPRootAbstracts
    ifrsMatch = any(k.startswith(pluginData.ifrsIdentifier) for k in val.modelXbrl.namespaceDocs.keys())
    if ifrsMatch:
        permissibleAbstracts = pluginData.permissibleIFRSRootAbstracts
    for ELR in val.modelXbrl.relationshipSet(parentChild).linkRoleUris:
        relSet = val.modelXbrl.relationshipSet(parentChild, ELR)
        for rootConcept in relSet.rootConcepts:
            if rels := relSet.fromModelObject(rootConcept):
                if rootConcept.qname not in permissibleAbstracts:
                    warnings.append(rels[0])
    if len(warnings) > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.RTS_Annex_II_Par_1_RTS_Annex_IV_par_7.missingRelevantPlaceholder',
            msg=_('A root abstract is being used that is not one of the starting abstracts defined by the regulator.  Review abstracts in use and update to defined abstracts.'),
            modelObject=warnings
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_RTS_Annex_IV_Par_11_G4_2_2_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.RTS_Annex_IV_Par_11_G4-2-2_1: Extension taxonomy MUST NOT define a custom type if a matching
    type is defined by the XBRL 2.1 specification or in the XBRL Data Types Registry.
    Similar to ESEF.RTS.Annex.IV.Par.11.customDataTypeDuplicatingXbrlOrDtrEntry
    """
    errors = []
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for modelDocument, extensionDocumentData in extensionData.extensionDocuments.items():
        for modelType in modelDocument.xmlRootElement.iterdescendants(tag=XbrlConst.qnXsdComplexType.clarkNotation):
            if isinstance(modelType, ModelType) and \
                    modelType.typeDerivedFrom is not None and \
                    modelType.typeDerivedFrom.qname.namespaceURI == XbrlConst.xbrli and \
                    not modelType.particlesList:
                errors.append(modelType)
    if len(errors) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.RTS_Annex_IV_Par_11_G4-2-2_1.customTypeAlreadyDefinedByXbrl',
            msg=_('A custom data type is being used that matches a standard data type from the XBRL Data Type Registry. '
                  'Update to remove duplicate data types and leverage the standard where appropriate.'),
            modelObject=errors
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_RTS_Annex_IV_Par_4_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.RTS_Annex_IV_Par_4_1: Extension elements must not duplicate the existing
    elements from the core taxonomy and be identifiable.
    """
    for name, concepts in val.modelXbrl.nameConcepts.items():
        if len(concepts) < 2:
            continue
        coreConcepts = []
        extensionConcepts = []
        for concept in concepts:
            if pluginData.isExtensionUri(concept.modelDocument.uri, val.modelXbrl):
                extensionConcepts.append(concept)
            else:
                coreConcepts.append(concept)
        if len(coreConcepts) == 0:
            continue
        coreConcept = coreConcepts[0]
        for extensionConcept in extensionConcepts:
            if extensionConcept.balance != coreConcept.balance:
                continue
            if extensionConcept.periodType != coreConcept.periodType:
                continue
            yield Validation.error(
                codes='NL.NL-KVK.RTS_Annex_IV_Par_4_1.extensionElementDuplicatesCoreElement',
                msg=_('An extension element was found that is a duplicate to a core element (%(qname)s). '
                      'Review use of element and update to core or revise extension element.'),
                modelObject=(coreConcept, extensionConcept),
                qname=coreConcept.qname,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_RTS_Annex_IV_Par_4_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.RTS_Annex_IV_Par_4_2: Extension elements must be equipped with an appropriate balance attribute.
    """
    errors = []
    for concept in pluginData.getExtensionConcepts(val.modelXbrl):
        if concept.isMonetary and concept.balance is None:
            errors.append(concept)
    if len(errors) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.RTS_Annex_IV_Par_4_2.monetaryConceptWithoutBalance',
            msg=_('Extension elements must have an appropriate balance attribute.'),
            modelObject=errors
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_RTS_Annex_IV_Par_4_3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.RTS_Annex_IV_Par_4_3: Extension elements must be provided with a standard label in the language corresponding to the language of the annual report.
    """
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    extensionConcepts = extensionData.extensionConcepts
    labelsRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    missingLabels =  []
    missingReportingLabels = []
    noStandardLabels = []
    for concept in extensionConcepts:
        if not concept.label(standardLabel,lang=pluginData.getReportXmlLang(val.modelXbrl),fallbackToQname=False):
            labelRels = labelsRelationshipSet.fromModelObject(concept)
            if len(labelRels) == 0:
                missingLabels.append(concept)
            for labelRel in labelRels:
                label = cast(ModelResource, labelRel.toModelObject)
                if  label.role == XbrlConst.standardLabel:
                    missingReportingLabels.append(concept)
                else:
                    noStandardLabels.append(label)
    message = 'Extension element is missing a standard label or is missing a label in the language of the report. Review to ensure a standard label is defined with at least the language of the report.'
    if len(missingLabels) > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.RTS_Annex_IV_Par_4_3.extensionConceptNoLabel',
            msg=_(message),
            modelObject=missingLabels,
            )
    if len(missingReportingLabels) > 0:
            yield Validation.warning(
                codes='NL.NL-KVK.RTS_Annex_IV_Par_4_3.missingLabelForRoleInReportLanguage',
                msg=_(message),
                modelObject=missingReportingLabels,
            )
    if len(noStandardLabels) > 0:
        yield Validation.warning(
            codes='NL.NL-KVK.RTS_Annex_IV_Par_4_3.extensionConceptNoStandardLabel',
            msg=_(message),
            modelObject=noStandardLabels,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_RTS_Annex_IV_Par_5(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.RTS_Annex_IV_Par_5: Each extension taxonomy element used in tagging
    must be included in at least one presentation and definition linkbase hierarchy.
    """
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    taggedExtensionConcepts = set(extensionData.extensionConcepts) & set(fact.concept for fact in val.modelXbrl.facts)

    def getConceptsInLinkbase(arcroles: frozenset[str], concepts: set[ModelConcept]) -> None:
        for fromModelObject, toRels in val.modelXbrl.relationshipSet(tuple(arcroles)).fromModelObjects().items():
            if isinstance(fromModelObject, ModelConcept):
                concepts.add(fromModelObject)
            for toRel in toRels:
                if isinstance(toRel.toModelObject, ModelConcept):
                    concepts.add(toRel.toModelObject)

    conceptsInDefinition: set[ModelConcept] = set()
    getConceptsInLinkbase(LinkbaseType.DEFINITION.getArcroles(), conceptsInDefinition)
    conceptsMissingFromDefinition = taggedExtensionConcepts - conceptsInDefinition
    if len(conceptsMissingFromDefinition) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.RTS_Annex_IV_Par_5.usableConceptsNotIncludedInDefinitionLink',
            msg=_('Extension elements are missing from definition linkbase. '
                  'Review use of extension elements.'),
            modelObject=conceptsMissingFromDefinition
        )

    conceptsInPresentation: set[ModelConcept] = set()
    getConceptsInLinkbase(LinkbaseType.PRESENTATION.getArcroles(), conceptsInPresentation)
    conceptsMissingFromPresentation = taggedExtensionConcepts - conceptsInPresentation
    if len(conceptsMissingFromPresentation) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.RTS_Annex_IV_Par_5.usableConceptsNotIncludedInPresentationLink',
            msg=_('Extension elements are missing from presentation linkbase. '
                  'Review use of extension elements.'),
            modelObject=conceptsMissingFromPresentation
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_RTS_Annex_IV_Par_6(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.RTS_Annex_IV_Par_6: Each NL-GAAP or IFRS financial statements structure MUST be equipped with
                               a calculation linkbase
    """
    hasCalcLinkbase = False
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for modelDoc, extensionDoc in extensionData.extensionDocuments.items():
        for linkbase in extensionDoc.linkbases:
            if linkbase.linkbaseType == LinkbaseType.CALCULATION:
                hasCalcLinkbase = True
    if not hasCalcLinkbase:
        yield Validation.error(
            codes='NL.NL-KVK.RTS_Annex_IV_Par_6.extensionTaxonomyWrongFilesStructure',
            msg=_('The filing package must include a calculation linkbase.'),
            modelObject=val.modelXbrl.modelDocument
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_RTS_Annex_IV_Par_8_G4_4_5(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.RTS_Annex_IV_Par_8_G4-4-5: Labels and references of the core
    taxonomy elements in extension taxonomies of issuer shall not be replaced.
    """
    extensionData = pluginData.getExtensionData(val.modelXbrl)
    for modelDocument, extensionDoc in extensionData.extensionDocuments.items():
        for linkbase in extensionDoc.linkbases:
            if linkbase.prohibitingLabelElements and \
                    linkbase.prohibitedBaseConcepts:
                if linkbase.linkbaseType == LinkbaseType.LABEL:
                    yield Validation.error(
                        codes='NL.NL-KVK.RTS_Annex_IV_Par_8_G4-4-5.coreTaxonomyLabelModification',
                        msg=_('Standard concept has a modified label from what was defined in the taxonomy. '
                              'Labels from the taxonomy should not be modified.'),
                        modelObject=modelDocument
                    )
                else:
                    # Assumed to be a reference linkbase.
                    # If anything else, we should probably fire an error anyway.
                    yield Validation.error(
                        codes='NL.NL-KVK.RTS_Annex_IV_Par_8_G4-4-5.coreTaxonomyReferenceModification',
                        msg=_('Standard concept has a modified reference from what was defined in the taxonomy. '
                              'References from the taxonomy should not be modified.'),
                        modelObject=modelDocument
                    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=NL_INLINE_GAAP_IFRS_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_RTS_Annex_IV_Par_9_Par_10(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.RTS_Annex_IV_Par_9_par_10: Legal entities MUST ensure that the
    extension taxonomy elements are linked to one or more core taxonomy elements.
    """
    anchorData = pluginData.getAnchorData(val.modelXbrl)
    if len(anchorData.extLineItemsNotAnchored) > 0:
        yield Validation.error(
            codes='NL.NL-KVK.RTS_Annex_IV_Par_9_Par_10.extensionConceptsNotAnchored',
            msg=_('Extension concept found without an anchor. '
                  'Extension concepts, excluding subtotals, are required to be anchored.'),
            modelObject=anchorData.extLineItemsNotAnchored,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_RTS_Art_3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.RTS_Art_3: Legal entities shall file their annual reports in XHTML format
    """
    for modelDocument in val.modelXbrl.urlDocs.values():
        docinfo = modelDocument.xmlRootElement.getroottree().docinfo
        docTypeMatch = DOCTYPE_XHTML_PATTERN.match(docinfo.doctype)
        if not docTypeMatch:
            continue
        if not docTypeMatch.group(1) or docTypeMatch.group(1).lower() == "html":
            yield Validation.error(
                codes='NL.NL-KVK.RTS_Art_3.htmlDoctype',
                msg=_('Doctype SHALL NOT specify html: %(doctype)s'),
                modelObject=val.modelXbrl.modelDocument,
                doctype=docinfo.doctype,
            )
        else:
            yield Validation.warning(
                codes='NL.NL-KVK.RTS_Art_3.xhtmlDoctype',
                msg=_('Doctype implies xhtml DTD validation but '
                      'inline 1.1 requires schema validation: %(doctype)s'),
                modelObject=val.modelXbrl.modelDocument,
                doctype=docinfo.doctype,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
def rule_nl_kvk_RTS_Art_6_a(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    NL-KVK.RTS_Art_6_a: Legal entities shall embed markups in the annual reports
    in XHTML format using the Inline XBRL specifications
    """
    for modelDocument in val.modelXbrl.urlDocs.values():
        if modelDocument.type != ModelDocument.Type.INLINEXBRL:
            continue
        factElements = list(modelDocument.xmlRootElement.iterdescendants(
            modelDocument.ixNStag + "nonNumeric",
            modelDocument.ixNStag + "nonFraction",
            modelDocument.ixNStag + "fraction"
        ))
        if len(factElements) == 0:
            yield Validation.error(
                codes='NL.NL-KVK.RTS_Art_6_a.noInlineXbrlTags',
                msg=_('Annual report is using xhtml extension, but there are no inline mark up tags identified.'),
                modelObject=modelDocument,
            )
