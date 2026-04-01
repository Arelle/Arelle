"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from arelle.oim._model import OimReport
from arelle.oim._tc.const import (
    TC_COLUMN_ORDER_PROPERTY_NAME,
    TC_CONSTRAINTS_PROPERTY_NAME,
    TC_KEYS_PROPERTY_NAME,
    TC_NAMESPACES,
    TC_PARAMETERS_PROPERTY_NAME,
    TC_PREFIX,
    TC_TABLE_CONSTRAINTS_PROPERTY_NAME,
    TCME_INVALID_NAMESPACE_PREFIX,
    TCME_MISPLACED_OR_UNKNOWN_PROPERTY,
)
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCMetadata
from arelle.typing import TypeGetText

_: TypeGetText

_TC_PREFIX_COLON = f"{TC_PREFIX}:"

_TABLE_TEMPLATES_KEY = "tableTemplates"
_COLUMNS_KEY = "columns"

_TEMPLATE_TC_PROPERTIES = frozenset(
    {
        TC_COLUMN_ORDER_PROPERTY_NAME,
        TC_KEYS_PROPERTY_NAME,
        TC_PARAMETERS_PROPERTY_NAME,
        TC_TABLE_CONSTRAINTS_PROPERTY_NAME,
    }
)

_COLUMN_TC_PROPERTIES = frozenset(
    {
        TC_CONSTRAINTS_PROPERTY_NAME,
    }
)


class TCMetadataValidator:
    def __init__(self, oim_report: OimReport, tc_metadata: TCMetadata) -> None:
        self._oim_object = oim_report.oim_object
        self._namespaces = oim_report.namespaces
        self._tc_metadata = tc_metadata

    def validate(self) -> Generator[TCMetadataValidationError, None, None]:
        yield from self._validate_namespace_prefixes()
        yield from self._validate_misplaced_tc_properties()

    def _validate_namespace_prefixes(self) -> Generator[TCMetadataValidationError, None, None]:
        for prefix, uri in self._namespaces.items():
            if uri in TC_NAMESPACES and prefix != TC_PREFIX:
                yield TCMetadataValidationError(
                    _(
                        "Table constraints namespace '{uri}' must be bound to prefix '{tc_prefix}', not '{prefix}'"
                    ).format(uri=uri, tc_prefix=TC_PREFIX, prefix=prefix),
                    code=TCME_INVALID_NAMESPACE_PREFIX,
                )

    def _validate_misplaced_tc_properties(self) -> Generator[TCMetadataValidationError, None, None]:
        for key, value in self._oim_object.items():
            if key.startswith(_TC_PREFIX_COLON):
                yield self._misplaced_property_error(key)
            elif key == _TABLE_TEMPLATES_KEY:
                yield from self._validate_table_templates_properties(value)
            else:
                yield from self._walk_value(value, key)

    def _validate_table_templates_properties(
        self,
        table_templates: Any,
    ) -> Generator[TCMetadataValidationError, None, None]:
        if not isinstance(table_templates, dict):
            return
        for template_id, template_obj in table_templates.items():
            if not isinstance(template_obj, dict):
                continue
            for key, value in template_obj.items():
                if key.startswith(_TC_PREFIX_COLON) and key not in _TEMPLATE_TC_PROPERTIES:
                    yield self._misplaced_property_error(_TABLE_TEMPLATES_KEY, template_id, key)
                if key == _COLUMNS_KEY:
                    yield from self._validate_column_properties(template_id, value)
                else:
                    yield from self._walk_value(value, _TABLE_TEMPLATES_KEY, template_id, key)

    def _validate_column_properties(
        self, template_id: str, columns: Any
    ) -> Generator[TCMetadataValidationError, None, None]:
        if not isinstance(columns, dict):
            return
        for col_id, col_obj in columns.items():
            if not isinstance(col_obj, dict):
                continue
            for key, value in col_obj.items():
                if key.startswith(_TC_PREFIX_COLON) and key not in _COLUMN_TC_PROPERTIES:
                    yield self._misplaced_property_error(_TABLE_TEMPLATES_KEY, template_id, _COLUMNS_KEY, col_id, key)
                yield from self._walk_value(value, _TABLE_TEMPLATES_KEY, template_id, _COLUMNS_KEY, col_id, key)

    def _walk_value(self, value: Any, *path: str) -> Generator[TCMetadataValidationError, None, None]:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.startswith(_TC_PREFIX_COLON):
                    yield self._misplaced_property_error(*path, key)
                yield from self._walk_value(child, *path, key)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                yield from self._walk_value(item, *path, str(i))

    @staticmethod
    def _misplaced_property_error(*path: str) -> TCMetadataValidationError:
        property_name = path[-1]
        return TCMetadataValidationError(
            _("Misplaced or unknown property: {property}").format(property=property_name),
            *path,
            code=TCME_MISPLACED_OR_UNKNOWN_PROPERTY,
        )
