'''
Created on Jan 4, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import copy, datetime
try:
    import regex as re
except ImportError:
    import re
XmlUtil = None

def qname(value, name=None, noPrefixIsNoNamespace=False, castException=None, prefixException=None):
    # either value can be an etree ModelObject element: if no name then qname is element tag quanem
    #     if name provided qname uses element as xmlns reference and name as prefixed name
    # value can be namespaceURI and name is localname or prefix:localname
    # value can be prefix:localname (and localname omitted)
    # for xpath qnames which do not take default namespace if no prefix, specify noPrefixIsNoNamespace
    if isinstance(value, ModelObject):
        if name: # name is prefixed name
            element = value  # may be an attribute
            value = name
            name = None
        else:
            return QName(value.prefix, value.namespaceURI, value.localName)
    elif isinstance(name, ModelObject):
        element = name
        name = None
        element = None
        value = name
    else:
        element = None
    if isinstance(value,QName):
        return value
    elif not isinstance(value,_STR_BASE):
        if castException: raise castException
        return None
    if value and value[0] == '{': # clark notation (with optional prefix)
        namespaceURI,sep,prefixedLocalName = value[1:].rpartition('}')
        prefix,sep,localName = prefixedLocalName.rpartition(':')
        if not sep:
            prefix = None
        namespaceDict = None
    else:
        if isinstance(name, dict):
            namespaceURI = None
            namespaceDict = name
        elif name is not None:
            if name:  # len > 0
                namespaceURI = value
            else:
                namespaceURI = None
            namespaceDict = None
            value = name
        else:
            namespaceURI = None
            namespaceDict = None
        prefix,sep,localName = value.strip().rpartition(":")  # must be whitespace collapsed
        if not prefix:
            prefix = None # don't want '' but instead None if no prefix
            if noPrefixIsNoNamespace:
                return QName(None, None, localName)
    if namespaceURI:
        return QName(prefix, namespaceURI, localName)
    elif namespaceDict and prefix in namespaceDict:
        return QName(prefix, namespaceDict[prefix], localName)
    elif element is not None:
        # same as XmlUtil.xmlns but local for efficiency
        namespaceURI = element.nsmap.get(prefix)
        if not namespaceURI and prefix == 'xml':
            namespaceURI = "http://www.w3.org/XML/1998/namespace"
    if not namespaceURI:
        if prefix: 
            if prefixException: raise prefixException
            return None  # error, prefix not found
        namespaceURI = None # cancel namespace if it is a zero length string
    return QName(prefix, namespaceURI, localName)

def qnameNsLocalName(namespaceURI, localName):  # does not handle localNames with prefix
    return QName(None, namespaceURI or None, localName)

def qnameClarkName(clarkname):  # does not handle clark names with prefix
    if clarkname and clarkname[0] == '{': # clark notation (with optional prefix)
        namespaceURI,sep,localName = clarkname[1:].rpartition('}')
        return QName(None, namespaceURI or None, localName)
    else:
        return QName(None, None, clarkname)

def qnameEltPfxName(element, prefixedName, prefixException=None):
    prefix,sep,localName = prefixedName.rpartition(':')
    if not prefix:
        prefix = None # don't want '' but instead None if no prefix
    namespaceURI = element.nsmap.get(prefix)
    if not namespaceURI:
        if prefix:
            if prefix == 'xml':
                namespaceURI = "http://www.w3.org/XML/1998/namespace"
            else:
                if prefixException: raise prefixException
                return None
        else:
            namespaceURI = None # cancel namespace if it is a zero length string
    return QName(prefix, namespaceURI, localName)

class QName:
    __slots__ = ("prefix", "namespaceURI", "localName", "qnameValueHash")
    def __init__(self,prefix,namespaceURI,localName):
        self.prefix = prefix
        self.namespaceURI = namespaceURI
        self.localName = localName
        self.qnameValueHash = hash( (namespaceURI, localName) )
    def __hash__(self):
        return self.qnameValueHash
    @property
    def clarkNotation(self):
        if self.namespaceURI:
            return '{{{0}}}{1}'.format(self.namespaceURI, self.localName)
        else:
            return self.localName
    def __repr__(self):
        return self.__str__() 
    def __str__(self):
        if self.prefix and self.prefix != '':
            return self.prefix + ':' + self.localName
        else:
            return self.localName
    def __eq__(self,other):
        try:
            return (self.qnameValueHash == other.qnameValueHash and 
                    self.localName == other.localName and self.namespaceURI == other.namespaceURI)
        except AttributeError:
            return False
        ''' don't think this is used any longer
        if isinstance(other,_STR_BASE):
            # only compare nsnames {namespace}localname format, if other has same hash
            return self.__hash__() == other.__hash__() and self.clarkNotation == other
        elif isinstance(other,QName):
            return self.qnameValueHash == other.qnameValueHash and \
                    self.namespaceURI == other.namespaceURI and self.localName == other.localName
        elif isinstance(other,ModelObject):
            return self.namespaceURI == other.namespaceURI and self.localName == other.localName
        '''
        '''
        try:
            return (self.qnameValueHash == other.qnameValueHash and 
                    self.namespaceURI == other.namespaceURI and self.localName == other.localName)
        except AttributeError:  # other may be a model object and not a QName
            try:
                return self.namespaceURI == other.namespaceURI and self.localName == other.localName
            except AttributeError:
                return False
        return False
        '''
    def __ne__(self,other):
        return not self.__eq__(other)
    def __lt__(self,other):
        return (self.namespaceURI is None and other.namespaceURI) or \
                (self.namespaceURI and other.namespaceURI and self.namespaceURI < other.namespaceURI) or \
                (self.namespaceURI == other.namespaceURI and self.localName < other.localName)
    def __le__(self,other):
        return (self.namespaceURI is None and other.namespaceURI) or \
                (self.namespaceURI and other.namespaceURI and self.namespaceURI < other.namespaceURI) or \
                (self.namespaceURI == other.namespaceURI and self.localName <= other.localName)
    def __gt__(self,other):
        return (self.namespaceURI and other.namespaceURI is None) or \
                (self.namespaceURI and other.namespaceURI and self.namespaceURI > other.namespaceURI) or \
                (self.namespaceURI == other.namespaceURI and self.localName > other.localName)
    def __ge__(self,other):
        return (self.namespaceURI and other.namespaceURI is None) or \
                (self.namespaceURI and other.namespaceURI and self.namespaceURI > other.namespaceURI) or \
                (self.namespaceURI == other.namespaceURI and self.localName >= other.localName)

from arelle.ModelObject import ModelObject
    
def anyURI(value):
    return AnyURI(value)

class AnyURI(str):
    def __new__(cls, value):
        return str.__new__(cls, value)

datetimePattern = re.compile(r"\s*([0-9]{4})-([0-9]{2})-([0-9]{2})[T ]([0-9]{2}):([0-9]{2}):([0-9]{2})\s*|"
                             r"\s*([0-9]{4})-([0-9]{2})-([0-9]{2})\s*")
timePattern = re.compile(r"\s*([0-9]{2}):([0-9]{2}):([0-9]{2})\s*")
durationPattern = re.compile(r"\s*(-?)P((-?[0-9]+)Y)?((-?[0-9]+)M)?((-?[0-9]+)D)?(T((-?[0-9]+)H)?((-?[0-9]+)M)?((-?[0-9.]+)S)?)?\s*")

DATE = 1
DATETIME = 2
DATEUNION = 3
def dateTime(value, time=None, addOneDay=None, type=None, castException=None):
    if value == "MinDate":
        return DateTime(datetime.MINYEAR,1,1)
    elif value == "maxyear":
        return DateTime(datetime.MAXYEAR,12,31)
    elif isinstance(value, ModelObject):
        value = value.text
    elif isinstance(value, DateTime) and not addOneDay and (value.dateOnly == (type == DATE)):
        return value    # no change needed for cast or conversion
    elif isinstance(value, datetime.datetime):
        if type == DATE: 
            dateOnly = True
        elif type == DATETIME: 
            dateOnly = False
        else: 
            dateOnly = isinstance(value, DateTime) and value.dateOnly
            if addOneDay and not dateOnly:
                addOneDay = False 
        return DateTime(value.year, value.month, value.day, value.hour, value.minute, value.second, value.microsecond, tzinfo=value.tzinfo, dateOnly=dateOnly, addOneDay=addOneDay)
    elif isinstance(value, datetime.date):
        return DateTime(value.year, value.month, value.day,dateOnly=True,addOneDay=addOneDay)
    elif castException and not isinstance(value, _STR_BASE):
        raise castException("not a string value")
    if value is None:
        return None
    match = datetimePattern.match(value.strip())
    if match is None:
        if castException:
            raise castException("lexical pattern mismatch")
        return None
    if match.lastindex == 6:
        if type == DATE: 
            if castException:
                raise castException("date-only object has too many fields or contains time")
            return None
        result = DateTime(int(match.group(1)),int(match.group(2)),int(match.group(3)),int(match.group(4)),int(match.group(5)),int(match.group(6)), dateOnly=False)
    else:
        if type == DATE or type == DATEUNION: 
            dateOnly = True
        elif type == DATETIME: 
            dateOnly = False
        else: 
            dateOnly = False
        result = DateTime(int(match.group(7)),int(match.group(8)),int(match.group(9)),dateOnly=dateOnly,addOneDay=addOneDay)
    return result

def lastDayOfMonth(year, month):
    if month in (1,3,5,7,8,10,12): return 31
    if month in (4,6,9,11): return 30
    if year % 400 == 0 or (year % 100 != 0 and year % 4 == 0): return 29
    return 28

#!!! see note in XmlUtil.py datetimeValue, may need exceptions handled or special treatment for end time of 9999-12-31

class DateTime(datetime.datetime):
    def __new__(cls, y, m, d, hr=0, min=0, sec=0, microsec=0, tzinfo=None, dateOnly=None, addOneDay=None):
        lastDay = lastDayOfMonth(y, m)
        # check day and month before adjustment
        if not 1 <= m <= 12: raise ValueError("month must be in 1..12")
        if not 1 <= d <= lastDay: raise ValueError("day is out of range for month")
        if hr == 24:
            if min != 0 or sec != 0 or microsec != 0: raise ValueError("hour 24 must have 0 mins and secs.")
            hr = 0
            d += 1
        if addOneDay: 
            d += 1
        if d > lastDay: d -= lastDay; m += 1
        if m > 12: m = 1; y += 1
        dateTime = datetime.datetime.__new__(cls, y, m, d, hr, min, sec, microsec, tzinfo)
        dateTime.dateOnly = dateOnly
        return dateTime
    def __copy__(self):
        return DateTime(self.year, self.month, self.day, self.hour, self.minute, self.second, self.microsecond, self.tzinfo, self.dateOnly)
    def __str__(self):
        if self.dateOnly:
            return "{0.year:04}-{0.month:02}-{0.day:02}".format(self)
        else:
            return "{0.year:04}-{0.month:02}-{0.day:02}T{0.hour:02}:{0.minute:02}:{0.second:02}".format(self)
    def addYearMonthDuration(self, other, sign):
        m = self.month + sign * other.months
        y = self.year + sign * other.years + m // 12
        m %= 12
        d = self.day
        lastDay = lastDayOfMonth(y, m)
        if d > lastDay: d = lastDay
        return DateTime(y, m, d, self.hour, self.minute, self.second, self.microsecond, self.tzinfo, self.dateOnly)
    def __add__(self, other):
        if isinstance(other, YearMonthDuration):
            return self.addYearMonthDuration(other, 1)
        else:
            if isinstance(other, Time): other = dayTimeDuration(other)
            dt = super(DateTime, self).__add__(other)
            return DateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond, dt.tzinfo, self.dateOnly)

    def __sub__(self, other):
        if isinstance(other, YearMonthDuration):
            return self.addYearMonthDuration(other, -1)
        else:
            dt = super(DateTime, self).__sub__(other)
            if isinstance(dt,datetime.timedelta):
                return DayTimeDuration(dt.days, 0, 0, dt.seconds)
            else:
                if isinstance(other, Time): other = dayTimeDuration(other)
                return DateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond, dt.tzinfo, self.dateOnly)
    
def dateUnionEqual(dateUnion1, dateUnion2, instantEndDate=False):
    if isinstance(dateUnion1,DateTime):
        if instantEndDate and dateUnion1.dateOnly:
            dateUnion1 += datetime.timedelta(1)
    elif isinstance(dateUnion1,datetime.date):
        dateUnion1 = dateTime(dateUnion1, addOneDay=instantEndDate)
    if isinstance(dateUnion2,DateTime):
        if instantEndDate and dateUnion2.dateOnly:
            dateUnion2 += datetime.timedelta(1)
    elif isinstance(dateUnion2,datetime.date):
        dateUnion2 = dateTime(dateUnion2, addOneDay=instantEndDate)
    return dateUnion1 == dateUnion2
        
def dateunionDate(datetimeValue, subtractOneDay=False):
    isDate = (hasattr(datetimeValue,'dateOnly') and datetimeValue.dateOnly) or not hasattr(datetimeValue, 'hour')
    d = datetimeValue
    if isDate or (d.hour == 0 and d.minute == 0 and d.second == 0):
        if subtractOneDay and not isDate: d -= datetime.timedelta(1)
    return datetime.date(d.year, d.month, d.day)

def yearMonthDuration(value):
    minus, hasYr, yrs, hasMo, mos, hasDay, days, hasTime, hasHr, hrs, hasMin, mins, hasSec, secs = durationPattern.match(value).groups()
    if hasDay or hasHr or hasMin or hasSec: raise ValueError
    sign = -1 if minus else 1
    return YearMonthDuration(sign * int(yrs if yrs else 0), sign * int(mos if mos else 0))
    
class YearMonthDuration():
    def __init__(self, years, months):
        self.years = years
        self.months = months

    def __repr__(self):
        return "P{0}Y{1}M".format(self.years, self.months)
    
def dayTimeDuration(value):
    if isinstance(value,Time):
        return DayTimeDuration(1 if value.hour24 else 0, value.hour, value.minute, value.second)
    minus, hasYr, yrs, hasMo, mos, hasDay, days, hasTime, hasHr, hrs, hasMin, mins, hasSec, secs = durationPattern.match(value).groups()
    if hasYr or hasMo: raise ValueError
    sign = -1 if minus else 1
    return DayTimeDuration(sign * int(days if days else 0), sign * int(hrs if hrs else 0), sign * int(mins if mins else 0), sign * int(secs if secs else 0))
    
class DayTimeDuration(datetime.timedelta):
    def __new__(cls, days, hours, minutes, seconds):
        dyTm = datetime.timedelta.__new__(cls,days,hours,minutes,seconds)
        return dyTm
    def dayHrsMinsSecs(self):
        days = int(self.days)
        if days < 0 and (self.seconds > 0 or self.microseconds > 0):
            days -= 1
            seconds = 86400 - self.seconds
            if seconds > 0 and self.microseconds > 0:
                microseconds = 1000000 - self.microseconds
                seconds -= 1
            elif self.microseconds > 0:
                microseconds = 1000000 - self.microseconds
        else:
            seconds = self.seconds
            microseconds = self.microseconds
        # round up microseconds
        if microseconds >= 500000:
            seconds += 1
        hours = int(seconds / 86400 )
        if hours > 24:
            days += hours / 24
            hours = hours % 24
        seconds -= hours * 86400
        minutes = int(seconds / 60)
        seconds -= minutes * 60
        return (days, hours, minutes, seconds)
    def __repr__(self):
        x = self.dayHrsMinsSecs
        return "P{0}DT{1}H{2}M{3}S".format(x[0], x[1], x[2], x[3])
        
def time(value, castException=None):
    if value == "MinTime":
        return Time(time.min)
    elif value == "MaxTime":
        return Time(time.max)
    elif isinstance(value, ModelObject):
        value = value.text
    elif isinstance(value, datetime.time):
        return Time(value.hour, value.minute, value.second, value.microsecond, value.tzinfo)
    elif isinstance(value, datetime.datetime):
        return Time(value.hour, value.minute, value.second, value.microsecond, value.tzinfo)
    elif castException and not isinstance(value, _STR_BASE):
        raise castException
    if value is None:
        return None
    match = timePattern.match(value.strip())
    if match is None:
        return None
    return Time(int(match.group(1)),int(match.group(2)),int(match.group(3)))

class Time(datetime.time):
    def __new__(cls, hour=0, minute=0, second=0, microsecond=0, tzinfo=None):
        hour24 = (hour == 24 and minute == 0 and second == 0 and microsecond == 0)
        if hour24: hour = 0
        time = datetime.time.__new__(cls, hour, minute, second, microsecond, tzinfo)
        time.hour24 = hour24
        return time
    
class gYearMonth():
    def __init__(self, year, month):
        self.year = int(year)
        self.month = int(month)

    def __repr__(self):
        return "-{0}-{1}".format(self.year, self.month)
    
    
class gMonthDay():
    def __init__(self, month, day):
        self.month = int(month)
        self.day = int(day)

    def __repr__(self):
        return "--{0}-{1}".format(self.month, self.day)
    
class gYear():
    def __init__(self, year):
        self.year = int(year)

    def __repr__(self):
        return "{0}".format(self.year)
    
class gMonth():
    def __init__(self, month):
        self.month = int(month)

    def __repr__(self):
        return "--{0}".format(self.month)
    
class gDay():
    def __init__(self, day):
        self.day = int(day)

    def __repr__(self):
        return "---{0}".format(self.day)
    
class InvalidValue(str):
    def __new__(cls, value):
        return str.__new__(cls, value)

INVALIDixVALUE = InvalidValue("(ixTransformValueError)")

    