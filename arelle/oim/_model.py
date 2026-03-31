"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any


@dataclass(frozen=True)
class OimReport:
    oim_object: dict[str, Any]
    loading_errors: int = 0

    @cached_property
    def document_info(self) -> dict[str, Any]:
        document_info = self.oim_object.get("documentInfo", {})
        return document_info if isinstance(document_info, dict) else {}

    @cached_property
    def namespaces(self) -> dict[str, str]:
        namespaces = self.document_info.get("namespaces", {})
        return {
            prefix: namespace
            for prefix, namespace in namespaces.items()
            if isinstance(namespace, str) and isinstance(prefix, str)
        }
