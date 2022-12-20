'''
This module is a local copy of python locale in order to allow
passing in localconv as an argument to functions without affecting
system-wide settings.  (The system settings can remain in 'C' locale.)

See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
import sys, subprocess
import regex as re
from typing import Generator, cast, Any, Callable
from fractions import Fraction
from arelle.typing import TypeGetText, LocaleDict
from collections.abc import Mapping
import unicodedata

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


def _getUserLocaleUnsafe(localeCode: str = '') -> tuple[LocaleDict, str | None]:
    """
    Get locale conventions dictionary. May change the global locale if called directly.
    :param localeCode: The locale code to use to retrieve conventions. Defaults to system default.
    :return: Tuple of local conventions dictionary and a user-directed setup message
    """
    import locale
    conv = None
    localeSetupMessage = None
    localeCode = localeCode.replace('-', '_')
    localeCodeWithDefault = (
        f"{localeCode}_{defaultLocaleCodes[localeCode]}"
        if localeCode in defaultLocaleCodes else None)
    candidateLocaleCodes = [localeCode] + ([localeCodeWithDefault] if localeCodeWithDefault else [])
    for candidateLocaleCode in candidateLocaleCodes:
        try:
            locale.setlocale(locale.LC_ALL, candidateLocaleCode)
            conv = locale.localeconv()
            if candidateLocaleCode == localeCodeWithDefault:
                localeSetupMessage = f'locale code "{localeCode}" should include a country code, e.g. {localeCodeWithDefault}'
            break
        except locale.Error:
            pass
    else:
        # Like above, but avoids a fork unless the earlier options don't work out.
        try:
            localeCodes = getLocaleList()
            # Don't die because we couldn't find a locale command or parse its output.
        except:
            localeCodes = []
        matchingLocaleCodes = sorted(
            (c for c in localeCodes if c.startswith(localeCode)),
            # prioritize localeCodeWithDefault prefix and UTF-8
            key=lambda c: (localeCodeWithDefault and not c.startswith(localeCodeWithDefault), not re.search(r'utf-?8$', c)))
        for candidateLocaleCode in matchingLocaleCodes:
            try:
                locale.setlocale(locale.LC_ALL, candidateLocaleCode)
                conv = locale.localeconv()
            except locale.Error:
                pass
    if conv is None:  # some other issue prevents getting culture code, use 'C' defaults (no thousands sep, no currency, etc)
        locale.setlocale(locale.LC_ALL, 'C')
        localeSetupMessage = f"locale code \"{localeCode}\" is not available on this system"
        conv = locale.localeconv() # use 'C' environment, e.g., en_US
    return cast(LocaleDict, conv), localeSetupMessage


def getUserLocale(localeCode: str = '') -> tuple[LocaleDict, str | None]:
    """
    Get locale conventions dictionary. Ensures that the locale (global to the process) is reset afterwards.
    :param localeCode: The locale code to use to retrieve conventions. Defaults to system default.
    :return: Tuple of local conventions dictionary and a user-directed setup message
    """
    import locale
    currentLocale = locale.setlocale(locale.LC_ALL)
    try:
        return _getUserLocaleUnsafe(localeCode)
    finally:
        locale.setlocale(locale.LC_ALL, currentLocale)


def getLanguageCode() -> str:
    if sys.platform == "darwin": # MacOS doesn't provide correct language codes
        localeQueryResult = subprocess.getstatusoutput("defaults read -g AppleLocale")  # MacOS only
        if localeQueryResult[0] == 0 and localeQueryResult[1]: # successful
            return localeQueryResult[1][:5].replace("_","-")
    import locale
    languageCode, encoding = locale.getdefaultlocale()
    # language code and encoding may be None if their values cannot be determined.
    if isinstance(languageCode, str):
        return languageCode.replace("_","-")
    from arelle.XbrlConst import defaultLocale
    return defaultLocale # XBRL international default locale

def getLanguageCodes(lang: str | None = None) -> list[str]:
    if lang is None:
        lang = getLanguageCode()
    # allow searching on the lang with country part, either python or standard form, or just language
    return [lang, lang.replace("-","_"), lang.partition("-")[0]]


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


def getLocaleList() -> list[str]:
    process = subprocess.run(['locale', '-a'], capture_output=True, encoding='iso8859-1', text=True)
    return process.stdout.splitlines() if process.returncode == 0 else []


_availableLocales = None
def availableLocales() -> set[str]:
    global _availableLocales
    if _availableLocales is not None:
        return _availableLocales
    else:
        _availableLocales = {locale.partition(".")[0].replace("_", "-") for locale in getLocaleList()}
        return _availableLocales

_languageCodes = None
def languageCodes() -> dict[str, str]:  # dynamically initialize after gettext is loaded
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
    import locale
    locale.setlocale(locale.LC_ALL, 'C')


_disableRTL: bool = False # disable for implementations where tkinter supports rtl
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

#perform the grouping from right to left
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

# decimal formatting
from decimal import Decimal

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
