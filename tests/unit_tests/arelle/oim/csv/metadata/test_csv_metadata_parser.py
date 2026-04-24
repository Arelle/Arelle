"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from typing import Any

import pytest

from arelle.oim.csv.metadata.model import (
    XbrlCsvColumn,
    XbrlCsvDimensions,
    XbrlCsvPropertyGroup,
    XbrlCsvTable,
)
from arelle.oim.csv.metadata.parser import (
    _parse_column,
    _parse_dimensions,
    _parse_features,
    _parse_final,
    _parse_link_group,
    _parse_link_targets,
    _parse_links,
    _parse_property_group,
    _parse_table,
    _parse_table_template,
    _parse_tables,
    parse_xbrl_csv_metadata,
)

DOCUMENT_TYPE = "https://xbrl.org/2021/xbrl-csv"


def _minimal_document_info() -> dict[str, Any]:
    return {"documentType": DOCUMENT_TYPE, "taxonomy": ["schema.xsd"]}


def _minimal_oim(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    oim: dict[str, Any] = {"documentInfo": _minimal_document_info()}
    if extra:
        oim.update(extra)
    return oim


class TestParseDimensions:
    def test_none_returns_none(self) -> None:
        assert _parse_dimensions(None) is None

    def test_empty_returns_none(self) -> None:
        assert _parse_dimensions({}) is None

    def test_non_dict_returns_none(self) -> None:
        assert _parse_dimensions("not a dict") is None
        assert _parse_dimensions([1, 2]) is None
        assert _parse_dimensions(42) is None

    def test_core_only(self) -> None:
        result = _parse_dimensions({"concept": "a:Revenue", "period": "2024"})
        assert result == XbrlCsvDimensions(concept="a:Revenue", period="2024")
        assert result is not None
        assert result.taxonomy_defined == {}

    def test_taxonomy_defined_only(self) -> None:
        result = _parse_dimensions({"pfx:dim": "val"})
        assert result is not None
        assert result.concept is None
        assert result.entity is None
        assert result.period is None
        assert result.unit is None
        assert result.language is None
        assert result.taxonomy_defined == {"pfx:dim": "val"}

    def test_mixed(self) -> None:
        result = _parse_dimensions({"concept": "a:X", "pfx:dim": "val", "unit": "iso4217:USD"})
        assert result is not None
        assert result.concept == "a:X"
        assert result.unit == "iso4217:USD"
        assert result.taxonomy_defined == {"pfx:dim": "val"}

    def test_all_core_keys(self) -> None:
        dims = {
            "concept": "a:X",
            "entity": "scheme:123",
            "period": "2024-01-01T00:00:00/P1Y",
            "unit": "iso4217:USD",
            "language": "en",
        }
        result = _parse_dimensions(dims)
        assert result == XbrlCsvDimensions(
            concept="a:X",
            entity="scheme:123",
            period="2024-01-01T00:00:00/P1Y",
            unit="iso4217:USD",
            language="en",
        )
        assert result.taxonomy_defined == {}

    def test_non_str_core_dim_filtered(self) -> None:
        result = _parse_dimensions({"concept": 42, "entity": "scheme:123"})
        assert result is not None
        assert result.concept is None
        assert result.entity == "scheme:123"

    def test_non_str_taxonomy_defined_key_filtered(self) -> None:
        result = _parse_dimensions({42: "val", "pfx:good": "val2"})
        assert result is not None
        assert result.taxonomy_defined == {"pfx:good": "val2"}

    def test_non_str_taxonomy_defined_value_filtered(self) -> None:
        result = _parse_dimensions({"pfx:good": "val", "pfx:bad": 99})
        assert result is not None
        assert result.taxonomy_defined == {"pfx:good": "val"}

    def test_taxonomy_defined_none_value_allowed(self) -> None:
        result = _parse_dimensions({"pfx:dim": None})
        assert result is not None
        assert result.taxonomy_defined == {"pfx:dim": None}

    def test_bool_taxonomy_defined_value_filtered(self) -> None:
        result = _parse_dimensions({"pfx:dim": True, "pfx:good": "val"})
        assert result is not None
        assert result.taxonomy_defined == {"pfx:good": "val"}

    def test_bool_core_dim_filtered(self) -> None:
        result = _parse_dimensions({"concept": True, "entity": "scheme:123"})
        assert result is not None
        assert result.concept is None
        assert result.entity == "scheme:123"

    def test_all_entries_filtered_returns_dimensions(self) -> None:
        result = _parse_dimensions({42: "val", 99: "other"})
        assert result is not None
        assert result.concept is None
        assert result.taxonomy_defined == {}


class TestParsePropertyGroup:
    def test_minimal(self) -> None:
        result = _parse_property_group({})
        assert result == XbrlCsvPropertyGroup()
        assert result.decimals is None
        assert result.dimensions is None

    def test_with_decimals_and_dimensions(self) -> None:
        result = _parse_property_group({"decimals": 2, "dimensions": {"concept": "a:X"}})
        assert result.decimals == 2
        assert result.dimensions == XbrlCsvDimensions(concept="a:X")

    def test_int_decimals_allowed(self) -> None:
        result = _parse_property_group({"decimals": 0})
        assert result.decimals == 0

    def test_str_decimals_allowed(self) -> None:
        result = _parse_property_group({"decimals": "$decimalsParam"})
        assert result.decimals == "$decimalsParam"

    def test_bool_decimals_filtered(self) -> None:
        result = _parse_property_group({"decimals": True})
        assert result.decimals is None

    def test_float_decimals_filtered(self) -> None:
        result = _parse_property_group({"decimals": 2.5})
        assert result.decimals is None

    def test_list_decimals_filtered(self) -> None:
        result = _parse_property_group({"decimals": [2]})
        assert result.decimals is None

    def test_non_dict_dimensions_filtered(self) -> None:
        result = _parse_property_group({"dimensions": "not a dict"})
        assert result.dimensions is None

    def test_list_dimensions_filtered(self) -> None:
        result = _parse_property_group({"dimensions": ["concept", "a:X"]})
        assert result.dimensions is None


class TestParseColumn:
    def test_empty_column(self) -> None:
        result = _parse_column({})
        assert result == XbrlCsvColumn()
        assert result.comment is False
        assert result.decimals is None
        assert result.dimensions is None
        assert result.property_groups == {}
        assert result.properties_from == ()

    def test_comment_true(self) -> None:
        result = _parse_column({"comment": True})
        assert result.comment is True

    def test_comment_false(self) -> None:
        result = _parse_column({"comment": False})
        assert result.comment is False

    def test_non_bool_comment_filtered(self) -> None:
        result = _parse_column({"comment": "yes"})
        assert result.comment is False

    def test_int_comment_filtered(self) -> None:
        result = _parse_column({"comment": 1})
        assert result.comment is False

    def test_with_dimensions_and_decimals(self) -> None:
        result = _parse_column(
            {
                "decimals": "$decimalsParam",
                "dimensions": {"concept": "a:Revenue", "pfx:d": "val"},
            }
        )
        assert result.decimals == "$decimalsParam"
        assert result.dimensions is not None
        assert result.dimensions.concept == "a:Revenue"
        assert result.dimensions.taxonomy_defined == {"pfx:d": "val"}

    def test_with_property_groups(self) -> None:
        result = _parse_column(
            {
                "propertyGroups": {
                    "group1": {"decimals": 3},
                    "group2": {"dimensions": {"unit": "iso4217:EUR"}},
                }
            }
        )
        assert len(result.property_groups) == 2
        assert result.property_groups["group1"].decimals == 3
        assert result.property_groups["group2"].dimensions == XbrlCsvDimensions(unit="iso4217:EUR")

    def test_with_properties_from(self) -> None:
        result = _parse_column({"propertiesFrom": ["colA", "colB"]})
        assert result.properties_from == ("colA", "colB")

    def test_bool_decimals_filtered(self) -> None:
        result = _parse_column({"decimals": True})
        assert result.decimals is None

    def test_wrong_type_decimals_filtered(self) -> None:
        result = _parse_column({"decimals": [1, 2]})
        assert result.decimals is None

    def test_non_dict_property_groups_gives_empty(self) -> None:
        result = _parse_column({"propertyGroups": "not a dict"})
        assert result.property_groups == {}

    def test_non_dict_property_group_entry_filtered(self) -> None:
        result = _parse_column({"propertyGroups": {"good": {"decimals": 1}, "bad": "oops"}})
        assert len(result.property_groups) == 1
        assert "good" in result.property_groups

    def test_non_str_property_group_key_filtered(self) -> None:
        result = _parse_column({"propertyGroups": {42: {"decimals": 1}, "good": {"decimals": 2}}})
        assert len(result.property_groups) == 1
        assert "good" in result.property_groups

    def test_non_str_properties_from_entry_filtered(self) -> None:
        result = _parse_column({"propertiesFrom": ["colA", 42, "colB"]})
        assert result.properties_from == ("colA", "colB")

    def test_non_list_properties_from_gives_empty_tuple(self) -> None:
        result = _parse_column({"propertiesFrom": "not a list"})
        assert result.properties_from == ()

    def test_dict_properties_from_gives_empty_tuple(self) -> None:
        result = _parse_column({"propertiesFrom": {"colA": True}})
        assert result.properties_from == ()

    def test_empty_properties_from_list_gives_empty_tuple(self) -> None:
        result = _parse_column({"propertiesFrom": []})
        assert result.properties_from == ()

    def test_none_in_properties_from_filtered(self) -> None:
        result = _parse_column({"propertiesFrom": ["colA", None, "colB"]})
        assert result.properties_from == ("colA", "colB")


class TestParseTableTemplate:
    def test_minimal(self) -> None:
        result = _parse_table_template({"columns": {}})
        assert result.columns == {}
        assert result.row_id_column is None
        assert result.decimals is None
        assert result.dimensions is None

    def test_no_columns_key_gives_empty(self) -> None:
        result = _parse_table_template({})
        assert result.columns == {}

    def test_full(self) -> None:
        result = _parse_table_template(
            {
                "columns": {"c1": {"decimals": 2}},
                "rowIdColumn": "id",
                "decimals": 4,
                "dimensions": {"concept": "a:X"},
            }
        )
        assert result.row_id_column == "id"
        assert result.decimals == 4
        assert result.dimensions == XbrlCsvDimensions(concept="a:X")
        assert "c1" in result.columns
        assert result.columns["c1"].decimals == 2

    def test_non_dict_columns_gives_empty(self) -> None:
        result = _parse_table_template({"columns": "not a dict"})
        assert result.columns == {}

    def test_non_dict_column_entry_filtered(self) -> None:
        result = _parse_table_template({"columns": {"good": {"decimals": 2}, "bad": "oops"}})
        assert len(result.columns) == 1
        assert "good" in result.columns

    def test_non_str_column_key_filtered(self) -> None:
        result = _parse_table_template({"columns": {42: {"decimals": 2}, "good": {"decimals": 3}}})
        assert len(result.columns) == 1
        assert "good" in result.columns

    def test_wrong_type_row_id_column_filtered(self) -> None:
        result = _parse_table_template({"columns": {}, "rowIdColumn": 42})
        assert result.row_id_column is None

    def test_bool_decimals_filtered(self) -> None:
        result = _parse_table_template({"columns": {}, "decimals": True})
        assert result.decimals is None

    def test_str_decimals_allowed(self) -> None:
        result = _parse_table_template({"columns": {}, "decimals": "$param"})
        assert result.decimals == "$param"


class TestParseTable:
    def test_minimal(self) -> None:
        result = _parse_table("facts.csv", {})
        assert result.url == "facts.csv"
        assert result.template is None
        assert result.optional is False
        assert result.parameters == {}

    def test_full(self) -> None:
        result = _parse_table("facts.csv", {"template": "t1", "optional": True, "parameters": {"p1": "v1"}})
        assert result == XbrlCsvTable(url="facts.csv", template="t1", optional=True, parameters={"p1": "v1"})

    def test_empty_parameters(self) -> None:
        result = _parse_table("facts.csv", {"parameters": {}})
        assert result.parameters == {}

    def test_wrong_type_template_filtered(self) -> None:
        result = _parse_table("f.csv", {"template": 42})
        assert result.template is None

    def test_list_template_filtered(self) -> None:
        result = _parse_table("f.csv", {"template": ["t1"]})
        assert result.template is None

    def test_non_bool_optional_filtered(self) -> None:
        result = _parse_table("f.csv", {"optional": "yes"})
        assert result.optional is False

    def test_int_optional_filtered(self) -> None:
        result = _parse_table("f.csv", {"optional": 1})
        assert result.optional is False

    def test_non_str_parameter_value_filtered(self) -> None:
        result = _parse_table("f.csv", {"parameters": {"good": "v1", "bad": 99}})
        assert result.parameters == {"good": "v1"}

    def test_non_str_parameter_key_filtered(self) -> None:
        result = _parse_table("f.csv", {"parameters": {42: "v2", "good": "v1"}})
        assert result.parameters == {"good": "v1"}

    def test_non_dict_parameters_gives_empty(self) -> None:
        result = _parse_table("f.csv", {"parameters": "not a dict"})
        assert result.parameters == {}


class TestParseTables:
    def test_non_dict_gives_empty(self) -> None:
        assert _parse_tables("not a dict") == {}
        assert _parse_tables(42) == {}
        assert _parse_tables(None) == {}
        assert _parse_tables([]) == {}

    def test_empty_dict_gives_empty(self) -> None:
        assert _parse_tables({}) == {}

    def test_minimal_table(self) -> None:
        result = _parse_tables({"t1": {"url": "facts.csv"}})
        assert "t1" in result
        assert result["t1"].url == "facts.csv"

    def test_table_without_url_dropped(self) -> None:
        result = _parse_tables({"good": {"url": "f.csv"}, "bad": {}})
        assert "good" in result
        assert "bad" not in result

    def test_table_with_non_str_url_dropped(self) -> None:
        result = _parse_tables({"good": {"url": "f.csv"}, "bad": {"url": 42}})
        assert "good" in result
        assert "bad" not in result

    def test_table_with_empty_str_url_dropped(self) -> None:
        result = _parse_tables({"good": {"url": "f.csv"}, "bad": {"url": ""}})
        assert "good" in result
        assert "bad" not in result

    def test_non_dict_table_entry_filtered(self) -> None:
        result = _parse_tables({"good": {"url": "f.csv"}, "bad": "oops"})
        assert "good" in result
        assert "bad" not in result

    def test_non_str_table_id_filtered(self) -> None:
        result = _parse_tables({42: {"url": "f.csv"}, "good": {"url": "g.csv"}})
        assert "good" in result
        assert 42 not in result

    def test_table_properties_preserved(self) -> None:
        result = _parse_tables(
            {"t1": {"url": "facts.csv", "template": "tmpl", "optional": True, "parameters": {"p": "v"}}}
        )
        table = result["t1"]
        assert table.url == "facts.csv"
        assert table.template == "tmpl"
        assert table.optional is True
        assert table.parameters == {"p": "v"}


class TestParseLinkTargets:
    def test_non_dict_gives_empty(self) -> None:
        assert _parse_link_targets("not a dict") == {}
        assert _parse_link_targets(42) == {}
        assert _parse_link_targets(None) == {}
        assert _parse_link_targets([]) == {}

    def test_empty_dict_gives_empty(self) -> None:
        assert _parse_link_targets({}) == {}

    def test_basic(self) -> None:
        result = _parse_link_targets({"f1": ["f2", "f3"]})
        assert result["f1"] == ("f2", "f3")

    def test_non_str_source_fact_id_filtered(self) -> None:
        result = _parse_link_targets({42: ["f2"], "f1": ["f3"]})
        assert 42 not in result
        assert "f1" in result

    def test_non_str_target_entry_filtered(self) -> None:
        result = _parse_link_targets({"f1": ["f2", 99, "f3"]})
        assert result["f1"] == ("f2", "f3")

    def test_non_list_targets_gives_empty_tuple(self) -> None:
        result = _parse_link_targets({"f1": "f2"})
        assert result["f1"] == ()

    def test_dict_targets_gives_empty_tuple(self) -> None:
        result = _parse_link_targets({"f1": {"f2": True}})
        assert result["f1"] == ()

    def test_empty_target_list_gives_empty_tuple(self) -> None:
        result = _parse_link_targets({"f1": []})
        assert result["f1"] == ()

    def test_none_in_target_list_filtered(self) -> None:
        result = _parse_link_targets({"f1": ["f2", None, "f3"]})
        assert result["f1"] == ("f2", "f3")


class TestParseLinkGroup:
    def test_non_dict_gives_empty(self) -> None:
        assert _parse_link_group("not a dict") == {}
        assert _parse_link_group(42) == {}
        assert _parse_link_group(None) == {}

    def test_empty_dict_gives_empty(self) -> None:
        assert _parse_link_group({}) == {}

    def test_basic(self) -> None:
        result = _parse_link_group({"default": {"f1": ["f2"]}})
        assert "default" in result
        assert result["default"]["f1"] == ("f2",)

    def test_non_str_link_group_key_filtered(self) -> None:
        result = _parse_link_group({42: {"f1": ["f2"]}, "default": {"f3": ["f4"]}})
        assert 42 not in result
        assert "default" in result

    def test_non_dict_link_targets_gives_empty(self) -> None:
        result = _parse_link_group({"default": "not a dict"})
        assert result["default"] == {}


class TestParseLinks:
    def test_non_dict_gives_empty(self) -> None:
        assert _parse_links("not a dict") == {}
        assert _parse_links(42) == {}
        assert _parse_links(None) == {}

    def test_empty_dict_gives_empty(self) -> None:
        assert _parse_links({}) == {}

    def test_full_structure(self) -> None:
        result = _parse_links({"footnote": {"default": {"f1": ["f2", "f3"]}}})
        assert "footnote" in result
        assert "default" in result["footnote"]
        assert result["footnote"]["default"]["f1"] == ("f2", "f3")

    def test_multiple_link_types(self) -> None:
        result = _parse_links(
            {
                "footnote": {"default": {"f1": ["f2"]}},
                "explanatory": {"default": {"f3": ["f4"]}},
            }
        )
        assert "footnote" in result
        assert "explanatory" in result

    def test_non_str_link_type_filtered(self) -> None:
        result = _parse_links({42: {"default": {}}, "footnote": {}})
        assert 42 not in result
        assert "footnote" in result

    def test_non_dict_link_group_gives_empty(self) -> None:
        result = _parse_links({"footnote": "not a dict"})
        assert result["footnote"] == {}


class TestParseFeatures:
    def test_non_dict_gives_empty(self) -> None:
        assert _parse_features("not a dict") == {}
        assert _parse_features(42) == {}
        assert _parse_features(None) == {}

    def test_empty_dict_gives_empty(self) -> None:
        assert _parse_features({}) == {}

    def test_bool_value_kept(self) -> None:
        result = _parse_features({"xbrl:canonicalValues": True})
        assert result["xbrl:canonicalValues"] is True

    def test_str_value_kept(self) -> None:
        result = _parse_features({"xbrl:canonicalValues": "true"})
        assert result["xbrl:canonicalValues"] == "true"

    def test_any_value_type_kept(self) -> None:
        result = _parse_features({"xbrl:feature": {"nested": "dict"}, "xbrl:num": 42, "xbrl:none": None})
        assert result["xbrl:feature"] == {"nested": "dict"}
        assert result["xbrl:num"] == 42
        assert result["xbrl:none"] is None

    def test_non_str_key_filtered(self) -> None:
        result = _parse_features({42: True, "xbrl:good": True})
        assert 42 not in result
        assert "xbrl:good" in result

    def test_false_value_kept(self) -> None:
        result = _parse_features({"xbrl:canonicalValues": False})
        assert result["xbrl:canonicalValues"] is False

    def test_list_value_kept(self) -> None:
        result = _parse_features({"xbrl:listFeature": [1, 2, 3]})
        assert result["xbrl:listFeature"] == [1, 2, 3]


class TestParseFinal:
    def test_non_dict_gives_empty_frozenset(self) -> None:
        assert _parse_final("not a dict") == frozenset()
        assert _parse_final(42) == frozenset()
        assert _parse_final(None) == frozenset()

    def test_empty_dict_gives_empty_frozenset(self) -> None:
        assert _parse_final({}) == frozenset()

    def test_true_values_included(self) -> None:
        result = _parse_final({"namespaces": True, "taxonomy": True})
        assert result == frozenset({"namespaces", "taxonomy"})

    def test_false_values_excluded(self) -> None:
        result = _parse_final({"namespaces": True, "tableTemplates": False})
        assert result == frozenset({"namespaces"})

    def test_non_bool_true_values_excluded(self) -> None:
        result = _parse_final({"namespaces": True, "taxonomy": "true", "tables": 1})
        assert result == frozenset({"namespaces"})

    def test_non_str_keys_excluded(self) -> None:
        result = _parse_final({42: True, "namespaces": True})
        assert result == frozenset({"namespaces"})


class TestParseXbrlCsvEffectiveMetadata:
    def test_minimal(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim())
        assert result.document_info.document_type == DOCUMENT_TYPE
        assert result.document_info.taxonomy == ("schema.xsd",)
        assert result.document_info.namespaces == {}
        assert result.document_info.link_types == {}
        assert result.document_info.link_groups == {}
        assert result.document_info.features == {}
        assert result.document_info.final == frozenset()
        assert result.document_info.base_url is None
        assert result.table_templates == {}
        assert result.tables == {}
        assert result.parameters == {}
        assert result.parameter_url is None
        assert result.dimensions is None
        assert result.decimals is None
        assert result.links == {}

    def test_full(self) -> None:
        doc_info: dict[str, Any] = {
            "documentType": DOCUMENT_TYPE,
            "taxonomy": ["schema.xsd", "extra.xsd"],
            "namespaces": {"acme": "https://acme.example/"},
            "linkTypes": {"foo": "https://foo.example/"},
            "linkGroups": {"grp": "https://grp.example/"},
            "features": {"xbrl:canonicalValues": True},
            "baseURL": "https://example.com/reports/",
        }
        oim: dict[str, Any] = {
            "documentInfo": doc_info,
            "tableTemplates": {
                "t1": {
                    "columns": {"c1": {"decimals": 2}},
                    "rowIdColumn": "id",
                    "decimals": 4,
                    "dimensions": {"concept": "a:X"},
                }
            },
            "tables": {"f1": {"url": "facts.csv", "template": "t1"}},
            "parameters": {"p1": "v1"},
            "parameterURL": "params.csv",
            "dimensions": {"entity": "scheme:123"},
            "decimals": 3,
            "links": {"footnote": {"default": {"f1": ["f2"]}}},
        }
        result = parse_xbrl_csv_metadata(oim)

        assert result.document_info.taxonomy == ("schema.xsd", "extra.xsd")
        assert result.document_info.namespaces == {"acme": "https://acme.example/"}
        assert result.document_info.link_types == {"foo": "https://foo.example/"}
        assert result.document_info.link_groups == {"grp": "https://grp.example/"}
        assert result.document_info.features == {"xbrl:canonicalValues": True}
        assert result.document_info.base_url == "https://example.com/reports/"

        assert "t1" in result.table_templates
        assert result.table_templates["t1"].row_id_column == "id"

        assert "f1" in result.tables

        assert result.parameters == {"p1": "v1"}
        assert result.parameter_url == "params.csv"
        assert result.dimensions == XbrlCsvDimensions(entity="scheme:123")
        assert result.decimals == 3
        assert result.links["footnote"]["default"]["f1"] == ("f2",)

    def test_missing_document_info_raises(self) -> None:
        with pytest.raises(TypeError):
            parse_xbrl_csv_metadata({})

    def test_non_dict_document_info_raises(self) -> None:
        with pytest.raises(TypeError):
            parse_xbrl_csv_metadata({"documentInfo": "not a dict"})

    def test_missing_document_type_raises(self) -> None:
        with pytest.raises(TypeError):
            parse_xbrl_csv_metadata({"documentInfo": {}})

    def test_non_str_document_type_raises(self) -> None:
        with pytest.raises(TypeError):
            parse_xbrl_csv_metadata({"documentInfo": {"documentType": 42}})

    def test_non_xbrl_csv_document_type_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_xbrl_csv_metadata({"documentInfo": {"documentType": "https://example.com/not-a-csv-document-type"}})

    def test_empty_collections(self) -> None:
        oim: dict[str, Any] = {
            "documentInfo": {
                "documentType": DOCUMENT_TYPE,
                "taxonomy": [],
                "namespaces": {},
                "linkTypes": {},
                "linkGroups": {},
                "features": {},
            },
            "tableTemplates": {},
            "tables": {},
            "parameters": {},
            "links": {},
        }
        result = parse_xbrl_csv_metadata(oim)
        assert result.document_info.namespaces == {}
        assert result.document_info.link_types == {}
        assert result.document_info.link_groups == {}
        assert result.document_info.features == {}
        assert result.table_templates == {}
        assert result.tables == {}
        assert result.parameters == {}
        assert result.links == {}

    def test_taxonomy_as_tuple(self) -> None:
        oim = {"documentInfo": {"documentType": DOCUMENT_TYPE, "taxonomy": ["a.xsd", "b.xsd"]}}
        result = parse_xbrl_csv_metadata(oim)
        assert result.document_info.taxonomy == ("a.xsd", "b.xsd")

    def test_non_str_taxonomy_entry_filtered(self) -> None:
        oim = {"documentInfo": {"documentType": DOCUMENT_TYPE, "taxonomy": ["good.xsd", 42, "also.xsd"]}}
        result = parse_xbrl_csv_metadata(oim)
        assert result.document_info.taxonomy == ("good.xsd", "also.xsd")

    def test_non_list_taxonomy_gives_empty_tuple(self) -> None:
        oim = {"documentInfo": {"documentType": DOCUMENT_TYPE, "taxonomy": "schema.xsd"}}
        result = parse_xbrl_csv_metadata(oim)
        assert result.document_info.taxonomy == ()

    def test_decimals_int(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim({"decimals": 4}))
        assert result.decimals == 4
        assert isinstance(result.decimals, int)

    def test_decimals_str(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim({"decimals": "$decimalsParam"}))
        assert result.decimals == "$decimalsParam"
        assert isinstance(result.decimals, str)

    def test_bool_decimals_filtered(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim({"decimals": True}))
        assert result.decimals is None

    def test_non_str_parameter_url_filtered(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim({"parameterURL": 42}))
        assert result.parameter_url is None

    def test_non_str_namespace_value_filtered(self) -> None:
        oim: dict[str, Any] = {
            "documentInfo": {
                "documentType": DOCUMENT_TYPE,
                "taxonomy": [],
                "namespaces": {"good": "https://example.com/", "bad": 42},
            }
        }
        result = parse_xbrl_csv_metadata(oim)
        assert result.document_info.namespaces == {"good": "https://example.com/"}

    def test_non_dict_table_template_entry_filtered(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim({"tableTemplates": {"good": {"columns": {}}, "bad": "oops"}}))
        assert len(result.table_templates) == 1
        assert "good" in result.table_templates

    def test_non_dict_table_entry_filtered(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim({"tables": {"good": {"url": "f.csv"}, "bad": "oops"}}))
        assert len(result.tables) == 1
        assert "good" in result.tables

    def test_table_without_url_filtered(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim({"tables": {"good": {"url": "f.csv"}, "no_url": {}}}))
        assert len(result.tables) == 1
        assert "good" in result.tables

    def test_final_as_frozenset(self) -> None:
        oim: dict[str, Any] = {
            "documentInfo": {
                "documentType": DOCUMENT_TYPE,
                "taxonomy": ["schema.xsd"],
                "final": {"namespaces": True, "taxonomy": True},
            }
        }
        result = parse_xbrl_csv_metadata(oim)
        assert result.document_info.final == frozenset({"namespaces", "taxonomy"})

    def test_final_false_values_excluded(self) -> None:
        oim: dict[str, Any] = {
            "documentInfo": {
                "documentType": DOCUMENT_TYPE,
                "taxonomy": [],
                "final": {"namespaces": True, "tableTemplates": False},
            }
        }
        result = parse_xbrl_csv_metadata(oim)
        assert result.document_info.final == frozenset({"namespaces"})

    def test_final_empty_gives_empty_frozenset(self) -> None:
        oim: dict[str, Any] = {"documentInfo": {"documentType": DOCUMENT_TYPE, "taxonomy": [], "final": {}}}
        result = parse_xbrl_csv_metadata(oim)
        assert result.document_info.final == frozenset()

    def test_final_non_dict_gives_empty_frozenset(self) -> None:
        oim: dict[str, Any] = {"documentInfo": {"documentType": DOCUMENT_TYPE, "taxonomy": [], "final": "namespaces"}}
        result = parse_xbrl_csv_metadata(oim)
        assert result.document_info.final == frozenset()

    def test_non_dict_top_level_table_templates_gives_empty(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim({"tableTemplates": "not a dict"}))
        assert result.table_templates == {}

    def test_non_dict_top_level_tables_gives_empty(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim({"tables": "not a dict"}))
        assert result.tables == {}

    def test_non_dict_top_level_parameters_gives_empty(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim({"parameters": [1, 2]}))
        assert result.parameters == {}

    def test_non_dict_top_level_dimensions_gives_none(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim({"dimensions": "not a dict"}))
        assert result.dimensions is None

    def test_non_dict_top_level_links_gives_empty(self) -> None:
        result = parse_xbrl_csv_metadata(_minimal_oim({"links": [1, 2]}))
        assert result.links == {}

    def test_non_str_table_template_id_filtered(self) -> None:
        result = parse_xbrl_csv_metadata(
            _minimal_oim({"tableTemplates": {42: {"columns": {}}, "good": {"columns": {}}}})
        )
        assert len(result.table_templates) == 1
        assert "good" in result.table_templates

    def test_full_nested_properties_verified(self) -> None:
        oim: dict[str, Any] = {
            "documentInfo": {
                "documentType": DOCUMENT_TYPE,
                "taxonomy": ["schema.xsd"],
                "namespaces": {"acme": "https://acme.example/"},
                "final": {"namespaces": True},
            },
            "tableTemplates": {
                "t1": {
                    "columns": {
                        "c1": {
                            "decimals": 2,
                            "dimensions": {"concept": "a:Revenue"},
                            "propertyGroups": {"pg1": {"decimals": 5}},
                            "propertiesFrom": ["c2"],
                        }
                    },
                    "rowIdColumn": "id",
                    "decimals": 4,
                    "dimensions": {"unit": "iso4217:USD", "pfx:dim": "val"},
                }
            },
            "tables": {"f1": {"url": "facts.csv", "template": "t1", "optional": True, "parameters": {"p": "v"}}},
        }
        result = parse_xbrl_csv_metadata(oim)

        assert result.document_info.final == frozenset({"namespaces"})

        tmpl = result.table_templates["t1"]
        assert tmpl.decimals == 4
        assert tmpl.row_id_column == "id"
        assert tmpl.dimensions is not None
        assert tmpl.dimensions.unit == "iso4217:USD"
        assert tmpl.dimensions.taxonomy_defined == {"pfx:dim": "val"}

        col = tmpl.columns["c1"]
        assert col.decimals == 2
        assert col.dimensions is not None
        assert col.dimensions.concept == "a:Revenue"
        assert col.property_groups["pg1"].decimals == 5
        assert col.properties_from == ("c2",)

        table = result.tables["f1"]
        assert table.url == "facts.csv"
        assert table.template == "t1"
        assert table.optional is True
        assert table.parameters == {"p": "v"}
