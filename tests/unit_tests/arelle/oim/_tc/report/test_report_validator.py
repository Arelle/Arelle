from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import MappingProxyType

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

    def test_repeated_header_uses_the_first_column(self) -> None:
        tc = _tc(t=_template(column_order=("a", "b")))
        assert _codes(_run(_SINGLE_TABLE, tc, {"t.csv": [["a", "b", "a"]]})) == []


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
