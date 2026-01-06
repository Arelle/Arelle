"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from dataclasses import dataclass

from arelle.ModelValue import QName
from arelle.testengine.ErrorLevel import ErrorLevel


@dataclass(frozen=True)
class ConstraintResult:
    code: str | QName | None
    diff: int
    level: ErrorLevel

    def __str__(self) -> str:
        if self.diff == 0:
            message = 'Matched'
        elif self.diff < 0:
            message = f'Missing {abs(self.diff)} expected'
        else:
            message = f'{self.diff} unexpected'
        return f"{message} {self.level} \"{self.code or '(any)'}\""
