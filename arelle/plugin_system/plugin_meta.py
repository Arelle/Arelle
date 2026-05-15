"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PluginMeta:
    aliases: frozenset[str]
    author: str
    description: str
    entry_point: dict[str, str]
    file_date: str
    hook_names: frozenset[str]
    import_urls: frozenset[str]
    imports: tuple[PluginMeta, ...]
    is_imported: bool
    license: str
    module_imports: frozenset[str]
    module_url: str
    name: str
    path: str
    status: str
    version: str
