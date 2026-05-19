'''
See COPYRIGHT.md for copyright information.

(originally part of XmlValidate, moved to separate module)
'''
from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from arelle import ValidateFilingText, XbrlConst, XmlValidate
from arelle.ModelObject import ModelObject
from arelle.ModelXbrl import ModelXbrl
from arelle.XhtmlInlineUtil import (
    INLINE_1_0_SCHEMA,
    INLINE_1_1_SCHEMA,
    htmlEltUriAttrs as htmlEltUriAttrs,
    ixMsgCode as ixMsgCode,
    resolveHtmlUri as resolveHtmlUri,
)

if TYPE_CHECKING:
    from arelle.typing import TypeGetText

_ : TypeGetText


def xhtmlValidate(modelXbrl: ModelXbrl, elt: ModelObject) -> None:
    validateEntryText = modelXbrl.modelManager.disclosureSystem.validateEntryText
    if validateEntryText:
        validationType = modelXbrl.modelManager.disclosureSystem.validationType
        assert validationType is not None, "If 'validateEntryText' is set, 'validationType' must also be set"
        valHtmlContentMsgPrefix = validationType + ".5.02.05."

    inlineSchema = INLINE_1_1_SCHEMA
    if containsNamespacedElements(elt, XbrlConst.ixbrl) and not containsNamespacedElements(elt, XbrlConst.ixbrl11):
        inlineSchema = INLINE_1_0_SCHEMA
    XmlValidate.lxmlSchemaValidate(elt.modelDocument, inlineSchema)

    # lxml bug: doesn't detect: class="" (min length 1)
    for e in elt.getroottree().iterfind(".//{http://www.w3.org/1999/xhtml}*[@class='']"):
        modelXbrl.error("arelle:xhtmlClassError",
            _("Attribute class must not be empty on element ix:%(element)s"),
            modelObject=e, element=e.localName)

    if validateEntryText:
        ValidateFilingText.validateHtmlContent(modelXbrl, elt, elt, "InlineXBRL", valHtmlContentMsgPrefix, isInline=True)


def containsNamespacedElements(elt: etree.ElementBase, namespace: str) -> bool:
    return elt.getroottree().find(".//ns:*", {"ns": namespace}) is not None
