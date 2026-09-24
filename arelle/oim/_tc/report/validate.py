"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Generator, Iterator, Mapping
from dataclasses import dataclass
from itertools import combinations

from arelle.oim._tc.const import (
    TCRE_COLUMN_PARAMETER_CONFLICT,
    TCRE_INVALID_COLUMN_ORDER,
    TCRE_INVALID_DURATION_TYPE,
    TCRE_INVALID_PERIOD_TYPE,
    TCRE_INVALID_VALUE,
    TCRE_MISSING_COLUMN,
    TCRE_MISSING_TIME_ZONE,
    TCRE_MISSING_VALUE,
    TCRE_SORT_KEY_VIOLATION,
    TCRE_UNEXPECTED_TIME_ZONE,
    TCRE_UNIQUE_KEY_VIOLATION,
)
from arelle.oim._tc.metadata.model import (
    TCMetadata,
    TCTemplateConstraints,
    TCUniqueKey,
    TCValueConstraint,
)
from arelle.oim._tc.report.cell import (
    UnknownSpecialValue,
    effective_column_value,
    effective_parameter_value,
    row_has_value,
)
from arelle.oim._tc.report.common import TCReportValidationError
from arelle.oim._tc.report.key_values import KeyFieldType, KeyValues, SortTracker
from arelle.oim._tc.report.keys import KeyStore, MemoryKeyStore
from arelle.oim._tc.value_validator import ValueConstraintValidator
from arelle.oim.const import NIL_SPECIAL_VALUE, XBRLCE_UNKNOWN_SPECIAL_VALUE
from arelle.oim.csv.metadata.model import XbrlCsvEffectiveMetadata, XbrlCsvTable
from arelle.typing import TypeGetText

_: TypeGetText

TableRows = Iterator[list[str]]
TableOpener = Callable[[str, XbrlCsvTable], TableRows | None]

_PROGRESS_ROW_INTERVAL = 1000
_COLUMN = "column"
_PARAMETER = "parameter"


@dataclass(frozen=True, slots=True)
class _ConstraintSubject:
    name: str
    kind: str
    constraint: TCValueConstraint
    validator: ValueConstraintValidator


@dataclass(frozen=True, slots=True)
class _KeyField:
    name: str
    is_parameter: bool
    field_type: KeyFieldType


@dataclass(frozen=True, slots=True)
class _UniqueKey:
    name: str
    fields: tuple[_KeyField, ...]
    severity: str
    store: KeyStore


@dataclass(frozen=True, slots=True)
class _Template:
    columns: tuple[_ConstraintSubject, ...]
    parameters: tuple[_ConstraintSubject, ...]
    column_order: tuple[str, ...] | None
    unique_keys: tuple[_UniqueKey, ...]
    sort_key: str | None


@dataclass(frozen=True, slots=True)
class _FieldSource(ABC):
    """Where a key field of one table takes its value from."""

    field_type: KeyFieldType

    @abstractmethod
    def value(self, row: list[str]) -> str | None:
        """The effective value of the field in a row."""


@dataclass(frozen=True, slots=True)
class _ColumnField(_FieldSource):
    """A key field read from a column of the table."""

    column_index: int

    def value(self, row: list[str]) -> str | None:
        literal = row[self.column_index] if self.column_index < len(row) else ""
        try:
            return effective_column_value(literal)
        except UnknownSpecialValue:
            # Reported as a cell error, the literal still takes part in the key.
            return literal


@dataclass(frozen=True, slots=True)
class _ConstantField(_FieldSource):
    """A key field with the same value in every row, a parameter or a missing column."""

    constant: str | None

    def value(self, row: list[str]) -> str | None:
        return self.constant


@dataclass(frozen=True, slots=True)
class _TableKey:
    key: _UniqueKey
    sources: tuple[_FieldSource, ...]
    sort: SortTracker | None = None


@dataclass(frozen=True, slots=True)
class _TableRange:
    table_id: str
    table: XbrlCsvTable
    first: KeyValues
    last: KeyValues


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
        report_parameters: Mapping[str, str | None],
        open_table: TableOpener,
        report_progress: Callable[[str], None] | None = None,
    ) -> None:
        self._csv_metadata = csv_metadata
        self._tc_metadata = tc_metadata
        self._report_parameters = report_parameters
        self._open_table = open_table
        self._report_progress = report_progress or (lambda message: None)
        # Metadata validation requires keys that share a name to be marked shared, so
        # one store serves them all.
        self._key_stores: dict[str, KeyStore] = {}
        self._templates = self._compile_templates()

    def _compile_templates(self) -> Mapping[str, _Template]:
        return {
            template_id: _Template(
                columns=self._compile_subjects(tc.constraints, _COLUMN),
                parameters=self._compile_subjects(tc.parameters, _PARAMETER),
                column_order=tc.column_order,
                unique_keys=self._compile_unique_keys(tc),
                sort_key=tc.keys.sort_key if tc.keys is not None else None,
            )
            for template_id, tc in self._tc_metadata.template_constraints.items()
            if self._template_has_report_checks(tc)
        }

    def _compile_unique_keys(self, tc: TCTemplateConstraints) -> tuple[_UniqueKey, ...]:
        if tc.keys is None or tc.keys.unique is None:
            return ()
        return tuple(
            _UniqueKey(
                key.name,
                self._compile_key_fields(tc, key),
                key.severity,
                self._key_stores.setdefault(key.name, MemoryKeyStore()),
            )
            for key in tc.keys.unique
        )

    def _compile_key_fields(
        self, tc: TCTemplateConstraints, key: TCUniqueKey
    ) -> tuple[_KeyField, ...]:
        namespaces = self._csv_metadata.document_info.namespaces
        fields = []
        for name in key.fields:
            is_parameter = name in tc.parameters
            constraint = tc.parameters[name] if is_parameter else tc.constraints[name]
            fields.append(
                _KeyField(name, is_parameter, KeyFieldType(constraint, namespaces))
            )
        return tuple(fields)

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
        return (
            bool(tc.constraints)
            or bool(tc.parameters)
            or tc.column_order is not None
            or tc.keys is not None
        )

    def validate(self) -> Generator[TCReportValidationError, None, None]:
        tables = self._csv_metadata.tables
        instantiated = {
            table.template or table_id for table_id, table in tables.items()
        }
        for template_id in self._templates:
            if template_id not in instantiated:
                yield from self._validate_uninstantiated_template(template_id)
        checked_report_params: set[tuple[str, str]] = set()
        sort_ranges: dict[str, list[_TableRange]] = {}
        for table_id, table in tables.items():
            template_id = table.template or table_id
            template = self._templates.get(template_id)
            if template is None:
                continue
            yield from self._validate_parameter_conflicts(table_id, table, template)
            yield from self._validate_defined_parameters(table_id, table, template_id, template, checked_report_params)
            rows = self._open_table(table_id, table)
            if rows is None:
                continue
            self._report_progress(_("Validating table constraints of table {}").format(table_id))
            sort = SortTracker() if template.sort_key is not None else None
            yield from self._validate_table(table_id, table, template, rows, sort)
            if sort is not None and sort.first is not None and sort.last is not None:
                sort_ranges.setdefault(template_id, []).append(
                    _TableRange(table_id, table, sort.first, sort.last)
                )
        for template_id, ranges in sort_ranges.items():
            yield from self._validate_sort_ranges(self._templates[template_id], ranges)

    def _validate_uninstantiated_template(self, template_id: str) -> Generator[TCReportValidationError, None, None]:
        for parameter in self._templates[template_id].parameters:
            literal = self._report_parameters.get(parameter.name)
            if literal is None:
                continue
            if violation := self._validate_parameter(parameter, literal, required=False):
                yield TCReportValidationError(
                    violation.message,
                    code=violation.code,
                    template_id=template_id,
                    parameter=parameter.name,
                )

    def _validate_parameter_conflicts(
        self, table_id: str, table: XbrlCsvTable, template: _Template
    ) -> Generator[TCReportValidationError, None, None]:
        for column in template.columns:
            if column.name in table.parameters:
                message = _(
                    "table parameter '{}' has the same name as a constrained column"
                )
            elif column.name in self._report_parameters:
                message = _(
                    "report parameter '{}' has the same name as a constrained column"
                )
            else:
                continue
            yield TCReportValidationError(
                message.format(column.name),
                code=TCRE_COLUMN_PARAMETER_CONFLICT,
                table_id=table_id,
                url=table.url,
                parameter=column.name,
            )

    def _validate_defined_parameters(
        self,
        table_id: str,
        table: XbrlCsvTable,
        template_id: str,
        template: _Template,
        checked_report_params: set[tuple[str, str]],
    ) -> Generator[TCReportValidationError, None, None]:
        for parameter in template.parameters:
            if parameter.name in table.parameters:
                literal: str | None = table.parameters[parameter.name]
            else:
                report_parameter_key = (template_id, parameter.name)
                if report_parameter_key in checked_report_params:
                    continue
                checked_report_params.add(report_parameter_key)
                literal = self._report_parameters.get(parameter.name)
            param_required = not parameter.constraint.optional
            if violation := self._validate_parameter(parameter, literal, param_required):
                yield TCReportValidationError(
                    violation.message,
                    code=violation.code,
                    table_id=table_id,
                    url=table.url,
                    parameter=parameter.name,
                )

    def _validate_table(
        self,
        table_id: str,
        table: XbrlCsvTable,
        template: _Template,
        rows: TableRows,
        sort: SortTracker | None,
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
        table_keys = tuple(
            _TableKey(
                key,
                self._field_sources(table, key.fields, column_indexes),
                sort if key.name == template.sort_key else None,
            )
            for key in template.unique_keys
        )
        for row_number, row in enumerate(rows, start=2):
            if row_number % _PROGRESS_ROW_INTERVAL == 0:
                self._report_progress(
                    _("Validating table constraints of table {} row {}").format(
                        table_id, row_number
                    )
                )
            yield from self._validate_row(
                table_id, table, present_columns, table_keys, row_number, row
            )

    @staticmethod
    def _validate_sort_ranges(
        template: _Template, ranges: list[_TableRange]
    ) -> Generator[TCReportValidationError, None, None]:
        for earlier, later in combinations(ranges, 2):
            if earlier.last >= later.first and later.last >= earlier.first:
                yield TCReportValidationError(
                    _("sort key '{}' rows overlap with those of table '{}'").format(
                        template.sort_key, earlier.table_id
                    ),
                    code=TCRE_SORT_KEY_VIOLATION,
                    table_id=later.table_id,
                    url=later.table.url,
                )

    def _field_sources(
        self,
        table: XbrlCsvTable,
        fields: tuple[_KeyField, ...],
        column_indexes: Mapping[str, int],
    ) -> tuple[_FieldSource, ...]:
        sources: list[_FieldSource] = []
        for field in fields:
            if field.is_parameter:
                constant = self._effective_parameter_value(table, field.name)
                sources.append(_ConstantField(field.field_type, constant))
            elif field.name in column_indexes:
                sources.append(_ColumnField(field.field_type, column_indexes[field.name]))
            else:
                # A missing column is reported once and its field is null in every row.
                sources.append(_ConstantField(field.field_type, None))
        return tuple(sources)

    def _effective_parameter_value(self, table: XbrlCsvTable, name: str) -> str | None:
        literal = table.parameters.get(name)
        if literal is None:
            literal = self._report_parameters.get(name)
        try:
            return effective_parameter_value(literal)
        except UnknownSpecialValue:
            return literal

    def _validate_row(
        self,
        table_id: str,
        table: XbrlCsvTable,
        present_columns: list[tuple[_ConstraintSubject, int]],
        table_keys: tuple[_TableKey, ...],
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
        for table_key in table_keys:
            values = _field_values(table_key.sources, row)
            key_values = _key_values(table_key.sources, values)
            if not table_key.key.store.add(key_values):
                yield TCReportValidationError(
                    _("unique key '{}' value {} appears in more than one row").format(
                        table_key.key.name, _describe_values(values)
                    ),
                    code=TCRE_UNIQUE_KEY_VIOLATION,
                    table_id=table_id,
                    url=table.url,
                    severity=table_key.key.severity,
                    row=row_number,
                )
            if table_key.sort is not None and not table_key.sort.add(key_values):
                yield TCReportValidationError(
                    _("sort key '{}' value {} does not follow the preceding rows").format(
                        table_key.key.name, _describe_values(values)
                    ),
                    code=TCRE_SORT_KEY_VIOLATION,
                    table_id=table_id,
                    url=table.url,
                    row=row_number,
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
    def _validate_parameter(parameter: _ConstraintSubject, literal: str | None, required: bool) -> _Violation | None:
        try:
            value = effective_parameter_value(literal)
        except UnknownSpecialValue:
            # The loader reports unknown special values in parameters.
            return None
        return _validate_value(parameter, literal, value, required)

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


def _field_values(
    sources: tuple[_FieldSource, ...], row: list[str]
) -> tuple[str | None, ...]:
    return tuple(source.value(row) for source in sources)


def _key_values(
    sources: tuple[_FieldSource, ...], values: tuple[str | None, ...]
) -> KeyValues:
    return tuple(
        source.field_type.key_value(value) for source, value in zip(sources, values)
    )


def _describe_values(values: tuple[str | None, ...]) -> str:
    return "({})".format(
        ", ".join("null" if value is None else repr(value) for value in values)
    )


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
