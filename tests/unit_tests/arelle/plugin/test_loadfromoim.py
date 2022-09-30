from __future__ import annotations
from unittest.mock import Mock

import pytest

from arelle import ModelRelationshipSet, ModelXbrl
from arelle.ModelDtsObject import ModelRelationship
from arelle.plugin.loadFromOIM import getTaxonomyContextElement


def _mock_model_xbrl(dts_context_elements: list[str]):
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
        "dts_context_elements, expected_context_element",
        [
            ([], "scenario"),
            (["scenario"], "scenario"),
            (["segment"], "segment"),
            (["segment", "scenario"], "scenario"),
        ]
    )
    def test_get_taxonomy_context_element(self, dts_context_elements: list[str], expected_context_element: str):
        model_xbrl = _mock_model_xbrl(dts_context_elements)

        result = getTaxonomyContextElement(model_xbrl)

        assert result == expected_context_element
