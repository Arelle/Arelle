"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass

from arelle.utils.PluginData import PluginData


@dataclass
class PluginValidationDataExtension(PluginData):

    # Identity hash for caching.
    def __hash__(self) -> int:
        return id(self)
