'''
See COPYRIGHT.md for copyright information.

Consistency checking for summation-item (calculation) relationships.

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
from .XbrlConst import xbrl
from .XbrlCube import conceptCoreDim
from .XbrlNetwork import XbrlNetwork

qnXbrlSummationItem = qname(xbrl, "xbrl:summation-item")
qnXbrlWeight = qname(xbrl, "xbrl:weight")

# Calculation control properties (proposal section 3). None of these are declared in the
# base taxonomy yet, so in practice every network takes the specification default; they are
# read here so that the checking behaves as specified as soon as they are declared.
qnRoundingMode = qname(xbrl, "xbrl:roundingMode")
qnTolerance = qname(xbrl, "xbrl:tolerance")
qnSummationRelation = qname(xbrl, "xbrl:summationRelation")

# Error codes for the consistency checks, from section 10 of the proposal. They are kept in
# one table so the namespace can be changed in one place.
_CALC_ERROR = {
    "inconsistentRounding": "oimtc:inconsistentCalculationUsingRounding",
    "inconsistentTruncation": "oimtc:inconsistentCalculationUsingTruncation",
    "excessDigits": "oimtc:excessDigits",
    "duplicatesRounding": "oimtc:disallowedDuplicateFactsUsingRounding",
    "duplicatesTruncation": "oimtc:disallowedDuplicateFactsUsingTruncation",
}

_NIL = object()


def _controlProperty(compMdl, ntwkObj, propertyQn, default=None):
    """Effective value of a calculation control property (proposal section 3.2).

    Precedence is relationship, then network, then XBRL model object, then the
    specification default. Relationship level is resolved by the caller where it applies.
    """
    value = ntwkObj.propertyObjectValue(propertyQn)
    if value is not None:
        return value
    for mdlObj in compMdl.xbrlModels.values():
        value = mdlObj.propertyObjectValue(propertyQn)
        if value is not None:
            return value
    return default


def _isTruncation(compMdl, ntwkObj):
    """True when the effective xbrl:roundingMode is truncation (proposal section 7.1)."""
    return str(_controlProperty(compMdl, ntwkObj, qnRoundingMode, "roundToNearest")) == "truncation"


def _tolerance(compMdl, ntwkObj):
    """Effective xbrl:tolerance (proposal section 7.2), as an absolute quantity.

    How the tolerance is scaled is the least settled part of the proposal (appendix C):
    the value may end up absolute, as coded here and as the current section 7.2 text says,
    or a multiple of the fact's own rounding unit 10**-decimals, or a fraction of the
    reported total. It is inert at its default of 0, so no reported result depends on the
    choice until a taxonomy declares the property.
    """
    value = _controlProperty(compMdl, ntwkObj, qnTolerance, 0)
    try:
        tolerance = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(0)
    return tolerance if tolerance > 0 else Decimal(0)


def _factValueInterval(bucket, truncate):
    """Interval for one reported data point, over its duplicate fact values.

    Implements sections 7.1, 7.4 and 7.5. Returns (status, interval) where status is None
    when the interval is usable, and otherwise "nil", "excessDigits" or
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
        if insignificantDigits(value, decimals=dec):
            return "excessDigits", None
        if dec in byDecimals:
            if byDecimals[dec] != value:
                return "inconsistentDuplicates", None
            continue
        byDecimals[dec] = value
        _lo, _hi, _loIncl, _hiIncl = rangeValue(value, dec, truncate=truncate)
        if lo is None or _lo >= lo:
            lo, loIncl = _lo, (_loIncl if lo is None or _lo > lo else loIncl or _loIncl)
        if hi is None or _hi <= hi:
            hi, hiIncl = _hi, (_hiIncl if hi is None or _hi < hi else hiIncl or _hiIncl)
    if lo > hi or (lo == hi and not (loIncl and hiIncl)):
        return "inconsistentDuplicates", None
    return None, (lo, hi, loIncl, hiIncl)


def _calculations(compMdl, ntwkObj):
    """The calculations of a summation-item network, as totalQn -> [(contributingQn, weight)].

    A calculation is the set of summation-item relationships sharing a total concept
    (proposal section 1).
    """
    calcs = defaultdict(list)
    for relObj in compMdl.effectiveRelationships(ntwkObj):
        weight = relObj.propertyObjectValue(qnXbrlWeight)
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
    """Bind and check the summation-item networks associated with a cube.

    Consistency checking is performed only on calculation networks listed in a cube's
    cubeNetworks, and binds only against that cube's facts (proposal section 6.1). This is
    what stops a calculation binding against facts the preparer never intended it to
    constrain: a report may hold facts for a second entity in a cube that carries only the
    presentation network, and those facts are then never bound by the calculation.
    """
    if not getattr(cubeObj, "_cellFacts", None) or not cubeObj.cubeNetworks:
        return
    calcNetworks = []
    for ntwkQn in cubeObj.cubeNetworks:
        ntwkObj = compMdl.namedObjects.get(ntwkQn)
        if isinstance(ntwkObj, XbrlNetwork) and ntwkObj.relationshipTypeName == qnXbrlSummationItem:
            calcNetworks.append(ntwkObj)
    if not calcNetworks:
        return
    aligned = _alignedCells(cubeObj)
    for ntwkObj in calcNetworks:
        truncate = _isTruncation(compMdl, ntwkObj)
        tolerance = _tolerance(compMdl, ntwkObj)
        relation = str(_controlProperty(compMdl, ntwkObj, qnSummationRelation, "equal"))
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
                              alignKey, truncate, tolerance, relation)


def _checkBinding(compMdl, cubeObj, ntwkObj, totalQn, totalBucket, bound, alignKey,
                  truncate, tolerance, relation):
    """Check one binding of one calculation (proposal section 7)."""
    # 1 and 2: a duplicate or excess-digit condition stops checking for this binding
    for bucket, _weight, _conceptQn in [(totalBucket, None, totalQn)] + bound:
        status, _interval = _factValueInterval(bucket, truncate)
        if status == "excessDigits":
            emit_error(compMdl, _CALC_ERROR["excessDigits"],
                       _("Calculation checking stopped for the total %(total)s in cube %(cube)s: a bound fact has digits in excess of its declared precision."),
                       xbrlObject=cubeObj, total=totalQn, cube=cubeObj.name)
            return
        if status == "inconsistentDuplicates":
            emit_error(compMdl, _CALC_ERROR["duplicatesTruncation" if truncate else "duplicatesRounding"],
                       _("Calculation checking stopped for the total %(total)s in cube %(cube)s: a bound data point has inconsistent duplicate facts."),
                       xbrlObject=cubeObj, total=totalQn, cube=cubeObj.name)
            return

    totalStatus, totalInterval = _factValueInterval(totalBucket, truncate)
    if totalStatus is not None:
        return  # an all-nil total is ignored for binding

    # 3 and 4: sum the contribution intervals, then widen by the tolerance
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
    if tolerance > 0:
        calcLo -= tolerance
        calcHi += tolerance
        calcLoIncl = calcHiIncl = True  # a widened bound is closed

    # 6: compare against the reported total in the effective summation relation
    reportedLo, reportedHi, reportedLoIncl, reportedHiIncl = totalInterval
    atMost = calcLo < reportedHi or (calcLo == reportedHi and calcLoIncl and reportedHiIncl)
    atLeast = reportedLo < calcHi or (reportedLo == calcHi and reportedLoIncl and calcHiIncl)
    consistent = {"atMost": atMost, "atLeast": atLeast}.get(relation, atMost and atLeast)
    if not consistent:
        emit_error(compMdl, _CALC_ERROR["inconsistentTruncation" if truncate else "inconsistentRounding"],
                   _("The calculation of %(total)s in network %(network)s bound in cube %(cube)s is inconsistent: the contributions sum to %(calculated)s but the reported total is %(reported)s (aspects %(aspects)s)."),
                   xbrlObject=cubeObj, total=totalQn, network=ntwkObj.name, cube=cubeObj.name,
                   calculated=f"[{calcLo}, {calcHi}]", reported=f"[{reportedLo}, {reportedHi}]",
                   aspects=", ".join(f"{d}={v}" for d, v in alignKey))
