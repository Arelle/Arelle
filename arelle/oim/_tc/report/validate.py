"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator, Mapping
from dataclasses import dataclass

from arelle.oim._tc.const import (
    TCRE_INVALID_COLUMN_ORDER,
    TCRE_INVALID_VALUE,
    TCRE_MISSING_COLUMN,
    TCRE_MISSING_VALUE,
)
from arelle.oim._tc.metadata.model import (
    TCMetadata,
    TCTemplateConstraints,
    TCValueConstraint,
)
from arelle.oim._tc.report.cell import (
    UnknownSpecialValue,
    effective_value,
    row_has_value,
)
from arelle.oim._tc.report.common import TCReportValidationError
from arelle.oim.const import NIL_SPECIAL_VALUE, XBRLCE_UNKNOWN_SPECIAL_VALUE
from arelle.oim.csv.metadata.model import XbrlCsvEffectiveMetadata, XbrlCsvTable
from arelle.typing import TypeGetText

_: TypeGetText

TableRows = Iterator[list[str]]
TableOpener = Callable[[str, XbrlCsvTable], TableRows | None]

_PROGRESS_ROW_INTERVAL = 1000


@dataclass(frozen=True, slots=True)
class _ConstrainedColumn:
    name: str
    constraint: TCValueConstraint


@dataclass(frozen=True, slots=True)
class _Template:
    columns: tuple[_ConstrainedColumn, ...]
    column_order: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class _CellViolation:
    code: str
    message: str


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
        present_columns = [
            (column, column_indexes[column.name])
            for column in template.columns
            if column.name in column_indexes
        ]
        for row_number, row in enumerate(rows, start=2):
            if row_number % _PROGRESS_ROW_INTERVAL == 0:
                self._report_progress(
                    _("Validating table constraints of table {} row {}").format(
                        table_id, row_number
                    )
                )
            yield from self._validate_row(
                table_id, table, present_columns, row_number, row
            )

    def _validate_row(
        self,
        table_id: str,
        table: XbrlCsvTable,
        present_columns: list[tuple[_ConstrainedColumn, int]],
        row_number: int,
        row: list[str],
    ) -> Generator[TCReportValidationError, None, None]:
        if not row_has_value(row):
            return
        for column, index in present_columns:
            literal = row[index] if index < len(row) else ""
            violation = self._validate_cell(column, literal)
            if violation is not None:
                yield TCReportValidationError(
                    violation.message,
                    code=violation.code,
                    table_id=table_id,
                    url=table.url,
                    row=row_number,
                    column=column.name,
                )

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

    @staticmethod
    def _validate_cell(
        column: _ConstrainedColumn, literal: str
    ) -> _CellViolation | None:
        constraint = column.constraint
        if literal == NIL_SPECIAL_VALUE and not constraint.nillable:
            return _CellViolation(
                TCRE_INVALID_VALUE,
                _("#nil is not permitted, the column is not nillable"),
            )
        try:
            value = effective_value(literal)
        except UnknownSpecialValue:
            return _CellViolation(
                XBRLCE_UNKNOWN_SPECIAL_VALUE,
                _("unknown special value {!r}").format(literal),
            )
        if value is None and not constraint.optional:
            return _CellViolation(
                TCRE_MISSING_VALUE, _("the column is required and has no value")
            )
        return None
