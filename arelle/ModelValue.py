from arelle.ModelObject import ModelObject
import re, datetime

def anyURI(value):
    return AnyURI(value)

class AnyURI(str):
    def __new__(cls, value):
        return super().__new__(cls, value)

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
    elif castException and not isinstance(value, str):
        raise castException
    if value is None:
        return None
    match = datetimePattern.match(value.strip())
    if match is None:
        if castException:
            raise castException
        return None
    if match.lastindex == 6:
        if type == DATE: 
            if castException:
                raise castException
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

class DateTime(datetime.datetime):
    def __new__(cls, y, m, d, hr=0, min=0, sec=0, microsec=0, tzinfo=None, dateOnly=None, addOneDay=None):
        if hr == 24:
            if min != 0 or sec != 0 or microsec != 0: raise ValueError
            hr = 0
            d += 1
        if addOneDay: 
            d += 1
        lastDay = lastDayOfMonth(y, m)
        if d > lastDay: d -= lastDay; m += 1
        if m > 12: m = 1; y += 1
        dateTime = super().__new__(cls, y, m, d, hr, min, sec, microsec, tzinfo)
        dateTime.dateOnly = dateOnly
        return dateTime
    def __copy__(self):
        return DateTime(self.year, self.month, self.day, self.hour, self.minute, self.second, self.microsecond, self.tzinfo, self.dateOnly)
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
        
def yearMonthDuration(value):
    minus, hasYr, yrs, hasMo, mos, hasDay, days, hasTime, hasHr, hrs, hasMin, mins, hasSec, secs = durationPattern.match(value).groups()
    if hasDay or hasHr or hasMin or hasSec: raise ValueError
    sign = -1 if minus else 1
    return YearMonthDuration(sign * int(yrs if yrs else 0), sign * int(mos if mos else 0))
    
class YearMonthDuration(object):
    def __new__(cls, years, months):
        yrMo = super().__new__(cls)
        yrMo.years = years
        yrMo.months = months
        return yrMo
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
        dyTm = super().__new__(cls,days,hours,minutes,seconds)
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
    elif castException and not isinstance(value, str):
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
        time = super().__new__(cls, hour, minute, second, microsecond, tzinfo)
        time.hour24 = hour24
        return time
    
        