"""
See COPYRIGHT.md for copyright information.
Type hints for Arelle.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict, TypeVar  # pylint: disable=no-name-in-module

try:
    from typing import assert_type as assert_type
except ImportError:
    T = TypeVar('T')
    def assert_type(x: T, _: Any, /) -> T:
        return x

TypeGetText = Callable[[str], str]

OptionalString = TypeVar("OptionalString", str, None)

EmptyTuple = tuple[()]


class LocaleDict(TypedDict):
    """Helps with typing arelle.Locale Module.

    Structure based on locale.localeconv and
    https://peps.python.org/pep-0589/
    """
    # Key -> example
    int_curr_symbol: str  # USD
    currency_symbol: str  # $
    mon_decimal_point: str  # '.'
    mon_thousands_sep: str  # ','
    mon_grouping: list[int]  # [3, 3, 0]
    positive_sign: str  # '' / '+'
    negative_sign: str  # '-'
    int_frac_digits: int  # 2
    frac_digits: int  # 2
    p_cs_precedes: int  # 1
    p_sep_by_space: int  # 0
    n_cs_precedes: int  # 1
    n_sep_by_space: int  # 0
    p_sign_posn: int  # 1
    n_sign_posn: int  # 1
    decimal_point: str  # '.'
    thousands_sep: str  # ','
    grouping: list[int]  # [3, 3, 0]
