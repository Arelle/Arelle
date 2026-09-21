"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Iterable

from arelle.oim.const import (
    EMPTY_SPECIAL_VALUE,
    NIL_SPECIAL_VALUE,
    NONE_SPECIAL_VALUE,
    SPECIAL_VALUE_PREFIX,
)

_NULL_LITERALS = frozenset({NIL_SPECIAL_VALUE, NONE_SPECIAL_VALUE})


class UnknownSpecialValue(ValueError):
    """The literal starts with # but is not one of the xBRL-CSV special values."""


def effective_column_value(literal: str) -> str | None:
    """Applies xBRL-CSV special value processing to a cell literal."""
    if literal == "":
        return None
    return effective_parameter_value(literal)


def effective_parameter_value(literal: str | None) -> str | None:
    """Applies xBRL-CSV special value processing to a parameter literal, where an
    empty string is a value and only JSON null, #none and #nil are null."""
    if literal is None or literal in _NULL_LITERALS:
        return None
    if literal == EMPTY_SPECIAL_VALUE:
        return ""
    if literal.startswith(SPECIAL_VALUE_PREFIX * 2):
        return literal[1:]
    if literal.startswith(SPECIAL_VALUE_PREFIX):
        raise UnknownSpecialValue(literal)
    return literal


def row_has_value(row: Iterable[str]) -> bool:
    """True when any cell of the CSV row is a non empty string, whitespace included."""
    return any(cell != "" for cell in row)
