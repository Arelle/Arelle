"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, Union

from arelle.PluginManager import pluginClassMethods

if TYPE_CHECKING:
    from arelle.ModelManager import ModelManager
    from arelle.typing import EmptyTuple


class ErrorManager:
    _errorCaptureLevel: int
    _errors: list[str | None]
    _logCount: dict[str, int] = {}
    _logHasRelevelerPlugin: bool
    _logRefFileRelUris: defaultdict[Any, dict[str, str]]
    _modelManager: ModelManager

    def __init__(self, modelManager: ModelManager, errorCaptureLevel: int):
        self._errorCaptureLevel = errorCaptureLevel
        self._errors = []
        self._logCount = {}
        self._logHasRelevelerPlugin: bool = any(True for m in pluginClassMethods("Logging.Severity.Releveler"))
        self._logRefFileRelUris = defaultdict(dict)
        self._modelManager = modelManager

    @property
    def errors(self) -> list[str | None]:
        return self._errors

    @property
    def logCount(self) -> dict[str, int]:
        return self._logCount

    def clear(self) -> None:
        self._errors.clear()
        self._logCount.clear()
