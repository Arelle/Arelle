'''
See COPYRIGHT.md for copyright information.
'''
import math, re, sre_constants
from arelle.ModelObject import ModelObject, ModelAttribute
from arelle.ModelValue import (qname, dateTime, DateTime, DATE, DATETIME, dayTimeDuration,
                         YearMonthDuration, DayTimeDuration, time, Time)
from arelle.FunctionUtil import anytypeArg, atomicArg, stringArg, numericArg, integerArg, qnameArg, nodeArg
from arelle import FunctionXs, XPathContext, XbrlUtil, XmlUtil, UrlUtil, ModelDocument, XmlValidate
from arelle.Locale import format_picture
from arelle.XmlValidate import VALID_NO_CONTENT
from decimal import Decimal
from lxml import etree
from numbers import Number

DECIMAL_5 = Decimal(.5)

class fnFunctionNotAvailable(Exception):
    def __init__(self):
        self.args =  ("fn function not available",)
    def __repr__(self):
        return self.args[0]

def call(xc, p, localname, contextItem, args):
    try:
        if localname not in fnFunctions: raise fnFunctionNotAvailable
        return fnFunctions[localname](xc, p, contextItem, args)
    except fnFunctionNotAvailable:
        raise XPathContext.FunctionNotAvailable("fn:{0}".format(localname))

def node_name(xc, p, contextItem, args):
    node = nodeArg(xc, args, 0, "node()?", missingArgFallback=contextItem, emptyFallback=())
    if node != ():
        return qname(node)
    return ()

def nilled(xc, p, contextItem, args):
    node = nodeArg(xc, args, 0, "node()?", missingArgFallback=contextItem, emptyFallback=())
    if node != () and isinstance(node,ModelObject):
        return node.get("{http://www.w3.org/2001/XMLSchema-instance}nil") == "true"
    return ()

def string(xc, p, contextItem, args):
    if len(args) > 1: raise XPathContext.FunctionNumArgs()
    item = anytypeArg(xc, args, 0, "item()?", missingArgFallback=contextItem)
    if item == ():
        return ''
    if isinstance(item, ModelObject) and getattr(item,"xValid", 0) == VALID_NO_CONTENT:
        x = item.stringValue # represents inner text of this and all subelements
    else:
        x = xc.atomize(p, item)
    return FunctionXs.xsString( xc, p, x )

def data(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return xc.atomize(p, args[0])

def base_uri(xc, p, contextItem, args):
    item = anytypeArg(xc, args, 0, "node()?", missingArgFallback=contextItem)
    if item == ():
        return ''
    if isinstance(item, (ModelObject, ModelDocument)):
        return UrlUtil.ensureUrl(item.modelDocument.uri)
    return ''

def document_uri(xc, p, contextItem, args):
    return xc.modelXbrl.modelDocument.uri

def error(xc, p, contextItem, args):
    if len(args) > 2: raise XPathContext.FunctionNumArgs()
    qn = qnameArg(xc, p, args, 0, 'QName?', emptyFallback=None)
    msg = stringArg(xc, args, 1, "xs:string", emptyFallback='')
    raise XPathContext.XPathException(p, (qn or "err:FOER0000"), msg)

def trace(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def fn_dateTime(xc, p, contextItem, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    date = anytypeArg(xc, args, 0, "xs:date", missingArgFallback=())
    time = anytypeArg(xc, args, 1, "xs:time", missingArgFallback=())
    if date is None or time is None:
        return ()
    return dateTime(date) + dayTimeDuration(time)

def fn_abs(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args)
    if math.isinf(x):
        x = float('inf')
    elif not math.isnan(x):
        x = abs(x)
    return x

def fn_ceiling(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return math.ceil(numericArg(xc, p, args))

def fn_floor(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return math.floor(numericArg(xc, p, args))

def fn_round(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args)
    if math.isinf(x) or math.isnan(x):
        return x
    return int(x + (DECIMAL_5 if isinstance(x,Decimal) else .5))  # round towards +inf

def fn_round_half_to_even(xc, p, contextItem, args):
    if len(args) > 2 or len(args) == 0: raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args)
    if len(args) == 2:
        precision = args[1]
        if len(precision) != 1 or not isinstance(precision[0],int): raise XPathContext.FunctionArgType(2,"integer")
        precision = precision[0]
        return round(x, precision)
    return round(x)

def codepoints_to_string(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    try:
        return ''.join(chr(c) for c in args[0])
    except TypeError:
        XPathContext.FunctionArgType(1,"xs:integer*")

def string_to_codepoints(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    str = stringArg(xc, args, 0, "xs:string", emptyFallback=())
    if str == (): return ()
    return tuple(ord(c) for c in str)

def compare(xc, p, contextItem, args):
    if len(args) == 3: raise fnFunctionNotAvailable()
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    comparand1 = stringArg(xc, args, 0, "xs:string?", emptyFallback=())
    comparand2 = stringArg(xc, args, 1, "xs:string?", emptyFallback=())
    if comparand1 == () or comparand2 == (): return ()
    if comparand1 == comparand2: return 0
    if comparand1 < comparand2: return -1
    return 1

def codepoint_equal(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def concat(xc, p, contextItem, args):
    if len(args) < 2: raise XPathContext.FunctionNumArgs()
    atomizedArgs = []
    for i in range(len(args)):
        item = anytypeArg(xc, args, i, "xs:anyAtomicType?")
        if item != ():
            atomizedArgs.append( FunctionXs.xsString( xc, p, xc.atomize(p, item) ) )
    return ''.join(atomizedArgs)

def string_join(xc, p, contextItem, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    joiner = stringArg(xc, args, 1, "xs:string")
    atomizedArgs = []
    for x in xc.atomize( p, args[0] ):
        if isinstance(x, str):
            atomizedArgs.append(x)
        else:
            raise XPathContext.FunctionArgType(0,"xs:string*")
    return joiner.join(atomizedArgs)

def substring(xc, p, contextItem, args):
    l = len(args)
    if l < 2 or l > 3: raise XPathContext.FunctionNumArgs()
    string = stringArg(xc, args, 0, "xs:string?")
    start = int(round( numericArg(xc, p, args, 1) )) - 1
    if l == 3:
        length = int(round( numericArg(xc, p, args, 2) ))
        if start < 0:
            length += start
            if length < 0: length = 0
            start = 0
        return string[start:start + length]
    if start < 0: start = 0
    return string[start:]

def string_length(xc, p, contextItem, args):
    if len(args) > 1: raise XPathContext.FunctionNumArgs()
    return len( stringArg(xc, args, 0, "xs:string", missingArgFallback=contextItem) )

nonSpacePattern = re.compile(r"\S+")
def normalize_space(xc, p, contextItem, args):
    if len(args) > 1: raise XPathContext.FunctionNumArgs()
    return ' '.join( nonSpacePattern.findall( stringArg(xc, args, 0, "xs:string", missingArgFallback=contextItem) ) )

def normalize_unicode(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def upper_case(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return stringArg(xc, args, 0, "xs:string").upper()

def lower_case(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return stringArg(xc, args, 0, "xs:string").lower()

def translate(xc, p, contextItem, args):
    if len(args) != 3: raise XPathContext.FunctionNumArgs()
    arg = stringArg(xc, args, 0, "xs:string?", emptyFallback=())
    mapString = stringArg(xc, args, 1, "xs:string", emptyFallback=())
    transString = stringArg(xc, args, 2, "xs:string", emptyFallback=())
    if arg == (): return ()
    out = []
    for c in arg:
        if c in mapString:
            i = mapString.index(c)
            if i < len(transString):
                out.append(transString[i])
        else:
            out.append(c)
    return ''.join(out)

def encode_for_uri(xc, p, contextItem, args):
    from urllib.parse import quote
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return quote(stringArg(xc, args, 0, "xs:string"))

def iri_to_uri(xc, p, contextItem, args):
    return encode_for_uri(xc, p, contextItem, args)

def escape_html_uri(xc, p, contextItem, args):
    return encode_for_uri(xc, p, contextItem, args)

def contains(xc, p, contextItem, args):
    return substring_functions(xc, args, contains=True)

def starts_with(xc, p, contextItem, args):
    return substring_functions(xc, args, startEnd=True)

def ends_with(xc, p, contextItem, args):
    return substring_functions(xc, args, startEnd=False)

def substring_before(xc, p, contextItem, args):
    return substring_functions(xc, args, beforeAfter=True)

def substring_after(xc, p, contextItem, args):
    return substring_functions(xc, args, beforeAfter=False)

def substring_functions(xc, args, contains=None, startEnd=None, beforeAfter=None):
    if len(args) == 3: raise fnFunctionNotAvailable()
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    string = stringArg(xc, args, 0, "xs:string?")
    portion = stringArg(xc, args, 1, "xs:string")
    if contains == True:
        return portion in string
    elif startEnd == True:
        return string.startswith(portion)
    elif startEnd == False:
        return string.endswith(portion)
    elif beforeAfter is not None:
        if portion == '': return ''
        try:
            if beforeAfter: return string.partition( portion )[0]
            else: return string.rpartition( portion )[2]
        except ValueError:
            return ''
    raise fnFunctionNotAvailable()  # wrong arguments?

def regexFlags(xc, p, args, n):
    f = 0
    flagsArg = stringArg(xc, args, n, "xs:string", missingArgFallback="", emptyFallback="")
    for c in flagsArg:
        if c == 's': f |= re.S
        elif c == 'm': f |= re.M
        elif c == 'i': f |= re.I
        elif c == 'x': f |= re.X
        else:
            raise XPathContext.XPathException(p, 'err:FORX0001', _('Regular expression interpretation flag unrecognized: {0}').format(flagsArg))
    return f

def matches(xc, p, contextItem, args):
    if not 2 <= len(args) <= 3: raise XPathContext.FunctionNumArgs()
    input = stringArg(xc, args, 0, "xs:string?", emptyFallback="")
    pattern = stringArg(xc, args, 1, "xs:string", emptyFallback="")
    try:
        return bool(re.search(pattern,input,flags=regexFlags(xc, p, args, 2)))
    except sre_constants.error as err:
        raise XPathContext.XPathException(p, 'err:FORX0002', _('fn:matches regular expression pattern error: {0}').format(err))


def replace(xc, p, contextItem, args):
    if not 3 <= len(args) <= 4: raise XPathContext.FunctionNumArgs()
    input = stringArg(xc, args, 0, "xs:string?", emptyFallback="")  # empty string is default
    pattern = stringArg(xc, args, 1, "xs:string", emptyFallback="")
    fnReplacement = stringArg(xc, args, 2, "xs:string", emptyFallback="")
    if re.findall(r"(^|[^\\])[$]|[$][^0-9]", fnReplacement):
        raise XPathContext.XPathException(p, 'err:FORX0004', _('fn:replace pattern \'$\' error in: {0}').format(fnReplacement))
    reReplacement = re.sub(r"[\\][$]", "$",
                         re.sub(r"(^|[^\\])[$]([1-9])", r"\\\2", fnReplacement))
    try:
        return re.sub(pattern,reReplacement,input,flags=regexFlags(xc, p, args, 3))
    except sre_constants.error as err:
        raise XPathContext.XPathException(p, 'err:FORX0002', _('fn:replace regular expression pattern error: {0}').format(err))

def tokenize(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def resolve_uri(xc, p, contextItem, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    relative = stringArg(xc, args, 0, "xs:string?", emptyFallback=())
    base = stringArg(xc, args, 1, "xs:string", emptyFallback=())
    return xc.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(relative,base)

def true(xc, p, contextItem, args):
    return True

def false(xc, p, contextItem, args):
    return False

def _not(xc, p, contextItem, args):
    return not boolean(xc, p, contextItem, args)

def years_from_duration(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'duration', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DayTimeDuration): return 0
    if isinstance(d, YearMonthDuration): return d.years
    raise XPathContext.FunctionArgType(1,"xs:duration")

def months_from_duration(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'duration', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DayTimeDuration): return 0
    if isinstance(d, YearMonthDuration): return d.months
    raise XPathContext.FunctionArgType(1,"xs:duration")

def days_from_duration(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'duration', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DayTimeDuration): return d.days
    if isinstance(d, YearMonthDuration): return d.dayHrsMinsSecs[0]
    raise XPathContext.FunctionArgType(1,"xs:duration")

def hours_from_duration(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'duration', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DayTimeDuration): return 0
    if isinstance(d, YearMonthDuration): return d.dayHrsMinsSecs[1]
    raise XPathContext.FunctionArgType(1,"xs:duration")

def minutes_from_duration(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'duration', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DayTimeDuration): return 0
    if isinstance(d, YearMonthDuration): return d.dayHrsMinsSecs[2]
    raise XPathContext.FunctionArgType(1,"xs:duration")

def seconds_from_duration(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'duration', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DayTimeDuration): return 0
    if isinstance(d, YearMonthDuration): return d.dayHrsMinsSecs[2]
    raise XPathContext.FunctionArgType(1,"xs:duration")

def year_from_dateTime(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'dateTime', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DateTime): return d.year
    raise XPathContext.FunctionArgType(1,"xs:dateTime")

def month_from_dateTime(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'dateTime', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DateTime): return d.month
    raise XPathContext.FunctionArgType(1,"xs:dateTime")

def day_from_dateTime(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'dateTime', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DateTime): return d.day
    raise XPathContext.FunctionArgType(1,"xs:dateTime")

def hours_from_dateTime(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'dateTime', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DateTime): return d.hour
    raise XPathContext.FunctionArgType(1,"xs:dateTime")

def minutes_from_dateTime(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'dateTime', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DateTime): return d.minute
    raise XPathContext.FunctionArgType(1,"xs:dateTime")

def seconds_from_dateTime(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'dateTime', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DateTime): return d.second
    raise XPathContext.FunctionArgType(1,"xs:dateTime")

def timezone_from_dateTime(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'dateTime', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DateTime): return d.tzinfo
    raise XPathContext.FunctionArgType(1,"xs:dateTime")

def year_from_date(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'dateTime', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DateTime): return d.year
    raise XPathContext.FunctionArgType(1,"xs:dateTime")

def month_from_date(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'dateTime', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DateTime): return d.month
    raise XPathContext.FunctionArgType(1,"xs:dateTime")

def day_from_date(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'dateTime', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DateTime): return d.day
    raise XPathContext.FunctionArgType(1,"xs:dateTime")

def timezone_from_date(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'dateTime', missingArgFallback=())
    if d == (): return d
    if isinstance(d, DateTime): return d.tzinfo
    raise XPathContext.FunctionArgType(1,"xs:dateTime")

def hours_from_time(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'time', missingArgFallback=())
    if d == (): return d
    if isinstance(d, Time): return d.hour
    raise XPathContext.FunctionArgType(1,"xs:time")

def minutes_from_time(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'time', missingArgFallback=())
    if d == (): return d
    if isinstance(d, Time): return d.minute
    raise XPathContext.FunctionArgType(1,"xs:time")

def seconds_from_time(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'time', missingArgFallback=())
    if d == (): return d
    if isinstance(d, Time): return d.second
    raise XPathContext.FunctionArgType(1,"xs:time")

def timezone_from_time(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    d = anytypeArg(xc, args, 0, 'time', missingArgFallback=())
    if d == (): return d
    if isinstance(d, Time): return d.tzinfo
    raise XPathContext.FunctionArgType(1,"xs:time")

def adjust_dateTime_to_timezone(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def adjust_date_to_timezone(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def adjust_time_to_timezone(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def resolve_QName(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def QName(xc, p, contextItem, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    ns = stringArg(xc, args, 0, "xs:string?")
    prefixedName = stringArg(xc, args, 1, "xs:string")
    return qname(ns, prefixedName)


def prefix_from_QName(xc, p, contextItem, args):
    return QName_functions(xc, p, args, prefix=True)

def local_name_from_QName(xc, p, contextItem, args):
    return QName_functions(xc, p, args, localName=True)

def namespace_uri_from_QName(xc, p, contextItem, args):
    return QName_functions(xc, p, args, namespaceURI=True)

def QName_functions(xc, p, args, prefix=False, localName=False, namespaceURI=False):
    qn = qnameArg(xc, p, args, 0, 'QName?', emptyFallback=())
    if qn != ():
        if prefix: return qn.prefix
        if localName: return qn.localName
        if namespaceURI: return qn.namespaceURI
    return ()

def namespace_uri_for_prefix(xc, p, contextItem, args):
    prefix = nodeArg(xc, args, 0, 'string?', emptyFallback='')
    node = nodeArg(xc, args, 1, 'element()', emptyFallback=())
    if node is not None and isinstance(node,ModelObject):
        return XmlUtil.xmlns(node, prefix)
    return ()

def in_scope_prefixes(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def name(xc, p, contextItem, args):
    return Node_functions(xc, contextItem, args, name=True)

def local_name(xc, p, contextItem, args):
    return Node_functions(xc, contextItem, args, localName=True)

def namespace_uri(xc, p, contextItem, args):
    return Node_functions(xc, contextItem, args, namespaceURI=True)

def Node_functions(xc, contextItem, args, name=None, localName=None, namespaceURI=None):
    node = nodeArg(xc, args, 0, 'node()?', missingArgFallback=contextItem, emptyFallback=())
    if node != () and isinstance(node, ModelObject):
        if name: return node.prefixedName
        if localName: return node.localName
        if namespaceURI: return node.namespaceURI
    return ''

NaN = float('NaN')

def number(xc, p, contextItem, args):
    # TBD: add argument of type of number to convert to (fallback is float)
    n = numericArg(xc, p, args, missingArgFallback=contextItem, emptyFallback=NaN, convertFallback=NaN)
    return float(n)

def lang(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def root(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def boolean(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    inputSequence = args[0]
    if inputSequence is None or len(inputSequence) == 0:
        return False
    item = inputSequence[0]
    if isinstance(item, (ModelObject, ModelAttribute, etree._ElementTree)):
        return True
    if len(inputSequence) == 1:
        if isinstance(item, bool):
            return item
        if isinstance(item, str):
            return len(item) > 0
        if isinstance(item, Number):
            return not math.isnan(item) and item != 0
    raise XPathContext.XPathException(p, 'err:FORG0006', _('Effective boolean value indeterminate'))

def index_of(xc, p, contextItem, args):
    if len(args) == 3: raise fnFunctionNotAvailable()
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    seq = xc.atomize(p, args[0])
    srch = xc.atomize(p, args[1])
    if isinstance(srch,(tuple,list)):
        if len(srch) != 1: raise XPathContext.FunctionArgType(1,'xs:anyAtomicType')
        srch = srch[0]
    indices = []
    pos = 0
    for x in seq:
        pos += 1
        if x == srch:
            indices.append(pos)
    return indices

def empty(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return len(xc.flattenSequence(args[0])) == 0

def exists(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return len(xc.flattenSequence(args[0])) > 0

def distinct_values(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    sequence = args[0]
    if len(sequence) == 0: return []
    return list(set(xc.atomize(p, sequence)))

def insert_before(xc, p, contextItem, args):
    if len(args) != 3: raise XPathContext.FunctionNumArgs()
    sequence = args[0]
    if isinstance(sequence, tuple): sequence = list(sequence)
    elif not isinstance(sequence, list): sequence = [sequence]
    index = integerArg(xc, p, args, 1, "xs:integer", convertFallback=0) - 1
    insertion = args[2]
    if isinstance(insertion, tuple): insertion = list(insertion)
    elif not isinstance(insertion, list): insertion = [insertion]
    return sequence[:index] + insertion + sequence[index:]

def remove(xc, p, contextItem, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    sequence = args[0]
    index = integerArg(xc, p, args, 1, "xs:integer", convertFallback=0) - 1
    return sequence[:index] + sequence[index+1:]

def reverse(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    sequence = args[0]
    if len(sequence) == 0: return []
    return list( reversed(sequence) )

def subsequence(xc, p, contextItem, args):
    if len(args) not in (2,3): raise XPathContext.FunctionNumArgs()
    l = len(args)
    if l < 2 or l > 3: raise XPathContext.FunctionNumArgs()
    sequence = args[0]
    start = int(round( numericArg(xc, p, args, 1) )) - 1
    if l == 3:
        length = int(round( numericArg(xc, p, args, 2) ))
        if start < 0:
            length += start
            if length < 0: length = 0
            start = 0
        return sequence[start:start + length]
    if start < 0: start = 0
    return sequence[start:]

def unordered(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return args[0]

def zero_or_one(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) > 1:
        raise XPathContext.FunctionNumArgs(errCode='err:FORG0003',
                                           errText=_('fn:zero-or-one called with a sequence containing more than one item'))
    return args[0]

def one_or_more(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) < 1:
        raise XPathContext.FunctionNumArgs(errCode='err:FORG0004',
                                           errText=_('fn:one-or-more called with a sequence containing no items'))
    return args[0]

def exactly_one(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) != 1:
        raise XPathContext.FunctionNumArgs(errCode='err:FORG0005',
                                           errText=_('fn:exactly-one called with a sequence containing zero or more than one item'))
    return args[0]

def deep_equal(xc, p, contextItem, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    return XbrlUtil.nodesCorrespond(xc.modelXbrl, args[0], args[1])

def count(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return len(xc.flattenSequence(args[0]))

def avg(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    addends = xc.atomize( p, args[0] )
    try:
        l = len(addends)
        if l == 0:
            return ()  # xpath allows empty sequence argument
        hasFloat = False
        hasDecimal = False
        for a in addends:
            if math.isnan(a) or math.isinf(a):
                return NaN
            if isinstance(a, float):
                hasFloat = True
            elif isinstance(a, Decimal):
                hasDecimal = True
        if hasFloat and hasDecimal: # promote decimals to float
            addends = [float(a) if isinstance(a, Decimal) else a
                       for a in addends]
        return sum( addends ) / len( args[0] )
    except TypeError:
        raise XPathContext.FunctionArgType(1,"sumable values", addends, errCode='err:FORG0001')

def fn_max(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    comparands = xc.atomize( p, args[0] )
    try:
        if len(comparands) == 0:
            return ()  # xpath allows empty sequence argument
        if any(isinstance(c, float) and math.isnan(c) for c in comparands):
            return NaN
        return max( comparands )
    except TypeError:
        raise XPathContext.FunctionArgType(1,"comparable values", comparands, errCode='err:FORG0001')

def fn_min(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    comparands = xc.atomize( p, args[0] )
    try:
        if len(comparands) == 0:
            return ()  # xpath allows empty sequence argument
        if any(isinstance(c, float) and math.isnan(c) for c in comparands):
            return NaN
        return min( comparands )
    except TypeError:
        raise XPathContext.FunctionArgType(1,"comparable values", comparands, errCode='err:FORG0001')

def fn_sum(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    addends = xc.atomize( p, args[0] )
    try:
        if len(addends) == 0:
            return 0  # xpath allows empty sequence argument
        hasFloat = False
        hasDecimal = False
        for a in addends:
            if math.isnan(a):
                return NaN
            if isinstance(a, float):
                hasFloat = True
            elif isinstance(a, Decimal):
                hasDecimal = True
        if hasFloat and hasDecimal: # promote decimals to float
            addends = [float(a) if isinstance(a, Decimal) else a
                       for a in addends]
        return sum( addends )
    except TypeError:
        raise XPathContext.FunctionArgType(1,"summable sequence", addends, errCode='err:FORG0001')

def id(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def idref(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def doc(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    uri = stringArg(xc, args, 0, "xs:string", emptyFallback=None)
    if uri is None:
        return ()
    if xc.progHeader is None or xc.progHeader.element is None:
        raise XPathContext.XPathException(p, 'err:FODC0005', _('Function xf:doc no formula resource element for {0}').format(uri))
    if not UrlUtil.isValidUriReference(uri):
        raise XPathContext.XPathException(p, 'err:FODC0005', _('Function xf:doc $uri is not valid {0}').format(uri))
    normalizedUri = xc.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(
                                uri,
                                xc.progHeader.element.modelDocument.baseForElement(xc.progHeader.element))
    if normalizedUri in xc.modelXbrl.urlDocs:
        return xc.modelXbrl.urlDocs[normalizedUri].xmlDocument
    modelDocument = ModelDocument.load(xc.modelXbrl, normalizedUri)
    if modelDocument is None:
        raise XPathContext.XPathException(p, 'err:FODC0005', _('Function xf:doc $uri not successfully loaded {0}').format(uri))
    # assure that document is validated
    XmlValidate.validate(xc.modelXbrl, modelDocument.xmlRootElement)
    return modelDocument.xmlDocument

def doc_available(xc, p, contextItem, args):
    return isinstance(doc(xc, p, contextItem, args), etree._ElementTree)

def collection(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def position(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def last(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

def current_dateTime(xc, p, contextItem, args):
    from datetime import datetime
    return dateTime(datetime.now(), type=DATETIME)

def current_date(xc, p, contextItem, args):
    from datetime import date
    return dateTime(date.today(), type=DATE)

def current_time(xc, p, contextItem, args):
    from datetime import datetime
    return time(datetime.now())

def implicit_timezone(xc, p, contextItem, args):
    from datetime import datetime
    return datetime.now().tzinfo

def default_collation(xc, p, contextItem, args):
    # only unicode is supported
    return "http://www.w3.org/2005/xpath-functions/collation/codepoint"

def static_base_uri(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

# added in XPATH 3
def  format_number(xc, p, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    value = numericArg(xc, p, args, 0, missingArgFallback='NaN', emptyFallback='NaN')
    picture = stringArg(xc, args, 1, "xs:string", missingArgFallback='', emptyFallback='')
    try:
        return format_picture(xc.modelXbrl.locale, value, picture)
    except ValueError as err:
        raise XPathContext.XPathException(p, 'err:FODF1310', str(err) )

fnFunctions = {
    'node-name': node_name,
    'nilled': nilled,
    'string': string,
    'data': data,
    'base-uri': base_uri,
    'document-uri': document_uri,
    'error': error,
    'trace': trace,
    'dateTime': fn_dateTime,
    'abs': fn_abs,
    'ceiling': fn_ceiling,
    'floor': fn_floor,
    'round': fn_round,
    'round-half-to-even': fn_round_half_to_even,
    'codepoints-to-string': codepoints_to_string,
    'string-to-codepoints': string_to_codepoints,
    'compare': compare,
    'codepoint-equal': codepoint_equal,
    'concat': concat,
    'string-join': string_join,
    'substring': substring,
    'string-length': string_length,
    'normalize-space': normalize_space,
    'normalize-unicode': normalize_unicode,
    'upper-case': upper_case,
    'lower-case': lower_case,
    'translate': translate,
    'encode-for-uri': encode_for_uri,
    'iri-to-uri': iri_to_uri,
    'escape-html-uri': escape_html_uri,
    'contains': contains,
    'starts-with': starts_with,
    'ends-with': ends_with,
    'substring-before': substring_before,
    'substring-after': substring_after,
    'matches': matches,
    'replace': replace,
    'tokenize': tokenize,
    'resolve-uri': resolve_uri,
    'true': true,
    'false': false,
    'not': _not,
    'years-from-duration': years_from_duration,
    'months-from-duration': months_from_duration,
    'days-from-duration': days_from_duration,
    'hours-from-duration': hours_from_duration,
    'minutes-from-duration': minutes_from_duration,
    'seconds-from-duration': seconds_from_duration,
    'year-from-dateTime': year_from_dateTime,
    'month-from-dateTime': month_from_dateTime,
    'day-from-dateTime': day_from_dateTime,
    'hours-from-dateTime': hours_from_dateTime,
    'minutes-from-dateTime': minutes_from_dateTime,
    'seconds-from-dateTime': seconds_from_dateTime,
    'timezone-from-dateTime': timezone_from_dateTime,
    'year-from-date': year_from_date,
    'month-from-date': month_from_date,
    'day-from-date': day_from_date,
    'timezone-from-date': timezone_from_date,
    'hours-from-time': hours_from_time,
    'minutes-from-time': minutes_from_time,
    'seconds-from-time': seconds_from_time,
    'timezone-from-time': timezone_from_time,
    'adjust-dateTime-to-timezone': adjust_dateTime_to_timezone,
    'adjust-date-to-timezone': adjust_date_to_timezone,
    'adjust-time-to-timezone': adjust_time_to_timezone,
    'resolve-QName': resolve_QName,
    'QName': QName,
    'prefix-from-QName': prefix_from_QName,
    'local-name-from-QName': local_name_from_QName,
    'namespace-uri-from-QName': namespace_uri_from_QName,
    'namespace-uri-for-prefix': namespace_uri_for_prefix,
    'in-scope-prefixes': in_scope_prefixes,
    'name': name,
    'local-name': local_name,
    'namespace-uri': namespace_uri,
    'number': number,
    'lang': lang,
    'root': root,
    'boolean': boolean,
    'index-of': index_of,
    'empty': empty,
    'exists': exists,
    'distinct-values': distinct_values,
    'insert-before': insert_before,
    'remove': remove,
    'reverse': reverse,
    'subsequence': subsequence,
    'unordered': unordered,
    'zero-or-one': zero_or_one,
    'one-or-more': one_or_more,
    'exactly-one': exactly_one,
    'deep-equal': deep_equal,
    'count': count,
    'avg': avg,
    'max': fn_max,
    'min': fn_min,
    'sum': fn_sum,
    'id': id,
    'idref': idref,
    'doc': doc,
    'doc-available': doc_available,
    'collection': collection,
    'position': position,
    'last': last,
    'current-dateTime': current_dateTime,
    'current-date': current_date,
    'current-time': current_time,
    'implicit-timezone': implicit_timezone,
    'default-collation': default_collation,
    'static-base-uri': static_base_uri,
    'format-number': format_number,
    }
