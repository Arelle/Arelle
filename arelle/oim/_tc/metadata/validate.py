"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Generator

from arelle.oim._model import OimReport
from arelle.oim._tc.const import (
    TC_NAMESPACES,
    TC_PREFIX,
    TCME_INVALID_NAMESPACE_PREFIX,
)
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCMetadata
from arelle.typing import TypeGetText

_: TypeGetText


class TCMetadataValidator:
    def __init__(self, oim_report: OimReport, tc_metadata: TCMetadata) -> None:
        self._oim_object = oim_report.oim_object
        self._namespaces = oim_report.namespaces
        self._tc_metadata = tc_metadata

    def validate(self) -> Generator[TCMetadataValidationError, None, None]:
        yield from self._validate_namespace_prefixes()

    def _validate_namespace_prefixes(self) -> Generator[TCMetadataValidationError, None, None]:
        for prefix, uri in self._namespaces.items():
            if uri in TC_NAMESPACES and prefix != TC_PREFIX:
                yield TCMetadataValidationError(
                    _(
                        "Table constraints namespace '{uri}' must be bound to prefix '{tc_prefix}', not '{prefix}'"
                    ).format(uri=uri, tc_prefix=TC_PREFIX, prefix=prefix),
                    code=TCME_INVALID_NAMESPACE_PREFIX,
                )
