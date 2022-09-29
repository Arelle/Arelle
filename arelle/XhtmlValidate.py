'''
See COPYRIGHT.md for copyright information.

(originally part of XmlValidate, moved to separate module)
'''
from arelle import XbrlConst, XmlUtil, XmlValidate, ValidateFilingText, UrlUtil
from arelle.ModelObject import ModelObject, ModelComment
from arelle.PythonUtil import normalizeSpace
from arelle.ModelXbrl import ModelXbrl
from arelle.ModelObject import ModelObject
from lxml import etree
import os, re, posixpath

EMPTYDICT = {}

XHTML_DTD = { # modified to have ixNestedContent elements as placeholders for ix footnote and nonnumeric/continuation elements
    XbrlConst.ixbrl: "xhtml1-strict-ix.dtd",
    XbrlConst.ixbrl11: "xhtml1_1-strict-ix.dtd"
    }

ixElements = {
     XbrlConst.ixbrl: {
        "denominator", "exclude", "footnote", "fraction", "header", "hidden",
        "nonFraction", "nonNumeric", "numerator", "references", "resources", "tuple"},
     XbrlConst.ixbrl11: {
        "continuation", "denominator", "exclude", "footnote", "fraction", "header", "hidden",
        "nonFraction", "nonNumeric","numerator", "references", "relationship","resources", "tuple"}
    }

ixAttrType = {
    XbrlConst.ixbrl: {
        "arcrole": "anyURI",
        "contextRef": "NCName",
        "decimals": "XBRLI_DECIMALSUNION",
        "escape": "boolean",
        "footnoteID": "NCName",
        "footnoteLinkRole": "anyURI",
        "footnoteRefs": "IDREFS",
        "footnoteRole": "anyURI",
        "format": "QName",
        "id": "NCName",
        "name": "QName",
        "precision": "XBRLI_PRECISIONUNION",
        "order": "decimal",
        "scale": "integer",
        "sign": {"type": "string", "pattern": re.compile("-$")},
        "target": "NCName",
        "title": "string",
        "tupleID": "NCName",
        "tupleRef": "NCName",
        "unitRef": "NCName"},
    XbrlConst.ixbrl11: {
        "arcrole": "anyURI",
        "contextRef": "NCName",
        "continuedAt": "NCName",
        "decimals": "XBRLI_DECIMALSUNION",
        "escape": "boolean",
        "footnoteRole": "anyURI",
        "format": "QName",
        "fromRefs": "IDREFS",
        "id": "NCName",
        "linkRole": "anyURI",
        "name": "QName",
        "precision": "XBRLI_PRECISIONUNION",
        "order": "decimal",
        "scale": "integer",
        "sign": {"type": "string", "pattern": re.compile("-$")},
        "target": "NCName",
        "title": "string",
        "toRefs": "IDREFS",
        "tupleID": "NCName",
        "tupleRef": "NCName",
        "unitRef": "NCName"}
    }
htmlAttrType = {
    "id": "ID",
    "class": "NMTOKENS",
    "colspan": "nonNegativeInteger",
    "rowspan": "nonNegativeInteger",
    "maxlength": "nonNegativeInteger",
    "rbspan": "nonNegativeInteger",
    "size": "nonNegativeInteger",
    "tabindex": "nonNegativeInteger",
    "hspace": "nonNegativeInteger",
    "vspace": "nonNegativeInteger",
    "border": "nonNegativeInteger",
    "marginwidth": "nonNegativeInteger",
    "marginheight": "nonNegativeInteger",
    "alink": {"type": "token", "pattern": re.compile("#[0-9a-fA-F]{6}$")},
    "bgcolor": {"type": "token", "pattern": re.compile("#[0-9a-fA-F]{6}$")},
    "color": {"type": "token", "pattern": re.compile("#[0-9a-fA-F]{6}$")},
    "link": {"type": "token", "pattern": re.compile("#[0-9a-fA-F]{6}$")},
    "text": {"type": "token", "pattern": re.compile("#[0-9a-fA-F]{6}$")},
    "vlinke": {"type": "token", "pattern": re.compile("#[0-9a-fA-F]{6}$")},
    "accesskey": {"type": "string", "length": 1},
    "char": {"type": "string", "length": 1},
    "height": {"type": "token", "pattern": re.compile(r"\d+%?$|\d*\.\d+%?$")},
    "width": {"type": "token", "pattern": re.compile(r"\d+%?$|\d*\.\d+%?$|\d*\*$")},
    # these can be nonNegativeInteger or MultiLength in frameset
    "cols": {"type": "token", "pattern": re.compile(r"(\d+%?|\d*\.\d+%?|\d*\*)(,\d+%?|,\d*\.\d+%?|,\d*\*)*$")},
    "rows": {"type": "token", "pattern": re.compile(r"(\d+%?|\d*\.\d+%?|\d*\*)(,\d+%?|,\d*\.\d+%?|,\d*\*)*$")},
    "rel": "NMTOKENS",
    "rev": "NMTOKENS",
    "datetime": "dateTime",
    "hfreflang": "language"
    }
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
ixAttrRequired = {
    XbrlConst.ixbrl: {
        "footnote": ("footnoteID",),
        "fraction": ("name", "contextRef", "unitRef"),
        "nonFraction": ("name", "contextRef", "unitRef"),
        "nonNumeric": ("name", "contextRef"),
        "tuple": ("name",)},
    XbrlConst.ixbrl11: {
        "continuation": ("id",),
        "footnote": ("id",),
        "fraction": ("name", "contextRef", "unitRef"),
        "nonFraction": ("name", "contextRef", "unitRef"),
        "nonNumeric": ("name", "contextRef"),
        "tuple": ("name",)}
    }
ixAttrDefined = {
    XbrlConst.ixbrl: {
        "footnote": ("id", "footnoteID", "arcrole", "footnoteLinkRole", "footnoteRole", "title"),
        "fraction": ("id", "name", "target", "contextRef", "unitRef", "tupleRef", "order",
                     "footnoteRefs"),
        "denominator": ("format", "scale", "sign"),
        "numerator": ("format", "scale", "sign"),
        "nonFraction": ("id", "name", "target", "contextRef", "unitRef", "tupleRef", "order",
                        "footnoteRefs", "format", "decimals", "precision", "scale", "sign"),
        "nonNumeric": ("id", "name", "target", "contextRef", "tupleRef", "order",
                       "footnoteRefs", "format", "escape"),
        "references": ("id", "target"),
        "tuple": ("id", "name", "target", "tupleID", "tupleRef", "order", "footnoteRefs")},
    XbrlConst.ixbrl11: {
        "continuation": ("id", "continuedAt"),
        "footnote": ("id", "continuedAt", "footnoteRole", "title"),
        "fraction": ("id", "name", "target", "contextRef", "unitRef", "tupleRef", "order"),
        "denominator": ("format", "scale", "sign"),
        "numerator": ("format", "scale", "sign"),
        "nonFraction": ("id", "name", "target", "contextRef", "unitRef", "tupleRef", "order",
                        "format", "decimals", "precision", "scale", "sign"),
        "nonNumeric": ("id", "name", "target", "contextRef", "tupleRef", "order",
                       "format", "escape", "continuedAt"),
        "references": ("id", "target"),
        "relationship": ("arcrole", "linkRole", "fromRefs", "toRefs", "order"),
        "tuple": ("id", "name", "target", "tupleID", "tupleRef", "order")}
    }
allowedNonIxAttrNS = {
    "footnote": "http://www.w3.org/XML/1998/namespace",
    "fraction": "##other",
    "denominator": "##other",
    "numerator": "##other",
    "nonFraction": "##other",
    "nonNumeric": "##other",
    "references": "##other",
    "relationship": "http://www.w3.org/XML/1998/namespace",
    "tuple": "##other"}
ixHierarchyConstraints = {
    # localName: (-rel means doesnt't have relation, +rel means has rel,
    #   &rel means only listed rels
    #   ^rel means must have at least one of listed rels and can't have any non-listed rels
    #   1rel means non-nil element must have only one of listed rels
    #   ?rel means 0 or 1 cardinality
    #   +rel means 1 or more cardinality
    "continuation": (("-ancestor",("hidden",)),),
    "exclude": (("+ancestor",("continuation", "footnote", "nonNumeric")),),
    "denominator": (("-descendant",('*',)),),
    "fraction": (("1descendant",('numerator',)),
                 ("1descendant",('denominator',))),
    "header": (("&child-sequence", ('hidden','references','resources')), # can only have these children, in order, no others
               ("?child-choice", ('hidden',)),
               ("?child-choice", ('resources',)),
               ("-ancestor",("{http://www.w3.org/1999/xhtml}head",))),
    "hidden": (("+parent", ("header",)),
               ("&child-choice", ('footnote', 'fraction', 'nonFraction', 'nonNumeric', 'tuple')),
               ("+child-choice", ('footnote', 'fraction', 'nonFraction', 'nonNumeric', 'tuple'))),
    "footnote": (("+child-or-text",('*',)),),
    "numerator": (("-descendant",('*',)),),
    "references": (("+parent",("header",)),
                   ("&child-choice", ('{http://www.xbrl.org/2003/linkbase}schemaRef', '{http://www.xbrl.org/2003/linkbase}linkbaseRef'))),
    "relationship": (("+parent",("resources",)),),
    "resources": (("+parent",("header",)),
                  ("&child-choice", ('relationship',
                                     '{http://www.xbrl.org/2003/linkbase}roleRef', '{http://www.xbrl.org/2003/linkbase}arcroleRef',
                                     '{http://www.xbrl.org/2003/instance}context', '{http://www.xbrl.org/2003/instance}unit'))),
    "tuple": (("-child-choice",("continuation", "exclude", "denominator", "footnote", "numerator", "header", "hidden",
                                "references", "relationship", "resources")),)
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
    from lxml.etree import DTD, XMLSyntaxError
    from arelle import FunctionIxt
    ixNsStartTags = ["{" + ns + "}" for ns in XbrlConst.ixbrlAll]
    validateEntryText = modelXbrl.modelManager.disclosureSystem.validateEntryText
    if validateEntryText:
        valHtmlContentMsgPrefix = modelXbrl.modelManager.disclosureSystem.validationType + ".5.02.05."
    # find ix version for messages
    _ixNS = getattr(elt.modelDocument, "ixNS", XbrlConst.ixbrl11)
    _ixNStag = "{{{}}}".format(_ixNS)
    _xhtmlDTD = XHTML_DTD[_ixNS]
    _customTransforms = modelXbrl.modelManager.customTransforms or {}

    def checkAttribute(elt, isIxElt, attrTag, attrValue):
        ixEltAttrDefs = ixAttrDefined.get(elt.namespaceURI, EMPTYDICT).get(elt.localName, ())
        if attrTag.startswith("{"):
            ns, sep, localName = attrTag[1:].partition("}")
        else:
            ns = None
            localName = attrTag
        if ns is not None and ns not in XbrlConst.ixbrlAll and attrTag not in ixEltAttrDefs:
            if ns == XbrlConst.xsi:
                pass # xsi attributes are always allowed
            elif isIxElt:
                allowedNs = allowedNonIxAttrNS.get(elt.localName, None)
                if allowedNs != "##other" and ns != allowedNs:
                    modelXbrl.error(ixMsgCode("qualifiedAttributeNotExpected", elt),
                        _("Inline XBRL element %(element)s has qualified attribute %(name)s"),
                        modelObject=elt, element=str(elt.elementQname), name=attrTag)
                if ns == XbrlConst.xbrli and elt.localName in {
                    "fraction", "nonFraction", "nonNumeric", "references", "relationship", "tuple"}:
                    modelXbrl.error(ixMsgCode("qualifiedAttributeDisallowed", elt),
                        _("Inline XBRL element %(element)s has disallowed attribute %(name)s"),
                        modelObject=elt, element=str(elt.elementQname), name=attrTag)
            else:
                if ns in XbrlConst.ixbrlAll:
                    modelXbrl.error(ixMsgCode("inlineAttributeMisplaced", elt, name="other"),
                        _("Inline XBRL attributes are not allowed on html elements: ix:%(name)s"),
                        modelObject=elt, name=localName)
                elif ns not in {XbrlConst.xml, XbrlConst.xsi, XbrlConst.xhtml}:
                    modelXbrl.error(ixMsgCode("extensionAttributeMisplaced", ns=_ixNS),
                        _("Extension attributes are not allowed on html elements: %(tag)s"),
                        modelObject=elt, tag=attrTag)
        elif isIxElt:
            try:
                _xsdType = ixAttrType[elt.namespaceURI][localName]
                if isinstance(_xsdType, dict):
                    baseXsdType = _xsdType["type"]
                    facets = _xsdType
                else:
                    baseXsdType = _xsdType
                    facets = None
                XmlValidate.validateValue(modelXbrl, elt, attrTag, baseXsdType, attrValue, facets=facets)

                if not (attrTag in ixEltAttrDefs or
                        (localName in ixEltAttrDefs and (not ns or ns in XbrlConst.ixbrlAll))):
                    raise KeyError
                disallowedXbrliAttrs = ({"scheme", "periodType",     "balance", "contextRef", "unitRef", "precision", "decimals"} -
                                        {"fraction": {"contextRef", "unitRef"},
                                         "nonFraction": {"contextRef", "unitRef", "decimals", "precision"},
                                         "nonNumeric": {"contextRef"}}.get(elt.localName, set()))
                disallowedAttrs = set(a for a in disallowedXbrliAttrs if elt.get(a) is not None)
                if disallowedAttrs:
                    modelXbrl.error(ixMsgCode("inlineElementAttributes",elt),
                        _("Inline XBRL element %(element)s has disallowed attributes %(attributes)s"),
                        modelObject=elt, element=elt.elementQname, attributes=", ".join(disallowedAttrs))
            except KeyError:
                modelXbrl.error(ixMsgCode("attributeNotExpected",elt),
                    _("Attribute %(attribute)s is not expected on element ix:%(element)s"),
                    modelObject=elt, attribute=attrTag, element=elt.localName)
        elif ns is None:
            _xsdType = htmlAttrType.get(localName)
            if _xsdType is not None:
                if isinstance(_xsdType, dict):
                    baseXsdType = _xsdType["type"]
                    facets = _xsdType
                else:
                    baseXsdType = _xsdType
                    facets = None
                XmlValidate.validateValue(modelXbrl, elt, attrTag, baseXsdType, attrValue, facets=facets)

    def checkHierarchyConstraints(elt):
        constraints = ixHierarchyConstraints.get(elt.localName)
        if constraints:
            for _rel, names in constraints:
                reqt = _rel[0]
                rel = _rel[1:]
                if reqt in ('&', '^', '1'):
                    nameFilter = ('*',)
                else:
                    nameFilter = names
                if nameFilter == ('*',):
                    namespaceFilter = namespacePrefix = '*'
                elif len(nameFilter) == 1 and "}" in nameFilter[0] and nameFilter[0][0] == "{":
                    namespaceFilter, _sep, nameFilter = nameFilter[0][1:].partition("}")
                    namespacePrefix = XmlUtil.xmlnsprefix(elt,namespaceFilter)
                else:
                    namespaceFilter = elt.namespaceURI
                    namespacePrefix = elt.prefix
                relations = {"ancestor": XmlUtil.ancestor,
                             "parent": XmlUtil.parent,
                             "child-choice": XmlUtil.children,
                             "child-sequence": XmlUtil.children,
                             "child-or-text": XmlUtil.children,
                             "descendant": XmlUtil.descendants}[rel](
                            elt,
                            namespaceFilter,
                            nameFilter)
                if rel in ("ancestor", "parent"):
                    if relations is None: relations = []
                    else: relations = [relations]
                if rel == "child-or-text":
                    relations += XmlUtil.innerTextNodes(elt, ixExclude=True, ixEscape=False, ixContinuation=False, ixResolveUris=False)
                issue = ''
                if reqt in ('^',):
                    if not any(r.localName in names and r.namespaceURI == elt.namespaceURI
                               for r in relations):
                        issue = " and is missing one of " + ', '.join(names)
                if reqt in ('1',) and not elt.isNil:
                    if sum(r.localName in names and r.namespaceURI == elt.namespaceURI
                           for r in relations) != 1:
                        issue = " and must have exactly one of " + ', '.join(names)
                if reqt in ('&', '^'):
                    disallowed = [str(r.elementQname)
                                  for r in relations
                                  if not (r.tag in names or
                                          (r.localName in names and r.namespaceURI == elt.namespaceURI))]
                    if disallowed:
                        issue += " and may not have " + ", ".join(disallowed)
                    elif rel == "child-sequence":
                        sequencePosition = 0
                        for i, r in enumerate(relations):
                            rPos = names.index(str(r.localName))
                            if rPos < sequencePosition:
                                issue += " and is out of sequence: " + str(r.elementQname)
                            else:
                                sequencePosition = rPos
                if reqt == '?' and len(relations) > 1:
                    issue = " may only have 0 or 1 but {0} present ".format(len(relations))
                if reqt == '+' and len(relations) == 0:
                    issue = " must have at least 1 but none present "
                disallowedChildText = bool(reqt == '&' and
                                           rel in ("child-sequence", "child-choice")
                                           and elt.textValue.strip(" \t\r\n"))
                if ((reqt == '+' and not relations) or
                    (reqt == '-' and relations) or
                    (issue) or disallowedChildText):
                    code = "{}:{}".format(ixSect[elt.namespaceURI].get(elt.localName,"other")["constraint"], {
                           'ancestor': "ancestorNode",
                           'parent': "parentNode",
                           'child-choice': "childNodes",
                           'child-sequence': "childNodes",
                           'child-or-text': "childNodesOrText",
                           'descendant': "descendantNodes"}[rel] + {
                            '+': "Required",
                            '-': "Disallowed",
                            '&': "Allowed",
                            '^': "Specified",
                            '1': "Specified"}.get(reqt, "Specified"))
                    msg = _("Inline XBRL ix:{0} {1} {2} {3} {4} element{5}").format(
                                elt.localName,
                                {'+': "must", '-': "may not", '&': "may only",
                                 '?': "may", '+': "must", '^': "must", '1': "must"}[reqt],
                                {'ancestor': "be nested in",
                                 'parent': "have parent",
                                 'child-choice': "have child",
                                 'child-sequence': "have child",
                                 'child-or-text': "have child or text,",
                                 'descendant': "have as descendant"}[rel],
                                '' if rel == 'child-or-text' else
                                ', '.join(str(r.elementQname) for r in relations)
                                if names == ('*',) and relations else
                                ", ".join("{}:{}".format(namespacePrefix, n) for n in names),
                                issue,
                                " and no child text (\"{}\")".format(elt.textValue.strip(" \t\r\n")[:32]) if disallowedChildText else "")
                    modelXbrl.error(code, msg,
                                    modelObject=[elt] + relations, requirement=reqt,
                                    messageCodes=("ix{ver.sect}:ancestorNode{Required|Disallowed}",
                                                  "ix{ver.sect}:childNodesOrTextRequired",
                                                  "ix{ver.sect}:childNodes{Required|Disallowed|Allowed}",
                                                  "ix{ver.sect}:descendantNodesDisallowed",
                                                  "ix{ver.sect}:parentNodeRequired"))
        # other static element checks (that don't require a complete object model, context, units, etc
        if elt.localName == "nonFraction":
            childElts = XmlUtil.children(elt, '*', '*')
            hasText = (elt.text or "") or any((childElt.tail or "") for childElt in childElts)
            if elt.isNil:
                ancestorNonFractions = XmlUtil.ancestors(elt, _ixNS, elt.localName)
                if ancestorNonFractions:
                    modelXbrl.error(ixMsgCode("nonFractionAncestors", elt),
                        _("Fact %(fact)s is a nil nonFraction and MUST not have an ancestor ix:nonFraction"),
                        modelObject=[elt] + ancestorNonFractions, fact=elt.qname)
                if childElts or hasText:
                    modelXbrl.error(ixMsgCode("nonFractionTextAndElementChildren", elt),
                        _("Fact %(fact)s is a nil nonFraction and MUST not have an child elements or text"),
                        modelObject=[elt] + childElts, fact=elt.qname)
                    elt.setInvalid() # prevent further validation or cascading errors
            else:
                if ((childElts and (len(childElts) != 1 or childElts[0].namespaceURI != _ixNS or childElts[0].localName != "nonFraction")) or
                    (childElts and hasText)):
                    modelXbrl.error(ixMsgCode("nonFractionTextAndElementChildren", elt),
                        _("Fact %(fact)s is a non-nil nonFraction and MUST have exactly one ix:nonFraction child element or text."),
                        modelObject=[elt] + childElts, fact=elt.qname)
                    elt.setInvalid()
        if elt.localName == "fraction":
            if elt.isNil:
                ancestorFractions = XmlUtil.ancestors(elt, _ixNS, elt.localName)
                if ancestorFractions:
                    modelXbrl.error(ixMsgCode("fractionAncestors", elt),
                        _("Fact %(fact)s is a nil fraction and MUST not have an ancestor ix:fraction"),
                        modelObject=[elt] + ancestorFractions, fact=elt.qname)
            else:
                nonFrChildren = [e for e in XmlUtil.children(elt, _ixNS, '*') if e.localName not in ("fraction", "numerator", "denominator")]
                if nonFrChildren:
                    modelXbrl.error(ixMsgCode("fractionElementChildren", elt),
                        _("Fact %(fact)s is a non-nil fraction and not have any child elements except ix:fraction, ix:numerator and ix:denominator: %(children)s"),
                        modelObject=[elt] + nonFrChildren, fact=elt.qname, children=", ".join(e.localName for e in nonFrChildren))
                for ancestorFraction in XmlUtil.ancestors(elt, XbrlConst.ixbrl11, "fraction"): # only ix 1.1
                    if normalizeSpace(elt.get("unitRef")) != normalizeSpace(ancestorFraction.get("unitRef")):
                        modelXbrl.error(ixMsgCode("fractionNestedUnitRef", elt),
                            _("Fact %(fact)s fraction and ancestor fractions must have matching unitRefs: %(unitRef)s, %(unitRef2)s"),
                            modelObject=[elt, ancestorFraction], fact=elt.qname, unitRef=elt.get("unitRef"), unitRef2=ancestorFraction.get("unitRef"))
        if elt.localName in ("nonFraction", "numerator", "denominator", "nonNumeric"):
            fmt = elt.format
            if fmt:
                if fmt in _customTransforms:
                    pass
                elif fmt.namespaceURI not in FunctionIxt.ixtNamespaceFunctions:
                    modelXbrl.error(ixMsgCode("invalidTransformation", elt, sect="validation"),
                        _("Fact %(fact)s has unrecognized transformation namespace %(namespace)s"),
                        modelObject=elt, fact=elt.qname, transform=fmt, namespace=fmt.namespaceURI)
                    elt.setInvalid()
                elif fmt.localName not in FunctionIxt.ixtNamespaceFunctions[fmt.namespaceURI]:
                    modelXbrl.error(ixMsgCode("invalidTransformation", elt, sect="validation"),
                        _("Fact %(fact)s has unrecognized transformation name %(name)s"),
                        modelObject=elt, fact=elt.qname, transform=fmt, name=fmt.localName)
                    elt.setInvalid()


    def ixToXhtml(fromRoot):
        toRoot = etree.Element(fromRoot.localName, nsmap={"ix": _ixNS})
        copyNonIxChildren(fromRoot, toRoot)
        for attrTag, attrValue in fromRoot.items():
            checkAttribute(fromRoot, False, attrTag, attrValue)
            if attrTag not in ('version', # used in inline test cases but not valid xhtml
                               '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'):
                toRoot.set(attrTag, attrValue)
        return toRoot

    def copyNonIxChildren(fromElt, toElt, excludeSubtree=False):
        for fromChild in fromElt.iterchildren():
            if isinstance(fromChild, ModelObject):
                isIxNs = fromChild.namespaceURI in XbrlConst.ixbrlAll
                if isIxNs:
                    if fromChild.localName not in ixElements[fromChild.namespaceURI]:
                        modelXbrl.error(ixMsgCode("elementNameInvalid",ns=_ixNS),
                            _("Inline XBRL element name %(element)s is not valid"),
                            modelObject=fromChild, element=str(fromChild.elementQname))
                    else:
                        checkHierarchyConstraints(fromChild)
                        for attrTag, attrValue in fromChild.items():
                            checkAttribute(fromChild, True, attrTag, attrValue)
                        for attrTag in ixAttrRequired[fromChild.namespaceURI].get(fromChild.localName,[]):
                            if fromChild.get(attrTag) is None:
                                modelXbrl.error(ixMsgCode("attributeRequired", fromChild),
                                    _("Attribute %(attribute)s required on element ix:%(element)s"),
                                    modelObject=fromChild, attribute=attrTag, element=fromChild.localName)
                if excludeSubtree or (fromChild.localName in {"references", "resources"} and isIxNs):
                    copyNonIxChildren(fromChild, toElt, excludeSubtree=True)
                else:
                    if fromChild.localName in {"footnote", "nonNumeric", "fraction", "numerator", "denominator", "nonFraction", "continuation", "exclude"} and isIxNs:
                        toChild = etree.Element(_ixNStag + fromChild.localName)
                        toElt.append(toChild)
                        if fromChild.text is not None:
                            toChild.text = fromChild.text
                        if fromChild.tail is not None:
                            toChild.tail = fromChild.tail
                        copyNonIxChildren(fromChild, toChild)
                    elif isIxNs:
                        copyNonIxChildren(fromChild, toElt)
                    else:
                        toChild = etree.Element(fromChild.localName)
                        toElt.append(toChild)
                        for attrTag, attrValue in fromChild.items():
                            checkAttribute(fromChild, False, attrTag, attrValue)
                            toChild.set(attrTag, attrValue)
                        if fromChild.text is not None:
                            if toChild.text:
                                toChild.text += fromChild.text
                            else:
                                toChild.text = fromChild.text
                        if fromChild.tail is not None:
                            if toChild.tail:
                                toChild.tail += fromChild.tail
                            else:
                                toChild.tail = fromChild.tail
                        copyNonIxChildren(fromChild, toChild)
            elif isinstance(fromChild, ModelComment): # preserve non-xsd-whitespac after comments
                if fromChild.tail and not XmlValidate.entirelyWhitespacePattern.match(fromChild.tail):
                    toChild = None # append to parent or last child of parent
                    for lastToElt in toElt.iterchildren(reversed=True):
                        toChild = lastToElt
                        break
                    if toChild is not None: # append onto tail of last child
                        if not toChild.tail:
                            toChild.tail = fromChild.tail
                        else:
                            toChild.tail += fromChild.tail
                    else: # comment is child of toElt, append to text
                        if toElt.text:
                            toElt.text += fromChild.tail
                        else:
                            toElt.text = fromChild.tail
    # copy xhtml elements to fresh tree
    with open(os.path.join(modelXbrl.modelManager.cntlr.configDir, _xhtmlDTD)) as fh:
        dtd = DTD(fh)
    htmlDtdTree = ixToXhtml(elt)
    def dtdErrs():
        errs = []
        elts = [] # elements causing errors for element pointers in error message
        for e in dtd.error_log.filter_from_errors():
            msg = e.message
            path = getattr(e, "path", None)
            if path:
                if path.startswith("/html/"):
                    errPath = "/".join("{{{}}}{}".format(_ixNS if (p.startswith("ixN") or p.startswith("ix:")) else XbrlConst.xhtml,
                                                         "*" if p.startswith("ixN") else p[3:] if p.startswith("ix:") else p)
                                        for p in path[6:].split("/"))
                    errElt = elt.find(errPath)
                    if errElt is not None:
                        if "ixNestedContent" in msg and isinstance(errElt,ModelObject):
                            msg = msg.replace("ixNestedContent", str(errElt.elementQname))
                        msg += " line {}".format(errElt.sourceline)
                        elts.append(errElt)
                # also show use element path
                msg += ", at path {}".format(path)
            errs.append(msg)
        return errs, elts
    try:
        # uncomment to debug:with open("/users/hermf/temp/testDtd.htm", "wb") as fh:
        # uncomment to debug:    fh.write(etree.tostring(htmlDtdTree, encoding="UTF-8", xml_declaration=True, pretty_print=True))
        if not dtd.validate( htmlDtdTree ):
            dtdErrMsgs, dtdErrElts = dtdErrs()
            modelXbrl.error("html:syntaxError",
                _("%(element)s error %(error)s"),
                modelObject=dtdErrElts or elt, element=elt.localName.title(), error=', '.join(dtdErrMsgs))
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
