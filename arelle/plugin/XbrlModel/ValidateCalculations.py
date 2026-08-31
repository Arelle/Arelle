'''
See COPYRIGHT.md for copyright information.

Consistency checking for summation-concept (calculation) relationships.

Implements sections 6.2 and 7 of the calculation relationships proposal,
oim/specifications/oim-taxonomy/summation-item-relationship-proposal.md: binding a
calculation against the facts of an associated cube, and checking the reported total
against the contributions using interval arithmetic.

The definition-time checks of section 5 are in ValidateNetworkObjects.py.

The interval arithmetic itself is not reimplemented here. arelle.ValidateXbrlCalcs
already carries the Calculations 1.1 implementation, and its rangeValue() and
insignificantDigits() are exactly the fact value interval of section 7.1 and the
digits-in-excess-of-declared-precision condition of section 7.4. Reusing them is what
keeps this implementation and Arelle's legacy calculation validation in step.
'''
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from arelle.ModelValue import qname
from arelle.ValidateXbrlCalcs import rangeValue, insignificantDigits

from .ErrorCatalog import emit_error
from .XbrlConst import xbrl, qnXbrlRootSource
from .XbrlCube import conceptCoreDim
from .XbrlNetwork import XbrlNetwork

qnXbrlSummationConcept = qname(xbrl, "xbrl:summation-concept")
qnXbrlGreaterLesser = qname(xbrl, "xbrl:greater-lesser")
qnXbrlWeight = qname(xbrl, "xbrl:weight")

# The one calculation control property (proposal section 3).
qnRoundingMode = qname(xbrl, "xbrl:roundingMode")

# Error codes for the consistency checks, from section 10 of the proposal. They are kept in
# one table so the namespace can be changed in one place.
_CALC_ERROR = {
    "inconsistentRounding": "oimtc:inconsistentCalculationUsingRounding",
    "inconsistentTruncation": "oimtc:inconsistentCalculationUsingTruncation",
    "excessDigits": "oimtc:excessDigits",
    "duplicatesRounding": "oimtc:disallowedDuplicateFactsUsingRounding",
    "duplicatesTruncation": "oimtc:disallowedDuplicateFactsUsingTruncation",
    "greaterLesserInconsistent": "oimtc:greaterLesserInconsistent",
}

_NIL = object()


def _propertyValue(obj, propertyQn):
    """A property's value, whether or not the object has been through property validation.

    propertyObjectValue returns the validated typed value, which validateProperties sets
    while validating the module that owns the object. A module compiled on demand -- the DTS
    a legacy report names, discovered while the report module is already being validated --
    is added to the model after its own validation pass would have run, so its relationships
    never acquire typed values. Falling back to the raw value keeps checking independent of
    the order in which modules happen to be compiled.
    """
    value = obj.propertyObjectValue(propertyQn)
    if value is not None:
        return value
    for propObj in getattr(obj, "properties", None) or ():
        if propObj.property == propertyQn:
            return getattr(propObj, "value", None)
    return None


def _controlProperty(compMdl, ntwkObj, propertyQn, default=None):
    """Effective value of a calculation control property (proposal section 3.2).

    Precedence is relationship, then network, then XBRL model object, then the
    specification default. Relationship level is resolved by the caller where it applies.
    """
    value = _propertyValue(ntwkObj, propertyQn)
    if value is not None:
        return value
    for mdlObj in compMdl.xbrlModels.values():
        value = _propertyValue(mdlObj, propertyQn)
        if value is not None:
            return value
    return default


def _isTruncation(compMdl, ntwkObj):
    """True when the effective xbrl:roundingMode is truncation (proposal section 7.1).

    A processor may override the declared mode at run time (proposal section 3.3), for a
    report whose rounding convention is known out of band, or to run a conformance suite
    that parameterises the mode per variation. Where the override is applied it MUST be
    reported, and the results are then not conformant results for the model as published.
    """
    declared = str(_controlProperty(compMdl, ntwkObj, qnRoundingMode, "roundToNearest"))
    override = getattr(compMdl, "calcRoundingModeOverride", None)
    if override is not None and override != declared:
        if not getattr(compMdl, "_calcRoundingModeOverrideReported", False):
            compMdl._calcRoundingModeOverrideReported = True
            compMdl.warning("arelle:calcRoundingModeOverridden",
                            _("The calculation rounding mode declared by the model, %(declared)s, "
                              "was overridden at run time with %(override)s. Calculation results "
                              "are not conformant results for the model as published."),
                            declared=declared, override=override)
        declared = override
    return declared == "truncation"


def _factValueInterval(bucket, truncate):
    """Interval for one reported data point, over its duplicate fact values.

    Implements sections 7.1, 7.4 and 7.5. Returns (status, interval) where status is None
    when the interval is usable, and otherwise "nil", "nonNumeric", "excessDigits" or
    "inconsistentDuplicates". The interval is the intersection over consistent duplicates.
    """
    values = [(fv, getattr(fv, "value", None), getattr(fv, "decimals", None)) for _f, fv in bucket]
    if all(v is None for _fv, v, _d in values):
        return "nil", None  # all nil: consistent, but ignored for binding
    if any(v is None for _fv, v, _d in values):
        return "inconsistentDuplicates", None  # mixing nil and non-nil is inconsistent
    lo = hi = None
    loIncl = hiIncl = False
    byDecimals = {}
    for _fv, value, decimals in values:
        dec = "INF" if decimals is None else decimals
        # A fact whose value is not a number can reach a numeric binding -- an inline fact
        # whose transformation failed keeps its raw text, for instance -- and rangeValue then
        # yields NaN, whose ordered comparison raises rather than returning a usable interval.
        # The defect is reported where the value was produced; here it makes the binding
        # uncheckable, which the caller must say rather than silently pass over.
        try:
            if insignificantDigits(value, decimals=dec):
                return "excessDigits", None
            _lo, _hi, _loIncl, _hiIncl = rangeValue(value, dec, truncate=truncate)
        except (InvalidOperation, ValueError, TypeError, ArithmeticError):
            return "nonNumeric", None
        if not (_lo.is_finite() and _hi.is_finite()):
            return "nonNumeric", None
        if dec in byDecimals:
            if byDecimals[dec] != value:
                return "inconsistentDuplicates", None
            continue
        byDecimals[dec] = value
        if lo is None or _lo >= lo:
            lo, loIncl = _lo, (_loIncl if lo is None or _lo > lo else loIncl or _loIncl)
        if hi is None or _hi <= hi:
            hi, hiIncl = _hi, (_hiIncl if hi is None or _hi < hi else hiIncl or _hiIncl)
    if lo > hi or (lo == hi and not (loIncl and hiIncl)):
        return "inconsistentDuplicates", None
    return None, (lo, hi, loIncl, hiIncl)


def _calculations(compMdl, ntwkObj):
    """The calculations of a summation-concept network, as totalQn -> [(contributingQn, weight)].

    A calculation is the set of summation-concept relationships sharing a total concept
    (proposal section 1).
    """
    calcs = defaultdict(list)
    for relObj in compMdl.effectiveRelationships(ntwkObj):
        weight = _propertyValue(relObj, qnXbrlWeight)
        if weight is None:
            continue  # rootSource relationships, and any relationship whose weight failed validation
        try:
            calcs[relObj.source].append((relObj.target, Decimal(str(weight))))
        except (InvalidOperation, ValueError):
            continue  # reported as a property value error
    return calcs


def _alignedCells(cubeObj):
    """Index a cube's cells by dimensional alignment (proposal section 6.2).

    Returns alignmentKey -> {conceptQn: bucket}, where the alignment key is every aspect of
    the cell other than the concept. Two data points are dimensionally aligned when they
    share an alignment key.
    """
    aligned = defaultdict(dict)
    for cellKey, bucket in (getattr(cubeObj, "_cellFacts", None) or {}).items():
        conceptQn = None
        others = []
        for dimQn, dimValue in cellKey:
            if dimQn == conceptCoreDim:
                conceptQn = dimValue
            else:
                others.append((dimQn, dimValue))
        if conceptQn is not None and bucket:
            aligned[tuple(others)][conceptQn] = bucket
    return aligned


def validateCubeCalculations(compMdl, cubeObj):
    """Bind and check the summation-concept networks associated with a cube.

    Consistency checking is performed only on calculation networks listed in a cube's
    cubeNetworks, and binds only against that cube's facts (proposal section 6.1). This is
    what stops a calculation binding against facts the preparer never intended it to
    constrain: a report may hold facts for a second entity in a cube that carries only the
    presentation network, and those facts are then never bound by the calculation.
    """
    if not getattr(cubeObj, "_cellFacts", None) or not cubeObj.cubeNetworks:
        return
    calcNetworks, orderingNetworks = [], []
    for ntwkQn in cubeObj.cubeNetworks:
        ntwkObj = compMdl.namedObjects.get(ntwkQn)
        if not isinstance(ntwkObj, XbrlNetwork):
            continue
        if ntwkObj.relationshipTypeName == qnXbrlSummationConcept:
            calcNetworks.append(ntwkObj)
        elif ntwkObj.relationshipTypeName == qnXbrlGreaterLesser:
            orderingNetworks.append(ntwkObj)
    if not calcNetworks and not orderingNetworks:
        return
    aligned = _alignedCells(cubeObj)
    for ntwkObj in orderingNetworks:
        _checkOrdering(compMdl, cubeObj, ntwkObj, aligned, _isTruncation(compMdl, ntwkObj))
    for ntwkObj in calcNetworks:
        truncate = _isTruncation(compMdl, ntwkObj)
        for totalQn, contributions in _calculations(compMdl, ntwkObj).items():
            for alignKey, byConcept in aligned.items():
                totalBucket = byConcept.get(totalQn)
                if not totalBucket:
                    continue
                bound = [(byConcept[conceptQn], weight, conceptQn)
                         for conceptQn, weight in contributions if conceptQn in byConcept]
                if not bound:
                    continue  # a calculation binds only where at least one contribution is reported
                _checkBinding(compMdl, cubeObj, ntwkObj, totalQn, totalBucket, bound,
                              alignKey, truncate)


def _recordResult(compMdl, cubeObj, ntwkObj, totalQn, alignKey, consistent,
                  code=None, calculated=None, reported=None):
    """Record what this processor concluded for one calculation binding.

    Kept so SaveModel can publish it as derived content. A conclusion reached under a
    particular rule set at a particular moment is not recoverable from the model afterwards --
    re-deriving it later answers a different question, because rules and implementations move --
    so it is recorded here rather than left to be recomputed. Only bindings that were actually
    checked are recorded: a binding skipped for a non-numeric or all-nil value has no verdict,
    and absence must not be readable as either outcome.

    Values are stored raw; SaveModel formats them, so that the unit tuple validation leaves in
    factDimensions is rendered by the one function that knows how.
    """
    results = getattr(compMdl, "_calculationResults", None)
    if results is None:
        results = compMdl._calculationResults = []
    results.append({
        "cube": cubeObj.name, "network": ntwkObj.name, "total": totalQn,
        "aspects": [(dimQn, dimValue) for dimQn, dimValue in alignKey if dimValue is not None],
        "consistent": consistent, "code": code,
        "calculated": calculated, "reported": reported})


def _checkOrdering(compMdl, cubeObj, ntwkObj, aligned, truncate):
    """Check a greater-lesser network's orderings (proposal section 11.2).

    Binds exactly as a calculation does: within this cube's facts, wherever a reported data
    point for the greater concept and one for the lesser concept are dimensionally aligned.
    The ordering is not strict -- gross equals net exactly when accumulated depreciation is
    zero -- so it is violated only when every value the lesser concept could have exceeds
    every value the greater concept could have.
    """
    for relObj in compMdl.effectiveRelationships(ntwkObj):
        if relObj.source == qnXbrlRootSource:
            continue
        for alignKey, byConcept in aligned.items():
            greaterBucket = byConcept.get(relObj.source)
            lesserBucket = byConcept.get(relObj.target)
            if not greaterBucket or not lesserBucket:
                continue
            greaterStatus, greaterInterval = _factValueInterval(greaterBucket, truncate)
            lesserStatus, lesserInterval = _factValueInterval(lesserBucket, truncate)
            if greaterStatus is not None or lesserStatus is not None:
                continue  # nil, excess digits or inconsistent duplicates: no verdict here
            greaterLo, greaterHi, _greaterLoIncl, greaterHiIncl = greaterInterval
            lesserLo, lesserHi, lesserLoIncl, _lesserHiIncl = lesserInterval
            consistent = (greaterHi > lesserLo
                          or (greaterHi == lesserLo and greaterHiIncl and lesserLoIncl))
            if not consistent:
                emit_error(compMdl, _CALC_ERROR["greaterLesserInconsistent"],
                           _("The greater-lesser relationship %(greater)s to %(lesser)s in network %(network)s bound in cube %(cube)s is violated: %(lesser)s is reported as %(lesserInterval)s, which exceeds %(greater)s at %(greaterInterval)s (aspects %(aspects)s)."),
                           xbrlObject=cubeObj, greater=relObj.source, lesser=relObj.target,
                           network=ntwkObj.name, cube=cubeObj.name,
                           lesserInterval=f"[{lesserLo}, {lesserHi}]",
                           greaterInterval=f"[{greaterLo}, {greaterHi}]",
                           aspects=", ".join(f"{d}={v}" for d, v in alignKey))


def _checkBinding(compMdl, cubeObj, ntwkObj, totalQn, totalBucket, bound, alignKey,
                  truncate):
    """Check one binding of one calculation (proposal section 7)."""
    # 1 and 2: a duplicate or excess-digit condition stops checking for this binding
    for bucket, _weight, _conceptQn in [(totalBucket, None, totalQn)] + bound:
        status, _interval = _factValueInterval(bucket, truncate)
        if status == "excessDigits":
            emit_error(compMdl, _CALC_ERROR["excessDigits"],
                       _("Calculation checking stopped for the total %(total)s in cube %(cube)s: a bound fact has digits in excess of its declared precision."),
                       xbrlObject=cubeObj, total=totalQn, cube=cubeObj.name)
            _recordResult(compMdl, cubeObj, ntwkObj, totalQn, alignKey, False,
                          _CALC_ERROR["excessDigits"])
            return
        if status == "inconsistentDuplicates":
            code = _CALC_ERROR["duplicatesTruncation" if truncate else "duplicatesRounding"]
            emit_error(compMdl, code,
                       _("Calculation checking stopped for the total %(total)s in cube %(cube)s: a bound data point has inconsistent duplicate facts."),
                       xbrlObject=cubeObj, total=totalQn, cube=cubeObj.name)
            _recordResult(compMdl, cubeObj, ntwkObj, totalQn, alignKey, False, code)
            return
        if status == "nonNumeric":
            # Not a calculation inconsistency -- the value is not a number, so the calculation
            # has no verdict at all. Skipping it silently would leave the calculation looking
            # checked and consistent, so say which concept made it uncheckable. The invalid
            # value itself is reported where it was produced (e.g. a failed inline transform).
            compMdl.warning("arelle:calcNotCheckedNonNumericValue",
                            _("Calculation checking skipped for the total %(total)s in cube %(cube)s: "
                              "the bound fact for %(concept)s has a value that is not a number."),
                            xbrlObject=cubeObj, total=totalQn, cube=cubeObj.name, concept=_conceptQn)
            return

    totalStatus, totalInterval = _factValueInterval(totalBucket, truncate)
    if totalStatus is not None:
        return  # an all-nil total is ignored for binding

    # 3 and 4: sum the contribution intervals
    calcLo = calcHi = Decimal(0)
    calcLoIncl = calcHiIncl = True
    contributed = False
    for bucket, weight, _conceptQn in bound:
        status, interval = _factValueInterval(bucket, truncate)
        if status is not None:
            continue  # an all-nil contribution simply does not participate
        lo, hi, loIncl, hiIncl = interval
        if weight < 0:
            lo, hi, loIncl, hiIncl = hi * weight, lo * weight, hiIncl, loIncl
        else:
            lo, hi = lo * weight, hi * weight
        calcLo += lo
        calcHi += hi
        calcLoIncl &= loIncl
        calcHiIncl &= hiIncl
        contributed = True
    if not contributed:
        return

    # 6: the calculated and reported total intervals must overlap
    reportedLo, reportedHi, reportedLoIncl, reportedHiIncl = totalInterval
    lowerFits = calcLo < reportedHi or (calcLo == reportedHi and calcLoIncl and reportedHiIncl)
    upperFits = reportedLo < calcHi or (reportedLo == calcHi and reportedLoIncl and calcHiIncl)
    consistent = lowerFits and upperFits
    _recordResult(compMdl, cubeObj, ntwkObj, totalQn, alignKey, consistent,
                  None if consistent else
                  _CALC_ERROR["inconsistentTruncation" if truncate else "inconsistentRounding"],
                  calculated=f"[{calcLo}, {calcHi}]",
                  reported=f"[{reportedLo}, {reportedHi}]")
    if not consistent:
        emit_error(compMdl, _CALC_ERROR["inconsistentTruncation" if truncate else "inconsistentRounding"],
                   _("The calculation of %(total)s in network %(network)s bound in cube %(cube)s is inconsistent: the contributions sum to %(calculated)s but the reported total is %(reported)s (aspects %(aspects)s)."),
                   xbrlObject=cubeObj, total=totalQn, network=ntwkObj.name, cube=cubeObj.name,
                   calculated=f"[{calcLo}, {calcHi}]", reported=f"[{reportedLo}, {reportedHi}]",
                   aspects=", ".join(f"{d}={v}" for d, v in alignKey))
