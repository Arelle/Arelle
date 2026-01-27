"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass

from arelle.testengine.ErrorLevel import ErrorLevel


@dataclass(frozen=True)
class ActualError:
    code: str
    level: ErrorLevel

    def __str__(self) -> str:
        if self.level:
            return f"{self.code} [{self.level}]"
        return self.code
