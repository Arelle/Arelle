'''
Created on Dec 20, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import math, re
from arelle.ModelObject import ModelObject, ModelAttribute
from arelle.ModelValue import (qname, dateTime, DateTime, DATE, DATETIME, dayTimeDuration,
                         YearMonthDuration, DayTimeDuration, time, Time)
from arelle.FunctionUtil import anytypeArg, stringArg, numericArg, qnameArg, nodeArg
from arelle import FunctionXs, XPathContext, XbrlUtil, XmlUtil, UrlUtil, ModelDocument, XmlValidate
from lxml import etree
    
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
    x = stringArg(xc, args, 0, "item()?", missingArgFallback=contextItem, emptyFallback='')
    return str( x )

def data(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return xc.atomize(p, args[0])

def base_uri(xc, p, contextItem, args):
    # TBD
    return []

def document_uri(xc, p, contextItem, args):
    return xc.modelXbrl.modelDocument.uri

def error(xc, p, contextItem, args):
    raise fnFunctionNotAvailable()

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
    math.ceil(numericArg(xc, p, args))

def fn_floor(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    math.floor(numericArg(xc, p, args))

def fn_round(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args)
    if math.isinf(x) or math.isnan(x): 
        return x
    return int(x + .5)  # round towards +inf

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
            atomizedArgs.append( FunctionXs.xsString( xc, xc.atomize(p, item) ) )
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
    start = round( numericArg(xc, p, args, 1) ) - 1
    if l == 3:
        length = round( numericArg(xc, p, args, 2) )
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
    return ' '.join( p.findall( stringArg(xc, args, 0, "xs:string", missingArgFallback=contextItem) ) )

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
            if beforeAfter: return string.lpartition( portion )[0]
            else: return string.rpartition( portion )[2]
        except ValueError:
            return ''
    raise fnFunctionNotAvailable()  # wrong arguments?

def matches(xc, p, contextItem, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    input = stringArg(xc, args, 0, "xs:string?", emptyFallback=())
    pattern = stringArg(xc, args, 1, "xs:string", emptyFallback=())
    return bool(re.match(pattern,input))

def replace(xc, p, contextItem, args):
    if len(args) != 3: raise XPathContext.FunctionNumArgs()
    input = stringArg(xc, args, 0, "xs:string?", emptyFallback=())
    pattern = stringArg(xc, args, 1, "xs:string", emptyFallback=())
    replacement = stringArg(xc, args, 1, "xs:string", emptyFallback=())
    return input.replace(pattern,replacement)

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

nan = float('NaN')

def number(xc, p, contextItem, args):
    return numericArg(xc, p, args, missingArgFallback=contextItem, emptyFallback=nan, convertFallback=nan)

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
        if isinstance(item, int) or isinstance(item, float):
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
    return list(set(sequence))

def insert_before(xc, p, contextItem, args):
    if len(args) != 3: raise XPathContext.FunctionNumArgs()
    sequence = args[0]
    if isinstance(sequence, tuple): sequence = list(sequence)
    elif not isinstance(sequence, list): sequence = [sequence]
    index = numericArg(xc, p, args, 1, "xs:integer", convertFallback=0) - 1
    insertion = args[2]
    if isinstance(insertion, tuple): insertion = list(insertion)
    elif not isinstance(insertion, list): insertion = [insertion]
    return sequence[:index] + insertion + sequence[index:]

def remove(xc, p, contextItem, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    sequence = args[0]
    index = numericArg(xc, p, args, 1, "xs:integer", convertFallback=0) - 1
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
    start = round( numericArg(xc, p, args, 1) ) - 1
    if l == 3:
        length = round( numericArg(xc, p, args, 2) )
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
    return len(args[0]) in ( 0, 1 )

def one_or_more(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return len(args[0]) >= 1

def exactly_one(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return len(args[0]) == 1

def deep_equal(xc, p, contextItem, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    return XbrlUtil.nodesCorrespond(xc.modelXbrl, args[0], args[1])

def count(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return len(xc.flattenSequence(args[0]))

def avg(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return sum( xc.atomize( p, args[0] ) ) / len( args[0] )

def max(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return max( xc.atomize( p, args[0] ) )

def min(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return min( xc.atomize( p, args[0] ) )

def fn_sum(xc, p, contextItem, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return sum( xc.atomize( p, args[0] ) )

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
    if not UrlUtil.isValid(uri):
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
    'max': max,
    'min': min,
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
    }

