'''
Created on Nov 26, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import xml.dom.minidom, math
from arelle import XbrlConst, XmlUtil
from arelle.ModelValue import qname, QName
from arelle.arelle_c import ModelObject
from arelle.XmlValidate import UNKNOWN, VALID, VALID_ID, validate as xmlValidate

S_EQUAL = 0 # ordinary S-equality from 2.1 spec
S_EQUAL2 = 1 # XDT definition adds QName comparisions
XPATH_EQ = 2 # XPath EQ on all types
VALIDATE_BY_STRING_VALUE = 3

NO_VALUE = "@no-value@" # singleton for no value

NO_IDs_EXCLUDED = 0
ALL_IDs_EXCLUDED = 1
TOP_IDs_EXCLUDED = 2 # only ancestor IDs are excluded

def nodesCorrespond(dts1, elt1, elt2, dts2=None, equalMode=XPATH_EQ, excludeIDs=ALL_IDs_EXCLUDED):
    if elt1 is None:
        return elt2 is None #both can be empty sequences (no element) and true
    elif elt2 is None or not isinstance(elt1, ModelObject) or not isinstance(elt2, ModelObject):
        return False
    # can accept either modelElements or modelAttributes
    #if isinstance(elt1,ModelAttribute):
    #    if isinstance(elt2,ModelAttribute):
    #        return elt1.attrTag == elt2.attrTag and elt1.xValue == elt2.xValue
    #    else:
    #        return False
    #elif isinstance(elt2,ModelAttribute):
    #    return False
    # sEqual only accepts modelElements
    return sEqual(dts1, elt1, elt2, equalMode=equalMode, dts2=dts2, excludeIDs=ALL_IDs_EXCLUDED)

# dts1 is modelXbrl for first element
# dts2 is for second element assumed same unless dts2 and ns2 to ns1 maping table provided
#   (as used in versioning reports and multi instance

def equalityHash(elt, equalMode=S_EQUAL, excludeIDs=NO_IDs_EXCLUDED):
    
    if isinstance(elt, ModelObject):
        _hash = elt.get("=hashSEqual", NO_VALUE) if equalMode == S_EQUAL else elt.get("=hashXpathEqual", NO_VALUE)
        if _hash is NO_VALUE:
            dts = elt.modelXbrl
            hashableValue = elt.sValue(elt.xValue) if equalMode == S_EQUAL else elt.xValue
            if isinstance(hashableValue,float) and math.isnan(hashableValue): 
                hashableValue = (hashableValue,elt)    # ensure this NaN only compares to itself and no other NaN
            _hash = hash((elt.elementQName,
                          hashableValue,
                          tuple(sorted(attributeDict(dts, elt, (), equalMode, excludeIDs, distinguishNaNs=True).items(),
                                       key=lambda item: item[0])), # must sort so attrs always hashed in same order
                          tuple(equalityHash(child,equalMode,excludeIDs) for child in elt.iterchildren())
                          ))
            elt.set("=hashSEqual" if equalMode == S_EQUAL else "=hashXpathEqual", _hash)
        return _hash
    elif isinstance(elt, (tuple,list,set)):
        return hash( tuple(equalityHash(i) for i in elt) )
    else:
        return hash(None)

def sEqual(dts1, elt1, elt2, equalMode=S_EQUAL, excludeIDs=NO_IDs_EXCLUDED, dts2=None, ns2ns1Tbl=None):
    if dts2 is None: dts2 = dts1
    if elt1.localName != elt2.localName:
        return False
    if ns2ns1Tbl and elt2.namespaceURI in ns2ns1Tbl:
        if elt1.namespaceURI != ns2ns1Tbl[elt2.namespaceURI]:
            return False
    elif elt1.namespaceURI != elt2.namespaceURI:
        return False
    #if not hasattr(elt1,"xValid"):
    #    xmlValidate(dts1, elt1)
    #if not hasattr(elt2,"xValid"):
    #    xmlValidate(dts2, elt2)
    children1 = childElements(elt1)
    children2 = childElements(elt2)
    if len(children1) != len(children2):
        return False
    if (not xEqual(elt1, elt2,
                   # must use stringValue for nested contents of mixed content 
                   # ... this is now in xValue for mixed content
                   # VALIDATE_BY_STRING_VALUE if len(children1) and elt1.xValid == VALID else
                   equalMode
                   ) or 
        attributeDict(dts1, elt1, (), equalMode, excludeIDs) != 
        attributeDict(dts2, elt2, (), equalMode, excludeIDs, ns2ns1Tbl)):
        return False
    excludeChildIDs = excludeIDs if excludeIDs != TOP_IDs_EXCLUDED else NO_IDs_EXCLUDED
    for i in range( len(children1) ):
        if not sEqual(dts1, children1[i], children2[i], equalMode, excludeChildIDs, dts2, ns2ns1Tbl):
            return False
    return True

def attributeDict(modelXbrl, elt, exclusions=set(), equalMode=S_EQUAL, excludeIDs=NO_IDs_EXCLUDED, ns2ns1Tbl=None, keyByTag=False, distinguishNaNs=False):
    #if not hasattr(elt,"xValid"):
    #    xmlValidate(modelXbrl, elt)
    attrs = {}
    # TBD: replace with validated attributes
    for attrTag, xValue in elt.iterattrs():
        ns, sep, localName = attrTag.partition('}')
        attrNsURI = ns[1:] if sep else None
        if ns2ns1Tbl and attrNsURI in ns2ns1Tbl:
            attrNsURI = ns2ns1Tbl[attrNsURI]
        if (attrTag not in exclusions and 
            (attrNsURI is None or attrNsURI not in exclusions)):
            if keyByTag:
                qname = attrTag
            elif attrNsURI is not None:
                qname = QName(None, attrNsURI, localName)
            else:
                qname = QName(None, None, attrTag)
            try:
                if excludeIDs:
                    concept = elt.elementDeclaration()
                    if concept is not None and concept.isAttrId(attrTag):
                        continue
                if equalMode <= S_EQUAL2:
                    value = elt.sValue(xValue)
                else:
                    value = xValue
                if distinguishNaNs and isinstance(value,float) and math.isnan(value):
                    value = (value,elt)
                attrs[qname] = value
            except KeyError:
                pass  # what should be done if attribute failed to have psvi value
    return attrs

def attributes(modelXbrl, elt, exclusions=set(), ns2ns1Tbl=None, keyByTag=False):
    a = attributeDict(modelXbrl, elt, exclusions, ns2ns1Tbl=ns2ns1Tbl, keyByTag=keyByTag)
    return tuple( (k,a[k]) for k in sorted(a.keys()) )    

def childElements(elt):
    return [child for child in elt.iterchildren()]

def xEqual(elt1, elt2, equalMode=S_EQUAL):
    #if not hasattr(elt1,"xValid"):
    #    xmlValidate(elt1.modelXbrl, elt1)
    #if not hasattr(elt2,"xValid"):
    #    xmlValidate(elt2.modelXbrl, elt2)
    if equalMode == VALIDATE_BY_STRING_VALUE:
        return elt1.stringValue == elt2.stringValue
    elif equalMode == S_EQUAL: # formula WG e-mail 2018-09-06: or (equalMode == S_EQUAL2 and not isinstance(elt1.sValue, QName)):
        return elt1.sValue(elt1.xValue) == elt2.sValue(elt2.xValue)
    else: # includes dimension S-equal2, use xpath-2 equality.
        return elt1.xValue == elt2.xValue
    
def vEqual(elt1, elt2):
    #if not hasattr(elt1,"xValid"):
    #    xmlValidate(elt1.modelXbrl, elt1)
    #if not hasattr(elt2,"xValid"):
    #    xmlValidate(elt2.modelXbrl, elt2)
    return elt1.sValue(elt1.xValue) == elt2.sValue(elt2.xValue)

def typedValue(dts, element, attrQname=None):
    try:
        if attrQname: # PSVI attribute value
            clarkName = attrQname.clarkNotation
            if element.attrs is not None and clarkName in element.attrs:
                return element.attrs[clarkName]
            for attrTag, attrXvalue in element.iterattrs():
                if clarkName == attrTag:
                    return attrXvalue
        else: # PSVI element value (of text)
            if element.xValid >= VALID:
                return element.xValue
    except (AttributeError, KeyError):
        if dts:
            xmlValidate(dts, element, recurse=False, attrQname=attrQname)
            return typedValue(None, element, attrQname=attrQname)
    return None
