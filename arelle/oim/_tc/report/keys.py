"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from arelle.oim._tc.report.key_values import KeyValues


class KeyStore(ABC):
    """The distinct key values of one unique key.

    Validation only uses this interface, so a store that manages keys on disk or in
    a database could be added if very large reports need one.
    """

    @abstractmethod
    def add(self, key_values: KeyValues) -> bool:
        """Adds key values and returns False if they were already present."""


class MemoryKeyStore(KeyStore):
    """Keeps every distinct key value in memory."""

    def __init__(self) -> None:
        self._keys: set[KeyValues] = set()

    def add(self, key_values: KeyValues) -> bool:
        if key_values in self._keys:
            return False
        self._keys.add(key_values)
        return True
