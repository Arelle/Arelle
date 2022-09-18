'''
cdrMethods processes the CDR formula functions in the context of an XBRL DTS and instance.

For description of CDR formula see: http://http://www.ffiec.gov/find/taxonomy/call_report_taxonomy.html

(c) Copyright 2014 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).
'''

from math import exp, fabs, isinf, isnan, log, log10, pow, sqrt
import datetime
from arelle.ModelDtsObject import ModelConcept, ModelRelationship
from arelle.ModelDocument import Type
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelValue import QName, dayTimeDuration, DayTimeDuration
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrlCalcs import inferredDecimals, inferredPrecision, roundValue
from arelle import XbrlConst, XmlUtil
evaluate = None # initialized at end
CdrException = None
UNBOUND = None
NONE = None

def moduleInit():
    global evaluate, CdrException, UNBOUND, NONE
    from .cdrEvaluator import evaluate, CdrException, UNBOUND, NONE

class Balance(): # fake class for balance type
    pass

class PeriodType(): # fake class for period type
    pass

class Period():
    def __init__(self, start=None, end=None):
        self.start = start
        self.end = end
    @property
    def isForever(self):
        return self.start is None and self.end is None
    @property
    def isInstant(self):
        return self.start is None and self.end is not None
    @property
    def isStartEnd(self):
        return self.start is not None and self.end is not None
    def __repr__(self):
        return "({0},{1})".format(self.start, self.end)
    def __eq__(self, other):
        if isinstance(other, Period):
            return self.start == other.start and self.end == other.end
        return False
    def __ne__(self, other):
        if isinstance(other, Period):
            return self.start != other.start or self.end != other.end
        return False
    def __lt__(self, other):
        if not isinstance(other, Period):
            return False
        if self.isInstant:
            if other.isInstant:
                return self.end < other.end
            elif other.isStartEnd:
                return self.end <= other.start
        elif self.isStartEnd:
            if other.isInstant:
                return self.end < other.end
            elif other.isStartEnd:
                return self.end <= other.start
        return False
    def __le__(self, other):
        if not isinstance(other, Period):
            return False
        if self.isInstant:
            if other.isInstant:
                return self.end <= other.end
            elif other.isStartEnd:
                return self.end <= other.start or self == other
        elif self.isStartEnd:
            if other.isInstant:
                return self.end <= other.end
            elif other.isStartEnd:
                return self.end <= other.start or self == other
        return False
    def __gt__(self, other):
        if not isinstance(other, Period):
            return False
        if self.isInstant:
            if other.isInstant:
                return self.end > other.end
            elif other.isStartEnd:
                return self.start > other.end
        elif self.isStartEnd:
            if other.isInstant:
                return self.end > other.end
            elif other.isStartEnd:
                return self.start > other.end
        return False
    def __ge__(self, other):
        if not isinstance(other, Period):
            return False
        if self.isInstant:
            if other.isInstant:
                return self.end >= other.end
            elif other.isStartEnd:
                return self.start >= other.start or self == other
        elif self.isStartEnd:
            if other.isInstant:
                return self.end >= other.end
            elif other.isStartEnd:
                return self.start >= other.start or self == other
        return False


def hasArg(node, cdrContext, args, i):
    if i >= len(args):
        raise CdrException(node, "sphinx.functionArgumentsMismatch",
                              _("Function %(name)s requires %(required)s parameters but %(provided)s are provided"),
                                name=node.name, required=i, provided=len(node.args))

def numericArg(node, cdrContext, args, i):
    hasArg(node, cdrContext, args, i)
    arg = args[i]
    if isinstance(arg, _NUM_TYPES):
        return arg
    raise CdrException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s numeric parameter %(num)s is not a number: %(value)s"),
                          name=node.name, num=i, value=arg)
    
def numericArgs(node, cdrContext, args, expectedArgsLen):
    if expectedArgsLen != len(args):
        raise CdrException(node, "sphinx.functionArgumentsMismatch",
                              _("Function %(name)s requires %(required)s parameters but %(provided)s are provided"),
                              name=node.name, required=expectedArgsLen, provided=len(args))
    numArgs = []
    for i, arg in enumerate(args):
        if i >= expectedArgsLen:
            break
        value = evaluate(arg, cdrContext, args, value=True)
        if not isinstance(value, _NUM_TYPES):
            raise CdrException(node, "sphinx.functionArgumentsMismatch",
                                  _("Function %(name)s numeric parameters but %(num)s is not numeric: %(value)s"),
                                  num=i, value=value)
            value = 0
        numArgs.append(value)
    for i in range(i, expectedArgsLen):
        numArgs.append(0)
    return numArgs
    
def strArg(node, cdrContext, args, i):
    hasArg(node, cdrContext, args, i)
    arg = args[i]
    if isinstance(arg, str):
        return arg
    raise CdrException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s string parameter %(num)s is not a string: %(value)s"),
                          name=node.name, num=i, value=arg)
    
def strArgs(node, cdrContext, args, expectedArgsLen):
    if expectedArgsLen != len(args):
        raise CdrException(node, "sphinx.functionArgumentsMismatch",
                              _("Function %(name)s requires %(required)s parameters but %(provided)s are provided"),
                              name=node.name, required=expectedArgsLen, provided=len(args))
    strArgs = []
    for i, arg in enumerate(args):
        if i >= expectedArgsLen:
            break
        value = evaluate(arg, cdrContext, value=True)
        if not isinstance(value, _STR_BASE):
            raise CdrException(node, "sphinx.functionArgumentsMismatch",
                                  _("Function %(name)s string parameters but %(num)s is not numeric: %(value)s"),
                                  name=node.name, num=i, value=value)
            value = 0
        strArgs.append(value)
    for i in range(i, expectedArgsLen):
        strArgs.append(0)
    return strArgs
    
def datetimeArg(node, cdrContext, args, i):
    hasArg(node, cdrContext, args, i)
    arg = args[i]
    if isinstance(arg, datetime.datetime):
        return arg
    raise CdrException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s datetime parameter %(num)s is not a datetime: %(value)s"),
                          name=node.name, num=i, value=arg)
    
def factArg(node, cdrContext, args, i):
    hasArg(node, cdrContext, args, i)
    fact = evaluate(args[i], cdrContext, value=False, hsBoundFact=True)
    if isinstance(fact, ModelFact):
        return fact
    raise CdrException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s fact parameter %(num)s is not a fact: %(value)s"),
                          name=node.name,
                          num=i, value=fact)


# numeric functions
NaN = float("NaN")
POSINF = float("INF")
NEGINF = float("-INF")

def _abs(node, cdrContext, args):
    args = numericArgs(node, cdrContext, args, 1)
    return fabs(args[0])
    
def _avg(node, cdrContext, args):
    sum = 0
    for i in len(args):
        sum += numericArgs(node, cdrContext, args, i)
    if len(args) > 0:
        return sum / len(args)
    return 0
    
def _concatenate(node, cdrContext, args):
    value1 = strArgs(node, cdrContext, args, 0)
    value2 = strArgs(node, cdrContext, args, 1)
    return value1 + value2
       
       
def _contextPeriodType(node, cdrContext, args):
    fact = factArg(node, cdrContext, args, 0)
    context = fact.context
    if context is not None:
        if context.isInstantPeriod:
            return "Instant"
        elif context.isStartEndPeriod:
            return "Duration"
        else:
            return "Forever"
    return None

       
def _contextPeriodEndDate(node, cdrContext, args):
    fact = factArg(node, cdrContext, args, 0)
    context = fact.context
    if context is not None:
        #return XmlUtil.dateunionValue(context.endDatetime, subtractOneDay=True)
        return context.endDatetime 
    return None

def _contextPeriodStartDate(node, cdrContext, args):
    fact = factArg(node, cdrContext, args, 0)
    context = fact.context
    if context is not None:
        #return XmlUtil.dateunionValue(context.startDatetime)
        return context.startDatetime
    return None

def _currnetPeriodEndDate(node, cdrContext, args):
    hasArg(node, cdrContext, args, 0)
    arg = args[0]
    if isinstance(arg, Period):
        if arg.isForever:
            return UNBOUND
        return arg.end
    raise CdrException(node, "cdrFormula.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a period %(value)s"),
                          name=node.name, value=arg)    

def _date(node, cdrContext, args):
    year = numericArg(node, cdrContext, args, 0)
    month = numericArg(node, cdrContext, args, 1)
    day = numericArg(node, cdrContext, args, 2)
    return datetime.datetime(year, month, day)
    
def _dateToString(node, cdrContext, args):
    value = datetimeArg(node, cdrContext, args, 0)
    fmt = strArg(node, cdrContext, args, 1)
    pyFmt = fmt.replace("yyyy", "%Y").replace('yy', "%y") \
               .replace("MM", "%m") \
               .replace("DD", "%d")
    return value.strftime(pyFmt)
    
def _dateValue(node, cdrContext, args):
    value = datetimeArg(node, cdrContext, args, 0)
    return (value - datetime.datetime(1899,12,30)).days # produces same number as excel
    
def _dayOf(node, cdrContext, args):
    value = datetimeArg(node, cdrContext, args, 0)
    return value.day
    
def _exists(node, cdrContext, args):
    hasArg(node, cdrContext, args, 0)
    fact = evaluate(args[0], cdrContext, value=False, hsBoundFact=True)
    if isinstance(fact, ModelFact):
        return True
    return False

def _existsNonNil(node, cdrContext, args):
    hasArg(node, cdrContext, args, 0)
    fact = evaluate(args[0], cdrContext, value=False, hsBoundFact=True)
    if isinstance(fact, ModelFact) and not fact.isNil:
        return True
    return False

def _exact(node, cdrContext, args):
    value1 = strArgs(node, cdrContext, args, 0)
    value2 = strArgs(node, cdrContext, args, 1)
    return value1 == value2

def _existsNonEmpty(node, cdrContext, args):
    hasArg(node, cdrContext, args, 0)
    fact = evaluate(args[0], cdrContext, value=False, hsBoundFact=True)
    if isinstance(fact, ModelFact) and not fact.isNil and fact.xValue:
        return True
    return False

def _existingOf(node, cdrContext, args):
    for arg in args:
        fact = evaluate(arg, cdrContext, value=False, hsBoundFact=True)
        if isinstance(fact, ModelFact):
            return fact
    return None

def _false(node, cdrContext, args):
    return False
       
def _if(node, cdrContext, args):
    test = numericArgs(node, cdrContext, args, 0)
    if test:
        return args[1]
    else:
        return args[2]
    
def _int(node, cdrContext, args):
    fact = factArg(node, cdrContext, args, 0)
    if fact is not None:
        return int(float(fact.xValue))
    return 0
       
def _left(node, cdrContext, args):
    value = strArgs(node, cdrContext, args, 0)
    len = numericArg(node, cdrContext, args, 1)
    return value[0:len]
       
def _len(node, cdrContext, args):
    value = strArgs(node, cdrContext, args, 0)
    return len(value)
       
def _lower(node, cdrContext, args):
    value = strArgs(node, cdrContext, args, 0)
    return value.lower()
       
def _max(node, cdrContext, args):
    value1 = numericArg(node, cdrContext, args, 0)
    value2 = numericArg(node, cdrContext, args, 1)
    return max(value1, value2)
       
def _mid(node, cdrContext, args):
    value = strArgs(node, cdrContext, args, 0)
    start = numericArg(node, cdrContext, args, 1)
    len = numericArg(node, cdrContext, args, 2)
    return value[start:start+len]
       
def _min(node, cdrContext, args):
    value1 = numericArg(node, cdrContext, args, 0)
    value2 = numericArg(node, cdrContext, args, 1)
    return min(value1, value2)
       
def _monthOf(node, cdrContext, args):
    value = datetimeArg(node, cdrContext, args, 0)
    return value.month
    
def _not(node, cdrContext, args):
    test = numericArgs(node, cdrContext, args, 0)
    return args[1] if test else args[2]
       
def _power(node, cdrContext, args):
    number = numericArg(node, cdrContext, args, 0)
    power = numericArg(node, cdrContext, args, 1)
    return pow(number,power)
       
def _proper(node, cdrContext, args):
    value = strArgs(node, cdrContext, args, 0)
    return value.title()

def _right(node, cdrContext, args):
    value = strArgs(node, cdrContext, args, 0)
    len = numericArg(node, cdrContext, args, 1)
    return value[-len:]
       
def _round(node, cdrContext, args):
    fact = factArg(node, cdrContext, args, 0)
    decimals = numericArg(node, cdrContext, args, 1)
    if fact is not None:
        return round(fact.xValue, decimals)
    return 0
       
def _replace(node, cdrContext, args):
    value = strArgs(node, cdrContext, args, 0)
    start = numericArg(node, cdrContext, args, 1)
    numChars = numericArg(node, cdrContext, args, 2)
    new = strArgs(node, cdrContext, args, 3)
    return value[0:start-1] + new + value[start + numChars - 1:]
       
def _search(node, cdrContext, args):
    pattern = strArgs(node, cdrContext, args, 0).lower()
    value = strArgs(node, cdrContext, args, 1).lower()
    return value.find(pattern)
    
def _sign(node, cdrContext, args):
    value = numericArg(node, cdrContext, args, 0)
    if value < 0:
        return -1
    return 1
       
def _sqrt(node, cdrContext, args):
    fact = factArg(node, cdrContext, args, 0)
    if fact is not None:
        return sqrt(fact.xValue)
    return 0
       
def _substitute(node, cdrContext, args):
    value = strArgs(node, cdrContext, args, 0)
    old = strArgs(node, cdrContext, args, 1)
    new = strArgs(node, cdrContext, args, 2)
    if len(args) > 3:
        instanceNum = numericArg(node, cdrContext, args, 3)
        start = 0
        for i in range(1, instanceNum):
            start = value.find(old, start)
            if start >= 0:
                if instanceNum == i:
                    return value[0:start] + new + value[start + len(old):]
                else:
                    start += len(old)
    return value
       
def _trim(node, cdrContext, args):
    value = strArgs(node, cdrContext, args, 0)
    return value.strip()

def _true(node, cdrContext, args):
    return True
       
def _truncate(node, cdrContext, args):
    fact = factArg(node, cdrContext, args, 0)
    if len(args) > 1:
        digits = numericArg(node, cdrContext, args, 1)
    else:
        digits = 0
    if fact is not None:
        v = fact.value
        if digits == 0:
            return int(v)
        return v - v % (10 ** -digits)
    return 0
       
def _upper(node, cdrContext, args):
    value = strArgs(node, cdrContext, args, 0)
    return value.upper()

def _value(node, cdrContext, args):
    fact = factArg(node, cdrContext, args, 0)
    if fact is not None:
        return float(fact.xValue)
    return 0
       
def _yearOf(node, cdrContext, args):
    value = datetimeArg(node, cdrContext, args, 0)
    return value.year
    
    

# miscellaneous methods    
    
def _notImplemented(node, cdrContext, args):
    cdrContext.modelXbrl.log("ERROR", "cdrFormula.functionNotImplemented",
                                _("Function %(name)s is not currently implemented"),
                                sourceFileLine=node.sourceFileLine,
                                name=node.name)
    return NaN
    
functionImplementation = {
    "if":             _if,
    "not":            _not,
    "true":           _true,
    "false":          _false,
    
    "exists":         _exists,
    "existsnonnil":   _existsNonNil,
    "existsnonempty": _existsNonEmpty,
    "existingof":     _existingOf,
    "context.period.type":      _contextPeriodType,
    "context.period.startdate": _contextPeriodStartDate,
    "context.period.enddate":   _contextPeriodEndDate,
    
    "yearof":         _yearOf,
    "monthof":        _monthOf,
    "dayof":          _dayOf,
    "datetostring":   _dateToString,
    "datevalue":      _dateValue,
    "date":           _date,
    
                        
    "abs":            _abs,
    "round":          _round,
    "truncate":       _truncate,
    "trunc":          _truncate,
    "int":            _int,
    "sqrt":           _sqrt,
    "min":            _min,
    "max":            _max,
    "sign":           _sign,
    "power":          _power,
    "avg":            _avg,
    
    "len":            _len,
    "left":           _left,
    "right":          _right,
    "concatenate":    _concatenate,
    "mid":            _mid,
    "trim":           _trim,
    "replace":        _replace,
    "substitute":     _substitute,
    "search":         _search,
    "exact":          _exact,
    "upper":          _upper,
    "lower":          _lower,
    "proper":         _proper,
    "value":          _value,

    
    

    }



