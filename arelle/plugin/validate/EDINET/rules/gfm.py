"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any, cast, Iterable

import regex

from arelle import XbrlConst, XmlUtil
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelObject import ModelObject
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
from arelle.utils.validate.ValidationUtil import etreeIterWithDepth
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..PluginValidationDataExtension import PluginValidationDataExtension


_: TypeGetText

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
    for modelDocument, elt, uri in values:
        if uri is None:
            continue
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
            for uncast_elt, depth in etreeIterWithDepth(rootElt):
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
            elt = cast(ModelObject, elt)
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
