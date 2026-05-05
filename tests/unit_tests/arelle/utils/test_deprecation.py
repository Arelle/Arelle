from __future__ import annotations

import warnings

import pytest

from arelle.utils.deprecation import ModuleDeprecations


class TestModuleDeprecations:
    def test_resolve_static(self) -> None:
        d = ModuleDeprecations("test")
        d.add("old_name", 42, "use new_name instead")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            assert d.resolve("old_name") == 42
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert str(w[0].message) == "test.old_name is deprecated. Will be removed in 3.0. use new_name instead."

    def test_custom_version(self) -> None:
        d = ModuleDeprecations("test")
        d.add("old_name", 42, "use new_name instead", removal_version="4.0")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            d.resolve("old_name")
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert str(w[0].message) == "test.old_name is deprecated. Will be removed in 4.0. use new_name instead."

    def test_multiple_attrs(self) -> None:
        d = ModuleDeprecations("test")
        d.add("attr_a", "value_a", "use A instead")
        d.add("attr_b", "value_b", "use B instead")
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            assert d.resolve("attr_a") == "value_a"
            assert d.resolve("attr_b") == "value_b"

    def test_none_value(self) -> None:
        d = ModuleDeprecations("test")
        d.add("old_name", None, "use new_name instead")
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            assert d.resolve("old_name") is None

    def test_unknown_attr_raises_attribute_error(self) -> None:
        d = ModuleDeprecations("test")
        with pytest.raises(AttributeError):
            d.resolve("nonexistent")

    def test_empty_raises_attribute_error(self) -> None:
        d = ModuleDeprecations("test")
        d.add("anything", 42, "use new_name instead")
        with pytest.raises(AttributeError):
            d.resolve("other_attr")

    def test_duplicate_add_raises(self) -> None:
        d = ModuleDeprecations("test")
        d.add("old_name", 42, "use new_name instead")
        with pytest.raises(ValueError, match="already registered"):
            d.add("old_name", 99, "use other_name instead")

    def test_duplicate_add_after_add_lazy_raises(self) -> None:
        d = ModuleDeprecations("test")
        d.add_lazy("old_name", lambda: 42, "use new_name instead")
        with pytest.raises(ValueError, match="already registered"):
            d.add("old_name", 99, "use other_name instead")

    def test_add_all(self) -> None:
        d = ModuleDeprecations("test")
        d.add_all({"attr_a": "value_a", "attr_b": "value_b"}, "use new module instead")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            assert d.resolve("attr_a") == "value_a"
            assert d.resolve("attr_b") == "value_b"
            assert len(w) == 2
            assert "attr_a" in str(w[0].message)
            assert "attr_b" in str(w[1].message)

    def test_add_all_duplicate_raises(self) -> None:
        d = ModuleDeprecations("test")
        d.add("old_name", 42, "use new_name instead")
        with pytest.raises(ValueError, match="already registered"):
            d.add_all({"old_name": 99}, "use other_name instead")


class TestModuleDeprecationsLazy:
    def test_resolve_calls_factory(self) -> None:
        d = ModuleDeprecations("test")
        d.add_lazy("old_name", lambda: 42, "use new_name instead")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            assert d.resolve("old_name") == 42
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert str(w[0].message) == "test.old_name is deprecated. Will be removed in 3.0. use new_name instead."

    def test_duplicate_add_lazy_raises(self) -> None:
        d = ModuleDeprecations("test")
        d.add_lazy("old_name", lambda: 42, "use new_name instead")
        with pytest.raises(ValueError, match="already registered"):
            d.add_lazy("old_name", lambda: 99, "use other_name instead")

    def test_duplicate_add_lazy_after_add_raises(self) -> None:
        d = ModuleDeprecations("test")
        d.add("old_name", 42, "use new_name instead")
        with pytest.raises(ValueError, match="already registered"):
            d.add_lazy("old_name", lambda: 99, "use other_name instead")

    def test_add_lazy_all(self) -> None:
        d = ModuleDeprecations("test")
        d.add_lazy_all(
            {"attr_a": lambda: "lazy_a", "attr_b": lambda: "lazy_b"},
            "use new module instead",
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            assert d.resolve("attr_a") == "lazy_a"
            assert d.resolve("attr_b") == "lazy_b"
            assert len(w) == 2
            assert "attr_a" in str(w[0].message)
            assert "attr_b" in str(w[1].message)

    def test_add_lazy_all_duplicate_raises(self) -> None:
        d = ModuleDeprecations("test")
        d.add_lazy("old_name", lambda: 42, "use new_name instead")
        with pytest.raises(ValueError, match="already registered"):
            d.add_lazy_all({"old_name": lambda: 99}, "use other_name instead")

    def test_mixed_static_and_lazy(self) -> None:
        d = ModuleDeprecations("test")
        d.add("static_attr", "static_value", "use A instead")
        d.add_lazy("lazy_attr", lambda: "lazy_value", "use B instead")
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            assert d.resolve("static_attr") == "static_value"
            assert d.resolve("lazy_attr") == "lazy_value"
