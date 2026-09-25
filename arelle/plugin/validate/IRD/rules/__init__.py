"""
See COPYRIGHT.md for copyright information.

Shared helpers for IRD validation rules.

All rule modules import from this package to avoid duplicating common
logic for fact value lookup/checks, form-type detection, and paired rule emission.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypeVar

from arelle.ModelValue import QName
from arelle.utils.validate.Facts import iterValidNonNilFactsByQname

if TYPE_CHECKING:
    from arelle.ModelInstanceObject import ModelFact
    from arelle.ModelXbrl import ModelXbrl


# ── Fact Value Lookup / Checks ──────────────────────────────────────────────────────────────

def getNumericValue(fact: ModelFact) -> Decimal | None:
    """Return the numeric *xValue* of *fact*, or ``None`` if unavailable."""
    try:
        val = fact.xValue
        if isinstance(val, (int, float, Decimal)):
            return Decimal(val)
    except Exception:
        pass
    return None


def getDateValue(fact: ModelFact) -> date | None:
    """Return the date component of *fact*'s *xValue*, or ``None``."""
    val = fact.xValue
    if isinstance(val, datetime):
        return val.date()
    return None


FactsByValueType = TypeVar("FactsByValueType")


def _getFactsByValue(
        modelXbrl: ModelXbrl,
        qnames: tuple[QName, ...],
        valueGetter: Callable[[ModelFact], FactsByValueType | None],
) -> dict[FactsByValueType, list[ModelFact]]:
    factsByValue = defaultdict(list)
    for qname in qnames:
        for fact in iterValidNonNilFactsByQname(modelXbrl, qname):
            val = valueGetter(fact)
            if val is None:
                continue
            factsByValue[val].append(fact)
    return dict(factsByValue)


def getFactsByDateValue(modelXbrl: ModelXbrl, qnames: tuple[QName, ...]) -> dict[date, list[ModelFact]]:
    return _getFactsByValue(modelXbrl, qnames, getDateValue)


# ── Currency / Unit Helpers ──────────────────────────────────────────────────

ISO4217_NAMESPACE = "http://www.xbrl.org/2003/iso4217"


def factUnitCurrencyCode(fact: ModelFact) -> str | None:
    """Return the ISO 4217 code of *fact*'s unit, if it is a single-measure
    currency unit (e.g. ``iso4217:HKD``); otherwise ``None`` (covers
    ``xbrli:pure``, share units, multi-measure units, or no unit at all).
    """
    unit = fact.unit
    if unit is None:
        return None
    numerator, denominator = unit.measures
    if len(numerator) != 1 or denominator:
        return None
    measure = numerator[0]
    if measure.namespaceURI != ISO4217_NAMESPACE:
        return None
    return measure.localName
