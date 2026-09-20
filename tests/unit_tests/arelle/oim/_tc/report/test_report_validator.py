from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import MappingProxyType

import pytest

from arelle import XbrlConst
from arelle.oim._tc.metadata.model import (
    TCKeys,
    TCMetadata,
    TCTemplateConstraints,
    TCUniqueKey,
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
    column_order: tuple[str, ...] | None = None,
    parameters: Mapping[str, TCValueConstraint] | None = None,
    keys: TCKeys | None = None,
    **constraints: TCValueConstraint,
) -> TCTemplateConstraints:
    return TCTemplateConstraints(
        constraints=MappingProxyType(constraints),
        parameters=MappingProxyType(parameters or {}),
        keys=keys,
        column_order=column_order,
    )


def _run(
    csv_metadata: XbrlCsvEffectiveMetadata,
    tc_metadata: TCMetadata,
    files: Mapping[str, list[list[str]]],
    opened: list[str] | None = None,
    report_parameters: Mapping[str, str | None] | None = None,
) -> list[TCReportValidationError]:
    def open_table(table_id: str, table: XbrlCsvTable) -> Iterator[list[str]] | None:
        if opened is not None:
            opened.append(table.url)
        rows = files.get(table.url)
        return iter(rows) if rows is not None else None

    return list(
        TCReportValidator(
            csv_metadata, tc_metadata, report_parameters or {}, open_table
        ).validate()
    )


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
            {},
            lambda table_id, table: iter([["n"], ["1"]]),
            messages.append,
        )
        assert list(validator.validate()) == []
        assert messages == ["Validating table constraints of table t"]


class TestColumnParameterConflicts:
    _TC = _tc(
        t=_template(n=TCValueConstraint("xs:integer"), s=TCValueConstraint("xs:string"))
    )
    _ROWS = {"t.csv": [["n", "s", "u"], ["1", "a", "b"]]}

    def test_report_parameter_named_like_a_constrained_column(self) -> None:
        (error,) = _run(
            _SINGLE_TABLE, self._TC, self._ROWS, report_parameters={"n": "1"}
        )
        assert error.code == "tcre:columnParameterConflict"
        assert (
            str(error)
            == "table 't' parameter 'n': report parameter 'n' has the same name as a constrained column, url: t.csv"
        )

    def test_table_parameter_named_like_a_constrained_column(self) -> None:
        tables = _tables(
            t=XbrlCsvTable(url="t.csv", parameters=MappingProxyType({"s": "x"}))
        )
        errors = _run(tables, self._TC, self._ROWS)
        assert _codes(errors) == ["tcre:columnParameterConflict"]
        assert errors[0].parameter == "s"
        assert "table parameter 's' has the same name" in str(errors[0])

    def test_conflict_is_reported_once_per_table_and_name(self) -> None:
        tables = _tables(
            t=XbrlCsvTable(url="t.csv", parameters=MappingProxyType({"n": "1"})),
            u=XbrlCsvTable(url="t.csv", template="t"),
        )
        errors = _run(tables, self._TC, self._ROWS, report_parameters={"n": "2"})
        assert [(error.table_id, error.parameter) for error in errors] == [
            ("t", "n"),
            ("u", "n"),
        ]

    def test_unconstrained_column_names_do_not_conflict(self) -> None:
        tables = _tables(
            t=XbrlCsvTable(url="t.csv", parameters=MappingProxyType({"u": "x"}))
        )
        assert _run(tables, self._TC, self._ROWS, report_parameters={"u": "y"}) == []


def _parameter_table(**parameters: str) -> XbrlCsvEffectiveMetadata:
    return _tables(t=XbrlCsvTable(url="t.csv", parameters=MappingProxyType(parameters)))


class TestDefinedParameters:
    _ROWS = {"t.csv": [["n"], ["1"]]}

    @staticmethod
    def _tc(**parameters: TCValueConstraint) -> TCMetadata:
        return _tc(
            t=_template(parameters=parameters, n=TCValueConstraint("xs:integer"))
        )

    def test_valid_parameters_produce_no_errors(self) -> None:
        tc = self._tc(
            p=TCValueConstraint("xs:integer"), q=TCValueConstraint("xs:string")
        )
        tables = _parameter_table(p="1")
        assert _run(tables, tc, self._ROWS, report_parameters={"q": "a"}) == []

    def test_invalid_table_parameter_is_reported_with_its_location(self) -> None:
        tc = self._tc(p=TCValueConstraint("xs:integer"))
        (error,) = _run(_parameter_table(p="x"), tc, self._ROWS)
        assert (
            error.code,
            error.table_id,
            error.row,
            error.column,
            error.parameter,
        ) == (
            "tcre:invalidValue",
            "t",
            None,
            None,
            "p",
        )
        assert (
            str(error)
            == "table 't' parameter 'p': value 'x' is not valid for the xs:integer constraint, url: t.csv"
        )

    def test_invalid_report_parameter_is_reported(self) -> None:
        tc = self._tc(p=TCValueConstraint("xs:integer"))
        errors = _run(_SINGLE_TABLE, tc, self._ROWS, report_parameters={"p": "x"})
        assert _codes(errors) == ["tcre:invalidValue"]

    def test_table_parameter_shadows_the_report_parameter(self) -> None:
        tc = self._tc(p=TCValueConstraint("xs:integer"))
        tables = _parameter_table(p="1")
        assert _run(tables, tc, self._ROWS, report_parameters={"p": "x"}) == []
        errors = _run(
            _parameter_table(p="x"), tc, self._ROWS, report_parameters={"p": "1"}
        )
        assert _codes(errors) == ["tcre:invalidValue"]

    def test_required_parameter_without_a_value_is_missing(self) -> None:
        tc = self._tc(p=TCValueConstraint("xs:integer"))
        (error,) = _run(_SINGLE_TABLE, tc, self._ROWS)
        assert error.code == "tcre:missingValue"
        assert (
            str(error)
            == "table 't' parameter 'p': the parameter is required and has no value, url: t.csv"
        )

    @pytest.mark.parametrize("literal", ["#none", "#nil"])
    def test_null_special_values_leave_a_required_parameter_missing(
        self, literal: str
    ) -> None:
        tc = self._tc(p=TCValueConstraint("xs:integer", nillable=True))
        errors = _run(
            _parameter_table(p=literal), tc, self._ROWS, report_parameters={"p": "1"}
        )
        assert _codes(errors) == ["tcre:missingValue"]

    def test_optional_parameter_without_a_value_is_fine(self) -> None:
        tc = self._tc(p=TCValueConstraint("xs:integer", optional=True))
        assert _run(_SINGLE_TABLE, tc, self._ROWS) == []

    def test_nil_in_a_parameter_that_is_not_nillable_is_invalid(self) -> None:
        tc = self._tc(p=TCValueConstraint("xs:integer", optional=True))
        errors = _run(_parameter_table(p="#nil"), tc, self._ROWS)
        assert _codes(errors) == ["tcre:invalidValue"]

    def test_empty_string_is_a_value(self) -> None:
        tc = self._tc(p=TCValueConstraint("xs:string"))
        assert _run(_parameter_table(p=""), tc, self._ROWS) == []
        tc = self._tc(p=TCValueConstraint("xs:integer", optional=True))
        errors = _run(_SINGLE_TABLE, tc, self._ROWS, report_parameters={"p": ""})
        assert _codes(errors) == ["tcre:invalidValue"]

    def test_empty_special_value_is_validated_as_an_empty_string(self) -> None:
        tc = self._tc(p=TCValueConstraint("xs:string", min_length=1))
        errors = _run(_parameter_table(p="#empty"), tc, self._ROWS)
        assert _codes(errors) == ["tcre:invalidValue"]

    def test_unknown_special_values_are_left_to_the_loader(self) -> None:
        tc = self._tc(p=TCValueConstraint("xs:integer"))
        assert _run(_parameter_table(p="#bogus"), tc, self._ROWS) == []

    def test_report_parameter_is_checked_once_per_template(self) -> None:
        tc = _tc(
            a=_template(parameters={"p": TCValueConstraint("xs:integer")}),
            b=_template(parameters={"p": TCValueConstraint("xs:integer")}),
        )
        tables = _tables(
            a1=XbrlCsvTable(url="a1.csv", template="a"),
            a2=XbrlCsvTable(url="a2.csv", template="a"),
            a3=XbrlCsvTable(
                url="a3.csv", template="a", parameters=MappingProxyType({"p": "y"})
            ),
            b1=XbrlCsvTable(url="b1.csv", template="b"),
        )
        errors = _run(tables, tc, {}, report_parameters={"p": "x"})
        assert [error.table_id for error in errors] == ["a1", "a3", "b1"]

    def test_parameters_are_checked_when_the_table_file_is_missing(self) -> None:
        tc = self._tc(p=TCValueConstraint("xs:integer"))
        assert _codes(_run(_SINGLE_TABLE, tc, {})) == ["tcre:missingValue"]


class TestUninstantiatedTemplates:
    _TC = _tc(
        t=_template(n=TCValueConstraint("xs:integer")),
        u=_template(parameters={"p": TCValueConstraint("xs:integer")}),
    )
    _ROWS = {"t.csv": [["n"], ["1"]]}

    def test_supplied_report_parameter_is_checked(self) -> None:
        (error,) = _run(
            _SINGLE_TABLE, self._TC, self._ROWS, report_parameters={"p": "x"}
        )
        assert error.code == "tcre:invalidValue"
        assert (
            str(error)
            == "template 'u' parameter 'p': value 'x' is not valid for the xs:integer constraint"
        )

    def test_nil_is_checked_but_null_is_not_missing(self) -> None:
        errors = _run(
            _SINGLE_TABLE, self._TC, self._ROWS, report_parameters={"p": "#nil"}
        )
        assert _codes(errors) == ["tcre:invalidValue"]
        assert (
            _run(_SINGLE_TABLE, self._TC, self._ROWS, report_parameters={"p": "#none"})
            == []
        )
        assert _run(_SINGLE_TABLE, self._TC, self._ROWS) == []


def _unique(
    *fields: str,
    name: str = "k",
    severity: str = "error",
    shared: bool = False,
    sort: bool = False,
) -> TCKeys:
    return TCKeys(
        unique=(TCUniqueKey(name, fields, severity, shared),),
        sort_key=name if sort else None,
    )


class TestUniqueKeys:
    _INTEGER = TCValueConstraint("xs:integer")
    _STRING = TCValueConstraint("xs:string", optional=True, nillable=True)

    def test_duplicate_key_value_is_reported_on_the_later_row(self) -> None:
        tc = _tc(t=_template(keys=_unique("a", "b"), a=self._INTEGER, b=self._STRING))
        rows = [["a", "b"], ["1", "x"], ["1", "y"], ["1", "x"]]
        (error,) = _run(_SINGLE_TABLE, tc, {"t.csv": rows})
        assert (
            error.code,
            error.severity,
            error.table_id,
            error.row,
            error.column,
        ) == (
            "tcre:uniqueKeyViolation",
            "error",
            "t",
            4,
            None,
        )
        assert (
            str(error)
            == "table 't' row 4: unique key 'k' value ('1', 'x') appears in more than one row, url: t.csv"
        )

    def test_warning_severity_is_kept(self) -> None:
        tc = _tc(t=_template(keys=_unique("a", severity="warning"), a=self._INTEGER))
        (error,) = _run(_SINGLE_TABLE, tc, {"t.csv": [["a"], ["1"], ["1"]]})
        assert (error.code, error.severity) == ("tcre:uniqueKeyViolation", "warning")

    def test_values_compare_in_the_value_space(self) -> None:
        tc = _tc(t=_template(keys=_unique("a"), a=self._INTEGER))
        errors = _run(_SINGLE_TABLE, tc, {"t.csv": [["a"], ["1"], ["01"], ["+1"]]})
        assert [error.row for error in errors] == [3, 4]

    def test_nulls_are_equal_and_distinct_from_the_empty_string(self) -> None:
        tc = _tc(t=_template(keys=_unique("a"), a=self._STRING, b=self._STRING))
        rows = [["a", "b"], ["", "x"], ["#nil", "x"], ["#none", "x"], ["#empty", "x"]]
        errors = _run(_SINGLE_TABLE, tc, {"t.csv": rows})
        assert [error.row for error in errors] == [3, 4]

    def test_rows_without_a_value_are_skipped(self) -> None:
        tc = _tc(t=_template(keys=_unique("a"), a=self._STRING))
        assert _run(_SINGLE_TABLE, tc, {"t.csv": [["a"], [""], [""]]}) == []

    def test_key_spans_tables_of_one_template(self) -> None:
        tables = _tables(
            t1=XbrlCsvTable(url="a.csv", template="t"),
            t2=XbrlCsvTable(url="b.csv", template="t"),
        )
        tc = _tc(t=_template(keys=_unique("a"), a=self._INTEGER))
        files = {"a.csv": [["a"], ["1"]], "b.csv": [["a"], ["2"], ["1"]]}
        (error,) = _run(tables, tc, files)
        assert (error.table_id, error.row) == ("t2", 3)

    def test_shared_key_spans_templates(self) -> None:
        tables = _tables(t=XbrlCsvTable(url="t.csv"), u=XbrlCsvTable(url="u.csv"))
        tc = _tc(
            t=_template(keys=_unique("a", shared=True), a=self._INTEGER),
            u=_template(keys=_unique("b", shared=True), b=self._INTEGER),
        )
        files = {"t.csv": [["a"], ["1"]], "u.csv": [["b"], ["1"]]}
        (error,) = _run(tables, tc, files)
        assert (error.table_id, error.row) == ("u", 2)

    def test_keys_with_different_names_are_independent(self) -> None:
        tables = _tables(t=XbrlCsvTable(url="t.csv"), u=XbrlCsvTable(url="u.csv"))
        tc = _tc(
            t=_template(keys=_unique("a", name="k1"), a=self._INTEGER),
            u=_template(keys=_unique("b", name="k2"), b=self._INTEGER),
        )
        files = {"t.csv": [["a"], ["1"]], "u.csv": [["b"], ["1"]]}
        assert _run(tables, tc, files) == []

    def test_parameter_fields_are_constant_per_table(self) -> None:
        tables = _tables(
            t1=XbrlCsvTable(url="a.csv", template="t", parameters={"p": "x"}),
            t2=XbrlCsvTable(url="b.csv", template="t", parameters={"p": "y"}),
            t3=XbrlCsvTable(url="b.csv", template="t", parameters={"p": "x"}),
        )
        tc = _tc(
            t=_template(
                keys=_unique("p", "a"),
                parameters={"p": self._STRING},
                a=self._INTEGER,
            )
        )
        files = {"a.csv": [["a"], ["1"]], "b.csv": [["a"], ["1"]]}
        (error,) = _run(tables, tc, files)
        assert (error.table_id, error.row) == ("t3", 2)
        assert "('x', '1')" in str(error)

    def test_report_parameter_field_falls_back_to_the_report(self) -> None:
        tc = _tc(
            t=_template(
                keys=_unique("p", "a"),
                parameters={"p": self._STRING},
                a=self._INTEGER,
            )
        )
        rows = [["a"], ["1"], ["1"]]
        (error,) = _run(
            _SINGLE_TABLE, tc, {"t.csv": rows}, report_parameters={"p": "#nil"}
        )
        assert "(null, '1')" in str(error)

    def test_missing_column_field_is_null(self) -> None:
        tc = _tc(t=_template(keys=_unique("a", "b"), a=self._INTEGER, b=self._STRING))
        errors = _run(_SINGLE_TABLE, tc, {"t.csv": [["a"], ["1"], ["1"]]})
        assert _codes(errors) == ["tcre:uniqueKeyViolation"]
        assert "('1', null)" in str(errors[0])

    def test_unknown_special_value_keeps_its_literal(self) -> None:
        tc = _tc(t=_template(keys=_unique("a"), a=self._STRING))
        errors = _run(_SINGLE_TABLE, tc, {"t.csv": [["a"], ["#bogus"], ["#bogus"]]})
        assert _codes(errors) == [
            "xbrlce:unknownSpecialValue",
            "xbrlce:unknownSpecialValue",
            "tcre:uniqueKeyViolation",
        ]


class TestSortKeys:
    _INTEGER = TCValueConstraint("xs:integer")
    _STRING = TCValueConstraint("xs:string", optional=True, nillable=True)

    def test_sorted_rows_produce_no_errors(self) -> None:
        tc = _tc(
            t=_template(
                keys=_unique("a", "b", sort=True), a=self._INTEGER, b=self._STRING
            )
        )
        rows = [["a", "b"], ["1", ""], ["1", "a"], ["2", ""], ["10", "b"]]
        assert _run(_SINGLE_TABLE, tc, {"t.csv": rows}) == []

    def test_first_row_out_of_order_is_reported_once(self) -> None:
        tc = _tc(t=_template(keys=_unique("a", sort=True), a=self._INTEGER))
        rows = [["a"], ["3"], ["2"], ["1"], ["4"]]
        (error,) = _run(_SINGLE_TABLE, tc, {"t.csv": rows})
        assert (error.code, error.table_id, error.row, error.column) == (
            "tcre:sortKeyViolation",
            "t",
            3,
            None,
        )
        assert (
            str(error)
            == "table 't' row 3: sort key 'k' value ('2') does not follow the preceding rows, url: t.csv"
        )

    def test_equal_rows_violate_both_sort_and_unique_keys(self) -> None:
        tc = _tc(t=_template(keys=_unique("a", sort=True), a=self._INTEGER))
        errors = _run(_SINGLE_TABLE, tc, {"t.csv": [["a"], ["1"], ["01"]]})
        assert _codes(errors) == ["tcre:uniqueKeyViolation", "tcre:sortKeyViolation"]

    def test_tie_is_resolved_by_the_next_field(self) -> None:
        tc = _tc(
            t=_template(
                keys=_unique("a", "b", sort=True), a=self._INTEGER, b=self._STRING
            )
        )
        rows = [["a", "b"], ["1", "b"], ["1", "a"]]
        assert _codes(_run(_SINGLE_TABLE, tc, {"t.csv": rows})) == [
            "tcre:sortKeyViolation"
        ]

    def test_null_sorts_first(self) -> None:
        tc = _tc(t=_template(keys=_unique("a", sort=True), a=self._STRING))
        assert _run(_SINGLE_TABLE, tc, {"t.csv": [["a"], ["#nil"], ["a"]]}) == []
        assert _codes(_run(_SINGLE_TABLE, tc, {"t.csv": [["a"], ["a"], ["#nil"]]})) == [
            "tcre:sortKeyViolation"
        ]

    def test_invalid_values_are_left_out_of_the_order(self) -> None:
        tc = _tc(t=_template(keys=_unique("a", sort=True), a=self._INTEGER))
        sorted_rows = [["a"], ["2"], ["x"], ["3"]]
        assert _codes(_run(_SINGLE_TABLE, tc, {"t.csv": sorted_rows})) == [
            "tcre:invalidValue"
        ]
        unsorted_rows = [["a"], ["2"], ["x"], ["1"]]
        assert _codes(_run(_SINGLE_TABLE, tc, {"t.csv": unsorted_rows})) == [
            "tcre:invalidValue",
            "tcre:sortKeyViolation",
        ]

    def test_invalid_later_field_leaves_the_row_out_of_the_order(self) -> None:
        tc = _tc(
            t=_template(
                keys=_unique("a", "b", sort=True), a=self._INTEGER, b=self._INTEGER
            )
        )
        rows = [["a", "b"], ["2", "1"], ["1", "x"]]
        assert _codes(_run(_SINGLE_TABLE, tc, {"t.csv": rows})) == [
            "tcre:invalidValue"
        ]

    def test_only_the_sort_key_is_checked_for_order(self) -> None:
        keys = TCKeys(
            unique=(
                TCUniqueKey("u", ("a",), "error", False),
                TCUniqueKey("s", ("b",), "error", False),
            ),
            sort_key="s",
        )
        tc = _tc(t=_template(keys=keys, a=self._INTEGER, b=self._INTEGER))
        other_key_unsorted = [["a", "b"], ["2", "1"], ["1", "2"]]
        assert _run(_SINGLE_TABLE, tc, {"t.csv": other_key_unsorted}) == []
        sort_key_unsorted = [["a", "b"], ["1", "2"], ["2", "1"]]
        (error,) = _run(_SINGLE_TABLE, tc, {"t.csv": sort_key_unsorted})
        assert "sort key 's'" in str(error)

    def test_parameter_field_precedes_column_fields(self) -> None:
        tc = _tc(
            t=_template(
                keys=_unique("p", "a", sort=True),
                parameters={"p": self._INTEGER},
                a=self._INTEGER,
            )
        )
        rows = [["a"], ["2"], ["1"]]
        (error,) = _run(_parameter_table(p="4"), tc, {"t.csv": rows})
        assert "('4', '1')" in str(error)

    def test_tables_are_sorted_independently(self) -> None:
        tables = _tables(
            t1=XbrlCsvTable(url="a.csv", template="t"),
            t2=XbrlCsvTable(url="b.csv", template="t"),
        )
        tc = _tc(t=_template(keys=_unique("a", sort=True), a=self._INTEGER))
        files = {"a.csv": [["a"], ["3"]], "b.csv": [["a"], ["1"]]}
        assert _run(tables, tc, files) == []
