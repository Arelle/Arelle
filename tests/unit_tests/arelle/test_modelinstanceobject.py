"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from arelle.ModelInstanceObject import ModelFact, ModelInlineFact


def _textFact(value, spec=ModelFact, **attrs):
    return Mock(
        spec=spec,
        isTuple=False,
        isNil=False,
        context=Mock(isEqualTo=Mock(return_value=True)),
        concept=Mock(isNumeric=False, isFraction=False),
        value=value,
        **attrs,
    )


def _escapedFact(value):
    return _textFact(value, spec=ModelInlineFact, isEscaped=True)


@pytest.mark.parametrize("normalizeXhtml, expected", [(False, False), (True, True)])
def test_isVEqualTo_normalizeXhtml(normalizeXhtml, expected):
    fact = _escapedFact("a <b>b</b>")
    other = _textFact('a <b xmlns="http://www.w3.org/1999/xhtml">b</b>')
    assert ModelFact.isVEqualTo(fact, other, normalizeXhtml=normalizeXhtml) is expected
    assert ModelFact.isVEqualTo(other, fact, normalizeXhtml=normalizeXhtml) is expected


@pytest.mark.parametrize("spec, attrs", [
    (ModelFact, {}),
    (ModelInlineFact, {"isEscaped": False}),
])
def test_isVEqualTo_normalizeXhtml_ignores_unescaped_facts(spec, attrs):
    fact = _textFact("a <b>b</b>", spec=spec, **attrs)
    other = _textFact('a <b xmlns="http://www.w3.org/1999/xhtml">b</b>')
    assert ModelFact.isVEqualTo(fact, other, normalizeXhtml=True) is False
    assert ModelFact.isVEqualTo(other, fact, normalizeXhtml=True) is False


def test_isVEqualTo_normalizeXhtml_keeps_text_comparison():
    fact = _textFact("a  &  b")
    assert ModelFact.isVEqualTo(fact, _textFact("a & b"), normalizeXhtml=True) is True
    assert ModelFact.isVEqualTo(fact, _textFact("a & c"), normalizeXhtml=True) is False


@pytest.mark.parametrize("otherValue, expected", [
    ('<b xmlns="http://www.w3.org/1999/xhtml">b</b> c', True),
    ('<b xmlns="http://www.w3.org/1999/xhtml">b</b>  c', False),
])
def test_isVEqualTo_normalizeXhtml_without_normalized_space(otherValue, expected):
    fact = _escapedFact("<b>b</b> c")
    assert ModelFact.isVEqualTo(fact, _textFact(otherValue), normalizeSpace=False, normalizeXhtml=True) is expected
