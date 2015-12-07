'''
Created on Jan 26, 2011

This module is a local copy of python locale in order to allow
passing in localconv as an argument to functions without affecting
system-wide settings.  (The system settings can remain in 'C' locale.)

@author: Mark V Systems Limited (incorporating python locale module code)
(original python authors: Martin von Loewis, improved by Georg Brandl)

(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import sys, subprocess
try:
    import regex as re
except ImportError:
    import re
import collections
import unicodedata

CHAR_MAX = 127
LC_ALL = 6
LC_COLLATE = 3
LC_CTYPE = 0
LC_MESSAGES = 5
LC_MONETARY = 4
LC_NUMERIC = 1
LC_TIME = 2

C_LOCALE = None # culture-invariant locale

def getUserLocale(localeCode=''):
    # get system localeconv and reset system back to default
    import locale
    global C_LOCALE
    conv = None
    if sys.platform == "darwin" and not localeCode:
        # possibly this MacOS bug: http://bugs.python.org/issue18378
        # macOS won't provide right default code for english-european culture combinations
        localeQueryResult = subprocess.getstatusoutput("defaults read -g AppleLocale")  # MacOS only
        if localeQueryResult[0] == 0 and '_' in localeQueryResult[1]: # successful
            localeCode = localeQueryResult[1]
    try:
        locale.setlocale(locale.LC_ALL, _STR_8BIT(localeCode))  # str needed for 3to2 2.7 python to work
        conv = locale.localeconv()
    except locale.Error:
        if sys.platform == "darwin":
            # possibly this MacOS bug: http://bugs.python.org/issue18378
            # the fix to this bug will loose the monetary/number configuration with en_BE, en_FR, etc
            # so use this alternative which gets the right culture code for numbers even if english default language
            localeCulture = '-' + localeCode[3:]
            # find culture (for any language) in available locales
            for availableLocale in availableLocales():
                if len(availableLocale) >= 5 and localeCulture in availableLocale:
                    try:
                        locale.setlocale(locale.LC_ALL, availableLocale.replace('-','_'))
                        conv = locale.localeconv() # should get monetary and numeric codes
                        break
                    except locale.Error:
                        pass # this one didn't work
    locale.setlocale(locale.LC_ALL, _STR_8BIT('C'))  # str needed for 3to2 2.7 python to work
    if conv is None: # some other issue prevents getting culture code, use 'C' defaults (no thousands sep, no currency, etc)
        conv = locale.localeconv() # use 'C' environment, e.g., en_US
    if C_LOCALE is None: # load culture-invariant C locale
        C_LOCALE = locale.localeconv()
    return conv

def getLanguageCode():
    if sys.platform == "darwin":
        # possibly this MacOS bug: http://bugs.python.org/issue18378
        # even when fixed, macOS won't provide right default code for some language-culture combinations
        localeQueryResult = subprocess.getstatusoutput("defaults read -g AppleLocale")  # MacOS only
        if localeQueryResult[0] == 0 and localeQueryResult[1]: # successful
            return localeQueryResult[1][:5].replace("_","-")
    import locale
    try:
        return locale.getdefaultlocale()[0].replace("_","-")
    except (AttributeError, ValueError): #language code and encoding may be None if their values cannot be determined.
        return "en"    

def getLanguageCodes(lang=None):
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

_availableLocales = None
def availableLocales():
    global _availableLocales
    if _availableLocales is not None:
        return _availableLocales
    else:
        localeQueryResult = subprocess.getstatusoutput("locale -a")  # Mac and Unix only
        if localeQueryResult[0] == 0: # successful
            _availableLocales = set(locale.partition(".")[0].replace("_", "-")
                                    for locale in localeQueryResult[1].split("\n"))
        else:
            _availableLocales = set()
        return _availableLocales

_languageCodes = None
def languageCodes():  # dynamically initialize after gettext is loaded
    global _languageCodes
    if _languageCodes is not None:
        return _languageCodes
    else:        
        _languageCodes = { # language name (in English), code, and setlocale string which works in windows
            _("Afrikaans (South Africa)"): "af-ZA afrikaans",
            _("Albanian (Albania)"): "sq-AL albanian",
            _("Arabic (Algeria)"): "ar-DZ arb_algeria",
            _("Arabic (Bahrain)"): "ar-BH arabic_bahrain",
            _("Arabic (Egypt)"): "ar-EG arb_egy",
            _("Arabic (Iraq)"): "ar-IQ arb_irq",
            _("Arabic (Jordan)"): "ar-JO arb_jor",
            _("Arabic (Kuwait)"): "ar-KW arb_kwt",
            _("Arabic (Lebanon)"): "ar-LB arb_lbn",
            _("Arabic (Libya)"): "ar-LY arb_lby",
            _("Arabic (Morocco)"): "ar-MA arb_morocco",
            _("Arabic (Oman)"): "ar-OM arb_omn",
            _("Arabic (Qatar)"): "ar-QA arabic_qatar",
            _("Arabic (Saudi Arabia)"): "ar-SA arb_sau",
            _("Arabic (Syria)"): "ar-SY arb_syr",
            _("Arabic (Tunisia)"): "ar-TN arb_tunisia",
            _("Arabic (U.A.E.)"): "ar-AE arb_are",
            _("Arabic (Yemen)"): "ar-YE arb_yem",
            _("Basque (Spain)"): "eu-ES basque",
            _("Bulgarian (Bulgaria)"): "bg-BG bulgarian",
            _("Belarusian (Belarus)"): "be-BY belarusian",
            _("Catalan (Spain)"): "ca-ES catalan",
            _("Chinese (PRC)"): "zh-CN chs",
            _("Chinese (Taiwan)"): "zh-TW cht",
            _("Chinese (Singapore)"): "zh-SG chs",
            _("Croatian (Croatia)"): "hr-HR croatian",
            _("Czech (Czech Republic)"): "cs-CZ czech",
            _("Danish (Denmark)"): "da-DK danish",
            _("Dutch (Belgium)"): "nl-BE nlb",
            _("Dutch (Netherlands)"): "nl-NL nld",
            _("English (Australia)"): "en-AU ena",
            _("English (Belize)"): "en-BZ eng_belize",
            _("English (Canada)"): "en-CA enc",
            _("English (Caribbean)"): "en-029 eng_caribbean",
            _("English (Ireland)"): "en-IE eni",
            _("English (Jamaica)"): "en-JM enj",
            _("English (New Zealand)"): "en-NZ enz",
            _("English (South Africa)"): "en-ZA ens",
            _("English (Trinidad)"): "en-TT eng",
            _("English (United States)"): "en-US enu",
            _("English (United Kingdom)"): "en-GB eng",
            _("Estonian (Estonia)"): "et-EE estonian",
            _("Faeroese (Faroe Islands)"): "fo-FO faroese",
            _("Farsi (Iran)"): "fa-IR persian",
            _("Finnish (Finland)"): "fi-FI fin",
            _("French (Belgium)"): "fr-BE frb",
            _("French (Canada)"): "fr-CA frc",
            _("French (France)"): "fr-FR fra",
            _("French (Luxembourg)"): "fr-LU frl",
            _("French (Switzerland)"): "fr-CH frs",
            _("German (Austria)"): "de-AT dea",
            _("German (Germany)"): "de-DE deu",
            _("German (Luxembourg)"): "de-LU del",
            _("German (Switzerland)"): "de-CH des",
            _("Greek (Greece)"): "el-GR ell",
            _("Hebrew (Israel)"): "he-IL hebrew",
            _("Hindi (India)"): "hi-IN hindi",
            _("Hungarian (Hungary)"): "hu-HU hun",
            _("Icelandic (Iceland)"): "is-IS icelandic",
            _("Indonesian (Indonesia)"): "id-ID indonesian",
            _("Italian (Italy)"): "it-IT ita",
            _("Italian (Switzerland)"): "it-CH its",
            _("Japanese (Japan)"): "ja-JP jpn",
            _("Korean (Korea)"): "ko-KR kor",
            _("Latvian (Latvia)"): "lv-LV latvian",
            _("Lithuanian (Lituania)"): "lt-LT lithuanian",
            _("Malaysian (Malaysia)"): "ms-MY malay",
            _("Maltese (Malta)"): "mt-MT maltese",
            _("Norwegian (Bokmal)"): "no-NO nor",
            _("Norwegian (Nynorsk)"): "no-NO non",
            _("Persian (Iran)"): "fa-IR persian",
            _("Polish (Poland)"): "pl-PL plk",
            _("Portuguese (Brazil)"): "pt-BR ptb",
            _("Portuguese (Portugal)"): "pt-PT ptg",
            _("Romanian (Romania)"): "ro-RO rom",
            _("Russian (Russia)"): "ru-RU rus",
            _("Serbian (Cyrillic)"): "sr-RS srb",
            _("Serbian (Latin)"): "sr-RS srl",
            _("Slovak (Slovakia)"): "sk-SK sky",
            _("Slovenian (Slovania)"): "sl-SI slovenian",
            _("Spanish (Argentina)"): "es-AR esr",
            _("Spanish (Bolivia)"): "es-BO esb",
            _("Spanish (Colombia)"): "es-CO eso",
            _("Spanish (Chile)"): "es-CL esl",
            _("Spanish (Costa Rica)"): "es-CR esc",
            _("Spanish (Dominican Republic)"): "es-DO esd",
            _("Spanish (Ecuador)"): "es-EC esf",
            _("Spanish (El Salvador)"): "es-SV ese",
            _("Spanish (Guatemala)"): "es-GT esg",
            _("Spanish (Honduras)"): "es-HN esh",
            _("Spanish (Mexico)"): "es-MX esm",
            _("Spanish (Nicaragua)"): "es-NI esi",
            _("Spanish (Panama)"): "es-PA esa",
            _("Spanish (Paraguay)"): "es-PY esz",
            _("Spanish (Peru)"): "es-PE esr",
            _("Spanish (Puerto Rico)"): "es-PR esu",
            _("Spanish (Spain)"): "es-ES esn",
            _("Spanish (United States)"): "es-US est",
            _("Spanish (Uruguay)"): "es-UY esy",
            _("Spanish (Venezuela)"): "es-VE esv",
            _("Swedish (Sweden)"): "sv-SE sve",
            _("Swedish (Finland)"): "sv-FI svf",
            _("Thai (Thailand)"): "th-TH thai",
            _("Turkish (Turkey)"): "tr-TR trk",
            _("Ukrainian (Ukraine)"): "uk-UA ukr",
            _("Urdu (Pakistan)"): "ur-PK urdu",
            _("Vietnamese (Vietnam)"): "vi-VN vietnamese",
        }
        return _languageCodes

def rtlString(source, lang):
    if lang and source and lang[0:2] in {"ar","he"}:
        line = []
        lineInsertion = 0
        words = []
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
def _grouping_intervals(grouping):
    last_interval = 3 # added by Mark V to prevent compile error but not necessary semantically
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
def _group(conv, s, monetary=False):
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
def _strip_padding(s, amount):
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

def format(conv, percent, value, grouping=False, monetary=False, *additional):
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

def _format(conv, percent, value, grouping=False, monetary=False, *additional):
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

def format_string(conv, f, val, grouping=False):
    """Formats a string in the same way that the % formatting would use,
    but takes the current locale into account.
    Grouping is applied if the third parameter is true."""
    percents = list(_percent_re.finditer(f))
    new_f = _percent_re.sub('%s', f)

    if isinstance(val, collections.Mapping):
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

    return new_f % val

def currency(conv, val, symbol=True, grouping=False, international=False):
    """Formats val according to the currency settings
    in the current locale."""

    # check for illegal values
    digits = conv[international and 'int_frac_digits' or 'frac_digits']
    if digits == 127:
        raise ValueError("Currency formatting is not possible using "
                         "the 'C' locale.")

    s = format('%%.%if' % digits, abs(val), grouping, monetary=True)
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

def ftostr(conv, val):
    """Convert float to integer, taking the locale into account."""
    return format(conv, "%.12g", val)

def atof(conv, string, func=float):
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

def atoi(conv, str):
    "Converts a string to an integer according to the locale settings."
    return atof(conv, str, _INT)

# decimal formatting
from decimal import getcontext, Decimal

def format_picture(conv, value, picture):
    monetary = False
    decimal_point = conv['decimal_point']
    thousands_sep = conv[monetary and 'mon_thousands_sep' or 'thousands_sep']
    percent = '%'
    per_mille = '\u2030'
    minus_sign = '-'
    #grouping = conv[monetary and 'mon_grouping' or 'grouping']

    if isinstance(value, float):
        value = Decimal.from_float(value)
    elif isinstance(value, _STR_NUM_TYPES):
        value = Decimal(value)
    elif not isinstance(value, Decimal):
        raise ValueError(_('Picture requires a number convertable to decimal or float').format(picture))
        
    if value.is_nan():
        return 'NaN'
    
    isNegative = value.is_signed()
    
    pic, sep, negPic = picture.partition(';')
    if negPic and ';' in negPic:
        raise ValueError(_('Picture contains multiple picture sepearators {0}').format(picture))
    if isNegative and negPic:
        pic = negPic
    
    if len([c for c in pic if c in (percent, per_mille) ]) > 1:
        raise ValueError(_('Picture contains multiple percent or per_mille charcters {0}').format(picture))
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
            raise ValueError(_('Sub-picture contains decimal point sepearators {0}').format(pic))
    
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

def format_decimal(conv, value, intPlaces=1, fractPlaces=2, curr='', sep=None, grouping=None, dp=None, pos=None, neg=None, trailpos=None, trailneg=None):
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
    >>> format(d, curr='$')
    '-$1,234,567.89'
    >>> format(d, places=0, sep='.', dp='', neg='', trailneg='-')
    '1.234.568-'
    >>> format(d, curr='$', neg='(', trailneg=')')
    '($1,234,567.89)'
    >>> format(Decimal(123456789), sep=' ')
    '123 456 789.00'
    >>> format(Decimal('-0.02'), neg='<', trailneg='>')
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
    sign, digits, exp = value.quantize(q).as_tuple()
    result = []
    digits = list(map(str, digits))
    build, next = result.append, digits.pop
    build(trailneg if sign else trailpos)
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
    build(neg if sign else pos)
    return ''.join(reversed(result))
