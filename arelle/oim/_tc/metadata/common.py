"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from arelle.oim._tc.common import TCError


class TCMetadataValidationError(TCError):
    def __init__(self, message: str, *path: str, code: str) -> None:
        self.path_segments: list[str] = list(path)
        self._message = message
        super().__init__(code)

    def prepend_path(self, *segments: str) -> None:
        self.path_segments = [*segments, *self.path_segments]

    @property
    def json_pointer(self) -> str:
        return "/" + "/".join(self.path_segments)

    def __str__(self) -> str:
        if self.path_segments:
            return f"{self.json_pointer}: {self._message}"
        return self._message
