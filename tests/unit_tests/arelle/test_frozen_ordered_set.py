from collections.abc import Iterable

import pytest

from arelle.PythonUtil import FrozenOrderedSet, OrderedSet


class TestFrozenOrderedSet:
    def test_empty_initialization(self):
        fos = FrozenOrderedSet()
        assert len(fos) == 0
        assert not fos
        assert list(fos) == []

    def test_initialization_with_list(self):
        fos = FrozenOrderedSet([1, 2, 3])
        assert list(fos) == [1, 2, 3]
        assert len(fos) == 3

    def test_initialization_with_tuple(self):
        fos = FrozenOrderedSet((4, 5, 6))
        assert list(fos) == [4, 5, 6]

    def test_initialization_with_string(self):
        fos = FrozenOrderedSet("abc")
        assert list(fos) == ["a", "b", "c"]

    def test_initialization_with_set(self):
        fos = FrozenOrderedSet({7, 8, 9})
        assert len(fos) == 3
        assert 7 in fos
        assert 8 in fos
        assert 9 in fos

    def test_initialization_with_ordered_set(self):
        fos = FrozenOrderedSet(OrderedSet([7, 8, 9]))
        assert len(fos) == 3
        assert 7 in fos
        assert 8 in fos
        assert 9 in fos

    def test_initialization_with_duplicates(self):
        fos = FrozenOrderedSet([1, 2, 2, 3, 1, 4])
        assert list(fos) == [1, 2, 3, 4]
        assert len(fos) == 4

    def test_contains(self):
        fos = FrozenOrderedSet([1, 2, 3, "a", "b"])

        assert 1 in fos
        assert 2 in fos
        assert 3 in fos

        assert 4 not in fos
        assert None not in fos

    def test_len(self):
        assert len(FrozenOrderedSet()) == 0
        assert len(FrozenOrderedSet([1])) == 1
        assert len(FrozenOrderedSet([1, 2, 3])) == 3
        assert len(FrozenOrderedSet([1, 1, 2, 2, 3])) == 3

    def test_iteration(self):
        fos = FrozenOrderedSet(["first", "second", "third"])
        result = []
        for item in fos:
            result.append(item)
        assert result == ["first", "second", "third"]

    def test_reversed_iteration(self):
        fos = FrozenOrderedSet(["first", "second", "third"])
        result = list(reversed(fos))
        assert result == ["third", "second", "first"]

    def test_repr(self):
        # Empty set
        fos_empty = FrozenOrderedSet()
        assert repr(fos_empty) == "FrozenOrderedSet()"

        # Non-empty set
        fos = FrozenOrderedSet([1, 2, 3])
        assert repr(fos) == "FrozenOrderedSet((1, 2, 3))"

        # With strings
        fos_str = FrozenOrderedSet(["a", "b"])
        assert repr(fos_str) == "FrozenOrderedSet(('a', 'b'))"

    def test_equality_with_frozen_ordered_set(self):
        fos1 = FrozenOrderedSet([1, 2, 3])
        fos2 = FrozenOrderedSet([1, 2, 3])
        fos3 = FrozenOrderedSet([3, 2, 1])
        fos4 = FrozenOrderedSet([1, 2, 3, 4])

        assert fos1 == fos2
        assert fos1 != fos3
        assert fos1 != fos4
        assert FrozenOrderedSet() == FrozenOrderedSet()

    def test_equality_with_ordered_set(self):
        fos = FrozenOrderedSet([1, 2, 3])
        os1 = OrderedSet([1, 2, 3])
        os2 = OrderedSet([3, 2, 1])

        assert fos == os1
        assert fos != os2

    def test_equality_with_other_iterables(self):
        fos = FrozenOrderedSet([1, 2, 3])

        assert fos == {1, 2, 3}
        assert fos == {3, 2, 1}
        assert fos == [1, 2, 3]
        assert fos == [3, 2, 1]
        assert fos == (1, 2, 3)
        assert fos == (3, 2, 1)
        assert fos != [1, 2, 4]
        assert fos != {1, 2, 4}

    def test_equality_with_non_iterables(self):
        fos = FrozenOrderedSet([1, 2, 3])

        assert fos != 42
        assert fos != "123"
        assert fos != None

    def test_hashable(self):
        fos1 = FrozenOrderedSet([1, 2, 3])
        fos2 = FrozenOrderedSet([1, 2, 3])
        fos3 = FrozenOrderedSet([3, 2, 1])

        assert hash(fos1) == hash(fos2)
        assert hash(fos1) != hash(fos3)

        d = {fos1: "value1", fos3: "value3"}
        assert d[fos1] == "value1"
        assert d[fos2] == "value1"
        assert d[fos3] == "value3"

        s = {fos1, fos2, fos3}
        assert len(s) == 2

    def test_hash_consistency(self):
        fos = FrozenOrderedSet([1, 2, 3])
        hash1 = hash(fos)
        hash2 = hash(fos)
        hash3 = hash(fos)

        assert hash1 == hash2
        assert hash2 == hash3

    def test_immutability(self):
        fos = FrozenOrderedSet([1, 2, 3])

        assert not hasattr(fos, "add")
        assert not hasattr(fos, "remove")
        assert not hasattr(fos, "discard")
        assert not hasattr(fos, "pop")
        assert not hasattr(fos, "clear")
        assert not hasattr(fos, "update")

    def test_set_operations_type_compatibility(self):
        fos = FrozenOrderedSet([1, 2, 3])

        assert isinstance(fos, Iterable)

    def test_with_unhashable_types(self):
        with pytest.raises(TypeError):
            FrozenOrderedSet([[1, 2], [3, 4]])

        with pytest.raises(TypeError):
            FrozenOrderedSet([{1: 2}, {3: 4}])

    def test_order_preservation_complex(self):
        fos = FrozenOrderedSet([3, 1, 4, 1, 5, 9, 2, 6, 5])
        expected_order = [3, 1, 4, 5, 9, 2, 6]
        assert list(fos) == expected_order

    def test_boolean_evaluation(self):
        assert not FrozenOrderedSet()
        assert FrozenOrderedSet([1])
        assert FrozenOrderedSet([0])
        assert FrozenOrderedSet([None])

    def test_large_dataset(self):
        large_list = list(range(1000))
        fos = FrozenOrderedSet(large_list)

        assert len(fos) == 1000
        assert list(fos) == large_list
        assert 500 in fos
        assert 1000 not in fos

    def test_nested_iteration(self):
        fos = FrozenOrderedSet(["a", "b", "c"])

        iter1 = iter(fos)
        iter2 = iter(fos)

        assert next(iter1) == "a"
        assert next(iter2) == "a"
        assert next(iter1) == "b"
        assert next(iter2) == "b"

    def test_edge_cases_empty_string_and_zero(self):
        fos = FrozenOrderedSet(["", 0, False, None])

        assert len(fos) == 3
        assert "" in fos
        assert 0 in fos
        assert False in fos
        assert None in fos

        assert list(fos) == ["", 0, None]

    def test_generator_as_input(self):

        def gen():
            yield 1
            yield 2
            yield 3
            yield 2

        fos = FrozenOrderedSet(gen())
        assert list(fos) == [1, 2, 3]
        assert len(fos) == 3

    def test_comparison_with_different_types(self):
        fos = FrozenOrderedSet([1, 2, 3])

        assert fos != "not_iterable_comparison"
        assert fos == frozenset([3, 2, 1])

    def test_index_access(self):
        fos = FrozenOrderedSet([10, 20, 30, 40, 50])

        assert fos[0] == 10
        assert fos[1] == 20
        assert fos[2] == 30
        assert fos[3] == 40
        assert fos[4] == 50

        assert fos[-1] == 50
        assert fos[-2] == 40
        assert fos[-3] == 30
        assert fos[-4] == 20
        assert fos[-5] == 10

    def test_index_access_empty_set(self):
        fos = FrozenOrderedSet()

        with pytest.raises(IndexError):
            fos[0]

        with pytest.raises(IndexError):
            fos[-1]

    def test_index_access_out_of_bounds(self):
        fos = FrozenOrderedSet([1, 2, 3])

        with pytest.raises(IndexError):
            fos[3]

        with pytest.raises(IndexError):
            fos[10]

        with pytest.raises(IndexError):
            fos[-4]

        with pytest.raises(IndexError):
            fos[-10]

    def test_index_access_single_element(self):
        fos = FrozenOrderedSet([42])

        assert fos[0] == 42
        assert fos[-1] == 42

        with pytest.raises(IndexError):
            fos[1]

        with pytest.raises(IndexError):
            fos[-2]

    def test_index_access_with_strings(self):
        fos = FrozenOrderedSet(["apple", "banana", "cherry"])

        assert fos[0] == "apple"
        assert fos[1] == "banana"
        assert fos[2] == "cherry"
        assert fos[-1] == "cherry"
        assert fos[-2] == "banana"
        assert fos[-3] == "apple"

    def test_index_access_with_duplicates_removed(self):
        fos = FrozenOrderedSet([5, 3, 5, 1, 3, 7])

        assert fos[0] == 5
        assert fos[1] == 3
        assert fos[2] == 1
        assert fos[3] == 7

        with pytest.raises(IndexError):
            fos[4]

    def test_index_access_invalid_type(self):
        fos = FrozenOrderedSet([1, 2, 3])

        with pytest.raises(TypeError):
            fos["invalid"]  # type: ignore[assignment]

        with pytest.raises(TypeError):
            fos[1.5]  # type: ignore[assignment]

        with pytest.raises(TypeError):
            fos[None]  # type: ignore[assignment]
