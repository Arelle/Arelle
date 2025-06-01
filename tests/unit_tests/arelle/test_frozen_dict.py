from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping

import pytest

from arelle.PythonUtil import FrozenDict


class TestFrozenDict:

    def test_init_empty(self) -> None:
        fd = FrozenDict({})
        assert len(fd) == 0
        assert dict(fd) == {}

    def test_getitem(self) -> None:
        fd = FrozenDict({"key": "value", "num": 42, "bool": True})
        assert fd["key"] == "value"
        assert fd["num"] == 42
        assert fd["bool"] is True

    def test_getitem_keyerror(self) -> None:
        fd = FrozenDict({"a": 1})
        with pytest.raises(KeyError):
            fd["missing"]

    def test_iter(self) -> None:
        data = {"x": 10, "y": 20, "z": 30}
        fd = FrozenDict(data)
        keys = list(fd)
        assert keys == ["x", "y", "z"]

    def test_len(self) -> None:
        assert len(FrozenDict({})) == 0
        assert len(FrozenDict({"a": 1})) == 1
        assert len(FrozenDict({"a": 1, "b": 2, "c": 3})) == 3

    def test_repr(self) -> None:
        fd = FrozenDict({"a": 1, "b": 2})
        repr_str = repr(fd)
        assert repr_str == "FrozenDict({'a': 1, 'b': 2})"

    def test_repr_empty(self) -> None:
        fd = FrozenDict({})
        assert repr(fd) == "FrozenDict()"

    def test_eq_with_frozendict(self) -> None:
        fd1 = FrozenDict({"a": 1, "b": 2})
        fd2 = FrozenDict({"a": 1, "b": 2})
        fd3 = FrozenDict({"a": 1, "b": 3})
        fd4 = FrozenDict({"a": 1, "c": 2})

        assert fd1 == fd2
        assert fd1 != fd3
        assert fd1 != fd4

    def test_eq_with_regular_dict(self) -> None:
        fd = FrozenDict({"a": 1, "b": 2})
        regular_dict = {"a": 1, "b": 2}
        different_dict = {"a": 1, "b": 3}
        empty_dict = {}

        assert fd == regular_dict
        assert fd != different_dict
        assert fd != empty_dict

    def test_eq_with_ordered_dict(self) -> None:
        fd = FrozenDict({"a": 1, "b": 2})
        od1 = OrderedDict([("a", 1), ("b", 2)])
        od2 = OrderedDict([("b", 2), ("a", 1)])
        od3 = OrderedDict([("a", 1), ("b", 3)])

        assert fd == od1
        assert fd == od2
        assert fd != od3

    def test_eq_with_non_mapping(self) -> None:
        fd = FrozenDict({"a": 1})
        assert fd != "not a mapping"
        assert fd != 42
        assert fd != ["a", 1]
        assert fd is not None

    def test_hash_consistency(self) -> None:
        fd = FrozenDict({"a": 1, "b": 2})
        hash1 = hash(fd)
        hash2 = hash(fd)
        assert hash1 == hash2

    def test_hash_equal_objects(self) -> None:
        fd1 = FrozenDict({"a": 1, "b": 2})
        fd2 = FrozenDict({"a": 1, "b": 2})
        assert hash(fd1) == hash(fd2)

    def test_hash_different_objects(self) -> None:
        fd1 = FrozenDict({"a": 1, "b": 2})
        fd2 = FrozenDict({"a": 1, "b": 3})
        fd3 = FrozenDict({"a": 1, "c": 2})

        assert hash(fd1) != hash(fd2)
        assert hash(fd1) != hash(fd3)

    def test_hash_order_independence(self) -> None:
        fd1 = FrozenDict({"a": 1, "b": 2})
        fd2 = FrozenDict({"b": 2, "a": 1})
        assert hash(fd1) == hash(fd2)

    def test_immutability(self) -> None:
        original_data = {"a": 1, "b": 2}
        fd = FrozenDict(original_data)

        original_data["c"] = 3
        original_data["a"] = 99

        assert "c" not in fd
        assert fd["a"] == 1
        assert len(fd) == 2

        with pytest.raises(TypeError, match="object does not support item assignment"):
            fd["a"] = 99  # type: ignore[assignment]

    def test_mapping_interface(self) -> None:
        fd = FrozenDict({"a": 1, "b": 2})
        assert isinstance(fd, Mapping)

        assert "a" in fd
        assert "c" not in fd
        assert fd.get("a") == 1
        assert fd.get("c") is None
        assert fd.get("c", "default") == "default"

        keys = list(fd.keys())
        values = list(fd.values())
        items = list(fd.items())

        assert set(keys) == {"a", "b"}
        assert set(values) == {1, 2}
        assert set(items) == {("a", 1), ("b", 2)}

    def test_complex_values(self) -> None:
        complex_data = {"list": [1, 2, 3], "dict": {"nested": "value"}, "tuple": (4, 5, 6), "none": None, "bool": False}
        fd = FrozenDict(complex_data)

        assert fd["list"] == [1, 2, 3]
        assert fd["dict"] == {"nested": "value"}
        assert fd["tuple"] == (4, 5, 6)
        assert fd["none"] is None
        assert fd["bool"] is False

    def test_nested_frozendict(self) -> None:
        inner_fd = FrozenDict({"inner_key": "inner_value"})
        outer_fd = FrozenDict({"outer_key": inner_fd})

        assert outer_fd["outer_key"] == inner_fd
        assert outer_fd["outer_key"]["inner_key"] == "inner_value"

    def test_hashable_keys_only(self) -> None:
        fd = FrozenDict({"string": 1, 42: 2, (1, 2): 3, frozenset([4, 5]): 4})

        assert fd["string"] == 1
        assert fd[42] == 2
        assert fd[(1, 2)] == 3
        assert fd[frozenset([4, 5])] == 4

    def test_dict_methods_not_available(self) -> None:
        fd = FrozenDict({"a": 1})

        assert not hasattr(fd, "clear")
        assert not hasattr(fd, "pop")
        assert not hasattr(fd, "popitem")
        assert not hasattr(fd, "setdefault")
        assert not hasattr(fd, "update")
        assert not hasattr(fd, "__setitem__")
        assert not hasattr(fd, "__delitem__")
