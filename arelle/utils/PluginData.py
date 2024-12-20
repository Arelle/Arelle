"""
See COPYRIGHT.md for copyright information.
"""
from dataclasses import dataclass


@dataclass
class PluginData:
    """
    Base dataclass which should be extended with fields by plugins that need to cache data while processing a report.
    """
    name: str
