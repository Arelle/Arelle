"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle import XbrlConst
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
def rule_frta_2_1_9(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5710W: [FRTA.2.1.9] All documentation of a concept must be contained
    in XBRL linkbases. Do not use the xsd:documentation element in an element definition.
    """
    errors = []
    for modelDocument in val.modelXbrl.urlDocs.values():
        if pluginData.isStandardTaxonomyUrl(modelDocument.uri, val.modelXbrl):
            continue
        rootElt = modelDocument.xmlRootElement
        for elt in rootElt.iterdescendants(XbrlConst.qnXsdDocumentation.clarkNotation):
            errors.append(elt)
    if len(errors) > 0:
        yield Validation.error(
            codes='EDINET.EC5710W.FRTA.2.1.9',
            msg=_("All documentation of a concept must be contained in XBRL linkbases. "
                  "Taxonomy element declarations should not use the XML Schema documentation element."),
            modelObject=errors,
        )
