"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Generator

from arelle.oim._tc.const import (
    TC_NAMESPACES,
    TC_PARAMETERS_PROPERTY_NAME,
    TC_PREFIX,
    TCME_COLUMN_PARAMETER_CONFLICT,
    TCME_INVALID_NAMESPACE_PREFIX,
)
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCMetadata
from arelle.oim.csv.metadata.common import COLUMNS_KEY, TABLE_TEMPLATES_KEY
from arelle.oim.csv.metadata.model import XbrlCsvEffectiveMetadata
from arelle.typing import TypeGetText

_: TypeGetText


class TCMetadataValidator:
    def __init__(self, xbrl_csv_effective_metadata: XbrlCsvEffectiveMetadata, tc_metadata: TCMetadata) -> None:
        self._namespaces = xbrl_csv_effective_metadata.document_info.namespaces
        self._tc_metadata = tc_metadata

    def validate(self) -> Generator[TCMetadataValidationError, None, None]:
        yield from self._validate_namespace_prefixes()
        yield from self._validate_column_parameter_conflicts()

    def _validate_namespace_prefixes(self) -> Generator[TCMetadataValidationError, None, None]:
        for prefix, uri in self._namespaces.items():
            if uri in TC_NAMESPACES and prefix != TC_PREFIX:
                yield TCMetadataValidationError(
                    _("Table constraints namespace '{}' must be bound to prefix '{}', not '{}'").format(
                        uri, TC_PREFIX, prefix
                    ),
                    code=TCME_INVALID_NAMESPACE_PREFIX,
                )

    def _validate_column_parameter_conflicts(self) -> Generator[TCMetadataValidationError, None, None]:
        for template_id, tc in self._tc_metadata.template_constraints.items():
            for name in tc.constraints.keys() & tc.parameters.keys():
                yield TCMetadataValidationError(
                    _("Constrained column '{}' conflicts with parameter of the same name").format(name),
                    TABLE_TEMPLATES_KEY,
                    template_id,
                    COLUMNS_KEY,
                    name,
                    code=TCME_COLUMN_PARAMETER_CONFLICT,
                    related_paths=((TABLE_TEMPLATES_KEY, template_id, TC_PARAMETERS_PROPERTY_NAME, name),),
                )
