from unittest.mock import Mock

import pytest

from arelle import XbrlConst
from arelle.ModelObject import ModelObject
from arelle.XhtmlInlineUtil import (
    ixMsgCode,
    resolveHtmlUri,
)


def _make_ix_elt(localName, namespaceURI, ixNS=None):
    """Helper to build a mock inline XBRL element for ixMsgCode tests."""
    modelDoc = Mock()
    if ixNS is not None:
        modelDoc.ixNS = ixNS
    else:
        del modelDoc.ixNS  # so getattr falls back to default
    return Mock(
        spec=ModelObject,
        localName=localName,
        namespaceURI=namespaceURI,
        modelDocument=modelDoc,
    )


class TestIxMsgCode:
    def test_defaults_elt_none(self):
        # ns defaults to ixbrl11, name defaults to "other"
        assert ixMsgCode("someName") == "ix11:someName"

    def test_elt_none_explicit_ns_and_name(self):
        result = ixMsgCode("refsAttr", ns=XbrlConst.ixbrl, name="references", sect="validation")
        assert result == "ix10.11.1.2:refsAttr"

    def test_elt_none_explicit_ns_only(self):
        # name defaults to "other"
        result = ixMsgCode("code", ns=XbrlConst.ixbrl)
        assert result == "ix10:code"

    def test_elt_none_explicit_name_only(self):
        # ns defaults to ixbrl11
        result = ixMsgCode("code", name="footnote")
        assert result == "ix11.6.1.1:code"

    @pytest.mark.parametrize("localName,sect,expected_prefix", [
        ("footnote", "constraint", "ix10.5.1.1"),
        ("footnote", "validation", "ix10.5.1.2"),
        ("fraction", "constraint", "ix10.6.1.1"),
        ("nonFraction", "validation", "ix10.9.1.2"),
        ("nonNumeric", "constraint", "ix10.10.1.1"),
        ("references", "validation", "ix10.11.1.2"),
        ("tuple", "constraint", "ix10.13.1.1"),
    ])
    def test_ix10_element_sects(self, localName, sect, expected_prefix):
        elt = _make_ix_elt(localName, XbrlConst.ixbrl)
        assert ixMsgCode("code", elt, sect=sect) == f"{expected_prefix}:code"

    @pytest.mark.parametrize("localName,sect,expected_prefix", [
        ("continuation", "constraint", "ix11.4.1.1"),
        ("exclude", "validation", "ix11.5.1.2"),
        ("footnote", "validation", "ix11.6.1.2"),
        ("fraction", "constraint", "ix11.7.1.2"),
        ("denominator", "constraint", "ix11.7.1.1"),
        ("numerator", "validation", "ix11.7.1.3"),
        ("nonFraction", "constraint", "ix11.10.1.1"),
        ("nonNumeric", "validation", "ix11.11.1.2"),
        ("relationship", "constraint", "ix11.13.1.1"),
        ("resources", "validation", "ix11.14.1.2"),
        ("tuple", "validation", "ix11.15.1.2"),
    ])
    def test_ix11_element_sects(self, localName, sect, expected_prefix):
        elt = _make_ix_elt(localName, XbrlConst.ixbrl11)
        assert ixMsgCode("code", elt, sect=sect) == f"{expected_prefix}:code"

    def test_non_validatable_ix10(self):
        elt = _make_ix_elt("header", XbrlConst.ixbrl)
        assert ixMsgCode("headerDisplayNone", elt, sect="non-validatable") == "ix10.7.1.2:headerDisplayNone"

    def test_non_validatable_ix11(self):
        elt = _make_ix_elt("header", XbrlConst.ixbrl11)
        assert ixMsgCode("headerDisplayNone", elt, sect="non-validatable") == "ix11.8.1.2:headerDisplayNone"

    def test_context_remapped_to_resources(self):
        elt = _make_ix_elt("context", XbrlConst.ixbrl11)
        assert ixMsgCode("code", elt, sect="validation") == "ix11.14.1.2:code"

    def test_unit_remapped_to_resources(self):
        elt = _make_ix_elt("unit", XbrlConst.ixbrl)
        assert ixMsgCode("code", elt, sect="constraint") == "ix10.12.1.1:code"

    def test_unrecognized_localname_falls_back_to_other(self):
        elt = _make_ix_elt("unknownElement", XbrlConst.ixbrl11)
        assert ixMsgCode("code", elt) == "ix11:code"

    def test_unrecognized_localname_ix10(self):
        elt = _make_ix_elt("unknownElement", XbrlConst.ixbrl)
        assert ixMsgCode("code", elt, sect="validation") == "ix10:code"

    def test_non_ix_namespace_uses_model_doc_ixNS(self):
        elt = _make_ix_elt("footnote", "http://www.w3.org/1999/xhtml", ixNS=XbrlConst.ixbrl11)
        assert ixMsgCode("code", elt, sect="validation") == "ix11.6.1.2:code"

    def test_non_ix_namespace_no_ixNS_defaults_to_ix11(self):
        elt = _make_ix_elt("footnote", "http://www.w3.org/1999/xhtml")
        assert ixMsgCode("code", elt, sect="validation") == "ix11.6.1.2:code"

    def test_non_ix_namespace_uses_model_doc_ixNS_ix10(self):
        elt = _make_ix_elt("nonFraction", "http://www.w3.org/1999/xhtml", ixNS=XbrlConst.ixbrl)
        assert ixMsgCode("code", elt, sect="constraint") == "ix10.9.1.1:code"

    def test_elt_with_explicit_name(self):
        elt = _make_ix_elt("footnote", XbrlConst.ixbrl11)
        assert ixMsgCode("code", elt, name="resources", sect="validation") == "ix11.14.1.2:code"

    def test_elt_with_explicit_name_context_not_remapped(self):
        # explicit name="context" is NOT remapped to "resources" — remap only applies to localName
        elt = _make_ix_elt("footnote", XbrlConst.ixbrl11)
        assert ixMsgCode("code", elt, name="context") == "ix11:code"  # falls back to "other"

    def test_elt_with_explicit_ns_raises(self):
        elt = _make_ix_elt("footnote", "http://www.w3.org/1999/xhtml", ixNS=XbrlConst.ixbrl)
        with pytest.raises(ValueError, match="ns must not be provided when elt is provided"):
            ixMsgCode("code", elt, ns=XbrlConst.ixbrl11, sect="validation")

    def test_elt_with_ix_ns_explicit_ns_raises(self):
        elt = _make_ix_elt("footnote", XbrlConst.ixbrl11)
        with pytest.raises(ValueError, match="ns must not be provided when elt is provided"):
            ixMsgCode("code", elt, ns=XbrlConst.ixbrl11, sect="validation")

    def test_default_sect_is_constraint(self):
        elt = _make_ix_elt("hidden", XbrlConst.ixbrl11)
        assert ixMsgCode("code", elt) == "ix11.9.1.1:code"


def _make_html_elt(localName, attrs=None, htmlBase=""):
    """Helper to build a mock HTML element for resolveHtmlUri tests."""
    attrs = attrs or {}
    return Mock(
        spec=ModelObject,
        localName=localName,
        namespaceURI="http://www.w3.org/1999/xhtml",
        modelDocument=Mock(htmlBase=htmlBase),
        prefix=None,
        get=attrs.get,
        items=attrs.items,
    )


class TestResolveHtmlUri:

    def test_relative_uri_resolved_against_html_base(self):
        elt = _make_html_elt("a", htmlBase="http://example.com/docs/")
        result = resolveHtmlUri(elt, "href", "page.html")
        assert result == "http://example.com/docs/page.html"

    def test_absolute_uri_unchanged(self):
        elt = _make_html_elt("a", htmlBase="http://example.com/docs/")
        result = resolveHtmlUri(elt, "href", "http://other.com/page.html")
        assert result == "http://other.com/page.html"

    def test_empty_html_base(self):
        elt = _make_html_elt("img", htmlBase="")
        result = resolveHtmlUri(elt, "src", "images/logo.png")
        assert result == "images/logo.png"

    def test_html_base_none_coerced(self):
        elt = _make_html_elt("img", htmlBase=None)
        result = resolveHtmlUri(elt, "src", "images/logo.png")
        assert result == "images/logo.png"

    def test_archive_splits_uris(self):
        elt = _make_html_elt("object", htmlBase="http://example.com/")
        result = resolveHtmlUri(elt, "archive", "a.jar b.jar c.jar")
        assert result == "http://example.com/a.jar http://example.com/b.jar http://example.com/c.jar"

    def test_archive_single_uri(self):
        elt = _make_html_elt("object", htmlBase="http://example.com/")
        result = resolveHtmlUri(elt, "archive", "lib.jar")
        assert result == "http://example.com/lib.jar"

    def test_object_classid_uses_codebase(self):
        elt = _make_html_elt("object", attrs={"codebase": "http://example.com/classes"})
        result = resolveHtmlUri(elt, "classid", "MyClass.class")
        assert result == "http://example.com/classes/MyClass.class"

    def test_object_data_uses_codebase(self):
        elt = _make_html_elt("object", attrs={"codebase": "http://example.com/data"})
        result = resolveHtmlUri(elt, "data", "info.xml")
        assert result == "http://example.com/data/info.xml"

    def test_object_without_codebase_uses_html_base(self):
        elt = _make_html_elt("object", attrs={}, htmlBase="http://example.com/base/")
        result = resolveHtmlUri(elt, "data", "info.xml")
        assert result == "http://example.com/base/info.xml"

    def test_object_codebase_not_used_for_usemap(self):
        # usemap is not in ("classid", "data", "archiveListElement") so codebase is ignored
        elt = _make_html_elt("object", attrs={"codebase": "http://example.com/classes"}, htmlBase="http://base.com/")
        result = resolveHtmlUri(elt, "usemap", "#mymap")
        assert result == "http://base.com/#mymap"

    def test_non_object_ignores_codebase_attr(self):
        # only <object> elements use codebase
        elt = _make_html_elt("img", attrs={"codebase": "http://example.com/classes"}, htmlBase="http://base.com/")
        result = resolveHtmlUri(elt, "src", "logo.png")
        assert result == "http://base.com/logo.png"

    def test_opaque_uri_not_path_normed(self):
        uri = "data:image/png;base64,iVBORw0K//a"
        elt = _make_html_elt("img", htmlBase=None)
        result = resolveHtmlUri(elt, "src", uri)
        assert result == uri
