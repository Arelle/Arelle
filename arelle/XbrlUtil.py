'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
from typing import Any, Sequence, TYPE_CHECKING
import math
from arelle.ModelValue import QName, DateTime
from arelle.ModelObject import ModelObject, ModelAttribute
from arelle.XmlValidate import UNKNOWN, VALID, VALID_ID, validate as xmlValidate

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl

S_EQUAL: int = 0 # ordinary S-equality from 2.1 spec
S_EQUAL2: int = 1 # XDT definition adds QName comparisons
XPATH_EQ: int = 2 # XPath EQ on all types
VALIDATE_BY_STRING_VALUE: int = 3

NO_IDs_EXCLUDED: int = 0
ALL_IDs_EXCLUDED: int = 1
TOP_IDs_EXCLUDED: int = 2 # only ancestor IDs are excluded

def nodesCorrespond(
    dts1: ModelXbrl,
    elt1: ModelObject | ModelAttribute | None,
    elt2: ModelObject | ModelAttribute | None,
    dts2: ModelXbrl | None = None,
    equalMode: int = XPATH_EQ,
    excludeIDs: int = ALL_IDs_EXCLUDED
) -> bool:
    if elt1 is None:
        return elt2 is None #both can be empty sequences (no element) and true
    elif elt2 is None or not isinstance(elt1, (ModelObject,ModelAttribute)) or not isinstance(elt2, (ModelObject,ModelAttribute)):
        return False
    # can accept either modelElements or modelAttributes
    if isinstance(elt1,ModelAttribute):
        if isinstance(elt2,ModelAttribute):
            return elt1.attrTag == elt2.attrTag and elt1.xValue == elt2.xValue
        else:
            return False
    elif isinstance(elt2,ModelAttribute):
        return False
    # sEqual only accepts modelElements
    return sEqual(dts1, elt1, elt2, equalMode=equalMode, dts2=dts2, excludeIDs=ALL_IDs_EXCLUDED)

# dts1 is modelXbrl for first element
# dts2 is for second element assumed same unless dts2 and ns2 to ns1 mapping table provided
#   (as used in versioning reports and multi instance

def equalityHash(
    elt: ModelObject | Sequence[ModelObject],
    equalMode: int = S_EQUAL,
    excludeIDs: int = NO_IDs_EXCLUDED
) -> int:
    if isinstance(elt, ModelObject):
        try:
            if equalMode == S_EQUAL:
                return elt._hashSEqual
            else:
                return elt._hashXpathEqual
        except AttributeError:
            dts = elt.modelXbrl
            from arelle.ModelXbrl import ModelXbrl
            assert isinstance(dts, ModelXbrl), 'dts is not an instance of ModelXbrl'
            if not hasattr(elt,"xValid"):
                xmlValidate(dts, elt)
            hashableValue = elt.sValue if equalMode == S_EQUAL else elt.xValue
            if isinstance(hashableValue,float) and math.isnan(hashableValue):
                hashableValue = (hashableValue,elt)  # type: ignore[assignment]    # ensure this NaN only compares to itself and no other NaN
            _hash = hash((elt.elementQname,
                          hashableValue,
                          tuple(sorted(attributeDict(dts, elt, set(), equalMode, excludeIDs, distinguishNaNs=True).items(),
                                       key=lambda item: item[0])), # must sort so attrs always hashed in same order
                          tuple(equalityHash(child,equalMode,excludeIDs) for child in childElements(elt))
                          ))
            if equalMode == S_EQUAL:
                elt._hashSEqual = _hash
            else:
                elt._hashXpathEqual = _hash
            return _hash
    elif isinstance(elt, (tuple,list,set)):
        return hash( tuple(equalityHash(i) for i in elt) )
    else:
        return hash(None)

def sEqual(
    dts1: ModelXbrl,
    elt1: ModelObject,
    elt2: ModelObject,
    equalMode: int = S_EQUAL,
    excludeIDs: int = NO_IDs_EXCLUDED,
    dts2: ModelXbrl | None = None,
    ns2ns1Tbl: dict[str, str] | None = None
) -> bool:
    if dts2 is None: dts2 = dts1
    if elt1.localName != elt2.localName:
        return False
    if ns2ns1Tbl and elt2.namespaceURI in ns2ns1Tbl:
        if elt1.namespaceURI != ns2ns1Tbl[elt2.namespaceURI]:
            return False
    elif elt1.namespaceURI != elt2.namespaceURI:
        return False
    if not hasattr(elt1,"xValid"):
        xmlValidate(dts1, elt1)
    if not hasattr(elt2,"xValid"):
        xmlValidate(dts2, elt2)
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
        attributeDict(dts1, elt1, set(), equalMode, excludeIDs) !=
        attributeDict(dts2, elt2, set(), equalMode, excludeIDs, ns2ns1Tbl)):
        return False
    excludeChildIDs = excludeIDs if excludeIDs != TOP_IDs_EXCLUDED else NO_IDs_EXCLUDED
    for i in range( len(children1) ):
        if not sEqual(dts1, children1[i], children2[i], equalMode, excludeChildIDs, dts2, ns2ns1Tbl):
            return False
    return True

def attributeDict(
    modelXbrl: ModelXbrl,
    elt: ModelObject,
    exclusions: set[str] = set(),
    equalMode: int = S_EQUAL,
    excludeIDs: int = NO_IDs_EXCLUDED,
    ns2ns1Tbl: dict[str, str] | None = None,
    keyByTag: bool = False,
    distinguishNaNs: bool = False
) -> dict[QName, Any]:  # value can be any element value
    if not hasattr(elt,"xValid"):
        xmlValidate(modelXbrl, elt)
    attrs = {}
    # TBD: replace with validated attributes
    for modelAttribute in getattr(elt, 'xAttributes', {}).values():
        attrTag = modelAttribute.attrTag
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
                if excludeIDs and getattr(modelAttribute, "xValid", 0) == VALID_ID:
                    continue
                if modelAttribute.xValid != UNKNOWN:
                    value = modelAttribute.sValue if equalMode <= S_EQUAL2 else modelAttribute.xValue
                else: # unable to validate, no schema definition, use string value of attribute
                    value = modelAttribute.text
                if distinguishNaNs and isinstance(value,float) and math.isnan(value):
                    value = (value,elt)
                attrs[qname] = value
            except KeyError:
                pass  # what should be done if attribute failed to have psvi value
    return attrs

def attributes(
    modelXbrl: ModelXbrl,
    elt: ModelObject,
    exclusions: set[str] = set(),
    ns2ns1Tbl: dict[str, str] | None = None,
    keyByTag: bool = False
) -> tuple[tuple[QName, Any], ...]:
    a = attributeDict(modelXbrl, elt, exclusions, ns2ns1Tbl=ns2ns1Tbl, keyByTag=keyByTag)
    return tuple( (k,a[k]) for k in sorted(a.keys()) )

def childElements(elt: ModelObject) -> list[ModelObject]:
    return [child for child in elt if isinstance(child,ModelObject)]

def xEqual(elt1: ModelObject, elt2: ModelObject, equalMode: int = S_EQUAL) -> bool:
    if not hasattr(elt1,"xValid"):
        xmlValidate(elt1.modelXbrl, elt1)
    if not hasattr(elt2,"xValid"):
        xmlValidate(elt2.modelXbrl, elt2)
    if equalMode == VALIDATE_BY_STRING_VALUE:
        return elt1.stringValue == elt2.stringValue
    elif equalMode == S_EQUAL: # formula WG e-mail 2018-09-06: or (equalMode == S_EQUAL2 and not isinstance(elt1.sValue, QName)):
        return elt1.sValue == elt2.sValue
    else: # includes dimension S-equal2, use xpath-2 equality.
        if isinstance(elt1.xValue, DateTime) \
            and isinstance(elt2.xValue, DateTime) \
                and elt1.xValue.dateOnly != elt2.xValue.dateOnly:
            return False
        return elt1.xValue == elt2.xValue

def vEqual(elt1: ModelObject, elt2: ModelObject) -> bool:
    if not hasattr(elt1,"xValid"):
        xmlValidate(elt1.modelXbrl, elt1)
    if not hasattr(elt2,"xValid"):
        xmlValidate(elt2.modelXbrl, elt2)
    return elt1.sValue == elt2.sValue

def typedValue(
    dts: ModelXbrl | None,
    element: ModelObject,
    attrQname: QName | None = None
) -> Any:  # This can by any type
    try:
        if attrQname: # PSVI attribute value
            modelAttribute = getattr(element, 'xAttributes')[attrQname.clarkNotation]
            if modelAttribute.xValid >= VALID:
                return modelAttribute.xValue
        else: # PSVI element value (of text)
            if getattr(element, 'xValid') >= VALID:
                return element.xValue
    except (AttributeError, KeyError):
        if dts:
            xmlValidate(dts, element, recurse=False, attrQname=attrQname)
            return typedValue(None, element, attrQname=attrQname)
    return None
