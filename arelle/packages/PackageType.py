"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PackageType:
    name: str
    errorPrefix: str
