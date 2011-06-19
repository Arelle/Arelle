'''
Created on Dec 20, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import datetime, re
from arelle import (XPathContext, ModelValue)
from arelle.FunctionUtil import (anytypeArg, atomicArg, stringArg, numericArg, qnameArg, nodeArg)
    
class FORG0001(Exception):
    def __init__(self):
        pass
    def __repr__(self):
        return _("Exception: FORG0001, invalid constructor")

class FONS0004(Exception):
    def __init__(self):
        pass
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
        return xsFunctions[localname](xc, source)
    except (FORG0001, ValueError, TypeError):
        raise XPathContext.XPathException(p, 'err:FORG0001', 
                                          _('invalid cast from {0} to xs:{1}').format(
                                            type(source).__name__,
                                            localname))
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
        'decimal': float,
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
        
def untypedAtomic(xc, source):
    raise xsFunctionNotAvailable()
  
def dateTime(xc, source):
    if isinstance(source,datetime.datetime): return source
    return ModelValue.dateTime(source, type=ModelValue.DATETIME, castException=FORG0001)

def xbrliDateUnion(xc, source):
    if isinstance(source,datetime.date): return source  # true for either datetime.date or datetime.datetime
    raise FORG0001
  
def date(xc, source):
    return ModelValue.dateTime(source, type=ModelValue.DATE, castException=FORG0001)
  
def time(xc, source):
    return ModelValue.time(source, castException=FORG0001)
  
def duration(xc, source):
    raise xsFunctionNotAvailable()
  
def yearMonthDuration(xc, source):
    return ModelValue.yearMonthDuration(source)
  
def dayTimeDuration(xc, source):
    return ModelValue.dayTimeDuration(source)
  
def xs_float(xc, source):
    try:
        return float(source)
    except ValueError:
        raise FORG0001
  
def double(xc, source):
    try:
        return float(source)
    except ValueError:
        raise FORG0001
  
def decimal(xc, source):
    try:
        return float(source)
    except ValueError:
        raise FORG0001
  
def integer(xc, source):
    try:
        return int(source)
    except ValueError:
        raise FORG0001
  
def nonPositiveInteger(xc, source):
    try:
        i = int(source)
        if i <= 0: return i
    except ValueError:
        pass
    raise FORG0001
  
def negativeInteger(xc, source):
    try:
        i = int(source)
        if i < 0: return i
    except ValueError:
        pass
    raise FORG0001
  
def long(xc, source):
    try:
        return int(source)
    except ValueError:
        raise FORG0001
  
def xs_int(xc, source):
    try:
        i = int(source)
        if i <= 2147483647 and i >= -2147483648: return i
    except ValueError:
        pass
    raise FORG0001
  
def short(xc, source):
    try:
        i = int(source)
        if i <= 32767 and i >= -32767: return i
    except ValueError:
        pass
    raise FORG0001
  
def byte(xc, source):
    try:
        i = int(source)
        if i <= 127 and i >= -128: return i
    except ValueError:
        pass
    raise FORG0001
  
def nonNegativeInteger(xc, source):
    try:
        i = int(source)
        if i >= 0: return i
    except ValueError:
        pass
    raise FORG0001
  
def unsignedLong(xc, source):
    try:
        i = int(source)
        if i >= 0: return i
    except ValueError:
        pass
    raise FORG0001
  
def unsignedInt(xc, source):
    try:
        i = int(source)
        if i <= 4294967295 and i >= 0: return i
    except ValueError:
        pass
    raise FORG0001
    
def unsignedShort(xc, source):
    try:
        i = int(source)
        if i <= 65535 and i >= 0: return i
    except ValueError:
        pass
    raise FORG0001
  
def unsignedByte(xc, source):
    try:
        i = int(source)
        if i <= 255 and i >= 0: return i
    except ValueError:
        pass
    raise FORG0001
  
def positiveInteger(xc, source):
    try:
        i = int(source)
        if i > 0: return i
    except ValueError:
        pass
    raise FORG0001
  
def gYearMonth(xc, source):
    raise xsFunctionNotAvailable()
  
def gYear(xc, source):
    raise xsFunctionNotAvailable()
  
def gMonthDay(xc, source):
    raise xsFunctionNotAvailable()
  
def gDay(xc, source):
    raise xsFunctionNotAvailable()
  
def gMonth(xc, source):
    raise xsFunctionNotAvailable()
  
def xsString(xc, source):
    if isinstance(source,bool):
        return 'true' if source else 'false'
    elif isinstance(source,float):
        from math import (isnan, fabs, isinf)
        if isnan(source):
            return "NaN"
        elif isinf(source):
            return "INF"
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
    elif isinstance(source,ModelValue.DateTime):
        return ('{0:%Y-%m-%d}' if source.dateOnly else '{0:%Y-%m-%dT%H:%M:%S}').format(source)
    return str(source)
  
def normalizedString(xc, source):
    return str(source)
  
tokenPattern = re.compile("(^\s([.]*[\s])*)$")
def token(xc, source):
    s = str(source)
    if tokenPattern.match(s): return s
    raise FORG0001
  
languagePattern = re.compile("[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*")
def language(xc, source):
    s = str(source)
    if languagePattern.match(s): return s
    raise FORG0001
  
def NMTOKEN(xc, source):
    raise xsFunctionNotAvailable()
  
def Name(xc, source):
    raise xsFunctionNotAvailable()
  
def NCName(xc, source):
    raise xsFunctionNotAvailable()
  
def ID(xc, source):
    raise xsFunctionNotAvailable()
  
def IDREF(xc, source):
    raise xsFunctionNotAvailable()
  
def ENTITY(xc, source):
    raise xsFunctionNotAvailable()
  
def boolean(xc, source):
    raise xsFunctionNotAvailable()
  
def base64Binary(xc, source):
    raise xsFunctionNotAvailable()
  
def hexBinary(xc, source):
    raise xsFunctionNotAvailable()
  
def anyURI(xc, source):
    return ModelValue.anyURI(source)
  
def QName(xc, source):
    if xc.progHeader:
        element = xc.progHeader.element
    else:
        element = xc.sourceElement
    return ModelValue.qname(element, source, castException=FORG0001, prefixException=FONS0004)
  
def NOTATION(xc, source):
    raise xsFunctionNotAvailable()

xsFunctions = {
    'untypedAtomic': untypedAtomic,
    'dateTime': dateTime,
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
  