import pytest
from unittest.mock import Mock

from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname
from arelle.XmlUtil import (
    escapedNode,
    escapedText,
    collapseWhitespace,
    replaceWhitespace,
    xhtmlFragmentsEqual,
)


def test_opaque_uris_not_path_normed():
    uri = "data:image/png;base64,iVBORw0K//a"
    elt_attrs = {"src": uri}
    elt = Mock(
        spec=ModelObject,

        localName="img",
        namespaceURI="http://www.w3.org/1999/xhtml",
        modelDocument=Mock(htmlBase=None),
        prefix=None,
        nsmap={},

        get=elt_attrs.get,
        items=elt_attrs.items,
    )
    elt.qname = qname(elt)
    node = escapedNode(elt, start=True, empty=True, ixEscape=True, ixResolveUris=True)
    assert node == f'<img src="{uri}">'


def test_object_codebase_resolved_without_changing_source():
    elt_attrs = {"codebase": "relative/codebase", "data": "path/to/data.file"}
    elt = Mock(
        spec=ModelObject,
        localName="object",
        namespaceURI="http://www.w3.org/1999/xhtml",
        modelDocument=Mock(htmlBase="http://www.example.com/base/"),
        prefix=None,
        nsmap={},
        get=elt_attrs.get,
        items=elt_attrs.items,
    )
    elt.qname = qname(elt)
    node = escapedNode(elt, start=True, empty=False, ixEscape=True, ixResolveUris=True)
    assert node == '<object codebase="http://www.example.com/base/relative/codebase" data="path/to/data.file">'
    elt.set.assert_not_called()


REPLACE_WHITESPACE_TESTS = [
    ("\n", " "),
    ("\r", " "),
    ("\t", " "),
    ("\r\t\n", " " * 3),
    ("\t\t \n\n \r\r", " " * 8),
    ("\r \n \t", " " * 5),
    # literal or entity \v and \f are illegal in XML but we shouldn't be touching them
    ("\r\v\t", " \v "),
    ("\r\f\t", " \f "),
    # Python's whitespace (\s, str.isspace) definition includes em space (U+2003)
    # but XSD replace does not so we shouldn't be touching it
    ("1\u2003", "1\u2003"),
    (" m u s h r o o m  ", " m u s h r o o m  "),
    (" m u s h\tr o o m  ", " m u s h r o o m  "),
]


@pytest.mark.parametrize("value, expected", REPLACE_WHITESPACE_TESTS)
def test_replaceWhitespace(value, expected):
    result = replaceWhitespace(value)
    assert result == expected


COLLAPSE_WHITESPACE_TESTS = [
    ("", ""),
    ("plain", "plain"),
    ("\talpha\u00a0beta \n gamma\u0085delta\r", "alpha\u00a0beta gamma\u0085delta"),
    ("\t\u2003\n\u2028\r\u2029 ", "\u2003 \u2028 \u2029"),
    ("\n", ""),
    ("\r", ""),
    ("\t", ""),
    ("\r\t\n", ""),
    ("\t\t \n\n \r\r", ""),
    ("\r \n \t", ""),
    # literal or entity \v and \f are illegal in XML but we shouldn't be touching them
    ("\r\v\t", "\v"),
    ("\r\f\t", "\f"),
    # Python's whitespace (\s, str.strip) definition includes em space (U+2003)
    # but XSD collapse does not so we shouldn't be touching it
    (" \u2003 \u2003  ", "\u2003 \u2003"),
    (" " * 10, ""),
    (" " * 10 + "1", "1"),
    (" " * 10 + "1  1", "1 1"),
    (" " * 10 + "1  1" + " " * 10, "1 1"),
    ("  \r\n  the \tspace  \t\nis  \n  right  \r\n\r\n", "the space is right"),
    (" x  xm   xml    xmln     ", "x xm xml xmln"),
    ("time: \n\tround\n\ttuit  \r\n", "time: round tuit"),
]


@pytest.mark.parametrize("value, expected", COLLAPSE_WHITESPACE_TESTS)
def test_collapseWhitespace(value, expected):
    result = collapseWhitespace(value)
    assert result == expected


XHTML_FRAGMENTS_EQUAL_TESTS = [
    ("a <b>b</b>", 'a <b xmlns="http://www.w3.org/1999/xhtml">b</b>', True),
    ("<a title='t' href='x'>y</a>", '<a href="x" title="t">y</a>', True),
    ("<b>&amp;lt;XML&gt;</b>", "<b>&#38;lt;XML&#62;</b>", True),
    ("<br/>", "<br></br>", True),
    ("<p>a\n  <b>b</b></p>", "<p>a <b>b</b></p>", True),
    ('\n<p xmlns="http://www.w3.org/1999/xhtml">p</p>\n0.10\n', "<p>p</p>\n0.10", True),
    ("<b>b</b>", '<b xmlns="http://example.com/">b</b>', False),
    ("<b>b</b>", "<i>b</i>", False),
    ("<b>b</b>", "&lt;b&gt;b&lt;/b&gt;", False),
    ("a < b", "a  <  b", False),
    ("<b>&nbsp;</b>", "<b>&#160;</b>", False),
]


@pytest.mark.parametrize("a, b, expected", XHTML_FRAGMENTS_EQUAL_TESTS)
def test_xhtmlFragmentsEqual(a, b, expected):
    assert xhtmlFragmentsEqual(a, b) is expected
    assert xhtmlFragmentsEqual(b, a) is expected


XHTML_FRAGMENTS_EQUAL_WITHOUT_NORMALIZED_SPACE_TESTS = [
    ("a <b>b</b>", 'a <b xmlns="http://www.w3.org/1999/xhtml">b</b>', True),
    ("<a title='t'  href='x'>y</a>", '<a href="x" title="t">y</a>', True),
    ("<p>a\n  <b>b</b></p>", "<p>a <b>b</b></p>", False),
    ("<p>p</p>\n", "<p>p</p>", False),
]


@pytest.mark.parametrize("a, b, expected", XHTML_FRAGMENTS_EQUAL_WITHOUT_NORMALIZED_SPACE_TESTS)
def test_xhtmlFragmentsEqual_without_normalized_space(a, b, expected):
    assert xhtmlFragmentsEqual(a, b, normalizeSpace=False) is expected
    assert xhtmlFragmentsEqual(b, a, normalizeSpace=False) is expected


ESCAPED_TEXT_TESTS = [
    ("", ""),
    ("hello", "hello"),
    ("a & b", "a &amp; b"),
    ("<tag>", "&lt;tag&gt;"),
    ("1 < 2 & 3 > 0", "1 &lt; 2 &amp; 3 &gt; 0"),
    ("&amp;", "&amp;amp;"),
    ("<<>>&&", "&lt;&lt;&gt;&gt;&amp;&amp;"),
    ("no special chars", "no special chars"),
    ('quotes "are" fine', 'quotes "are" fine'),
    ("apostrophe's ok", "apostrophe's ok"),
    ("a&b<c>d", "a&amp;b&lt;c&gt;d"),
    ("&<>", "&amp;&lt;&gt;"),
    (" & ", " &amp; "),
    ("\n&\t<\r>", "\n&amp;\t&lt;\r&gt;"),
]


@pytest.mark.parametrize("value, expected", ESCAPED_TEXT_TESTS)
def test_escapedText(value, expected):
    assert escapedText(value) == expected
