"""
This module is a local copy of python locale in order to allow
passing in localconv as an argument to functions without affecting
system-wide settings.  (The system settings can remain in 'C' locale.)

See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import ctypes
import locale
import sys
import unicodedata
from collections.abc import Callable, Generator, Iterator, Mapping
from decimal import Decimal
from functools import cache
from fractions import Fraction
from typing import Any, NamedTuple, cast

import regex as re

from arelle.PythonUtil import tryRunCommand
from arelle.typing import LocaleDict, TypeGetText

_: TypeGetText

CHAR_MAX = 127
LC_ALL = 6
LC_COLLATE = 3
LC_CTYPE = 0
LC_MESSAGES = 5
LC_MONETARY = 4
LC_NUMERIC = 1
LC_TIME = 2

defaultLocaleCodes = {
    "af": "ZA", "ar": "AE", "be": "BY", "bg": "BG", "ca": "ES", "cs": "CZ",
    "da": "DK", "de": "DE", "el": "GR", "en": "GB", "es": "ES", "et": "EE",
    "eu": "ES", "fa": "IR", "fi": "FI", "fo": "FO", "fr": "FR", "he": "IL",
    "hi": "IN", "hr": "HR", "hu": "HU", "id": "ID", "is": "IS", "it": "IT",
    "ja": "JP", "ko": "KR", "lt": "LT", "lv": "LV", "ms": "MY", "mt": "MT",
    "nl": "NL", "no": "NO", "pl": "PL", "pt": "PT", "ro": "RO", "ru": "RU",
    "sk": "SK", "sl": "SI", "sq": "AL", "sr": "RS", "sv": "SE", "th": "TH",
    "tr": "TR", "uk": "UA", "ur": "PK", "vi": "VN", "zh": "CN"}


BCP47_LANGUAGE_REGION_SEPARATOR = '-'
POSIX_LANGUAGE_REGION_SEPARATOR = '_'
POSIX_LOCALE_ENCODING_SEPARATOR = '.'
POSIX_LOCALE_DEFAULT_ENCODING = 'utf-8'
POSIX_PSEUDO_LOCALES = frozenset({'C', 'POSIX'})

BCP47_LANGUAGE_TAG_RE = re.compile(r"^[a-zA-Z]{2,8}(-[a-zA-Z0-9]{1,8})*$")
POSIX_LOCALENAME_RE = re.compile(r"^[a-zA-Z]{2,3}(_[a-zA-Z]{2})?(\.[a-zA-Z0-9-]+)?(@[a-zA-Z0-9]+)?$")


class _LocaleCode(NamedTuple):
    """Structured representation of a locale code that can be expressed in both POSIX and BCP47 formats.

    Only locale codes meaningful in both formats are supported — pseudo-locales ('C', 'POSIX'),
    UN M.49 numeric regions, and other platform-specific variants are rejected or normalised at
    parse time.

    Choosing a constructor:
    - Use `parse` when the input format is unknown or comes from user/config/OS — it validates,
      detects format automatically, and rejects pseudo-locales and garbage.
    - Use `from_posix` or `from_bcp47` only when you already know the format with certainty
      (e.g. constructing from a value you just built, or from a source whose format is fixed).
      These do no validation and will silently produce nonsensical objects from bad input.
    """

    lang: str
    region: str | None
    encoding: str | None

    @classmethod
    def from_posix(cls, posixLocale: str) -> _LocaleCode:
        """Parse a known-POSIX locale string (e.g. 'en_US.UTF-8', 'sr_RS@latin') without validation.

        @modifier suffixes (script/currency indicators) are stripped. Use `parse` instead if the
        input is untrusted or its format is not guaranteed.
        """
        # Strip @modifier (script indicator like @latin, or currency like @euro).
        posixLocale = posixLocale.partition('@')[0]
        lang_region, _, encoding = posixLocale.partition(POSIX_LOCALE_ENCODING_SEPARATOR)
        lang, _, region = lang_region.partition(POSIX_LANGUAGE_REGION_SEPARATOR)
        return cls(lang=lang, region=region or None, encoding=encoding or None)

    @classmethod
    def from_bcp47(cls, bcp47Lang: str) -> _LocaleCode:
        """Parse a known-BCP47 language tag (e.g. 'en-US', 'zh-Hans-CN') without validation.

        4-alpha ISO 15924 script subtags (e.g. 'Hans', 'Latn') are detected and skipped so that
        the following subtag is treated as the region. Use `parse` instead if the input is
        untrusted or its format is not guaranteed.
        """
        subtags = iter(bcp47Lang.split(BCP47_LANGUAGE_REGION_SEPARATOR))
        lang = next(subtags)
        # Second subtag is script (4-alpha, ISO 15924 e.g. 'Hans') or region — skip script to reach region.
        subtag = next(subtags, None)
        if subtag and len(subtag) == 4 and subtag.isalpha():
            subtag = next(subtags, None)
        return cls(lang=lang, region=subtag, encoding=None)

    @classmethod
    def parse(cls, localeStr: str, fallbackToDefaultLocale: bool = False) -> _LocaleCode:
        """Parse a locale string of unknown format, detecting POSIX or BCP47 automatically.

        Rejects pseudo-locales ('C', 'POSIX'), validates against format regexes, and raises
        ValueError for anything unrecognised. Pass fallbackToDefaultLocale=True to return the
        Arelle default locale instead of raising — useful for public API callers that should
        degrade gracefully rather than surface errors.
        """
        if localeStr not in POSIX_PSEUDO_LOCALES:
            if BCP47_LANGUAGE_TAG_RE.match(localeStr):
                return cls.from_bcp47(localeStr)
            if POSIX_LOCALENAME_RE.match(localeStr):
                return cls.from_posix(localeStr)
        if fallbackToDefaultLocale:
            return _defaultLocaleCode()
        raise ValueError(f"Invalid locale: {localeStr!r}")

    @property
    def to_posix(self) -> str:
        """Render as a POSIX locale string (e.g. 'en_US', 'en_US.UTF-8').

        Regions that are not ISO 3166-1 alpha-2 (e.g. UN M.49 numeric codes) are silently
        dropped, since POSIX does not support them.
        """
        result = self.lang
        # Only alpha-2 regions (ISO 3166-1) are valid in POSIX; drop UN M.49 numerics etc.
        if self.region and len(self.region) == 2 and self.region.isalpha():
            result += POSIX_LANGUAGE_REGION_SEPARATOR + self.region
        if self.encoding:
            result += POSIX_LOCALE_ENCODING_SEPARATOR + self.encoding
        return result

    @property
    def to_bcp47(self) -> str:
        """Render as a BCP47 language tag (e.g. 'en-US', 'en'). Encoding is always omitted."""
        if self.region:
            return self.lang + BCP47_LANGUAGE_REGION_SEPARATOR + self.region
        return self.lang

    def strip_encoding(self) -> _LocaleCode:
        """Return a copy with encoding set to None."""
        return self._replace(encoding=None)


@cache
def _defaultLocaleCode() -> _LocaleCode:
    from arelle.XbrlConst import defaultLocale
    return _LocaleCode.from_bcp47(defaultLocale)


@cache
def _probeLocale(localeStr: str) -> LocaleDict | None:
    """
    Try to activate localeStr and return its localeconv dict.
    Returns None if the locale is not available on this system.
    Result is cached — setlocale is only called once per unique localeStr.
    Not thread-safe (Python's locale module uses global C state).
    """
    saved = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, localeStr)
        return cast(LocaleDict, locale.localeconv())
    except locale.Error:
        return None
    finally:
        locale.setlocale(locale.LC_ALL, saved)


def getUserLocale(posixLocale: str | None = None) -> tuple[LocaleDict, str | None]:
    """
    Get locale conventions dictionary.
    :param posixLocale: The locale code to use to retrieve conventions. Defaults to system default.
    :return: Tuple of (locale conventions dict, optional error message for the user)
    """
    localeStr = posixLocale or ''
    if (conv := _probeLocale(localeStr)) is not None:
        return conv, None
    # Locale not available — fall back to C and report it
    return cast(LocaleDict, _probeLocale('C') or locale.localeconv()), \
        _('Locale code "{}" is not available on this system.').format(posixLocale)


def getLanguageCode() -> str:
    if posixLocale := getLocale():
        return _LocaleCode.from_posix(posixLocale).to_bcp47
    return _defaultLocaleCode().to_bcp47


def getLanguageCodes(configLang: str | None = None) -> list[str]:
    """
    Returns a list of language code formats that can be used with gettext to look up translation files.
    configLang is user specified and may be in the BCP 47 format (en-US) or POSIX locale (en_US.utf-8).
    The translation files can also be user generated and in any of these formats.
    We do our best to work with both formats.
    [en_US, en-US, en]
    [fr]
    """
    lc = _LocaleCode.parse(configLang or getLanguageCode()).strip_encoding()
    if lc.region:
        return [lc.to_posix, lc.to_bcp47, lc.lang]
    if defaultRegion := defaultLocaleCodes.get(lc.lang):
        default_lc = _LocaleCode(lc.lang, defaultRegion, None)
        return [lc.lang, default_lc.to_posix, default_lc.to_bcp47]
    return [lc.lang]


def findCompatibleLocale(localeValue: str | None) -> str | None:
    """
    Attempts to find a system-compatible locale based on the provided value.
    Checks default regions and possible encodings.

    :param localeValue: Locale string in BCP-47 format (e.g. ``'en-US'``) or POSIX format (e.g. ``'en_US.utf-8'``).
    :return: A POSIX-style locale string that can be passed to ``setlocale``, or ``None`` if no compatible locale is found.
    """
    if localeValue is None:
        return None
    try:
        posixLocale = _LocaleCode.parse(localeValue).to_posix
    except ValueError:
        return None
    if _probeLocale(posixLocale) is not None:
        return posixLocale
    for candidate in _candidatePosixLocales(posixLocale):
        if _probeLocale(candidate) is not None:
            return candidate
    return None


def _candidatePosixLocales(posixLocale: str) -> Iterator[str]:
    """
    Yields additional candidate POSIX locales to try when the requested locale is unavailable.
    Yields default-encoding and default-region variants first, then compatible system locales.
    """
    lc = _LocaleCode.from_posix(posixLocale)
    defaultRegion = defaultLocaleCodes.get(lc.lang)
    not_default_encoding = lc.encoding is not None and lc.encoding.lower() != POSIX_LOCALE_DEFAULT_ENCODING

    primary: list[_LocaleCode] = []
    if not_default_encoding:
        primary.append(lc._replace(encoding=POSIX_LOCALE_DEFAULT_ENCODING))
    if lc.region and defaultRegion and lc.region != defaultRegion:
        primary.append(lc._replace(region=defaultRegion))
        if not_default_encoding:
            primary.append(lc._replace(region=defaultRegion, encoding=POSIX_LOCALE_DEFAULT_ENCODING))
    yield from (c.to_posix for c in primary)
    yield from (c.to_posix for c in _compatibleSystemLocales(lc, exclude=set(primary)))


def _compatibleSystemLocales(lc: _LocaleCode, exclude: set[_LocaleCode]) -> list[_LocaleCode]:
    """
    Returns system locales matching the given language, sorted by relevance.
    Excludes any locales already in the ``exclude`` set.

    :param lc: Locale to match against.
    :param exclude: Locale codes to skip (already-generated candidates).
    :return: Sorted list of compatible locale codes.
    """
    matches: set[_LocaleCode] = {
        lc_sys
        for lc_sys in _getSystem_LocaleCodes()
        if lc_sys not in exclude and lc_sys.lang == lc.lang
    }

    def _sortKey(candidate: _LocaleCode) -> tuple[bool, bool, str]:
        region_match = lc.region is None or candidate.region == lc.region
        encoding_match = (candidate.encoding is None and lc.encoding is None) or \
                     (candidate.encoding == (lc.encoding or POSIX_LOCALE_DEFAULT_ENCODING))
        return (not region_match, not encoding_match, candidate.to_posix)

    return sorted(matches, key=_sortKey)


def bcp47LangToPosixLocale(bcp47Lang: str) -> str:
    """
    Normalise a locale string to POSIX format (en_US). Accepts BCP47 (en-US) or POSIX (en_US.utf-8).
    Unrecognised strings fall back to the Arelle default locale.
    """
    return _LocaleCode.parse(bcp47Lang, fallbackToDefaultLocale=True).to_posix


def posixLocaleToBCP47Lang(posixLocale: str) -> str:
    """
    Normalise a locale string to BCP47 format (en-US). Accepts POSIX (en_US.utf-8) or BCP47 (en-US).
    Unrecognised strings fall back to the Arelle default locale.
    """
    return _LocaleCode.parse(posixLocale, fallbackToDefaultLocale=True).to_bcp47


def _getNativeLocale() -> str | None:
    """
    Returns the user's locale from the platform-native API, or None if unavailable.
    On Windows this is a BCP-47 tag (e.g. 'en-GB') from GetUserDefaultLocaleName.
    On macOS this is the AppleLocale value (e.g. 'en_AU') from defaults.
    On other platforms returns None (no native API).
    """
    if sys.platform == "darwin":
        return tryRunCommand("defaults", "read", "-g", "AppleLocale")
    elif sys.platform == "win32":
        # https://learn.microsoft.com/en-us/windows/win32/api/winnls/nf-winnls-getuserdefaultlocalename
        # https://learn.microsoft.com/en-us/windows/win32/intl/locale-name-constants
        LOCALE_NAME_MAX_LENGTH = 85
        buf = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
        if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, LOCALE_NAME_MAX_LENGTH):
            return buf.value
    return None


@cache
def getLocale() -> str | None:
    """
    Returns the user's locale as a POSIX locale string without encoding (e.g. 'en_US', 'fr_FR').
    The result is cached after the first call.
    """
    if pythonCompatibleLocale := findCompatibleLocale(_getNativeLocale()):
        return pythonCompatibleLocale

    if sys.version_info < (3, 12) or (3, 13, 3) <= sys.version_info[:3] <= (3, 13, 4):
        # Using locale.setlocale(...) because getlocale() in Python versions prior to 3.12 incorrectly aliased C.UTF-8 to en_US.UTF-8.
        # https://github.com/python/cpython/issues/74940
        # Similar bug was reintroduced in Python 3.13.3 and fixed in 3.13.5.
        # https://github.com/python/cpython/pull/135347
        result: str | None = locale.setlocale(locale.LC_CTYPE).partition(POSIX_LOCALE_ENCODING_SEPARATOR)[0]
    else:
        result = locale.getlocale()[0]

    # C and POSIX are pseudo-locales with no real language; treat as unset.
    return result if result and result not in POSIX_PSEUDO_LOCALES else None


iso3region = {
"AU": "aus",
"AT": "aut",
"BE": "bel",
"BR": "bra",
"CA": "can",
"CN": "chn",
"CZ": "cze",
"DA": "dnk",
"FN": "fin",
"FR": "fra",
"DE": "deu",
"GR": "grc",
"HK": "hkg",
"HU": "hun",
"IS": "isl",
"IE": "irl",
"IT": "ita",
"JA": "jpn",
"KO": "kor",
"MX": "mex",
"NL": "nld",
"NZ": "nzl",
"NO": "nor",
"PL": "pol",
"PT": "prt",
"RU": "rus",
"SG": "sgp",
"SL": "svk",
"ES": "esp",
"SV": "swe",
"CH": "che",
"TW": "twn",
"TR": "tur",
"UK": "gbr",
"US": "usa"}


def _enumerateWindowsLocales() -> list[str]:
    """
    Enumerate system locale names on Windows using EnumSystemLocalesEx.
    Returns a list of BCP-47 locale name strings (e.g. 'en-US', 'fr-FR').
    Returns an empty list if the call fails.
    """
    if sys.platform != "win32":
        # keep the type checkers happy
        return []

    # https://learn.microsoft.com/en-us/windows/win32/api/winnls/nf-winnls-enumsystemlocalesex
    # https://learn.microsoft.com/en-us/windows/win32/api/winnls/nc-winnls-locale_enumprocex
    # LOCALE_WINDOWS: Enumerate all locales that come with the operating system, including replacement locales, but excluding alternate sorts.
    LOCALE_WINDOWS = 0x00000001
    # LOCALE_SUPPLEMENTAL: Enumerate supplemental locales. https://learn.microsoft.com/en-us/windows/win32/intl/custom-locales
    LOCALE_SUPPLEMENTAL = 0x00000002
    # LOCALE_SPECIFICDATA: Locale data specified by both language and country/region.
    LOCALE_SPECIFICDATA = 0x00000020
    _LOCALE_ENUMPROCEX = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_void_p)
    locales: list[str] = []

    def _callback(localeName: str | None, _flags: int, _param: int) -> int:
        if localeName:
            locales.append(localeName)
        return 1 # TRUE to continue enumeration

    try:
        ctypes.windll.kernel32.EnumSystemLocalesEx(
            _LOCALE_ENUMPROCEX(_callback),
            LOCALE_WINDOWS | LOCALE_SUPPLEMENTAL | LOCALE_SPECIFICDATA,
            0, None,
        )
    except (OSError, AttributeError):
        return []
    return locales


@cache
def _getSystem_LocaleCodes() -> frozenset[_LocaleCode]:
    """
    Returns a cached set of system locale codes.
    """
    if sys.platform == "win32":
        return frozenset(
            _LocaleCode.from_bcp47(loc)
            for loc in _enumerateWindowsLocales()
        )
    elif locales := tryRunCommand("locale", "-a"):
        return frozenset(
            _LocaleCode.from_posix(loc)
            for loc in locales.splitlines()
            # Skip C/POSIX pseudo-locales; @modifier variants (e.g. sr_RS@latin,
            # de_AT@euro) are handled by from_posix stripping the modifier.
            if loc and loc not in POSIX_PSEUDO_LOCALES and not loc.startswith('C.')
        )
    return frozenset()


def getLocaleList() -> list[str]:
    """
    Returns a list of available system locale codes in POSIX format (e.g. 'en_US', 'fr_FR').
    """
    return sorted(lc.to_posix for lc in _getSystem_LocaleCodes())


@cache
def availableLocales() -> frozenset[str]:
    """
    Returns a set of available system languages (POSIX format without encoding).
    """
    return frozenset(lc.strip_encoding().to_posix for lc in _getSystem_LocaleCodes())


@cache
def availableBCP47LangTags() -> frozenset[str]:
    """
    Returns a set of available system languages (BCP-47 format).
    """
    return frozenset(lc.to_bcp47 for lc in _getSystem_LocaleCodes())


_languageCodes: dict[str, str] | None = None


def languageCodes() -> dict[str, str]:
    """Return a mapping of English language names to BCP47 tags (e.g. 'English (United Kingdom)' → 'en-GB')."""
    global _languageCodes
    if _languageCodes is not None:
        return _languageCodes
    else:
        _languageCodes = { # language name (in English) and lang code
            _("Afrikaans (South Africa)"): "af-ZA",
            _("Albanian (Albania)"): "sq-AL",
            _("Arabic (Algeria)"): "ar-DZ",
            _("Arabic (Bahrain)"): "ar-BH",
            _("Arabic (Egypt)"): "ar-EG",
            _("Arabic (Iraq)"): "ar-IQ",
            _("Arabic (Jordan)"): "ar-JO",
            _("Arabic (Kuwait)"): "ar-KW",
            _("Arabic (Lebanon)"): "ar-LB",
            _("Arabic (Libya)"): "ar-LY",
            _("Arabic (Morocco)"): "ar-MA",
            _("Arabic (Oman)"): "ar-OM",
            _("Arabic (Qatar)"): "ar-QA",
            _("Arabic (Saudi Arabia)"): "ar-SA",
            _("Arabic (Syria)"): "ar-SY",
            _("Arabic (Tunisia)"): "ar-TN",
            _("Arabic (U.A.E.)"): "ar-AE",
            _("Arabic (Yemen)"): "ar-YE",
            _("Basque (Spain)"): "eu-ES",
            _("Bulgarian (Bulgaria)"): "bg-BG",
            _("Belarusian (Belarus)"): "be-BY",
            _("Catalan (Spain)"): "ca-ES",
            _("Chinese (PRC)"): "zh-CN",
            _("Chinese (Taiwan)"): "zh-TW",
            _("Chinese (Singapore)"): "zh-SG",
            _("Croatian (Croatia)"): "hr-HR",
            _("Czech (Czech Republic)"): "cs-CZ",
            _("Danish (Denmark)"): "da-DK",
            _("Dutch (Belgium)"): "nl-BE",
            _("Dutch (Netherlands)"): "nl-NL",
            _("English (Australia)"): "en-AU",
            _("English (Belize)"): "en-BZ",
            _("English (Canada)"): "en-CA",
            _("English (Caribbean)"): "en-029", #en-CB does not work with windows or linux
            _("English (Ireland)"): "en-IE",
            _("English (Jamaica)"): "en-JM",
            _("English (New Zealand)"): "en-NZ",
            _("English (South Africa)"): "en-ZA",
            _("English (Trinidad)"): "en-TT",
            _("English (United States)"): "en-US",
            _("English (United Kingdom)"): "en-GB",
            _("Estonian (Estonia)"): "et-EE",
            _("Faeroese (Faroe Islands)"): "fo-FO",
            _("Farsi (Iran)"): "fa-IR",
            _("Finnish (Finland)"): "fi-FI",
            _("French (Belgium)"): "fr-BE",
            _("French (Canada)"): "fr-CA",
            _("French (France)"): "fr-FR",
            _("French (Luxembourg)"): "fr-LU",
            _("French (Switzerland)"): "fr-CH",
            _("German (Austria)"): "de-AT",
            _("German (Germany)"): "de-DE",
            _("German (Luxembourg)"): "de-LU",
            _("German (Switzerland)"): "de-CH",
            _("Greek (Greece)"): "el-GR",
            _("Hebrew (Israel)"): "he-IL",
            _("Hindi (India)"): "hi-IN",
            _("Hungarian (Hungary)"): "hu-HU",
            _("Icelandic (Iceland)"): "is-IS",
            _("Indonesian (Indonesia)"): "id-ID",
            _("Italian (Italy)"): "it-IT",
            _("Italian (Switzerland)"): "it-CH",
            _("Japanese (Japan)"): "ja-JP",
            _("Korean (Korea)"): "ko-KR",
            _("Latvian (Latvia)"): "lv-LV",
            _("Lithuanian (Lituania)"): "lt-LT",
            _("Malaysian (Malaysia)"): "ms-MY",
            _("Maltese (Malta)"): "mt-MT",
            _("Norwegian (Bokmal)"): "no-NO",
            _("Norwegian (Nynorsk)"): "no-NO",
            _("Persian (Iran)"): "fa-IR",
            _("Polish (Poland)"): "pl-PL",
            _("Portuguese (Brazil)"): "pt-BR",
            _("Portuguese (Portugal)"): "pt-PT",
            _("Romanian (Romania)"): "ro-RO",
            _("Russian (Russia)"): "ru-RU",
            _("Serbian (Cyrillic)"): "sr-RS",
            _("Serbian (Latin)"): "sr-RS",
            _("Slovak (Slovakia)"): "sk-SK",
            _("Slovenian (Slovania)"): "sl-SI",
            _("Spanish (Argentina)"): "es-AR",
            _("Spanish (Bolivia)"): "es-BO",
            _("Spanish (Colombia)"): "es-CO",
            _("Spanish (Chile)"): "es-CL",
            _("Spanish (Costa Rica)"): "es-CR",
            _("Spanish (Dominican Republic)"): "es-DO",
            _("Spanish (Ecuador)"): "es-EC",
            _("Spanish (El Salvador)"): "es-SV",
            _("Spanish (Guatemala)"): "es-GT",
            _("Spanish (Honduras)"): "es-HN",
            _("Spanish (Mexico)"): "es-MX",
            _("Spanish (Nicaragua)"): "es-NI",
            _("Spanish (Panama)"): "es-PA",
            _("Spanish (Paraguay)"): "es-PY",
            _("Spanish (Peru)"): "es-PE",
            _("Spanish (Puerto Rico)"): "es-PR",
            _("Spanish (Spain)"): "es-ES",
            _("Spanish (United States)"): "es-US",
            _("Spanish (Uruguay)"): "es-UY",
            _("Spanish (Venezuela)"): "es-VE",
            _("Swedish (Sweden)"): "sv-SE",
            _("Swedish (Finland)"): "sv-FI",
            _("Thai (Thailand)"): "th-TH",
            _("Turkish (Turkey)"): "tr-TR",
            _("Ukrainian (Ukraine)"): "uk-UA",
            _("Urdu (Pakistan)"): "ur-PK",
            _("Vietnamese (Vietnam)"): "vi-VN",
        }
        return _languageCodes


def setApplicationLocale() -> None:
    """
    Sets the locale to C, to be used when running Arelle as a standalone application
    (e.g., `arelleCmdLine`, `arelleGUI`.)
    :return:
    """
    locale.setlocale(locale.LC_ALL, 'C')


_disableRTL: bool = False  # disable for implementations where tkinter supports rtl


def setDisableRTL(disableRTL: bool) -> None:
    global _disableRTL
    _disableRTL = disableRTL


def rtlString(source: str, lang: str | None) -> str:
    if lang and source and lang[0:2] in {"ar","he"} and not _disableRTL:
        line: list[str] = []
        lineInsertion = 0
        words: list[str] = []
        rtl = True
        for c in source:
            bidi = unicodedata.bidirectional(c)
            if rtl:
                if bidi == 'L':
                    if words:
                        line.insert(lineInsertion, ''.join(words))
                        words = []
                    rtl = False
                elif bidi in ('R', 'NSM', 'AN'):
                    pass
                else:
                    if words:
                        line.insert(lineInsertion, ''.join(words))
                        words = []
                    line.insert(lineInsertion, c)
                    continue
            else:
                if bidi == 'R' or bidi == 'AN':
                    if words:
                        line.append(''.join(words))
                        words = []
                    rtl = True
            words.append(c)
        if words:
            if rtl:
                line.insert(0, ''.join(words))
        return ''.join(line)
    else:
        return source


# Iterate over grouping intervals
def _grouping_intervals(grouping: list[int]) -> Generator[int, None, None]:
    last_interval = 3 # added to prevent compile error but not necessary semantically
    for interval in grouping:
        # if grouping is -1, we are done
        if interval == CHAR_MAX:
            return
        # 0: re-use last group ad infinitum
        if interval == 0:
            while True:
                yield last_interval
        yield interval
        last_interval = interval


# perform the grouping from right to left
def _group(conv: LocaleDict, s: str, monetary: bool = False) -> tuple[str, int]:
    thousands_sep = conv[monetary and 'mon_thousands_sep' or 'thousands_sep']
    grouping = conv[monetary and 'mon_grouping' or 'grouping']
    if not grouping:
        return (s, 0)
    result = ""
    seps = 0
    if s[-1] == ' ':
        stripped = s.rstrip()
        right_spaces = s[len(stripped):]
        s = stripped
    else:
        right_spaces = ''
    left_spaces = ''
    groups = []
    for interval in _grouping_intervals(grouping):
        if not s or s[-1] not in "0123456789":
            # only non-digit characters remain (sign, spaces)
            left_spaces = s
            s = ''
            break
        groups.append(s[-interval:])
        s = s[:-interval]
    if s:
        groups.append(s)
    groups.reverse()
    return (
        left_spaces + thousands_sep.join(groups) + right_spaces,
        len(thousands_sep) * (len(groups) - 1)
    )


# Strip a given amount of excess padding from the given string
def _strip_padding(s: str, amount: int) -> str:
    lpos = 0
    while amount and s[lpos] == ' ':
        lpos += 1
        amount -= 1
    rpos = len(s) - 1
    while amount and s[rpos] == ' ':
        rpos -= 1
        amount -= 1
    return s[lpos:rpos+1]


_percent_re = re.compile(r'%(?:\((?P<key>.*?)\))?'
                         r'(?P<modifiers>[-#0-9 +*.hlL]*?)[eEfFgGdiouxXcrs%]')


def format(
    conv: LocaleDict,
    percent: str,
    value: Any, # this can be a Mapping, tuple, str, float ... anything that can appear in "{}".format(<value>)
    grouping: bool = False,
    monetary: bool = False,
    *additional: str
) -> str:
    """Returns the locale-aware substitution of a %? specifier
    (percent).

    additional is for format strings which contain one or more
    '*' modifiers."""
    # this is only for one-percent-specifier strings and this should be checked
    if not percent.startswith("{"):
        match = _percent_re.match(percent)
        if not match or len(match.group())!= len(percent):
            raise ValueError(("format() must be given exactly one %%char "
                             "format specifier, %s not valid") % repr(percent))
    return _format(conv, percent, value, grouping, monetary, *additional)


def _format(
    conv: LocaleDict,
    percent: str,
    value: Any, # this can be a Mapping, tuple, str, float ... anything that can appear in "{}".format(<value>)
    grouping: bool = False,
    monetary: bool = False,
    *additional: str
) -> str:
    if percent.startswith("{"): # new formatting {:.{}f}
        formattype = percent[-2]
        if additional:
            formatted = percent.format(*((value,) + additional))
        else:
            formatted = percent.format(*value if isinstance(value,tuple) else value)
    else: # percent formatting %.*f
        formattype = percent[-1]
        if additional:
            formatted = percent % ((value,) + additional)
        else:
            formatted = percent % value
    # floats and decimal ints need special action!
    if formattype in 'eEfFgG':
        seps = 0
        parts = formatted.split('.')
        if grouping:
            parts[0], seps = _group(conv, parts[0], monetary=monetary)
        decimal_point = conv[monetary and 'mon_decimal_point' or 'decimal_point']
        formatted = decimal_point.join(parts)
        if seps:
            formatted = _strip_padding(formatted, seps)
    elif formattype in 'diu':
        seps = 0
        if grouping:
            formatted, seps = _group(conv, formatted, monetary=monetary)
        if seps:
            formatted = _strip_padding(formatted, seps)
    return formatted


def format_string(
    conv: LocaleDict,
    f: str,
    val: Any, # this can be a Mapping, tuple, str, float ... anything that can appear in "{}".format(<val>)
    grouping: bool = False
) -> str:
    """Formats a string in the same way that the % formatting would use,
    but takes the current locale into account.
    Grouping is applied if the third parameter is true."""
    percents = list(_percent_re.finditer(f))
    new_f = _percent_re.sub('%s', f)

    if isinstance(val, Mapping):
        new_val = []
        for perc in percents:
            if perc.group()[-1]=='%':
                new_val.append('%')
            else:
                new_val.append(format(conv, perc.group(), val, grouping))
    else:
        if not isinstance(val, tuple):
            val = (val,)
        new_val = []
        i = 0
        for perc in percents:
            if perc.group()[-1]=='%':
                new_val.append('%')
            else:
                starcount = perc.group('modifiers').count('*')
                new_val.append(_format(conv,
                                       perc.group(),
                                       val[i],
                                       grouping,
                                       False,
                                       *val[i+1:i+1+starcount]))
                i += (1 + starcount)
    val = tuple(new_val)

    return cast(str, new_f % val)


def currency(
    conv: LocaleDict,
    val: int | float,
    symbol: bool = True,
    grouping: bool = False,
    international: bool = False
) -> str:
    """Formats val according to the currency settings
    in the current locale."""

    # check for illegal values
    digits = conv[international and 'int_frac_digits' or 'frac_digits']
    if digits == 127:
        raise ValueError("Currency formatting is not possible using "
                         "the 'C' locale.")

    s = format(conv, '%%.%if' % digits, abs(val), grouping, monetary=True)
    # '<' and '>' are markers if the sign must be inserted between symbol and value
    s = '<' + s + '>'

    if symbol:
        smb = conv[international and 'int_curr_symbol' or 'currency_symbol']
        precedes = conv[val<0 and 'n_cs_precedes' or 'p_cs_precedes']
        separated = conv[val<0 and 'n_sep_by_space' or 'p_sep_by_space']

        if precedes:
            s = smb + (separated and ' ' or '') + s
        else:
            s = s + (separated and ' ' or '') + smb

    sign_pos = conv[val<0 and 'n_sign_posn' or 'p_sign_posn']
    sign = conv[val<0 and 'negative_sign' or 'positive_sign']

    if sign_pos == 0:
        s = '(' + s + ')'
    elif sign_pos == 1:
        s = sign + s
    elif sign_pos == 2:
        s = s + sign
    elif sign_pos == 3:
        s = s.replace('<', sign)
    elif sign_pos == 4:
        s = s.replace('>', sign)
    else:
        # the default if nothing specified;
        # this should be the most fitting sign position
        s = sign + s

    return s.replace('<', '').replace('>', '')


def ftostr(conv: LocaleDict, val: Any) -> str:
    """Convert float to integer, taking the locale into account."""
    return format(conv, "%.12g", val)


def atof(conv: LocaleDict, string: str, func: Callable[[str], Any] = float) -> Any:  # return type depends on func param, it is used to return float, int, and str
    "Parses a string as a float according to the locale settings."
    #First, get rid of the grouping
    ts = conv['thousands_sep']
    if ts:
        string = string.replace(ts, '')
    #next, replace the decimal point with a dot
    dd = conv['decimal_point']
    if dd:
        string = string.replace(dd, '.')
    #finally, parse the string
    return func(string)


def atoi(conv: LocaleDict, str: str) -> int:
    "Converts a string to an integer according to the locale settings."
    return cast(int, atof(conv, str, int))


def format_picture(conv: LocaleDict, value: Any, picture: str) -> str:
    monetary = False
    decimal_point = conv['decimal_point']
    thousands_sep = conv[monetary and 'mon_thousands_sep' or 'thousands_sep']
    percent = '%'
    per_mille = '\u2030'
    minus_sign = '-'
    #grouping = conv[monetary and 'mon_grouping' or 'grouping']

    if isinstance(value, float):
        value = Decimal.from_float(value)
    elif isinstance(value, (str, int)):
        value = Decimal(value)
    elif isinstance(value, Fraction):
        value = Decimal(float(value))
    elif not isinstance(value, Decimal):
        raise ValueError(_('Picture requires a number convertible to decimal or float').format(picture))

    if value.is_nan():
        return 'NaN'

    isNegative = value.is_signed()

    pic, sep, negPic = picture.partition(';')
    if negPic and ';' in negPic:
        raise ValueError(_('Picture contains multiple picture separators {0}').format(picture))
    if isNegative and negPic:
        pic = negPic

    if len([c for c in pic if c in (percent, per_mille) ]) > 1:
        raise ValueError(_('Picture contains multiple percent or per_mille characters {0}').format(picture))
    if percent in pic:
        value *= 100
    elif per_mille in pic:
        value *= 1000

    intPart, sep, fractPart = pic.partition(decimal_point)
    prefix = ''
    numPlaces = 0
    intPlaces = 0
    grouping = 0
    fractPlaces = 0
    suffix = ''
    if fractPart:
        if decimal_point in fractPart:
            raise ValueError(_('Sub-picture contains decimal point separators {0}').format(pic))

        for c in fractPart:
            if c.isdecimal():
                numPlaces += 1
                fractPlaces += 1
                if suffix:
                    raise ValueError(_('Sub-picture passive character {0} between active characters {1}').format(c, fractPart))
            else:
                suffix += c

    intPosition = 0
    for c in reversed(intPart):
        if c.isdecimal() or c == '#' or c == thousands_sep:
            if prefix:
                raise ValueError(_('Sub-picture passive character {0} between active characters {1}').format(c, intPart))
        if c.isdecimal():
            numPlaces += 1
            intPlaces += 1
            intPosition += 1
            prefix = ''
        elif c == '#':
            numPlaces += 1
            intPosition += 1
        elif c == thousands_sep:
            if not grouping:
                grouping = intPosition
        else:
            prefix = c + prefix

    if not numPlaces and prefix != minus_sign:
            raise ValueError(_('Sub-picture must contain at least one digit position or sign character {0}').format(pic))
    if intPlaces == 0 and fractPlaces == 0:
        intPlaces = 1

    return format_decimal(None, value, intPlaces=intPlaces, fractPlaces=fractPlaces,
                          sep=thousands_sep, dp=decimal_point, grouping=grouping,
                          pos=prefix,
                          neg=prefix if negPic else prefix + minus_sign,
                          trailpos=suffix,
                          trailneg=suffix)


def format_decimal(
    conv: LocaleDict | None,
    value: Decimal,
    intPlaces: int = 1,
    fractPlaces: int = 2,
    curr: str = '',
    sep: str | None = None,
    grouping: int | None = None,
    dp: str | None = None,
    pos: str | None = None,
    neg: str | None = None,
    trailpos: str | None = None,
    trailneg: str | None = None
) -> str:
    """Convert Decimal to a formatted string including currency if any.

    intPlaces:  required number of digits before the decimal point
    fractPlaces:  required number of places after the decimal point
    curr:    optional currency symbol before the sign (may be blank)
    sep:     optional grouping separator (comma, period, space, or blank)
    dp:      decimal point indicator (comma or period)
             only specify as blank when places is zero
    pos:     optional sign for positive numbers: '+', space or blank
    neg:     optional sign for negative numbers: '-', '(', space or blank
    trailneg:optional trailing minus indicator:  '-', ')', space or blank

    >>> d = Decimal('-1234567.8901')
    >>> format_decimal(getUserLocale()[0], d, curr='$')
    '-$1,234,567.89'
    >>> format_decimal(getUserLocale()[0], d, fractPlaces=0, sep='.', dp='', neg='', trailneg='-')
    '1.234.568-'
    >>> format_decimal(getUserLocale()[0], d, curr='$', neg='(', trailneg=')')
    '($1,234,567.89)'
    >>> format_decimal(getUserLocale()[0], Decimal(123456789), sep=' ')
    '123 456 789.00'
    >>> format_decimal(getUserLocale()[0], Decimal('-0.02'), neg='<', trailneg='>')
    '<0.02>'
    """
    if conv is not None:
        if dp is None:
            dp = conv['decimal_point'] or '.'
        if sep is None:
            sep = conv['thousands_sep'] or ','
        if pos is None and trailpos is None:
            possign = conv['positive_sign']
            pospos = conv['p_sign_posn']
            if pospos in('0', 0):
                pos = '('; trailpos = ')'
            elif pospos in ('1', 1, '3', 3):
                pos = possign; trailpos = ''
            elif pospos in ('2', 2, '4', 4):
                pos = ''; trailpos = possign
            else:
                pos = ''; trailpos = ''
        if neg is None and trailneg is None:
            negsign = conv['negative_sign']
            negpos = conv['n_sign_posn']
            if negpos in ('0', 0):
                neg = '('; trailneg = ')'
            elif negpos in ('1', 1, '3', 3):
                neg = negsign; trailneg = ''
            elif negpos in ('2', 2, '4', 4):
                neg = ''; trailneg = negsign
            elif negpos == 127:
                neg = '-'; trailneg = ''
            else:
                neg = ''; trailneg = ''
        if grouping is None:
            groups = conv['grouping']
            grouping = groups[0] if groups else 3
    else:
        if dp is None:
            dp = '.'
        if sep is None:
            sep = ','
        if neg is None and trailneg is None:
            neg = '-'; trailneg = ''
        if grouping is None:
            grouping = 3
    q = Decimal(10) ** -fractPlaces      # 2 places --> '0.01'
    sign, _digits, exp = value.quantize(q).as_tuple()
    result: list[str] = []
    digits = list(map(str, _digits))
    build, next = result.append, digits.pop
    build((trailneg if sign else trailpos) or '')
    if value.is_finite():
        for i in range(fractPlaces):
            build(next() if digits else '0')
        if fractPlaces:
            build(dp)
        i = 0
        while digits or intPlaces > 0:
            build(next() if digits else '0')
            intPlaces -= 1
            i += 1
            if grouping and i == grouping and digits:
                i = 0
                build(sep)
    elif value.is_nan():
        result.append("NaN")
    elif value.is_infinite():
        result.append("ytinifnI")
    build(curr)
    build((neg if sign else pos) or '')
    return ''.join(reversed(result))
