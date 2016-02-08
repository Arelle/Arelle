'''
Created on Sept 1, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.

(originally part of XmlValidate, moved to separate module)
'''
from arelle import XbrlConst, XmlUtil, XmlValidate, ValidateFilingText
from arelle.ModelObject import ModelObject
from lxml import etree
import os, re

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
        "footnote": ("footnoteID",),
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
        "footnote": ("id", "continuedAt", "footnote", "title"),
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
nonIxAttrNS = {
    "footnote": "http://www.w3.org/XML/1998/namespace",
    "fraction": "##other",
    "nonFraction": "##other",
    "nonNumeric": "##other",
    "references": "##other",
    "relationship": "http://www.w3.org/XML/1998/namespace",
    "tuple": "##other"}
ixHierarchyConstraints = {
    # localName: (-rel means doesnt't have relation, +rel means has rel,
    #   &rel means only listed rels
    #   ^rel means must have one of listed rels and can't have any non-listed rels
    #   ?rel means 0 or 1 cardinality
    #   +rel means 1 or more cardinality
    "continuation": (("-ancestor",("hidden",)),),
    "exclude": (("+ancestor",("continuation", "footnote", "nonNumeric")),),
    "denominator": (("-descendant",('*',)),),
    "header": (("&child-sequence", ('hidden','references','resources')), # can only have these children, in order, no others
               ("?child-choice", ('hidden',)),
               ("?child-choice", ('resources',))),
    "hidden": (("+parent", ("header",)),
               ("&child-choice", ('footnote', 'fraction', 'nonFraction', 'nonNumeric', 'tuple')),
               ("+child-choice", ('footnote', 'fraction', 'nonFraction', 'nonNumeric', 'tuple'))),
    "footnote": (("+child-or-text",('*',)),),
    "numerator": (("-descendant",('*',)),),
    "references": (("+parent",("header",)),),
    "relationship": (("+parent",("resources",)),),
    "resources": (("+parent",("header",)),
                  ("&child-choice", ('relationship', 
                                     '{http://www.xbrl.org/2003/linkbase}roleRef', '{http://www.xbrl.org/2003/linkbase}arcroleRef', 
                                     '{http://www.xbrl.org/2003/instance}context', '{http://www.xbrl.org/2003/instance}unit'))),
    "tuple": (("-child-choice",("continuation", "exclude", "denominator", "footnote", "numerator", "header", "hidden",
                                "references", "relationship", "resources")),)
    }

def xhtmlValidate(modelXbrl, elt):
    from lxml.etree import DTD, XMLSyntaxError
    ixNsStartTags = ["{" + ns + "}" for ns in XbrlConst.ixbrlAll]
    isEFM = modelXbrl.modelManager.disclosureSystem.validationType == "EFM"
    
    def checkAttribute(elt, isIxElt, attrTag, attrValue):
        if attrTag.startswith("{"):
            ns, sep, localName = attrTag[1:].partition("}")
        else:
            ns = None
            localName = attrTag
        if ns is not None and ns not in XbrlConst.ixbrlAll:
            if isIxElt:
                allowedNs = nonIxAttrNS.get(elt.localName, None)
                if allowedNs != "##other" and ns != allowedNs:
                    modelXbrl.error("ix:qualifiedAttributeNotExpected",
                        _("Inline XBRL element %(element)s: has qualified attribute %(name)s"),
                        modelObject=elt, element=str(elt.elementQname), name=attrTag)
            else:
                if ns in XbrlConst.ixbrlAll:
                    modelXbrl.error("ix:inlineAttributeMisplaced",
                        _("Inline XBRL attributes are not allowed on html elements: ix:%(name)s"),
                        modelObject=elt, name=localName)
                elif ns not in {XbrlConst.xml, XbrlConst.xsi, XbrlConst.xhtml}:
                    modelXbrl.error("ix:extensionAttributeMisplaced",
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
                
                if localName not in ixAttrDefined[elt.namespaceURI][elt.localName]:
                    raise KeyError
                disallowedXbrliAttrs = ({"scheme", "periodType",     "balance", "contextRef", "unitRef", "precision", "decimals"} -
                                        {"fraction": {"contextRef", "unitRef"},
                                         "nonFraction": {"contextRef", "unitRef", "decimals", "precision"},
                                         "nonNumeric": {"contextRef"}}.get(elt.localName, set()))
                disallowedAttrs = set(a for a in disallowedXbrliAttrs if elt.get(a) is not None)
                if disallowedAttrs:
                    modelXbrl.error("ix:inlineElementAttributes",
                        _("Inline XBRL element %(element)s has disallowed attributes %(attributes)s"),
                        modelObject=elt, element=elt.elementQname, attributes=", ".join(disallowedAttrs))
            except KeyError:
                modelXbrl.error("ix:attributeNotExpected",
                    _("Attribute %(attribute)s is not expected on element ix:%(element)s"),
                    modelObject=elt, attribute=attrTag, element=elt.localName)
                
    def checkHierarchyConstraints(elt):
        constraints = ixHierarchyConstraints.get(elt.localName)
        if constraints:
            for _rel, names in constraints:
                reqt = _rel[0]
                rel = _rel[1:]
                if reqt in ('&', '^'):
                    nameFilter = ('*',)
                else:
                    nameFilter = names
                if nameFilter == ('*',):
                    namespaceFilter = namespacePrefix = '*'
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
                    relations += XmlUtil.innerTextNodes(elt, ixExclude=True, ixEscape=False, ixContinuation=False)
                issue = ''
                if reqt == '^':
                    if not any(r.localName in names and r.namespaceURI == elt.namespaceURI
                               for r in relations):
                        issue = " and is missing one of " + ', '.join(names)
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
                if ((reqt == '+' and not relations) or
                    (reqt == '-' and relations) or
                    (issue)):
                    code = "ix:" + {
                           'ancestor': "ancestorNode",
                           'parent': "parentNode",
                           'child-choice': "childNodes",
                           'child-sequence': "childNodes",
                           'child-or-text': "childNodesOrText",
                           'descendant': "descendantNodes"}[rel] + {
                            '+': "Required",
                            '-': "Disallowed",
                            '&': "Allowed",
                            '^': "Specified"}.get(reqt, "Specified")
                    msg = _("Inline XBRL 1.0 ix:{0} {1} {2} {3} {4} element").format(
                                elt.localName,
                                {'+': "must", '-': "may not", '&': "may only",
                                 '?': "may", '+': "must"}[reqt],
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
                                issue)
                    modelXbrl.error(code, msg, 
                                    modelObject=[elt] + relations, requirement=reqt)
                
    def ixToXhtml(fromRoot):
        toRoot = etree.Element(fromRoot.localName)
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
                        modelXbrl.error("ix:elementNameInvalid",
                            _("Inline XBRL element name %(element)s is not valid"),
                            modelObject=fromChild, element=str(fromChild.elementQname))
                    else:
                        checkHierarchyConstraints(fromChild)
                        for attrTag, attrValue in fromChild.items():
                            checkAttribute(fromChild, True, attrTag, attrValue)
                        for attrTag in ixAttrRequired[fromChild.namespaceURI].get(fromChild.localName,[]):
                            if fromChild.get(attrTag) is None:
                                modelXbrl.error("ix:attributeRequired",
                                    _("Attribute %(attribute)s required on element ix:%(element)s"),
                                    modelObject=elt, attribute=attrTag, element=fromChild.localName)
                if excludeSubtree or (fromChild.localName in {"references", "resources"} and isIxNs):
                    copyNonIxChildren(fromChild, toElt, excludeSubtree=True)
                else:
                    if fromChild.localName in {"footnote", "nonNumeric", "continuation"} and isIxNs:
                        toChild = etree.Element("ixNestedContent")
                        toElt.append(toChild)
                        copyNonIxChildren(fromChild, toChild)
                        if fromChild.text is not None:
                            toChild.text = fromChild.text
                        if fromChild.tail is not None:
                            toChild.tail = fromChild.tail
                    elif isIxNs:
                        copyNonIxChildren(fromChild, toElt)
                    else:
                        toChild = etree.Element(fromChild.localName)
                        toElt.append(toChild)
                        copyNonIxChildren(fromChild, toChild)
                        for attrTag, attrValue in fromChild.items():
                            checkAttribute(fromChild, False, attrTag, attrValue)
                            toChild.set(attrTag, attrValue)
                        if fromChild.text is not None:
                            toChild.text = fromChild.text
                        if fromChild.tail is not None:
                            toChild.tail = fromChild.tail    
                            
    # copy xhtml elements to fresh tree
    with open(os.path.join(modelXbrl.modelManager.cntlr.configDir, "xhtml1-strict-ix.dtd")) as fh:
        dtd = DTD(fh)
    try:
        #with open("/users/hermf/temp/testDtd.htm", "w") as fh:
        #    fh.write(etree.tostring(ixToXhtml(elt), encoding=_STR_UNICODE, pretty_print=True))
        if not dtd.validate( ixToXhtml(elt) ):
            modelXbrl.error("ix:DTDelementUnexpected",
                _("%(element)s error %(error)s"),
                modelObject=elt, element=elt.localName.title(),
                error=', '.join(e.message for e in dtd.error_log.filter_from_errors()))
        if isEFM:
            ValidateFilingText.validateHtmlContent(modelXbrl, elt, elt, "InlineXBRL", "EFM.5.02.02.") 
    except XMLSyntaxError as err:
        modelXbrl.error("ix:DTDerror",
            _("%(element)s error %(error)s"),
            modelObject=elt, element=elt.localName.title(), error=dtd.error_log.filter_from_errors())

