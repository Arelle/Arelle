'''
Custom transforms for SEC

Created by staff of the U.S. Securities and Exchange Commission.
Data and content created by government employees within the scope of their employment 
are not subject to domestic copyright protection. 17 U.S.C. 105.

(c) Copyright 2015 Mark V Systems Limited, All rights reserved.
'''
from arelle.ModelValue import qname
from arelle.XPathContext import FunctionArgType

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

def getValue(arg):
    try:
        n = float(arg) # could cause a ValueError exception
        if n < 0:
            return (abs(n), '-') # add a negative sign
        return (n, '') # don't add a sign
    except ValueError:
        raise FunctionArgType(1, "xs:duration")
    
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
    if m is not None:
        output += str(m) + 'M'
    if d is not None:
        output += str(d) + 'D'
    if h is not None:
        output += 'T' + str(h) + 'H'
    return output

def numinf(arg):
    return "INF"

def numneginf(arg):
    return "-INF"

def numnan(arg):
    return "NaN"

    
def loadSECtransforms(customTransforms, *args, **kwargs):
    ixtSEC = "http://www.sec.gov/inlineXBRL/transformation/2015-08-31"
    customTransforms.update({
        qname(ixtSEC, "ixt-sec:duryear"): duryear,
        qname(ixtSEC, "ixt-sec:durmonth"): durmonth,
        qname(ixtSEC, "ixt-sec:durweek"): durweek,
        qname(ixtSEC, "ixt-sec:durday"): durday,
        qname(ixtSEC, "ixt-sec:durhour"): durhour,
        qname(ixtSEC, "ixt-sec:numinf"): numinf,
        qname(ixtSEC, "ixt-sec:numneginf"): numneginf,
        qname(ixtSEC, "ixt-sec:numnan"): numnan
    })
    
__pluginInfo__ = {
    'name': 'SEC Inline Transforms',
    'version': '1.0.0.178', # SEC version
    'description': "This plug-in adds custom transforms SEC inline filing with durations.  ",
    'license': 'Apache-2',
    'author': 'SEC employees (integrated by Mark V Systems Limited)',
    'copyright': '(c) Copyright 2015 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'ModelManager.LoadCustomTransforms': loadSECtransforms,
}
