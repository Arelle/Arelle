"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator, Mapping
from dataclasses import dataclass

from arelle.oim._tc.const import (
    TCRE_INVALID_COLUMN_ORDER,
    TCRE_INVALID_DURATION_TYPE,
    TCRE_INVALID_PERIOD_TYPE,
    TCRE_INVALID_VALUE,
    TCRE_MISSING_COLUMN,
    TCRE_MISSING_TIME_ZONE,
    TCRE_MISSING_VALUE,
    TCRE_UNEXPECTED_TIME_ZONE,
)
from arelle.oim._tc.metadata.model import (
    TCMetadata,
    TCTemplateConstraints,
    TCValueConstraint,
)
from arelle.oim._tc.report.cell import (
    UnknownSpecialValue,
    effective_column_value,
    row_has_value,
)
from arelle.oim._tc.report.common import TCReportValidationError
from arelle.oim._tc.value_validator import ValueConstraintValidator
from arelle.oim.const import NIL_SPECIAL_VALUE, XBRLCE_UNKNOWN_SPECIAL_VALUE
from arelle.oim.csv.metadata.model import XbrlCsvEffectiveMetadata, XbrlCsvTable
from arelle.typing import TypeGetText

_: TypeGetText

TableRows = Iterator[list[str]]
TableOpener = Callable[[str, XbrlCsvTable], TableRows | None]

_PROGRESS_ROW_INTERVAL = 1000
_COLUMN = "column"


@dataclass(frozen=True, slots=True)
class _ConstraintSubject:
    name: str
    kind: str
    constraint: TCValueConstraint
    validator: ValueConstraintValidator


@dataclass(frozen=True, slots=True)
class _Template:
    columns: tuple[_ConstraintSubject, ...]
    column_order: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class _Violation:
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
                columns=self._compile_subjects(tc.constraints, _COLUMN),
                column_order=tc.column_order,
            )
            for template_id, tc in self._tc_metadata.template_constraints.items()
            if self._template_has_report_checks(tc)
        }

    def _compile_subjects(
        self, constraints: Mapping[str, TCValueConstraint], kind: str
    ) -> tuple[_ConstraintSubject, ...]:
        namespaces = self._csv_metadata.document_info.namespaces
        return tuple(
            _ConstraintSubject(
                name, kind, constraint, ValueConstraintValidator(constraint, namespaces)
            )
            for name, constraint in constraints.items()
        )

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
        present_columns: list[tuple[_ConstraintSubject, int]],
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
    def _validate_cell(column: _ConstraintSubject, literal: str) -> _Violation | None:
        try:
            value = effective_column_value(literal)
        except UnknownSpecialValue:
            return _Violation(
                XBRLCE_UNKNOWN_SPECIAL_VALUE,
                _("unknown special value {!r}").format(literal),
            )
        return _validate_value(column, literal, value, not column.constraint.optional)


def _validate_value(
    subject: _ConstraintSubject, literal: str | None, value: str | None, required: bool
) -> _Violation | None:
    constraint = subject.constraint
    if literal == NIL_SPECIAL_VALUE and not constraint.nillable:
        return _Violation(
            TCRE_INVALID_VALUE,
            _("#nil is not permitted, the {} is not nillable").format(subject.kind),
        )
    if value is None:
        if not required:
            return None
        return _Violation(
            TCRE_MISSING_VALUE,
            _("the {} is required and has no value").format(subject.kind),
        )
    code = subject.validator.first_violation(value)
    if code is None:
        return None
    return _Violation(code, _describe_violation(code, value, constraint))


def _describe_violation(code: str, value: str, constraint: TCValueConstraint) -> str:
    if code == TCRE_MISSING_TIME_ZONE:
        return _("value {!r} must have a time zone").format(value)
    if code == TCRE_UNEXPECTED_TIME_ZONE:
        return _("value {!r} must not have a time zone").format(value)
    if code == TCRE_INVALID_PERIOD_TYPE:
        return _("value {!r} is not a period of type {}").format(
            value, constraint.period_type
        )
    if code == TCRE_INVALID_DURATION_TYPE:
        return _("value {!r} is not a duration of type {}").format(
            value, constraint.duration_type
        )
    return _("value {!r} is not valid for the {} constraint").format(
        value, constraint.type
    )
