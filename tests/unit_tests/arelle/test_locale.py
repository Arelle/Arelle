from __future__ import annotations
from typing import Any
import locale
import pytest
from decimal import Decimal
from arelle.Locale import format_decimal
from arelle.Locale import getUserLocale
from arelle.Locale import (
    bcp47LangToPosixLocale,
    posixLocaleToBCP47Lang,
)


d = Decimal('-1234567.8901')

@pytest.mark.parametrize(
    'params, result',
    [
        (
            {
                'conv': getUserLocale()[0],
                'value': d,
                'curr': '$',
                'neg': '-'
            },
            '-$1,234,567.89'
        ),
        (
            {
                'conv': getUserLocale()[0],
                'value': d,
                'fractPlaces': 0,
                'sep': '.',
                'dp': '',
                'trailneg': '-'
            },
            '1.234.568-'
        ),
        (
            {
                'conv': getUserLocale()[0],
                'value': d,
                'curr': '$',
                'neg': '(',
                'trailneg': ')'
            },
            '($1,234,567.89)'
        ),
        (
            {
                'conv': getUserLocale()[0],
                'value': Decimal(123456789),
                'sep': ' '
            },
            '123 456 789.00'
        ),
        (
            {
                'conv': getUserLocale()[0],
                'value': Decimal('-0.02'),
                'neg': '<',
                'trailneg': '>'
            },
            '<0.02>'
        ),
    ]
)
def test_format_decimal(params: dict[str, Any], result: str) -> None:
    assert format_decimal(**params) == result


@pytest.mark.parametrize('locale_code', ['', 'C', 'invalid'])
def test_get_user_locale_reset(locale_code) -> None:
    before_locale = locale.setlocale(locale.LC_ALL)
    getUserLocale(locale_code)
    after_locale = locale.setlocale(locale.LC_ALL)
    assert after_locale == before_locale

class TestBcp47LangToPosixLocale:
    @pytest.mark.parametrize('bcp47, expected', [
        ('en-US', 'en_US'),
        ('fr-FR', 'fr_FR'),
        ('zh-CN', 'zh_CN'),
        ('en', 'en'),
    ])
    def test_converts_bcp47_to_posix(self, bcp47: str, expected: str) -> None:
        assert bcp47LangToPosixLocale(bcp47) == expected

    @pytest.mark.parametrize('posix', ['en_US', 'fr_FR', 'de_DE', 'en'])
    def test_posix_input_passes_through(self, posix: str) -> None:
        """A POSIX locale without encoding and no hyphens should pass through unchanged."""
        assert bcp47LangToPosixLocale(posix) == posix

    @pytest.mark.parametrize('posix_with_encoding', [
        'en_US.UTF-8',
        'fr_FR.utf-8',
    ])
    def test_posix_with_encoding_passes_through(self, posix_with_encoding: str) -> None:
        """POSIX locales with encoding should pass through unchanged."""
        assert bcp47LangToPosixLocale(posix_with_encoding) == posix_with_encoding


class TestPosixLocaleToBCP47Lang:
    @pytest.mark.parametrize('posix, expected', [
        ('en_US', 'en-US'),
        ('en_US.UTF-8', 'en-US'),
        ('fr_FR.utf-8', 'fr-FR'),
        ('en', 'en'),
    ])
    def test_converts_posix_to_bcp47(self, posix: str, expected: str) -> None:
        assert posixLocaleToBCP47Lang(posix) == expected

    @pytest.mark.parametrize('bcp47', ['en-US', 'fr-FR', 'de-DE', 'en'])
    def test_bcp47_input_passes_through(self, bcp47: str) -> None:
        """A BCP-47 tag with no underscores should pass through unchanged."""
        assert posixLocaleToBCP47Lang(bcp47) == bcp47

