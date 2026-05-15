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
    _candidatePosixLocales,
    _compatibleSystemLocales,
    _enumerateWindowsLocales,
    findCompatibleLocale,
    _getNativeLocale,
    availableLocales,
    availableBCP47LangTags,
    bcp47LangToPosixLocale,
    getLocale,
    _getSystem_LocaleCodes,
    _LocaleCode,
    posixLocaleToBCP47Lang,
)
from arelle.PythonUtil import tryRunCommand
from arelle.XbrlConst import defaultLocale
import arelle.Locale as LocaleModule


d = Decimal('-1234567.8901')

_SYSTEM_LOCALES = _getSystem_LocaleCodes()
_HAS_EN_US = any(lc.lang == 'en' and lc.region == 'US' for lc in _SYSTEM_LOCALES)
_HAS_EN_GB = any(lc.lang == 'en' and lc.region == 'GB' for lc in _SYSTEM_LOCALES)
_HAS_FI = any(lc.lang == 'fi' and lc.region for lc in _SYSTEM_LOCALES)
_HAS_FIL = any(lc.lang == 'fil' and lc.region for lc in _SYSTEM_LOCALES)


@pytest.fixture()
def reset_system_locales():
    _getSystem_LocaleCodes.cache_clear()
    availableLocales.cache_clear()
    availableBCP47LangTags.cache_clear()
    yield
    _getSystem_LocaleCodes.cache_clear()
    availableLocales.cache_clear()
    availableBCP47LangTags.cache_clear()


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

    def test_get_system_locale_codes_on_windows(self, reset_system_locales) -> None:
        result = _getSystem_LocaleCodes()
        assert len(result) > 0
        assert any(lc.lang == 'en' and lc.region == 'US' for lc in result)
        assert all(lc.lang for lc in result)

    def test_available_locales_nonempty_on_windows(self, reset_system_locales) -> None:
        result = availableLocales()
        assert len(result) > 0
        assert 'en_US' in result

    def test_available_bcp47_lang_tags_nonempty_on_windows(self, reset_system_locales) -> None:
        result = availableBCP47LangTags()
        assert len(result) > 0
        assert 'en-US' in result


class TestGetSystem_LocaleCodes:
    def test_posix_locales_from_locale_command(self, reset_system_locales) -> None:
        """On non-Windows, output of locale -a is parsed into _LocaleCode objects."""
        with patch.object(LocaleModule, 'tryRunCommand', return_value='en_US.UTF-8\nfr_FR.UTF-8\nde_DE.UTF-8'):
            with patch('arelle.Locale.sys') as mock_sys:
                mock_sys.platform = 'linux'
                result = _getSystem_LocaleCodes()
        assert result == frozenset({_LocaleCode('en', 'US', 'UTF-8'), _LocaleCode('fr', 'FR', 'UTF-8'), _LocaleCode('de', 'DE', 'UTF-8')})

    def test_windows_locales_converted_from_bcp47(self, reset_system_locales) -> None:
        """On Windows, BCP-47 names from EnumSystemLocalesEx are parsed into _LocaleCode objects."""
        with patch.object(LocaleModule, '_enumerateWindowsLocales', return_value=['en-US', 'fr-FR', 'de-DE']):
            with patch('arelle.Locale.sys') as mock_sys:
                mock_sys.platform = 'win32'
                result = _getSystem_LocaleCodes()
        assert result == frozenset({_LocaleCode('en', 'US', None), _LocaleCode('fr', 'FR', None), _LocaleCode('de', 'DE', None)})

    def test_returns_empty_when_locale_command_fails(self, reset_system_locales) -> None:
        """Returns an empty set when locale -a produces no output."""
        with patch.object(LocaleModule, 'tryRunCommand', return_value=None):
            with patch('arelle.Locale.sys') as mock_sys:
                mock_sys.platform = 'linux'
                result = _getSystem_LocaleCodes()
        assert result == frozenset()

    def test_windows_locale_codes_parsed_from_bcp47(self, reset_system_locales) -> None:
        """_enumerateWindowsLocales output is parsed into _LocaleCode objects."""
        with patch.object(LocaleModule, '_enumerateWindowsLocales', return_value=['en-US', 'fr-FR']):
            with patch('arelle.Locale.sys') as mock_sys:
                mock_sys.platform = 'win32'
                result = _getSystem_LocaleCodes()
        assert result == frozenset({_LocaleCode('en', 'US', None), _LocaleCode('fr', 'FR', None)})

    def test_posix_filters_special_locales(self, reset_system_locales) -> None:
        """C, POSIX, and C.UTF-8 pseudo-locales are excluded; @modifier variants are parsed."""
        raw = 'en_US.UTF-8\nC\nPOSIX\nC.UTF-8\nsr_RS@latin\nde_AT@euro\nfr_FR.UTF-8'
        with patch.object(LocaleModule, 'tryRunCommand', return_value=raw):
            with patch('arelle.Locale.sys') as mock_sys:
                mock_sys.platform = 'linux'
                result = _getSystem_LocaleCodes()
        assert result == frozenset({
            _LocaleCode('en', 'US', 'UTF-8'),
            _LocaleCode('sr', 'RS', None),   # sr_RS@latin — modifier stripped
            _LocaleCode('de', 'AT', None),   # de_AT@euro — modifier stripped
            _LocaleCode('fr', 'FR', 'UTF-8'),
        })


class Test_LocaleCode:
    @pytest.mark.parametrize('posix, expected', [
        ('en_US.UTF-8',    _LocaleCode('en', 'US', 'UTF-8')),
        ('en_US',          _LocaleCode('en', 'US', None)),    # no encoding → None
        ('en',             _LocaleCode('en', None, None)),    # no region → None
        ('en.UTF-8',       _LocaleCode('en', None, 'UTF-8')), # encoding without region
        ('sr_RS@latin',    _LocaleCode('sr', 'RS', None)),   # script modifier stripped
        ('de_AT@euro',     _LocaleCode('de', 'AT', None)),   # non-script modifier stripped
        ('sr_RS.UTF-8@latin', _LocaleCode('sr', 'RS', 'UTF-8')), # encoding + modifier
    ])
    def test_from_posix(self, posix: str, expected: _LocaleCode) -> None:
        assert _LocaleCode.from_posix(posix) == expected

    @pytest.mark.parametrize('bcp47, expected', [
        ('en-US',      _LocaleCode('en', 'US', None)),   # encoding always None
        ('en',         _LocaleCode('en', None, None)),   # no region → None
        ('zh-Hans-CN', _LocaleCode('zh', 'CN', None)),  # script subtag dropped
        ('zh-Hans',    _LocaleCode('zh', None, None)),  # script-only, no region
        ('sr-Latn-RS', _LocaleCode('sr', 'RS', None)),  # script subtag dropped
        ('ar-001',     _LocaleCode('ar', '001', None)), # numeric region preserved in struct
    ])
    def test_from_bcp47(self, bcp47: str, expected: _LocaleCode) -> None:
        assert _LocaleCode.from_bcp47(bcp47) == expected

    @pytest.mark.parametrize('locale_str, expected', [
        ('en_US.UTF-8', _LocaleCode('en', 'US', 'UTF-8')),  # POSIX with encoding
        ('en_US',       _LocaleCode('en', 'US', None)),     # POSIX no encoding
        ('en-US',       _LocaleCode('en', 'US', None)),     # BCP47
        ('en',          _LocaleCode('en', None, None)),     # bare lang
        ('sr_RS@latin', _LocaleCode('sr', 'RS', None)),     # POSIX with @modifier
        ('de@euro',     _LocaleCode('de', None, None)),     # @-only routes to POSIX path
    ])
    def test_parse(self, locale_str: str, expected: _LocaleCode) -> None:
        assert _LocaleCode.parse(locale_str) == expected

    @pytest.mark.parametrize('lc, expected', [
        (_LocaleCode('en', 'US', 'UTF-8'), 'en_US.UTF-8'),
        (_LocaleCode('en', 'US', None),    'en_US'),
        (_LocaleCode('en', None, None),    'en'),
        (_LocaleCode('en', None, 'UTF-8'), 'en.UTF-8'),
        (_LocaleCode('ar', '001', None),   'ar'),        # numeric region dropped
    ])
    def test_to_posix(self, lc: _LocaleCode, expected: str) -> None:
        assert lc.to_posix == expected

    @pytest.mark.parametrize('lc, expected', [
        (_LocaleCode('en', 'US', 'UTF-8'), 'en-US'),
        (_LocaleCode('en', 'US', None),    'en-US'),
        (_LocaleCode('en', None, None),    'en'),
        (_LocaleCode('ar', '001', None),   'ar-001'),   # numeric region kept in BCP47
    ])
    def test_to_bcp47(self, lc: _LocaleCode, expected: str) -> None:
        assert lc.to_bcp47 == expected

    def test_strip_encoding(self) -> None:
        assert _LocaleCode('en', 'US', 'UTF-8').strip_encoding() == _LocaleCode('en', 'US', None)

    def test_strip_encoding_already_none(self) -> None:
        lc = _LocaleCode('en', 'US', None)
        assert lc.strip_encoding() == lc

    @pytest.mark.parametrize('invalid', [
        'I am a badger',
        '',
        '123',
        'en_US_extra_underscores',
        'toolonglanguage',
        'C',
        'POSIX',
    ])
    def test_parse_invalid_raises(self, invalid: str) -> None:
        with pytest.raises(ValueError):
            _LocaleCode.parse(invalid)


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
        """POSIX input (no encoding) passes through unchanged."""
        assert bcp47LangToPosixLocale(posix) == posix

    @pytest.mark.parametrize('posix_with_encoding', [
        'en_US.UTF-8',
        'fr_FR.utf-8',
    ])
    def test_posix_with_encoding_passes_through(self, posix_with_encoding: str) -> None:
        """POSIX locales with encoding pass through unchanged."""
        assert bcp47LangToPosixLocale(posix_with_encoding) == posix_with_encoding

    @pytest.mark.parametrize('with_script, expected', [
        ('zh-Hans-CN', 'zh_CN'),   # 4-alpha script subtag dropped
        ('sr-Latn-RS', 'sr_RS'),
        ('zh-Hans',    'zh'),      # script-only, no region
    ])
    def test_bcp47_script_subtag_dropped(self, with_script: str, expected: str) -> None:
        assert bcp47LangToPosixLocale(with_script) == expected

    @pytest.mark.parametrize('with_modifier, expected', [
        ('sr_RS@latin', 'sr_RS'),  # POSIX @modifier stripped
        ('de_AT@euro',  'de_AT'),
    ])
    def test_posix_modifier_stripped(self, with_modifier: str, expected: str) -> None:
        assert bcp47LangToPosixLocale(with_modifier) == expected

    @pytest.mark.parametrize('invalid', [
        'I am a badger',
        '',
        '123',
        'toolonglanguage-US',
    ])
    def test_invalid_input_falls_back_to_default(self, invalid: str) -> None:
        assert bcp47LangToPosixLocale(invalid) == 'en_GB'


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
        """BCP-47 input passes through unchanged."""
        assert posixLocaleToBCP47Lang(bcp47) == bcp47

    @pytest.mark.parametrize('with_script, expected', [
        ('zh-Hans-CN', 'zh-CN'),   # 4-alpha script subtag dropped
        ('sr-Latn-RS', 'sr-RS'),
        ('zh-Hans',    'zh'),      # script-only, no region
    ])
    def test_bcp47_script_subtag_dropped(self, with_script: str, expected: str) -> None:
        assert posixLocaleToBCP47Lang(with_script) == expected

    @pytest.mark.parametrize('with_modifier, expected', [
        ('sr_RS@latin', 'sr-RS'),  # POSIX @modifier stripped
        ('de_AT@euro',  'de-AT'),
    ])
    def test_posix_modifier_stripped(self, with_modifier: str, expected: str) -> None:
        assert posixLocaleToBCP47Lang(with_modifier) == expected

    @pytest.mark.parametrize('invalid', [
        'I am a badger',
        '',
        '123',
        'toolonglanguage-US',
    ])
    def test_invalid_input_falls_back_to_default(self, invalid: str) -> None:
        assert posixLocaleToBCP47Lang(invalid) == 'en-GB'


class TestCompatibleSystemLocales:
    def test_filters_by_language(self) -> None:
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('en', 'US', None), _LocaleCode('fr', 'FR', None), _LocaleCode('de', 'DE', None)})):
            result = _compatibleSystemLocales(_LocaleCode('en', 'US', None), exclude=set())
        assert result == [_LocaleCode('en', 'US', None)]

    def test_excludes_already_listed(self) -> None:
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('en', 'US', None), _LocaleCode('en', 'GB', None)})):
            result = _compatibleSystemLocales(_LocaleCode('en', 'US', None), exclude={_LocaleCode('en', 'US', None)})
        assert _LocaleCode('en', 'US', None) not in result
        assert _LocaleCode('en', 'GB', None) in result

    def test_matches_bare_language(self) -> None:
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('en', None, None), _LocaleCode('fr', None, None)})):
            result = _compatibleSystemLocales(_LocaleCode('en', None, None), exclude=set())
        assert result == [_LocaleCode('en', None, None)]

    def test_no_false_prefix_match(self) -> None:
        """'english' should not match language 'en' — parsed lang field must equal 'en' exactly."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('english', None, None), _LocaleCode('eno', None, None)})):
            result = _compatibleSystemLocales(_LocaleCode('en', None, None), exclude=set())
        assert result == []

    def test_language_prefix_does_not_match_longer_language_code(self) -> None:
        """'fi' (Finnish) must not match 'fil_PH' (Filipino) even though 'fil' starts with 'fi'."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('fi', 'FI', None), _LocaleCode('fil', 'PH', None)})):
            result = _compatibleSystemLocales(_LocaleCode('fi', 'FI', None), exclude=set())
        assert _LocaleCode('fil', 'PH', None) not in result
        assert _LocaleCode('fi', 'FI', None) in result

    def test_longer_language_code_does_not_match_prefix(self) -> None:
        """'fil' (Filipino) must not match 'fi_FI' (Finnish) even though 'fil' starts with 'fi'."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('fi', 'FI', None), _LocaleCode('fil', 'PH', None)})):
            result = _compatibleSystemLocales(_LocaleCode('fil', 'PH', None), exclude=set())
        assert _LocaleCode('fi', 'FI', None) not in result
        assert _LocaleCode('fil', 'PH', None) in result

    def test_sort_prefers_matching_region(self) -> None:
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('en', 'US', None), _LocaleCode('en', 'GB', None), _LocaleCode('en', 'AU', None)})):
            result = _compatibleSystemLocales(_LocaleCode('en', 'US', None), exclude=set())
        assert result[0] == _LocaleCode('en', 'US', None)

    def test_sort_prefers_matching_encoding(self) -> None:
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('en', 'US', 'UTF-8'), _LocaleCode('en', 'US', 'ISO-8859-1')})):
            result = _compatibleSystemLocales(_LocaleCode('en', 'US', 'UTF-8'), exclude=set())
        assert result[0] == _LocaleCode('en', 'US', 'UTF-8')

    def test_empty_system_locales(self) -> None:
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset()):
            result = _compatibleSystemLocales(_LocaleCode('en', 'US', None), exclude=set())
        assert result == []

    def test_bare_language_matches_all_regions(self) -> None:
        """Bare 'en' with no region matches en_US, en_GB, en_AU etc."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('en', 'US', None), _LocaleCode('en', 'GB', None), _LocaleCode('en', 'AU', None), _LocaleCode('fr', 'FR', None)})):
            result = _compatibleSystemLocales(_LocaleCode('en', None, None), exclude=set())
        assert set(result) == {_LocaleCode('en', 'US', None), _LocaleCode('en', 'GB', None), _LocaleCode('en', 'AU', None)}

    def test_bare_language_matches_encoding_variants(self) -> None:
        """Bare 'ja' matches ja_JP.UTF-8, ja_JP.eucJP etc."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('ja', 'JP', 'UTF-8'), _LocaleCode('ja', 'JP', 'eucJP'), _LocaleCode('en', 'US', None)})):
            result = _compatibleSystemLocales(_LocaleCode('ja', None, None), exclude=set())
        assert set(result) == {_LocaleCode('ja', 'JP', 'UTF-8'), _LocaleCode('ja', 'JP', 'eucJP')}

    def test_bare_language_with_encoding_dot_separator(self) -> None:
        """Bare 'en' matches en.UTF-8 (dot separator at lang_len)."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('en', None, 'UTF-8'), _LocaleCode('en', 'US', None)})):
            result = _compatibleSystemLocales(_LocaleCode('en', None, None), exclude=set())
        assert set(result) == {_LocaleCode('en', None, 'UTF-8'), _LocaleCode('en', 'US', None)}

    def test_sort_encoding_no_encoding_requested_prefers_no_encoding(self) -> None:
        """When no encoding requested, locales without encoding sort first."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('en', 'US', None), _LocaleCode('en', 'US', 'UTF-8'), _LocaleCode('en', 'US', 'ISO-8859-1')})):
            result = _compatibleSystemLocales(_LocaleCode('en', 'US', None), exclude=set())
        assert result[0] == _LocaleCode('en', 'US', None)

    def test_sort_non_utf8_encoding_requested(self) -> None:
        """When ISO-8859-1 is requested, that encoding sorts first."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('en', 'US', 'UTF-8'), _LocaleCode('en', 'US', 'ISO-8859-1')})):
            result = _compatibleSystemLocales(_LocaleCode('en', 'US', 'ISO-8859-1'), exclude=set())
        assert result[0] == _LocaleCode('en', 'US', 'ISO-8859-1')

    def test_all_encoding_variants_included(self) -> None:
        """All encoding variants of the language are included, not just the requested one."""
        system = frozenset({_LocaleCode('en', 'US', 'UTF-8'), _LocaleCode('en', 'US', 'ISO-8859-1'), _LocaleCode('en', 'US', 'eucJP')})
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=system):
            result = _compatibleSystemLocales(_LocaleCode('en', 'US', 'UTF-8'), exclude=set())
        assert set(result) == system

    def test_bare_language_sorts_before_regionalized_when_no_region(self) -> None:
        """When region=None, bare 'en' should sort before 'en_US' / 'en_GB'."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('en', None, None), _LocaleCode('en', 'US', None), _LocaleCode('en', 'GB', None)})):
            result = _compatibleSystemLocales(_LocaleCode('en', None, None), exclude=set())
        assert result[0] == _LocaleCode('en', None, None)


class TestCompatibleSystemLocalesIntegration:
    """Integration tests for _compatibleSystemLocales against the real system locale list.

    Unlike TestCompatibleSystemLocales, these tests do not mock _getSystemLocalesAsPosix,
    so they depend on specific locales being installed on the host. Individual tests are
    skipped when the required locales are absent.
    """

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> Generator:
        _getSystem_LocaleCodes.cache_clear()
        yield
        _getSystem_LocaleCodes.cache_clear()

    @pytest.mark.skipif(not _HAS_EN_US, reason="en_US locale not installed")
    def test_en_US_in_results(self) -> None:
        result = _compatibleSystemLocales(_LocaleCode('en', 'US', None), exclude=set())
        assert any(r.lang == 'en' and r.region == 'US' for r in result)
        assert result[0].lang == 'en' and result[0].region == 'US'
        assert all(r.lang == 'en' for r in result)

    @pytest.mark.skipif(not _HAS_EN_GB, reason="en_GB locale not installed")
    def test_arelle_default_locale_en_GB_in_results(self) -> None:
        result = _compatibleSystemLocales(_LocaleCode('en', 'GB', None), exclude=set())
        assert any(r.lang == 'en' and r.region == 'GB' for r in result)
        assert result[0].lang == 'en' and result[0].region == 'GB'
        assert all(r.lang == 'en' for r in result)

    @pytest.mark.skipif(not _HAS_FI or not _HAS_FIL, reason="fi and fil locales not installed")
    def test_fi_and_fil_do_not_cross_contaminate(self) -> None:
        """fi (Finnish) and fil (Filipino) are present on both Windows and Linux."""
        fi_result = _compatibleSystemLocales(_LocaleCode('fi', None, None), exclude=set())
        fil_result = _compatibleSystemLocales(_LocaleCode('fil', None, None), exclude=set())
        assert not any(r.lang == 'fil' for r in fi_result)
        assert not any(r.lang == 'fi' for r in fil_result)


class TestCandidate_LocaleCodes:
    def test_non_default_region_adds_default_variant(self) -> None:
        """en_US should produce en_GB since default_LocaleCodes['en'] == 'GB'."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset()):
            result = _candidatePosixLocales('en_US')
        assert 'en_GB' in result

    def test_non_default_encoding_adds_utf8_variant(self) -> None:
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset()):
            result = _candidatePosixLocales('en_US.ISO-8859-1')
        assert 'en_US.utf-8' in result

    def test_bare_language_no_region_variants(self) -> None:
        """Bare language 'en' has no region, so no region-swap candidates are generated."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset()):
            result = _candidatePosixLocales('en')
        # No computed candidates — region is None so the region != defaultRegion branch is skipped
        assert not any('_' in code for code in result)

    def test_unknown_language_with_region_does_not_produce_bare_lang_candidate(self) -> None:
        """A language absent from default_LocaleCodes should not generate a bare-lang candidate."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset()):
            result = _candidatePosixLocales('xx_YY')
        # defaultRegion is None for 'xx', so no region-swap candidate should appear
        assert 'xx' not in result

    def test_system_locales_come_after_computed(self) -> None:
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('en', 'AU', None)})):
            result = _candidatePosixLocales('en_US')
        # en_GB is the computed default-region variant, en_AU comes from system locales
        assert result.index('en_GB') < result.index('en_AU')

    def test_no_duplicates(self) -> None:
        """System locales that match a computed candidate should not appear twice."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset({_LocaleCode('en', 'GB', None), _LocaleCode('en', 'AU', None)})):
            result = _candidatePosixLocales('en_US')
        assert result.count('en_GB') == 1

    def test_bare_language_en(self) -> None:
        """Bare 'en' generates no computed candidates but picks up system locales."""
        system = frozenset({_LocaleCode('en', 'US', None), _LocaleCode('en', 'GB', None), _LocaleCode('en', 'AU', 'UTF-8'), _LocaleCode('fr', 'FR', None)})
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=system):
            result = _candidatePosixLocales('en')
        assert 'fr_FR' not in result
        assert set(result) == {'en_US', 'en_GB', 'en_AU.UTF-8'}

    def test_bare_language_ja(self) -> None:
        """Bare 'ja' picks up all ja_* system locales."""
        system = frozenset({_LocaleCode('ja', 'JP', 'UTF-8'), _LocaleCode('ja', 'JP', 'eucJP'), _LocaleCode('en', 'US', None)})
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=system):
            result = _candidatePosixLocales('ja')
        assert set(result) == {'ja_JP.UTF-8', 'ja_JP.eucJP'}

    def test_non_default_encoding_generates_utf8_and_default_region_variants(self) -> None:
        """en_US.ISO-8859-1 generates en_US.utf-8, en_GB.ISO-8859-1, and en_GB.utf-8."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset()):
            result = _candidatePosixLocales('en_US.ISO-8859-1')
        assert 'en_US.utf-8' in result
        assert 'en_GB.ISO-8859-1' in result
        assert 'en_GB.utf-8' in result

    def test_utf8_encoding_does_not_duplicate(self) -> None:
        """en_US.utf-8 is already the default encoding — no utf-8 variant generated."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset()):
            result = _candidatePosixLocales('en_US.utf-8')
        assert result.count('en_US.utf-8') == 0  # input itself is not in candidates
        # Only the default-region variant is generated
        assert 'en_GB.utf-8' in result

    def test_UTF8_case_insensitive(self) -> None:
        """en_US.UTF-8 (uppercase) is treated as default encoding."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset()):
            result = _candidatePosixLocales('en_US.UTF-8')
        # Should not generate en_US.utf-8 since UTF-8 is already the default
        assert 'en_US.utf-8' not in result
        assert 'en_GB.UTF-8' in result

    def test_default_region_no_extra_candidates(self) -> None:
        """en_GB is the default region for 'en' — no region-swap candidate generated."""
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=frozenset()):
            result = _candidatePosixLocales('en_GB')
        # region == defaultRegion, so no fallback to another region
        assert not any(code.startswith('en_') and 'GB' not in code for code in result)

    def test_system_encoding_variants_sorted_by_relevance(self) -> None:
        """System locales with matching encoding sort before non-matching."""
        system = frozenset({_LocaleCode('en', 'US', 'UTF-8'), _LocaleCode('en', 'US', 'ISO-8859-1'), _LocaleCode('en', 'US', 'eucJP')})
        system_posix = {lc.to_posix for lc in system}
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=system):
            result = _candidatePosixLocales('en_US.ISO-8859-1')
        # Computed candidates come first, then system locales
        # Among system locales, ISO-8859-1 would match but it's excluded (already computed as en_US.utf-8 variant)
        # en_US.ISO-8859-1 is the original input (not in candidates), but system has it
        system_portion = [c for c in result if c in system_posix]
        # The one matching the requested encoding should come first among system locales
        iso_idx = [i for i, c in enumerate(system_portion) if 'ISO-8859-1' in c]
        utf8_idx = [i for i, c in enumerate(system_portion) if 'UTF-8' in c]
        assert iso_idx[0] < utf8_idx[0]

    def test_language_prefix_does_not_include_longer_language_code(self) -> None:
        """Candidates for 'fi' (Finnish) must not include 'fil_PH' (Filipino) system locales."""
        system = frozenset({_LocaleCode('fi', 'FI', None), _LocaleCode('fil', 'PH', None)})
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=system):
            result = _candidatePosixLocales('fi_FI')
        assert 'fil_PH' not in result

    def test_longer_language_code_does_not_include_prefix_locales(self) -> None:
        """Candidates for 'fil' (Filipino) must not include 'fi_FI' (Finnish) system locales."""
        system = frozenset({_LocaleCode('fi', 'FI', None), _LocaleCode('fil', 'PH', None)})
        with patch.object(LocaleModule, '_getSystem_LocaleCodes', return_value=system):
            result = _candidatePosixLocales('fil_PH')
        assert 'fi_FI' not in result


_FAKE_CONV = {'decimal_point': '.'}


class TestFindCompatibleLocale:
    def test_none_returns_none(self) -> None:
        assert findCompatibleLocale(None) is None

    @pytest.mark.parametrize('pseudo', ['C', 'POSIX'])
    def test_pseudo_locale_returns_none(self, pseudo: str) -> None:
        assert findCompatibleLocale(pseudo) is None

    @pytest.mark.parametrize('invalid', ['I am a badger', '', '123'])
    def test_invalid_locale_returns_none(self, invalid: str) -> None:
        assert findCompatibleLocale(invalid) is None

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
            with patch.object(LocaleModule, '_candidatePosixLocales', return_value=['en_AU', 'en_GB', 'en_NZ']):
                result = findCompatibleLocale('en_US')
        assert result == 'en_GB'

    def test_no_working_locale_returns_none(self) -> None:
        """Returns None when neither the direct probe nor any candidate succeeds."""
        with patch.object(LocaleModule, '_probeLocale', return_value=None):
            with patch.object(LocaleModule, '_candidatePosixLocales', return_value=['en_GB', 'en_AU']):
                result = findCompatibleLocale('en_US')
        assert result is None

    def test_empty_candidates_returns_none(self) -> None:
        """Returns None when the direct probe fails and the candidate list is empty."""
        with patch.object(LocaleModule, '_probeLocale', return_value=None):
            with patch.object(LocaleModule, '_candidatePosixLocales', return_value=[]):
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

    @pytest.mark.parametrize('pseudo_locale', ['C', 'POSIX'])
    def test_pseudo_locale_returns_none(self, reset_locale, pseudo_locale: str) -> None:
        """C and POSIX pseudo-locales have no real language; getLocale should return None."""
        with patch.object(LocaleModule, '_getNativeLocale', return_value=None):
            with patch.object(LocaleModule.locale, 'setlocale', return_value=pseudo_locale):
                with patch.object(LocaleModule.locale, 'getlocale', return_value=(pseudo_locale, None)):
                    result = getLocale()
        assert result is None


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


class TestSystemLocalesPassValidation:
    """Every locale string reported by the platform should pass _LocaleCode.parse."""

    @pytest.mark.skipif(sys.platform != 'win32', reason='Windows only')
    def test_windows_locales_pass_parse(self) -> None:
        for loc in _enumerateWindowsLocales():
            try:
                _LocaleCode.parse(loc)
            except ValueError as e:
                pytest.fail(f"Windows locale {loc!r} failed parse: {e}")

    @pytest.mark.skipif(sys.platform == 'win32', reason='non-Windows only')
    def test_posix_system_locales_pass_parse(self) -> None:
        locales_output = tryRunCommand('locale', '-a')
        if locales_output is None:
            pytest.skip('locale -a unavailable')
        for loc in locales_output.splitlines():
            # C and POSIX pseudo-locales have no standard lang tag form.
            # @modifier locales (e.g. sr_RS@latin) are now handled by parse via
            # the POSIX_LOCALE regex which accepts the @modifier suffix.
            if not loc or loc in ('C', 'POSIX') or loc.startswith('C.'):
                continue
            try:
                _LocaleCode.parse(loc)
            except ValueError as e:
                pytest.fail(f"System locale {loc!r} failed parse: {e}")
