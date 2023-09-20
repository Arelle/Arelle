"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Level(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True)
class Validation:
    level: Level
    codes: str | tuple[str, ...]
    msg: str
    args: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def error(
        codes: str | tuple[str, ...],
        msg: str,
        **kwargs: Any,
    ) -> Validation:
        return Validation(level=Level.ERROR, codes=codes, msg=msg, args=kwargs)

    @staticmethod
    def warning(
        codes: str | tuple[str, ...],
        msg: str,
        **kwargs: Any,
    ) -> Validation:
        return Validation(level=Level.WARNING, codes=codes, msg=msg, args=kwargs)
