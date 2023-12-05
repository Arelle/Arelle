"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from arelle import ModelDocument
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XbrlConst import qnLinkSchemaRef, qnLinkLinkbaseRef, qnLinkRoleRef, qnLinkArcroleRef, qnXbrliContext, qnXbrliUnit
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (
    DISCLOSURE_SYSTEM_NT16,
    DISCLOSURE_SYSTEM_NT17,
    DISCLOSURE_SYSTEM_NT18,
)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

INSTANCE_ELEMENT_ORDER = {
    qnLinkSchemaRef.clarkNotation: 0,
    qnLinkLinkbaseRef.clarkNotation: 1,
    qnLinkRoleRef.clarkNotation: 2,
    qnLinkArcroleRef.clarkNotation: 3,
    qnXbrliContext.clarkNotation: 4,
    qnXbrliUnit.clarkNotation: 5,
    'fact': 6,
}


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18,
    ],
)
def rule_fg_nl_04(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FG-NL-04: An XBRL instance document SHOULD order the elements so that referents precede references.
    The children of the 'xbrli:xbrl' element should appear in the following order:
    1. schemaRef
    2. linkbaseRef
    3. roleRef
    4. arcroleRef
    5. context
    6. units
    7. facts
    """
    errors = defaultdict(list)
    for doc in val.modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            currentName = list(INSTANCE_ELEMENT_ORDER.keys())[0]
            currentIndex = INSTANCE_ELEMENT_ORDER[currentName]
            for elt in doc.xmlRootElement.iter():
                if not isinstance(elt, ModelObject):
                    continue
                if isinstance(elt, ModelFact):
                    thisName = 'fact'
                else:
                    thisName = elt.elementQname.clarkNotation
                if thisName not in INSTANCE_ELEMENT_ORDER:
                    continue
                thisIndex = INSTANCE_ELEMENT_ORDER[thisName]
                if thisIndex == currentIndex:
                    continue
                if thisIndex > currentIndex:
                    currentIndex = thisIndex
                    currentName = thisName
                else:
                    errors[(thisName, currentName)].append(elt)
    for names, elts in errors.items():
        beforeName, afterName = names
        yield Validation.warning(
            codes='NL.FG-NL-04',
            msg=_('"%(beforeName)s" elements should not appear after "%(afterName)s" elements.'),
            modelObject=elts,
            beforeName=qname(beforeName),
            afterName=qname(afterName),
        )
