"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class TCMetadata:
    template_constraints: Mapping[str, TCTemplateConstraints] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class TCTemplateConstraints:
    constraints: Mapping[str, TCValueConstraint] = field(default_factory=lambda: MappingProxyType({}))
    parameters: Mapping[str, TCValueConstraint] = field(default_factory=lambda: MappingProxyType({}))
    keys: TCKeys | None = None
    column_order: tuple[str, ...] | None = None
    table_constraints: TCTableConstraints | None = None


@dataclass(frozen=True, slots=True)
class TCValueConstraint:
    type: str
    optional: bool = False
    nillable: bool = False
    enumeration_values: Set[str] | None = None
    patterns: Set[str] | None = None
    time_zone: bool | None = None
    period_type: str | None = None
    duration_type: str | None = None
    length: int | None = None
    min_length: int | None = None
    max_length: int | None = None
    min_inclusive: str | None = None
    max_inclusive: str | None = None
    min_exclusive: str | None = None
    max_exclusive: str | None = None
    total_digits: int | None = None
    fraction_digits: int | None = None


@dataclass(frozen=True, slots=True)
class TCKeys:
    unique: tuple[TCUniqueKey, ...] | None = None
    reference: tuple[TCReferenceKey, ...] | None = None
    sort_key: str | None = None


@dataclass(frozen=True, slots=True)
class TCUniqueKey:
    name: str
    fields: tuple[str, ...]
    severity: str = "error"
    shared: bool = False


@dataclass(frozen=True, slots=True)
class TCReferenceKey:
    name: str
    fields: tuple[str, ...]
    referenced_key_name: str
    negate: bool = False
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class TCTableConstraints:
    min_tables: int | None = None
    max_tables: int | None = None
    min_table_rows: int | None = None
    max_table_rows: int | None = None
