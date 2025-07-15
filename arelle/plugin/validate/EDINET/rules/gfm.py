"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any, cast, Iterable

import regex

from arelle import XbrlConst, XmlUtil
from arelle.ModelObject import ModelObject
from arelle.PrototypeDtsObject import LocPrototype, ArcPrototype
from arelle.UrlUtil import isHttpUrl, splitDecodeFragment
from arelle.ValidateXbrl import ValidateXbrl
from arelle.ValidateXbrlCalcs import insignificantDigits
from arelle.XbrlConst import xhtmlBaseIdentifier, xmlBaseIdentifier
from arelle.XmlValidate import VALID
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.utils.validate.ValidationUtil import etreeIterWithDepth
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

GFM_CONTEXT_DATE_PATTERN = regex.compile(r"^[12][0-9]{3}-[01][0-9]-[0-3][0-9]$")


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
    unusedUnits = set(val.modelXbrl.units.values()) - {fact.unit for fact in val.modelXbrl.facts if fact.unit is not None}
    if len(unusedUnits) > 0:
        yield Validation.warning(
            codes='EDINET.EC5700W.GFM.1.2.27',
            msg=_("Delete unused units from the instance."),
            modelObject=list(unusedUnits)
        )
