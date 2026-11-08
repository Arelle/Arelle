"""
FormulaDuplicates.py - duplicate resolution for the Tavi Query and Rules Language.

A fact query de-duplicates: where more than one reported value falls at the same
intersection, the query yields one value rather than one per report of it.  This
is the behaviour of XBRL Formula 1.0 and it matters in practice -- a total that a
report states both in a table and parenthetically in the surrounding text would
otherwise produce two iterations and double every sum computed from it.

Two things de-duplicate by the same rule:

  * several XbrlFact objects with the same dimensions (Tavi's duplicate facts);
  * one XbrlFact carrying several XbrlFactValue objects, which is the same value
    reported in more than one place, or amended.

Classification follows Tavi's duplicate fact validation: complete duplicates
agree on value and decimals; consistent duplicates are numeric and have
intersecting intervals; anything else is inconsistent and cannot be
de-duplicated to a single value. A value's interval follows its rounding mode:
closed for a rounded value, half-open towards zero for a truncated one, the
mode resolved as calculation validation resolves it (the fact value's own
roundingMode, else the model's, else round-to-nearest).

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, List, Optional, Sequence, Tuple

from arelle.ModelValue import QName


COMPLETE = "complete"
CONSISTENT = "consistent"
INCONSISTENT = "inconsistent"


def _asDecimal(value) -> Optional[Decimal]:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except (InvalidOperation, ValueError):
            return None
    return None


def _decimalsOf(obj) -> Optional[int]:
    """The stated decimals, or None for an exact (infinite-precision) value."""
    d = obj.decimals
    if d is None:
        return None
    if isinstance(d, str):
        if d.strip().upper() in ("INF", "+INF"):
            return None
        try:
            return int(d)
        except ValueError:
            return None
    try:
        return int(d)
    except (TypeError, ValueError):
        return None


def _interval(value: Decimal, decimals: Optional[int], truncate: bool):
    """(low, high, lowIncluded, highIncluded) a value with this accuracy could have come from.

    As arelle.ValidateXbrlCalcs.rangeValue: a rounded value is the closed interval
    half a unit either side; a truncated value was cut towards zero, so the bound
    nearer zero is included and the other is not (both excluded for zero).
    """
    if decimals is None:
        return (value, value, True, True)
    unit = Decimal(10) ** Decimal(-decimals)
    if not truncate:
        return (value - unit / 2, value + unit / 2, True, True)
    if value > 0:
        return (value, value + unit, True, False)
    if value < 0:
        return (value - unit, value, False, True)
    return (-unit, unit, False, False)


def classify(values: Sequence[Any], decimalsList: Sequence[Optional[int]],
             truncations: Optional[Sequence[bool]] = None) -> str:
    """Classify a set of duplicate values as complete, consistent or inconsistent.

    truncations gives each value's rounding mode (True for truncation); absent,
    every value is taken as rounded to nearest.
    """
    if len(values) < 2:
        return COMPLETE
    first = values[0]
    firstDec = decimalsList[0]
    if all(v == first for v in values) and all(d == firstDec for d in decimalsList):
        return COMPLETE

    decs = [_asDecimal(v) for v in values]
    if any(d is None for d in decs):
        # A non-numeric value that is not a complete duplicate of the others has
        # no rounding interval to reconcile, so it cannot be consistent.
        return INCONSISTENT

    truncations = truncations or [False] * len(decs)
    lo = hi = None
    loIncl = hiIncl = True
    for value, dec, trunc in zip(decs, decimalsList, truncations):
        vlo, vhi, vloIncl, vhiIncl = _interval(value, dec, trunc)
        # The intersection includes a shared bound only where both intervals do.
        if lo is None or vlo > lo:
            lo, loIncl = vlo, vloIncl
        elif vlo == lo:
            loIncl = loIncl and vloIncl
        if hi is None or vhi < hi:
            hi, hiIncl = vhi, vhiIncl
        elif vhi == hi:
            hiIncl = hiIncl and vhiIncl
        if lo > hi or (lo == hi and not (loIncl and hiIncl)):
            return INCONSISTENT
    return CONSISTENT


def _truncations(fact, fvs) -> List[bool]:
    """Whether each fact value was truncated, resolved as calculation validation resolves it."""
    from XbrlModel.ValidateCalculations import _isTruncation, _truncationOf
    compMdl = fact.xbrlCompMdl
    if compMdl is None:
        return [str(fv.roundingMode or "") == "truncation" for fv in fvs]
    truncationOf = _truncationOf(compMdl, _isTruncation(compMdl))
    return [truncationOf(fv) for fv in fvs]


def _mostPrecise(items: Sequence[Any], decimalsList: Sequence[Optional[int]]) -> Any:
    """The item stating the greatest accuracy; an exact value wins outright."""
    best, bestDec = items[0], decimalsList[0]
    for item, dec in zip(items[1:], decimalsList[1:]):
        if bestDec is None:
            break
        if dec is None or dec > bestDec:
            best, bestDec = item, dec
    return best


# ---------------------------------------------------------------------------
# Fact value de-duplication (several XbrlFactValue on one XbrlFact)
# ---------------------------------------------------------------------------

def effectiveFactValue(fact) -> Optional[Any]:
    """The fact value object that carries the fact's value.

    Where a fact has several fact value objects -- the same value located in a
    table and again in narrative text, say -- they are duplicates of each other
    and resolve to one.  Inconsistent values cannot resolve, and the first is
    returned so that a rule still sees a value; a rule that needs to detect the
    disagreement reads `factValues`.
    """
    fvs = list(fact.factValues or ())
    if not fvs:
        return None
    if len(fvs) == 1:
        return fvs[0]
    values = [fv.value for fv in fvs]
    decs = [_decimalsOf(fv) for fv in fvs]
    kind = classify(values, decs, _truncations(fact, fvs))
    if kind == CONSISTENT:
        return _mostPrecise(fvs, decs)
    return fvs[0]


# ---------------------------------------------------------------------------
# Fact de-duplication (several XbrlFact at one intersection)
# ---------------------------------------------------------------------------

def _dimensionKey(fact) -> frozenset:
    dims = fact.factDimensions or {}
    return frozenset(
        (k, v) for k, v in dims.items()
        if isinstance(k, QName)
    )


def deduplicateFacts(facts: List[Any], mode: Optional[str] = None) -> List[Any]:
    """Collapse duplicate facts, preserving the order they were matched in.

    mode is None for the default (complete and consistent duplicates collapse,
    inconsistent duplicates are all kept), "nodups" (inconsistent duplicates are
    dropped entirely), or "dups" (no de-duplication at all).
    """
    if mode == "dups" or len(facts) < 2:
        return facts

    groups: dict = {}
    order: List[frozenset] = []
    for fact in facts:
        key = _dimensionKey(fact)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(fact)

    out: List[Any] = []
    for key in order:
        group = groups[key]
        if len(group) == 1:
            out.append(group[0])
            continue
        fvs = [effectiveFactValue(f) for f in group]
        values = [fv.value if fv is not None else None for fv in fvs]
        decs = [_decimalsOf(fv) if fv is not None else None for fv in fvs]
        truncs = [_truncations(f, [fv])[0] if fv is not None else False
                  for f, fv in zip(group, fvs)]
        kind = classify(values, decs, truncs)
        if kind == COMPLETE:
            out.append(group[0])
        elif kind == CONSISTENT:
            out.append(_mostPrecise(group, decs))
        elif mode == "nodups":
            continue
        else:
            out.extend(group)
    return out
