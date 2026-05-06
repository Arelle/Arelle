from __future__ import annotations

import pytest

from arelle.ModelValue import QName, qnameFromNsmap

NSMAP = {
    None: "http://default.ns",
    "pfx": "http://pfx.ns",
    "other": "http://other.ns",
}


class TestQnameFromNsmap:
    def test_unprefixed_name(self):
        result = qnameFromNsmap(NSMAP, "localName")
        assert result == QName(None, "http://default.ns", "localName")

    def test_prefixed_name(self):
        result = qnameFromNsmap(NSMAP, "pfx:localName")
        assert result == QName("pfx", "http://pfx.ns", "localName")

    def test_xml_prefix(self):
        result = qnameFromNsmap(NSMAP, "xml:lang")
        assert result == QName("xml", "http://www.w3.org/XML/1998/namespace", "lang")

    def test_href_style(self):
        result = qnameFromNsmap(NSMAP, "http://some.ns#localName")
        assert result == QName(None, "http://some.ns", "localName")

    def test_href_no_namespace(self):
        result = qnameFromNsmap(NSMAP, "#localName")
        assert result == QName(None, "", "localName")

    def test_undefined_prefix_returns_none(self):
        result = qnameFromNsmap(NSMAP, "bad:localName")
        assert result is None

    def test_undefined_prefix_raises_custom_exception(self):
        with pytest.raises(ValueError):
            qnameFromNsmap(NSMAP, "bad:localName", prefixException=ValueError)

    def test_undefined_prefix_raises_custom_exception_instance(self):
        with pytest.raises(ValueError, match="my message"):
            qnameFromNsmap(NSMAP, "bad:localName", prefixException=ValueError("my message"))

    def test_no_default_namespace(self):
        nsmap = {"pfx": "http://pfx.ns"}
        result = qnameFromNsmap(nsmap, "localName")
        assert result == QName(None, None, "localName")

    def test_empty_nsmap(self):
        result = qnameFromNsmap({}, "localName")
        assert result == QName(None, None, "localName")

    def test_empty_nsmap_with_prefix_returns_none(self):
        result = qnameFromNsmap({}, "pfx:localName")
        assert result is None

    def test_empty_nsmap_with_prefix_raises(self):
        with pytest.raises(ValueError):
            qnameFromNsmap({}, "pfx:localName", prefixException=ValueError)
