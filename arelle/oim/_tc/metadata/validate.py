"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Generator

from arelle.oim._tc.const import (
    TC_COLUMN_ORDER_PROPERTY_NAME,
    TC_NAMESPACES,
    TC_PARAMETERS_PROPERTY_NAME,
    TC_PREFIX,
    TCME_COLUMN_PARAMETER_CONFLICT,
    TCME_INCONSISTENT_COLUMN_ORDER_DEFINITION,
    TCME_INVALID_NAMESPACE_PREFIX,
)
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCMetadata
from arelle.oim.csv.metadata.common import COLUMNS_KEY, TABLE_TEMPLATES_KEY
from arelle.oim.csv.metadata.model import XbrlCsvEffectiveMetadata, XbrlCsvTableTemplate
from arelle.typing import TypeGetText

_: TypeGetText


class TCMetadataValidator:
    def __init__(self, xbrl_csv_effective_metadata: XbrlCsvEffectiveMetadata, tc_metadata: TCMetadata) -> None:
        self._namespaces = xbrl_csv_effective_metadata.document_info.namespaces
        self._table_templates = xbrl_csv_effective_metadata.table_templates
        self._tc_metadata = tc_metadata

    def validate(self) -> Generator[TCMetadataValidationError, None, None]:
        yield from self._validate_namespace_prefixes()
        yield from self._validate_column_parameter_conflicts()
        yield from self._validate_column_order()

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

    def _validate_column_order(self) -> Generator[TCMetadataValidationError, None, None]:
        for template_id, tc in self._tc_metadata.template_constraints.items():
            if tc.column_order is None:
                continue
            csv_template: XbrlCsvTableTemplate | None = self._table_templates.get(template_id)
            if csv_template is None:
                continue
            known_columns = set(csv_template.columns)
            column_order_set = set(tc.column_order)
            base_path = (TABLE_TEMPLATES_KEY, template_id, TC_COLUMN_ORDER_PROPERTY_NAME)
            missing_from_order = sorted(col for col in known_columns if col not in column_order_set)
            if missing_from_order:
                yield TCMetadataValidationError(
                    _("Not all columns defined for the template are included in tc:columnOrder"),
                    *base_path,
                    code=TCME_INCONSISTENT_COLUMN_ORDER_DEFINITION,
                    related_paths=tuple(
                        (TABLE_TEMPLATES_KEY, template_id, COLUMNS_KEY, col) for col in missing_from_order
                    ),
                )
            unknown_in_order = [index for index, col in enumerate(tc.column_order) if col not in known_columns]
            if unknown_in_order:
                yield TCMetadataValidationError(
                    _("tc:columnOrder contains column names not defined in the template"),
                    *base_path,
                    code=TCME_INCONSISTENT_COLUMN_ORDER_DEFINITION,
                    related_paths=tuple(
                        (TABLE_TEMPLATES_KEY, template_id, TC_COLUMN_ORDER_PROPERTY_NAME, str(index))
                        for index in unknown_in_order
                    ),
                )
