"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Iterable

from arelle.oim._tc.common import TCError


class TCMetadataValidationError(TCError):
    """Represents a validation error at one or more JSON pointer locations.

    All paths must share the same frame of reference, either all relative
    (to be prefixed via prepend_path later) or all absolute. Callers must
    not mix relative and absolute paths on a single error.
    """

    def __init__(
        self,
        message: str,
        *path: str,
        code: str,
        related_paths: Iterable[Iterable[str]] = (),
    ) -> None:
        self._message = message
        self._paths: list[list[str]] = [list(p) for p in (path, *related_paths) if p]
        super().__init__(code)

    @property
    def json_pointers(self) -> list[str]:
        return [self._encode_path(p) for p in self._paths]

    def prepend_path(self, *segments: str) -> None:
        if not segments:
            return
        if not self._paths:
            self._paths.append(list(segments))
            return
        for path in self._paths:
            path[:0] = list(segments)

    @staticmethod
    def _encode_path(segments: Iterable[str]) -> str:
        return "/" + "/".join(s.replace("~", "~0").replace("/", "~1") for s in segments)

    def __str__(self) -> str:
        if json_pointers := self.json_pointers:
            return ", ".join(json_pointers) + ": " + self._message
        return self._message
