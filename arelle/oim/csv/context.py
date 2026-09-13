"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arelle.oim._tc.metadata.model import TCMetadata
    from arelle.oim.csv.metadata.model import XbrlCsvEffectiveMetadata


@dataclass(frozen=True, slots=True)
class XbrlCsvLoadingContext:
    """Contains parsed and resolved CSV metadata models."""

    metadata: XbrlCsvEffectiveMetadata
    tc_metadata: TCMetadata | None = None
    report_parameters: Mapping[str, str | None] = field(default_factory=lambda: MappingProxyType({}))
    metadata_path: str | None = None
