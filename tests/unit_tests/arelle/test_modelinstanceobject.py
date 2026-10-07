"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from arelle.ModelInstanceObject import ModelFact


def _textFact(value):
    return Mock(
        spec=ModelFact,
        isTuple=False,
        isNil=False,
        context=Mock(isEqualTo=Mock(return_value=True)),
        concept=Mock(isNumeric=False, isFraction=False),
        value=value,
    )


@pytest.mark.parametrize("normalizeXhtml, expected", [(False, False), (True, True)])
def test_isVEqualTo_normalizeXhtml(normalizeXhtml, expected):
    fact = _textFact("a <b>b</b>")
    other = _textFact('a <b xmlns="http://www.w3.org/1999/xhtml">b</b>')
    assert ModelFact.isVEqualTo(fact, other, normalizeXhtml=normalizeXhtml) is expected


def test_isVEqualTo_normalizeXhtml_keeps_text_comparison():
    fact = _textFact("a  &  b")
    assert ModelFact.isVEqualTo(fact, _textFact("a & b"), normalizeXhtml=True) is True
    assert ModelFact.isVEqualTo(fact, _textFact("a & c"), normalizeXhtml=True) is False


@pytest.mark.parametrize("otherValue, expected", [
    ('<b xmlns="http://www.w3.org/1999/xhtml">b</b> c', True),
    ('<b xmlns="http://www.w3.org/1999/xhtml">b</b>  c', False),
])
def test_isVEqualTo_normalizeXhtml_without_normalized_space(otherValue, expected):
    fact = _textFact("<b>b</b> c")
    assert ModelFact.isVEqualTo(fact, _textFact(otherValue), normalizeSpace=False, normalizeXhtml=True) is expected
