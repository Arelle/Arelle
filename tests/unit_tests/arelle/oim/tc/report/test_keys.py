from __future__ import annotations

from decimal import Decimal

import pytest

from arelle.oim.tc.report.key_values import NULL_KEY_VALUE, KeyValue, KeyValues
from arelle.oim.tc.report.keys import MemoryKeyStore


def _typed(value: object) -> KeyValue:
    return KeyValue(1, value)


class TestMemoryKeyStore:
    def test_second_add_of_a_key_is_a_duplicate(self) -> None:
        store = MemoryKeyStore()
        assert store.add((_typed("a"),))
        assert not store.add((_typed("a"),))

    @pytest.mark.parametrize(
        "first, second",
        [
            ((_typed(Decimal("1.0")),), (_typed(Decimal("1")),)),
            ((_typed(Decimal("-0")),), (_typed(Decimal("0.00")),)),
            ((_typed(Decimal("1E+2")),), (_typed(Decimal("100")),)),
            (
                (_typed((20089, Decimal("0.0"), True)),),
                (_typed((20089, Decimal(0), True)),),
            ),
        ],
    )
    def test_equal_key_values_are_duplicates(
        self, first: KeyValues, second: KeyValues
    ) -> None:
        assert first == second
        store = MemoryKeyStore()
        assert store.add(first)
        assert not store.add(second)

    @pytest.mark.parametrize(
        "first, second",
        [
            ((NULL_KEY_VALUE,), (_typed(""),)),
            ((NULL_KEY_VALUE,), (_typed("None"),)),
            ((_typed(""),), (KeyValue(2, ""),)),
            ((_typed("a"), _typed("bc")), (_typed("ab"), _typed("c"))),
            (
                (_typed("x\x001:1:y"), _typed("z")),
                (_typed("x"), _typed("y\x001:1:z")),
            ),
            (
                (_typed((20089, Decimal(0), True)),),
                (_typed((20089, Decimal(0), False)),),
            ),
            ((_typed(Decimal("0.1")),), (_typed(Decimal("1")),)),
            (
                (_typed(Decimal("1234567890123456789012345678901")),),
                (_typed(Decimal("1234567890123456789012345678902")),),
            ),
        ],
    )
    def test_different_key_values_are_distinct(
        self, first: KeyValues, second: KeyValues
    ) -> None:
        assert first != second
        store = MemoryKeyStore()
        assert store.add(first)
        assert store.add(second)

    def test_contains_equal_key_values(self) -> None:
        store = MemoryKeyStore()
        store.add((_typed(Decimal("1.0")),))
        assert (_typed(Decimal("1")),) in store
        assert (_typed(Decimal("2")),) not in store

    def test_clear_forgets_every_key(self) -> None:
        store = MemoryKeyStore()
        store.add((_typed("a"),))
        store.clear()
        assert (_typed("a"),) not in store
