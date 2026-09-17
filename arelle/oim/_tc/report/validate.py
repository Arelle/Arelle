"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator, Mapping
from dataclasses import dataclass

from arelle.oim._tc.const import TCRE_INVALID_COLUMN_ORDER, TCRE_MISSING_COLUMN
from arelle.oim._tc.metadata.model import (
    TCMetadata,
    TCTemplateConstraints,
    TCValueConstraint,
)
from arelle.oim._tc.report.common import TCReportValidationError
from arelle.oim.csv.metadata.model import XbrlCsvEffectiveMetadata, XbrlCsvTable
from arelle.typing import TypeGetText

_: TypeGetText

TableRows = Iterator[list[str]]
TableOpener = Callable[[str, XbrlCsvTable], TableRows | None]


@dataclass(frozen=True, slots=True)
class _ConstrainedColumn:
    name: str
    constraint: TCValueConstraint


@dataclass(frozen=True, slots=True)
class _Template:
    columns: tuple[_ConstrainedColumn, ...]
    column_order: tuple[str, ...] | None


class TCReportValidator:
    """Validates the data tables of an xBRL-CSV report against its table constraints,
    streaming rows from the effective metadata alone so no model is needed."""

    def __init__(
        self,
        csv_metadata: XbrlCsvEffectiveMetadata,
        tc_metadata: TCMetadata,
        open_table: TableOpener,
        report_progress: Callable[[str], None] | None = None,
    ) -> None:
        self._csv_metadata = csv_metadata
        self._tc_metadata = tc_metadata
        self._open_table = open_table
        self._report_progress = report_progress or (lambda message: None)
        self._templates = self._compile_templates()

    def _compile_templates(self) -> Mapping[str, _Template]:
        return {
            template_id: _Template(
                columns=tuple(
                    _ConstrainedColumn(name, constraint)
                    for name, constraint in tc.constraints.items()
                ),
                column_order=tc.column_order,
            )
            for template_id, tc in self._tc_metadata.template_constraints.items()
            if self._template_has_report_checks(tc)
        }

    @staticmethod
    def _template_has_report_checks(tc: TCTemplateConstraints) -> bool:
        return bool(tc.constraints) or tc.column_order is not None

    def validate(self) -> Generator[TCReportValidationError, None, None]:
        for table_id, table in self._csv_metadata.tables.items():
            template = self._templates.get(table.template or table_id)
            if template is None:
                continue
            rows = self._open_table(table_id, table)
            if rows is None:
                continue
            self._report_progress(
                _("Validating table constraints of table {}").format(table_id)
            )
            yield from self._validate_table(table_id, table, template, rows)

    def _validate_table(
        self, table_id: str, table: XbrlCsvTable, template: _Template, rows: TableRows
    ) -> Generator[TCReportValidationError, None, None]:
        header = next(rows, [])
        column_indexes: dict[str, int] = {}
        for index, name in enumerate(header):
            # The loader reports repeated identifiers, the first occurrence wins here.
            column_indexes.setdefault(name, index)
        yield from self._validate_header(table_id, table, template, column_indexes)

    def _validate_header(
        self,
        table_id: str,
        table: XbrlCsvTable,
        template: _Template,
        column_indexes: Mapping[str, int],
    ) -> Generator[TCReportValidationError, None, None]:
        missing_columns = [
            column.name
            for column in template.columns
            if not column.constraint.optional and column.name not in column_indexes
        ]
        if template.column_order is not None:
            missing_columns.extend(
                name
                for name in template.column_order
                if name not in column_indexes and name not in missing_columns
            )
        for name in missing_columns:
            yield TCReportValidationError(
                _("column '{}' is missing from the header row").format(name),
                code=TCRE_MISSING_COLUMN,
                table_id=table_id,
                url=table.url,
                column=name,
            )
        if template.column_order is None:
            return
        ordered_indexes = [
            column_indexes[name]
            for name in template.column_order
            if name in column_indexes
        ]
        if ordered_indexes != sorted(ordered_indexes):
            yield TCReportValidationError(
                _("columns must appear in the order {}").format(
                    ", ".join(template.column_order)
                ),
                code=TCRE_INVALID_COLUMN_ORDER,
                table_id=table_id,
                url=table.url,
            )
