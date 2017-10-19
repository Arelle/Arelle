'''
Created on July 5, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
try:
    import regex as re
except ImportError:
    import re
from arelle.PluginManager import pluginClassMethods
from arelle import XPathContext
from datetime import datetime

class ixtFunctionNotAvailable(Exception):
    def __init__(self):
        self.args =  (_("ixt function not available"),)
    def __repr__(self):
        return self.args[0]
    
def call(xc, p, qn, args):
    try:
        _ixtFunction = ixtNamespaceFunctions[qn.namespaceURI][qn.localName]
    except KeyError:
        raise XPathContext.FunctionNotAvailable(str(qn))
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) != 1: raise XPathContext.FunctionArgType(1,"xs:string")
    return _ixtFunction(str(args[0][0]))

dateslashPattern = re.compile(r"^\s*(\d+)/(\d+)/(\d+)\s*$")
daymonthslashPattern = re.compile(r"^\s*([0-9]{1,2})/([0-9]{1,2})\s*$")
monthdayslashPattern = re.compile(r"^\s*([0-9]{1,2})/([0-9]{1,2})\s*$")
datedotPattern = re.compile(r"^\s*(\d+)\.(\d+)\.(\d+)\s*$")
daymonthPattern = re.compile(r"^\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})\s*$")
monthdayPattern = re.compile(r"^\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})[A-Za-z]*\s*$")
daymonthyearPattern = re.compile(r"^\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{4}|[0-9]{1,2})\s*$")
monthdayyearPattern = re.compile(r"^\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{4}|[0-9]{1,2})\s*$")

dateUsPattern = re.compile(r"^\s*(\w+)\s+(\d+),\s+(\d+)\s*$")
dateEuPattern = re.compile(r"^\s*(\d+)\s+(\w+)\s+(\d+)\s*$")
daymonthDkPattern = re.compile(r"^\s*([0-9]{1,2})[^0-9]+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)([A-Za-z]*)([.]*)\s*$", re.IGNORECASE)
daymonthEnPattern = re.compile(r"^\s*([0-9]{1,2})[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s*$")
monthdayEnPattern = re.compile(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]{1,2})[A-Za-z]{0,2}\s*$")
daymonthyearDkPattern = re.compile(r"^\s*([0-9]{1,2})[^0-9]+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)([A-Za-z]*)([.]*)[^0-9]*([0-9]{4}|[0-9]{1,2})\s*$", re.IGNORECASE)
daymonthyearEnPattern = re.compile(r"^\s*([0-9]{1,2})[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]{4}|[0-9]{1,2})\s*$")
daymonthyearInPattern = re.compile(r"^\s*([0-9\u0966-\u096F]{1,2})\s([\u0966-\u096F]{2}|[^\s0-9\u0966-\u096F]+)\s([0-9\u0966-\u096F]{2}|[0-9\u0966-\u096F]{4})\s*$")
monthdayyearEnPattern = re.compile(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]+)[^0-9]+([0-9]{4}|[0-9]{1,2})\s*$")
monthyearDkPattern = re.compile(r"^\s*(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)([A-Za-z]*)([.]*)[^0-9]*([0-9]{4}|[0-9]{1,2})\s*$", re.IGNORECASE)
monthyearEnPattern = re.compile(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearInPattern = re.compile(r"^\s*([^\s0-9\u0966-\u096F]+)\s([0-9\u0966-\u096F]{4})\s*$")
yearmonthEnPattern = re.compile(r"^\s*([0-9]{1,2}|[0-9]{4})[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s*$")

# TR1-only patterns, only allow space separators, no all-CAPS month name, only 2 or 4 digit years
dateLongUkTR1Pattern = re.compile(r"^\s*(\d|\d{2,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (\d{2,2}|\d{4,4})\s*$")
dateShortUkTR1Pattern = re.compile(r"^\s*(\d|\d{2,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{2,2}|\d{4,4})\s*$")
dateLongUsTR1Pattern = re.compile(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December) (\d|\d{2,2}), (\d{2,2}|\d{4,4})\s*$")
dateShortUsTR1Pattern = re.compile(r"^\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d|\d{2,2}), (\d{2,2}|\d{4,4})\s*$")
daymonthLongEnTR1Pattern = re.compile(r"^\s*(\d|\d{2,2}) (January|February|March|April|May|June|July|August|September|October|November|December)\s*$")
daymonthShortEnTR1Pattern = re.compile(r"^\s*([0-9]{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*$")
monthdayLongEnTR1Pattern = re.compile(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December) (\d|\d{2,2})\s*$")
monthdayShortEnTR1Pattern = re.compile(r"^\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+([0-9]{1,2})[A-Za-z]{0,2}\s*$")
monthyearShortEnTR1Pattern = re.compile(r"^\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+([0-9]{2}|[0-9]{4})\s*$")
monthyearLongEnTR1Pattern = re.compile(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+([0-9]{2}|[0-9]{4})\s*$")
yearmonthShortEnTR1Pattern = re.compile(r"^\s*([0-9]{2}|[0-9]{4})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*$")
yearmonthLongEnTR1Pattern = re.compile(r"^\s*([0-9]{2}|[0-9]{4})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s*$")

erayearmonthjpPattern = re.compile("^[\\s\u00A0]*(\u660E\u6CBB|\u660E|\u5927\u6B63|\u5927|\u662D\u548C|\u662D|\u5E73\u6210|\u5E73)[\\s\u00A0]*([0-9]{1,2}|\u5143)[\\s\u00A0]*\u5E74[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u6708[\\s\u00A0]*$")
erayearmonthdayjpPattern = re.compile("^[\\s\u00A0]*(\u660E\u6CBB|\u660E|\u5927\u6B63|\u5927|\u662D\u548C|\u662D|\u5E73\u6210|\u5E73)[\\s\u00A0]*([0-9]{1,2}|\u5143)[\\s\u00A0]*\u5E74[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u6708[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u65E5[\\s\u00A0]*$")
yearmonthcjkPattern = re.compile("^[\\s\u00A0]*([0-9]{4}|[0-9]{1,2})[\\s\u00A0]*\u5E74[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u6708\\s*$")
yearmonthdaycjkPattern = re.compile("^[\\s\u00A0]*([0-9]{4}|[0-9]{1,2})[\\s\u00A0]*\u5E74[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u6708[\\s\u00A0]*([0-9]{1,2})[\\s\u00A0]*\u65E5[\\s\u00A0]*$")

monthyearPattern = re.compile("^[\\s\u00A0]*([0-9]{1,2})[^0-9]+([0-9]{4}|[0-9]{1,2})[\\s\u00A0]*$")
yearmonthdayPattern = re.compile("^[\\s\u00A0]*([0-9]{4}|[0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{1,2})[\\s\u00A0]*$")

zeroDashPattern = re.compile(r"^\s*([-]|\u002D|\u002D|\u058A|\u05BE|\u2010|\u2011|\u2012|\u2013|\u2014|\u2015|\uFE58|\uFE63|\uFF0D)\s*$")
numDotDecimalPattern = re.compile(r"^\s*[0-9]{1,3}([, \xA0]?[0-9]{3})*(\.[0-9]+)?\s*$")
numDotDecimalInPattern = re.compile(r"^(([0-9]{1,2}[, \xA0])?([0-9]{2}[, \xA0])*[0-9]{3})([.][0-9]+)?$|^([0-9]+)([.][0-9]+)?$")
numCommaDecimalPattern = re.compile(r"^\s*[0-9]{1,3}([. \xA0]?[0-9]{3})*(,[0-9]+)?\s*$")
numUnitDecimalPattern = re.compile(r"^([0]|([1-9][0-9]{0,2}([.,\uFF0C\uFF0E]?[0-9]{3})*))[^0-9,.\uFF0C\uFF0E]+([0-9]{1,2})[^0-9,.\uFF0C\uFF0E]*$")
numUnitDecimalInPattern = re.compile(r"^(([0-9]{1,2}[, \xA0])?([0-9]{2}[, \xA0])*[0-9]{3})([^0-9]+)([0-9]{1,2})([^0-9]*)$|^([0-9]+)([^0-9]+)([0-9]{1,2})([^0-9]*)$")
numCommaPattern = re.compile(r"^\s*[0-9]+(,[0-9]+)?\s*$")
numCommaDotPattern = re.compile(r"^\s*[0-9]{1,3}(,[0-9]{3,3})*([.][0-9]+)?\s*$")
numDashPattern = re.compile(r"^\s*-\s*$")
numDotCommaPattern = re.compile(r"^\s*[0-9]{1,3}([.][0-9]{3,3})*(,[0-9]+)?\s*$")
numSpaceDotPattern = re.compile(r"^\s*[0-9]{1,3}([ \xA0][0-9]{3,3})*([.][0-9]+)?\s*$")
numSpaceCommaPattern = re.compile(r"^\s*[0-9]{1,3}([ \xA0][0-9]{3,3})*(,[0-9]+)?\s*$")

monthnumber = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6, 
               "July":7, "August":8, "September":9, "October":10, "November":11, "December":12, 
               "Jan":1, "Feb":2, "Mar":3, "Apr":4, "May":5, "Jun":6, 
               "Jul":7, "Aug":8, "Sep":9, "Oct":10, "Nov":11, "Dec":12, 
               "JAN":1, "FEB":2, "MAR":3, "APR":4, "MAY":5, "JUN":6, 
               "JUL":7, "AUG":8, "SEP":9, "OCT":10, "NOV":11, "DEC":12, 
               "JANUARY":1, "FEBRUARY":2, "MARCH":3, "APRIL":4, "MAY":5, "JUNE":6, 
               "JULY":7, "AUGUST":8, "SEPTEMBER":9, "OCTOBER":10, "NOVEMBER":11, "DECEMBER":12,
               # danish
               "jan":1, "feb":2, "mar": 3, "apr":4, "maj":5, "jun":6,
               "jul":7, "aug":8, "sep":9, "okt":10, "nov":11, "dec":12,
               }

maxDayInMo = {"01": "30", "02": "29", "03": "31", "04": "30", "05": "31", "06": "30",
              "07": "31", "08": "31", "09": "30", "10": "31", "11": "30", "12":"31",
              1: "30", 2: "29", 3: "31", 4: "30", 5: "31", 6: "30",
              7: "31", 8: "31", 9: "30", 10: "31", 11: "30", 12:"31"}
gLastMoDay = [31,28,31,30,31,30,31,31,30,31,30,31]

gregorianHindiMonthNumber = {
                "\u091C\u0928\u0935\u0930\u0940": "01",
                "\u092B\u0930\u0935\u0930\u0940": "02", 
                "\u092E\u093E\u0930\u094D\u091A": "03", 
                "\u0905\u092A\u094D\u0930\u0948\u0932": "04",
                "\u092E\u0908": "05", 
                "\u091C\u0942\u0928": "06",
                "\u091C\u0941\u0932\u093E\u0908": "07", 
                "\u0905\u0917\u0938\u094D\u0924": "08",
                "\u0938\u093F\u0924\u0902\u092C\u0930": "09",
                "\u0905\u0915\u094D\u0924\u0942\u092C\u0930": "10",
                "\u0928\u0935\u092E\u094D\u092C\u0930": "11",
                "\u0926\u093F\u0938\u092E\u094D\u092C\u0930": "12"
                }

sakaMonthNumber = {
                "Chaitra":1, "\u091A\u0948\u0924\u094D\u0930":1,
                "Vaisakha":2, "Vaishakh":2, "Vai\u015B\u0101kha":2, "\u0935\u0948\u0936\u093E\u0916":2, "\u092C\u0948\u0938\u093E\u0916":2,
                "Jyaishta":3, "Jyaishtha":3, "Jyaistha":3, "Jye\u1E63\u1E6Dha":3, "\u091C\u094D\u092F\u0947\u0937\u094D\u0920":3,
                "Asadha":4, "Ashadha":4, "\u0100\u1E63\u0101\u1E0Dha":4, "\u0906\u0937\u093E\u0922":4, "\u0906\u0937\u093E\u0922\u093C":4,
                "Sravana":5, "Shravana":5, "\u015Ar\u0101va\u1E47a":5, "\u0936\u094D\u0930\u093E\u0935\u0923":5, "\u0938\u093E\u0935\u0928":5,
                "Bhadra":6, "Bhadrapad":6, "Bh\u0101drapada":6, "Bh\u0101dra":6, "Pro\u1E63\u1E6Dhapada":6, "\u092D\u093E\u0926\u094D\u0930\u092A\u0926":6, "\u092D\u093E\u0926\u094B":6,
                "Aswina":7, "Ashwin":7, "Asvina":7, "\u0100\u015Bvina":7, "\u0906\u0936\u094D\u0935\u093F\u0928":7, 
                "Kartiak":8, "Kartik":8, "Kartika":8, "K\u0101rtika":8, "\u0915\u093E\u0930\u094D\u0924\u093F\u0915":8, 
                "Agrahayana":9,"Agrah\u0101ya\u1E47a":9,"Margashirsha":9, "M\u0101rga\u015B\u012Br\u1E63a":9, "\u092E\u093E\u0930\u094D\u0917\u0936\u0940\u0930\u094D\u0937":9, "\u0905\u0917\u0939\u0928":9,
                "Pausa":10, "Pausha":10, "Pau\u1E63a":10, "\u092A\u094C\u0937":10,
                "Magha":11, "Magh":11, "M\u0101gha":11, "\u092E\u093E\u0918":11,
                "Phalguna":12, "Phalgun":12, "Ph\u0101lguna":12, "\u092B\u093E\u0932\u094D\u0917\u0941\u0928":12,
                }
sakaMonthPattern = re.compile(r"(C\S*ait|\u091A\u0948\u0924\u094D\u0930)|"
                              r"(Vai|\u0935\u0948\u0936\u093E\u0916|\u092C\u0948\u0938\u093E\u0916)|"
                              r"(Jy|\u091C\u094D\u092F\u0947\u0937\u094D\u0920)|"
                              r"(dha|\u1E0Dha|\u0906\u0937\u093E\u0922|\u0906\u0937\u093E\u0922\u093C)|"
                              r"(vana|\u015Ar\u0101va\u1E47a|\u0936\u094D\u0930\u093E\u0935\u0923|\u0938\u093E\u0935\u0928)|"
                              r"(Bh\S+dra|Pro\u1E63\u1E6Dhapada|\u092D\u093E\u0926\u094D\u0930\u092A\u0926|\u092D\u093E\u0926\u094B)|"
                              r"(in|\u0906\u0936\u094D\u0935\u093F\u0928)|"
                              r"(K\S+rti|\u0915\u093E\u0930\u094D\u0924\u093F\u0915)|"
                              r"(M\S+rga|Agra|\u092E\u093E\u0930\u094D\u0917\u0936\u0940\u0930\u094D\u0937|\u0905\u0917\u0939\u0928)|"
                              r"(Pau|\u092A\u094C\u0937)|"
                              r"(M\S+gh|\u092E\u093E\u0918)|"
                              r"(Ph\S+lg|\u092B\u093E\u0932\u094D\u0917\u0941\u0928)")
sakaMonthLength = (30,31,31,31,31,31,30,30,30,30,30,30) # Chaitra has 31 days in Gregorian leap year
sakaMonthOffset = ((3,22,0),(4,21,0),(5,22,0),(6,22,0),(7,23,0),(8,23,0),(9,23,0),(10,23,0),(11,22,0),(12,22,0),(1,21,1),(2,20,1))

# common helper functions
def checkDate(y,m,d):
    try:
        datetime(_INT(y), _INT(m), _INT(d))
        return True
    except (ValueError):
        return False

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

def yrin(arg, _mo, _day):   # zero pad to 4 digits
    if len(arg) == 2:
        if arg > '21' or (arg == '21' and _mo >= 10 and _day >= 11):
            return '19' + arg
        else:
            return '20' + arg
    return arg

def devanagariDigitsToNormal(devanagariDigits):
    normal = ''
    for d in devanagariDigits:
        if '\u0966' <= d <= '\u096F':
            normal += chr( ord(d) - 0x0966 + ord('0') )
        else:
            normal += d
    return normal

def jpDigitsToNormal(jpDigits):
    normal = ''
    for d in jpDigits:
        if '\uFF10' <= d <= '\uFF19':
            normal += chr( ord(d) - 0xFF10 + ord('0') )
        else:
            normal += d
    return normal

def sakaToGregorian(sYr, sMo, sDay): # replacement of plug-in sakaCalendar.py which is LGPL-v3 licensed
    gYr = sYr + 78  # offset from Saka to Gregorian year
    sStartsInLeapYr = gYr % 4 == 0 and (not gYr % 100 == 0 or gYr % 400 == 0) # Saka yr starts in leap yr
    if gYr < 0:
        raise ValueError(_("Saka calendar year not supported: {0} {1} {2} "), sYr, sMo, sDay)
    if  sMo < 1 or sMo > 12:
        raise ValueError(_("Saka calendar month error: {0} {1} {2} "), sYr, sMo, sDay)
    sMoLength = sakaMonthLength[sMo - 1]
    if sStartsInLeapYr and sMo == 1:
        sMoLength += 1 # Chaitra has 1 extra day when starting in gregorian leap years
    if sDay < 1 or sDay > sMoLength: 
        raise ValueError(_("Saka calendar day error: {0} {1} {2} "), sYr, sMo, sDay)
    gMo, gDayOffset, gYrOffset = sakaMonthOffset[sMo - 1] # offset Saka to Gregorian by Saka month
    if sStartsInLeapYr and sMo == 1:
        gDayOffset -= 1 # Chaitra starts 1 day earlier when starting in Gregorian leap years
    gYr += gYrOffset # later Saka months offset into next Gregorian year
    gMoLength = gLastMoDay[gMo - 1] # month length (days in month)
    if gMo == 2 and gYr % 4 == 0 and (not gYr % 100 == 0 or gYr % 400 == 0): # does Phalguna (Feb) end in a Gregorian leap year?
        gMoLength += 1 # Phalguna (Feb) is in a Gregorian leap year (Feb has 29 days)
    gDay = gDayOffset + sDay - 1
    if gDay > gMoLength: # overflow from Gregorial month of start of Saka month to next Gregorian month
        gDay -= gMoLength
        gMo += 1
        if gMo == 13:  # overflow from Gregorian year of start of Saka year to following Gregorian year
            gMo = 1
            gYr += 1
    return (gYr, gMo, gDay)

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
    
def datelongusTR1(arg):
    m = dateLongUsTR1Pattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1:02}-{2}".format(yr(m.group(3)), monthnumber[m.group(1)], z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def dateshortusTR1(arg):
    m = dateShortUsTR1Pattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1:02}-{2}".format(yr(m.group(3)), monthnumber[m.group(1)], z2(m.group(2)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datelongukTR1(arg):
    m = dateLongUkTR1Pattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1:02}-{2}".format(yr(m.group(3)), monthnumber[m.group(2)], z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def dateshortukTR1(arg):
    m = dateShortUkTR1Pattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1:02}-{2}".format(yr(m.group(3)), monthnumber[m.group(2)], z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datelongeu(arg):
    m = dateEuPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1:02}-{2}".format(yr(m.group(3)), monthnumber[m.group(2)], z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datedaymonth(arg):
    m = daymonthPattern.match(arg)
    if m and m.lastindex == 2:
        mo = z2(m.group(2))
        day = z2(m.group(1))
        if "01" <= day <= maxDayInMo.get(mo, "00"): 
            return "--{0}-{1}".format(mo, day)
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datemonthday(arg):
    m = monthdayPattern.match(arg)
    if m and m.lastindex == 2:
        mo = z2(m.group(1))
        day = z2(m.group(2))
        if "01" <= day <= maxDayInMo.get(mo, "00"): 
            return "--{0}-{1}".format(mo, day)
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datedaymonthSlashTR1(arg):
    m = daymonthslashPattern.match(arg)
    if m and m.lastindex == 2:
        mo = z2(m.group(2))
        day = z2(m.group(1))
        return "--{0}-{1}".format(mo, day)
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datemonthdaySlashTR1(arg):
    m = monthdayslashPattern.match(arg)
    if m and m.lastindex == 2:
        mo = z2(m.group(1))
        day = z2(m.group(2))
        return "--{0}-{1}".format(mo, day)
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datedaymonthdk(arg):
    m = daymonthDkPattern.match(arg)
    if m and m.lastindex == 4:
        day = z2(m.group(1))
        mon3 = m.group(2).lower()
        mon3 = m.group(2).lower()
        monEnd = m.group(3)
        monPer = m.group(4)
        if (mon3 in monthnumber):
            mo = monthnumber[mon3]
            if (((not monEnd and not monPer) or
                 (not monEnd and monPer) or
                 (monEnd and not monPer)) and
                "01" <= day <= maxDayInMo.get(mo, "00")):
                return "--{0:02}-{1}".format(mo, day)
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datedaymonthen(arg):
    m = daymonthEnPattern.match(arg)
    if m and m.lastindex == 2:
        _mo = monthnumber[m.group(2)]
        _day = z2(m.group(1))
        if "01" <= _day <= maxDayInMo.get(_mo, "00"): 
            return "--{0:02}-{1}".format(_mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datedaymonthShortEnTR1(arg):
    m = daymonthShortEnTR1Pattern.match(arg)
    if m and m.lastindex == 2:
        _mo = monthnumber[m.group(2)]
        _day = z2(m.group(1))
        return "--{0:02}-{1}".format(_mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datedaymonthLongEnTR1(arg):
    m = daymonthLongEnTR1Pattern.match(arg)
    if m and m.lastindex == 2:
        _mo = monthnumber[m.group(2)]
        _day = z2(m.group(1))
        return "--{0:02}-{1}".format(_mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")
    
def datemonthdayen(arg):
    m = monthdayEnPattern.match(arg)
    if m and m.lastindex == 2:
        _mo = monthnumber[m.group(1)]
        _day = z2(m.group(2))
        if "01" <= _day <= maxDayInMo.get(_mo, "00"): 
            return "--{0:02}-{1}".format(_mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")

def datemonthdayLongEnTR1(arg):
    m = monthdayLongEnTR1Pattern.match(arg)
    if m and m.lastindex == 2:
        _mo = monthnumber[m.group(1)]
        _day = z2(m.group(2))
        return "--{0:02}-{1}".format(_mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")

def datemonthdayShortEnTR1(arg):
    m = monthdayShortEnTR1Pattern.match(arg)
    if m and m.lastindex == 2:
        _mo = monthnumber[m.group(1)]
        _day = z2(m.group(2))
        return "--{0:02}-{1}".format(_mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:gMonthDay")

def datedaymonthyear(arg):
    m = daymonthyearPattern.match(arg)
    if m and m.lastindex == 3 and checkDate(yr(m.group(3)), m.group(2), m.group(1)):
        return "{0}-{1}-{2}".format(yr(m.group(3)), z2(m.group(2)), z2(m.group(1)))
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datemonthdayyear(arg): 
    m = monthdayyearPattern.match(arg)
    if m and m.lastindex == 3:
        _yr = yr(m.group(3))
        _mo = z2(m.group(1))
        _day = z2(m.group(2))
        if checkDate(_yr, _mo, _day):
            return "{0}-{1}-{2}".format(_yr, _mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def datemonthyear(arg):
    m = monthyearPattern.match(arg) # "(M)M*(Y)Y(YY)", with non-numeric separator,
    if m and m.lastindex == 2:
        _mo = z2(m.group(1))
        if "01" <= _mo <= "12":
            return "{0}-{1:2}".format(yr(m.group(2)), _mo)
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")
    
def datemonthyeardk(arg):
    m = monthyearDkPattern.match(arg)
    if m and m.lastindex == 4:
        mon3 = m.group(1).lower()
        monEnd = m.group(2)
        monPer = m.group(3)
        if mon3 in monthnumber and ((not monEnd and not monPer) or
                                    (not monEnd and monPer) or
                                    (monEnd and not monPer)):
            return "{0}-{1:02}".format(yr(m.group(4)), monthnumber[mon3])
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")
    
def datemonthyearen(arg):
    m = monthyearEnPattern.match(arg)
    if m and m.lastindex == 2:
        return "{0}-{1:02}".format(yr(m.group(2)), monthnumber[m.group(1)])
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")
    
def datemonthyearShortEnTR1(arg):
    m = monthyearShortEnTR1Pattern.match(arg)
    if m and m.lastindex == 2:
        return "{0}-{1:02}".format(yr(m.group(2)), monthnumber[m.group(1)])
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")
    
def datemonthyearLongEnTR1(arg):
    m = monthyearLongEnTR1Pattern.match(arg)
    if m and m.lastindex == 2:
        return "{0}-{1:02}".format(yr(m.group(2)), monthnumber[m.group(1)])
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")
    
def datemonthyearin(arg):
    m = monthyearInPattern.match(arg)
    try:
        return "{0}-{1}".format(yr(devanagariDigitsToNormal(m.group(2))), 
                                   gregorianHindiMonthNumber[m.group(1)])
    except (AttributeError, IndexError, KeyError):
        pass
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")
    
def dateyearmonthen(arg):
    m = yearmonthEnPattern.match(arg)
    if m and m.lastindex == 2:
        return "{0}-{1:02}".format(yr(m.group(1)), monthnumber[m.group(2)])
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")

def dateyearmonthShortEnTR1(arg):
    m = yearmonthShortEnTR1Pattern.match(arg)
    if m and m.lastindex == 2:
        return "{0}-{1:02}".format(yr(m.group(1)), monthnumber[m.group(2)])
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")

def dateyearmonthLongEnTR1(arg):
    m = yearmonthLongEnTR1Pattern.match(arg)
    if m and m.lastindex == 2:
        return "{0}-{1:02}".format(yr(m.group(1)), monthnumber[m.group(2)])
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")

def datedaymonthyeardk(arg):
    m = daymonthyearDkPattern.match(arg)
    if m and m.lastindex == 5:
        _yr = yr(m.group(5))
        _day = z2(m.group(1))
        _mon3 = m.group(2).lower()
        _monEnd = m.group(3)
        _monPer = m.group(4)
        if _mon3 in monthnumber and ((not _monEnd and not _monPer) or
                                     (not _monEnd and _monPer) or
                                     (_monEnd and not _monPer)):
            _mo = monthnumber[_mon3]
            if checkDate(_yr, _mo, _day):
                return "{0}-{1:02}-{2}".format(_yr, _mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:date")

def datedaymonthyearen(arg):
    m = daymonthyearEnPattern.match(arg)
    if m and m.lastindex == 3:
        _yr = yr(m.group(3))
        _mo = monthnumber[m.group(2)]
        _day = z2(m.group(1))
        if checkDate(_yr, _mo, _day):
            return "{0}-{1:02}-{2}".format(_yr, _mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:date")

def datedaymonthyearin(arg):
    m = daymonthyearInPattern.match(arg)
    try:
        _yr = yr(devanagariDigitsToNormal(m.group(3)))
        _mo = gregorianHindiMonthNumber.get(m.group(2), devanagariDigitsToNormal(m.group(2)))
        _day = z2(devanagariDigitsToNormal(m.group(1)))
        if checkDate(_yr, _mo, _day):
            return "{0}-{1}-{2}".format(_yr, _mo, _day)
    except (AttributeError, IndexError, KeyError):
        pass
    raise XPathContext.FunctionArgType(1,"xs:date")

def calindaymonthyear(arg):
    m = daymonthyearInPattern.match(arg)
    try:
        # Transformation registry 3 requires use of pattern comparisons instead of exact transliterations
        #_mo = _INT(sakaMonthNumber[m.group(2)])
        # pattern approach
        _mo = sakaMonthPattern.search(m.group(2)).lastindex
        _day = _INT(devanagariDigitsToNormal(m.group(1)))
        _yr = _INT(devanagariDigitsToNormal(yrin(m.group(3), _mo, _day)))
        #sakaDate = [_yr, _mo, _day]
        #for pluginMethod in pluginClassMethods("SakaCalendar.ToGregorian"):  # LGPLv3 plugin (moved to examples/plugin)
        #    gregorianDate = pluginMethod(sakaDate)
        #    return "{0}-{1:02}-{2:02}".format(gregorianDate[0], gregorianDate[1], gregorianDate[2])
        #raise NotImplementedError (_("ixt:calindaymonthyear requires plugin sakaCalendar.py, please install plugin.  "))
        gregorianDate = sakaToGregorian(_yr, _mo, _day) # native implementation for Arelle
        return "{0}-{1:02}-{2:02}".format(gregorianDate[0], gregorianDate[1], gregorianDate[2])
    except (AttributeError, IndexError, KeyError, ValueError):
        pass
    raise XPathContext.FunctionArgType(1,"xs:date")

def datemonthdayyearen(arg):
    m = monthdayyearEnPattern.match(arg)
    if m and m.lastindex == 3:
        _yr = yr(m.group(3))
        _mo = monthnumber[m.group(1)]
        _day = z2(m.group(2))
        if checkDate(_yr, _mo, _day):
            return "{0}-{1:02}-{2}".format(_yr, _mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:date")
    
def dateerayearmonthdayjp(arg):
    m = erayearmonthdayjpPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex == 4:
        _yr = eraYear(m.group(1), m.group(2))
        _mo = z2(m.group(3))
        _day = z2(m.group(4))
        if checkDate(_yr, _mo, _day):
            return "{0}-{1}-{2}".format(_yr, _mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:date")

def dateyearmonthday(arg):
    m = yearmonthdayPattern.match(jpDigitsToNormal(arg)) # (Y)Y(YY)*MM*DD with kangu full-width numerals
    if m and m.lastindex == 3:
        _yr = yr(m.group(1))
        _mo = z2(m.group(2))
        _day = z2(m.group(3))
        if checkDate(_yr, _mo, _day):
            return "{0}-{1}-{2}".format(_yr, _mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:date")

def dateerayearmonthjp(arg):
    m = erayearmonthjpPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex == 3:
        _yr = eraYear(m.group(1), m.group(2))
        _mo = z2(m.group(3))
        if "01" <= _mo <= "12":
            return "{0}-{1}".format(_yr, _mo)
    raise XPathContext.FunctionArgType(1,"xs:gYearMonth")

def dateyearmonthdaycjk(arg):
    m = yearmonthdaycjkPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex == 3:
        _yr = yr(m.group(1))
        _mo = z2(m.group(2))
        _day = z2(m.group(3))
        if checkDate(_yr, _mo, _day):
            return "{0}-{1}-{2}".format(_yr, _mo, _day)
    raise XPathContext.FunctionArgType(1,"xs:date")

def dateyearmonthcjk(arg):
    m = yearmonthcjkPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex == 2:
        _mo =  z2(m.group(2))
        if "01" <= _mo <= "12":
            return "{0}-{1}".format(yr(m.group(1)), _mo)
    raise XPathContext.FunctionArgType(1,"xs:date")

def nocontent(arg):
    return ''

def numcommadecimal(arg):
    if numCommaDecimalPattern.match(arg):
        return arg.replace('.', '').replace(',', '.').replace(' ', '').replace('\u00A0', '')
    raise XPathContext.FunctionArgType(1,"ixt:nonNegativeDecimalType")

def numcommadot(arg):
    if numCommaDotPattern.match(arg):
        return arg.replace(',', '')
    raise XPathContext.FunctionArgType(1,"ixt:numcommadot")

def numdash(arg):
    if numDashPattern.match(arg):
        return arg.replace('-','0')
    raise XPathContext.FunctionArgType(1,"ixt:numdash")

def numspacedot(arg):
    if numSpaceDotPattern.match(arg):
        return arg.replace(' ', '').replace('\u00A0', '')
    raise XPathContext.FunctionArgType(1,"ixt:numspacedot")

def numcomma(arg):
    if numCommaPattern.match(arg):
        return arg.replace(',', '.')
    raise XPathContext.FunctionArgType(1,"ixt:numcomma")

def numdotcomma(arg):
    if numDotCommaPattern.match(arg):
        return arg.replace('.', '').replace(',', '.')
    raise XPathContext.FunctionArgType(1,"ixt:numdotcomma")

def numspacecomma(arg):
    if numSpaceCommaPattern.match(arg):
        return arg.replace(' ', '').replace('\u00A0', '').replace(',', '.')
    raise XPathContext.FunctionArgType(1,"ixt:numspacecomma")

def zerodash(arg):
    if zeroDashPattern.match(arg):
        return '0'
    raise XPathContext.FunctionArgType(1,"ixt:zerodashType")

def numdotdecimal(arg):
    if numDotDecimalPattern.match(arg):
        return arg.replace(',', '').replace(' ', '').replace('\u00A0', '')
    raise XPathContext.FunctionArgType(1,"ixt:numdotdecimalType")

def numdotdecimalin(arg):
    m = numDotDecimalInPattern.match(arg)
    if m:
        m2 = [g for g in m.groups() if g is not None]
        if m2[-1].startswith("."):
            fract = m2[-1]
        else:
            fract = ""
        return m2[0].replace(',','').replace(' ','').replace('\xa0','') + fract
    raise XPathContext.FunctionArgType(1,"ixt:numdotdecimalinType")

def numunitdecimal(arg):
    # remove comma (normal), full-width comma, and stops (periods)
    m = numUnitDecimalPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex > 1:
        return m.group(1).replace('.','').replace(',','').replace('\uFF0C','').replace('\uFF0E','') + '.' + z2(m.group(m.lastindex))
    raise XPathContext.FunctionArgType(1,"ixt:nonNegativeDecimalType")

def numunitdecimalin(arg):
    m = numUnitDecimalInPattern.match(arg)
    if m:
        m2 = [g for g in m.groups() if g is not None]
        return m2[0].replace(',','').replace(' ','').replace('\xa0','') + '.' + z2(m2[-2])
    raise XPathContext.FunctionArgType(1,"ixt:numunitdecimalinType")
    
tr1Functions = {
    # 2010-04-20 functions
    'dateslashus': dateslashus,
    'dateslasheu': dateslasheu,
    'datedotus': datedotus,
    'datedoteu': datedoteu,
    'datelongus': datelongusTR1,
    'dateshortus': dateshortusTR1,
    'datelonguk': datelongukTR1,
    'dateshortuk': dateshortukTR1,
    'numcommadot': numcommadot,
    'numdash': numdash,
    'numspacedot': numspacedot,
    'numdotcomma': numdotcomma,
    'numcomma': numcomma,
    'numspacecomma': numspacecomma,
    'datelongdaymonthuk': datedaymonthLongEnTR1,
    'dateshortdaymonthuk': datedaymonthShortEnTR1,
    'datelongmonthdayus': datemonthdayLongEnTR1,
    'dateshortmonthdayus': datemonthdayShortEnTR1,
    'dateslashdaymontheu': datedaymonthSlashTR1,
    'dateslashmonthdayus': datemonthdaySlashTR1,
    'datelongyearmonth': dateyearmonthLongEnTR1,
    'dateshortyearmonth': dateyearmonthShortEnTR1,
    'datelongmonthyear': datemonthyearLongEnTR1,
    'dateshortmonthyear': datemonthyearShortEnTR1
}

tr2Functions = {
                           
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
    'numunitdecimal': numunitdecimal
}
    
    # transformation registry v-3 functions
tr3Functions = tr2Functions # tr3 starts with tr2 and adds more functions
tr3Functions.update ({
    # same as v2: 'booleanfalse': booleanfalse,
    # same as v2: 'booleantrue': booleantrue,
    'calindaymonthyear': calindaymonthyear, # TBD: calindaymonthyear,
    #'calinmonthyear': nocontent, # TBD: calinmonthyear,
    # same as v2: 'datedaymonth': datedaymonth,
    'datedaymonthdk': datedaymonthdk,
    # same as v2: 'datedaymonthen': datedaymonthen,
    # same as v2: 'datedaymonthyear': datedaymonthyear,
    'datedaymonthyeardk': datedaymonthyeardk,
    # same as v2: 'datedaymonthyearen': datedaymonthyearen,
    'datedaymonthyearin': datedaymonthyearin,
    # same as v2: 'dateerayearmonthdayjp': dateerayearmonthdayjp,
    # same as v2: 'dateerayearmonthjp': dateerayearmonthjp,
    # same as v2: 'datemonthday': datemonthday,
    # same as v2: 'datemonthdayen': datemonthdayen,
    # same as v2: 'datemonthdayyear': datemonthdayyear, 
    # same as v2: 'datemonthdayyearen': datemonthdayyearen,
    'datemonthyear': datemonthyear,
    'datemonthyeardk': datemonthyeardk,
    # same as v2: 'datemonthyearen': datemonthyearen,
    'datemonthyearin': datemonthyearin,
    # same as v2: 'dateyearmonthcjk': dateyearmonthcjk,
    'dateyearmonthday': dateyearmonthday, # (Y)Y(YY)*MM*DD allowing kanji full-width numerals
    # same as v2: 'dateyearmonthdaycjk': dateyearmonthdaycjk,
    # same as v2: 'dateyearmonthen': dateyearmonthen,
    # same as v2: 'nocontent': nocontent,
    # same as v2: 'numcommadecimal': numcommadecimal,
    # same as v2: 'numdotdecimal': numdotdecimal,
    'numdotdecimalin': numdotdecimalin,
    # same as v2: 'numunitdecimal': numunitdecimal,
    'numunitdecimalin': numunitdecimalin,
    # same as v2: 'zerodash': zerodash,
})

deprecatedNamespaceURI = 'http://www.xbrl.org/2008/inlineXBRL/transformation' # the CR/PR pre-REC namespace

ixtNamespaceFunctions = {
    'http://www.xbrl.org/inlineXBRL/transformation/2010-04-20': tr1Functions, # transformation registry v1
    'http://www.xbrl.org/inlineXBRL/transformation/2011-07-31': tr2Functions, # transformation registry v2
    'http://www.xbrl.org/inlineXBRL/transformation/2015-02-26': tr3Functions, # transformation registry v3
    'http://www.xbrl.org/2008/inlineXBRL/transformation': tr1Functions # the CR/PR pre-REC namespace
}
