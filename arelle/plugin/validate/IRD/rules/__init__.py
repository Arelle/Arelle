"""
See COPYRIGHT.md for copyright information.

Shared helpers for IRD validation rules.

All rule modules import from this package to avoid duplicating common
logic for fact value lookup/checks, form-type detection, and paired rule emission.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Callable
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypeVar

from arelle.ModelValue import QName
from arelle.utils.validate.Facts import iterValidNonNilFactsByQname, hasValidNonNilFactByQname, getValidNonNilFactsByQname
from arelle.utils.validate.Validation import Validation

if TYPE_CHECKING:
    from arelle.ModelInstanceObject import ModelFact
    from arelle.ModelXbrl import ModelXbrl


# ── Fact Value Lookup / Checks ──────────────────────────────────────────────────────────────

def isZeroOrAbsent(modelXbrl: ModelXbrl, qn: QName) -> bool:
    """True if *qn* has no facts or every valid, non-nil fact has zero numeric value.

    Non-numeric facts (e.g. string or boolean) are treated as *present* (not
    zero/absent) because the caller is checking for a non-zero amount.
    """
    for fact in iterValidNonNilFactsByQname(modelXbrl, qn):
        try:
            if isinstance(fact.xValue, bool) or fact.xValue != 0:
                return False
        except Exception:
            # xValue unavailable or non-numeric; treat as present
            return False
    return True


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


# ── Details / Amount Pairing Helpers ─────────────────────────────────────────

def detailsMissingAmountValidation(
    modelXbrl: ModelXbrl,
    detailsQn: QName,
    amountQn: QName,
    code: str,
    msg: str,
) -> Iterable[Validation]:
    """Emit an error when the details element is present but the
    corresponding amount is absent.
    """
    if not hasValidNonNilFactByQname(modelXbrl, detailsQn):
        return
    if not hasValidNonNilFactByQname(modelXbrl, amountQn):
        yield Validation.error(
            codes=code,
            msg=msg,
            modelObject=getValidNonNilFactsByQname(modelXbrl, detailsQn),
        )


def nonzeroAmountMissingDetailsValidation(
    modelXbrl: ModelXbrl,
    detailsQn: QName,
    amountQn: QName,
    code: str,
    msg: str,
) -> Iterable[Validation]:
    """Emit an error when the amount is non-zero but the details
    element is absent.
    """
    if not isZeroOrAbsent(modelXbrl, amountQn) and not hasValidNonNilFactByQname(modelXbrl, detailsQn):
        yield Validation.error(
            codes=code,
            msg=msg,
            modelObject=getValidNonNilFactsByQname(modelXbrl, amountQn),
        )
