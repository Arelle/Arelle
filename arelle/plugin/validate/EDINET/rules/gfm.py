"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle import XbrlConst, XmlUtil
from arelle.UrlUtil import isHttpUrl, splitDecodeFragment
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


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
        yield Validation.error(
            codes='EDINET.EC5700W.GFM.1.1.3',
            msg=_("The URI content of the xlink:href attribute, the xsi:schemaLocation "
                  "attribute and the schemaLocation attribute must be relative and "
                  "contain no forward slashes, or a recognized external location of "
                  "a standard taxonomy schema file, or a '#' followed by a shorthand "
                  "xpointer. The URI '%(uri)s' is not valid."),
            uri=uri,
            modelObject=elt,
        )
