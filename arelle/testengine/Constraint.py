"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from arelle.testengine.ErrorLevel import ErrorLevel

if TYPE_CHECKING:
    from arelle.ModelValue import QName

@dataclass(frozen=True)
class Constraint:
    count: int = 1
    level: ErrorLevel = ErrorLevel.ERROR
    pattern: str | None = None
    qname: QName | None = None

    def __str__(self) -> str:
        value = str(self.qname or self.pattern or '(any)')
        if self.level:
            value += f" [{self.level}]"
        if self.count != 1:
            value += f" x{self.count}"
        return value

    @staticmethod
    def normalize_constraints(
            constraints: list[Constraint]
    ) -> list[Constraint]:
        normalized_constraints_map: dict[tuple[QName | None, str | None, ErrorLevel], int] = {}
        for constraint in constraints:
            key = (
                constraint.qname,
                constraint.pattern,
                constraint.level,
            )
            if key not in normalized_constraints_map:
                normalized_constraints_map[key] = 0
            normalized_constraints_map[key] += constraint.count
        normalized_constraints = [
            Constraint(
                count=_count,
                level=_level,
                pattern=_pattern,
                qname=_qname,
            )
            for (
                _qname,
                _pattern,
                _level,
            ), _count in normalized_constraints_map.items()
        ]
        return normalized_constraints
