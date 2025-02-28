import pytest
import regex

from arelle.FunctionFn import tokenize, normalize_space
from arelle.formula import XPathContext

from test_xmlutil import COLLAPSE_WHITESPACE_TESTS

# See https://www.w3.org/TR/xpath-functions/#func-tokenize for test sources:
TOKENIZE_TESTS = [
    # If $input is the empty sequence, or if $input is the zero-length string, the function returns the empty sequence.
    (("",), ([]), None),
    (("", r"."), ([]), None),
    (((),), ([]), None),
    (((), r"."), ([]), None),
    # If two alternatives within the supplied $pattern both match at the same position in the $input string, then the match that is chosen is the first. For example:
    (("abracadabra", r"ab|a"), ("", "r", "c", "d", "r", ""), None),
    (("abracadabra", r"(?:ab)|(?:a)"), ("", "r", "c", "d", "r", ""), None),
    # Should still work the same with capturing groups specified
    (("abracadabra", r"(ab)|(a)"), ("", "r", "c", "d", "r", ""), None),
    # Examples from
    ((" red green blue ",), ("red", "green", "blue"), None),
    (
        ("The cat sat on the mat", r"\s+"),
        ("The", "cat", "sat", "on", "the", "mat"),
        None,
    ),
    ((" red green blue ", r"\s+"), ("", "red", "green", "blue", ""), None),
    (("1, 15, 24, 50", r",\s*"), ("1", "15", "24", "50"), None),
    (("1,15,,24,50,", r","), ("1", "15", "", "24", "50", ""), None),
    (("abba", ".?"), None, "[err:FORX0003]"),
    (
        ("Some unparsed <br> HTML <BR> text", r"\s*<br>\s*", "i"),
        ("Some unparsed", "HTML", "text"),
        None,
    ),
    # Broken regex raises right error code
    (("a", "*"), None, "[err:FORX0002]"),
    (("a", "*", "i"), None, "[err:FORX0002]"),
    # Broken flags raises right error code
    (("a", ".", "p"), None, "[err:FORX0001]"),
    # Pattern not found in input, return input string as singleton
    (("asdf", "99", ""), ("asdf",), None),
]


@pytest.mark.parametrize("args,expected,raises", TOKENIZE_TESTS)
def test_tokenize(args, expected, raises):
    xc = None
    p = None
    contextItem = None
    if raises is None:
        result = tokenize(xc, p, contextItem, args)
        assert result == list(expected)
    else:
        with pytest.raises(XPathContext.XPathException, match=regex.escape(raises)):
            result = tokenize(xc, p, contextItem, args)


@pytest.mark.parametrize("test,expected", COLLAPSE_WHITESPACE_TESTS)
def test_normalize_whitespace(test, expected):
    xc = None
    p = None
    contextItem = None
    args = (test,)
    result = normalize_space(xc, p, contextItem, args)
    assert result == expected


XPATH_NORMALIZE_SPACE_EXAMPLES = {
    (
        (
            " The    wealthy curled darlings                                         of    our    nation. ",
        ),
        "The wealthy curled darlings of our nation.",
    ),
    (((),), ""),
}


@pytest.mark.parametrize("args,expected", XPATH_NORMALIZE_SPACE_EXAMPLES)
def test_normalize_whitespace_examples(args, expected):
    xc = None
    p = None
    contextItem = None
    result = normalize_space(xc, p, contextItem, args)
    assert result == expected
