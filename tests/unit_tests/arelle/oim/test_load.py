from __future__ import annotations

from unittest.mock import Mock

import pytest

from arelle import ModelRelationshipSet, ModelXbrl
from arelle.ModelDtsObject import ModelRelationship
from arelle.oim.Load import (
    NONE_CELL,
    getTaxonomyContextElement,
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
