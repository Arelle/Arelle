from __future__ import annotations

import io
from typing import IO, Any
from unittest.mock import Mock

import pytest

from arelle import ModelRelationshipSet, ModelXbrl
from arelle.FileSource import FileSource
from arelle.ModelDtsObject import ModelRelationship
from arelle.oim.Load import (
    CSV_FACTS_FILE,
    NONE_CELL,
    getTaxonomyContextElement,
    openCsvReader,
    parseParameterValues,
)


def _mock_model_xbrl(dts_context_elements: list[str]) -> Mock:
    return Mock(
        spec=ModelXbrl,
        relationshipSet=lambda x: Mock(
            spec=ModelRelationshipSet,
            modelRelationships=[
                Mock(spec_set=ModelRelationship, contextElement=context_element)
                for context_element in dts_context_elements
            ]
        )
    )


class TestLoadFromOIM:

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("", ""),
            ("value", "value"),
            ("#empty", ""),
            ("#nil", None),
            ("#none", NONE_CELL),
            ("##escaped", "#escaped"),
        ],
    )
    def test_parse_parameter_values(self, value: str, expected: str | None) -> None:
        parameters = {"parameter": value}
        error = Mock()

        parseParameterValues(parameters, error)

        if expected is NONE_CELL:
            assert parameters["parameter"] is NONE_CELL
        else:
            assert parameters["parameter"] == expected
        error.assert_not_called()

    def test_parse_parameter_values_unknown_special_value(self) -> None:
        parameters = {"parameter": "#unknown"}
        error = Mock()

        parseParameterValues(parameters, error)

        assert parameters["parameter"] == "#unknown"
        error.assert_called_once()
        assert error.call_args.args[0] == "xbrlce:unknownSpecialValue"

    @pytest.mark.parametrize(
        "dts_context_elements, expected_context_element",
        [
            ([], "scenario"),
            (["scenario"], "scenario"),
            (["segment"], "segment"),
            (["segment", "scenario"], "scenario"),
        ]
    )
    def test_get_taxonomy_context_element(self, dts_context_elements: list[str], expected_context_element: str) -> None:
        model_xbrl = _mock_model_xbrl(dts_context_elements)

        result = getTaxonomyContextElement(model_xbrl)

        assert result == expected_context_element


def test_open_csv_reader_closes_the_file_after_iteration() -> None:
    handles: list[IO[Any]] = []

    def file(
        filepath: str, binary: bool = False, encoding: str | None = None
    ) -> tuple[IO[Any]]:
        handle: IO[Any] = (
            io.BytesIO(b"a,b\n1,2\n") if binary else io.StringIO("a,b\n1,2\n")
        )
        handles.append(handle)
        return (handle,)

    file_source = Mock(spec=FileSource, file=file)
    assert list(openCsvReader(file_source, "t.csv", CSV_FACTS_FILE)) == [
        ["a", "b"],
        ["1", "2"],
    ]
    assert all(handle.closed for handle in handles)
