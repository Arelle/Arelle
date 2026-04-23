"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from arelle.oim.csv.metadata.common import CSV_DOCUMENT_TYPES
from arelle.oim.csv.metadata.model import (
    LinkGroups,
    Links,
    LinkTargets,
    XbrlCsvColumn,
    XbrlCsvDimensions,
    XbrlCsvDocumentInfo,
    XbrlCsvEffectiveMetadata,
    XbrlCsvPropertyGroup,
    XbrlCsvTable,
    XbrlCsvTableTemplate,
)
from arelle.typing import TypeGetText

_: TypeGetText

_BUILT_IN_DIMENSION_KEYS = frozenset({"concept", "entity", "period", "unit", "language"})


def parse_xbrl_csv_metadata(oim_object: dict[str, Any]) -> XbrlCsvEffectiveMetadata:
    """Build a resolved `XbrlCsvEffectiveMetadata` from a fully merged OIM object dict.

    Structural validation has already been performed upstream during JSON merging. This function parses the merged dict.
    Raises `TypeError` if `documentInfo` is missing or not a dict, or `documentType` is missing or not a string.
    Raises `ValueError` if `documentType` is not a recognised CSV document type URI.
    All other type mismatched values and unknown keys are dropped, yielding a well typed partial model.
    """
    return XbrlCsvEffectiveMetadata(
        document_info=_parse_document_info(oim_object),
        table_templates=_parse_table_templates(oim_object.get("tableTemplates")),
        tables=_parse_tables(oim_object.get("tables")),
        parameters=_as_str_map(oim_object.get("parameters")),
        parameter_url=_as_str_or_none(oim_object.get("parameterURL")),
        dimensions=_parse_dimensions(oim_object.get("dimensions")),
        decimals=_as_decimals_or_none(oim_object.get("decimals")),
        links=_parse_links(oim_object.get("links")),
    )


def _parse_document_info(oim_object: dict[str, Any]) -> XbrlCsvDocumentInfo:
    oim_document_info = oim_object.get("documentInfo")
    if not isinstance(oim_document_info, dict):
        raise TypeError(
            _("documentInfo must be a dictionary, instead found {0}").format(type(oim_document_info).__name__)
        )
    document_type = oim_document_info.get("documentType")
    if not isinstance(document_type, str):
        raise TypeError(_("documentType must be a string, instead found {0}").format(type(document_type).__name__))
    if document_type not in CSV_DOCUMENT_TYPES:
        raise ValueError(
            _("documentType must be a valid CSV document type URI, instead found {0}").format(document_type)
        )

    return XbrlCsvDocumentInfo(
        document_type=document_type,
        taxonomy=_as_str_tuple(oim_document_info.get("taxonomy")),
        namespaces=_as_str_map(oim_document_info.get("namespaces")),
        link_types=_as_str_map(oim_document_info.get("linkTypes")),
        link_groups=_as_str_map(oim_document_info.get("linkGroups")),
        features=_parse_features(oim_document_info.get("features")),
        final=_parse_final(oim_document_info.get("final")),
        base_url=_as_str_or_none(oim_document_info.get("baseURL")),
    )


def _parse_features(raw_features: Any) -> Mapping[str, Any]:
    if not isinstance(raw_features, dict):
        return MappingProxyType({})
    return MappingProxyType(
        {
            feature_name: feature_val
            for feature_name, feature_val in raw_features.items()
            if isinstance(feature_name, str)
        }
    )


def _parse_final(raw_final: Any) -> frozenset[str]:
    if not isinstance(raw_final, dict):
        return frozenset()
    return frozenset(
        property_name
        for property_name, property_val in raw_final.items()
        if isinstance(property_name, str)
        if property_val is True
    )


def _parse_table_templates(raw_table_templates: Any) -> Mapping[str, XbrlCsvTableTemplate]:
    if not isinstance(raw_table_templates, dict):
        return MappingProxyType({})
    return MappingProxyType(
        {
            table_id: _parse_table_template(raw_table_template)
            for table_id, raw_table_template in raw_table_templates.items()
            if isinstance(table_id, str)
            if isinstance(raw_table_template, dict)
        }
    )


def _parse_table_template(raw_table_template: dict[str, Any]) -> XbrlCsvTableTemplate:
    return XbrlCsvTableTemplate(
        columns=_parse_columns(raw_table_template.get("columns")),
        row_id_column=_as_str_or_none(raw_table_template.get("rowIdColumn")),
        decimals=_as_decimals_or_none(raw_table_template.get("decimals")),
        dimensions=_parse_dimensions(raw_table_template.get("dimensions")),
    )


def _parse_columns(raw_cols: Any) -> Mapping[str, XbrlCsvColumn]:
    if not isinstance(raw_cols, dict):
        return MappingProxyType({})
    return MappingProxyType(
        {
            col_id: _parse_column(col)
            for col_id, col in raw_cols.items()
            if isinstance(col_id, str)
            if isinstance(col, dict)
        }
    )


def _parse_column(col_dict: dict[str, Any]) -> XbrlCsvColumn:
    raw_property_groups = col_dict.get("propertyGroups")
    if not isinstance(raw_property_groups, dict):
        raw_property_groups = {}
    property_groups = MappingProxyType(
        {
            property_group_name: _parse_property_group(property_group)
            for property_group_name, property_group in raw_property_groups.items()
            if isinstance(property_group_name, str)
            if isinstance(property_group, dict)
        }
    )
    raw_properties_from = col_dict.get("propertiesFrom")
    if not isinstance(raw_properties_from, list):
        raw_properties_from = []
    properties_from = tuple(prop for prop in raw_properties_from if isinstance(prop, str))

    return XbrlCsvColumn(
        comment=_as_bool(col_dict.get("comment")),
        decimals=_as_decimals_or_none(col_dict.get("decimals")),
        dimensions=_parse_dimensions(col_dict.get("dimensions")),
        property_groups=property_groups,
        properties_from=properties_from,
    )


def _parse_property_group(pg_dict: dict[str, Any]) -> XbrlCsvPropertyGroup:
    return XbrlCsvPropertyGroup(
        decimals=_as_decimals_or_none(pg_dict.get("decimals")),
        dimensions=_parse_dimensions(pg_dict.get("dimensions")),
    )


def _parse_dimensions(dims: Any) -> XbrlCsvDimensions | None:
    if not isinstance(dims, dict) or not dims:
        return None
    return XbrlCsvDimensions(
        concept=_as_str_or_none(dims.get("concept")),
        entity=_as_str_or_none(dims.get("entity")),
        period=_as_str_or_none(dims.get("period")),
        unit=_as_str_or_none(dims.get("unit")),
        language=_as_str_or_none(dims.get("language")),
        taxonomy_defined=_parse_taxonomy_defined_dimensions(dims),
    )


def _parse_taxonomy_defined_dimensions(dims: dict[str, Any]) -> Mapping[str, str | None]:
    return MappingProxyType(
        {
            key: val
            for key, val in dims.items()
            if isinstance(key, str)
            if key not in _BUILT_IN_DIMENSION_KEYS
            if isinstance(val, str) or val is None
        }
    )


def _parse_tables(raw_tables: Any) -> Mapping[str, XbrlCsvTable]:
    if not isinstance(raw_tables, dict):
        return MappingProxyType({})
    return MappingProxyType(
        {
            raw_table_id: _parse_table(table_url, raw_table)
            for raw_table_id, raw_table in raw_tables.items()
            if isinstance(raw_table_id, str)
            if isinstance(raw_table, dict)
            if (table_url := _as_str_or_none(raw_table.get("url")))
        }
    )


def _parse_table(table_url: str, raw_table: dict[str, Any]) -> XbrlCsvTable:
    return XbrlCsvTable(
        url=table_url,
        template=_as_str_or_none(raw_table.get("template")),
        optional=_as_bool(raw_table.get("optional")),
        parameters=_as_str_map(raw_table.get("parameters")),
    )


def _parse_links(raw_links: Any) -> Links:
    if not isinstance(raw_links, dict):
        return MappingProxyType({})
    return MappingProxyType(
        {
            link_type: _parse_link_group(raw_link_group)
            for link_type, raw_link_group in raw_links.items()
            if isinstance(link_type, str)
        }
    )


def _parse_link_group(raw_link_group: Any) -> LinkGroups:
    if not isinstance(raw_link_group, dict):
        return MappingProxyType({})
    return MappingProxyType(
        {
            link_group: _parse_link_targets(link_targets)
            for link_group, link_targets in raw_link_group.items()
            if isinstance(link_group, str)
        }
    )


def _parse_link_targets(raw_link_targets: Any) -> LinkTargets:
    if not isinstance(raw_link_targets, dict):
        return MappingProxyType({})
    return MappingProxyType(
        {
            source_fact_id: _as_str_tuple(target_fact_ids)
            for source_fact_id, target_fact_ids in raw_link_targets.items()
            if isinstance(source_fact_id, str)
        }
    )


def _as_str_tuple(item: Any) -> tuple[str, ...]:
    if not isinstance(item, list):
        return ()
    return tuple(val for val in item if isinstance(val, str))


def _as_str_map(item: Any) -> Mapping[str, str]:
    if not isinstance(item, dict):
        return MappingProxyType({})
    return MappingProxyType({key: val for key, val in item.items() if isinstance(key, str) and isinstance(val, str)})


def _as_str_or_none(item: Any) -> str | None:
    return item if isinstance(item, str) else None


def _as_bool(item: Any) -> bool:
    return item if isinstance(item, bool) else False


def _as_decimals_or_none(item: Any) -> int | str | None:
    if isinstance(item, bool):
        return None
    if isinstance(item, (int, str)):
        return item
    return None
