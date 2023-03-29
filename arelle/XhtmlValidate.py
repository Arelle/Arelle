'''
See COPYRIGHT.md for copyright information.

(originally part of XmlValidate, moved to separate module)
'''
from arelle import XbrlConst, XmlUtil, XmlValidate, ValidateFilingText, UrlUtil
from arelle.ModelXbrl import ModelXbrl
from arelle.ModelObject import ModelObject
from lxml import etree
import os, posixpath

htmlEltUriAttrs = { # attributes with URI content (for relative correction and %20 canonicalization
    "a": {"href"},
    "area": {"href"},
    "blockquote": {"cite"},
    "del": {"cite"},
    "form": {"action"},
    "input": {"src", "usemap"},
    "ins": {"cite"},
    "img": {"src", "longdesc", "usemap"},
    "object": ("codebase", "classid", "data", "archive", "usemap"), # codebase must be first to reolve others
    "q": {"cite"},
    }

ixSect = {
    XbrlConst.ixbrl: {
        "footnote": {"constraint": "ix10.5.1.1", "validation": "ix10.5.1.2"},
        "fraction": {"constraint": "ix10.6.1.1", "validation": "ix10.6.1.2"},
        "denominator": {"constraint": "ix10.6.1.1", "validation": "ix10.6.1.2"},
        "numerator": {"constraint": "ix10.6.1.1", "validation": "ix10.6.1.2"},
        "header": {"constraint": "ix10.7.1.1", "non-validatable": "ix10.7.1.2", "validation": "ix10.7.1.3"},
        "hidden": {"constraint": "ix10.8.1.1", "validation": "ix10.8.1.2"},
        "nonFraction": {"constraint": "ix10.9.1.1", "validation": "ix10.9.1.2"},
        "nonNumeric": {"constraint": "ix10.10.1.1", "validation": "ix10.10.1.2"},
        "references": {"constraint": "ix10.11.1.1", "validation": "ix10.11.1.2"},
        "resources": {"constraint": "ix10.12.1.1", "validation": "ix10.12.1.2"},
        "tuple": {"constraint": "ix10.13.1.1", "validation": "ix10.13.1.2"},
        "other": {"constraint": "ix10", "validation": "ix10"}},
    XbrlConst.ixbrl11: {
        "continuation": {"constraint": "ix11.4.1.1", "validation": "ix11.4.1.2"},
        "exclude": {"constraint": "ix11.5.1.1", "validation": "ix11.5.1.2"},
        "footnote": {"constraint": "ix11.6.1.1", "validation": "ix11.6.1.2"},
        "fraction": {"constraint": "ix11.7.1.2", "validation": "ix11.7.1.3"},
        "denominator": {"constraint": "ix11.7.1.1", "validation": "ix11.7.1.3"},
        "numerator": {"constraint": "ix11.7.1.1", "validation": "ix11.7.1.3"},
        "header": {"constraint": "ix11.8.1.1", "non-validatable": "ix11.8.1.2", "validation": "ix11.8.1.3"},
        "hidden": {"constraint": "ix11.9.1.1", "validation": "ix11.9.1.2"},
        "nonFraction": {"constraint": "ix11.10.1.1", "validation": "ix11.10.1.2"},
        "nonNumeric": {"constraint": "ix11.11.1.1", "validation": "ix11.11.1.2"},
        "references": {"constraint": "ix11.12.1.1", "validation": "ix11.12.1.2"},
        "relationship": {"constraint": "ix11.13.1.1", "validation": "ix11.13.1.2"},
        "resources": {"constraint": "ix11.14.1.1", "validation": "ix11.14.1.2"},
        "tuple": {"constraint": "ix11.15.1.1", "validation": "ix11.15.1.2"},
        "other": {"constraint": "ix11", "validation": "ix11"}}
    }
def ixMsgCode(codeName, elt=None, sect="constraint", ns=None, name=None) -> str:
    if elt is None:
        if ns is None: ns = XbrlConst.ixbrl11
        if name is None: name = "other"
    else:
        if ns is None and elt.namespaceURI in XbrlConst.ixbrlAll:
            ns = elt.namespaceURI
        else:
            ns = getattr(elt.modelDocument, "ixNS", XbrlConst.ixbrl11)
        if name is None:
            name = elt.localName
            if name in ("context", "unit"):
                name = "resources"
    return "{}:{}".format(ixSect[ns].get(name,"other")[sect], codeName)

def xhtmlValidate(modelXbrl: ModelXbrl, elt: ModelObject) -> None:
    from lxml.etree import XMLSyntaxError
    validateEntryText = modelXbrl.modelManager.disclosureSystem.validateEntryText
    if validateEntryText:
        valHtmlContentMsgPrefix = modelXbrl.modelManager.disclosureSystem.validationType + ".5.02.05."


    XmlValidate.lxmlSchemaValidate(elt.modelDocument, 
                                   "http://www.xbrl.org/2013/inlineXBRL/xhtml-inlinexbrl-1_1.xsd",
                                   # pass valid hrefs becalse lxml entity resolver doesn't pass back parent's baseURL
                                   {"http://www.xbrl.org/2013/inlineXBRL/xhtml",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-link-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml11-model-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-meta-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-inlstruct-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-inlpres-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-nameident-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-hypertext-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-inlstyle-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-inlphras-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-basic10.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-misc-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-datatypes-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-basic10-module-redefines-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-image-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-basic10-model-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-param-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-table-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xml-events-copyright-2.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-basic-table-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml11.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xml-events-copyright-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml11-modules-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-target-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-legacy-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-edit-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-pres-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-script-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xml-handlers-2.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-style-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-frames-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-csismap-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-blkstruct-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-basic-form-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml11-module-redefines-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xml-events-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-events-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-text-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xframes-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml2.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xml-events-2.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-ruby-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-list-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-framework-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-ssismap-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-struct-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-copyright-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xml-events-attribs-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-blkphras-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-applet-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-blkpres-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-ruby-basic-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xml-events-attribs-2.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-basic10-modules-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-charent-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-object-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-iframe-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-notations-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-attribs-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-bdo-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-base-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml/xhtml-form-1.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml-inlinexbrl-1_1-definitions.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml-inlinexbrl-1_1-model.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml-inlinexbrl-1_1-modules.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xbrl",
                                    "http://www.xbrl.org/2013/inlineXBRL/xbrl/xl-2003-12-31.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xbrl/xbrl-linkbase-2003-12-31-ixmod.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xbrl/xlink-2003-12-31.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xbrl/xbrl-instance-2003-12-31-ixmod.xsd",
                                    "http://www.xbrl.org/2013/inlineXBRL/xhtml-inlinexbrl-1_1.xsd"})
    # lxml bug: doesn't detect: class="" (min length 1)
    for e in elt.getroottree().iterfind("//{http://www.w3.org/1999/xhtml}*[@class='']"):
        modelXbrl.error("arelle:xhtmlClassError",
            _("Attribute class must not be empty on element ix:%(element)s"),
            modelObject=e, element=e.localName)

    try:
        if validateEntryText:
            ValidateFilingText.validateHtmlContent(modelXbrl, elt, elt, "InlineXBRL", valHtmlContentMsgPrefix, isInline=True)
    except XMLSyntaxError as err:
        modelXbrl.error("html:syntaxError",
            _("%(element)s error %(error)s"),
            modelObject=elt, element=elt.localName.title(), error=', '.join(dtdErrs()))

def resolveHtmlUri(elt, name, value):
    if name == "archive": # URILIST
        return " ".join(resolveHtmlUri(elt, "archiveListElement", v) for v in value.split(" "))
    if not UrlUtil.isAbsolute(value):
        if elt.localName == "object" and name in ("classid", "data", "archiveListElement") and elt.get("codebase"):
            base = elt.get("codebase") + "/"
        else:
            base = getattr(elt.modelDocument, "htmlBase") # None if no htmlBase, empty string if it's not set
        if base:
            if value.startswith("/"): # add to authority
                value = UrlUtil.authority(base) + value
            elif value.startswith("#"): # add anchor to base document
                value = base + value
            else:
                value = os.path.dirname(base) + "/" + value
    # canonicalize ../ and ./
    scheme, sep, pathpart = value.rpartition("://")
    if sep:
        pathpart = pathpart.replace('\\','/')
        endingSep = '/' if pathpart[-1] == '/' else ''  # normpath drops ending directory separator
        _uri = scheme + "://" + posixpath.normpath(pathpart) + endingSep
    else:
        _uri = posixpath.normpath(value)
    return _uri # .replace(" ", "%20")  requirement for this is not yet clear
