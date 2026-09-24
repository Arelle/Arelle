from __future__ import annotations

import io
from unittest.mock import Mock

import pytest

from arelle import ModelRelationshipSet, ModelXbrl
from arelle.FileSource import FileSource
from arelle.ModelDtsObject import ModelRelationship
from arelle.oim.Load import (
    CSV_FACTS_FILE,
    NONE_CELL,
    OIMException,
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


def _stream_file_source(data: bytes, streams: list[io.BytesIO]) -> Mock:
    def stream(filepath: str) -> io.BytesIO:
        handle = io.BytesIO(data)
        streams.append(handle)
        return handle

    return Mock(spec=FileSource, stream=stream)


def test_open_csv_reader_opens_the_file_once_and_closes_it() -> None:
    streams: list[io.BytesIO] = []
    file_source = _stream_file_source(b"a,b\n1,2\n", streams)
    assert list(openCsvReader(file_source, "t.csv", CSV_FACTS_FILE)) == [
        ["a", "b"],
        ["1", "2"],
    ]
    (stream,) = streams
    assert stream.closed


def test_open_csv_reader_closes_the_file_when_a_check_fails() -> None:
    streams: list[io.BytesIO] = []
    file_source = _stream_file_source("a,b\n".encode("utf-16"), streams)
    with pytest.raises(OIMException):
        openCsvReader(file_source, "t.csv", CSV_FACTS_FILE)
    (stream,) = streams
    assert stream.closed


def test_open_csv_reader_keeps_line_breaks_inside_quoted_cells() -> None:
    file_source = _stream_file_source(b'a,b\r\n"x\r\ny",2\r\n', [])
    assert list(openCsvReader(file_source, "t.csv", CSV_FACTS_FILE)) == [["a", "b"], ["x\r\ny", "2"]]
