'''
See COPYRIGHT.md for copyright information.

(originally part of XmlValidate, moved to separate module)
'''
from lxml import etree
from lxml.etree import XMLSyntaxError

from arelle import ValidateFilingText, XbrlConst, XmlValidate
from arelle.ModelObject import ModelObject
from arelle.ModelXbrl import ModelXbrl
from arelle.XhtmlInlineUtil import (
    INLINE_1_0_SCHEMA,
    INLINE_1_1_SCHEMA,
    htmlEltUriAttrs as htmlEltUriAttrs,
    ixMsgCode as ixMsgCode,
)


def xhtmlValidate(modelXbrl: ModelXbrl, elt: ModelObject) -> None:
    validateEntryText = modelXbrl.modelManager.disclosureSystem.validateEntryText
    if validateEntryText:
        valHtmlContentMsgPrefix = modelXbrl.modelManager.disclosureSystem.validationType + ".5.02.05."

    inlineSchema = INLINE_1_1_SCHEMA
    if _containsNamespacedElements(elt, XbrlConst.ixbrl) and not _containsNamespacedElements(elt, XbrlConst.ixbrl11):
        inlineSchema = INLINE_1_0_SCHEMA
    XmlValidate.lxmlSchemaValidate(elt.modelDocument, inlineSchema)

    # lxml bug: doesn't detect: class="" (min length 1)
    for e in elt.getroottree().iterfind(".//{http://www.w3.org/1999/xhtml}*[@class='']"):
        modelXbrl.error("arelle:xhtmlClassError",
            _("Attribute class must not be empty on element ix:%(element)s"),
            modelObject=e, element=e.localName)

    try:
        if validateEntryText:
            ValidateFilingText.validateHtmlContent(modelXbrl, elt, elt, "InlineXBRL", valHtmlContentMsgPrefix, isInline=True)
    except XMLSyntaxError as err:
        modelXbrl.error("html:syntaxError",
            _("%(element)s error %(error)s"),
            modelObject=elt, element=elt.localName.title(), error=err.msg)


def _containsNamespacedElements(elt: etree.ElementBase, namespace: str) -> bool:
    return elt.getroottree().find(".//ns:*", {"ns": namespace}) is not None
