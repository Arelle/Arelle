"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from enum import Enum


class ErrorLevel(Enum):
    OK = "OK"
    SATISIFED = "SATISIFED"
    NOT_SATISFIED = "NOT_SATISFIED"
    WARNING = "WARNING"
    ERROR = "ERROR"

    def __str__(self) -> str:
        return self.value
