# -*- coding: utf-8 -*-
'''
Custom transforms for SEC

Created by staff of the U.S. Securities and Exchange Commission.
Data and content created by government employees within the scope of their employment
are not subject to domestic copyright protection. 17 U.S.C. 105.

See COPYRIGHT.md for copyright information.

Local copy of text2num.py was obtained from https://github.com/ghewgill/text2num

'''
import datetime
from arelle.ModelValue import qname, lastDayOfMonth
from arelle.Version import authorLabel, copyrightLabel
from arelle.formula.XPathContext import FunctionArgType

#local copy of text2num.py from https://github.com/ghewgill/text2num
from .text2num import text2num, NumberException

from regex import compile as re_compile

# these five transformations take as input a number and output either an exception, or a value in xs:duration type
# they handle zero values and also negative values

# if arg is not an integer, the rest can spill into months and days, but nothing lower
def duryear(arg):
    n, sign = getValue(arg)
    years = int(n)
    months =  (n - years) * 12
    days = int((months - int(months)) * 30.4375)
    months = int(months)
    return durationValue(years, months, days, None, sign)

# if arg is not an integer, the rest can spill into days, but nothing lower
def durmonth(arg):
    n, sign = getValue(arg)
    months = int(n)
    days = int((n - months) * 30.4375)
    return durationValue(None, months, days, None, sign)

# the output will only be in days, nothing lower
# xs:durationType doesn't have weeks, only years, months and days, so we display it all in days
def durweek(arg):
    n, sign = getValue(arg)
    days = int(n * 7)
    return durationValue(None, None, days, None, sign)

# if arg is not an integer, the rest can spill into hours, but nothing lower
def durday(arg):
    n, sign = getValue(arg)
    days = int(n)
    hours = int((n - days) * 24)
    return durationValue(None, None, days, hours, sign)

# the output will only be in hours, nothing lower
def durhour(arg):
    n, sign = getValue(arg)
    hours = int(n)
    return durationValue(None, None, None, hours, sign)

dateQuarterEndPattern = re_compile(r"(^[ \t\n\r]*(?:(?![0-9]{2})\w[^0-9]*)?(1|[Ff]irst|2|[Ss]econd|3|[Tt]hird|4|[Ff]ourth|[Ll]ast)[^0-9]*([0-9]{4})[ \t\n\r]*$)|(^[ \t\n\r]*([0-9]{4})[^0-9]*(1|[Ff]irst|2|[Ss]econd|3|[Tt]hird|4|[Ff]ourth|[Ll]ast)((?![0-9]).*\w+)?[ \t\n\r]*$)")

# the output is a date value of a calendar quarter end
def datequarterend(arg):
    try:
        m = dateQuarterEndPattern.match(arg)
        year = int(m.group(3) or m.group(5)) # year pattern, raises AttributeError if no pattern match
        month = {"first":3, "1":3, "second":6, "2":6, "third":9, "3":9, "fourth":12, "last":12, "4":12
                 }[(m.group(2) or m.group(6)).lower()]
        return str(datetime.date(year, month, lastDayOfMonth(year, month)))
    except (AttributeError, ValueError, KeyError):
        raise FunctionArgType(0, "xs:date")

decimalValuePattern = re_compile(r"^[ \t\n\r]*[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)[ \t\n\r]*$")

def getValue(arg):
    if not decimalValuePattern.match(arg):
        raise FunctionArgType(0, "xs:duration")
    try:
        n = float(arg) # could cause a ValueError exception
        if n < 0:
            return (abs(n), '-') # add a negative sign
        return (n, '') # don't add a sign
    except ValueError:
        raise FunctionArgType(0, "xs:duration")

def durationValue(y, m, d, h, sign):

    # preprocess each value so we don't print P0Y0M0D or something like that.
    # in this case, we should print P0Y, and leave out the months and days.
    if all(i == 0 or i is None for i in [y, m, d, h]):
        sign = '' # don't need to print -P0Y, just print P0Y
        hitFirstZeroYet = False
        if y is not None and y == 0:
            hitFirstZeroYet = True
        if m is not None and m == 0:
            if hitFirstZeroYet:
                m = None
            else:
                hitFirstZeroYet = True
        if d is not None and d == 0:
            if hitFirstZeroYet:
                d = None
            else:
                hitFirstZeroYet = True
        if h is not None and h == 0 and hitFirstZeroYet:
            h = None

    output = sign + "P"
    if y is not None:
        output += str(y) + 'Y'
    if m is not None and (m != 0 or y is None):
        output += str(m) + 'M'
    if d is not None and (d != 0 or (y is None and m is None)):
        output += str(d) + 'D'
    if h is not None and (h != 0 or (y is None and m is None and d is None)):
        output += 'T' + str(h) + 'H'
    return output

def numinf(arg):
    return "INF"

def numneginf(arg):
    return "-INF"

def numnan(arg):
    return "NaN"

numwordsenPattern = re_compile(r"^[ \t\n\r]*(((((([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)\s+[Hh]undred(\s+(and\s+)?(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))?)|(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))\s+[Qq]uintillion(\s*,\s*|\s+|$))?(((([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)\s+[Hh]undred(\s+(and\s+)?(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))?)|(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))\s+[Qq]uadrillion(\s*,\s*|\s+|$))?(((([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)\s+[Hh]undred(\s+(and\s+)?(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))?)|(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))\s+[Tt]rillion(\s*,\s*|\s+|$))?(((([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)\s+[Hh]undred(\s+(and\s+)?(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))?)|(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))\s+[Bb]illion(\s*,\s*|\s+|$))?(((([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)\s+[Hh]undred(\s+(and\s+)?(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))?)|(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))\s+[Mm]illion(\s*,\s*|\s+|$))?((((([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)\s+[Hh]undred(\s+(and\s+)?(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))?)|(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))\s+[Tt]housand((\s*,\s*|\s+)((([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)\s+[Hh]undred(\s+(and\s+)?(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))?)|(and\s+)?(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?)))?)|(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)\s+[Hh]undred(\s+(and\s+)?(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))?)|(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))?)|[Zz]ero|[Nn]o(ne)?|[Nn]il)[ \t\n\r]*$")

numwordsNoPattern = re_compile(r"^[ \t\n\r]*([Nn]o(ne)?|[Nn]il)[ \t\n\r]*$")

commaAndPattern = re_compile(r",|\sand\s") # substitute whitespace for comma or and

def numwordsen(arg):
    if not numwordsenPattern.match(arg) or len(arg) == 0:
        raise FunctionArgType(0, "numwordsen lexical error")
    elif numwordsNoPattern.match(arg): # match "no" or "none"
        return "0"
    try:
        return str(text2num(commaAndPattern.sub(" ", arg.strip().lower()))) # must be returned as a string
    except (NumberException, TypeError, ValueError) as ex:
        raise FunctionArgType(0, str(ex))

durwordsenPattern = re_compile(r"^[ \t\n\r]*((((([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)[Hh]undred(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)(and\s+)?(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))?)|(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))|[Zz]ero|[Nn]o|[0-9][0-9]{0,3})([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)[Yy]ears?(,?([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)(and\s+)?|$))?((((([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)[Hh]undred(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)(and\s+)?(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))?)|(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))|[Zz]ero|[Nn]o|[0-9][0-9]{0,3})([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)[Mm]onths?(,?([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)(and\s+)?|$))?((((([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)[Hh]undred(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)(and\s+)?(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))?)|(([Oo]ne|[Tt](wo|hree|en|welve|hirteen)|[Ff](our(teen)?|ive|ifteen)|[Ss](ix(teen)?|even(teen)?)|[Ee](ight(een)?|leven)|[Nn]ine(teen)?)|([Tt](wenty|hirty)|[Ff](orty|ifty)|[Ss](ixty|eventy)|[Ee]ighty|[Nn]inety)(([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)([Oo]ne|[Tt](wo|hree)|[Ff](our|ive)|[Ss](ix|even)|[Ee]ight|[Nn]ine))?))|[Zz]ero|[Nn]o|[0-9][0-9]{0,3})([\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]|\s+)[Dd]ays?)?[ \t\n\r]*$")

durwordZeroNoPattern = re_compile(r"^[ \t\n\r]*[\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]?([Zz]ero|[Nn]o(ne)?)[\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D-]?[ \t\n\r]*$")


def durwordsen(arg):
    durWordsMatch = durwordsenPattern.match(arg)
    if not durWordsMatch or len(arg.strip()) == 0:
        raise FunctionArgType(1, "durwordsen lexical error")
    try:
        dur = 'P'
        durWordsMatchGroups = durWordsMatch.groups()
        for groupIndex, groupSuffix in ((1,"Y"), (65,"M"), (129, "D")):
            groupPart = durWordsMatchGroups[groupIndex]
            if groupPart and not durwordZeroNoPattern.match(groupPart):
                if groupPart.isnumeric():
                    dur += groupPart + groupSuffix
                else:
                    dur += str(text2num(commaAndPattern.sub(" ", groupPart.strip().lower()))) + groupSuffix
        return dur if len(dur) > 1 else "P0D" # must have at least one number and designator
    except (NumberException, TypeError, ValueError) as ex:
        raise FunctionArgType(0, str(ex))

ballotboxPattern = re_compile(r"^[ \t\n\r]*([\u2610-\u2612])[ \t\n\r]*$")

def boolballotbox(arg):
    ballotboxMatch = ballotboxPattern.match(arg)
    if not ballotboxMatch or len(arg.strip()) == 0:
        raise FunctionArgType(1, "boolballotboxMatch lexical error")
    try:
        return ("false", "true", "true")[ord(ballotboxMatch.group(1)[0]) - ord('\u2610')]
    except (IndexException, TypeError) as ex:
        raise FunctionArgType(0, str(ex))

def yesnoballotbox(arg):
    ballotboxMatch = ballotboxPattern.match(arg)
    if not ballotboxMatch or len(arg.strip()) == 0:
        raise FunctionArgType(1, "yesnoballotboxMatch lexical error")
    try:
        return ("No", "Yes", "Yes")[ord(ballotboxMatch.group(1)[0]) - ord('\u2610')]
    except (IndexException, TypeError) as ex:
        raise FunctionArgType(0, str(ex))

def codeIndex(match):
    groups = match.groups()
    for grpNbr in range(1, len(groups)):
        if groups[grpNbr] is not None:
            # ith group matched, get pattern's code position
            parenNbr = 0 # outer paren is for the enclosure of all the groups
            for codeIndex, patternForCode in enumerate(match.re.pattern.split(")|")):
                inCharacterClass = False
                for c in patternForCode:
                    if c == "[":
                        inCharacterClass = True
                    elif c == "]":
                        inCharacterClass = False
                    if c == "(" and not inCharacterClass:
                        if parenNbr == grpNbr:
                            return codeIndex # this is the code which matched
                        parenNbr += 1
    return None # no match


countryNamePattern = re_compile(r"^[ \t\n\r]*(([Aa]fghanistan)|([ÅåAa]land\s+[Ii]slands)|([Aa]lbania)|([Aa]lgeria)|([Aa]merican\s+[Ss]amoa)|([Aa]ndorra)|([Aa]ngola)|([Aa]nguilla)|([Aa]ntarctica)|([Aa]ntigua\s+[Aa]nd\s+[Bb]arbuda)|((([Tt]he\s+)?[Rr]epublic\s+[Oo]f\s+)?[Aa]rgentina)|([Aa]rmenia)|([Aa]ruba)|([Aa]ustralia)|([Aa]ustria)|([Aa]zerbaijan)|([Bb]ahamas)|([Bb]ahrain)|([Bb]angladesh)|([Bb]arbados)|([Bb]elarus)|([Bb]elgium)|([Bb]elize)|([Bb]enin)|([Bb]ermuda)|([Bb]hutan)|([Bb]olivia)|([Bb]onaire,\s+[Ss]int\s+[Ee]ustatius\s+[Aa]nd\s+[Ss]aba)|([Bb]osnia\s+[Aa]nd\s+[Hh]erzegovina)|([Bb]otswana)|([Bb]ouvet\s+[Ii]sland)|((([Tt]he\s+)?[Ff]ederative\s+[Rr]epublic\s+[Oo]f\s+)?[Bb]ra[sz]il)|([Bb]ritish\s+[Ii]ndian\s+[Oo]cean\s+[Tt]erritory)|([Bb]runei\s+[Dd]arussalam)|([Bb]ulgaria)|([Bb]urkina\s+[Ff]aso)|([Bb]urundi)|([Cc]abo\s+[Vv]erde)|([Cc]ambodia)|([Cc]ameroon)|([Cc]anada)|([Cc]ayman\s+[Ii]slands)|([Cc]entral\s+[Aa]frican\s+[Rr]epublic)|([Cc]had)|([Cc]hile)|((([Tt]he\s+)?[Pp]eople['’]?s\s+[Rr]epublic\s+[Oo]f\s+)?[Cc]hina)|([Cc]hristmas\s+[Ii]sland)|([Cc]ocos\s+(.[Kk]eeling.\s+)?[Ii]slands)|((([Tt]he\s+)?[Rr]epublic\s+[Oo]f\s+)?[Cc]olombia)|([Cc]omoros)|([Dd]emocratic\s+[Rr]epublic\s+[Oo]f\s+([Tt]he\s+)?[Cc]ongo)|([Cc]ongo)|([Cc]ook\s+[Ii]slands)|([Cc]osta\s+[Rr]ica)|([Cc][ôo]te\s+d['’][Ii]voire)|([Cc]roatia)|([Cc]uba)|([Cc]ura[çc]ao)|([Cc]yprus)|([Cc]zechia|[Cc]zech\s+[Rr]epublic)|((([Tt]he\s+)?[Kk]ingdom\s+[Oo]f\s+)?[Dd]enmark)|([Dd]jibouti)|([Dd]ominica)|([Dd]ominican\s+[Rr]epublic)|([Ee]cuador)|([Ee]gypt)|([Ee]l\s+[Ss]alvador)|([Ee]quatorial\s+[Gg]uinea)|([Ee]ritrea)|([Ee]stonia)|([Ee]swatini)|([Ee]thiopia)|(([Tt]he\s+)?[Ff]alkland\s+[Ii]slands(\s+.[Mm]alvinas.)?|([Ii]slas\s+)?[Mm]alvinas(\s+[Ii]slands)?)|([Ff]aroe\s+[Ii]slands)|([Ff]iji)|([Ff]inland)|([Ff]rance)|([Ff]rench\s+[Gg]uiana)|([Ff]rench\s+[Pp]olynesia)|([Ff]rench\s+[Ss]outhern\s+[Tt]erritories)|([Gg]abon)|([Gg]ambia)|([Gg]eorgia)|([Gg]ermany)|([Gg]hana)|([Gg]ibraltar)|([Gg]reece)|([Gg]reenland)|([Gg]renada)|([Gg]uadeloupe)|([Gg]uam)|([Gg]uatemala)|([Gg]uernsey)|([Gg]uinea)|([Gg]uinea-[Bb]issau)|([Gg]uyana)|([Hh]aiti)|([Hh]eard\s+[Ii]sland\s+[Aa]nd\s+[Mm]cDonald\s+[Ii]slands)|(([Tt]he\s+)?[Hh]oly\s+[Ss]ee|[Vv]atican\s+[Cc]ity)|([Hh]onduras)|([Hh]ong\s+[Kk]ong)|([Hh]ungary)|([Ii]celand)|([Ii]ndia)|([Ii]ndonesia)|((([Tt]he\s+)?[Ii]slamic\s+[Rr]epublic\s+of\s+)?[Ii]ran)|([Ii]raq)|([Ii]reland)|([Ii]sle\s+[Oo]f\s+[Mm]an)|([Ii]srael)|([Ii]taly)|([Jj]amaica)|([Jj]apan)|([Jj]ersey)|([Jj]ordan)|([Kk]azakhstan)|([Kk]enya)|([Kk]iribati)|(([Nn]orth|[Dd]emocratic\s+[Pp]eople['’]?s\s+[Rr]epublic\s+[Oo]f)\s+[Kk]orea)|(([Ss]outh|[Rr]epublic\s+[Oo]f)\s+[Kk]orea)|([Kk]uwait)|([Kk]yrgyzstan)|([Ll]ao\s+[Pp]eople['’]?s\s+[Dd]emocratic\s+[Rr]epublic)|([Ll]atvia)|([Ll]ebanon)|([Ll]esotho)|([Ll]iberia)|((([Tt]he\s+)?[Ss]tate\s+[Oo]f\s+)?[Ll]ibya)|([Ll]iechtenstein)|([Ll]ithuania)|((([Tt]he\s+)?([Gg]rand\s+)?[Dd]uchy\s+[Oo]f\s+)?[Ll]uxembourg)|([Mm]aca[ou])|([Mm]adagascar)|([Mm]alawi)|([Mm]alaysia)|([Mm]aldives)|([Mm]ali)|([Mm]alta)|((([Tt]he\s+)?[Rr]epublic\s+[Oo]f\s+([Tt]he\s+)?)?[Mm]arshall\s+[Ii]slands)|([Mm]artinique)|([Mm]auritania)|([Mm]auritius)|([Mm]ayotte)|([Mm]exico|[Uu]nited\s+[Mm]exican\s+[Ss]tates)|((([Tt]he\s+)?[Ff]ederated\s+[Ss]tates\s+[Oo]f\s+)?[Mm]icronesia)|((([Tt]he\s+)?[Rr]epublic\s+[Oo]f\s+)?[Mm]oldova)|([Mm]onaco)|([Mm]ongolia)|([Mm]ontenegro)|([Mm]ontserrat)|([Mm]orocco)|([Mm]ozambique)|([Mm]yanmar)|([Nn]amibia)|([Nn]auru)|([Nn]epal)|([Nn]etherlands)|([Nn]ew\s+[Cc]aledonia)|([Nn]ew\s+[Zz]ealand)|([Nn]icaragua)|([Nn]iger)|([Nn]igeria)|([Nn]iue)|([Nn]orfolk\s+[Ii]sland)|((([Tt]he\s+)?[Rr]epublic\s+[Oo]f\s+)?[Nn]orth\s+[Mm]acedonia)|([Nn]orthern\s+[Mm]ariana\s+[Ii]slands)|([Nn]orway)|([Oo]man)|([Pp]akistan)|([Pp]alau)|((([Tt]he\s+)?[Ss]tate\s+[Oo]f\s+)?[Pp]alestine)|([Pp]anama)|([Pp]apua\s+[Nn]ew\s+[Gg]uinea)|([Pp]araguay)|([Pp]eru)|([Pp]hilippines)|([Pp]itcairn)|([Pp]oland)|([Pp]ortugal)|([Pp]uerto\s+[Rr]ico)|([Qq]atar)|([Rr][ée]union)|([Rr]omania)|([Rr]ussian\s+[Ff]ederation)|([Rr]wanda)|([Ss]aint\s+[Bb]arth[ée]lemy)|([Ss]aint\s+[Hh]elena(,\s+[Aa]scension,?\s+[Aa]nd\s+[Tt]ristan(\s+[Dd]a\s+[Cc]unha)?)?)|([Ss]aint\s+[Kk]itts\s+[Aa]nd\s+[Nn]evis)|([Ss]aint\s+[Ll]ucia)|([Ss]aint\s+[Mm]artin)|([Ss]aint\s+[Pp]ierre\s+[Aa]nd\s+[Mm]iquelon)|([Ss]aint\s+[Vv]incent(\s+[Aa]nd\s+([Tt]he\s+)?[Gg]renadines)?)|([Ss]amoa)|([Ss]an\s+[Mm]arino)|([Ss]ao\s+[Tt]ome\s+[Aa]nd\s+[Pp]rincipe)|([Ss]audi\s+[Aa]rabia)|([Ss]enegal)|([Ss]erbia)|([Ss]eychelles)|([Ss]ierra\s+[Ll]eone)|([Ss]ingapore)|([Ss]int\s+[Mm]aarten)|([Ss]lovakia)|([Ss]lovenia)|([Ss]olomon\s+[Ii]slands)|([Ss]omalia)|((([Tt]he\s+)?[Rr]epublic\s+[Oo]f\s+)?[Ss]outh\s+[Aa]frica)|([Ss]outh\s+[Gg]eorgia\s+[Aa]nd\s+([Tt]he\s+)?[Ss]outh\s+[Ss]andwich\s+[Ii]slands)|([Ss]outh\s+[Ss]udan)|((([Tt]he\s+)?[Kk]ingdom\s+[Oo]f\s+)?[Ss]pain|[Ee]spa[ñn]a)|([Ss]ri\s+[Ll]anka)|([Ss]udan)|([Ss]uriname)|([Ss]valbard\s+[Aa]nd\s+[Jj]an\s+[Mm]ayen)|([Ss]weden)|([Ss]witzerland)|([Ss]yria(n\s+[Aa]rab\s+[Rr]epublic)?)|([Tt]aiwan(,?\s+[Pp]rovince\s+[Oo]f\s+[Cc]hina)?)|([Tt]ajikistan)|((([Tt]he\s+)?[Uu]nited\s+[Rr]epublic\s+[Oo]f\s+)?[Tt]anzania)|([Tt]hailand)|([Tt]imor-[Ll]este)|([Tt]ogo)|([Tt]okelau)|([Tt]onga)|([Tt]rinidad\s+[Aa]nd\s+[Tt]obago)|([Tt]unisia)|([Tt][uü]rk(ey|iye))|([Tt]urkmenistan)|([Tt]urks\s+[Aa]nd\s+[Cc]aicos\s+[Ii]slands)|([Tt]uvalu)|([Uu]ganda)|([Uu]kraine)|(UAE|[Uu]nited\s+[Aa]rab\s+[Ee]mirates)|(U[.]?K[.]?|[Bb]ritain|[Gg]reat\s+[BBb]ritain|[Uu]nited\s+[Kk]ingdom(\s+[Oo]f\s+[Gg]reat\s+[Bb]ritain\s+[Aa]nd\s+[Nn]orthern\s+[Ii]reland)?|[Ee]ngland(\s+[Aa]nd\s+[Ww]ales)?)|([Uu]nited\s+[Ss]tates\s+[Mm]inor\s+[Oo]utlying\s+[Ii]slands)|(U[.]?S[.]?A[.]?|[Uu]nited\s+[Ss]tates(\s+[Oo]f\s+[Aa]merica)?)|([Uu]ruguay)|([Uu]zbekistan)|([Vv]anuatu)|([Vv]enezuela)|([Vv]iet\s+[Nn]am)|([Bb]ritish\s+[Vv]irgin\s+[Ii]slands)|([Uu][.]?[Ss][.]?\s+[Vv]irgin\s+[Ii]slands)|([Ww]allis\s+[Aa]nd\s+[Ff]utuna)|([Ww]estern\s+[Ss]ahara*)|([Yy]emen)|([Zz]ambia)|([Zz]imbabwe))[ \t\n\r]*$")

countryCodes = ("AF", "AX", "AL", "DZ", "AS", "AD", "AO", "AI", "AQ", "AG", "AR", "AM", "AW", "AU", "AT", "AZ", "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ", "BM", "BT", "BO", "BQ", "BA", "BW", "BV", "BR", "IO", "BN", "BG", "BF", "BI", "CV", "KH", "CM", "CA", "KY", "CF", "TD", "CL", "CN", "CX", "CC", "CO", "KM", "CD", "CG", "CK", "CR", "CI", "HR", "CU", "CW", "CY", "CZ", "DK", "DJ", "DM", "DO", "EC", "EG", "SV", "GQ", "ER", "EE", "SZ", "ET", "FK", "FO", "FJ", "FI", "FR", "GF", "PF", "TF", "GA", "GM", "GE", "DE", "GH", "GI", "GR", "GL", "GD", "GP", "GU", "GT", "GG", "GN", "GW", "GY", "HT", "HM", "VA", "HN", "HK", "HU", "IS", "IN", "ID", "IR", "IQ", "IE", "IM", "IL", "IT", "JM", "JP", "JE", "JO", "KZ", "KE", "KI", "KP", "KR", "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY", "LI", "LT", "LU", "MO", "MG", "MW", "MY", "MV", "ML", "MT", "MH", "MQ", "MR", "MU", "YT", "MX", "FM", "MD", "MC", "MN", "ME", "MS", "MA", "MZ", "MM", "NA", "NR", "NP", "NL", "NC", "NZ", "NI", "NE", "NG", "NU", "NF", "MK", "MP", "NO", "OM", "PK", "PW", "PS", "PA", "PG", "PY", "PE", "PH", "PN", "PL", "PT", "PR", "QA", "RE", "RO", "RU", "RW", "BL", "SH", "KN", "LC", "MF", "PM", "VC", "WS", "SM", "ST", "SA", "SN", "RS", "SC", "SL", "SG", "SX", "SK", "SI", "SB", "SO", "ZA", "GS", "SS", "ES", "LK", "SD", "SR", "SJ", "SE", "CH", "SY", "TW", "TJ", "TZ", "TH", "TL", "TG", "TK", "TO", "TT", "TN", "TR", "TM", "TC", "TV", "UG", "UA", "AE", "GB", "UM", "US", "UY", "UZ", "VU", "VE", "VN", "VG", "VI", "WF", "EH", "YE", "ZM", "ZW")

def countrynameen(arg):
    countryMatch = countryNamePattern.match(arg)
    if not countryMatch or len(arg.strip()) == 0:
        raise FunctionArgType(1, "countrynameen lexical error")
    try:
        return countryCodes[codeIndex(countryMatch)]
    except (IndexException, TypeError) as ex:
        raise FunctionArgType(0, str(ex))

stateProvNamePattern = re_compile(r"^[ \t\n\r]*(([Aa]labama)|([Aa]laska)|([Aa]rizona)|([Aa]rkansas)|([Cc]alifornia)|([Cc]olorado)|([Cc]onnecticut)|([Dd]elaware)|([Ff]lorida)|([Gg]eorgia)|([Hh]awaii)|([Ii]daho)|([Ii]llinois)|([Ii]ndiana)|([Ii]owa)|([Kk]ansas)|([Kk]entucky)|([Ll]ouisiana)|([Mm]aine)|([Mm]aryland)|([Mm]assachusetts)|([Mm]ichigan)|([Mm]innesota)|([Mm]ississippi)|([Mm]issouri)|([Mm]ontana)|([Nn]ebraska)|([Nn]evada)|([Nn]ew\s+[Hh]ampshire)|([Nn]ew\s+[Jj]ersey)|([Nn]ew\s+[Mm]exico)|([Nn]ew\s+[Yy]ork)|([Nn]orth\s+[Cc]arolina)|([Nn]orth\s+[Dd]akota)|([Oo]hio)|([Oo]klahoma)|([Oo]regon)|([Pp]ennsylvania)|([Rr]hode\s+[Ii]sland)|([Ss]outh\s+[Cc]arolina)|([Ss]outh\s+[Dd]akota)|([Tt]ennessee)|([Tt]exas)|([Uu]tah)|([Vv]ermont)|([Vv]irginia)|([Ww]ashington)|([Ww]est\s+[Vv]irginia)|([Ww]isconsin)|([Ww]yoming)|([Dd]istrict\s+[Oo]f\s+[Cc]olumbia)|(([Aa]merican\s+)?[Ss]amoa)|([Gg]uam)|([Nn]orthern\s+[Mm]ariana\s+[Ii]slands)|([Pp]uerto\s+[Rr]ico)|([Uu]nited\s+[Ss]tates\s+[Mm]inor\s+[Oo]utlying\s+[Ii]slands)|([Vv]irgin\s+[Ii]slands,\s+U[.]S[.])|([Aa]lberta)|([Bb]ritish\s+[Cc]olumbia)|([Mm]anitoba)|([Nn]ew\s+[Bb]runswick)|([Nn]ewfoundland(\s+[Aa]nd\s+[Ll]abrador)?)|([Nn]ova\s+[Ss]cotia)|([Nn]orthwest\s+[Tt]erritories)|([Nn]unavut)|([Oo]ntario)|([Pp]rince\s+[Ee]dward\s+[Ii]sland)|([Qq]u[eé]bec)|([Ss]askatchewan)|([Yy]ukon))[ \t\n\r]*$")

stateProvCodes = ("AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC", "AS", "GU", "MP", "PR", "UM", "VI", "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT")

def stateprovnameen(arg):
    stateProvMatch = stateProvNamePattern.match(arg)
    if not stateProvMatch or len(arg.strip()) == 0:
        raise FunctionArgType(1, "stateprovnameen lexical error")
    try:
        return stateProvCodes[codeIndex(stateProvMatch)]
    except (IndexException, TypeError) as ex:
        raise FunctionArgType(0, str(ex))

edgarProvCountryNamePattern = re_compile(r"^[ \t\n\r]*(([Aa]merican\s+[Ss]amoa)|([Gg]uam)|([Pp]uerto\s+[Rr]ico)|([Uu]nited\s+[Ss]tates\s+[Mm]inor\s+[Oo]utlying\s+[Ii]slands)|([Vv]irgin\s+[Ii]slands,\s+U[.]?S[.]?|U([.]\s*)?S[.]?\s+[Vv]irgin\s+[Ii]slands)|([Aa]lberta(,?\s+[Cc]anada)?)|([Bb]ritish\s+[Cc]olumbia(,?\s+[Cc]anada)?)|([Mm]anitoba(,?\s+[Cc]anada)?)|([Nn]ew\s+[Bb]runswick(,?\s+[Cc]anada)?)|([Nn]ewfoundland(\s+[Aa]nd\s+[Ll]abrador)?(,?\s+[Cc]anada)?)|([Nn]ova\s+[Ss]cotia(,?\s+[Cc]anada)?)|([Oo]ntario(,?\s+[Cc]anada)?)|([Pp]rince\s+[Ee]dward\s+[Ii]sland(,?\s+[Cc]anada)?)|([Qq]u[eé]bec(,?\s+[Cc]anada)?)|([Ss]askatchewan(,?\s+[Cc]anada)?)|([Yy]ukon(,?\s+[Cc]anada)?)|([Aa]fghanistan)|([ÅåAa]land\s+[Ii]slands)|([Aa]lbania)|([Aa]lgeria)|([Aa]merican\s+[Ss]amoa)|([Aa]ndorra)|([Aa]ngola)|([Aa]nguilla)|([Aa]ntarctica)|([Aa]ntigua\s+[Aa]nd\s+[Bb]arbuda)|((([Tt]he\s+)?[Rr]epublic\s+[Oo]f\s+)?[Aa]rgentina)|([Aa]rmenia)|([Aa]ruba)|([Aa]ustralia)|([Aa]ustria)|([Aa]zerbaijan)|([Bb]ahamas)|([Bb]ahrain)|([Bb]angladesh)|([Bb]arbados)|([Bb]elarus)|([Bb]elgium)|([Bb]elize)|([Bb]enin)|([Bb]ermuda)|([Bb]hutan)|([Bb]olivia)|([Bb]osnia\s+[Aa]nd\s+[Hh]erzegovina)|([Bb]otswana)|([Bb]ouvet\s+[Ii]sland)|((([Tt]he\s+)?[Ff]ederative\s+[Rr]epublic\s+[Oo]f\s+)?[Bb]ra[sz]il)|([Bb]ritish\s+[Ii]ndian\s+[Oo]cean\s+[Tt]erritory)|([Bb]runei\s+[Dd]arussalam)|([Bb]ulgaria)|([Bb]urkina\s+[Ff]aso)|([Bb]urundi)|([Cc]a(bo|pe)\s+[Vv]erde)|([Cc]ambodia)|([Cc]ameroon)|([Cc]anada)|([Cc]ayman\s+[Ii]slands)|([Cc]entral\s+[Aa]frican\s+[Rr]epublic)|([Cc]had)|([Cc]hile)|((([Tt]he\s+)?[Pp]eople['’]?s\s+[Rr]epublic\s+[Oo]f\s+)?[Cc]hina)|([Cc]hristmas\s+[Ii]sland)|([Cc]ocos\s+(.[Kk]eeling.\s+)?[Ii]slands)|((([Tt]he\s+)?[Rr]epublic\s+[Oo]f\s+)?[Cc]olombia)|([Cc]omoros)|([Dd]emocratic\s+[Rr]epublic\s+[Oo]f\s+([Tt]he\s+)?[Cc]ongo)|([Cc]ongo)|([Cc]ook\s+[Ii]slands)|([Cc]osta\s+[Rr]ica)|([Cc][ôo]te\s+d['’][Ii]voire)|([Cc]roatia)|([Cc]uba)|([Cc]yprus)|([Cc]zechia|[Cc]zech\s+[Rr]epublic)|((([Tt]he\s+)?[Kk]ingdom\s+[Oo]f\s+)?[Dd]enmark)|([Dd]jibouti)|([Dd]ominica)|([Dd]ominican\s+[Rr]epublic)|([Ee]cuador)|([Ee]gypt)|([Ee]l\s+[Ss]alvador)|([Ee]quatorial\s+[Gg]uinea)|([Ee]ritrea)|([Ee]stonia)|([Ee]thiopia)|(([Tt]he\s+)?[Ff]alkland\s+[Ii]slands(\s+.[Mm]alvinas.)?|([Ii]slas\s+)?[Mm]alvinas(\s+[Ii]slands)?)|([Ff]aroe\s+[Ii]slands)|([Ff]iji)|([Ff]inland)|([Ff]rance)|([Ff]rench\s+[Gg]uiana)|([Ff]rench\s+[Pp]olynesia)|([Ff]rench\s+[Ss]outhern\s+[Tt]erritories)|([Gg]abon)|([Gg]ambia)|([Gg]eorgia)|([Gg]ermany)|([Gg]hana)|([Gg]ibraltar)|([Gg]reece)|([Gg]reenland)|([Gg]renada)|([Gg]uadeloupe)|([Gg]uatemala)|([Gg]uernsey)|([Gg]uinea)|([Gg]uinea-[Bb]issau)|([Gg]uyana)|([Hh]aiti)|([Hh]eard\s+[Ii]sland\s+[Aa]nd\s+[Mm]cDonald\s+[Ii]slands)|(([Tt]he\s+)?[Hh]oly\s+[Ss]ee|[Vv]atican\s+[Cc]ity)|([Hh]onduras)|([Hh]ong\s+[Kk]ong)|([Hh]ungary)|([Ii]celand)|([Ii]ndia)|([Ii]ndonesia)|((([Tt]he\s+)?[Ii]slamic\s+[Rr]epublic\s+of\s+)?[Ii]ran)|([Ii]raq)|([Ii]reland)|([Ii]sle\s+[Oo]f\s+[Mm]an)|([Ii]srael)|([Ii]taly)|([Jj]amaica)|([Jj]apan)|([Jj]ersey)|([Jj]ordan)|([Kk]azakhstan)|([Kk]enya)|([Kk]iribati)|(([Nn]orth|[Dd]emocratic\s+[Pp]eople['’]?s\s+[Rr]epublic\s+[Oo]f)\s+[Kk]orea)|(([Ss]outh|[Rr]epublic\s+[Oo]f)\s+[Kk]orea)|([Kk]uwait)|([Kk]yrgyzstan)|([Ll]ao\s+[Pp]eople['’]?s\s+[Dd]emocratic\s+[Rr]epublic)|([Ll]atvia)|([Ll]ebanon)|([Ll]esotho)|([Ll]iberia)|((([Tt]he\s+)?[Ss]tate\s+[Oo]f\s+)?[Ll]ibya)|([Ll]iechtenstein)|([Ll]ithuania)|((([Tt]he\s+)?([Gg]rand\s+)?[Dd]uchy\s+[Oo]f\s+)?[Ll]uxembourg)|([Mm]aca[ou])|([Mm]adagascar)|([Mm]alawi)|([Mm]alaysia)|([Mm]aldives)|([Mm]ali)|([Mm]alta)|((([Tt]he\s+)?[Rr]epublic\s+[Oo]f\s+([Tt]he\s+)?)?[Mm]arshall\s+[Ii]slands)|([Mm]artinique)|([Mm]auritania)|([Mm]auritius)|([Mm]ayotte)|([Mm]exico|[Uu]nited\s+[Mm]exican\s+[Ss]tates)|((([Tt]he\s+)?[Ff]ederated\s+[Ss]tates\s+[Oo]f\s+)?[Mm]icronesia)|((([Tt]he\s+)?[Rr]epublic\s+[Oo]f\s+)?[Mm]oldova)|([Mm]onaco)|([Mm]ongolia)|([Mm]ontenegro)|([Mm]ontserrat)|([Mm]orocco)|([Mm]ozambique)|([Mm]yanmar)|([Nn]amibia)|([Nn]auru)|([Nn]epal)|([Nn]etherlands\s+[Aa]ntilles)|([Nn]etherlands)|([Nn]ew\s+[Cc]aledonia)|([Nn]ew\s+[Zz]ealand)|([Nn]icaragua)|([Nn]iger)|([Nn]igeria)|([Nn]iue)|([Nn]orfolk\s+[Ii]sland)|((([Tt]he\s+)?[Rr]epublic\s+[Oo]f\s+)?([Nn]orth\s+)?[Mm]acedonia)|([Nn]orthern\s+[Mm]ariana\s+[Ii]slands)|([Nn]orway)|([Oo]man)|([Pp]akistan)|([Pp]alau)|((([Tt]he\s+)?[Ss]tate\s+[Oo]f\s+)?[Pp]alestine)|([Pp]anama)|([Pp]apua\s+[Nn]ew\s+[Gg]uinea)|([Pp]araguay)|([Pp]eru)|([Pp]hilippines)|([Pp]itcairn)|([Pp]oland)|([Pp]ortugal)|([Qq]atar)|([Rr][ée]union)|([Rr]omania)|([Rr]ussian\s+[Ff]ederation)|([Rr]wanda)|([Ss]aint\s+[Bb]arth[ée]lemy)|([Ss]aint\s+[Hh]elena(,\s+[Aa]scension,?\s+[Aa]nd\s+[Tt]ristan(\s+[Dd]a\s+[Cc]unha)?)?)|([Ss]aint\s+[Kk]itts\s+[Aa]nd\s+[Nn]evis)|([Ss]aint\s+[Ll]ucia)|([Ss]aint\s+[Mm]artin)|([Ss]aint\s+[Pp]ierre\s+[Aa]nd\s+[Mm]iquelon)|([Ss]aint\s+[Vv]incent(\s+[Aa]nd\s+([Tt]he\s+)?[Gg]renadines)?)|([Ss]amoa)|([Ss]an\s+[Mm]arino)|([Ss]ao\s+[Tt]ome\s+[Aa]nd\s+[Pp]rincipe)|([Ss]audi\s+[Aa]rabia)|([Ss]enegal)|([Ss]erbia)|([Ss]eychelles)|([Ss]ierra\s+[Ll]eone)|([Ss]ingapore)|([Ss]lovakia)|([Ss]lovenia)|([Ss]olomon\s+[Ii]slands)|([Ss]omalia)|((([Tt]he\s+)?[Rr]epublic\s+[Oo]f\s+)?[Ss]outh\s+[Aa]frica)|([Ss]outh\s+[Gg]eorgia\s+[Aa]nd\s+([Tt]he\s+)?[Ss]outh\s+[Ss]andwich\s+[Ii]slands)|((([Tt]he\s+)?[Kk]ingdom\s+[Oo]f\s+)?[Ss]pain|[Ee]spa[ñn]a)|([Ss]ri\s+[Ll]anka)|([Ss]udan)|([Ss]uriname)|([Ss]valbard\s+[Aa]nd\s+[Jj]an\s+[Mm]ayen)|([Ss]waziland)|([Ss]weden)|([Ss]witzerland)|([Ss]yria(n\s+[Aa]rab\s+[Rr]epublic)?)|([Tt]aiwan(,?\s+[Pp]rovince\s+[Oo]f\s+[Cc]hina)?)|([Tt]ajikistan)|((([Tt]he\s+)?[Uu]nited\s+[Rr]epublic\s+[Oo]f\s+)?[Tt]anzania)|([Tt]hailand)|([Tt]imor-[Ll]este)|([Tt]ogo)|([Tt]okelau)|([Tt]onga)|([Tt]rinidad\s+[Aa]nd\s+[Tt]obago)|([Tt]unisia)|([Tt][uü]rk(ey|iye))|([Tt]urkmenistan)|([Tt]urks\s+[Aa]nd\s+[Cc]aicos\s+[Ii]slands)|([Tt]uvalu)|([Uu]ganda)|([Uu]kraine)|(UAE|[Uu]nited\s+[Aa]rab\s+[Ee]mirates)|(U[.]?K[.]?|[Bb]ritain|[Gg]reat\s+[BBb]ritain|[Uu]nited\s+[Kk]ingdom(\s+[Oo]f\s+[Gg]reat\s+[Bb]ritain\s+[Aa]nd\s+[Nn]orthern\s+[Ii]reland)?|[Ee]ngland(\s+[Aa]nd\s+[Ww]ales)?)|([Uu]nited\s+[Ss]tates\s+[Mm]inor\s+[Oo]utlying\s+[Ii]slands)|(U[.]?S[.]?A[.]?|[Uu]nited\s+[Ss]tates(\s+[Oo]f\s+[Aa]merica)?)|([Uu]ruguay)|([Uu]zbekistan)|([Vv]anuatu)|([Vv]enezuela)|([Vv]iet\s+[Nn]am)|([Bb]ritish\s+[Vv]irgin\s+[Ii]slands|[Vv]irgin\s+[Ii]slands,?\s+[Bb]ritish)|([Ww]allis\s+[Aa]nd\s+[Ff]utuna)|([Ww]estern\s+[Ss]ahara*)|([Yy]emen)|([Zz]ambia)|([Zz]imbabwe)|([Uu]nknown))[ \t\n\r]*$")

edgarProvCountryCodes = ("B5", "GU", "PR", "2J", "VI", "A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "B0", "B2", "Y6", "B3", "B4", "B5", "B6", "B7", "1A", "B8", "B9", "C1", "1B", "1C", "C3", "C4", "1D", "C5", "C6", "C7", "C8", "1F", "C9", "D1", "G6", "D0", "D2", "D3", "1E", "B1", "D4", "D5", "D6", "D9", "E0", "X2", "E2", "E8", "E3", "E4", "Z4", "E9", "F0", "F2", "F3", "F4", "F6", "F7", "F8", "F9", "Y3", "G0", "G1", "G2", "L7", "1M", "G3", "G4", "2N", "G7", "1G", "G9", "G8", "H1", "H2", "H3", "H4", "1J", "1H", "H5", "H7", "H6", "H8", "H9", "I0", "I3", "I4", "2C", "I5", "I6", "2Q", "2M", "J0", "J1", "J3", "J4", "J5", "J6", "J8", "Y7", "J9", "S0", "K0", "K1", "K4", "X4", "K2", "K3", "K5", "K6", "K7", "K8", "K9", "L0", "L2", "Y8", "L3", "L6", "L8", "M0", "Y9", "M2", "1P", "M3", "J2", "M4", "M5", "M6", "1N", "M7", "1R", "M8", "M9", "N0", "N1", "N2", "1Q", "N4", "N5", "N6", "N7", "N8", "N9", "O0", "O1", "1T", "O2", "O3", "O4", "2P", "O5", "1K", "1S", "O9", "P0", "Z5", "P1", "P2", "P3", "E1", "T6", "P5", "P6", "P8", "P7", "1W", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "1U", "1V", "Q8", "P4", "R0", "1Y", "1X", "R1", "R2", "R4", "R5", "R6", "R8", "R9", "S1", "S3", "S4", "S5", "1Z", "S6", "Z0", "U8", "U7", "U9", "Z1", "V0", "V1", "Y0", "S8", "S9", "T0", "T1", "Z2", "T2", "T8", "U0", "2B", "2A", "D7", "U1", "T3", "1L", "U3", "F1", "V2", "V3", "L9", "V6", "V7", "V8", "V9", "F5", "2D", "W0", "W1", "Z3", "W2", "W3", "W4", "W5", "W6", "W8", "2E", "W7", "2G", "W9", "2H", "C0", "X0", "2J", "X1", "X3", "2K", "2L", "X5", "Q1", "D8", "X8", "U5", "T7", "Y4", "Y5", "XX")

def edgarprovcountryen(arg):
    edgarProvCountryMatch = edgarProvCountryNamePattern.match(arg)
    if not edgarProvCountryMatch or len(arg.strip()) == 0:
        raise FunctionArgType(1, "stateorcountrynameen lexical error")
    try:
        return edgarProvCountryCodes[codeIndex(edgarProvCountryMatch)]
    except (IndexException, TypeError) as ex:
        raise FunctionArgType(0, str(ex))

exchNamePattern = re_compile(r"^[ \t\n\r]*((([Tt]he\s+)?[Bb][Oo][Xx]\s+[Ee]xchange(,?\s+[Ll][Ll][Cc])?)|(([Tt]he\s+)?[Cc]boe\s+[Bb][Yy][Xx]\s+[Ee]xchange(,?\s+[Ii]nc[.]?)?)|(([Tt]he\s+)?[Cc]boe\s+[Bb][Zz][Xx]\s+[Ee]xchange(,?\s+[Ii]nc[.]?)?)|(([Tt]he\s+)?[Cc]boe\s+[Cc]2\s+[Ee]xchange(,?\s+[Ii]nc[.]?)?)|(([Tt]he\s+)?[Cc]boe\s+[Ee][Dd][Gg][Aa]\s+[Ee]xchange(,?\s+[Ii]nc[.]?)?)|(([Tt]he\s+)?[Cc]boe\s+[Ee][Dd][Gg][Xx]\s+[Ee]xchange(,?\s+[Ii]nc[.]?)?)|(([Tt]he\s+)?[Cc]boe\s+[Ee]xchange(,?\s+[Ii]nc[.]?)?)|(([Tt]he\s+)?[Cc]hicago\s+[Ss]tock\s+[Ee]xchange(,?\s+[Ii]nc[.]?)?)|(([Tt]he\s+)?[Ii]nvestors\s+[Ee]xchange(,?\s+[Ll][Ll][Cc])?)|(([Tt]he\s+)?[Mm]iami\s+[Ii]nternational\s+[Ss]ecurities\s+[Ee]xchange(,?\s+[Ll][Ll][Cc])?)|(([Tt]he\s+)?[Mm]IAX\s+[Pp]EARL(,?\s+[Ll][Ll][Cc])?)|(([Tt]he\s+)?[Nn][Aa][Ss][Dd][Aa][Qq]\s+[Bb][Xx](,?\s+[Ii]nc[.]?)?)|(([Tt]he\s+)?[Nn][Aa][Ss][Dd][Aa][Qq]\s+[Gg][Ee][Mm][Xx](,?\s+[Ll][Ll][Cc])?)|(([Tt]he\s+)?[Nn][Aa][Ss][Dd][Aa][Qq]\s+[Ii][Ss][Ee](,?\s+[Ll][Ll][Cc])?)|(([Tt]he\s+)?[Nn][Aa][Ss][Dd][Aa][Qq]\s+[Mm][Rr][Xx](,?\s+[Ll][Ll][Cc])?)|([Nn][Aa][Ss][Dd][Aa][Qq]\s+[Pp][Hh][Ll][Xx](,?\s+[Ll][Ll][Cc])?)|(([Tt]he\s+)?[Nn][Yy][Ss][Ee]|([Tt]he\s+)?[Nn]ew\s+[Yy]ork\s+[Ss]tock\s+[Ee]xchange(,?\s+[Ll][Ll][Cc])?)|(([Tt]he\s+)?[Nn][Yy][Ss][Ee]\s+[Aa]merican(,?\s+[Ll][Ll][Cc])?)|(([Tt]he\s+)?[Nn][Yy][Ss][Ee]\s+[Aa]rca(,?\s+[Ii]nc[.]?)?)|(([Tt]he\s+)?[Nn][Yy][Ss][Ee]\s+[Nn]ational(,?\s+[Ii]nc[.]?)?)|(([Tt]he\s+)?[Nn][Aa][Ss][Dd][Aa][Qq](\s+([Ss]tock|[Gg]lobal(\s+[Ss]elect)?)\s+[Mm]arket(,?\s+[Ll][Ll][Cc])?)?))[ \t\n\r]*$")

exchCodes = ("BOX", "CboeBYX", "CboeBZX", "C2", "CboeEDGA", "CboeEDGX", "CBOE", "CHX", "IEX", "MIAX", "PEARL", "BX", "GEMX", "ISE", "MRX", "Phlx", "NYSE", "NYSEAMER", "NYSEArca", "NYSENAT", "NASDAQ")

def exchnameen(arg):
    exchMatch = exchNamePattern.match(arg)
    if not exchMatch or len(arg.strip()) == 0:
        raise FunctionArgType(1, "exchnameen lexical error")
    try:
        return exchCodes[codeIndex(exchMatch)]
    except (IndexException, TypeError) as ex:
        raise FunctionArgType(0, str(ex))

entityFilerNamePattern = re_compile(r"^[ \t\n\r]*(([Ll]arge\s+[Aa]ccelerated\s+[Ff]iler)|([Aa]ccelerated\s+[Ff]iler)|([Nn]on[^\w]+[Aa]ccelerated\s+[Ff]iler))[ \t\n\r]*$")

entityFilerCodes = ("Large Accelerated Filer", "Accelerated Filer", "Non-accelerated Filer")


def entityfilercategoryen(arg):
    entityFilerMatch = entityFilerNamePattern.match(arg)
    if not entityFilerMatch or len(arg.strip()) == 0:
        raise FunctionArgType(1, "entityfilercategoryen lexical error")
    try:
        return entityFilerCodes[codeIndex(entityFilerMatch)]
    except (IndexException, TypeError) as ex:
        raise FunctionArgType(0, str(ex))

def loadSECtransforms(customTransforms, *args, **kwargs):
    ixtSEC = "http://www.sec.gov/inlineXBRL/transformation/2015-08-31"
    customTransforms.update({
        qname(ixtSEC, "ixt-sec:duryear"): duryear,
        qname(ixtSEC, "ixt-sec:durmonth"): durmonth,
        qname(ixtSEC, "ixt-sec:durweek"): durweek,
        qname(ixtSEC, "ixt-sec:durday"): durday,
        qname(ixtSEC, "ixt-sec:durhour"): durhour,
        qname(ixtSEC, "ixt-sec:datequarterend"): datequarterend,
        qname(ixtSEC, "ixt-sec:numinf"): numinf,
        qname(ixtSEC, "ixt-sec:numneginf"): numneginf,
        qname(ixtSEC, "ixt-sec:numnan"): numnan,
        qname(ixtSEC, "ixt-sec:numwordsen"): numwordsen,
        qname(ixtSEC, "ixt-sec:durwordsen"): durwordsen,
        qname(ixtSEC, "ixt-sec:boolballotbox"): boolballotbox,
        qname(ixtSEC, "ixt-sec:yesnoballotbox"): yesnoballotbox,
        qname(ixtSEC, "ixt-sec:countrynameen"): countrynameen,
        qname(ixtSEC, "ixt-sec:stateprovnameen"): stateprovnameen,
        qname(ixtSEC, "ixt-sec:edgarprovcountryen"): edgarprovcountryen,
        qname(ixtSEC, "ixt-sec:exchnameen"): exchnameen,
        qname(ixtSEC, "ixt-sec:entityfilercategoryen"): entityfilercategoryen
    })

__pluginInfo__ = {
    'name': 'SEC Inline Transforms',
    'version': '19.2', # SEC version
    'description': "This plug-in adds custom transforms SEC inline filing with durations.  ",
    'license': 'Apache-2',
    'author': f'SEC employees (integrated by {authorLabel})',
    'copyright': f'{copyrightLabel} \nUtilizes text2num.py (c) 2008 Greg Hewgill',
    # classes of mount points (required)
    'ModelManager.LoadCustomTransforms': loadSECtransforms,
}
