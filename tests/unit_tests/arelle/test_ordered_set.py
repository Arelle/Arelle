
import pytest

from arelle.PythonUtil import OrderedSet


class TestOrderedSet:

    def test_init_empty(self):
        os = OrderedSet()
        assert len(os) == 0
        assert list(os) == []
        assert bool(os) is False

    def test_init_with_iterable(self):
        os = OrderedSet([1, 2, 3, 2, 1])
        assert len(os) == 3
        assert list(os) == [1, 2, 3]

    def test_add_duplicate_order(self):
        os = OrderedSet()
        os.add(1)
        os.add(2)
        os.add(1)
        assert list(os) == [1, 2]
        assert len(os) == 2

    def test_contains(self):
        os = OrderedSet([1, 2, 3])
        assert 1 in os
        assert 2 in os
        assert 3 in os
        assert 4 not in os
        assert "1" not in os

    def test_update(self):
        os = OrderedSet([1, 2])
        os.update([3, 4, 2, 5])
        assert list(os) == [1, 2, 3, 4, 5]

    def test_update_with_string(self):
        os = OrderedSet(['a', 'b'])
        os.update("bcd")
        assert list(os) == ['a', 'b', 'c', 'd']

    def test_discard(self):
        os = OrderedSet([1, 2, 3, 4])
        os.discard(2)
        assert list(os) == [1, 3, 4]

        # Discarding non-existent element should not raise error
        non_existent_element = 10
        os.discard(non_existent_element)
        assert list(os) == [1, 3, 4]

    def test_discard_from_empty(self):
        os = OrderedSet()
        os.discard(1)
        assert len(os) == 0

    def test_pop_last(self):
        os = OrderedSet([1, 2, 3, 4])
        result = os.pop()
        assert result == 4
        assert list(os) == [1, 2, 3]

    def test_pop_first(self):
        os = OrderedSet([1, 2, 3, 4])
        result = os.pop(last=False)
        assert result == 1
        assert list(os) == [2, 3, 4]

    def test_pop_empty_set(self):
        os = OrderedSet()
        with pytest.raises(KeyError, match="set is empty"):
            os.pop()

    def test_iteration(self):
        os = OrderedSet([1, 2, 3])
        result = []
        for item in os:
            result.append(item)
        assert result == [1, 2, 3]

    def test_reversed_iteration(self):
        os = OrderedSet([1, 2, 3])
        result = list(reversed(os))
        assert result == [3, 2, 1]

    def test_len(self):
        os = OrderedSet()
        assert len(os) == 0

        os.add(1)
        assert len(os) == 1

        os.add(2)
        assert len(os) == 2

        os.add(1)  # Duplicate
        assert len(os) == 2

    def test_bool(self):
        os = OrderedSet()
        assert bool(os) is False

        os.add(1)
        assert bool(os) is True

    def test_repr_empty(self):
        os = OrderedSet()
        assert repr(os) == "OrderedSet()"

    def test_repr_with_elements(self):
        os = OrderedSet([1, 2, 3])
        assert repr(os) == "OrderedSet([1, 2, 3])"

    def test_eq_with_ordered_set(self):
        os1 = OrderedSet([1, 2, 3])
        os2 = OrderedSet([1, 2, 3])
        os3 = OrderedSet([3, 2, 1])
        os4 = OrderedSet([1, 2])

        assert os1 == os2
        assert os1 != os3
        assert os1 != os4

    def test_eq_with_regular_set(self):
        os = OrderedSet([1, 2, 3])
        s = {1, 2, 3}
        s_different = {1, 2}

        assert os == s
        assert os != s_different

    def test_eq_with_list(self):
        os = OrderedSet([1, 2, 3])
        lst = [1, 2, 3]

        assert os == lst

    def test_eq_with_non_iterable(self):
        os = OrderedSet([1, 2, 3])
        assert os != 42
        assert os != "hello"

    def test_order_preservation(self):
        os = OrderedSet()
        items = [5, 1, 3, 2, 4]
        for item in items:
            os.add(item)
        assert list(os) == items

    def test_order_preservation_with_duplicates(self):
        os = OrderedSet()
        os.add(1)
        os.add(2)
        os.add(3)
        os.add(2)
        assert list(os) == [1, 2, 3]

    def test_complex_operations(self):
        os = OrderedSet([1, 2, 3, 4, 5])

        os.discard(3)
        os.discard(5)
        assert list(os) == [1, 2, 4]

        os.add(6)
        os.add(0)
        assert list(os) == [1, 2, 4, 6, 0]

        os.update([7, 2, 8])
        assert list(os) == [1, 2, 4, 6, 0, 7, 8]

        last = os.pop()
        first = os.pop(last=False)
        assert last == 8
        assert first == 1
        assert list(os) == [2, 4, 6, 0, 7]

    def test_empty_set_operations(self):
        os = OrderedSet()

        assert list(os) == []
        assert list(reversed(os)) == []

        os.update([])
        assert len(os) == 0

    def test_single_element_operations(self):
        os = OrderedSet([42])

        assert len(os) == 1
        assert 42 in os
        assert list(os) == [42]
        assert list(reversed(os)) == [42]

        result = os.pop()
        assert result == 42
        assert len(os) == 0

    def test_unhashable_types_not_supported(self):
        os = OrderedSet()
        with pytest.raises(TypeError):
            os.add([1, 2, 3])

        with pytest.raises(TypeError):
            os.add({1: 2})

    def test_index_access_basic(self):
        os = OrderedSet([1, 2, 3, 4, 5])

        assert os[0] == 1
        assert os[1] == 2
        assert os[2] == 3
        assert os[3] == 4
        assert os[4] == 5

        assert os[-1] == 5
        assert os[-2] == 4
        assert os[-3] == 3
        assert os[-4] == 2
        assert os[-5] == 1

    def test_index_access_out_of_bounds(self):
        os = OrderedSet([1, 2, 3])

        with pytest.raises(IndexError):
            os[3]
        with pytest.raises(IndexError):
            os[10]

        with pytest.raises(IndexError):
            os[-4]
        with pytest.raises(IndexError):
            os[-10]

    def test_index_access_empty_set(self):
        os = OrderedSet()

        with pytest.raises(IndexError):
            os[0]
        with pytest.raises(IndexError):
            os[-1]

    def test_index_access_single_element(self):
        os = OrderedSet([42])

        assert os[0] == 42
        assert os[-1] == 42

        with pytest.raises(IndexError):
            os[1]
        with pytest.raises(IndexError):
            os[-2]

    def test_index_access_after_modifications(self):
        os = OrderedSet([1, 2, 3, 4])

        os.discard(2)
        assert os[0] == 1
        assert os[1] == 3
        assert os[2] == 4

        os.add(5)
        assert os[3] == 5

        os.pop()
        assert len(os) == 3
        with pytest.raises(IndexError):
            os[3]
