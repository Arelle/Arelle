from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import MappingProxyType

import pytest

from arelle import XbrlConst
from arelle.oim._tc.metadata.model import (
    TCMetadata,
    TCTemplateConstraints,
    TCValueConstraint,
)
from arelle.oim._tc.report.common import TCReportValidationError
from arelle.oim._tc.report.validate import TCReportValidator
from arelle.oim.csv.metadata.model import (
    XbrlCsvDocumentInfo,
    XbrlCsvEffectiveMetadata,
    XbrlCsvTable,
)

_DOCUMENT_INFO = XbrlCsvDocumentInfo(
    document_type="https://xbrl.org/2021/xbrl-csv",
    namespaces=MappingProxyType({"xs": XbrlConst.xsd, "eg": "http://example.com/eg"}),
)


def _tables(**tables: XbrlCsvTable) -> XbrlCsvEffectiveMetadata:
    return XbrlCsvEffectiveMetadata(
        document_info=_DOCUMENT_INFO, tables=MappingProxyType(tables)
    )


def _tc(**templates: TCTemplateConstraints) -> TCMetadata:
    return TCMetadata(template_constraints=MappingProxyType(templates))


def _template(
    column_order: tuple[str, ...] | None = None, **constraints: TCValueConstraint
) -> TCTemplateConstraints:
    return TCTemplateConstraints(
        constraints=MappingProxyType(constraints), column_order=column_order
    )


def _run(
    csv_metadata: XbrlCsvEffectiveMetadata,
    tc_metadata: TCMetadata,
    files: Mapping[str, list[list[str]]],
    opened: list[str] | None = None,
) -> list[TCReportValidationError]:
    def open_table(table_id: str, table: XbrlCsvTable) -> Iterator[list[str]] | None:
        if opened is not None:
            opened.append(table.url)
        rows = files.get(table.url)
        return iter(rows) if rows is not None else None

    return list(TCReportValidator(csv_metadata, tc_metadata, open_table).validate())


def _codes(errors: list[TCReportValidationError]) -> list[str]:
    return [error.code for error in errors]


_SINGLE_TABLE = _tables(t=XbrlCsvTable(url="t.csv"))


class TestCells:
    def test_valid_rows_produce_no_errors(self) -> None:
        tc = _tc(
            t=_template(
                n=TCValueConstraint("xs:integer"),
                s=TCValueConstraint("xs:string", optional=True),
            )
        )
        rows = [
            ["n", "s", "other"],
            ["1", "a", ""],
            ["2", "", "x"],
            ["3", "#empty", ""],
        ]
        assert _run(_SINGLE_TABLE, tc, {"t.csv": rows}) == []

    def test_invalid_value_is_reported_with_its_location(self) -> None:
        tc = _tc(t=_template(n=TCValueConstraint("xs:integer")))
        (error,) = _run(_SINGLE_TABLE, tc, {"t.csv": [["n"], ["1"], ["x"]]})
        assert error.code == "tcre:invalidValue"
        assert (error.table_id, error.url, error.row, error.column) == (
            "t",
            "t.csv",
            3,
            "n",
        )
        assert (
            str(error)
            == "table 't' row 3 column 'n': value 'x' is not valid for the xs:integer constraint, url: t.csv"
        )

    @pytest.mark.parametrize(
        "constraint, value, expected_code",
        [
            (
                TCValueConstraint("xs:date", time_zone=True),
                "2024-01-01",
                "tcre:missingTimeZone",
            ),
            (
                TCValueConstraint("xs:date", time_zone=False),
                "2024-01-01Z",
                "tcre:unexpectedTimeZone",
            ),
            (
                TCValueConstraint("period", period_type="year"),
                "2024Q1",
                "tcre:invalidPeriodType",
            ),
            (
                TCValueConstraint("xs:duration", duration_type="dayTime"),
                "P1Y",
                "tcre:invalidDurationType",
            ),
            (TCValueConstraint("xs:decimal"), "1d-2", "tcre:invalidValue"),
        ],
    )
    def test_value_violations_use_the_validator_code(
        self, constraint: TCValueConstraint, value: str, expected_code: str
    ) -> None:
        errors = _run(
            _SINGLE_TABLE, _tc(t=_template(c=constraint)), {"t.csv": [["c"], [value]]}
        )
        assert _codes(errors) == [expected_code]

    def test_required_column_without_value_is_missing(self) -> None:
        tc = _tc(
            t=_template(
                n=TCValueConstraint("xs:integer"),
                c=TCValueConstraint("xs:string", optional=True),
            )
        )
        rows = [["c", "n"], ["x", ""], ["y", "#none"], ["z", "#nil"]]
        errors = _run(_SINGLE_TABLE, tc, {"t.csv": rows})
        assert _codes(errors) == [
            "tcre:missingValue",
            "tcre:missingValue",
            "tcre:invalidValue",
        ]
        assert [error.row for error in errors] == [2, 3, 4]
        assert (
            str(errors[0])
            == "table 't' row 2 column 'n': the column is required and has no value, url: t.csv"
        )

    def test_nil_is_allowed_when_nillable(self) -> None:
        tc = _tc(
            t=_template(n=TCValueConstraint("xs:integer", optional=True, nillable=True))
        )
        assert _run(_SINGLE_TABLE, tc, {"t.csv": [["n", "c"], ["#nil", "x"]]}) == []

    def test_nil_in_required_column_is_invalid_not_missing(self) -> None:
        tc = _tc(t=_template(n=TCValueConstraint("xs:integer")))
        assert _codes(_run(_SINGLE_TABLE, tc, {"t.csv": [["n"], ["#nil"]]})) == [
            "tcre:invalidValue"
        ]

    def test_unknown_special_value_is_reported(self) -> None:
        tc = _tc(t=_template(n=TCValueConstraint("xs:string")))
        errors = _run(
            _SINGLE_TABLE, tc, {"t.csv": [["n"], ["#foo"], ["##foo"], ["#empty"]]}
        )
        assert _codes(errors) == ["xbrlce:unknownSpecialValue"]

    def test_rows_without_any_value_are_skipped(self) -> None:
        tc = _tc(t=_template(n=TCValueConstraint("xs:integer")))
        rows = [["n", "c"], [], [""], ["", ""], ["", " "], ["1", ""]]
        (error,) = _run(_SINGLE_TABLE, tc, {"t.csv": rows})
        assert (error.code, error.row) == ("tcre:missingValue", 5)

    def test_short_rows_are_treated_as_empty_cells(self) -> None:
        tc = _tc(
            t=_template(
                n=TCValueConstraint("xs:integer", optional=True),
                s=TCValueConstraint("xs:string"),
            )
        )
        assert _codes(_run(_SINGLE_TABLE, tc, {"t.csv": [["s", "n"], ["a"]]})) == []
        assert _codes(_run(_SINGLE_TABLE, tc, {"t.csv": [["n", "s"], ["1"]]})) == [
            "tcre:missingValue"
        ]

    def test_repeated_header_uses_the_first_column(self) -> None:
        tc = _tc(t=_template(n=TCValueConstraint("xs:integer")))
        assert (
            _codes(_run(_SINGLE_TABLE, tc, {"t.csv": [["n", "n"], ["1", "x"]]})) == []
        )


class TestHeader:
    def test_required_column_missing_from_header(self) -> None:
        tc = _tc(
            t=_template(
                n=TCValueConstraint("xs:integer"),
                o=TCValueConstraint("xs:integer", optional=True),
            )
        )
        (error,) = _run(_SINGLE_TABLE, tc, {"t.csv": [["other"]]})
        assert (error.code, error.column, error.row) == (
            "tcre:missingColumn",
            "n",
            None,
        )
        assert (
            str(error)
            == "table 't' column 'n': column 'n' is missing from the header row, url: t.csv"
        )

    def test_empty_file_reports_required_columns(self) -> None:
        tc = _tc(t=_template(n=TCValueConstraint("xs:integer")))
        assert _codes(_run(_SINGLE_TABLE, tc, {"t.csv": []})) == ["tcre:missingColumn"]

    def test_column_order_requires_all_columns_once(self) -> None:
        tc = _tc(
            t=_template(
                column_order=("a", "b", "c"),
                a=TCValueConstraint("xs:string", optional=True),
            )
        )
        errors = _run(_SINGLE_TABLE, tc, {"t.csv": [["b"]]})
        assert _codes(errors) == ["tcre:missingColumn", "tcre:missingColumn"]
        assert [error.column for error in errors] == ["a", "c"]

    def test_column_order_is_enforced(self) -> None:
        tc = _tc(t=_template(column_order=("a", "b", "c")))
        assert _codes(_run(_SINGLE_TABLE, tc, {"t.csv": [["a", "b", "c"]]})) == []
        assert _codes(_run(_SINGLE_TABLE, tc, {"t.csv": [["c", "a", "b"]]})) == [
            "tcre:invalidColumnOrder"
        ]

    def test_missing_and_misordered_columns_are_both_reported(self) -> None:
        tc = _tc(t=_template(column_order=("a", "b", "c")))
        errors = _run(_SINGLE_TABLE, tc, {"t.csv": [["b", "a"]]})
        assert _codes(errors) == ["tcre:missingColumn", "tcre:invalidColumnOrder"]


class TestTables:
    def test_template_defaults_to_table_id_and_tables_share_templates(self) -> None:
        csv_metadata = _tables(
            t=XbrlCsvTable(url="t.csv"),
            u=XbrlCsvTable(url="u.csv", template="t"),
            v=XbrlCsvTable(url="v.csv", template="unconstrained"),
        )
        tc = _tc(
            t=_template(n=TCValueConstraint("xs:integer")),
            unconstrained=TCTemplateConstraints(),
        )
        files = {"t.csv": [["m"]], "u.csv": [["m"]], "v.csv": [["m"]]}
        opened: list[str] = []
        errors = _run(csv_metadata, tc, files, opened)
        assert [(error.table_id, error.url) for error in errors] == [
            ("t", "t.csv"),
            ("u", "u.csv"),
        ]
        assert opened == ["t.csv", "u.csv"], (
            "tables of templates without report checks are not read"
        )

    def test_tables_without_a_file_are_skipped(self) -> None:
        tc = _tc(t=_template(n=TCValueConstraint("xs:integer")))
        assert _run(_SINGLE_TABLE, tc, {}) == []

    def test_progress_is_reported_per_table(self) -> None:
        messages: list[str] = []
        tc = _tc(t=_template(n=TCValueConstraint("xs:integer")))
        validator = TCReportValidator(
            _SINGLE_TABLE,
            tc,
            lambda table_id, table: iter([["n"], ["1"]]),
            messages.append,
        )
        assert list(validator.validate()) == []
        assert messages == ["Validating table constraints of table t"]
