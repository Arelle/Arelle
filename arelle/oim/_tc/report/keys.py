"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from arelle.oim._tc.common import EXACT_CONTEXT
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
        self._keys: set[bytes] = set()

    def add(self, key_values: KeyValues) -> bool:
        encoded = encode_key_values(key_values)
        if encoded in self._keys:
            return False
        self._keys.add(encoded)
        return True


def encode_key_values(key_values: KeyValues) -> bytes:
    """Encodes key values as bytes that are equal exactly when the key values are."""
    parts: list[str] = []
    for key_value in key_values:
        parts.append(str(key_value.rank))
        _add_value_parts(key_value.value, parts)
    return b"".join(_netstring(part.encode()) for part in parts)


def _add_value_parts(value: object, parts: list[str]) -> None:
    if isinstance(value, tuple):
        for item in value:
            _add_value_parts(item, parts)
    elif isinstance(value, Decimal):
        parts.append(_decimal_text(value))
    else:
        parts.append(str(value))


def _netstring(data: bytes) -> bytes:
    """The data as a netstring, its byte length, a colon, the data and a comma."""
    return b"%d:%s," % (len(data), data)


def _decimal_text(value: Decimal) -> str:
    """The same text for equal decimals, so 1.0 and 1 both give "1"."""
    if value.is_zero():
        # normalize keeps the sign of -0, which equals 0.
        return "0"
    return str(value.normalize(EXACT_CONTEXT))
