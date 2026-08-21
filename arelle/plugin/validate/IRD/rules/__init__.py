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
from typing import TYPE_CHECKING, TypeVar

from arelle.ModelValue import QName
from arelle.utils.validate.Facts import iterValidNonNilFactsByQname

if TYPE_CHECKING:
    from arelle.ModelInstanceObject import ModelFact
    from arelle.ModelXbrl import ModelXbrl


# ── Fact Value Lookup / Checks ──────────────────────────────────────────────────────────────

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
