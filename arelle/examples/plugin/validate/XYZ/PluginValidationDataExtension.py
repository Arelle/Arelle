"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from arelle.utils.PluginData import PluginData


class PluginValidationDataExtension(PluginData):
    positiveFactConcepts: set[str] | None = None
