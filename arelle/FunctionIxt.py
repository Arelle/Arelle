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
daymonthDkPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec|JAN|FEB|MAR|APR|MAJ|JUN|JUL|AUG|SEP|OKT|NOV|DEC|Jan|Feb|Mar|Apr|Maj|Jun|Jul|Aug|Sep|Okt|Nov|Dec)\s*")
daymonthEnPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s*")
monthdayEnPattern = re.compile(r"\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]{1,2}[a-zA-Z]{0,2})\s*")
daymonthyearDkPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec|JAN|FEB|MAR|APR|MAJ|JUN|JUL|AUG|SEP|OKT|NOV|DEC|Jan|Feb|Mar|Apr|Maj|Jun|Jul|Aug|Sep|Okt|Nov|Dec)[^0-9]+([0-9]{4}|[0-9]{1,2})\s*")
daymonthyearEnPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]{4}|[0-9]{1,2})\s*")
monthdayyearEnPattern = re.compile(r"\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]+)[^0-9]+([0-9]+)\s*")
monthyearDkPattern = re.compile(r"\s*(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec|JAN|FEB|MAR|APR|MAJ|JUN|JUL|AUG|SEP|OKT|NOV|DEC|Jan|Feb|Mar|Apr|Maj|Jun|Jul|Aug|Sep|Okt|Nov|Dec)[^0-9]+([0-9]+)\s*")
monthyearEnPattern = re.compile(r"\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]+)\s*")
yearmonthEnPattern = re.compile(r"\s*([0-9]+)[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s*")

erayearmonthjpPattern = re.compile("[\\s\u00A0]*(\u660E\u6CBB|\u660E|\u5927\u6B63|\u5927|\u662D\u548C|\u662D|\u5E73\u6210|\u5E73)[\\s\u00A0]*([0-9]{1,2}|\u5143)[\\s\u00A0]*\u5E74[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u6708[\\s\u00A0]*")
erayearmonthdayjpPattern = re.compile("[\\s\u00A0]*(\u660E\u6CBB|\u660E|\u5927\u6B63|\u5927|\u662D\u548C|\u662D|\u5E73\u6210|\u5E73)[\\s\u00A0]*([0-9]{1,2}|\u5143)[\\s\u00A0]*\u5E74[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u6708[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u65E5[\\s\u00A0]*")
yearmonthcjkPattern = re.compile("[\\s\u00A0]*([0-9]{4}|[0-9]{1,2})[\\s\u00A0]*\u5E74[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u6708\s*")
yearmonthdaycjkPattern = re.compile("[\\s\u00A0]*([0-9]{4}|[0-9]{1,2})[\\s\u00A0]*\u5E74[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u6708[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u65E5[\\s\u00A0]*")

monthyearPattern = re.compile("[\\s\u00A0]*([0-9]{1,2})[^0-9]+([0-9]{4}|[0-9]{1,2})[\\s\u00A0]*")
yearmonthdayPattern = re.compile("[\\s\u00A0]*([0-9]{4}|[0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{1,2})[\\s\u00A0]*")

numcommadecimalPattern = re.compile(r"\s*[0-9]{1,3}((\.| |\u00A0)?[0-9]{3})*(,[0-9]+)?\s*")
numunitdecimalPattern = re.compile(r"\s*([0-9]+)([^0-9]+)([0-9]+)([^0-9]*)\s*")

monthnumber = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6, 
               "July":7, "August":8, "September":9, "October":10, "November":11, "December":12, 
               "Jan":1, "Feb":2, "Mar":3, "Apr":4, "May":5, "Jun":6, 
               "Jul":7, "Aug":8, "Sep":9, "Oct":10, "Nov":11, "Dec":12, 
               "JAN":1, "FEB":2, "MAR":3, "APR":4, "MAY":5, "JUN":6, 
               "JUL":7, "AUG":8, "SEP":9, "OCT":10, "NOV":12, "DEC":13, 
               "JANUARY":1, "FEBRUARY":3, "MARCH":4, "APRIL":5, "MAY":6, "JUNE":7, 
               "JULY":8, "AUGUST":9, "SEPTEMBER":9, "OCTOBER":10, "NOVEMBER":11, "DECEMBER":12,
               # danish
               "jan":1, "feb":2, "mar": 3, "apr":4, "maj":5, "jun":6,
               "jul":7, "aug":8, "sep":9, "okt":10, "nov":11, "dec":12,
               "MAJ":5, "OKT":10, "Maj":5, "Okt":10,
               }

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
    
def datedaymonthdk(arg):
    m = daymonthDkPattern.match(arg)
    if m and m.lastindex == 2:
        return "--{0:02}-{1}".format(monthnumber[m.group(2)], z2(m.group(1)))
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
    
def datemonthyear(arg):
    m = monthyearPattern.match(arg) # "(M)M*(Y)Y(YY)", with non-numeric separator,
    if m and m.lastindex == 2:
        return "{0}-{1:02}".format(yr(m.group(2)), z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")
    
def datemonthyeardk(arg):
    m = monthyearDkPattern.match(arg)
    if m and m.lastindex == 2:
        return "{0}-{1:02}".format(yr(m.group(2)), monthnumber[m.group(1)])
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")
    
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

def datedaymonthyeardk(arg):
    m = daymonthyearDkPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1:02}-{2}".format(yr(m.group(3)), monthnumber[m.group(2)], z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:date")

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

def dateyearmonthday(arg):
    m = yearmonthdayPattern.match(jpDigitsToNormal(arg)) # (Y)Y(YY)*MM*DD with kangu full-width numerals
    if m and m.lastindex == 3:
        return "{0}-{1}-{2}".format(yr(m.group(1)), z2(m.group(2)), z2(m.group(3)))
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
    
    # transformation registry v-3 functions
    
    # same as v2: 'booleanfalse': booleanfalse,
    # same as v2: 'booleantrue': booleantrue,
    'calindaymonthyear': nocontent, # TBD: calindaymonthyear,
    'calinmonthyear': nocontent, # TBD: calinmonthyear,
    # same as v2: 'datedaymonth': datedaymonth,
    'datedaymonthdk': datedaymonthdk,
    # same as v2: 'datedaymonthen': datedaymonthen,
    # same as v2: 'datedaymonthyear': datedaymonthyear,
    'datedaymonthyeardk': datedaymonthyeardk,
    # same as v2: 'datedaymonthyearen': datedaymonthyearen,
    'datedaymonthyearin': nocontent, # TBD: datedaymonthyearin,
    # same as v2: 'dateerayearmonthdayjp': dateerayearmonthdayjp,
    # same as v2: 'dateerayearmonthjp': dateerayearmonthjp,
    # same as v2: 'datemonthday': datemonthday,
    # same as v2: 'datemonthdayen': datemonthdayen,
    # same as v2: 'datemonthdayyear': datemonthdayyear, 
    # same as v2: 'datemonthdayyearen': datemonthdayyearen,
    'datemonthyear': datemonthyear,
    'datemonthyeardk': datemonthyeardk,
    # same as v2: 'datemonthyearen': datemonthyearen,
    'datemonthyearin': nocontent, # TBD: datemonthyearin,
    # same as v2: 'dateyearmonthcjk': dateyearmonthcjk,
    'dateyearmonthday': dateyearmonthday, # (Y)Y(YY)*MM*DD allowing kanji full-width numerals
    # same as v2: 'dateyearmonthdaycjk': dateyearmonthdaycjk,
    # same as v2: 'dateyearmonthen': dateyearmonthen,
    # same as v2: 'nocontent': nocontent,
    # same as v2: 'numcommadecimal': numcommadecimal,
    # same as v2: 'numdotdecimal': numdotdecimal,
    'numdotdecimalin': nocontent, # TBD: numdotdecimalin,
    # same as v2: 'numunitdecimal': numunitdecimal,
    'numunitdecimalin': nocontent, # TBD: numunitdecimalin,
    # same as v2: 'zerodash': zerodash,
}

deprecatedNamespaceURI = 'http://www.xbrl.org/2008/inlineXBRL/transformation' # the CR/PR pre-REC namespace

ixtNamespaceURIs = {
    'http://www.xbrl.org/inlineXBRL/transformation/2010-04-20', # transformation registry v1
    'http://www.xbrl.org/inlineXBRL/transformation/2011-07-31', # transformation registry v2
    'http://www.xbrl.org/inlineXBRL/transformation/2014-05-14', # transformation registry v3
    'http://www.xbrl.org/2008/inlineXBRL/transformation' # the CR/PR pre-REC namespace
}
