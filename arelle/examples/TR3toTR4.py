'''
See COPYRIGHT.md for copyright information.
License: https://www.apache.org/licenses/LICENSE-2.0

usage: python3 {tr2 or tr3 input-file} {tr4 output-file}
'''

import io, os, sys, time
from lxml import etree

if len(sys.argv) < 3:
    print("Please enter input and output filename arguments")
    exit(1)
INFILE = sys.argv[1]
OUTFILE = sys.argv[2]

if not INFILE or not os.path.isfile(INFILE) or not OUTFILE:
    print("Please enter existing input filename and output filename")
    exit(1)

xhtmlNs = "http://www.w3.org/1999/xhtml"
ixNS = "http://www.xbrl.org/2013/inlineXBRL"
ixEltsWithFormat = ["{{{}}}{}".format(ixNS, localName) for localName in ("denominator", "numerator", "nonFraction", "nonNumeric")]
xhtmlRootElts = ["{{{}}}{}".format(xhtmlNs, localName) for localName in ("html", "xhtml")]
TR2NS = "http://www.xbrl.org/inlineXBRL/transformation/2011-07-31"
TR3NS = "http://www.xbrl.org/inlineXBRL/transformation/2015-02-26"
TR4NS = "http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"
TR23to4 = {
    "booleanfalse": "fixed-false",
    "booleantrue": "fixed-true",
    "calindaymonthyear": "date-ind-day-monthname-year-hi",
    "datedaymonth": "date-day-month",
    "datedaymonthdk": "date-day-monthname-da",
    "datedaymonthen": "date-day-monthname-en",
    "datedaymonthyear": "date-day-month-year",
    "datedaymonthyeardk": "date-day-monthname-year-da",
    "datedaymonthyearen": "date-day-monthname-year-en",
    "datedaymonthyearin": "date-day-monthname-year-hi", # does not handle this: Use date-day-month-year when using Devanagari numerals for the month, otherwise use date-day-monthname-year-hi.
    "dateerayearmonthdayjp": "date-jpn-era-year-month-day",
    "dateerayearmonthjp": "date-jpn-era-year-month",
    "datemonthday": "date-month-day",
    "datemonthdayen": "date-monthname-day-en",
    "datemonthdayyear": "date-month-day-year",
    "datemonthdayyearen": "date-monthname-day-year-en",
    "datemonthyear": "date-month-year",
    "datemonthyeardk": "date-monthname-year-da",
    "datemonthyearen": "date-monthname-year-en",
    "datemonthyearin": "date-monthname-year-hi",
    "dateyearmonthday": "date-year-month-day",
    "dateyearmonthdaycjk": "date-year-month-day",
    "dateyearmonthcjk": "date-year-month",
    "dateyearmonthen": "date-year-monthname-en",
    "nocontent": "fixed-empty",
    "numcommadecimal": "num-comma-decimal",
    "numdotdecimal": "num-dot-decimal",
    "numdotdecimalin": "num-dot-decimal",
    "numunitdecimal": "num-unit-decimal",
    "numunitdecimalin": "num-unit-decimal",
    "zerodash": "fixed-zero"
    }

print("Parsing TR3 file {}".format(INFILE))
startedAt = time.time()
parser = etree.XMLParser(recover=True, huge_tree=True)
with io.open(INFILE, "rb") as fh:
    doc = etree.parse(fh,parser=parser,base_url=INFILE)

# replace format TR3 with TR4
nsToChange = set()
for elt in doc.iter(*ixEltsWithFormat):
    prefix, _sep, localName = elt.get("format", "").rpartition(":")
    if localName:
        ns = elt.nsmap.get(prefix)
        if ns in (TR2NS, TR3NS):
            if localName in TR23to4:
                elt.set("format", "ixt:" + TR23to4[localName])
                nsToChange.add(ns)
            else:
                print("{} line {}: nable to convert transform {}".format(elt.tag, elt.sourceline, elt.get("format")))

# replace TR2 and TR3 namespaces in any xmlns'ed element
outXhtml = etree.tostring(doc, encoding=doc.docinfo.encoding, xml_declaration=True)
for ns in nsToChange:
    outXhtml = outXhtml.replace(ns.encode(), TR4NS.encode())

with io.open(OUTFILE, "wb", ) as fh:
    fh.write(outXhtml)
print("Converted in {:.3f} secs, TR4 file {}".format(time.time()-startedAt, INFILE))
