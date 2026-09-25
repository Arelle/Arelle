"""
See COPYRIGHT.md for copyright information.

Unit signatures.

A datatype's `unitComposition` is an object of two multisets of datatype QNames: a
numerator naming the datatypes whose units are multiplied together to form the units of
that datatype, and a denominator naming the datatypes whose units divide them.  Expanding a composition recursively gives the
datatype's unit signature, a pair of multisets of base datatypes.

A fact's unit dimension is valid where the signature of its unit dimension value equals
the signature of the fact's datatype, an absent unit dimension being the pure unit, whose
signature is empty.  This replaces the earlier rule, which compared the concept's
datatype with the datatype of each measure and could not accept, say, three feet measures
for a volume.

Reference: tavi.md#sec-fact-unit-validation
"""
from collections import Counter

from arelle.ModelValue import QName, qname

from .XbrlConcept import XbrlDataType
from .XbrlUnit import XbrlUnit

XSD_NAMESPACE = "http://www.w3.org/2001/XMLSchema"

def emptySignature():
    """((Counter, Counter)) -- the signature of a dimensionless datatype."""
    return (Counter(), Counter())

def isEmptySignature(signature):
    """(bool) -- True where neither multiset of the signature has any member."""
    return not signature[0] and not signature[1]

def signaturesEqual(signature1, signature2):
    """(bool) -- True where the numerator multisets are equal and the denominator multisets are equal."""
    return signature1[0] == signature2[0] and signature1[1] == signature2[1]

def signatureString(signature):
    """(str) -- a signature as ( numerators ; denominators ), for error messages."""
    def side(counter):
        return ", ".join(str(qn) for qn in sorted(counter.elements(), key=str))
    return f"( {side(signature[0])} ; {side(signature[1])} )"

def unitCompositionQNames(dtObj, compMdl):
    """((QName,...), (QName,...)) -- the numerator and denominator of a datatype's unitComposition, or None where it declares none.

    A QName that did not resolve is dropped here, having been reported by the loader as
    oimce:unboundPrefix.
    """
    try:
        return dtObj._unitCompositionQNames
    except AttributeError:
        pass
    result = None
    composition = getattr(dtObj, "unitComposition", None)
    if composition is not None:
        result = (tuple(qn for qn in (getattr(composition, "numerator", None) or ()) if qn is not None),
                  tuple(qn for qn in (getattr(composition, "denominator", None) or ()) if qn is not None))
    dtObj._unitCompositionQNames = result
    return result

def unitDeclaredDataTypes(compMdl):
    """(frozenset) -- the dataTypes that a unit object declares, other than the pure unit's.

    A datatype in this set, declaring no composition, is a base datatype: units exist for
    it and it is not composed of anything else.  The pure unit is excluded so that the
    pure datatype is dimensionless, which is what makes an absent unit dimension valid
    for a dimensionless fact.
    """
    try:
        return compMdl._unitDeclaredDataTypes
    except AttributeError:
        from .ValidateFacts import qnPureUnit
        pureUnitObj = compMdl.namedObjects.get(qnPureUnit)
        pureDataType = getattr(pureUnitObj, "dataType", None)
        compMdl._unitDeclaredDataTypes = frozenset(
            obj.dataType for obj in compMdl.namedObjects.values()
            if isinstance(obj, XbrlUnit) and obj.dataType is not None and obj.dataType != pureDataType)
        return compMdl._unitDeclaredDataTypes

def dataTypeSignature(dtQn, compMdl, visiting=None):
    """((Counter, Counter)) -- the unit signature of a datatype, by the first rule that applies.

    1. a dimensionless datatype: both multisets are empty;
    2. a datatype declaring a unitComposition: the union of the signatures of its
       numerator datatypes and of the inverses of the signatures of its denominators;
    3. a base datatype: that datatype alone in the numerator multiset;
    4. otherwise the signature of the datatype it derives from.

    Rule 3 preceding rule 4 is what makes a datatype's own units take precedence over
    those of the datatype it derives from.
    """
    if not hasattr(compMdl, "_unitSignatures"):
        compMdl._unitSignatures = {}
    signature = compMdl._unitSignatures.get(dtQn)
    if signature is not None:
        return signature
    if visiting is None:
        visiting = set()
    if dtQn in visiting: # cyclic composition, reported as oimte:circularUnitComposition
        return emptySignature()
    visiting.add(dtQn)
    numerators = Counter()
    denominators = Counter()
    dtObj = compMdl.namedObjects.get(dtQn)
    if isinstance(dtObj, XbrlDataType):
        composition = unitCompositionQNames(dtObj, compMdl)
        if composition is not None: # rule 2
            for compQn in composition[0]:
                num, den = dataTypeSignature(compQn, compMdl, visiting)
                numerators += num
                denominators += den
            for compQn in composition[1]: # inverted: numerators of a denominator divide
                num, den = dataTypeSignature(compQn, compMdl, visiting)
                numerators += den
                denominators += num
        elif dtQn in unitDeclaredDataTypes(compMdl): # rule 3
            numerators[dtQn] += 1
        elif isinstance(compMdl.namedObjects.get(dtObj.baseType), XbrlDataType): # rule 4
            numerators, denominators = dataTypeSignature(dtObj.baseType, compMdl, visiting)
        # rule 1 otherwise: dimensionless, both multisets empty
    visiting.discard(dtQn)
    signature = (+Counter(numerators), +Counter(denominators)) # unary plus drops any zero counts
    compMdl._unitSignatures[dtQn] = signature
    return signature

def unitDimensionSignature(unitMeasures, compMdl):
    """((Counter, Counter)) -- the unit signature of a unit dimension value.

    unitMeasures is the (numerators, denominators) tuple of measure QNames that
    parseUnitString returns.  The pure unit contributes nothing, and the signature of a
    denominator measure is inverted.  A measure resolving to no unit object is skipped;
    it is reported as oimce:invalidUnitStringRepresentation where the fact is resolved.
    """
    from .ValidateFacts import qnPureUnit
    numerators = Counter()
    denominators = Counter()
    for isDenominator, measures in enumerate(unitMeasures[:2]):
        for measureQn in measures:
            if measureQn == qnPureUnit:
                continue
            unitObj = compMdl.namedObjects.get(measureQn)
            if not isinstance(unitObj, XbrlUnit):
                continue
            num, den = dataTypeSignature(unitObj.dataType, compMdl)
            if isDenominator:
                num, den = den, num
            numerators += num
            denominators += den
    return (+Counter(numerators), +Counter(denominators))

def compositionCycle(dtObj, compMdl, visiting=None):
    """(bool) -- True where a datatype appears in its own unitComposition, directly or transitively."""
    if visiting is None:
        visiting = set()
    if dtObj.name in visiting:
        return True
    visiting.add(dtObj.name)
    composition = unitCompositionQNames(dtObj, compMdl)
    if composition is not None:
        for side in composition:
            for compQn in side:
                compObj = compMdl.namedObjects.get(compQn)
                if isinstance(compObj, XbrlDataType) and compositionCycle(compObj, compMdl, visiting):
                    return True
    visiting.discard(dtObj.name)
    return False

def _measuresKey(measures):
    """(tuple) -- an order-independent key for a (numerators, denominators) measure tuple."""
    return (tuple(sorted(str(m) for m in measures[0])), tuple(sorted(str(m) for m in measures[1])))

def unitByCompositeRepresentation(compMdl):
    """(dict) -- measures key -> unit QName, for every compositeUnitRepresentation in the model."""
    try:
        return compMdl._unitByCompositeRepresentation
    except AttributeError:
        index = {}
        for obj in compMdl.namedObjects.values():
            if isinstance(obj, XbrlUnit):
                for measures in getattr(obj, "_unitsMeasures", None) or ():
                    index.setdefault(_measuresKey(measures), obj.name)
        compMdl._unitByCompositeRepresentation = index
        return index

def canonicalUnitValue(unitMeasures, compMdl):
    """((QName,...), (QName,...)) -- the canonical unit dimension value of reported measures.

    Pure unit measures are removed, measures that are together the compositeUnitRepresentation
    of a unit object are replaced by that unit's QName, and the measures that remain are ordered.
    A fact reporting utr:ft*utr:sqft therefore reports the unit utr:ft3, and matches a cube whose
    unit dimension is a domain containing utr:ft3.  Reference: tavi.md "Unit equivalence".
    """
    from .ValidateFacts import qnPureUnit
    numerators = [m for m in unitMeasures[0] if m != qnPureUnit]
    denominators = [m for m in unitMeasures[1] if m != qnPureUnit]
    index = unitByCompositeRepresentation(compMdl)
    seen = set()
    while True:
        key = _measuresKey((numerators, denominators))
        unitQn = index.get(key)
        if unitQn is None or key in seen: # a representation of itself would not terminate
            break
        seen.add(key)
        numerators, denominators = [unitQn], []
    return (tuple(sorted(numerators, key=str)), tuple(sorted(denominators, key=str)))
