from __future__ import annotations
from typing import Any
import locale
import sys
from unittest.mock import patch
import pytest
from decimal import Decimal
from arelle.Locale import format_decimal
from arelle.Locale import getUserLocale
from arelle.Locale import (
    _enumerateWindowsLocales,
    findCompatibleLocale,
    _getNativeLocale,
    availableLocales,
    bcp47LangToPosixLocale,
    getLocale,
    _getSystemLocalesAsPosix,
    posixLocaleToBCP47Lang,
)
from arelle.XbrlConst import defaultLocale
import arelle.Locale as LocaleModule


d = Decimal('-1234567.8901')


@pytest.fixture()
def reset_system_locales():
    _getSystemLocalesAsPosix.cache_clear()
    yield
    _getSystemLocalesAsPosix.cache_clear()


@pytest.fixture()
def reset_locale():
    getLocale.cache_clear()
    yield
    getLocale.cache_clear()

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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
class TestWindowsLocaleEnumeration:
    def test_enumerate_windows_locales_returns_nonempty(self) -> None:
        locales = _enumerateWindowsLocales()
        assert len(locales) > 0

    def test_enumerate_windows_locales_bcp47_format(self) -> None:
        locales = _enumerateWindowsLocales()
        # BCP-47 tags use hyphens, not underscores
        simple_locales = [loc for loc in locales if len(loc) == 5]
        assert len(simple_locales) > 0
        for loc in simple_locales:
            assert '-' in loc, f"Expected BCP-47 format with hyphen: {loc}"
            assert '_' not in loc, f"Unexpected POSIX underscore in: {loc}"

    def test_enumerate_windows_locales_contains_en_US(self) -> None:
        locales = _enumerateWindowsLocales()
        assert 'en-US' in locales
    
    def test_enumerate_windows_locales_contains_default_locale(self) -> None:
        locales = _enumerateWindowsLocales()
        assert defaultLocale in locales

    def test_get_system_locale_list_as_posix_on_windows(self, reset_system_locales) -> None:
        result = _getSystemLocalesAsPosix()
        assert len(result) > 0
        assert 'en_US' in result
        for loc in [l for l in result if len(l) == 5]:
            assert '_' in loc

    def test_available_locales_nonempty_on_windows(self, reset_system_locales) -> None:
        result = availableLocales()
        assert len(result) > 0
        assert 'en_US' in result


class TestGetSystemLocalesAsPosix:
    def test_posix_locales_from_locale_command(self, reset_system_locales) -> None:
        """On non-Windows, output of locale -a is returned as-is."""
        with patch.object(LocaleModule, 'tryRunCommand', return_value='en_US.UTF-8\nfr_FR.UTF-8\nde_DE.UTF-8'):
            with patch('arelle.Locale.sys') as mock_sys:
                mock_sys.platform = 'linux'
                result = _getSystemLocalesAsPosix()
        assert result == frozenset({'en_US.UTF-8', 'fr_FR.UTF-8', 'de_DE.UTF-8'})

    def test_windows_locales_converted_from_bcp47(self, reset_system_locales) -> None:
        """On Windows, BCP-47 names from EnumSystemLocalesEx are converted to POSIX."""
        with patch.object(LocaleModule, '_enumerateWindowsLocales', return_value=['en-US', 'fr-FR', 'de-DE']):
            with patch('arelle.Locale.sys') as mock_sys:
                mock_sys.platform = 'win32'
                result = _getSystemLocalesAsPosix()
        assert result == frozenset({'en_US', 'fr_FR', 'de_DE'})

    def test_returns_empty_when_locale_command_fails(self, reset_system_locales) -> None:
        """Returns an empty set when locale -a produces no output."""
        with patch.object(LocaleModule, 'tryRunCommand', return_value=None):
            with patch('arelle.Locale.sys') as mock_sys:
                mock_sys.platform = 'linux'
                result = _getSystemLocalesAsPosix()
        assert result == frozenset()


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

_FAKE_CONV = {'decimal_point': '.'}


class TestFindCompatibleLocale:
    def test_none_returns_none(self) -> None:
        assert findCompatibleLocale(None) is None

    def test_bcp47_converted_to_posix_before_probe(self) -> None:
        """BCP-47 input is normalised to POSIX before being passed to _probeLocale."""
        probed: list[str] = []
        def mock_probe(code: str):
            probed.append(code)
            return _FAKE_CONV
        with patch.object(LocaleModule, '_probeLocale', side_effect=mock_probe):
            findCompatibleLocale('en-US')
        assert probed[0] == 'en_US'

    def test_direct_match_returns_posix_value(self) -> None:
        """When the POSIX-converted locale probes successfully it is returned immediately."""
        with patch.object(LocaleModule, '_probeLocale', return_value=_FAKE_CONV):
            result = findCompatibleLocale('en-US')
        assert result == 'en_US'

    def test_posix_input_passed_through_unchanged(self) -> None:
        """POSIX input (underscore / encoding) is left unchanged by the BCP-47 conversion."""
        probed: list[str] = []
        def mock_probe(code: str):
            probed.append(code)
            return _FAKE_CONV
        with patch.object(LocaleModule, '_probeLocale', side_effect=mock_probe):
            result = findCompatibleLocale('en_US.UTF-8')
        assert probed[0] == 'en_US.UTF-8'
        assert result == 'en_US.UTF-8'

    def test_falls_back_to_first_working_candidate(self) -> None:
        """When the direct probe fails, returns the first candidate that probes successfully."""
        def mock_probe(code: str):
            return _FAKE_CONV if code == 'en_GB' else None
        with patch.object(LocaleModule, '_probeLocale', side_effect=mock_probe):
            with patch.object(LocaleModule, '_candidateLocaleCodes', return_value=['en_AU', 'en_GB', 'en_NZ']):
                result = findCompatibleLocale('en_US')
        assert result == 'en_GB'

    def test_no_working_locale_returns_none(self) -> None:
        """Returns None when neither the direct probe nor any candidate succeeds."""
        with patch.object(LocaleModule, '_probeLocale', return_value=None):
            with patch.object(LocaleModule, '_candidateLocaleCodes', return_value=['en_GB', 'en_AU']):
                result = findCompatibleLocale('en_US')
        assert result is None

    def test_empty_candidates_returns_none(self) -> None:
        """Returns None when the direct probe fails and the candidate list is empty."""
        with patch.object(LocaleModule, '_probeLocale', return_value=None):
            with patch.object(LocaleModule, '_candidateLocaleCodes', return_value=[]):
                result = findCompatibleLocale('xx_YY')
        assert result is None


class TestGetLocale:
    def test_returns_cached_value(self, reset_locale) -> None:
        first = getLocale()
        assert getLocale.cache_info().currsize == 1
        second = getLocale()
        assert getLocale.cache_info().hits >= 1
        assert first == second

    def test_returns_nonempty_string(self, reset_locale) -> None:
        result = getLocale()
        assert result is not None
        assert len(result) >= 2

    def test_result_is_cached(self, reset_locale) -> None:
        first = getLocale()
        second = getLocale()
        assert first == second
        assert getLocale.cache_info().hits >= 1

    def test_result_has_no_encoding(self, reset_locale) -> None:
        result = getLocale()
        assert '.' not in result, f"Locale should not contain encoding separator: {result}"

    def test_result_is_posix_format(self, reset_locale) -> None:
        """getLocale always returns POSIX-style locale (underscore separator, no hyphens)."""
        result = getLocale()
        assert result is not None
        if len(result) == 5:
            assert '_' in result, f"Expected POSIX underscore separator: {result}"
            assert '-' not in result, f"Unexpected BCP-47 hyphen in: {result}"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
class TestGetNativeLocaleWindows:
    def test_returns_bcp47_from_windows_api(self) -> None:
        """On Windows, _getNativeLocale returns BCP-47 from GetUserDefaultLocaleName."""
        result = _getNativeLocale()
        assert result is not None
        assert len(result) >= 2
        if len(result) == 5:
            assert '-' in result, f"Expected BCP-47 hyphen separator: {result}"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
class TestGetLocaleWindows:
    def test_returns_posix_locale(self, reset_locale) -> None:
        """On Windows, getLocale normalizes BCP-47 to POSIX."""
        result = getLocale()
        assert result is not None
        if len(result) == 5:
            assert '_' in result, f"Expected POSIX underscore separator: {result}"
            assert '-' not in result, f"Unexpected BCP-47 hyphen in: {result}"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only test")
class TestGetNativeLocaleMacOS:
    def test_returns_locale(self) -> None:
        """On macOS, _getNativeLocale returns from defaults read."""
        result = _getNativeLocale()
        assert result is not None
        assert len(result) >= 2
