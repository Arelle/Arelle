"""
Constants and enums for duplicate fact validation.
Kept in a separate module so that API and Cntlr* code can import these lightweight types
without pulling in the heavy model/validation imports of ValidateDuplicateFacts.

See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import Enum, Flag, auto
from typing import Any


class DuplicateType(Flag):
    NONE = 0
    INCONSISTENT = auto()
    CONSISTENT = auto()
    INCOMPLETE = auto()
    COMPLETE = auto()

    # Flags before 3.11 did not support iterating Flag values,
    # so we have to override with our own iterator. Remove when we no longer support 3.10
    def __iter__(self) -> Iterator[DuplicateType]:
        # num must be a positive integer
        num = self.value
        while num:
            b = num & (~num + 1)
            yield DuplicateType(b)
            num ^= b

    @property
    def description(self) -> str:
        return "|".join([str(n.name) for n in self if n.name]).lower()


class DuplicateTypeArg(Enum):
    NONE = "none"
    INCONSISTENT = "inconsistent"
    CONSISTENT = "consistent"
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"
    ALL = "all"

    def duplicateType(self) -> DuplicateType:
        return DUPLICATE_TYPE_ARG_MAP.get(self, DuplicateType.NONE)


class DeduplicationType(Enum):
    COMPLETE = "complete"
    CONSISTENT_PAIRS = "consistent-pairs"
    CONSISTENT_SETS = "consistent-sets"


DUPLICATE_TYPE_ARG_MAP = {
    DuplicateTypeArg.NONE: DuplicateType.NONE,
    DuplicateTypeArg.INCONSISTENT: DuplicateType.INCONSISTENT,
    DuplicateTypeArg.CONSISTENT: DuplicateType.CONSISTENT,
    DuplicateTypeArg.INCOMPLETE: DuplicateType.INCOMPLETE,
    DuplicateTypeArg.COMPLETE: DuplicateType.COMPLETE,
    DuplicateTypeArg.ALL: DuplicateType.INCONSISTENT | DuplicateType.CONSISTENT,
}


class FactValueEqualityType(Enum):
    DEFAULT = "default"
    DATETIME = "datetime"
    LANGUAGE = "language"


TypeFactValueEqualityKey = tuple[FactValueEqualityType, tuple[Any, ...]]
