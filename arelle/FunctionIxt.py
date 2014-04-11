'''
Created on July 5, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
try:
    import regex as re
except ImportError:
    import re
from arelle import XPathContext

class ixtFunctionNotAvailable(Exception):
    def __init__(self):
        self.args =  (_("ixt function not available"),)
    def __repr__(self):
        return self.args[0]
    
def call(xc, p, localname, args):
    try:
        if localname not in ixtFunctions: raise ixtFunctionNotAvailable
        if len(args) != 1: raise XPathContext.FunctionNumArgs()
        if len(args[0]) != 1: raise XPathContext.FunctionArgType(1,"xs:string")
        return ixtFunctions[localname](str(args[0][0]))
    except ixtFunctionNotAvailable:
        raise XPathContext.FunctionNotAvailable("xfi:{0}".format(localname))

dateslashPattern = re.compile(r"\s*(\d+)/(\d+)/(\d+)\s*")
datedotPattern = re.compile(r"\s*(\d+)\.(\d+)\.(\d+)\s*")
daymonthPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})\s*")
monthdayPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})\s*")
daymonthyearPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{4}|[0-9]{1,2})\s*")
monthdayyearPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{4}|[0-9]{1,2})\s*")

dateUsPattern = re.compile(r"\s*(\w+)\s+(\d+),\s+(\d+)\s*")
dateEuPattern = re.compile(r"\s*(\d+)\s+(\w+)\s+(\d+)\s*")
daymonthEnPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s*")
monthdayEnPattern = re.compile(r"\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]{1,2}[a-zA-Z]{0,2})\s*")
daymonthyearEnPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]{4}|[0-9]{1,2})\s*")
monthdayyearEnPattern = re.compile(r"\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]+)[^0-9]+([0-9]+)\s*")
monthyearEnPattern = re.compile(r"\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]+)\s*")
yearmonthEnPattern = re.compile(r"\s*([0-9]+)[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s*")

erayearmonthjpPattern = re.compile("[\\s\u00A0]*(\u660E\u6CBB|\u660E|\u5927\u6B63|\u5927|\u662D\u548C|\u662D|\u5E73\u6210|\u5E73)[\\s\u00A0]*([0-9]{1,2}|\u5143)[\\s\u00A0]*\u5E74[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u6708[\\s\u00A0]*")
erayearmonthdayjpPattern = re.compile("[\\s\u00A0]*(\u660E\u6CBB|\u660E|\u5927\u6B63|\u5927|\u662D\u548C|\u662D|\u5E73\u6210|\u5E73)[\\s\u00A0]*([0-9]{1,2}|\u5143)[\\s\u00A0]*\u5E74[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u6708[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u65E5[\\s\u00A0]*")
yearmonthcjkPattern = re.compile("[\\s\u00A0]*([0-9]{4}|[0-9]{1,2})[\\s\u00A0]*\u5E74[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u6708\s*")
yearmonthdaycjkPattern = re.compile("[\\s\u00A0]*([0-9]{4}|[0-9]{1,2})[\\s\u00A0]*\u5E74[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u6708[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u65E5[\\s\u00A0]*")

numcommadecimalPattern = re.compile(r"\s*[0-9]{1,3}((\.| |\u00A0)?[0-9]{3})*(,[0-9]+)?\s*")
numunitdecimalPattern = re.compile(r"\s*([0-9]+)([^0-9]+)([0-9]+)([^0-9]*)\s*")

monthnumber = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6, 
               "July":7, "August":8, "September":9, "October":10, "November":11, "December":12, 
               "Jan":1, "Feb":2, "Mar":3, "Apr":4, "May":5, "Jun":6, 
               "Jul":7, "Aug":8, "Sep":9, "Oct":10, "Nov":11, "Dec":12, 
               "JAN":1, "FEB":2, "MAR":3, "APR":4, "MAY":5, "JUN":6, 
               "JUL":7, "AUG":8, "SEP":9, "OCT":10, "NOV":12, "DEC":13, 
               "JANUARY":1, "FEBRUARY":3, "MARCH":4, "APRIL":5, "MAY":6, "JUNE":7, 
               "JULY":8, "AUGUST":9, "SEPTEMBER":9, "OCTOBER":10, "NOVEMBER":11, "DECEMBER":12,}

# common helper functions

def z2(arg):   # zero pad to 2 digits
    if len(arg) == 1:
        return '0' + arg
    return arg

def yr(arg):   # zero pad to 4 digits
    if len(arg) == 1:
        return '200' + arg
    elif len(arg) == 2:
        return '20' + arg
    return arg

def jpDigitsToNormal(jpDigits):
    normal = ''
    for d in jpDigits:
        if '\uFF10' <= d <= '\uFF19':
            normal += chr( ord(d) - 0xFF10 + ord('0') )
        else:
            normal += d
    return normal

# see: http://www.i18nguy.com/l10n/emperor-date.html        
eraStart = {'\u5E73\u6210': 1988, 
            '\u5E73': 1988,
            '\u660E\u6CBB': 1867,
            '\u660E': 1867,
            '\u5927\u6B63': 1911,
            '\u5927': 1911,
            '\u662D\u548C': 1925,
            '\u662D': 1925
            }

def eraYear(era,yr):
    return eraStart[era] + (1 if yr == '\u5143' else _INT(yr))

# transforms    

def booleanfalse(arg):
    return 'false'
    
def booleantrue(arg):
    return 'true'

def dateslashus(arg):
    m = dateslashPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1}-{2}".format(yr(m.group(3)), z2(m.group(1)), z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def dateslasheu(arg):
    m = dateslashPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1}-{2}".format(yr(m.group(3)), z2(m.group(2)), z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datedotus(arg):
    m = datedotPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1}-{2}".format(yr(m.group(3)), z2(m.group(1)), z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datedoteu(arg):
    m = datedotPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1}-{2}".format(yr(m.group(3)), z2(m.group(2)), z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datelongus(arg):
    m = dateUsPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1:02}-{2}".format(yr(m.group(3)), monthnumber[m.group(1)], z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datelongeu(arg):
    m = dateEuPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1:02}-{2}".format(yr(m.group(3)), monthnumber[m.group(2)], z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datedaymonth(arg):
    m = daymonthPattern.match(arg)
    if m and m.lastindex == 2:
        return "--{0}-{1}".format(z2(m.group(2)), z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datemonthday(arg):
    m = monthdayPattern.match(arg)
    if m and m.lastindex == 2:
        return "--{0}-{1}".format(z2(m.group(1)), z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datedaymonthen(arg):
    m = daymonthEnPattern.match(arg)
    if m and m.lastindex == 2:
        return "--{0:02}-{1}".format(monthnumber[m.group(2)], z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datemonthdayen(arg):
    m = monthdayEnPattern.match(arg)
    if m and m.lastindex == 2:
        return "--{0:02}-{1}".format(monthnumber[m.group(1)], z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")

def datedaymonthyear(arg):
    m = daymonthyearPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1}-{2}".format(yr(m.group(3)), z2(m.group(2)), z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datemonthdayyear(arg): 
    m = monthdayyearPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1}-{2}".format(yr(m.group(3)), z2(m.group(1)), z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datemonthyearen(arg):
    m = monthyearEnPattern.match(arg)
    if m and m.lastindex == 2:
        return "{0}-{1:02}".format(yr(m.group(2)), monthnumber[m.group(1)])
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")
    
def dateyearmonthen(arg):
    m = yearmonthEnPattern.match(arg)
    if m and m.lastindex == 2:
        return "{0}-{1:02}".format(yr(m.group(1)), monthnumber[m.group(2)])
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")

def datedaymonthyearen(arg):
    m = daymonthyearEnPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1:02}-{2}".format(yr(m.group(3)), monthnumber[m.group(2)], z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datemonthdayyearen(arg):
    m = monthdayyearEnPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1:02}-{2}".format(yr(m.group(3)), monthnumber[m.group(1)], z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def dateerayearmonthdayjp(arg):
    m = erayearmonthdayjpPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex == 4:
        return "{0}-{1}-{2}".format(eraYear(m.group(1), m.group(2)), z2(m.group(3)), z2(m.group(4)))
    raise XPathContext.FunctionArgType(1,"xs:date")

def dateerayearmonthjp(arg):
    m = erayearmonthjpPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex == 3:
        return "{0}-{1}".format(eraYear(m.group(1), m.group(2)), z2(m.group(3)))
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")

def dateyearmonthdaycjk(arg):
    m = yearmonthdaycjkPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex == 3:
        return "{0}-{1}-{2}".format(yr(m.group(1)), z2(m.group(2)), z2(m.group(3)))
    raise XPathContext.FunctionArgType(1,"xs:date")

def dateyearmonthcjk(arg):
    m = yearmonthdaycjkPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex == 3:
        return "{0}-{1}".format(m.group(1), z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:date")

def nocontent(arg):
    return ''

def numcommadecimal(arg):
    if numcommadecimalPattern.match(arg):
        return arg.replace('.', '').replace(',', '.').replace(' ', '').replace('\u00A0', '')
    raise XPathContext.FunctionArgType(1,"ixt:nonNegativeDecimalType")

def numcommadot(arg):
    return arg.replace(',', '')

def numdash(arg):
    return arg.replace('-','0')

def numspacedot(arg):
    return arg.replace(' ', '')

def numdotcomma(arg):
    return arg.replace('.', '').replace(',', '.')

def numspacecomma(arg):
    return arg.replace(' ', '').replace(',', '.')

def zerodash(arg):
    return '0'

def numdotdecimal(arg):
    return arg.replace(',', '').replace(' ', '').replace('\u00A0', '')

def numunitdecimal(arg):
    # remove comma (normal), full-width comma, and stops (periods)
    m = numunitdecimalPattern.match(jpDigitsToNormal(arg.replace(',', '')
                                                     .replace('\uFF0C', '')
                                                     .replace('.', '')))
    if m and m.lastindex == 4:
        return m.group(1) + '.' + z2(m.group(3))
    raise XPathContext.FunctionArgType(1,"ixt:nonNegativeDecimalType")
    
ixtFunctions = {
                
    # 3010-04-20 functions
    'dateslashus': dateslashus,
    'dateslasheu': dateslasheu,
    'datedotus': datedotus,
    'datedoteu': datedoteu,
    'datelongus': datelongus,
    'dateshortus': datelongus,
    'datelongeu': datelongeu,
    'dateshorteu': datelongeu,
    'datelonguk': datelongeu,
    'dateshortuk': datelongeu,
    'numcommadot': numcommadot,
    'numdash': numdash,
    'numspacedot': numspacedot,
    'numdotcomma': numdotcomma,
    'numcomma': numdotcomma,
    'numspacecomma': numspacecomma,    
                           
    # 2011-07-31 functions
    'booleanfalse': booleanfalse,
    'booleantrue': booleantrue,
    'datedaymonth': datedaymonth,
    'datedaymonthen': datedaymonthen,
    'datedaymonthyear': datedaymonthyear,
    'datedaymonthyearen': datedaymonthyearen,
    'dateerayearmonthdayjp': dateerayearmonthdayjp,
    'dateerayearmonthjp': dateerayearmonthjp,
    'datemonthday': datemonthday,
    'datemonthdayen': datemonthdayen,
    'datemonthdayyear': datemonthdayyear,
    'datemonthdayyearen': datemonthdayyearen,
    'datemonthyearen': datemonthyearen,
    'dateyearmonthdaycjk': dateyearmonthdaycjk,
    'dateyearmonthen': dateyearmonthen,
    'dateyearmonthcjk': dateyearmonthcjk,
    'nocontent': nocontent,
    'numcommadecimal': numcommadecimal,
    'zerodash': zerodash,
    'numdotdecimal': numdotdecimal,
    'numunitdecimal': numunitdecimal,
}

deprecatedNamespaceURI = 'http://www.xbrl.org/2008/inlineXBRL/transformation' # the CR/PR pre-REC namespace

ixtNamespaceURIs = {
    'http://www.xbrl.org/inlineXBRL/transformation/2010-04-20',
    'http://www.xbrl.org/inlineXBRL/transformation/2011-07-31',
    'http://www.xbrl.org/2008/inlineXBRL/transformation' # the CR/PR pre-REC namespace
}
