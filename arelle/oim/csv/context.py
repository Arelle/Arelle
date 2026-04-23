"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arelle.oim._tc.metadata.model import TCMetadata
    from arelle.oim.csv.metadata.model import XbrlCsvEffectiveMetadata


@dataclass(frozen=True, slots=True)
class XbrlCsvLoadingContext:
    """Contains parsed and resolved CSV metadata models."""

    metadata: XbrlCsvEffectiveMetadata
    tc_metadata: TCMetadata | None = None
