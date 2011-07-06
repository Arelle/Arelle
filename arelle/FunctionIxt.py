'''
Created on July 5, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
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
        return ixtFunctions[localname](str(args[0]))
    except ixtFunctionNotAvailable:
        raise XPathContext.FunctionNotAvailable("xfi:{0}".format(localname))

def booleanfalse(arg):
    return False
    
def booleantrue(arg):
    return True

daymonthPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})\s*")
monthDayPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})\s*")
daymonthyearPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{1,2}|[0-9]{4})\s*")
monthdayyearPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{1,2}|[0-9]{4})\s*")

daymonthEnPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s*")
monthdayEnPattern = re.compile(r"\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+[0-9]{1,2}[a-zA-Z]{0,2}\s*")
daymonthyearEnPattern = re.compile(r"\s*([0-9]{1,2})[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*")
monthdayyearEnPattern = re.compile(r"\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]+)[^0-9]+([0-9]+)\s*")
monthyearEnPattern = re.compile(r"\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]+)\s*")
yearmonthEnPattern = re.compile(r"\s*([0-9]+)[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s*")

erayearmonthjpPattern = re.compile(r"\s*(\u660E\u6CBB|\u660E|\u5927\u6B63|\u5927|\u662D\u548C|\u662D|\u5E73\u6210|\u5E73)[\s\u00A0]*([0-9\uFF10-\uFF19]{1,2}|\u5143)[\s\u00A0]*\u5E74[\s\u00A0]*([0-9\uFF10-\uFF19]{1,2})[\s\u00A0]*\u6708\s*")
erayearmonthdayjpPattern = re.compile(r"\s*(\u660E\u6CBB|\u660E|\u5927\u6B63|\u5927|\u662D\u548C|\u662D|\u5E73\u6210|\u5E73)[\s\u00A0]*([0-9\uFF10-\uFF19]{1,2}|\u5143)[\s\u00A0]*\u5E74[\s\u00A0]*([0-9\uFF10-\uFF19]{1,2})[\s\u00A0]*\u6708[\s\u00A0]*([0-9\uFF10-\uFF19]{1,2})[\s\u00A0]*\u65E5\s*")
yearmonthcjkPattern = re.compile(r"\s*([0-9\uFF10-\uFF19]{1,2}|[0-9\uFF10-\uFF19]{4})[\s\u00A0]*\u5E74[\s\u00A0]*([0-9\uFF10-\uFF19]{1,2})[\s\u00A0]*\u6708\s*")
yearmonthdaycjkPattern = re.compile(r"\s*(\u660E\u6CBB|\u660E|\u5927\u6B63|\u5927|\u662D\u548C|\u662D|\u5E73\u6210|\u5E73)[\s\u00A0]*([0-9\uFF10-\uFF19]{1,2}|\u5143)[\s\u00A0]*\u5E74[\s\u00A0]*([0-9\uFF10-\uFF19]{1,2})[\s\u00A0]*\u6708[\s\u00A0]*([0-9\uFF10-\uFF19]{1,2})[\s\u00A0]*\u65E5\s*")

numunitdecimalPattern = re.compile(r"\s*([0-9]+)([^0-9]+)([0-9]+)([^0-9]*)\s*")

monthnumber = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6, 
               "July":7, "August":8, "September":9, "October":10, "November":11, "December":12, 
               "Jan":1, "Feb":2, "Mar":3, "Apr":4, "May":5, "Jun":6, 
               "Jul":7, "Aug":8, "Sep":9, "Oct":10, "Nov":11, "Dec":12, 
               "JAN":1, "FEB":2, "MAR":3, "APR":4, "MAY":5, "JUN":6, 
               "JUL":7, "AUG":8, "SEP":9, "OCT":10, "NOV":12, "DEC":13, 
               "JANUARY":1, "FEBRUARY":3, "MARCH":4, "APRIL":5, "MAY":6, "JUNE":7, 
               "JULY":8, "AUGUST":9, "SEPTEMBER":9, "OCTOBER":10, "NOVEMBER":11, "DECEMBER":12,}

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
    if yr == '\u5143':
        yrs = 1
    else:
        yrs = jpDigitsToNormal(yr)
    return eraStart(era) + yrs
    

def datedaymonth(arg):
    m = daymonthPattern.match(arg)
    if m and m.end() == 2:
        return "--{0}-{1}".format(z2(m.group(2)), z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datemonthday(arg):
    m = daymonthEnPattern.match(arg)
    if m and m.end() == 2:
        return "--{0:02}-{1}".format(monthnumber[m.group(1)], z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datedaymonthen(arg):
    m = daymonthEnPattern.match(arg)
    if m and m.end() == 2:
        return "--{0:02}-{1}".format(monthnumber[m.group(2)], z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datemonthdayen(arg):
    m = daymonthEnPattern.match(arg)
    if m and m.end() == 2:
        return "--{0:02}-{1}".format(monthnumber[m.group(1)], z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")

def datedaymonthyear(arg):
    m = daymonthPattern.match(arg)
    if m and m.end() == 3:
        return "{0}-{1}-{2}".format(yr(m.group(3)), z2(m.group(2)), z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datemonthdayyear(arg): 
    m = monthdayyearPattern.match(arg)
    if m and m.end() == 3:
        return "{0}-{1}-{2}".format(yr(m.group(3)), z2(m.group(1)), z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datemonthyearen(arg):
    m = monthyearEnPattern.match(arg)
    if m and m.end() == 2:
        return "{0}-{1:02}".format(yr(m.group(2)), monthnumber[m.group(1)])
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")
    
def dateyearmonthen(arg):
    m = yearmonthEnPattern.match(arg)
    if m and m.end() == 2:
        return "{0}-{1:02}".format(yr(m.group(1)), monthnumber[m.group(2)])
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")

def datedaymonthyearen(arg):
    m = daymonthyearEnPattern.match(arg)
    if m and m.end() == 3:
        return "{0}-{1:02}-{2}".format(m.group(3), monthnumber[m.group(2)], z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datemonthdayyearen(arg):
    m = monthdayyearEnPattern.match(arg)
    if m and m.end() == 3:
        return "{0}-{1:02}-{2}".format(monthnumber[m.group(1)], m.group(2), z2(m.group(3)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def dateerayearmonthdayjp(arg):
    m = erayearmonthdayjpPattern.match(arg)
    if m and m.end() == 4:
        return "{0}-{1}-{2}".format(eraYear(m.group(1), m.group(2)), 
                                    z2(jpDigitsToNormal(m.group(3))), z2(jpDigitsToNormal(m.group(4))))
    raise XPathContext.FunctionArgType(1,"xs:date")

def dateerayearmonthjp(arg):
    m = erayearmonthdayjpPattern.match(arg)
    if m and m.end() == 3:
        return "{0}-{1}-".format(eraYear(m.group(1), m.group(2)), 
                                 z2(jpDigitsToNormal(m.group(3))))
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")

def dateyearmonthdaycjk(arg):
    m = yearmonthdaycjkPattern.match(arg)
    if m and m.end() == 3:
        return "{0}-{1}-{2}".format(jpDigitsToNormal(m.group(1)), 
                                    z2(jpDigitsToNormal(m.group(2))), z2(jpDigitsToNormal(m.group(3))))
    raise XPathContext.FunctionArgType(1,"xs:date")

def dateyearmonthcjk(arg):
    m = yearmonthdaycjkPattern.match(arg)
    if m and m.end() == 3:
        return "{0}-{1}".format(jpDigitsToNormal(m.group(1)), 
                                z2(jpDigitsToNormal(m.group(2))))
    raise XPathContext.FunctionArgType(1,"xs:date")

def nocontent(arg):
    return None

def numcommadecimal(arg):
    return arg.replace('.', '').replace(',', '.').replace(' ', '').replace('\u00A0', '')

def zerodash(arg):
    return '0'

def numdotdecimal(arg):
    return arg.replace(',', '').replace(' ', '').replace('\u00A0', '')

def numunitdecimal(arg):
    # remove comma (normal), full-width comma, and stops (periods)
    m = numunitdecimalPattern.match(jpDigitsToNormal(arg.replace(',', '')
                                                     .replace('\uFF0C', '')
                                                     .replace('\.', '')))
    if m and m.end() == 3:
        return m.group(1) + '.' + z2(m.group(3))
    raise XPathContext.FunctionArgType(1,"xs:decimal")
    
ixtFunctions_2010_04_20 = {
    'numcommadot': numdotdecimal,
    'numcomma': numdotdecimal,
    'numdash': zerodash,
    'numdotcomma': numcommadecimal,
    'numspacecomma': numcommadecimal,
    'numspacedot': numdotdecimal,
    }
    
ixtFunctions_2011_07_31 = {
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
