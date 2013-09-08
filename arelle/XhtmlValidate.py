'''
Created on Sept 1, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.

(originally part of XmlValidate, moved to separate module)
'''
from arelle import XbrlConst, XmlUtil, XmlValidate
from arelle.ModelObject import ModelObject
from lxml import etree
import os, re

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
ixHierarchyConstraints = {
    # localName: (-rel means doesnt't have relation, +rel means has rel,
    #   &rel means only listed rels
    #   ^rel means must have one of listed rels and can't have any non-listed rels
    #   ?rel means 0 or 1 cardinality
    #   +rel means 1 or more cardinality
    "continuation": (("-ancestor",("hidden",)),),
    "exclude": (("+ancestor",("continuation", "footnote", "nonNumeric")),),
    "denominator": (("-descendant",('*',)),),
    "numerator": (("-descendant",('*',)),),
    "header": (("&child", ('hidden','references','resources')), # can only have these children, no others
               ("?child", ('hidden',)),
               ("?child", ('resources',))),
    "hidden": (("+parent", ("header",)),
               ("&child", ('footnote', 'fraction', 'nonFraction', 'nonNumeric', 'tuple')),
               ("+child", ('footnote', 'fraction', 'nonFraction', 'nonNumeric', 'tuple'))),
    "references": (("+parent",("header",)),),
    "relationship": (("+parent",("resources",)),),
    "resources": (("+parent",("header",)),),
    "tuple": (("-child",("continuation", "exclude", "denominator", "footnote", "numerator", "header", "hidden",
                         "references", "relationship", "resources")),)
    }

def xhtmlValidate(modelXbrl, elt):
    from lxml.etree import DTD, XMLSyntaxError
    ixNsStartTags = ["{" + ns + "}" for ns in XbrlConst.ixbrlAll]
    
    def checkAttribute(elt, isIxElt, attrTag, attrValue):
        if attrTag.startswith("{"):
            ns, sep, localName = attrTag[1:].partition("}")
            if isIxElt:
                if ns not in (XbrlConst.xml, XbrlConst.xsi):
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
                _xsdType = ixAttrType[elt.namespaceURI][attrTag]
                if isinstance(_xsdType, dict):
                    baseXsdType = _xsdType["type"]
                    facets = _xsdType
                else:
                    baseXsdType = _xsdType
                    facets = None
                XmlValidate.validateValue(modelXbrl, elt, attrTag, baseXsdType, attrValue, facets=facets)
                
                disallowedXbrliAttrs = ({"scheme", "periodType", "balance", "contextRef", "unitRef", "precision", "decimals"} -
                                        {"fraction": {"contextRef", "unitRef"},
                                         "nonFraction": {"contextRef", "unitRef", "decimals", "precision"},
                                         "nonNumeric": {"contextRef"}}.get(elt.localName, set()))
                disallowedAttrs = [a for a in disallowedXbrliAttrs if elt.get(a) is not None]
                if disallowedAttrs:
                    modelXbrl.error("ix:inlineElementAttributes",
                        _("Inline XBRL element %(element)s has disallowed attributes %(attributes)s"),
                        modelObject=elt, element=elt.elementQname, attributes=", ".join(disallowedAttrs))
            except KeyError:
                modelXbrl.error("ix:attributeNotExpected",
                    _("Attribute %(attribute)s is not expected on element element ix:%(element)s"),
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
                relations = {"ancestor": XmlUtil.ancestor, 
                             "parent": XmlUtil.parent, 
                             "child": XmlUtil.children, 
                             "descendant": XmlUtil.descendants}[rel](
                            elt, 
                            '*' if nameFilter == ('*',) else elt.namespaceURI,
                            nameFilter)
                if rel in ("ancestor", "parent"):
                    if relations is None: relations = []
                    else: relations = [relations]
                issue = ''
                if reqt == '^':
                    if not any(r.localName in names and r.namespaceURI == elt.namespaceURI
                               for r in relations):
                        issue = " and is missing one of " + ', '.join(names)
                if reqt in ('&', '^'):
                    disallowed = [str(r.elementQname)
                                  for r in relations
                                  if r.localName not in names or r.namespaceURI != elt.namespaceURI]
                    if disallowed:
                        issue += " and may not have " + ", ".join(disallowed)
                if reqt == '?' and len(relations) > 1:
                    issue = " may only have 0 or 1 but {0} present ".format(len(relations))
                if reqt == '+' and len(relations) == 0:
                    issue = " must have more than 1 but none present "
                if ((reqt == '+' and not relations) or
                    (reqt == '-' and relations) or
                    (issue)):
                    code = "ix:" + {
                           'ancestor': "ancestorNode",
                           'parent': "parentNode",
                           'child': "childNodes",
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
                                 'child': "have child",
                                 'descendant': "have as descendant"}[rel],
                                ', '.join(str(r.elementQname) for r in relations)
                                if names == ('*',) and relations else
                                ", ".join("ix:" + n for n in names),
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

    def copyNonIxChildren(fromElt, toElt):
        for fromChild in fromElt.iterchildren():
            if isinstance(fromChild, ModelObject):
                isIxNs = fromChild.namespaceURI in XbrlConst.ixbrlAll
                if isIxNs:
                    checkHierarchyConstraints(fromChild)
                    for attrTag, attrValue in fromChild.items():
                        checkAttribute(fromChild, True, attrTag, attrValue)
                    for attrTag in ixAttrRequired[fromChild.namespaceURI].get(fromChild.localName,[]):
                        if fromChild.get(attrTag) is None:
                            modelXbrl.error("ix:attributeRequired",
                                _("Attribute %(attribute)s required on element ix:%(element)s"),
                                modelObject=elt, attribute=attrTag, element=fromChild.localName)
                if not (fromChild.localName in {"references", "resources"} and isIxNs):
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
        if not dtd.validate( ixToXhtml(elt) ):
            modelXbrl.error("xhmlDTD:elementUnexpected",
                _("%(element)s error %(error)s"),
                modelObject=elt, element=elt.localName.title(),
                error=', '.join(e.message for e in dtd.error_log.filter_from_errors()))
    except XMLSyntaxError as err:
        modelXbrl.error("xmlDTD:error",
            _("%(element)s error %(error)s"),
            modelObject=elt, element=elt.localName.title(), error=dtd.error_log.filter_from_errors())

