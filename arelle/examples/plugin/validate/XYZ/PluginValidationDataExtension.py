"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from arelle.utils.validate.PluginValidationData import PluginValidationData


class PluginValidationDataExtension(PluginValidationData):
    positiveFactConcepts: set[str] | None = None
