"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

LinkTargets = Mapping[str, tuple[str, ...]]
LinkGroups = Mapping[str, LinkTargets]
Links = Mapping[str, LinkGroups]


@dataclass(frozen=True, slots=True)
class XbrlCsvEffectiveMetadata:
    document_info: XbrlCsvDocumentInfo
    table_templates: Mapping[str, XbrlCsvTableTemplate] = field(default_factory=lambda: MappingProxyType({}))
    tables: Mapping[str, XbrlCsvTable] = field(default_factory=lambda: MappingProxyType({}))
    parameters: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    parameter_url: str | None = None
    dimensions: XbrlCsvDimensions | None = None
    decimals: int | str | None = None
    links: Links = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class XbrlCsvDocumentInfo:
    """Document level information from the resolved effective metadata.

    `extends` is absent from the resolved model: it's consumed during the
    JSON metadata file extension merging phase and has no logical meaning
    in the resolved effective model.
    """

    document_type: str
    namespaces: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    link_types: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    link_groups: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    taxonomy: tuple[str, ...] = ()
    features: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    final: Set[str] = frozenset()
    base_url: str | None = None


@dataclass(frozen=True, slots=True)
class XbrlCsvTableTemplate:
    row_id_column: str | None = None
    columns: Mapping[str, XbrlCsvColumn] = field(default_factory=lambda: MappingProxyType({}))
    decimals: int | str | None = None
    dimensions: XbrlCsvDimensions | None = None


@dataclass(frozen=True, slots=True)
class XbrlCsvColumn:
    comment: bool = False
    decimals: int | str | None = None
    dimensions: XbrlCsvDimensions | None = None
    property_groups: Mapping[str, XbrlCsvPropertyGroup] = field(default_factory=lambda: MappingProxyType({}))
    properties_from: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class XbrlCsvDimensions:
    concept: str | None = None
    entity: str | None = None
    period: str | None = None
    unit: str | None = None
    language: str | None = None
    taxonomy_defined: Mapping[str, str | None] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class XbrlCsvPropertyGroup:
    decimals: int | str | None = None
    dimensions: XbrlCsvDimensions | None = None


@dataclass(frozen=True, slots=True)
class XbrlCsvTable:
    url: str
    template: str | None = None
    optional: bool = False
    parameters: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
