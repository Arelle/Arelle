'''
See COPYRIGHT.md for copyright information.
'''
import datetime, re
from arelle import (XPathContext, ModelValue)
from arelle.FunctionUtil import (anytypeArg, atomicArg, stringArg, numericArg, qnameArg, nodeArg)
from arelle.XmlValidate import lexicalPatterns
from arelle.XPathParser import ProgHeader
from math import isnan, fabs, isinf
from decimal import Decimal, InvalidOperation
from numbers import Number

class FORG0001(Exception):
    def __init__(self, message=None):
        self.message = message
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _("Exception: FORG0001, invalid constructor")

class FONS0004(Exception):
    def __init__(self, message=None):
        self.message = message
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _("Exception: FONS0004, no namespace found for prefix")

class xsFunctionNotAvailable(Exception):
    def __init__(self):
        self.args =  (_("xs function not available"),)
    def __repr__(self):
        return self.args[0]

def call(xc, p, localname, args):
    source = atomicArg(xc, p, args, 0, "value?", missingArgFallback=() )
    if source == (): return source
    try:
        if localname not in xsFunctions: raise xsFunctionNotAvailable
        return xsFunctions[localname](xc, p, source)
    except (FORG0001, ValueError, TypeError) as ex:
        if hasattr(ex, "message") and ex.message:
            exMsg = ", " + ex.message
        else:
            exMsg = ""
        raise XPathContext.XPathException(p, 'err:FORG0001',
                                          _('invalid cast from {0} to xs:{1}{2}').format(
                                            type(source).__name__,
                                            localname,
                                            exMsg))
    except xsFunctionNotAvailable:
        raise XPathContext.FunctionNotAvailable("xs:{0}".format(localname))

objtype = {
        #'untypedAtomic': untypedAtomic,
        'dateTime':  ModelValue.DateTime,
        'date': ModelValue.DateTime,
        'time': ModelValue.Time,
        #'duration': duration,
        'yearMonthDuration': ModelValue.YearMonthDuration,
        'dayTimeDuration': ModelValue.DayTimeDuration,
        'float': float,
        'double': float,
        'decimal': Decimal,
        'integer': int,
        'nonPositiveInteger': int,
        'negativeInteger': int,
        'long': int,
        'int': int,
        'short': int,
        'byte': int,
        'nonNegativeInteger': int,
        'unsignedLong': int,
        'unsignedInt': int,
        'unsignedShort': int,
        'unsignedByte': int,
        'positiveInteger': int,
        #'gYearMonth': gYearMonth,
        #'gYear': gYear,
        #'gMonthDay': gMonthDay,
        #'gDay': gDay,
        #'gMonth': gMonth,
        'string': str,
        'normalizedString': str,
        'token': str,
        'language': str,
        'NMTOKEN': str,
        'Name': str,
        'NCName': str,
        'ID': str,
        'IDREF': str,
        'ENTITY': str,
        'boolean': bool,
        #'base64Binary': byte,
        #'hexBinary': byte,
        'anyURI': ModelValue.AnyURI,
        'QName': ModelValue.QName,
        'NOTATION': str,
      }

def isXsType(localName):
    if localName[-1] in ('?', '+', '*'):
        return localName[:-1] in xsFunctions
    return localName in xsFunctions

def untypedAtomic(xc, p, source):
    raise xsFunctionNotAvailable()

def anyType(xc, p, source):
    raise xsFunctionNotAvailable()

def anyAtomicType(xc, p, source):
    raise xsFunctionNotAvailable()

def dateTime(xc, p, source):
    if isinstance(source,datetime.datetime): return source
    return ModelValue.dateTime(source, type=ModelValue.DATETIME, castException=FORG0001)

def dateTimeInstantEnd(xc, p, source):
    if isinstance(source,datetime.datetime): return source  # true for either datetime.date or datetime.datetime
    return ModelValue.dateTime(source, addOneDay=True, type=ModelValue.DATETIME, castException=FORG0001)

def xbrliDateUnion(xc, p, source):
    if isinstance(source,datetime.date): return source  # true for either datetime.date or datetime.datetime
    return ModelValue.dateTime(source, type=ModelValue.DATEUNION, castException=FORG0001)

def date(xc, p, source):
    return ModelValue.dateTime(source, type=ModelValue.DATE, castException=FORG0001)

def time(xc, p, source):
    return ModelValue.time(source, castException=FORG0001)

def duration(xc, p, source):
    raise xsFunctionNotAvailable()

def yearMonthDuration(xc, p, source):
    return ModelValue.yearMonthDuration(source)

def dayTimeDuration(xc, p, source):
    return ModelValue.dayTimeDuration(source)

def xs_float(xc, p, source):
    try:
        return float(source)
    except ValueError:
        raise FORG0001

def double(xc, p, source):
    try:
        return float(source)
    except ValueError:
        raise FORG0001

def decimal(xc, p, source):
    try:
        return Decimal(source)
    except InvalidOperation:
        raise FORG0001

def integer(xc, p, source):
    try:
        return int(source)
    except ValueError:
        raise FORG0001

def nonPositiveInteger(xc, p, source):
    try:
        i = int(source)
        if i <= 0: return i
    except ValueError:
        pass
    raise FORG0001

def negativeInteger(xc, p, source):
    try:
        i = int(source)
        if i < 0: return i
    except ValueError:
        pass
    raise FORG0001

def long(xc, p, source):
    try:
        return int(source)
    except ValueError:
        raise FORG0001

def xs_int(xc, p, source):
    try:
        i = int(source)
        if i <= 2147483647 and i >= -2147483648: return i
    except ValueError:
        pass
    raise FORG0001

def short(xc, p, source):
    try:
        i = int(source)
        if i <= 32767 and i >= -32767: return i
    except ValueError:
        pass
    raise FORG0001

def byte(xc, p, source):
    try:
        i = int(source)
        if i <= 127 and i >= -128: return i
    except ValueError:
        pass
    raise FORG0001

def nonNegativeInteger(xc, p, source):
    try:
        i = int(source)
        if i >= 0: return i
    except ValueError:
        pass
    raise FORG0001

def unsignedLong(xc, p, source):
    try:
        i = int(source)
        if i >= 0: return i
    except ValueError:
        pass
    raise FORG0001

def unsignedInt(xc, p, source):
    try:
        i = int(source)
        if i <= 4294967295 and i >= 0: return i
    except ValueError:
        pass
    raise FORG0001

def unsignedShort(xc, p, source):
    try:
        i = int(source)
        if i <= 65535 and i >= 0: return i
    except ValueError:
        pass
    raise FORG0001

def unsignedByte(xc, p, source):
    try:
        i = int(source)
        if i <= 255 and i >= 0: return i
    except ValueError:
        pass
    raise FORG0001

def positiveInteger(xc, p, source):
    try:
        i = int(source)
        if i > 0: return i
    except ValueError:
        pass
    raise FORG0001

def gYearMonth(xc, p, source):
    try:
        match = lexicalPatterns['gYearMonth'].match(source)
        if match:
            year, month, zSign, zHrMin, zHr, zMin = match.groups()
            return ModelValue.gYearMonth(year, month)
    except (ValueError, TypeError):
        pass
    raise FORG0001

def gYear(xc, p, source):
    try:
        match = lexicalPatterns['gYear'].match(source)
        if match:
            year, zSign, zHrMin, zHr, zMin = match.groups()
            return ModelValue.gYear(year)
    except (ValueError, TypeError):
        pass
    raise FORG0001

def gMonthDay(xc, p, source):
    try:
        match = lexicalPatterns['gMonthDay'].match(source)
        if match:
            month, day, zSign, zHrMin, zHr, zMin = match.groups()
            if not int(day) > {2:29, 4:30, 6:30, 9:30, 11:30, 1:31, 3:31, 5:31, 7:31, 8:31, 10:31, 12:31}[int(month)]:
                return ModelValue.gMonthDay(month, day)
    except (ValueError, TypeError):
        pass
    raise FORG0001

def gDay(xc, p, source):
    try:
        match = lexicalPatterns['gDay'].match(source)
        if match:
            day, zSign, zHrMin, zHr, zMin = match.groups()
            return ModelValue.gDay(day)
    except (ValueError, TypeError):
        pass
    raise FORG0001

def gMonth(xc, p, source):
    try:
        match = lexicalPatterns['gMonth'].match(source)
        if match:
            month, zSign, zHrMin, zHr, zMin = match.groups()
            return ModelValue.gMonth(month)
    except (ValueError, TypeError):
        pass
    raise FORG0001

def xsString(xc, p, source):
    if isinstance(source,bool):
        return 'true' if source else 'false'
    elif isinstance(source,float):
        if isnan(source):
            return "NaN" # note that -NaN is reported as NaN in XML
        elif isinf(source):
            return "-INF" if source < 0 else "INF"
        '''
        numMagnitude = fabs(source)
        if numMagnitude < 1000000 and numMagnitude > .000001:
            # don't want floating notation which python does for more than 4 decimal places
            s =
        '''
        s = str(source)
        if s.endswith(".0"):
            s = s[:-2]
        return s
    elif isinstance(source,Decimal):
        if isnan(source):
            return "NaN" # note that -NaN is reported as NaN in XML
        elif isinf(source):
            return "-INF" if source < 0 else "INF"
        return "{:f}".format(source) # str(source) causes unwanted scientific notation for values like 0.00000001
    elif isinstance(source,ModelValue.DateTime):
        return ('{0:%Y-%m-%d}' if source.dateOnly else '{0:%Y-%m-%dT%H:%M:%S}').format(source)
    return str(source)

def normalizedString(xc, p, source):
    return str(source)

tokenPattern = re.compile(r"^\s*([-\.:\w]+)\s*$")
def token(xc, p, source):
    s = str(source)
    if tokenPattern.match(s): return s
    raise FORG0001

languagePattern = re.compile("[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*")
def language(xc, p, source):
    s = str(source)
    if languagePattern.match(s): return s
    raise FORG0001

def NMTOKEN(xc, p, source):
    raise xsFunctionNotAvailable()

def Name(xc, p, source):
    raise xsFunctionNotAvailable()

def NCName(xc, p, source):
    raise xsFunctionNotAvailable()

def ID(xc, p, source):
    raise xsFunctionNotAvailable()

def IDREF(xc, p, source):
    raise xsFunctionNotAvailable()

def ENTITY(xc, p, source):
    raise xsFunctionNotAvailable()

def boolean(xc, p, source):
    if isinstance(source,bool):
        return source
    elif isinstance(source, Number):
        if source == 1:
            return True
        elif source == 0:
            return False
    elif isinstance(source,str):
        b = source.lower()
        if b in ('true','yes'):
            return True
        elif b in ('false','no'):
            return False
    raise FORG0001

def base64Binary(xc, p, source):
    raise xsFunctionNotAvailable()

def hexBinary(xc, p, source):
    raise xsFunctionNotAvailable()

def anyURI(xc, p, source):
    return ModelValue.anyURI(source)

def QName(xc, p, source):
    if isinstance(p, ProgHeader):
        element = p.element
    elif xc.progHeader:
        element = xc.progHeader.element
    else:
        element = xc.sourceElement
    return ModelValue.qname(element, source, castException=FORG0001, prefixException=FONS0004)

def NOTATION(xc, p, source):
    raise xsFunctionNotAvailable()

xsFunctions = {
    'untypedAtomic': untypedAtomic,
    'anyType': anyType,
    'anyAtomicType': anyAtomicType,
    'dateTime': dateTime,
    'DATETIME_START': dateTime,
    'DATETIME_INSTANT_END': dateTimeInstantEnd,
    'XBRLI_DATEUNION': xbrliDateUnion,
    'date': date,
    'time': time,
    'duration': duration,
    'yearMonthDuration': yearMonthDuration,
    'dayTimeDuration': dayTimeDuration,
    'float': xs_float,
    'double': double,
    'decimal': decimal,
    'integer': integer,
    'nonPositiveInteger': nonPositiveInteger,
    'negativeInteger': negativeInteger,
    'long': long,
    'int': xs_int,
    'short': short,
    'byte': byte,
    'nonNegativeInteger': nonNegativeInteger,
    'unsignedLong': unsignedLong,
    'unsignedInt': unsignedInt,
    'unsignedShort': unsignedShort,
    'unsignedByte': unsignedByte,
    'positiveInteger': positiveInteger,
    'gYearMonth': gYearMonth,
    'gYear': gYear,
    'gMonthDay': gMonthDay,
    'gDay': gDay,
    'gMonth': gMonth,
    'string': xsString,
    'normalizedString': normalizedString,
    'token': token,
    'language': language,
    'NMTOKEN': NMTOKEN,
    'Name': Name,
    'NCName': NCName,
    'ID': ID,
    'IDREF': IDREF,
    'ENTITY': ENTITY,
    'boolean': boolean,
    'base64Binary': base64Binary,
    'hexBinary': hexBinary,
    'anyURI': anyURI,
    'QName': QName,
    'NOTATION': NOTATION,
    }
