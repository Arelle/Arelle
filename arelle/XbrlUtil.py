'''
Created on Nov 26, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import xml.dom.minidom
from arelle import (ModelValue, XbrlConst, XmlUtil, XmlValidate)

S_EQUAL = 0 # ordinary S-equality from 2.1 spec
S_EQUAL2 = 1 # XDT definition adds QName comparisions
XPATH_EQ = 2 # XPath EQ on all types

def nodesCorrespond(dts1, elt1, elt2, dts2=None):
    if elt1 is None:
        return elt2 is None #both can be empty sequences (no element) and true
    elif elt2 is None:
        return False
    return sEqual(dts1, elt1, elt2, equalMode=XPATH_EQ, dts2=dts2, excludeIDs=True)

# dts1 is modelXbrl for first element
# dts2 is for second element assumed same unless dts2 and ns2 to ns1 maping table provided
#   (as used in versioning reports and multi instance

def sEqual(dts1, elt1, elt2, equalMode=S_EQUAL, excludeIDs=False, dts2=None, ns2ns1Tbl=None):
    if dts2 is None: dts2 = dts1
    if elt1.localName != elt2.localName:
        return False
    if ns2ns1Tbl and elt2.namespaceURI in ns2ns1Tbl:
        if elt1.namespaceURI != ns2ns1Tbl[elt2.namespaceURI]:
            return False
    elif elt1.namespaceURI != elt2.namespaceURI:
        return False
    # is the element typed?
    modelConcept1 = dts1.qnameConcepts.get(ModelValue.qname(elt1))
    modelConcept2 = dts2.qnameConcepts.get(ModelValue.qname(elt2))
    if (not xEqual(modelConcept1, elt1, elt2, equalMode, modelConcept2=modelConcept2) or 
        attributeSet(dts1, modelConcept1, elt1, (), equalMode, excludeIDs) != 
        attributeSet(dts2, modelConcept2, elt2, (), equalMode, excludeIDs, ns2ns1Tbl)):
        return False
    children1 = childElements(elt1)
    children2 = childElements(elt2)
    if len(children1) != len(children2):
        return False
    for i in range( len(children1) ):
        if not sEqual(dts1, children1[i], children2[i], equalMode, excludeIDs, dts2, ns2ns1Tbl):
            return False
    return True

def attributeSet(modelXbrl, modelConcept, elt, exclusions=(), equalMode=S_EQUAL, excludeIDs=False, ns2ns1Tbl=None):
    attrs = set()
    for i in range(len(elt.attributes)):
        attr = elt.attributes.item(i)
        attrNsURI = attr.namespaceURI
        if ns2ns1Tbl and attrNsURI in ns2ns1Tbl:
            attrNsURI = ns2ns1Tbl[attrNsURI]
        attrName = "{{{0}}}{1}".format(attrNsURI,attr.localName) if attrNsURI else attr.name            
        if (attrName not in exclusions and 
            (attrNsURI is None or attrNsURI not in exclusions) and 
            attr.name not in ("xmlns") and attr.prefix != "xmlns"):
            if attrNsURI:
                qname = ModelValue.qname(attrNsURI, attr.localName)
            else:
                qname = ModelValue.qname(attr.localName)
            baseXsdAttrType = None
            if modelConcept:
                baseXsdAttrType = modelConcept.baseXsdAttrType(qname) if modelConcept else None
            if baseXsdAttrType is None:
                attrObject = modelXbrl.qnameAttributes.get(qname)
                if attrObject:
                    baseXsdAttrType = attrObject.baseXsdType
            if excludeIDs and baseXsdAttrType == "ID":
                continue
            value = xTypeValue(baseXsdAttrType, elt, attr, attr.value, equalMode)
            attrs.add( (qname,value) )
    return attrs

def attributes(modelXbrl, modelConcept, elt, exclusions=(), ns2ns1Tbl=None):
    attributeList = list( attributeSet(modelXbrl, modelConcept, elt, exclusions, ns2ns1Tbl=ns2ns1Tbl) )
    attributeList.sort()
    return tuple( attributeList )
    

def childElements(elt):
    children = []
    for child in elt.childNodes:
        if child.nodeType == 1:
            children.append(child)
    return children

def xEqual(modelConcept1, node1, node2, equalMode=S_EQUAL, modelConcept2=None):
    text1 = XmlUtil.text(node1)
    text2 = XmlUtil.text(node2)
    baseXsdType1 = modelConcept1.baseXsdType if modelConcept1 else None
    if modelConcept1:
        baseXsdType1 = modelConcept1.baseXsdType
        if len(text1) == 0 and modelConcept1.default is not None:
            text1 = modelConcept1.default
        if not modelConcept2:
            modelConcept2 = modelConcept1
    else:
        baseXsdType1 = None
    if modelConcept2:
        baseXsdType2 = modelConcept2.baseXsdType
        if len(text2) == 0 and modelConcept2.default is not None:
            text1 = modelConcept2.default
    else:
        baseXsdType2 = None
    return (xTypeValue(baseXsdType1, node1, node1, text1, equalMode) == 
            xTypeValue(baseXsdType2, node2, node2, text2, equalMode))
    
def xTypeValue(baseXsdType, elt, node, value, equalMode=S_EQUAL):
    try:
        if node.xValid == XmlValidate.VALID:
            xvalue = node.xValue
            if (equalMode == XPATH_EQ or
                isinstance(xvalue,(float,int,bool)) or
                (equalMode == S_EQUAL2 and isinstance(xvalue,(ModelValue.QName)))):
                value = xvalue
    except AttributeError:
        if baseXsdType in ("decimal", "float", "double"):
            try:
                return float(value)
            except ValueError:
                return value
        elif baseXsdType in ("integer",):
            try:
                return int(value)
            except ValueError:
                return value
        elif baseXsdType == "boolean":
            return (value == "true" or value == "1")
        elif equalMode == S_EQUAL2 and baseXsdType == "QName":
            return ModelValue.qname(elt, value)
        elif equalMode == XPATH_EQ and baseXsdType in ("normalizedString","token","language","NMTOKEN","Name","NCName","ID","IDREF","ENTITY"):
            return value.strip()
    return value

def vEqual(modelConcept1, node1, modelConcept2, node2):
    text1 = XmlUtil.text(node1)
    text2 = XmlUtil.text(node2)
    if modelConcept1:
        baseXsdType1 = modelConcept1.baseXsdType
        if len(text1) == 0 and modelConcept1.default is not None:
            text1 = modelConcept1.default
    else:
        baseXsdType1 = None
    if modelConcept2:
        baseXsdType2 = modelConcept2.baseXsdType
        if len(text2) == 0 and modelConcept2.default is not None:
            text1 = modelConcept2.default
    else:
        baseXsdType2 = None
    return xTypeValue(baseXsdType1, node1, node1, text1) == xTypeValue(baseXsdType2, node2, node2, text2)

def typedValue(dts, element, attrQname=None):
    try:
        if attrQname:
            node = element.getAttributeNodeNS(attrQname.namespaceURI,attrQname.localName)
        else:
            node = element
        if node.xValid == XmlValidate.VALID:
            return node.xValue
    except AttributeError:
        if dts:
            XmlValidate.validate(dts, element, recurse=False, attrQname=attrQname)
            return typedValue(None, element, attrQname=attrQname)
        return None
    
