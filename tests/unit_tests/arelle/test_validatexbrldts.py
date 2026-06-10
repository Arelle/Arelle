from __future__ import annotations

import pytest

from arelle.ValidateXbrlDTS import _isNegativeDecimal


class TestIsNegativeDecimal:
    """Tests for _isNegativeDecimal helper used by ix11.10.1.2 validation."""

    @pytest.mark.parametrize("text", [
        "-1",
        "-0.5",
        "-100",
        "-0.001",
        " -1 ",       # with whitespace
        "-1.0",
        "-99999999",
    ])
    def test_negative_numbers_return_true(self, text: str) -> None:
        assert _isNegativeDecimal(text) is True

    @pytest.mark.parametrize("text", [
        "0",
        "1",
        "0.5",
        "100",
        "0.001",
        " 1 ",        # with whitespace
        "99999999",
        "0.0",
    ])
    def test_non_negative_numbers_return_false(self, text: str) -> None:
        assert _isNegativeDecimal(text) is False

    @pytest.mark.parametrize("text", [
        "a-b",
        "2023-01-01",
        "hello-world",
        "some-text-with-hyphens",
        "",
        "   ",
        "abc",
        "1.2.3",
        "-",
        "--1",
        "1-2",
        "not-a-number",
    ])
    def test_non_numeric_text_returns_false(self, text: str) -> None:
        """Non-numeric text must NOT trigger the negative error (the false positive fix)."""
        assert _isNegativeDecimal(text) is False
