from unittest.mock import MagicMock

import pytest

from arelle.plugin.saveLoadableOIM import NamespacePrefixes, nsOim


class TestNamespacePrefixes:
    def test_init_empty(self):
        np = NamespacePrefixes()
        assert np.namespaces == {}

    def test_init_with_prefixes(self):
        np = NamespacePrefixes({"https://example.com/": "ex"})
        assert np.namespaces == {"ex": "https://example.com/"}

    def test_init_with_report_populates_ns_map(self):
        report = MagicMock()
        report.prefixedNamespaces = {"ex": "https://example.com/"}
        np = NamespacePrefixes(report=report)
        # Report ns map is used as fallback for addNamespace; verify it added "ex" for the namespace.
        prefix = np.addNamespace("https://example.com/")
        assert prefix == "ex"

    def test_contains_true(self):
        np = NamespacePrefixes({"https://example.com/": "ex"})
        assert "https://example.com/" in np

    def test_contains_false(self):
        np = NamespacePrefixes()
        assert "https://example.com/" not in np

    def test_get_prefix_known(self):
        np = NamespacePrefixes({"https://example.com/": "ex"})
        assert np.getPrefix("https://example.com/") == "ex"

    def test_get_prefix_unknown(self):
        np = NamespacePrefixes()
        assert np.getPrefix("https://example.com/") is None

    def test_namespaces_sorted_by_prefix(self):
        np = NamespacePrefixes({
            "https://b.example/": "bbb",
            "https://a.example/": "aaa",
            "https://c.example/": "ccc",
        })
        assert list(np.namespaces.keys()) == ["aaa", "bbb", "ccc"]

    def test_add_namespace_returns_existing_prefix(self):
        np = NamespacePrefixes({"https://example.com/": "ex"})
        prefix = np.addNamespace("https://example.com/", "other")
        assert prefix == "ex"

    def test_add_namespace_reserved_uri(self):
        np = NamespacePrefixes()
        prefix = np.addNamespace(nsOim)
        assert prefix == "xbrl"

    def test_add_namespace_uses_preferred_prefix_when_available(self):
        np = NamespacePrefixes()
        prefix = np.addNamespace("https://example.com/", "ex")
        assert prefix == "ex"
        assert "https://example.com/" in np

    def test_add_namespace_generates_numbered_suffix_when_preferred_taken(self):
        np = NamespacePrefixes({"https://other.com/": "ex"})
        prefix = np.addNamespace("https://example.com/", "ex")
        assert prefix == "ex0"

    def test_add_namespace_increments_suffix_past_existing(self):
        np = NamespacePrefixes({
            "https://other.com/": "ex",
            "https://another.com/": "ex0",
        })
        prefix = np.addNamespace("https://example.com/", "ex")
        assert prefix == "ex1"

    def test_add_namespace_falls_back_to_ns_prefix_without_preferred(self):
        np = NamespacePrefixes()
        prefix = np.addNamespace("https://example.com/")
        assert prefix == "ns0"

    def test_add_namespace_ns_suffix_increments(self):
        np = NamespacePrefixes()
        np.addNamespace("https://a.example/")
        prefix = np.addNamespace("https://b.example/")
        assert prefix == "ns1"

    def test_add_binding_raises_on_duplicate_namespace(self):
        np = NamespacePrefixes({"https://example.com/": "ex"})
        with pytest.raises(ValueError):
            np._bind("https://example.com/", "other")

    def test_add_binding_raises_on_duplicate_prefix(self):
        np = NamespacePrefixes({"https://example.com/": "ex"})
        with pytest.raises(ValueError):
            np._bind("https://other.com/", "ex")
