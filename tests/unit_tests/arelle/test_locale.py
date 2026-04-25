from __future__ import annotations
from collections.abc import Generator
from typing import Any
import locale
import sys
from unittest.mock import patch
import pytest
from decimal import Decimal
from arelle.Locale import format_decimal
from arelle.Locale import getUserLocale
from arelle.Locale import (
    _candidateLocaleCodes,
    _compatibleSystemLocales,
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

_SYSTEM_LOCALES = _getSystemLocalesAsPosix()
_HAS_EN_US = 'en_US' in _SYSTEM_LOCALES
_HAS_EN_GB = 'en_GB' in _SYSTEM_LOCALES
_HAS_FI = any(loc.startswith('fi_') for loc in _SYSTEM_LOCALES)
_HAS_FIL = any(loc.startswith('fil_') for loc in _SYSTEM_LOCALES)


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


class TestCompatibleSystemLocales:
    def test_filters_by_language(self) -> None:
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'en_US', 'fr_FR', 'de_DE'})):
            result = _compatibleSystemLocales('en', region='US', encoding=None, exclude=[])
        assert result == ['en_US']

    def test_excludes_already_listed(self) -> None:
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'en_US', 'en_GB'})):
            result = _compatibleSystemLocales('en', region='US', encoding=None, exclude=['en_US'])
        assert 'en_US' not in result
        assert 'en_GB' in result

    def test_matches_bare_language(self) -> None:
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'en', 'fr'})):
            result = _compatibleSystemLocales('en', region=None, encoding=None, exclude=[])
        assert result == ['en']

    def test_no_false_prefix_match(self) -> None:
        """'english' should not match language 'en' — must have a separator at lang_len."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'english', 'eno'})):
            result = _compatibleSystemLocales('en', region=None, encoding=None, exclude=[])
        assert result == []

    def test_language_prefix_does_not_match_longer_language_code(self) -> None:
        """'fi' (Finnish) must not match 'fil_PH' (Filipino) even though 'fil' starts with 'fi'."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'fi_FI', 'fil_PH'})):
            result = _compatibleSystemLocales('fi', region='FI', encoding=None, exclude=[])
        assert 'fil_PH' not in result
        assert 'fi_FI' in result

    def test_longer_language_code_does_not_match_prefix(self) -> None:
        """'fil' (Filipino) must not match 'fi_FI' (Finnish) even though 'fil' starts with 'fi'."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'fi_FI', 'fil_PH'})):
            result = _compatibleSystemLocales('fil', region='PH', encoding=None, exclude=[])
        assert 'fi_FI' not in result
        assert 'fil_PH' in result

    def test_sort_prefers_matching_region(self) -> None:
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'en_US', 'en_GB', 'en_AU'})):
            result = _compatibleSystemLocales('en', region='US', encoding=None, exclude=[])
        assert result[0] == 'en_US'

    def test_sort_prefers_matching_encoding(self) -> None:
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'en_US.UTF-8', 'en_US.ISO-8859-1'})):
            result = _compatibleSystemLocales('en', region='US', encoding='UTF-8', exclude=[])
        assert result[0] == 'en_US.UTF-8'

    def test_empty_system_locales(self) -> None:
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset()):
            result = _compatibleSystemLocales('en', region='US', encoding=None, exclude=[])
        assert result == []

    def test_bare_language_matches_all_regions(self) -> None:
        """Bare 'en' with no region matches en_US, en_GB, en_AU etc."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'en_US', 'en_GB', 'en_AU', 'fr_FR'})):
            result = _compatibleSystemLocales('en', region=None, encoding=None, exclude=[])
        assert set(result) == {'en_US', 'en_GB', 'en_AU'}

    def test_bare_language_matches_encoding_variants(self) -> None:
        """Bare 'ja' matches ja_JP.UTF-8, ja_JP.eucJP etc."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'ja_JP.UTF-8', 'ja_JP.eucJP', 'en_US'})):
            result = _compatibleSystemLocales('ja', region=None, encoding=None, exclude=[])
        assert set(result) == {'ja_JP.UTF-8', 'ja_JP.eucJP'}

    def test_bare_language_with_encoding_dot_separator(self) -> None:
        """Bare 'en' matches en.UTF-8 (dot separator at lang_len)."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'en.UTF-8', 'en_US'})):
            result = _compatibleSystemLocales('en', region=None, encoding=None, exclude=[])
        assert set(result) == {'en.UTF-8', 'en_US'}

    def test_sort_encoding_no_encoding_requested_prefers_no_encoding(self) -> None:
        """When no encoding requested, locales without encoding sort first."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'en_US', 'en_US.UTF-8', 'en_US.ISO-8859-1'})):
            result = _compatibleSystemLocales('en', region='US', encoding=None, exclude=[])
        assert result[0] == 'en_US'

    def test_sort_non_utf8_encoding_requested(self) -> None:
        """When ISO-8859-1 is requested, that encoding sorts first."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'en_US.UTF-8', 'en_US.ISO-8859-1'})):
            result = _compatibleSystemLocales('en', region='US', encoding='ISO-8859-1', exclude=[])
        assert result[0] == 'en_US.ISO-8859-1'

    def test_all_encoding_variants_included(self) -> None:
        """All encoding variants of the language are included, not just the requested one."""
        system = frozenset({'en_US.UTF-8', 'en_US.ISO-8859-1', 'en_US.eucJP'})
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=system):
            result = _compatibleSystemLocales('en', region='US', encoding='UTF-8', exclude=[])
        assert set(result) == system

    def test_bare_language_sorts_before_regionalized_when_no_region(self) -> None:
        """When region=None, bare 'en' should sort before 'en_US' / 'en_GB'."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'en', 'en_US', 'en_GB'})):
            result = _compatibleSystemLocales('en', region=None, encoding=None, exclude=[])
        assert result[0] == 'en'


class TestCompatibleSystemLocalesIntegration:
    """Integration tests for _compatibleSystemLocales against the real system locale list.

    Unlike TestCompatibleSystemLocales, these tests do not mock _getSystemLocalesAsPosix,
    so they depend on specific locales being installed on the host. Individual tests are
    skipped when the required locales are absent.
    """

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> Generator:
        _getSystemLocalesAsPosix.cache_clear()
        yield
        _getSystemLocalesAsPosix.cache_clear()

    @pytest.mark.skipif(not _HAS_EN_US, reason="en_US locale not installed")
    def test_en_US_in_results(self) -> None:
        result = _compatibleSystemLocales('en', region='US', encoding=None, exclude=[])
        assert 'en_US' in result
        assert result[0] == 'en_US'
        assert all(r.startswith('en') for r in result)

    @pytest.mark.skipif(not _HAS_EN_GB, reason="en_GB locale not installed")
    def test_arelle_default_locale_en_GB_in_results(self) -> None:
        result = _compatibleSystemLocales('en', region='GB', encoding=None, exclude=[])
        assert 'en_GB' in result
        assert result[0] == 'en_GB'
        assert all(r.startswith('en') for r in result)

    @pytest.mark.skipif(not _HAS_FI or not _HAS_FIL, reason="fi and fil locales not installed")
    def test_fi_and_fil_do_not_cross_contaminate(self) -> None:
        """fi (Finnish) and fil (Filipino) are present on both Windows and Linux."""
        fi_result = _compatibleSystemLocales('fi', region=None, encoding=None, exclude=[])
        fil_result = _compatibleSystemLocales('fil', region=None, encoding=None, exclude=[])
        assert not any(r.startswith('fil') for r in fi_result)
        assert not any(r == 'fi' or r.startswith('fi_') for r in fil_result)


class TestCandidateLocaleCodes:
    def test_non_default_region_adds_default_variant(self) -> None:
        """en_US should produce en_GB since defaultLocaleCodes['en'] == 'GB'."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset()):
            result = _candidateLocaleCodes('en_US')
        assert 'en_GB' in result

    def test_non_default_encoding_adds_utf8_variant(self) -> None:
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset()):
            result = _candidateLocaleCodes('en_US.ISO-8859-1')
        assert 'en_US.utf-8' in result

    def test_bare_language_no_region_variants(self) -> None:
        """Bare language 'en' has no region, so no region-swap candidates are generated."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset()):
            result = _candidateLocaleCodes('en')
        # No computed candidates — region is None so the region != defaultRegion branch is skipped
        assert not any('_' in code for code in result)

    def test_system_locales_come_after_computed(self) -> None:
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'en_AU'})):
            result = _candidateLocaleCodes('en_US')
        # en_GB is the computed default-region variant, en_AU comes from system locales
        assert result.index('en_GB') < result.index('en_AU')

    def test_no_duplicates(self) -> None:
        """System locales that match a computed candidate should not appear twice."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset({'en_GB', 'en_AU'})):
            result = _candidateLocaleCodes('en_US')
        assert result.count('en_GB') == 1

    def test_bare_language_en(self) -> None:
        """Bare 'en' generates no computed candidates but picks up system locales."""
        system = frozenset({'en_US', 'en_GB', 'en_AU.UTF-8', 'fr_FR'})
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=system):
            result = _candidateLocaleCodes('en')
        assert 'fr_FR' not in result
        assert set(result) == {'en_US', 'en_GB', 'en_AU.UTF-8'}

    def test_bare_language_ja(self) -> None:
        """Bare 'ja' picks up all ja_* system locales."""
        system = frozenset({'ja_JP.UTF-8', 'ja_JP.eucJP', 'en_US'})
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=system):
            result = _candidateLocaleCodes('ja')
        assert set(result) == {'ja_JP.UTF-8', 'ja_JP.eucJP'}

    def test_non_default_encoding_generates_utf8_and_default_region_variants(self) -> None:
        """en_US.ISO-8859-1 generates en_US.utf-8, en_GB.ISO-8859-1, and en_GB.utf-8."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset()):
            result = _candidateLocaleCodes('en_US.ISO-8859-1')
        assert 'en_US.utf-8' in result
        assert 'en_GB.ISO-8859-1' in result
        assert 'en_GB.utf-8' in result

    def test_utf8_encoding_does_not_duplicate(self) -> None:
        """en_US.utf-8 is already the default encoding — no utf-8 variant generated."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset()):
            result = _candidateLocaleCodes('en_US.utf-8')
        assert result.count('en_US.utf-8') == 0  # input itself is not in candidates
        # Only the default-region variant is generated
        assert 'en_GB.utf-8' in result

    def test_UTF8_case_insensitive(self) -> None:
        """en_US.UTF-8 (uppercase) is treated as default encoding."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset()):
            result = _candidateLocaleCodes('en_US.UTF-8')
        # Should not generate en_US.utf-8 since UTF-8 is already the default
        assert 'en_US.utf-8' not in result
        assert 'en_GB.UTF-8' in result

    def test_default_region_no_extra_candidates(self) -> None:
        """en_GB is the default region for 'en' — no region-swap candidate generated."""
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=frozenset()):
            result = _candidateLocaleCodes('en_GB')
        # region == defaultRegion, so no fallback to another region
        assert not any(code.startswith('en_') and 'GB' not in code for code in result)

    def test_system_encoding_variants_sorted_by_relevance(self) -> None:
        """System locales with matching encoding sort before non-matching."""
        system = frozenset({'en_US.UTF-8', 'en_US.ISO-8859-1', 'en_US.eucJP'})
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=system):
            result = _candidateLocaleCodes('en_US.ISO-8859-1')
        # Computed candidates come first, then system locales
        # Among system locales, ISO-8859-1 would match but it's excluded (already computed as en_US.utf-8 variant)
        # en_US.ISO-8859-1 is the original input (not in candidates), but system has it
        system_portion = [c for c in result if c in system]
        # The one matching the requested encoding should come first among system locales
        iso_idx = [i for i, c in enumerate(system_portion) if 'ISO-8859-1' in c]
        utf8_idx = [i for i, c in enumerate(system_portion) if 'UTF-8' in c]
        assert iso_idx[0] < utf8_idx[0]

    def test_language_prefix_does_not_include_longer_language_code(self) -> None:
        """Candidates for 'fi' (Finnish) must not include 'fil_PH' (Filipino) system locales."""
        system = frozenset({'fi_FI', 'fil_PH'})
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=system):
            result = _candidateLocaleCodes('fi_FI')
        assert 'fil_PH' not in result

    def test_longer_language_code_does_not_include_prefix_locales(self) -> None:
        """Candidates for 'fil' (Filipino) must not include 'fi_FI' (Finnish) system locales."""
        system = frozenset({'fi_FI', 'fil_PH'})
        with patch.object(LocaleModule, '_getSystemLocalesAsPosix', return_value=system):
            result = _candidateLocaleCodes('fil_PH')
        assert 'fi_FI' not in result


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
