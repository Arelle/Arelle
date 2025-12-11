"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import contextlib
from collections import defaultdict
from datetime import timedelta
from typing import Any, cast, Iterable

import regex

from arelle import ModelDocument, UrlUtil, XbrlConst, XmlUtil
from arelle.HtmlUtil import attrValue
from arelle.LinkbaseType import LinkbaseType
from arelle.ModelDtsObject import ModelConcept, ModelResource
from arelle.ModelInstanceObject import ModelFact, ModelInlineFootnote
from arelle.ModelObject import ModelObject, ModelComment
from arelle.ModelValue import QName
from arelle.PrototypeDtsObject import LocPrototype, ArcPrototype
from arelle.UrlUtil import isHttpUrl, splitDecodeFragment
from arelle.ValidateXbrl import ValidateXbrl
from arelle.ValidateXbrlCalcs import insignificantDigits
from arelle.XbrlConst import qnXbrlScenario, qnXbrldiExplicitMember, xhtmlBaseIdentifier, xmlBaseIdentifier
from arelle.XmlValidate import VALID
from arelle.typing import TypeGetText
from arelle.utils.Contexts import getDuplicateContextGroups
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.Units import getDuplicateUnitGroups
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..Constants import JAPAN_LANGUAGE_CODES, NUMERIC_LABEL_ROLES, domainItemTypeQname, LC3_NAME_PATTERN, HALF_KANA
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..PluginValidationDataExtension import PluginValidationDataExtension


_: TypeGetText

DISALLOWED_LABEL_WHITE_SPACE_CHARACTERS = regex.compile(r'\s{2,}')
XBRLI_IDENTIFIER_PATTERN = regex.compile(r"^[A-Z]\d{5}-\d{3}$")
GFM_CONTEXT_DATE_PATTERN = regex.compile(r"^[12][0-9]{3}-[01][0-9]-[0-3][0-9]$")
GFM_RECOMMENDED_NAMESPACE_PREFIXES = {
    XbrlConst.xbrli: ("xbrli",),
    XbrlConst.xsi: ("xsi",),
    XbrlConst.xsd: ("xs", "xsd",),
    XbrlConst.link: ("link",),
    XbrlConst.xl: ("xl",),
    XbrlConst.xlink: ("xlink",),
    XbrlConst.ref2004: ("ref",),
    XbrlConst.ref2006: ("ref",),
    XbrlConst.xbrldt: ("xbrldt",),
    XbrlConst.xbrldi: ("xbrldi",),
    XbrlConst.ixbrl: ("ix",),
    XbrlConst.ixt: ("ixt",),
    XbrlConst.xhtml: ("xhtml",),
}


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_1_3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.1.3] The URI content of the xlink:href attribute,
    the xsi:schemaLocation attribute and the schemaLocation attribute must
    be relative and contain no forward slashes, or a recognized external
    location of a standard taxonomy schema file, or a "#" followed by a
    shorthand xpointer.
    """
    values = []
    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl):
            continue
        rootElt = modelDocument.xmlRootElement
        for elt in rootElt.iterdescendants(XbrlConst.qnLinkLoc.clarkNotation):
            uri = elt.attrib.get(XbrlConst.qnXlinkHref.clarkNotation)
            values.append((modelDocument, elt, uri))
        for elt in rootElt.iterdescendants(XbrlConst.qnXsdImport.clarkNotation):
            uri = elt.attrib.get('schemaLocation')
            values.append((modelDocument, elt, uri))
        for elt in rootElt.iterdescendants(XbrlConst.qnLinkLinkbase.clarkNotation):
            uri = elt.attrib.get(XbrlConst.qnXsiSchemaLocation.clarkNotation)
            values.append((modelDocument, elt, uri))
        for elt in rootElt.iterdescendants(XbrlConst.qnLinkLinkbaseRef.clarkNotation):
            uri = elt.attrib.get(XbrlConst.qnXlinkHref.clarkNotation)
            values.append((modelDocument, elt, uri))
    for modelDocument, elt, uri in values:
        if uri is None:
            continue
        if uri in val.modelXbrl.urlUnloadableDocs:
            continue  # Already blocked, error fired.
        if not isHttpUrl(uri):
            if '/' not in uri:
                continue  # Valid relative path
        if pluginData.isStandardTaxonomyUrl(uri, val.modelXbrl):
            continue  # Valid external URL
        splitUri, hrefId = splitDecodeFragment(uri)
        if pluginData.isStandardTaxonomyUrl(splitUri, val.modelXbrl):
            if hrefId is None or len(hrefId) == 0:
                continue  # Valid external URL
            if not any(scheme == "element" for scheme, __ in XmlUtil.xpointerSchemes(hrefId)):
                continue  # Valid shorthand xpointer
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.1.3',
            msg=_("The URI content of the xlink:href attribute, the xsi:schemaLocation "
                  "attribute and the schemaLocation attribute must be relative and "
                  "contain no forward slashes, or a recognized external location of "
                  "a standard taxonomy schema file, or a '#' followed by a shorthand "
                  "xpointer. The URI '%(uri)s' is not valid."),
            uri=uri,
            modelObject=elt,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_1_6(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.1.6] Filing must have one or more submitter specific(extension) taxonomies
    """
    if not hasattr(val, 'hasExtensionSchema'):
        val.hasExtensionSchema = False
    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isExtensionUri(modelDocument.uri, val.modelXbrl) and modelDocument.type == ModelDocument.Type.SCHEMA:
            val.hasExtensionSchema = True
            break
    if not val.hasExtensionSchema:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.1.6',
            msg=_("Filing is missing an extension taxonomy."),
            modelObject=val.modelXbrl,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_1_7(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.1.7] Attribute xml:base must not appear in any filing document.
    This check has been updated to check for the xhtml:base attribute in order to account for iXBRL filings.

    Original GFM text: Attribute xml:base must not appear in any filing document.
    """
    baseElements = []
    for rootElt in val.modelXbrl.ixdsHtmlElements:
            for uncast_elt in rootElt.iter():
                elt = cast(Any, uncast_elt)
                if elt.get(xmlBaseIdentifier) is not None:
                    baseElements.append(elt)
                if elt.tag == xhtmlBaseIdentifier:
                    baseElements.append(elt)
    if len(baseElements) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.1.7',
            msg=_("Attribute xml:base must not appear in any filing document."),
            modelObject=baseElements,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.1] The scheme of the entity identifier must be http://disclosure.edinet-fsa.go.jp
    """
    entityIdentifierValues = val.modelXbrl.entityIdentifiersInDocument()
    for entityId in entityIdentifierValues:
        if entityId[0] != 'http://disclosure.edinet-fsa.go.jp':
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.2.1',
                msg=_("The scheme of the entity identifier is: '%(scheme)s' but it must be 'http://disclosure.edinet-fsa.go.jp'."),
                scheme=entityId[0],
                modelObject=entityId,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.2] The entity identifier element must match the following: X00000-000
    """
    entityIdentifierValues = val.modelXbrl.entityIdentifiersInDocument()
    for entityId in entityIdentifierValues:
        if not XBRLI_IDENTIFIER_PATTERN.match(entityId[1]):
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.2.2',
                msg=_("The entity identifier element: '%(element)s' is incorrect. It must take the form of 'X00000-000'."),
                element=entityId[1],
                modelObject=entityId,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.3] All xbrli:identifier elements in an instance must have identical content.
    """
    entityIdentifierValues = val.modelXbrl.entityIdentifiersInDocument()
    if len(entityIdentifierValues) >1:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.3',
            msg=_('All identifier elements must be identical.'),
                modelObject = val.modelXbrl
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_4(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.4] Segment must not be used in the context.
    """
    allContexts = val.modelXbrl.contextsByDocument()
    contextsWithSegments =[]
    for contexts in allContexts.values():
        for context in contexts:
            if context.hasSegment:
                contextsWithSegments.append(context)
    if len(contextsWithSegments) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.4',
            msg=_('Set the scenario element in the context. Do not set the segment element.'),
            modelObject = contextsWithSegments
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_5(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.5] If an xbrli:scenario element appears in a context, then its children
    must be one or more xbrldi:explicitMember elements.
    """
    allContexts = val.modelXbrl.contextsByDocument()
    contextsWithDisallowedScenarioChildren =[]
    for contexts in allContexts.values():
        for context in contexts:
            for elt in context.iterdescendants(qnXbrlScenario.clarkNotation):
                if isinstance(elt, ModelObject):
                    if any(isinstance(child, ModelObject) and child.tag != qnXbrldiExplicitMember.clarkNotation
                           for child in elt.iterchildren()):
                        contextsWithDisallowedScenarioChildren.append(context)
    if len(contextsWithDisallowedScenarioChildren) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.5',
            msg=_('Please delete all child elements other than the xbrldi:explicitMember '
                  'element from the segment element or scenario element.'),
            modelObject = contextsWithDisallowedScenarioChildren
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_7(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.7] An instance must not contain duplicate xbrli:context elements.
    """
    for contexts in getDuplicateContextGroups(val.modelXbrl):
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.7',
            msg=_('Duplicate context. Remove the duplicate.'),
            modelObject = contexts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_8(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.8] Every xbrli:context element must appear in at least one
    contextRef attribute in the same instance.
    """
    unusedContexts = list(set(val.modelXbrl.contexts.values()) - set(val.modelXbrl.contextsInUse))
    unusedContexts.extend(val.modelXbrl.ixdsUnmappedContexts.values())
    unusedContexts.sort(key=lambda x: x.id if x.id is not None else "")
    for context in unusedContexts:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.8',
            msg=_('If you are not using a context, delete it if it is not needed.'),
            modelObject=context
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_9(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.9] The same date must not appear as the content of both an xbrli:startDate and
    an xbrli:endDate in an instance.
    """
    invalidDurationContexts = []
    for contexts in val.modelXbrl.contextsByDocument().values():
        for context in contexts:
            if not context.isInstantPeriod:
                if context.endDatetime and context.startDatetime and context.startDatetime == context.endDatetime - timedelta(days=1):
                    invalidDurationContexts.append(context)
    if len(invalidDurationContexts) > 0:
        for context in invalidDurationContexts:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.2.9',
                msg=_("Set the context's startDate and endDate elements to different dates."),
                modelObject=context
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_10(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.10] Element xbrli:xbrl must not have duplicate child xbrli:unit elements.
    """
    for duplicateUnits in getDuplicateUnitGroups(val.modelXbrl):
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.10',
            msg=_('The unit element contains duplicate content. Please remove the duplicates.'),
            modelObject = duplicateUnits
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_13(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.13] An instance having a fact with non-nil content and the xml:lang
    attribute of value different than the default language must also contain a fact using the same element
    and all other attributes with an xml:lang attribute that represents the default language.
    """
    defaultLang = cast(str, val.disclosureSystem.defaultXmlLang)
    languageFacts: dict[str,dict[QName, set[ModelFact]]] = defaultdict(lambda: defaultdict(set))
    for fact in val.modelXbrl.facts:
        if fact.xValid >= VALID and fact.xmlLang is not None and not fact.isNil:
            languageFacts[fact.xmlLang][fact.qname].add(fact)
    for language, qnames in languageFacts.items():
        if language != defaultLang:
            for qname, facts in qnames.items():
                matchingQnames = languageFacts[defaultLang][qname]
                for fact in facts:
                    if not any(fact.context.isEqualTo(mq.context) for mq in matchingQnames):
                        yield Validation.warning(
                            codes='EDINET.EC5700W.GFM.1.2.13',
                            msg=_('There is an element whose xml:lang attribute is in a language other than Japanese, '
                                  'but there is no element whose xml:lang attribute is in Japanese. Delete the non-Japanese element, '
                                  'or set an element whose xml:lang attribute is in Japanese.'),
                            modelObject = fact
                        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_14(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM.1.2.14] The content of an element with a data type of nonnum:textBlockItemType is not well-formed XML
    (a format that conforms to XML grammar, such as all start and end tags being paired, and the end tag of a nested tag not coming after the end tag of its parent tag, etc.).
    Please modify it so that it is well-formed.
    """
    problematicFacts = pluginData.getProblematicTextBlocks(val.modelXbrl)
    if len(problematicFacts) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.14',
            msg=_('The content of an element with a data type of nonnum:textBlockItemType is not well-formed XML (a format that conforms to XML grammar, '
                  'such as all start and end tags being in pairs, and the end tag of a nested tag not coming after the end tag of its parent tag). '
                  'Correct the content so that it is well-formed.'),
            modelObject = problematicFacts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_16(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.16] Use the decimals attribute instead of the precision attribute.

    Original GFM text: The xbrli:xbrl element must not have any facts with the precision attribute.
    """
    errors = []
    for fact in val.modelXbrl.facts:
        concept = fact.concept
        if concept is None:
            continue
        if not concept.isNumeric:
            continue
        if fact.precision is not None:
            errors.append(fact)
    if len(errors) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.16',
            msg=_("Use the decimals attribute instead of the precision attribute."),
            modelObject=errors,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_22(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.22] In your taxonomy, do not expand the
    xlink:arcrole attribute of the link:footnoteArc element. Modify the value
    of the xlink:arcrole attribute to "http://www.xbrl.org/2003/arcrole/fact-footnote".

    Original GFM text: The xlink:arcrole attribute of a link:footnoteArc element must
    be defined in the XBRL Specification 2.1 or declared in a standard taxonomy schema.
    """
    errors = []
    for elt in pluginData.getFootnoteLinkElements(val.modelXbrl):
        for child in elt:
            if not isinstance(child, (ModelObject, LocPrototype, ArcPrototype)):
                continue
            xlinkType = child.get(XbrlConst.qnXlinkType.clarkNotation)
            if xlinkType == "arc":
                arcrole = child.get(XbrlConst.qnXlinkArcRole.clarkNotation)
                if arcrole != XbrlConst.factFootnote:
                    errors.append(child)
    if len(errors) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.22',
            msg=_("Do not use extension arcroles for the link:footnoteArc element. "
                  "Use the standard 'http://www.xbrl.org/2003/arcrole/fact-footnote' arcrole instead."),
            modelObject=errors,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_25(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.25] Set the date in the period element in the
    following format: YYYY-MM-DD.

    Original GFM text: Dates in period element of the context must comply with
    yyyy-mm-dd format. No time is allowed in the value for dates.
    """
    errors = []
    for context in val.modelXbrl.contexts.values():
        for elt in context.iterdescendants(
            XbrlConst.qnXbrliStartDate.clarkNotation,
            XbrlConst.qnXbrliEndDate.clarkNotation,
            XbrlConst.qnXbrliInstant.clarkNotation
        ):
            dateText = XmlUtil.text(elt)
            if not GFM_CONTEXT_DATE_PATTERN.match(dateText):
                errors.append(elt)
    if len(errors) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.25',
            msg=_("Set the date in the period element in the following "
                  "format: YYYY-MM-DD."),
            modelObject=errors,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_26(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.26] The decimals attribute value must not cause truncation of
    non-zero digits in the fact value. Update the fact value to match the precision of
    the decimals attribute, or update the decimals attribute.

    Original GFM text: The decimals attribute value must not cause non-zero digits in
    the fact value to be changed to zero.
    """
    errors = []
    for fact in val.modelXbrl.facts:
        if (
                fact.context is None or
                fact.concept is None or
                fact.concept.type is None or
                getattr(fact,"xValid", 0) < VALID or
                fact.isNil or
                not fact.isNumeric or
                not fact.decimals or
                fact.decimals == "INF"
        ):
            continue
        try:
            insignificance = insignificantDigits(fact.xValue, decimals=fact.decimals)
            if insignificance is not None:
                errors.append(fact)
        except (ValueError,TypeError):
            errors.append(fact)
    if len(errors) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.26',
            msg=_("The decimals attribute value must not cause truncation of "
                  "non-zero digits in the fact value. Update the fact value to "
                  "match the precision of the decimals attribute, or update the"
                  "decimals attribute."),
            modelObject=errors,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_27(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.27] An instance must not contain unused units.
    """
    # TODO: Consolidate validations involving unused units
    unusedUnits = list(set(val.modelXbrl.units.values()) - set(val.modelXbrl.unitsInUse))
    unusedUnits.extend(val.modelXbrl.ixdsUnmappedUnits.values())
    unusedUnits.sort(key=lambda x: x.hash)
    if len(unusedUnits) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.27',
            msg=_("Delete unused units from the instance."),
            modelObject=unusedUnits
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_28(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.28] The prefix declaration for the namespace is incorrect.
    """
    for doc in val.modelXbrl.urlDocs.values():
        rootElt = doc.xmlRootElement
        for prefix, namespace in rootElt.nsmap.items():
            if prefix is None:
                continue
            if namespace not in GFM_RECOMMENDED_NAMESPACE_PREFIXES:
                continue
            if prefix in GFM_RECOMMENDED_NAMESPACE_PREFIXES[namespace]:
                continue
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.2.28',
                msg=_("The prefix declaration '%(prefix)s' for the namespace '%(namespace)s' "
                      "is incorrect. "
                      "Correct the prefix (%(prefixes)s)."),
                prefix=prefix,
                namespace=namespace,
                prefixes=", ".join(GFM_RECOMMENDED_NAMESPACE_PREFIXES[namespace]),
                modelObject=rootElt
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_2_30(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.2.30] A context must not contain the xbrli:forever element.
    """
    errors = []
    for context in val.modelXbrl.contexts.values():
        for elt in context.iterdescendants(XbrlConst.qnXbrliForever.clarkNotation):
            errors.append(elt)
    if len(errors) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.30',
            msg=_("A context must not contain the xbrli:forever element."),
            modelObject=errors
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.1] The submitter-specific taxonomy contains include elements.
    """
    warnings = []
    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl):
            continue
        rootElt = modelDocument.xmlRootElement
        for elt in rootElt.iterdescendants(XbrlConst.qnXsdInclude.clarkNotation):
            warnings.append(elt)
    if len(warnings) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.3.1',
            msg=_("The submitter-specific taxonomy contains include elements."),
            modelObject=warnings
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.2] The schemaLocation attribute of the xsd:import element specifying the EDINET taxonomy does not point to a valid location.

    GFM-1.3.2:  If an xsd:import element has a namespace attribute equal to a standard taxonomy
    schema, then its schemaLocation attribute must be the standard taxonomy assigned
    to that namespace.
    """
    for document in val.modelXbrl.urlDocs.values():
        if not pluginData.isExtensionUri(document.uri, val.modelXbrl) or not document.type == ModelDocument.Type.SCHEMA:
            continue
        for refDoc in document.referencesDocument.values():
            if 'import' not in refDoc.referenceTypes:
                continue
            namespace = refDoc.referringModelObject.attrib.get('namespace')
            schemaLocation = refDoc.referringModelObject.attrib.get('schemaLocation')
            if not namespace or not schemaLocation:
                continue
            expectedXSDLocationSet = val.disclosureSystem.standardTaxonomiesDict.get(namespace)
            if expectedXSDLocationSet is not None and schemaLocation not in expectedXSDLocationSet:
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.3.2',
                    msg=_("The schemaLocation attribute of the xsd:import element specifying the EDINET taxonomy does not point to a valid location. "
                          "The schemaLocation attribute value '%(schemaLocation)s'."),
                    schemaLocation = schemaLocation,
                    modelObject = refDoc.referringModelObject
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_8(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.8] TThe submitter-specific taxonomy has an embedded linkbase.
    """
    embeddedElements = []
    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl):
            continue
        rootElt = modelDocument.xmlRootElement
        for elt in rootElt.iterdescendants(XbrlConst.qnLinkLinkbaseRef.clarkNotation):
            if elt.attrib.get(XbrlConst.qnXlinkType.clarkNotation) in ('extended', 'arc', 'resource', 'locator'):
                embeddedElements.append(elt)
    if len(embeddedElements) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.3.8',
            msg=_("The submitter-specific taxonomy has an embedded linkbase."),
            modelObject=embeddedElements
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_10(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.10] Remove the duplicate link:roleType element.
    """
    for modelRoleTypes in val.modelXbrl.roleTypes.values():
        if modelRoleTypes and len(modelRoleTypes) > 1:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.3.10',
                msg=_("Remove the duplicate link:roleType element. Duplicate roleURI: %(roleURI)s"),
                roleURI=modelRoleTypes[0].roleURI,
                modelObject=modelRoleTypes
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_11(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.11] The usedOn attribute of the extended link role should be set to include all of link:presentationLink, link:calculationLink, and link:definitionLink.
    """
    requiredUsedOns = {XbrlConst.qnLinkPresentationLink,
                       XbrlConst.qnLinkCalculationLink,
                       XbrlConst.qnLinkDefinitionLink}
    for modelRoleTypes in val.modelXbrl.roleTypes.values():
        if len(modelRoleTypes) > 0:
            modelRoleType = modelRoleTypes[0]
            usedOns = modelRoleType.usedOns
            if not usedOns.isdisjoint(requiredUsedOns) and len(requiredUsedOns - usedOns) > 0:
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.3.11',
                    msg=_("The usedOn attribute of the extended link role should be set to include all of link:presentationLink, link:calculationLink, and link:definitionLink. "
                          "Extended link role roleURI: %(roleURI)s is missing %(usedOn)s."),
                    roleURI=modelRoleType.roleURI,
                    modelObject=modelRoleType
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_13(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.13]  Remove any leading or trailing XML whitespace and newline
    characters from the "link:definition" of your extended link role.
    """
    for modelRoleTypes in val.modelXbrl.roleTypes.values():
        if len(modelRoleTypes) > 0:
            modelRoleType = modelRoleTypes[0]
            if (
                    modelRoleType.definition and modelRoleType.definitionNotStripped
                    and modelRoleType.definition != modelRoleType.definitionNotStripped
            ):
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.3.13',
                    msg=_("Remove any leading or trailing XML whitespace and newline characters from "
                          "the `link:definition` of your extended link role. Definition: %(definition)s"),
                    definition=modelRoleTypes[0].definitionNotStripped,
                    modelObject=modelRoleTypes[0]
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_16(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.16] Remove the duplicate link:arcroleType element.
    """
    for modelArcRoleTypes in val.modelXbrl.arcroleTypes.values():
        if len(modelArcRoleTypes) > 1:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.3.16',
                msg=_("Remove the duplicate link:arcroleType element. Duplicate arcroleURI: %(arcroleURI)s"),
                arcroleURI=modelArcRoleTypes[0].arcroleURI,
                modelObject=modelArcRoleTypes
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_17(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.17] Add a link:definition to the link:arcroleType element.
    """
    for modelArcRoleTypes in val.modelXbrl.arcroleTypes.values():
        modelArcRoleType = modelArcRoleTypes[0]
        if not modelArcRoleType.definition:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.3.17',
                msg=_("Add a link:definition to the link:arcroleType element. ArcroleURI: %(arcroleURI)s"),
                arcroleURI=modelArcRoleType.arcroleURI,
                modelObject=modelArcRoleType
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_18(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.18] The submitter's taxonomy contains an element whose name matches an element in the EDINET taxonomy.
    Modify the element name so that it does not match the EDINET taxonomy, or use the element in the EDINET taxonomy and delete the
    element added in the submitter's taxonomy.
    """
    for extensionConcept in pluginData.getExtensionConcepts(val.modelXbrl):
        name = extensionConcept.get("name")
        if name is not None:
            concepts = val.modelXbrl.nameConcepts.get(name, [])
            for concept in concepts:
                if not pluginData.isExtensionUri(concept.document.uri, val.modelXbrl):
                    yield Validation.warning(
                        codes='EDINET.EC5700W.GFM.1.3.18',
                        msg=_("Your extension taxonomy contains an element, %(concept)s, which has the same name as an element "
                              "in the base taxonomy, %(standardConcept)s.  Please ensure that this extension is appropriate and "
                              "if so, please change the extension concept."),
                        concept=name,
                        standardConcept=concept
                    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_19(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.19] The id attribute of the element defined in the submitter-specific taxonomy
    should be set in the following format:{namespace prefix}_{element name}.
    """
    improperlyFormattedIds = set()
    for concept in pluginData.getExtensionConcepts(val.modelXbrl):
        prefix = concept.qname.prefix or ""
        name = concept.qname.localName
        requiredId = f"{prefix}_{name}"
        if concept.id != requiredId or not prefix:
            improperlyFormattedIds.add(concept)
    if len(improperlyFormattedIds) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.3.19',
            msg=_("The id attribute of the element defined in the submitter-specific taxonomy should be set in the following format: {namespace prefix}_{element name}"),
            modelObject=improperlyFormattedIds
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_20(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.20] Set the nillable attribute value to "true".

    GFM 1.3.20 The nillable attribute value of an xsd:element must equal "true".
    """
    nonNillableElements = set()
    for concept in val.modelXbrl.qnameConcepts.values():
        if concept.namespaceURI == XbrlConst.xsd:
            if concept.get("nillable") == "false":
                nonNillableElements.add(concept)
    if len(nonNillableElements) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.3.20',
            msg=_("Set the nillable attribute value to 'true'."),
            modelObject=nonNillableElements
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_21(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.21] Remove the tuple definition.
    """
    tupleConcepts = [
        concept for concept in pluginData.getExtensionConcepts(val.modelXbrl)
        if concept.isTuple
    ]
    if len(tupleConcepts) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.3.21',
            msg=_("Remove the tuple definition."),
            modelObject=tupleConcepts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_22(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.22] Do not set the xbrldt:typedDomainRef attribute on elements defined in submitter-specific taxonomies.
    """
    typedDomainConcepts = [
        concept for concept in pluginData.getExtensionConcepts(val.modelXbrl)
        if concept.isTypedDimension
    ]

    if len(typedDomainConcepts) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.3.22',
            msg=_("Do not set the xbrldt:typedDomainRef attribute on elements defined in submitter-specific taxonomies."),
            modelObject=typedDomainConcepts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_23(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.23] Set the periodType attribute to "duration".

    GFM 1.3.23 If the abstract attribute of xsd:element is "true", then the
    xbrli:periodType attribute must be "duration".
    """
    instantAbstractElements = set()
    for concept in val.modelXbrl.qnameConcepts.values():
        if concept.abstract == "true" and  concept.periodType == "instant":
            instantAbstractElements.add(concept)
    if len(instantAbstractElements) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.3.23',
            msg=_("Set the periodType attribute to 'duration'."),
            modelObject=instantAbstractElements
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_25(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.25] Correct the element name so that it does not end with "Axis", or correct the
    substitutionGroup to "xbrldt:dimensionItem".

    GFM 1.3.25: The xsd:element substitutionGroup attribute must equal "xbrldt:dimensionItem" if
    and only if the name attribute ends with "Axis".
    """
    for concept in pluginData.getExtensionConcepts(val.modelXbrl):
        if concept.qname.localName.endswith("Axis") != (concept.substitutionGroupQname == XbrlConst.qnXbrldtDimensionItem):
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.3.25',
                msg=_("Modify the element name, '%(conceptName)s', so that it does not end with 'Axis', or modify the substitutionGroup to 'xbrldt:dimensionItem'."),
                conceptName=concept.qname.localName,
                modelObject=concept,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_26(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.26] Correct the element name so that it does not end with "Table", or correct the
    substitutionGroup to "xbrldt:hypercubeItem".

    GFM 1.3.26: The xsd:element name attribute must ends with "Table" if and only if
    substitutionGroup attribute equals "xbrldt:hypercubeItem".
    """
    for concept in pluginData.getExtensionConcepts(val.modelXbrl):
        if concept.qname.localName.endswith("Table") != (concept.substitutionGroupQname == XbrlConst.qnXbrldtHypercubeItem):
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.3.26',
                msg=_("The substitution group 'xbrldt:hypercubeItem' is only allowed with an element name that ends with 'Table'."
                      "Please change %(conceptName)s or change the substitutionGroup."),
                conceptName=concept.qname.localName,
                modelObject=concept
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_28(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.28] If the element name of an element extended by a submitter-specific taxonomy ends with "LineItems",
    set the abstract attribute to "true".
    """
    for concept in pluginData.getExtensionConcepts(val.modelXbrl):
        if concept.qname.localName.endswith("LineItems") and not concept.isAbstract:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.3.28',
                msg=_("If the element name of an element extended by a submitter-specific taxonomy ends with 'LineItems', "
                      "set the abstract attribute to 'true'. For the element, '%(conceptName)s', the abstract attribute is 'false'."),
                conceptName=concept.qname.localName,
                modelObject=concept
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_29(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.29] If the element name of an element extended by the submitter-specific taxonomy ends with
    "Domain" or "Member", please set the type attribute to "nonnum:domainItemType".

    GFM 1.3.29: The xsd:element name attribute must end with "Domain" or "Member" if and only
    if the type attribute equals "nonnum:domainItemType".
    """
    for concept in pluginData.getExtensionConcepts(val.modelXbrl):
        isConceptDomain = concept.type.isDomainItemType if concept.type is not None else False
        if ((concept.qname.localName.endswith("Domain") or concept.qname.localName.endswith("Member")) != isConceptDomain):
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.3.29',
                msg=_("The type 'us-types:domainItemType' is only allowed with an element name that ends with 'Domain' or 'Member'. "
                      "Please change %(conceptName)s or change the type."),
                conceptName=concept.qname.localName,
                modelObject=concept
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_30(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.30] Set the periodType attribute to "duration".

    GFM 1.3.30 If xsd:element type attribute equals "nonnum:domainItemType" then
    the xbrli:periodType attribute must equal "duration".
    """
    instantDomainElements = set()
    for concept in val.modelXbrl.qnameConcepts.values():
        if concept.type is not None and concept.type.isDomainItemType and concept.periodType == "instant":
            instantDomainElements.add(concept)
    if len(instantDomainElements) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.3.30',
            msg=_("Set the periodType attribute to 'duration'."),
            modelObject=instantDomainElements
        )

@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_3_31(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.3.31] Set the abstract attribute to "true".

    GFM 1.3.31: If xsd:element type attribute equals "nonnum:domainItemType" then
    the abstract attribute must equal to "true".
    """
    nonAbstractDomainElements = set()
    for concept in val.modelXbrl.qnameConcepts.values():
        if concept.type is not None and concept.type.isDomainItemType and concept.abstract != "true":
            nonAbstractDomainElements.add(concept)
    if len(nonAbstractDomainElements) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.3.31',
            msg=_("Set the abstract attribute to 'true'."),
            modelObject=nonAbstractDomainElements
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_4_4(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.4.4] If the type attribute is "extended" or "resource", set the xlink:role attribute to the extended link role.

    GFM 1.4.4: The xlink:role attribute of an element with a type="extended" attribute or a
    type="resource" attribute must be present and must not be empty.
    """
    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl):
            continue
        rootElt = modelDocument.xmlRootElement
        ns = {'xlink': 'http://www.w3.org/1999/xlink'}
        for elt in rootElt.xpath('//*[@xlink:type="extended" or @xlink:type="resource"]', namespaces=ns):
            xlinkRole = elt.get(XbrlConst.qnXlinkRole.clarkNotation)
            if not xlinkRole:
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.4.4',
                    msg=_("If the type attribute is 'extended' or 'resource', set the xlink:role attribute to the extended link role."
                            "%(element)s is missing an xlink:role"),
                            modelObject=elt, element=elt.qname
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_4_6(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.4.6] Please correct the value of the link:arcroleRef attribute to
    one specified in the XBRL 2.1 specification or the EDINET taxonomy.
    GFM 1.4.6: The text preceding a sharp sign "#" in an xlink:href attribute of link:arcroleRef must
    be a standard taxonomy or in a file recognised in the disclosure system.
    """

    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl):
            continue
        rootElt = modelDocument.xmlRootElement
        for elt in rootElt.iter(XbrlConst.qnLinkArcroleRef.clarkNotation):
            refUri = elt.get("arcroleURI")
            hrefAttr = elt.get(XbrlConst.qnXlinkHref.clarkNotation)
            hrefUri, hrefId = UrlUtil.splitDecodeFragment(hrefAttr)
            if hrefUri not in val.disclosureSystem.standardTaxonomiesDict:
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.4.6',
                    msg=_("Please correct the value of the link:arcroleRef attribute to one specified in the XBRL 2.1 specification or the EDINET taxonomy."
                          " link:arcroleRef: %(xlinkHref)s, arcrole: %(refURI)s,"),
                    modelObject=elt,
                    refURI=refUri,
                    xlinkHref=hrefUri
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_4_8(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.4.8] Correct the priority attribute value so that it is less than 10.
    """

    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl):
            continue
        rootElt = modelDocument.xmlRootElement
        ns = {'xlink': 'http://www.w3.org/1999/xlink'}
        for elt in rootElt.xpath('//*[@xlink:type="arc"][@priority]', namespaces=ns):
            priority = elt.get("priority")
            with contextlib.suppress(ValueError, TypeError):
                if int(priority) >= 10:
                    yield Validation.warning(
                        codes='EDINET.EC5700W.GFM.1.4.8',
                        msg=_("Correct the priority attribute value so that it is less than 10. Arc element: %(arcName)s, priority: %(priority)s"),
                        arcName=elt.qname,
                        modelObject=elt,
                        priority=priority,
                    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_5_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.5.1] An element used in a fact or xbrldi:explicitMember in an instance must have a Japanese
                                language standard label in the DTS of that instance.
    """
    usedConcepts = pluginData.getUsedConcepts(val.modelXbrl)
    labelRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    if labelRelationshipSet is None:
        return
    for concept in usedConcepts:
        labelRels = labelRelationshipSet.fromModelObject(concept)
        labelExists = False
        for rel in labelRels:
            label = rel.toModelObject
            if (label is not None and
                    label.role == XbrlConst.standardLabel and
                    label.xmlLang in JAPAN_LANGUAGE_CODES):
                labelExists = True
                break
        if not labelExists:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.5.1',
                msg=_("The used concept of '%(concept)s' is missing a standard label in Japanese"),
                concept=concept.qname.localName,
                modelObject=concept
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_5_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.5.2] An element used in a fact or xbrldi:explicitMember in an instance must have at most one
                                label for any combination of the xlink:role attribute and the xml:lang attribute in the
                                DTS of that instance.
    """
    usedConcepts = pluginData.getUsedConcepts(val.modelXbrl)
    labelRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    if labelRelationshipSet is None:
        return
    for concept in usedConcepts:
        labelRels = labelRelationshipSet.fromModelObject(concept)
        labelsByRoleAndLang = defaultdict(list)
        for rel in labelRels:
            label = rel.toModelObject
            if label is None:
                continue
            labelsByRoleAndLang[(label.role, label.xmlLang)].append(label)
        warningLabels = []
        for key, labels in labelsByRoleAndLang.items():
            if len(labels) > 1:
                warningLabels.append(key)
        if len(warningLabels) > 0:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.5.2',
                msg=_("The used concept of '%(concept)s' has more than one label for the given role/lang pairs: %(pairs)s."),
                concept=concept.qname.localName,
                pairs=warningLabels,
                modelObject=concept
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_5_3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.5.3] If an element used in an instance is assigned a label in the DTS whose xml:lang
                                attribute does not reflect the default language, then the DTS must also contain a
                                link:label for the same element and all other attributes with an xml:lang attribute
                                reflecting the default language.
    """
    usedConcepts = pluginData.getUsedConcepts(val.modelXbrl)
    labelRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    if labelRelationshipSet is None:
        return
    for concept in usedConcepts:
        labelRels = labelRelationshipSet.fromModelObject(concept)
        labelsByRole = defaultdict(list)
        for rel in labelRels:
            label = rel.toModelObject
            if label is None:
                continue
            labelsByRole[label.role].append(label)
        warningRoles = []
        for role, labels in labelsByRole.items():
            if len([label for label in labels if label.xmlLang in JAPAN_LANGUAGE_CODES]) == 0:
                warningRoles.append(role)
        if len(warningRoles) > 0:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.5.3',
                msg=_("The used concept of '%(concept)s' is missing a label in Japanese in the following roles: %(roles)s."),
                concept=concept.qname.localName,
                roles=warningRoles,
                modelObject=concept
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_5_5(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.5.5] A label linkbase must not have a documentation label for an element defined in a
                                standard taxonomy.
    """
    labelRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    if labelRelationshipSet is None:
        return
    for concept in val.modelXbrl.qnameConcepts.values():
        if concept.namespaceURI is not None and not pluginData.isStandardTaxonomyUrl(concept.namespaceURI, val.modelXbrl):
            continue
        labelRels = labelRelationshipSet.fromModelObject(concept)
        for rel in labelRels:
            label = rel.toModelObject
            if (label is not None and
                    not pluginData.isStandardTaxonomyUrl(label.modelDocument.uri, val.modelXbrl) and
                    label.role == XbrlConst.documentationLabel):
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.5.5',
                    msg=_("The standard concept of '%(concept)s' must not have a documentation label defined."),
                    concept=concept.qname.localName,
                    modelObject=label
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_5_6(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.5.6] The length of a label must be less than 511 characters unless its role is documentation.
    """
    labelRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    if labelRelationshipSet is None:
        return
    for concept in val.modelXbrl.qnameConcepts.values():
        labelRels = labelRelationshipSet.fromModelObject(concept)
        for rel in labelRels:
            label = rel.toModelObject
            if (label is not None and
                    label.role != XbrlConst.documentationLabel and
                    label.viewText() is not None and
                    len(label.viewText()) >= 511):
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.5.6',
                    msg=_("The concept of '%(concept)s' has a label classified as '%(role)s' that is greater than or equal to 511 characters: %(label)s"),
                    concept=concept.qname,
                    role=label.role,
                    label=label.viewText(),
                    modelObject=label
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_5_7(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.5.7] A label cannot contain the "<" character or consecutive white space characters including
                    but not limited to: space, carriage return, line feed or tab.
    """
    labelRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    if labelRelationshipSet is None:
        return
    for concept in val.modelXbrl.qnameConcepts.values():
        labelRels = labelRelationshipSet.fromModelObject(concept)
        for rel in labelRels:
            label = rel.toModelObject
            if label is not None and label.role != XbrlConst.documentationLabel and label.textValue is not None:
                if '<' in label.textValue:
                    yield Validation.warning(
                        codes='EDINET.EC5700W.GFM.1.5.7',
                        msg=_("The concept of '%(concept)s' has a label classified as '%(role)s that contains the '<' character: %(label)s"),
                        concept=concept.qname,
                        role=label.role,
                        label=label.textValue,
                        modelObject=label
                    )
                elif DISALLOWED_LABEL_WHITE_SPACE_CHARACTERS.search(label.textValue):
                    yield Validation.warning(
                        codes='EDINET.EC5700W.GFM.1.5.7',
                        msg=_("The concept of '%(concept)s' has a label classified as '%(role)s' that contains consecutive white space characters: %(label)s"),
                        concept=concept.qname,
                        role=label.role,
                        label=label.textValue,
                        modelObject=label
                    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_5_8(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.5.8] A label should not begin or end with a white space character
    """
    labelRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    if labelRelationshipSet is None:
        return
    for concept in val.modelXbrl.qnameConcepts.values():
        labelRels = labelRelationshipSet.fromModelObject(concept)
        for rel in labelRels:
            label = rel.toModelObject
            if label is not None and label.textValue is not None and label.textValue != label.textValue.strip():
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.5.8',
                    msg=_("The concept of '%(concept)s' has a label that contains disallowed white space either at the begining or the end: '%(label)s'"),
                    concept=concept.qname,
                    label=label.textValue,
                    modelObject=label
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_5_10(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.5.10] A non-numeric concept should not have a label with a numeric role
    """
    labelRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    if labelRelationshipSet is None:
        return
    for concept in val.modelXbrl.qnameConcepts.values():
        if concept.isNumeric:
            continue
        labelRels = labelRelationshipSet.fromModelObject(concept)
        for rel in labelRels:
            label = rel.toModelObject
            if (label is not None and
                    not pluginData.isStandardTaxonomyUrl(label.modelDocument.uri, val.modelXbrl) and
                    label.role in NUMERIC_LABEL_ROLES):
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.5.10',
                    msg=_("The non-numeric concept of '%(concept)s' has a label with a numeric role of '%(labelrole)s'"),
                    concept=concept.qname,
                    labelrole=label.role,
                    modelObject=label
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_6_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.6.1] All presentation relationships must have an order attribute
    """
    presentationRelationshipSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.PRESENTATION.getArcroles()))
    if presentationRelationshipSet is None:
        return
    for rel in presentationRelationshipSet.modelRelationships:
        if not rel.arcElement.get("order"):
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.6.1',
                msg=_("The presentation relationship is missing the order attribute"),
                modelObject=rel
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_6_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.6.2] Presentation relationships must have unique order attributes
    """
    presentationRelationshipSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.PRESENTATION.getArcroles()))
    if presentationRelationshipSet is None:
        return
    for modelObject, rels in presentationRelationshipSet.fromModelObjects().items():
        if len(rels) <= 1:
            continue
        relsByOrder = defaultdict(list)
        for rel in rels:
            order = rel.arcElement.get("order")
            if order is not None:
                relsByOrder[(order, rel.linkrole)].append(rel)
        for key, orderRels in relsByOrder.items():
            if len(orderRels) > 1:
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.6.2',
                    msg=_("The presentation relationships have the same order attribute: '%(order)s'"),
                    order=key[0],
                    modelObject=orderRels
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_6_5(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.6.5] If an element used in an instance is the target in the instance DTS of more than one
                                effective presentation arc in a base set with the same source element, then the
                                presentation arcs must have distinct values of the preferredLabel attribute.
    """
    presentationRelationshipSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.PRESENTATION.getArcroles()))
    if presentationRelationshipSet is None:
        return
    for modelObject, rels in presentationRelationshipSet.toModelObjects().items():
        if len(rels) <= 1:
            continue
        relsByFrom = defaultdict(list)
        for rel in rels:
            relsByFrom[(rel.fromModelObject, rel.preferredLabel, rel.linkrole)].append(rel)
        for key, fromRels in relsByFrom.items():
            if len(fromRels) > 1:
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.6.5',
                    msg=_("The presentation relationships must have distinct values of the preferredLabel attribute "
                          "when they have the same source and target elements"),
                    modelObject=fromRels
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_7_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.7.1] All calculation relationships must have an order attribute
    """
    calculationRelationshipSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.CALCULATION.getArcroles()))
    if calculationRelationshipSet is None:
        return
    for rel in calculationRelationshipSet.modelRelationships:
        if not rel.arcElement.get("order"):
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.7.1',
                msg=_("The calculation relationship is missing the order attribute"),
                modelObject=rel
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_7_2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.7.2] All calculation relationships must have a weight of either 1 or -1
    """
    calculationRelationshipSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.CALCULATION.getArcroles()))
    if calculationRelationshipSet is None:
        return
    for rel in calculationRelationshipSet.modelRelationships:
        if rel.weight not in [1, -1]:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.7.2',
                msg=_("The calculation relationship must have a weight of 1 or -1, actual weight: '%(weight)s'"),
                weight=rel.weight,
                modelObject=rel
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_7_3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.7.3] The concepts participating in a calculation relationship must have the same period type
    """
    calculationRelationshipSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.CALCULATION.getArcroles()))
    if calculationRelationshipSet is None:
        return
    for rel in calculationRelationshipSet.modelRelationships:
        fromConcept = rel.fromModelObject
        toConcept = rel.toModelObject
        if fromConcept is not None and toConcept is not None and fromConcept.periodType != toConcept.periodType:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.7.3',
                msg=_("The concepts participating in a calculation relationship must have the same period types. "
                      "The concept of '%(concept1)s' has a period type of '%(concept1PeriodType)s' and the concept "
                      "of '%(concept2)s' has a period type of '%(concept2PeriodType)s'"),
                concept1=fromConcept.qname,
                concept1PeriodType=fromConcept.periodType,
                concept2=toConcept.qname,
                concept2PeriodType=toConcept.periodType,
                modelObject=rel
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_7_5(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.7.5] The source and target of a calculation relationship must appear in either:
                                1) a presentation relationship within each other
                                2) two presentation relationships with any other elements that also share the same ELR.
    """
    calculationRelationshipSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.CALCULATION.getArcroles()))
    if calculationRelationshipSet is None:
        return
    for rel in calculationRelationshipSet.modelRelationships:
        conceptsMissingRels = []
        concepts = []
        for concept in [rel.fromModelObject, rel.toModelObject]:
            if concept is not None:
                conceptFacts = val.modelXbrl.factsByQname.get(concept.qname, set())
                if len([fact for fact in conceptFacts if fact.xValid >= VALID and not fact.isNil]) > 0:
                    concepts.append(concept)
        if len(concepts) > 0:
            presentationRelationshipSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.PRESENTATION.getArcroles()), rel.linkrole)
            if presentationRelationshipSet is None:
                conceptsMissingRels.extend(concepts)
            else:
                for concept in concepts:
                    if (len(presentationRelationshipSet.fromModelObject(concept)) == 0 and
                            len(presentationRelationshipSet.toModelObject(concept)) == 0):
                        conceptsMissingRels.append(concept)
            if len(conceptsMissingRels) > 0:
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.7.5',
                    msg=_("The concepts participating in a calculation relationship must also participate in a presentation "
                          "relationship within the same extended link role. The concept(s) of '%(concepts)s' "
                          "do not appear in a presentation relationship within the extended link role of '%(elr)s'."),
                    concepts=' and '.join([concept.qname.localName for concept in conceptsMissingRels]),
                    elr=rel.linkrole,
                    modelObject=rel
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_7_6(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.7.6] Calculation relationships must have unique order attributes
    """
    calculationRelationshipSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.CALCULATION.getArcroles()))
    if calculationRelationshipSet is None:
        return
    for modelObject, rels in calculationRelationshipSet.fromModelObjects().items():
        if len(rels) <= 1:
            continue
        relsByOrder = defaultdict(list)
        for rel in rels:
            order = rel.arcElement.get("order")
            if order is not None:
                relsByOrder[(order, rel.linkrole)].append(rel)
        for key, orderRels in relsByOrder.items():
            if len(orderRels) > 1:
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.7.6',
                    msg=_("The calculation relationships have the same order attribute: '%(order)s'"),
                    order=key[0],
                    modelObject=orderRels
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_8_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.8.1] All definition relationships must have an order attribute
    """
    definitionRelationshipSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.DEFINITION.getArcroles()))
    if definitionRelationshipSet is None:
        return
    for rel in definitionRelationshipSet.modelRelationships:
        if not rel.arcElement.get("order"):
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.8.1',
                msg=_("The definition relationship is missing the order attribute"),
                modelObject=rel
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_8_3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.8.3] The target of an effective arc with an xlink:arcrole attribute equal to
                                "http://xbrl.org/int/dim/arcrole/dimension-domain" or
                                "http://xbrl.org/int/arcrole/dimension-default" must be of type
                                nonnum:domainItemType.
    """
    dimensionRelationshipSet = val.modelXbrl.relationshipSet((XbrlConst.dimensionDomain, XbrlConst.dimensionDefault))
    if dimensionRelationshipSet is None:
        return
    for rel in dimensionRelationshipSet.modelRelationships:
        toConcept = rel.toModelObject
        if toConcept is not None and toConcept.typeQname != domainItemTypeQname:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.8.3',
                msg=_("The definition relationship target concept of '%(concept)s' has a type of '%(type)s' instead of 'nonnum:domainItemType'."),
                concept=toConcept.qname,
                type=toConcept.typeQname,
                modelObject=rel
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_8_5(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.8.5] Each ELR can have at most one effective arc with the role of http://xbrl.org/int/dim/arcrole/all.
    """
    dimensionAllRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.all)
    if dimensionAllRelationshipSet is None:
        return
    relsByLinkrole = defaultdict(list)
    for rel in dimensionAllRelationshipSet.modelRelationships:
        relsByLinkrole[rel.linkrole].append(rel)
    for linkrole, rels in relsByLinkrole.items():
        if len(rels) > 1:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.8.5',
                msg=_("The extended link role of '%(elr)s' has more than one effective arc with the role of 'http://xbrl.org/int/dim/arcrole/all'"),
                elr=linkrole,
                modelObject=rels
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_8_9(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.8.9] Each ELR can have at most one effective arc with the role of http://xbrl.org/int/dim/arcrole/all.

    GFM 1.8.9:  If the value of attribute xbrldt:targetRole on an effective definition relationship is
    not empty, then that relationship must have at least one effective consecutive
    relationship (as defined by the XBRL Dimensions 1.0 specification).
    """
    drsELRs = set()
    for baseSetKey, baseSetModelLinks  in val.modelXbrl.baseSets.items():
        arcrole, elr, linkqname, arcqname = baseSetKey
        if elr and linkqname and arcqname and not arcrole.startswith("XBRL-"):
            if arcrole == XbrlConst.all or arcrole == XbrlConst.notAll:
                drsELRs.add(elr)
    for ELR in drsELRs:
        domainMemberRelationshipSet = val.modelXbrl.relationshipSet( XbrlConst.domainMember, ELR)
        primaryItems = set()
        for hypercubeArcrole in (XbrlConst.all, XbrlConst.notAll):
            hypercubeRelationships = val.modelXbrl.relationshipSet(
                hypercubeArcrole, ELR).fromModelObjects()
            for hypercubeRels in hypercubeRelationships.values():
                for hypercubeRel in hypercubeRels:
                    hypercube = hypercubeRel.toModelObject
                    fromConcept = hypercubeRel.fromModelObject
                    primaryItems.add(fromConcept)
                    toConcept = hypercubeRel.toModelObject
                    dimELR = hypercubeRel.targetRole
                    dimTargetRequired = (dimELR is not None)
                    if not dimELR:
                        dimELR = elr
                    hypercubeDimRels = val.modelXbrl.relationshipSet(XbrlConst.hypercubeDimension, dimELR).fromModelObject(toConcept)
                    if dimTargetRequired and len(hypercubeDimRels) == 0:
                        yield Validation.warning(
                            codes='EDINET.EC5700W.GFM.1.8.9',
                            msg=_("Add the arc related to the xbrldt:targetRole attribute or remove the attribute. "
                                  "Arcrole %(arcroleURI)s from %(fromConcept)s to %(toConcept)s."),
                            modelObject=hypercubeRel,
                            arcroleURI=hypercubeRel.arcrole,
                            fromConcept=fromConcept.qname,
                            toConcept=toConcept.qname,
                        )
                    for hypercubeDimRel in hypercubeDimRels:
                        dim = hypercubeDimRel.toModelObject
                        if not isinstance(dim, ModelConcept):
                            continue
                        domELR = hypercubeDimRel.targetRole
                        domTargetRequired = (domELR is not None)
                        if not domELR and dim.isExplicitDimension:
                            domELR = dimELR
                        dimDomRels = val.modelXbrl.relationshipSet(XbrlConst.dimensionDomain, domELR).fromModelObject(dim)
                        if domTargetRequired and len(dimDomRels) == 0:
                            yield Validation.warning(
                                codes='EDINET.EC5700W.GFM.1.8.9',
                                msg=_("Add the arc related to the xbrldt:targetRole attribute or remove the attribute. "
                                      "Arcrole %(arcroleURI)s from %(fromConcept)s to %(toConcept)s."),
                                modelObject=hypercubeDimRel,
                                arcroleURI=hypercubeRel.arcrole,
                                fromConcept=hypercube.qname,
                                toConcept=dim.qname,
                                )
                    fromRelationships = domainMemberRelationshipSet.fromModelObjects()
                    for relFrom, rels in fromRelationships.items():
                        for rel in rels:
                            fromMbr = rel.fromModelObject
                            toMbr = rel.toModelObject
                            toELR = rel.targetRole
                            if isinstance(toMbr, ModelConcept) and toELR and len(
                                    val.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(toMbr)) == 0:
                                        yield Validation.warning(
                                            codes='EDINET.EC5700W.GFM.1.8.9',
                                            msg=_("Add the arc related to the xbrldt:targetRole attribute or remove the attribute. "
                                                      "Arcrole %(arcroleURI)s from %(fromConcept)s to %(toConcept)s."),
                                            modelObject=rel,
                                            arcroleURI=hypercubeRel.arcrole,
                                            fromConcept=toMbr.qname,
                                            toConcept=fromMbr.qname,
                                        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_8_10(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.8.10] Definition relationships must have unique order attributes
    """
    definitionRelationshipSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.DEFINITION.getArcroles()))
    if definitionRelationshipSet is None:
        return
    for modelObject, rels in definitionRelationshipSet.loadModelRelationshipsFrom().items():
        if len(rels) <= 1:
            continue
        relsByOrder = defaultdict(list)
        for rel in rels:
            order = rel.arcElement.get("order")
            if order is not None:
                relsByOrder[(order, rel.linkrole, rel.arcrole)].append(rel)
        for key, orderRels in relsByOrder.items():
            if len(orderRels) > 1:
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.1.8.10',
                    msg=_("The definition relationships have the same order attribute: '%(order)s'"),
                    order=key[0],
                    modelObject=orderRels
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_8_11(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.8.11] Definition relationships can not have the xbrldt:usable attribute set to False
    """
    definitionRelationshipSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.DEFINITION.getArcroles()))
    if definitionRelationshipSet is None:
        return
    for rel in definitionRelationshipSet.modelRelationships:
        if rel.arcrole in [XbrlConst.dimensionDomain, XbrlConst.domainMember]:
            continue
        if not rel.isUsable:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.8.11',
                msg=_("The definition relationship can not have the xbrldt:usable attribute set to False"),
                modelObject=rel
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_9_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.9.1] References should not be defined for extension concepts.
    """
    conceptReferenceSet = val.modelXbrl.relationshipSet(XbrlConst.conceptReference)
    for modelConcept in conceptReferenceSet.fromModelObjects():
        if not isinstance(modelConcept, ModelConcept):
            continue
        if modelConcept.qname is None or modelConcept.qname.namespaceURI is None:
            continue
        if pluginData.isExtensionUri(modelConcept.document.uri, val.modelXbrl):
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.9.1',
                msg=_("References should not be defined for extension concepts: %(conceptName)s"),
                conceptName=modelConcept.qname,
                modelObject=modelConcept
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_10_3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.10.3] The Inline XBRL document must contain all necessary namespace declarations including
    those for QName values of attributes. These namespace declarations must be on the root html element.
    """
    for ixdsHtmlRootElt in val.modelXbrl.ixdsHtmlElements:
        for elt in ixdsHtmlRootElt.iterdescendants():
            if not isinstance(elt, ModelObject):
                continue
            parent = elt.getparent()
            if parent is None or elt.nsmap == parent.nsmap:
                continue
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.10.3',
                msg=_('The Inline XBRL document must contain all necessary namespace declarations on the root html '
                      'element. Found namespace declaration on descendant element %(elementName)s.'),
                elementName=elt.tag,
                modelObject=elt
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_charsets(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1010E: The charset specification in the content attribute of the HTML <meta> tag must be UTF-8.
    EDINET.EC5000E: The encoding of the file must be UTF-8.
    EDINET.EC5003E: Prohibited characters must not be used.
    EDINET.EC5700W: [GFM 1.10.4] The document encoding must be set in both the XML document declaration and the HTML
    meta element for content type.
    """
    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl):
            continue

        if modelDocument.type != ModelDocument.Type.INLINEXBRLDOCUMENTSET:
            if modelDocument.documentEncoding is None or modelDocument.documentEncoding.lower() not in ('utf-8', 'utf-8-sig'):
                yield Validation.error(
                    codes='EDINET.EC5000E',
                    msg=_("The encoding is not UTF-8. "
                          "File name: '%(path)s'. "
                          "Please change the encoding of the relevant file to UTF-8."),
                    path=modelDocument.uri,
                    modelObject=modelDocument,
                )

        # TODO: Consolidate wtih NL.FR-NL-1.02
        for elt in modelDocument.xmlRootElement.iter():
            if isinstance(elt, ModelComment):
                texts = [getattr(elt, 'text')]
            else:
                texts = [elt.elementAttributesStr, elt.textValue]
            illegalChars: set[str] = set()
            for text in texts:
                illegalChars.update(HALF_KANA.intersection(set(text)))
            if len(illegalChars) > 0:
                yield Validation.error(
                    codes='EDINET.EC5003E',
                    msg=_("Prohibited characters (%(chars)s) are used. "
                          "File name: '%(file)s' (line %(line)s). "
                          "The file in question contains prohibited characters. "
                          "Please correct the prohibited characters. "),
                    chars=', '.join(sorted(illegalChars)),
                    file=modelDocument.basename,
                    line=elt.sourceline,
                    modelObject=elt,
                )

        if modelDocument.type != ModelDocument.Type.INLINEXBRL:
            continue

        xmlDeclaredEncoding = None
        try:
            with val.modelXbrl.fileSource.file(modelDocument.filepath)[0] as f:
                fileContent = cast(str, f.read(512))
            match = XmlUtil.xmlEncodingPattern.match(fileContent)
            if match:
                xmlDeclaredEncoding = match.group(1)
        except Exception:
            pass

        if xmlDeclaredEncoding is None:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.10.4',
                msg=_("The document encoding must be declared in an XML document declaration"),
                modelObject=modelDocument
            )

        metaCharsetDeclared = False
        for metaElt in modelDocument.xmlRootElement.iterdescendants(tag=XbrlConst.qnXhtmlMeta.clarkNotation):
            metaCharset = None
            httpEquiv = metaElt.get("http-equiv", "").lower()
            if httpEquiv == "content-type":
                content = metaElt.get("content")
                if content:
                    metaCharset = attrValue(content)
            if metaCharset is not None:
                metaCharsetDeclared = True
                if xmlDeclaredEncoding is not None and metaCharset.lower() != xmlDeclaredEncoding.lower():
                    yield Validation.warning(
                        codes='EDINET.EC5700W.GFM.1.10.4',
                        msg=_("The XML declaration encoding '%(xmlEncoding)s' does not match the HTML meta charset '%(metaCharset)s'"),
                        xmlEncoding=xmlDeclaredEncoding,
                        metaCharset=metaCharset,
                        modelObject=metaElt
                    )
                if metaCharset.lower() != 'utf-8':
                    yield Validation.error(
                        codes='EDINET.EC1010E',
                        msg=_("The charset specification in the content attribute of the HTML <meta> tag is not UTF-8. "
                            "File name: '%(path)s'. "
                            "Please set the character code of the file to UTF-8."),
                        path=modelDocument.uri,
                        modelObject=metaElt,
                    )

        if not metaCharsetDeclared:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.10.4',
                msg=_("The document encoding must be declared in an HTML meta element charset"),
                modelObject=modelDocument
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_10_12(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.10.12] In all inline XBRL files, multiple target attribute values ​​are not allowed.
    Correct the target attribute value. (A warning will be issued if the target attribute is not specified and is
    specified at the same time.)
    """
    targets: set[str | None] = set()
    for ixdsHtmlRootElt in val.modelXbrl.ixdsHtmlElements:
        targetEltTags = [qname.clarkNotation for qname in XbrlConst.ixbrlAllTargetElements]
        for elt in ixdsHtmlRootElt.iter(targetEltTags):
            targets.add(elt.get("target"))
    if len(targets) > 1:
        if None in targets:
            msg = _("Inline document set may not use multiple target documents. Found targets: default, %(targets)s")
        else:
            msg = _("Inline document set may not use multiple target documents. Found targets: %(targets)s")
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.10.12',
            msg=msg,
            targets=",".join(target for target in targets if target is not None),
            modelObject=val.modelXbrl,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_1_10_14(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 1.10.14] All non-empty footnotes must be referenced by an element
    """
    footnotes = set()
    usedFootnoteIDs = set()
    for ixdsHtmlRootElt in val.modelXbrl.ixdsHtmlElements:
        for elt in ixdsHtmlRootElt.iterdescendants(XbrlConst.qnIXbrlFootnote.clarkNotation, XbrlConst.qnIXbrl11Footnote.clarkNotation):
            if isinstance(elt, ModelInlineFootnote) and elt.value != '':
                footnotes.add(elt)
    for rel in val.modelXbrl.relationshipSet("XBRL-footnotes").modelRelationships:
        if rel.fromModelObject is not None and rel.toModelObject is not None:
            usedFootnoteIDs.add(rel.toModelObject.footnoteID)
    for footnote in footnotes:
        if footnote.footnoteID not in usedFootnoteIDs:
            yield Validation.warning(
                codes='EDINET.EC5700W.GFM.1.10.14',
                msg=_("A non-empty footnote is not referenced by an element"),
                modelObject=footnote
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_2_3_5(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 2.3.5] The name attribute of an xsd:element should consist of
    capitalized words corresponding to the standard label, a convention called Label
    Camel Case Concatenation (LC3).
    1. The first character of a name attribute must not be underscore.
    2. The first character of a name attribute must be capitalized.
    3. The following characters are not allowed in a name attribute:
        ()*+[]?\\/^{}|@#%^=~`“‘;:,<>&$₤€
    4. Do not use digits in the name attribute unless the element is
        being declared specifically because it must identify a regulation
        known by a number (“12b-1 Fees”, “FAS 132”). Always begin the name
        with a letter (e.g., “Rule12b1Fees”) and conform to LC3 (e.g., “Fas132”).
    5. Convert acronyms to Proper case (e.g., FAS becomes Fas, FHLC becomes
        Fhlc). Treat digits in an acronym as word separators (e.g., WIN2K becomes Win2K).

    Note: "corresponding to the standard label" is not enforceable, this implementation
    only checks the LC3 formatting rules. Similarly, rule 4 and 5 are not enforced here.
    """
    for name, concepts in val.modelXbrl.nameConcepts.items():
        for concept in concepts:
            if pluginData.isStandardTaxonomyUrl(concept.modelDocument.uri, val.modelXbrl):
                continue
            if not LC3_NAME_PATTERN.fullmatch(name):
                yield Validation.warning(
                    codes='EDINET.EC5700W.GFM.2.3.5',
                    msg=_("Element names should be set using capitalized words "
                          "(LC3 conversion rules) that correspond to standard labels."),
                    modelObject=concept
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_2_5_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 2.5.1] A presentation linkbase of a standard taxonomy should not be included in the DTS of an instance.
    """
    for elt in pluginData.getStandardTaxonomyExtensionLinks(LinkbaseType.PRESENTATION, val.modelXbrl):
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.2.5.1',
            msg=_("A presentation linkbase from the standard taxonomy file of '%(uri)s' is not allowed."),
            uri=elt.attr(XbrlConst.qnXlinkHref.clarkNotation),
            modelObject=elt
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_2_6_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 2.6.1] A calculation linkbase of a standard taxonomy should not be included in the DTS of an instance.
    """
    for elt in pluginData.getStandardTaxonomyExtensionLinks(LinkbaseType.CALCULATION, val.modelXbrl):
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.2.6.1',
            msg=_("A calculation linkbase from the standard taxonomy file of '%(uri)s' is not allowed."),
            uri=elt.attr(XbrlConst.qnXlinkHref.clarkNotation),
            modelObject=elt
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_gfm_2_8_1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5700W: [GFM 2.8.1] A reference linkbase of a standard taxonomy should not be included in the DTS of an instance.
    """
    for elt in pluginData.getStandardTaxonomyExtensionLinks(LinkbaseType.REFERENCE, val.modelXbrl):
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.2.8.1',
            msg=_("A reference linkbase from the standard taxonomy file of '%(uri)s' is not allowed."),
            uri=elt.attr(XbrlConst.qnXlinkHref.clarkNotation),
            modelObject=elt
        )
