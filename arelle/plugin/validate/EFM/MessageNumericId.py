# -*- coding: utf-8 -*-
'''
Created by staff of the U.S. Securities and Exchange Commission.
Data and content created by government employees within the scope of their employment are not subject
to domestic copyright protection. 17 U.S.C. 105.

Provides an integer code for each message
'''
from regex import compile as re_compile
from arelle.ModelInstanceObject import ModelFact

ftStart   = 10000000 # fee tagging messages
efmStart  = 20000000 # EFM check messages
ixStart   = 30000000 # inline XBRL messages
xbrlStart = 40000000 # XBRL 2.1 messates
xml1Start = 51000000 # XML value
xml2Start = 52000000 # XML element issue in traditional XML (Python check)
xml3Start = 52000000 # XML element issue in inline XML (LXML schema check)
unknown   = 60000000 # no pattern match

ignoredCodes = {
    "debug", "info", None}
ftTableStartCode = (
    (1000000, "Submission / Fees Summary"),
    (2000000, "Offering"),
    (3000000, "Offset"),
    (4000000, "Combined Prospectus"),
    (5000000, "Securities, 424I"),
    (1000000, "")) # catch all
ftRuleCode = (
    (100000, "Rule 457(a)"),
    (200000, "Rule 457(o)"),
    (300000, "Rule 457(u)"),
    (400000, "Rule 457(r)"),
    # 0-11 below under 0-11(a(2)
    (600000, "Other Rule"),
    (700000, "Rule 415(a)(6)"),
    (800000, "Rule 0-11(a)(2)"),
    (500000, "Rule 0-11"), # check after preceding longer string check
    (900000, "Rule 457(p)"),
    (1000000, "Rule 429"),
    (100000, "")) # catch all
codesPatterns = (
    (efmStart,  re_compile(r"EFM\.([0-9]+(\.[0-9]+)*).*"), "."),
    (ixStart,   re_compile(r"ix11\.([0-9]+(\.[0-9]+)*).*"), "."),
    (xbrlStart, re_compile(r"xbrl\.([0-9]+(\.[0-9]+)*).*"), "."),
    (xml1Start, re_compile(r"xmlSchema.valueError"), "."),
    (xml2Start, re_compile(r"xmlSchema"), "."),
    (xml3Start, re_compile(r"lxml.SCHEMA[A-Za-z_]*([0-9]+(_[0-9]+)*).*"), "_"),
    )

def messageNumericId(modelXbrl, level, messageCode, args):
    code = 0 # unknown situation
    if messageCode in ignoredCodes:
        return None
    modelObject = args.get("modelObject")
    if isinstance(modelObject, (tuple, list)) and len(modelObject) > 0:
        modelObject = modelObject[0]
    ftContext = args.get("ftContext")
    if isinstance(modelObject, ModelFact) and ftContext and messageCode.startswith("EFM.ft."):
        for code, tbl in ftTableStartCode:
            if ftContext.startswith(tbl):
                code += ftStart
                break
        # code has the table portion in it
        for ruleCode, rule in ftRuleCode:
            if rule in ftContext:
                code += ruleCode
                break
        if code:
            return code
    try:
        for code, pattern, splitChar in codesPatterns:
            m = pattern.match(messageCode)
            if m and m.lastindex is not None and m.lastindex >= 1:
                return code + sum(int(n) * 100**i
                                  for i,n in enumerate(reversed(m.group(1).split(splitChar))))
    except ValueError as ex:
        return unknown
    return unknown
