'''
Created on Nov 26, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import xml.dom.minidom
from arelle import (ModelValue, XbrlConst, XmlUtil, XmlValidate)
from arelle.ModelObject import ModelObject

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

def equalityHash(elt, equalMode=S_EQUAL, excludeIDs=False):
    if not isinstance(elt, ModelObject):
        return hash(None)
    try:
        if equalMode == S_EQUAL:
            return elt._hashSEqual
        else:
            return elt._hashXpathEqual
    except AttributeError:
        dts = elt.modelXbrl
        if not hasattr(elt,"xValid"):
            XmlValidate.validate(dts, elt)
        _hash = hash((elt.sValue if equalMode == S_EQUAL else elt.xValue,
                      tuple(attributeDict(dts, elt, (), equalMode, excludeIDs).items()),
                      tuple(hash(dts,child,equalMode,excludeIDs) for child in childElements(elt))
                      ))
        if equalMode == S_EQUAL:
            elt._hashSEqual = _hash
        else:
            elt._hashXpathEqual = _hash
        return _hash

def sEqual(dts1, elt1, elt2, equalMode=S_EQUAL, excludeIDs=False, dts2=None, ns2ns1Tbl=None):
    if dts2 is None: dts2 = dts1
    if elt1.localName != elt2.localName:
        return False
    if ns2ns1Tbl and elt2.namespaceURI in ns2ns1Tbl:
        if elt1.namespaceURI != ns2ns1Tbl[elt2.namespaceURI]:
            return False
    elif elt1.namespaceURI != elt2.namespaceURI:
        return False
    if not hasattr(elt1,"xValid"):
        XmlValidate.validate(dts1, elt1)
    if not hasattr(elt2,"xValid"):
        XmlValidate.validate(dts2, elt2)
    if (not xEqual(elt1, elt2, equalMode) or 
        attributeDict(dts1, elt1, (), equalMode, excludeIDs) != 
        attributeDict(dts2, elt2, (), equalMode, excludeIDs, ns2ns1Tbl)):
        return False
    children1 = childElements(elt1)
    children2 = childElements(elt2)
    if len(children1) != len(children2):
        return False
    for i in range( len(children1) ):
        if not sEqual(dts1, children1[i], children2[i], equalMode, excludeIDs, dts2, ns2ns1Tbl):
            return False
    return True

def attributeDict(modelXbrl, elt, exclusions=set(), equalMode=S_EQUAL, excludeIDs=False, ns2ns1Tbl=None, keyByTag=False):
    if not hasattr(elt,"xValid"):
        XmlValidate.validate(modelXbrl, elt)
    attrs = {}
    for attrTag, attrValue in elt.items():
        ns, sep, localName = attrTag.partition('}')
        attrNsURI = ns[1:] if sep else None
        if ns2ns1Tbl and attrNsURI in ns2ns1Tbl:
            attrNsURI = ns2ns1Tbl[attrNsURI]
        if (attrTag not in exclusions and 
            (attrNsURI is None or attrNsURI not in exclusions)):
            if keyByTag:
                qname = attrTag
            elif attrNsURI:
                qname = ModelValue.QName(None, attrNsURI, localName)
            else:
                qname = ModelValue.QName(None, None, attrTag)
            xValid, xValue, sValue = elt.xAttributes[attrTag]
            if excludeIDs and xValid == XmlValidate.VALID_ID:
                continue
            attrs[qname] = sValue if equalMode == S_EQUAL2 else xValue
    return attrs

def attributes(modelXbrl, elt, exclusions=set(), ns2ns1Tbl=None, keyByTag=False):
    a = attributeDict(modelXbrl, elt, exclusions, ns2ns1Tbl=ns2ns1Tbl, keyByTag=keyByTag)
    return tuple( (k,a[k]) for k in sorted(a.keys()) )    

def childElements(elt):
    children = []
    for child in elt.getchildren():
        if isinstance(child,ModelObject):
            children.append(child)
    return children

def xEqual(elt1, elt2, equalMode=S_EQUAL):
    if equalMode == S_EQUAL:
        return elt1.sValue == elt2.sValue
    else:
        return elt1.xValue == elt2.xValue
    
def vEqual(elt1, elt2):
    if not hasattr(elt1,"xValid"):
        XmlValidate.validate(elt1.modelXbrl, elt1)
    if not hasattr(elt2,"xValid"):
        XmlValidate.validate(elt2.modelXbrl, elt2)
    return elt1.sValue == elt2.sValue

def typedValue(dts, element, attrQname=None):
    try:
        if element.xValid == XmlValidate.VALID:
            if attrQname:
                valid, xValue, sValue = element.xAttributes[attrQname.clarkNotation]
            else:
                xValue = element.xValue
            return xValue
    except AttributeError:
        if dts:
            XmlValidate.validate(dts, element, recurse=False, attrQname=attrQname)
            return typedValue(None, element, attrQname=attrQname)
    return None
