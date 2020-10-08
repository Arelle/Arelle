'''
loadFromExcel.py is an example of a plug-in that will load an extension taxonomy from Excel
input and optionally save an (extension) DTS.

(c) Copyright 2016 Mark V Systems Limited, All rights reserved.

Example to run from web server:

1) POSTing excel in a zip, getting instance and log back in zip:

   curl -k -v -X POST "-HContent-type: application/zip" -T /Users/hermf/Documents/blahblah.xlsx.zip "localhost:8080/rest/xbrl/open?media=zip&file=WIP_DETAILED_3.xlsx&plugins=loadFromOIM&saveOIMinstance=myinstance.xbrl" -o out.zip
   
2) POSTing json within an archive of XII test cases and log and instance back in zip

   curl -k -v -X POST "-HContent-type: application/zip" -T test.zip  "localhost:8080/rest/xbrl/open?media=zip&file=100-json/helloWorld.json&plugins=loadFromOIM&saveOIMinstance=myinstance.xbrl" -o out.zip


'''
import os, sys, io, time, traceback, json, csv, logging, math, zipfile, datetime, isodate
try:
    from regex import compile as re_compile, match as re_match, DOTALL as re_DOTALL
except ImportError:
    from re import compile as re_compile, match as re_match, DOTALL as re_DOTALL
from lxml import etree
from collections import defaultdict, OrderedDict
from arelle.ModelDocument import Type, create as createModelDocument
from arelle.ModelDtsObject import ModelResource
from arelle import XbrlConst, ModelDocument, ModelXbrl, PackageManager, ValidateXbrlDimensions
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname, dateTime, DATETIME, yearMonthDuration, dayTimeDuration
from arelle.PrototypeInstanceObject import DimValuePrototype
from arelle.PythonUtil import attrdict
from arelle.UrlUtil import isHttpUrl, isAbsolute as isAbsoluteUri, relativeUrlPattern
from arelle.XbrlConst import (qnLinkLabel, standardLabelRoles, qnLinkReference, standardReferenceRoles,
                              qnLinkPart, gen, link, defaultLinkRole, footnote, factFootnote, isStandardRole,
                              conceptLabel, elementLabel, conceptReference, all as hc_all, notAll as hc_notAll,
                              xhtml)
from arelle.XmlUtil import addChild, addQnameValue, copyIxFootnoteHtml, setXmlns
from arelle.XmlValidate import integerPattern, languagePattern, NCNamePattern, QNamePattern, validate as xmlValidate, VALID
from arelle.ValidateXbrlCalcs import inferredDecimals, rangeValue

nsOims = ("http://www.xbrl.org/WGWD/YYYY-MM-DD",
          "http://www.xbrl.org/CR/2020-05-06",
          "http://www.xbrl.org/((~status_date_uri~))"
         )
nsOimCes = ("http://www.xbrl.org/WGWD/YYYY-MM-DD/oim-common/error",
            "http://www.xbrl.org/CR/2020-05-06/oim-common/error",
            "http://www.xbrl.org/((~status_date_uri~))/oim-common/error"
    )
jsonDocumentTypes = (
        "http://www.xbrl.org/WGWD/YYYY-MM-DD/xbrl-json",
        "http://www.xbrl.org/YYYY-MM-DD/xbrl-json",
        "http://www.xbrl.org/((~status_date_uri~))/xbrl-json", # allows loading of XII "template" test cases without CI production
        "http://www.xbrl.org/CR/2020-05-06/xbrl-json",
    )
csvDocumentTypes = (
        "http://www.xbrl.org/WGWD/YYYY-MM-DD/xbrl-csv",
        "http://xbrl.org/YYYY/xbrl-csv",
        "http://www.xbrl.org/((~status_date_uri~))/xbrl-csv", # allows loading of XII "template" test cases without CI production
        "http://www.xbrl.org/CR/2019-10-19/xbrl-csv"
    )
csvDocinfoObjects = {"documentType", "reportDimensions", "namespaces", "taxonomy", "decimals", "extends", "final"}
csvExtensibleObjects = {"namespaces", "linkTypes", "linkGroups", "tableTemplates", "tables", "reportDimensions", "final"}

         
reservedLinkTypes = {
        "footnote":         "http://www.xbrl.org/2003/arcrole/fact-footnote",
        "explanatoryFact":  "http://www.xbrl.org/2009/arcrole/fact-explanatoryFact"
    }
reservedLinkTypeAliases = {
        "http://www.xbrl.org/2003/arcrole/fact-footnote": "footnote",
        "http://www.xbrl.org/2009/arcrole/fact-explanatoryFact": "explanatoryFact"
    }
reservedLinkGroups = {
        "_":     "http://www.xbrl.org/2003/role/link"
    }
reservedLinkGroupAliases = {
        "http://www.xbrl.org/2003/role/link": "_"
    }


XLINKTYPE = "{http://www.w3.org/1999/xlink}type"
XLINKLABEL = "{http://www.w3.org/1999/xlink}label"
XLINKARCROLE = "{http://www.w3.org/1999/xlink}arcrole"
XLINKFROM = "{http://www.w3.org/1999/xlink}from"
XLINKTO = "{http://www.w3.org/1999/xlink}to"
XLINKHREF = "{http://www.w3.org/1999/xlink}href"
XMLLANG = "{http://www.w3.org/XML/1998/namespace}lang"

JSONdocumentType = "http://www.xbrl.org/WGWD/YYYY-MM-DD/xbrl-json"

NSReservedAliasURIs = {
    "xbrl": nsOims,
    "xs": (XbrlConst.xsd,),
    "enum2": XbrlConst.enum2s,
    "oimce": nsOimCes,
    "xbrli": (XbrlConst.xbrli,),
    "xs": (XbrlConst.xsd,),
    "utr": (XbrlConst.utr,),
    "iso4217": (XbrlConst.iso4217,),
    #"xbrle":  [ns + "/error" for ns in nsOims],
    #"xbrlxe": [ns + "/xbrl-xml/error" for ns in nsOims]
    }
JSONNSReservedAliasURIs = {
    "xbrlje": [ns + "/xbrl-json/error" for ns in nsOims],
    }
CSVNSReservedAliasURIs = {
    "xbrlce": [ns + "/xbrl-csv/error" for ns in nsOims],
    }
NSReservedAliasURIPrefixes = { # for starts-with checking
    # "dtr-type": "http://www.xbrl.org/dtr/type/", 
    }
NSReservedURIAlias = {}

OIMReservedAliasURIs = {
    "namespaces": NSReservedAliasURIs,
    "linkTypes": reservedLinkTypes,
    "linkGroups": reservedLinkGroups
    }
OIMReservedURIAlias = {
    "namespaces": NSReservedURIAlias,
    "linkTypes": reservedLinkTypeAliases,
    "linkGroups": reservedLinkGroupAliases
    }

ENTITY_NA_QNAME = qname("https://xbrl.org/entities", "NA")
EMPTY_DICT = {}
EMPTY_LIST = []

DUPJSONKEY = "!@%duplicateKeys%@!"
DUPJSONVALUE = "!@%duplicateValues%@!"
    
UTF_7_16_Pattern = re_compile(r"(?P<utf16>(^([\x00][^\x00])+$)|(^([^\x00][\x00])+$))|(?P<utf7>^\s*\+AHs-)")
JSONmetadataPattern = re_compile(r"\s*\{.*\"documentInfo\"\s*:.*\}", re_DOTALL)
NoCanonicalPattern = attrdict(match=lambda s: True)
CanonicalFloatPattern = re_compile(r"^-?[0-9]\.[0-9]([0-9]*[1-9])?E-?([1-9][0-9]*|0)$|^-?INF$|^NaN$")
CanonicalIntegerPattern = re_compile(r"^-?([1-9][0-9]*)?[0-9]$")
CanonicalXmlTypePattern = {
    "boolean": re_compile("^true$|^false$"),
    "date": re_compile(r"-?[0-9]{4}-[0-9]{2}-[0-9]{2}Z?$"),
    "dateTime": re_compile(r"-?[0-9]{4}-[0-9]{2}-[0-9]{2}T([01][0-9]|20|21|22|23):[0-9]{2}:[0-9]{2}(\.[0-9]([0-9]*[1-9])?)?Z?$"),
    "time": re_compile(r"-?([01][0-9]|20|21|22|23):[0-9]{2}:[0-9]{2}(\.[0-9]([0-9]*[1-9])?)?Z?$"),
    "decimal": re_compile(r"^[-]?([1-9][0-9]*)?[0-9]\.[0-9]([0-9]*[1-9])?$"),
    "float": CanonicalFloatPattern,
    "double": CanonicalFloatPattern,
    "hexBinary": re_compile(r"^([0-9A-F][0-9A-F])*$"),
    "integer": CanonicalIntegerPattern,
    "nonPositiveInteger": CanonicalIntegerPattern,
    "negativeInteger": CanonicalIntegerPattern,
    "long": CanonicalIntegerPattern,
    "int": CanonicalIntegerPattern,
    "short": CanonicalIntegerPattern,
    "byte": CanonicalIntegerPattern,
    "nonNegativeInteger": CanonicalIntegerPattern,
    "unsignedLong": CanonicalIntegerPattern,
    "unsignedInt": CanonicalIntegerPattern,
    "unsignedShort": CanonicalIntegerPattern,
    "unsignedByte": CanonicalIntegerPattern,
    "positiveInteger": CanonicalIntegerPattern,
    }
IdentifierPattern = re_compile(
    "^[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
     r"[_\-" 
     "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*$")
PeriodPattern = re_compile(
    "^-?[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})?"
    "(/-?[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})?)?$"
    )
PrefixedQName = re_compile(
    "[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
     r"[_\-\." 
     "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*:"
    "[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
     r"[_\-\." 
     "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*")
SQNamePattern = re_compile(
    "[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
     r"[_\-\." 
     "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*:"
    r"\S+")
UnitPrefixedQNameSubstitutionChar = "\x07" # replaces PrefixedQName in unit pattern
UnitPattern = re_compile(
    # QNames are replaced by \x07 in these expressions
    # numerator only (no parentheses)
    "(^\x07$)|(^\x07([*]\x07)+$)|"
    # numerator and optional denominator, with parentheses if more than one term in either
    "(^((\x07)|([(]\x07([*]\x07)+[)]))([/]((\x07)|([(]\x07([*]\x07)+[)])))?$)"
    )
UrlInvalidPattern = re_compile(
    r"^[ \t\n\r]+[^ \t\n\r]*|.*[^ \t\n\r][ \t\n\r]+$|" # leading or trailing whitespace
    r".*[^ \t\n\r]([\t\n\r]+|[ \t\n\r]{2,})[^ \t\n\r]|" # embedded uncollapsed whitespace
    r".*%[^0-9a-fA-F]|.*%[0-9a-fA-F][^0-9a-fA-F]|.*#.*#" # invalid %nn or two ##s
    )
WhitespacePattern = re_compile(r"[ \t\n\r]")
WhitespaceUntrimmedPattern = re_compile(r"^[ \t\n\r]|.*[ \t\n\r]$")

xlUnicodePattern = re_compile("_x([0-9A-F]{4})_")

precisionZeroPattern = re_compile(r"^\s*0+\s*$")
decimalsSuffixPattern = re_compile(r"(0|-?[1-9][0-9]*|INF)$")

htmlBodyTemplate = "<body xmlns='http://www.w3.org/1999/xhtml'>\n{0}\n</body>\n"
xhtmlTagPrefix = "{http://www.w3.org/1999/xhtml}"

# allowed duplicates settings
NONE = 1
COMPLETE = 2
CONSISTENT = 3
ALL = 4
AllowedDuplicatesFeatureValues = {"none": NONE, "complete": COMPLETE, "consistent": CONSISTENT, "all": ALL}
DisallowedDescription = {NONE: "Disallowed", COMPLETE: "Inequivalent", CONSISTENT: "Inconsistent", ALL: "Allowed"}

class SQNameType:
    pass # fake class for detecting SQName type in JSON structure check

class QNameType:
    pass # fake class for detecting QName type in JSON structure check

class LangType:
    pass

class URIType:
    pass

class NoRecursionCheck:
    pass

UnrecognizedDocMemberTypes = {
    "/documentInfo": dict,
    "/documentInfo/documentType": str,
    }
UnrecognizedDocRequiredMembers = {
    "/": {"documentInfo"},
    "/documentInfo/": {"documentType","taxonomy"},
    }

JsonMemberTypes = {
    # keys are json pointer with * meaning any id,  and *:* meaning any SQName or QName, for array no index is used
    # report
    "/documentInfo": dict,
    "/facts": dict,
    "/*:*": (int,bool,str,dict,list,type(None),NoRecursionCheck), # custom extensions
    # documentInfo
    "/documentInfo/baseURL": URIType,
    "/documentInfo/documentType": str,
    "/documentInfo/features": dict,
    "/documentInfo/features/*:*": (int,bool,str,type(None)),
    "/documentInfo/namespaces": dict,
    "/documentInfo/namespaces/*": URIType,
    "/documentInfo/linkTypes": dict,
    "/documentInfo/linkTypes/*": str,
    "/documentInfo/linkGroups": dict,
    "/documentInfo/linkGroups/*": str,
    "/documentInfo/taxonomy": list,
    "/documentInfo/taxonomy/": str,
    "/documentInfo/*:*": (int,bool,str,dict,list,type(None),NoRecursionCheck), # custom extensions
    # facts
    "/facts/*": dict,
    "/facts/*/value": (str,type(None)),
    "/facts/*/decimals": int,
    "/facts/*/dimensions": dict,
    "/facts/*/links": dict,
    "/facts/*/links/*": dict,
    "/facts/*/links/*/*": list,
    "/facts/*/links/*/*/": str,
    # dimensions
    "/facts/*/dimensions/concept": QNameType,
    "/facts/*/dimensions/entity": SQNameType,
    "/facts/*/dimensions/period": str,
    "/facts/*/dimensions/unit": str,
    "/facts/*/dimensions/language": LangType,
    "/facts/*/dimensions/noteId": str,
    "/facts/*/dimensions/*:*": (str,type(None)),
    # custom properties on fact are unchecked
    "/facts/*/*:*": (int,bool,str,dict,list,type(None),NoRecursionCheck), # custom extensions
    }
JsonRequiredMembers = {
    "/": {"documentInfo"},
    "/documentInfo/": {"documentType","taxonomy"},
    "/facts/*/": {"value","dimensions"},
    "/facts/*/dimensions/": {"concept"}
    }

CsvMemberTypes = {
    # report
    "/documentInfo": dict,
    "/tableTemplates": dict,
    "/tables": dict,
    "/parameters": dict,
    "/parameters/*": (str,int),
    "/parameterURL": str,
    "/dimensions": dict,
    "/decimals": (int,str),
    "/links": dict,
    # documentInfo
    "/documentInfo/documentType": str,
    "/documentInfo/namespaces": dict,
    "/documentInfo/namespaces/*": str,
    "/documentInfo/linkTypes": dict,
    "/documentInfo/linkTypes/*": str,
    "/documentInfo/linkGroups": dict,
    "/documentInfo/linkGroups/*": str,
    "/documentInfo/taxonomy": list,
    "/documentInfo/taxonomy/": str,
    "/documentInfo/extends": list,
    "/documentInfo/extends/": str,
    "/documentInfo/final": dict,
    "/documentInfo/features": dict,
    "/documentInfo/features/*": (int,bool,str,type(None)),
    # documentInfo/final
    "/documentInfo/final/namespaces": bool,
    "/documentInfo/final/taxonomy": bool,
    "/documentInfo/final/linkTypes": bool,
    "/documentInfo/final/linkGroups": bool,
    "/documentInfo/final/features": bool,
    "/documentInfo/final/tableTemplates": bool,
    "/documentInfo/final/tables": bool,
    "/documentInfo/final/dimensions": bool,
    "/documentInfo/final/parameters": bool,
    # table templates
    "/tableTemplates/*": dict,
    "/tableTemplates/*/rowIdColumn": str,
    "/tableTemplates/*/columns": dict,
    "/tableTemplates/*/decimals": (int,str),
    "/tableTemplates/*/dimensions": dict,
    "/tableTemplates/*/dimensions/concept": str,
    "/tableTemplates/*/dimensions/entity": str,
    "/tableTemplates/*/dimensions/period": str,
    "/tableTemplates/*/dimensions/unit": str,
    "/tableTemplates/*/dimensions/language": str,
    "/tableTemplates/*/dimensions/noteId": str,
    "/tableTemplates/*/dimensions/*:*": str,
    "/tableTemplates/*/dimensions/$*": str,
    #"/tableTemplates/*/transposed": bool,
    # columns
    "/tableTemplates/*/columns/*": dict,
    "/tableTemplates/*/columns/*/decimals": (int,str),
    "/tableTemplates/*/columns/*/default": str,
    "/tableTemplates/*/columns/*/dimensions": dict,
    # dimensions (column)
    "/tableTemplates/*/columns/*/dimensions/concept": str,
    "/tableTemplates/*/columns/*/dimensions/entity": str,
    "/tableTemplates/*/columns/*/dimensions/period": str,
    "/tableTemplates/*/columns/*/dimensions/unit": str,
    "/tableTemplates/*/columns/*/dimensions/language": str,
    "/tableTemplates/*/columns/*/dimensions/noteId": str,
    "/tableTemplates/*/columns/*/dimensions/*:*": str,
    "/tableTemplates/*/columns/*/dimensions/$*": str,
    # property groups (column)
    "/tableTemplates/*/columns/*/propertiesFrom": str,
    "/tableTemplates/*/columns/*/propertyGroups": dict,
    "/tableTemplates/*/columns/*/propertyGroups/*": dict,
    "/tableTemplates/*/columns/*/propertyGroups/*/decimals": (int,str),
    "/tableTemplates/*/columns/*/propertyGroups/*/dimensions": dict,
    "/tableTemplates/*/columns/*/propertyGroups/*/dimensions/concept": str,
    "/tableTemplates/*/columns/*/propertyGroups/*/dimensions/entity": str,
    "/tableTemplates/*/columns/*/propertyGroups/*/dimensions/period": str,
    "/tableTemplates/*/columns/*/propertyGroups/*/dimensions/unit": str,
    "/tableTemplates/*/columns/*/propertyGroups/*/dimensions/language": str,
    "/tableTemplates/*/columns/*/propertyGroups/*/dimensions/noteId": str,
    "/tableTemplates/*/columns/*/propertyGroups/*/dimensions/*:*": str,
    "/tableTemplates/*/columns/*/propertyGroups/*/dimensions/$*": str,
    # dimensions (top level)
    "/dimensions/concept": str,
    "/dimensions/entity": str,
    "/dimensions/period": str,
    "/dimensions/unit": str,
    "/dimensions/language": str,
    "/dimensions/noteId": str,
    "/dimensions/*:*": str,
    "/dimensions/$*": str,
    # tables
    "/tables/*": dict,
    "/tables/*/url": str,
    "/tables/*/template": str,
    "/tables/*/optional": bool,
    "/tables/*/parameters": dict,
    "/tables/*/parameters/*": (str, int),
    # links
    "/links/*": dict,
    # link group
    "/links/*/*": dict,
    # fact links
    "/links/*/*/*": list,
    # fact IDs
    "/links/*/*/*/*": str,
    }
CsvRequiredMembers = {
    "/": {"documentInfo"},
    "/documentInfo/": {"documentType"},
    "/tableTemplates/*/": {"columns"},
    "/tables/*/": {"url"}
    }
EMPTY_SET = set()

def jsonGet(tbl, key, default=None):
    if isinstance(tbl, dict):
        return tbl.get(key, default)
    return default

def csvCellValue(cellValue):
    if cellValue == "#nil":
        return None
    elif cellValue == "#empty":
        return ""
    elif isinstance(cellValue, str) and cellValue.startswith("##"):
        return cellValue[1:]
    else:
        return cellValue

def xlUnicodeChar(match):
    return chr(int(match.group(1), 16))
    
def xlValue(cell): # excel values may have encoded unicode, such as _0000D_
    v = cell.value
    if isinstance(v, str):
        v = xlUnicodePattern.sub(xlUnicodeChar, v).replace('\r\n','\n').replace('\r','\n')
    elif v is None:
        v = ""
    else:
        v = str(v)
    return csvCellValue(v)

def xlTrimHeaderRow(row):
    numEmptyCellsAtEndOfRow = 0
    for i in range(len(row)-1, -1, -1):
        if row[i] in (None, ""):
            numEmptyCellsAtEndOfRow += 1
        else:
            break
    if numEmptyCellsAtEndOfRow:
        return row[:-numEmptyCellsAtEndOfRow]
    return row

class OIMException(Exception):
    def __init__(self, code=None, message=None, **kwargs):
        self.code = code
        self.message = message
        self.msgArgs = kwargs
        self.args = ( self.__repr__(), )
    def __repr__(self):
        if self.code and self.message:
            return _('[{0}] exception {1}').format(self.code, self.message % self.msgArgs)
        else:
            return "Errors noted in log"

class NotOIMException(Exception):
    def __init__(self, **kwargs):
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[NotOIM] not an OIM document')

PER_ISO = 0
PER_INCLUSIVE_DATES = 1
PER_SINGLE_DAY = 2
PER_MONTH = 3
PER_YEAR = 4
PER_QTR = 5
PER_HALF = 6
PER_WEEK = 7
ONE_DAY = dayTimeDuration("P1D")
ONE_MONTH = yearMonthDuration("P1M")
ONE_YEAR = yearMonthDuration("P1Y")
ONE_QTR = yearMonthDuration("P3M")
ONE_HALF = yearMonthDuration("P6M")
    
periodForms = ((PER_ISO, re_compile("([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(Z|[+-][0-2][0-9]([:]?)[0-5][0-9]+)?(/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})?(Z|[+-][0-2][0-9]([:]?)[0-5][0-9]+)?)$")),
               (PER_INCLUSIVE_DATES, re_compile("([0-9]{4}-[0-9]{2}-[0-9]{2})[.][.]([0-9]{4}-[0-9]{2}-[0-9]{2})$")),
               (PER_SINGLE_DAY, re_compile("([0-9]{4}-[0-9]{2}-[0-9]{2})(@(start|end))?$")),
               (PER_MONTH,  re_compile("([0-9]{4}-[0-9]{2})(@(start|end))?$")),
               (PER_YEAR, re_compile("([0-9]{4})(@(start|end))?$")),
               (PER_QTR, re_compile("([0-9]{4})Q([1-4])(@(start|end))?$")),
               (PER_HALF, re_compile("([0-9]{4})H([1-2])(@(start|end))?$")),
               (PER_WEEK, re_compile("([0-9]{4}W[1-5]?[0-9])(@(start|end))?$")))

    
def csvPeriod(cellValue, startOrEnd):
    if cellValue in ("", "#none"):
        return None
    isoDuration = None
    for perType, perFormMatch in periodForms:
        m = perFormMatch.match(cellValue)
        if m:
            try:
                if perType == PER_ISO:
                    if not m.group(4) and startOrEnd: # instant date
                        return "referenceTargetNotDuration"
                    isoDuration = cellValue
                    startendSuffixGroup = 0
                elif perType == PER_INCLUSIVE_DATES:
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(dateTime(m.group(1)), dateTime(m.group(2)) + ONE_DAY)
                    startendSuffixGroup = 0
                elif perType == PER_SINGLE_DAY:
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(dateTime(m.group(1)), dateTime(m.group(1)) + ONE_DAY)
                    startendSuffixGroup = 3
                elif perType == PER_MONTH:
                    moStart = dateTime(m.group(1) + "-01")
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(moStart, moStart + ONE_MONTH)
                    startendSuffixGroup = 3
                elif perType == PER_YEAR:
                    yrStart = dateTime(m.group(1) + "-01-01")
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(yrStart, yrStart + ONE_YEAR)
                    startendSuffixGroup = 3
                elif perType == PER_QTR:
                    qtrStart = dateTime(m.group(1) + "-{:02}-01".format(int(m.group(2))*3 - 2))
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(qtrStart, qtrStart + ONE_QTR)
                    startendSuffixGroup = 4
                elif perType == PER_HALF:
                    qtrStart = dateTime(m.group(1) + "-{:02}-01".format(int(m.group(2))*6 - 5))
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(qtrStart, qtrStart + ONE_HALF)
                    startendSuffixGroup = 4
                elif perType == PER_WEEK:
                    weekStart = dateTime(isodate.parse_date(m.group(1)))
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(weekStart, weekStart + datetime.timedelta(7))
                    startendSuffixGroup = 3
                if startendSuffixGroup and m.group(startendSuffixGroup):
                    if startOrEnd:
                        # period specifier is being applied to an instant date
                        return "referenceTargetNotDuration"
                    startOrEnd = m.group(startendSuffixGroup)
            except ValueError:
                return None
        if isoDuration:
            if startOrEnd == "start":
                return isoDuration.partition("/")[0]
            elif startOrEnd == "end":
                return isoDuration.partition("/")[2]
            return isoDuration
    return None

# no longer used because transpose is not supported
def transposer(rowIterator, default=""):
    cells = [row for row in rowIterator]
    if cells:
        colsCount = max(len(row) for row in cells)
        rowsCount = len(cells)
        for colIndex in range(colsCount):
            yield [(cells[rowIndex][colIndex] if colIndex < len(cells[colIndex]) else default) 
                   for rowIndex in range(rowsCount)]
            
def idDeduped(modelXbrl, id):
    for i in range(99999):
        if i == 0:
            candidateId = id
        else:
            candidateId = "{}.{}".format(id, i)
        if candidateId not in modelXbrl.modelDocument.idObjects:
            return candidateId
    return None
            
def oimEquivalentFacts(f1, f2):
        if f1.context is None or f1.concept is None:
            return False # need valid context and concept for v-Equality of nonTuple
        if f1.isNil:
            return f2.isNil
        if f2.isNil:
            return False
        if not f1.context.isEqualTo(f2.context):
            return False
        elif type(f1.xValue) == type(f2.xValue):
            return f1.xValue == f2.xValue # required to handle date/time with 24 hrs.
        return f1.value == f2.value
    
def checkForDuplicates(modelXbrl, allowedDups, footnoteIDs):
    # intended to be use after loading OIM or possibly in future for xBRL-XML
    if allowedDups != ALL:
        factForConceptContextUnitHash = defaultdict(list)
        for f in modelXbrl.factsInInstance:
            if (f.isNil or getattr(f,"xValid", 0) >= 4) and f.context is not None and f.concept is not None and f.concept.type is not None:
                factForConceptContextUnitHash[f.conceptContextUnitHash].append(f)
        aspectEqualFacts = defaultdict(dict) # dict [(qname,lang)] of dict(cntx,unit) of [fact, fact] 
        for hashEquivalentFacts in factForConceptContextUnitHash.values():
            if len(hashEquivalentFacts) > 1:
                for f in hashEquivalentFacts: # check for hash collision by value checks on context and unit
                    cuDict = aspectEqualFacts[(f.qname,
                                               (f.xmlLang or "").lower() if f.concept.type.isWgnStringFactType else None)]
                    _matched = False
                    for (_cntx,_unit),fList in cuDict.items():
                        if (((_cntx is None and f.context is None) or (f.context is not None and f.context.isEqualTo(_cntx))) and
                            ((_unit is None and f.unit is None) or (f.unit is not None and f.unit.isEqualTo(_unit)))):
                            _matched = True
                            fList.append(f)
                            break
                    if not _matched:
                        cuDict[(f.context,f.unit)] = [f]
                for cuDict in aspectEqualFacts.values(): # dups by qname, lang
                    for fList in cuDict.values():  # dups by equal-context equal-unit
                        if len(fList) > 1:
                            f0 = fList[0]
                            if allowedDups == NONE:
                                _inConsistent = True
                            elif allowedDups == CONSISTENT and f0.concept.isNumeric:
                                if any(f.isNil for f in fList):
                                    _inConsistent = not all(f.isNil for f in fList)
                                elif all(inferredDecimals(f) == inferredDecimals(f0) for f in fList[1:]): # same decimals
                                    v0 = rangeValue(f0.value)
                                    _inConsistent = not all(rangeValue(f.value) == v0 for f in fList[1:])
                                else: # not all have same decimals
                                    aMax, bMin = rangeValue(f0.value, inferredDecimals(f0))
                                    for f in fList[1:]:
                                        a, b = rangeValue(f.value, inferredDecimals(f))
                                        if a > aMax: aMax = a
                                        if b < bMin: bMin = b
                                    _inConsistent = (bMin < aMax)
                            else: # includes COMPLETE
                                _inConsistent = any(not oimEquivalentFacts(f0, f) for f in fList[1:])
                            if _inConsistent:
                                modelXbrl.error("oime:disallowedDuplicateFacts",
                                    "%(disallowance)s duplicate fact values %(element)s: %(values)s, %(contextIDs)s.",
                                    modelObject=fList, disallowance=DisallowedDescription[allowedDups], element=f0.qname, 
                                    contextIDs=", ".join(sorted(set(f.contextID for f in fList))), 
                                    values=", ".join(f.value for f in fList))
                aspectEqualFacts.clear()
        del factForConceptContextUnitHash, aspectEqualFacts
        
        ''' impossible to have dup footnotes (?)
        aspectEqualFootnotes = defaultdict(list) # dict [lang] of footnotes
        for footnoteID in  footnoteIDs:
            f = modelXbrl.modelDocument.idObjects[footnoteID]
            aspectEqualFootnotes[f.xmlLang.lower()].append(f)
        for lang, footnotes in aspectEqualFootnotes.items():
            fByValue = sorted(footnotes, key=lambda f: f.viewText())
            lenF = len(fByValue)
            for i, f in enumerate(fByValue):
                if i == 0:
                    fText = f.viewText()
                else:
                    fText = fNext
                if i < lenF - 1:
                    f2 = fByValue[i+1]
                    fNext = f2.viewText()
                    if fText == fNext:
                        modelXbrl.error("oime:disallowedDuplicateFacts",
                            "%(disallowance)s duplicate footnote ids %(IDs)s: value: %(value)s.",
                            modelObject=(f, f2), disallowance=DisallowedDescription[allowedDups], 
                            IDs="{}, {}".format(f.id, f2.id),
                            value=fText[:64])
        del aspectEqualFootnotes
        '''
        
def loadFromOIM(cntlr, error, warning, modelXbrl, oimFile, mappedUri):
    from openpyxl import load_workbook
    from openpyxl.cell import Cell
    from arelle import ModelDocument, ModelXbrl, XmlUtil
    from arelle.ModelDocument import ModelDocumentReference
    from arelle.ModelValue import qname
    
    _return = None # modelDocument or an exception
    
    try:
        currentAction = "initializing"
        startingErrorCount = len(modelXbrl.errors) if modelXbrl else 0
        startedAt = time.time()
        
        currentAction = "determining file type"
        isJSON = False
        # isCSV means metadata loaded from separate JSON file (but instance data can be in excel or CSV)
        isCSV = False # oimFile.endswith(".csv") # this option is not currently supported
        instanceFileName = os.path.splitext(oimFile)[0] + ".xbrl"
        
        currentAction = "loading and parsing OIM file"
        loadDictErrors = []
        def openCsvReader(csvFilePath, hasHeaderRow=True):
            _file, = modelXbrl.fileSource.file(csvFilePath, encoding='utf-8-sig')
            chars = _file.read(16) # test encoding
            m = UTF_7_16_Pattern.match(chars)
            if m:
                raise OIMException("xbrlce:invalidJSON",
                      _("CSV file MUST use utf-8 encoding: %(file)s, appears to be %(encoding)s"),
                      file=csvFilePath, encoding=m.lastgroup)
            _file.seek(0)
            if hasHeaderRow:
                try:
                    chars = _file.read(1024)
                    _dialect = csv.Sniffer().sniff(chars, delimiters=[',', '\t', ';', '|']) # also check for disallowed potential separators
                    if _dialect.lineterminator not in ("\r", "\n", "\r\n"):
                        raise OIMException("xbrlce:invalidCSVFileFormat",
                                           _("CSV line ending is not CR, LF or CR LF, file %(file)s"),
                                          file=csvFilePath)
                    if _dialect.delimiter not in (",\t"):
                        raise OIMException("xbrlce:invalidCSVFileFormat",
                                           _("CSV deliminator \"%(deliminator)s\" is not comma or TAB, file %(file)s"),
                                          file=csvFilePath, deliminator=_dialect.delimiter)
                except csv.Error as ex:
                    # possibly can't br sniffed because there's only one column in the rows
                    _dialect = None
                    for char in chars:
                        if char in  (",", "\n", "\r"):
                            _dialect = "excel"
                            break
                        elif char == "\t":
                            _dialect = "excel-tab"
                            break
                    if not _dialect:
                        raise OIMException("xbrlce:invalidCSVFileFormat",
                                           _("CSV file %(file)s: %(error)s"),
                                          file=csvFilePath, error=str(ex))
                _file.seek(0)
            else:
                # check for comma or tab in first line
                _dialect = "excel" # fallback if no first line tab is determinable
                for char in _file.read(1024):
                    if char in (",", "\n", "\r", ";", "|"): # ;, | force invalid parameter file detection
                        _dialect = "excel"
                        break
                    elif char == "\t": # only way to sniff first row deliminator if value contains SQName semicolon
                        _dialect = "excel-tab"
                        break
                _file.seek(0)
            return csv.reader(_file, _dialect)
            
        def ldError(msgCode, msgText, **kwargs):
            loadDictErrors.append((msgCode, msgText, kwargs))
        def loadDict(keyValuePairs):
            _dict = OrderedDict() # preserve fact order in resulting instance
            _valueKeyDict = {}
            for key, value in keyValuePairs:
                if isinstance(value, dict):
                    if key in ("namespaces", "linkTypes", "linkGroups"):
                        normalizedDict = OrderedDict()
                        normalizedValueKeyDict = {}
                        if DUPJSONKEY in value:
                            normalizedDict[DUPJSONKEY] = value[DUPJSONKEY]
                        if DUPJSONVALUE in value:
                            normalizedDict[DUPJSONVALUE] = value[DUPJSONVALUE]
                        for _key, _value in value.items():
                            if not isinstance(_value, str):
                                continue # skip dup key/value entries
                            # _key = _key.strip() # per !178 keys have only normalized values, don't normalize key
                            # _value = _value.strip()
                            if _key in normalizedDict: # don't put the duplicate in the dictionary but report it as error
                                if DUPJSONKEY not in normalizedDict:
                                    normalizedDict[DUPJSONKEY] = []
                                normalizedDict[DUPJSONKEY].append((_key, _value, normalizedDict[_key]))
                            else: # do put into dictionary, only report if it's a map object
                                normalizedDict[_key] = _value
                                if _value in normalizedValueKeyDict:
                                    if DUPJSONVALUE not in normalizedDict:
                                        normalizedDict[DUPJSONVALUE] = []
                                    normalizedDict[DUPJSONVALUE].append((_value, _key, normalizedValueKeyDict[_value]))
                                else:
                                    normalizedValueKeyDict[_value] = _key
                            if not NCNamePattern.match(_key):
                                ldError("{}:invalidJSONStructure",
                                      _("The %(map)s alias \"%(alias)s\" must be a canonical NCName value"),
                                      modelObject=modelXbrl, map=key, alias=_key)
                            if UrlInvalidPattern.match(_value):
                                ldError("{}:invalidJSONStructure",
                                      _("The %(map)s alias \"%(alias)s\" URI must be a canonical URI value: \"%(URI)s\"."),
                                      modelObject=modelXbrl, map=key, alias=_key, URI=_value)
                            elif not (_value and isAbsoluteUri(_value)) or UrlInvalidPattern.match(_value):
                                ldError("oimce:invalidURI",
                                        _("The %(map)s \"%(alias)s\" URI is invalid: \"%(URI)s\"."),
                                        modelObject=modelXbrl, map=key, alias=_key, URI=_value)
                        value.clear() # replace with normalized values
                        for _key, _value in normalizedDict.items():
                            value[_key] = _value
                    if DUPJSONKEY in value:
                        for _errKey, _errValue, _otherValue in value[DUPJSONKEY]:
                            if key in ("namespaces", "linkTypes", "linkGroups"):
                                ldError("{}:invalidJSON", # {} expanded when loadDictErrors are processed
                                                _("The %(map)s alias \"%(prefix)s\" is used on uri \"%(uri1)s\" and uri \"\"%(uri2)s."),
                                                modelObject=modelXbrl, map=key, prefix=_errKey, uri1=_errValue, uri2=_otherValue)
                            else:
                                ldError("{}:invalidJSON", # {} expanded when loadDictErrors are processed
                                                _("The %(obj)s key \"%(key)s\" is used on multiple objects."),
                                                modelObject=modelXbrl, obj=key, key=_errKey)
                        del value[DUPJSONKEY]
                    if DUPJSONVALUE in value:
                        if key in ("namespaces", "linkTypes", "linkGroups"):
                            for _errValue, _errKey, _otherKey in value[DUPJSONVALUE]:
                                ldError("oimce:multipleAliasesForURI",
                                                _("The \"%(map)s\" value \"%(uri)s\" is used on alias \"%(alias1)s\" and alias \"%(alias2)s\"."),
                                                modelObject=modelXbrl, map=key, uri=_errValue, alias1=_errKey, alias2=_otherKey)
                        del value[DUPJSONVALUE]
                if key in _dict: # don't put the duplicate in the dictionary but report it as error
                    if DUPJSONKEY not in _dict:
                        _dict[DUPJSONKEY] = []
                    _dict[DUPJSONKEY].append((key, value, _dict[key]))
                else: # do put into dictionary, only report if it's a map object
                    _dict[key] = value
                    if isinstance(value, str):
                        if value in _valueKeyDict:
                            if DUPJSONVALUE not in _dict:
                                _dict[DUPJSONVALUE] = []
                            _dict[DUPJSONVALUE].append((value, key, _valueKeyDict[value]))
                        else:
                            _valueKeyDict[value] = key
            return _dict
        
        primaryOimFile = oimFile
        
        def loadOimObject(oimFile, extendingFile, primaryReportParameters=None): # returns oimObject, oimWb
            # isXL means metadata loaded from Excel (but instance data can be in excel or CSV)
            isXL = oimFile.endswith(".xlsx") or oimFile.endswith(".xls")
            # same logic as modelDocument.load
            normalizedUrl = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(oimFile, extendingFile)
            if modelXbrl.fileSource.isMappedUrl(normalizedUrl):
                mappedUrl = modelXbrl.fileSource.mappedUrl(normalizedUrl)
            elif PackageManager.isMappedUrl(normalizedUrl):
                mappedUrl = PackageManager.mappedUrl(normalizedUrl)
            else:
                mappedUrl = modelXbrl.modelManager.disclosureSystem.mappedUrl(normalizedUrl)
            if modelXbrl.fileSource.isInArchive(mappedUrl):
                filepath = mappedUrl
            else:
                filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(mappedUrl) # , reload=reloadCache, checkModifiedTime=kwargs.get("checkModifiedTime",False))
                if filepath:
                    url = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(filepath)
            if filepath.endswith(".csv") or ("metadata" in filepath and filepath.endswith(".json")):
                errPrefix = "xbrlce"
            else:
                errPrefix = "xbrlje"
            if not isXL:
                try:
                    _file, = modelXbrl.fileSource.file(filepath, encoding="utf-8-sig")
                    with _file as f:
                        chars = f.read(16) # test encoding
                        m = UTF_7_16_Pattern.match(chars)
                        if m:
                            raise OIMException("{}:invalidJSON".format(errPrefix),
                                  _("File MUST use utf-8 encoding: %(file)s, appears to be %(encoding)s"),
                                  file=filepath, encoding=m.lastgroup)
                        else:
                            f.seek(0)
                            oimObject = json.load(f, object_pairs_hook=loadDict)
                except UnicodeDecodeError as ex:
                    raise OIMException("{}:invalidJSON".format(errPrefix),
                          _("File MUST use utf-8 encoding: %(file)s, error %(error)s"),
                          file=filepath, error=str(ex))
                except json.JSONDecodeError as ex:
                    raise OIMException("{}:invalidJSON".format(errPrefix),
                            "JSON error while %(action)s, %(file)s, error %(error)s",
                            file=filepath, action=currentAction, error=ex)
                # check for top-level key duplicates
                if isinstance(oimObject, dict) and DUPJSONKEY in oimObject:
                    for _errKey, _errValue, _otherValue in oimObject[DUPJSONKEY]:
                        error("{}:invalidJSON".format(errPrefix),
                              _("The key %(key)s is used on multiple objects"),
                              modelObject=modelXbrl, key=_errKey)
                    del oimObject[DUPJSONKEY]
                oimWb = None
            elif isXL:
                _file, = modelXbrl.fileSource.file(filepath, binary=True)
                with _file as f:
                    oimWb = load_workbook(f, data_only=True)
                if "metadata" not in oimWb:
                    raise OIMException("xbrlwe:missingWorkbookWorksheets", 
                                       _("Unable to identify worksheet tabs for metadata"))
                _foundMatch = False
                for row in range(1,10): # allow metadata to be indented or surrounded by column and row title columns
                    for col in range(1,10):
                        _metadata = xlValue(oimWb["metadata"].cell(row=row,column=col))
                        if _metadata and JSONmetadataPattern.match(_metadata): # find JSON metadata cell
                            _foundMatch = True
                            break
                    if _foundMatch:
                        break
                try:
                    oimObject = json.loads(_metadata, object_pairs_hook=loadDict)
                except UnicodeDecodeError as ex:
                    raise OIMException("{}:invalidJSON".format(errPrefix),
                          _("File MUST use utf-8 encoding: %(file)s \"metadata\" worksheet, error %(error)s"),
                          file=filepath, error=str(ex))
                except json.JSONDecodeError as ex:
                    raise OIMException("{}:invalidJSON".format(errPrefix),
                            "JSON error while %(action)s, %(file)s \"metadata\" worksheet, error %(error)s",
                            file=filepath, action=currentAction, error=ex)
            # identify document type (JSON or CSV)
            documentInfo = jsonGet(oimObject, "documentInfo", {})
            documentType = jsonGet(documentInfo, "documentType")
            documentBase = jsonGet(documentInfo, "baseURL")
            if documentType in jsonDocumentTypes:
                isCSV = False
                isJSON = True
                errPrefix = "xbrlje"
                oimMemberTypes = JsonMemberTypes
                oimRequiredMembers = JsonRequiredMembers
            elif documentType in csvDocumentTypes:
                isJSON = False
                isCSV = not isXL
                errPrefix = "xbrlce"
                oimMemberTypes = CsvMemberTypes
                oimRequiredMembers = CsvRequiredMembers
            else: # if wrong type defer to type checking
                isCSV = False
                isJSON = False
                #errPrefix was set earlier based on file name
                oimMemberTypes = UnrecognizedDocMemberTypes
                oimRequiredMembers = UnrecognizedDocRequiredMembers
            isCSVorXL = isCSV or isXL

            # report loadDict errors
            for msgCode, msgText, kwargs in loadDictErrors:
                error(msgCode.format(errPrefix), msgText, href=filepath, **kwargs)
            del loadDictErrors[:]
            
            invalidMemberTypes = []
            missingRequiredMembers = []
            unexpectedMembers = []
            def showPathObj(parts, obj): # this can be replaced with jsonPath syntax if appropriate
                try:
                    shortObjStr = json.dumps(obj)
                except TypeError:
                    shortObjStr = str(obj)
                if len(shortObjStr) > 34:
                    shortObjStr = "{:.32}...".format(shortObjStr)
                return "/{}={}".format("/".join(str(p) for p in parts), shortObjStr) 
            def checkMemberTypes(obj, path, pathParts):
                checkNestedMembers = True
                if (isinstance(obj,dict)):
                    for missingMbr in oimRequiredMembers.get(path,EMPTY_SET) - obj.keys():
                        missingRequiredMembers.append(path + missingMbr)
                    for mbrName, mbrObj in obj.items():
                        mbrPath = path + mbrName
                        pathParts.append(mbrName)
                        if mbrPath in oimMemberTypes:
                            mbrTypes = oimMemberTypes[mbrPath]
                            if (not ((mbrTypes is QNameType or (isinstance(mbrTypes,tuple) and QNameType in mbrTypes)) and isinstance(mbrObj, str) and QNamePattern.match(mbrObj)) and
                                not ((mbrTypes is SQNameType or (isinstance(mbrTypes,tuple) and SQNameType in mbrTypes)) and isinstance(mbrObj, str) and SQNamePattern.match(mbrObj)) and
                                not ((mbrTypes is LangType or (isinstance(mbrTypes,tuple) and LangType in mbrTypes)) and isinstance(mbrObj, str) and languagePattern.match(mbrObj)) and
                                not ((mbrTypes is URIType or (isinstance(mbrTypes,tuple) and URIType in mbrTypes)) and isinstance(mbrObj, str) and relativeUrlPattern.match(mbrObj) and not WhitespaceUntrimmedPattern.match(mbrObj)) and
                                not ((mbrTypes is int or (isinstance(mbrTypes,tuple) and int in mbrTypes)) and isinstance(mbrObj, str) and CanonicalIntegerPattern.match(mbrObj)) and
                                not isinstance(mbrObj, mbrTypes)):
                                invalidMemberTypes.append(showPathObj(pathParts, mbrObj))
                        elif ":" in mbrName and path + "*:*" in oimMemberTypes:
                            if not (QNamePattern.match(mbrName) and
                                    isinstance(mbrObj, oimMemberTypes[path + "*:*"])):
                                invalidMemberTypes.append(showPathObj(pathParts, mbrObj))
                            elif NoRecursionCheck in oimMemberTypes[path + "*:*"]:
                                checkNestedMembers = False # custom types, block recursive check
                            mbrPath = path + "*.*" # for recursion
                        elif path + "*" in oimMemberTypes:
                            mbrTypes = oimMemberTypes[path + "*"]
                            if (not ((mbrTypes is URIType or (isinstance(mbrTypes,tuple) and isinstance(mbrObj, str) and URIType in mbrTypes)) and relativeUrlPattern.match(mbrObj)) and
                                not isinstance(mbrObj, mbrTypes)):
                                invalidMemberTypes.append(showPathObj(pathParts, mbrObj))
                            mbrPath = path + "*" # for recursion
                        else:
                            unexpectedMembers.append(showPathObj(pathParts, mbrObj))
                        if isinstance(mbrObj, (dict,list)) and checkNestedMembers:
                            checkMemberTypes(mbrObj, mbrPath + "/", pathParts)
                        pathParts.pop() # remove mbrName
                if (isinstance(obj,list)):
                    mbrNdx = 1
                    for mbrObj in obj:
                        mbrPath = path # list entry just uses path ending in /
                        pathParts.append(mbrNdx)
                        if mbrPath in oimMemberTypes:
                            if not isinstance(mbrObj, oimMemberTypes[mbrPath]):
                                invalidMemberTypes.append(showPathObj(pathParts, mbrObj))
                        if isinstance(mbrObj, (dict,list)):
                            checkMemberTypes(mbrObj, mbrPath + "/", pathParts)
                        pathParts.pop() # remove mbrNdx
                        mbrNdx += 1
            checkMemberTypes(oimObject, "/", [])
            numErrorsBeforeJsonCheck = len(modelXbrl.errors)
            if not isJSON and not isCSV and not isXL:
                error("oimce:unsupportedDocumentType",
                      _("Unrecognized /documentInfo/docType: %(documentType)s"),
                      documentType=documentType)
            if missingRequiredMembers or unexpectedMembers:
                msg = []
                if missingRequiredMembers:
                    msg.append(_("Required element(s) are missing from metadata: %(missing)s"))
                if unexpectedMembers:
                    msg.append(_("Unexpected element(s) in metadata: %(unexpected)s"))
                error("{}:invalidJSONStructure".format(errPrefix),
                      "\n ".join(msg), documentType=documentType,
                      missing=", ".join(missingRequiredMembers), unexpected=", ".join(unexpectedMembers))
            if invalidMemberTypes:
                error("{}:invalidJSONStructure".format(errPrefix),
                      _("Invalid JSON structure member types in metadata: %(members)s"),
                      members=", ".join(invalidMemberTypes))
                
            if isCSV and not primaryReportParameters:
                primaryReportParameters = oimObject.setdefault("parameters", {})
                
            # read reportParameters if in a CSV file relative to parent metadata file
            if isinstance(oimObject.get("parameterURL"), str):
                parameterURL = oimObject["parameterURL"]
                parameterFilePath = os.path.join(os.path.dirname(primaryOimFile), parameterURL)
                if modelXbrl.fileSource.exists(parameterFilePath):
                    problems = []
                    for i, row in enumerate(openCsvReader(parameterFilePath, hasHeaderRow=False)):
                        if i == 0:
                            if row != ["name", "value"]:
                                problems.append(_("The first row must only consist of \"name\" and \"value\" but contains: {}").format(",".join(row)))
                        elif row[0]:
                            if not IdentifierPattern.match(row[0]):
                                problems.append(_("Row {} column 1 is not a valid identifier: {}").format(i+1, row[0]))
                            elif len(row) < 2 or not row[1]:
                                problems.append(_("Row {} value column 2 missing").format(i+1))
                            elif any(cell for cell in row[2:]):
                                problems.append(_("Row {} columns 3 - {} must be empty").format(i+1, len(row)))
                            elif row[0] in primaryReportParameters:
                                if primaryReportParameters[row[0]] != row[1]:
                                    error("xbrlce:illegalReportParameterRedefinition", 
                                          _("Report parameter %(name)s redefined in file %(file)s, report value %(value1)s, csv value %(value2)s"),
                                          file=parameterURL, name=row[0], value1=primaryReportParameters[row[0]], value2=row[1])
                            else:
                                primaryReportParameters[row[0]] = row[1]
                        elif any(cell for cell in row):
                            problems.append(_("Row {} has no identifier, all columns must be empty").format(i+1))
                    if problems:
                        error("xbrlce:invalidParameterCSVFile", 
                              _("Report parameter file %(file)s issues:\n %(issues)s"),
                              file=parameterURL, issues=", \n".join(problems))
                else:
                    error("xbrlce:missingParametersFile", 
                          _("Report parameter file is missing: %(file)s"),
                          file=parameterURL)


            if isCSVorXL and "extends" in documentInfo:
                # process extension
                for extendedFile in documentInfo["extends"]:
                    extendedOimObject = loadOimObject(extendedFile, mappedUrl)
                    # extended must be CSV
                    extendedDocumentInfo = extendedOimObject.get("documentInfo", EMPTY_DICT)
                    extendedDocumentType = extendedDocumentInfo.get("documentType")
                    extendedFinal = extendedDocumentInfo.get("final", EMPTY_DICT)
                    if extendedDocumentType != documentType:
                        error("{}:invalidExtendedDocumentType".format(errPrefix), 
                              _("Extended documentType %(extendedDocumentType)s must same as extending documentType %(documentType)s in file %(extendedFile)s"),
                              extendedFile=extendedFile, extendedDocumentType=extendedDocumentType, documentType=documentType)
                        raise OIMException()
                    if extendedFinal.get("parameters") and "parameterURL" in oimObject:
                        error("{}:unusableParameterURL".format(errPrefix),
                              _("Extending file %(extendedFile)s final parameters conflicts with extended parameterURL %(parameterURL)s"),
                              extendedFile=extendedFile, parameterURL=oimObject["parameterURL"])
                    else:
                        oimParameters = oimObject.setdefault("parameters", {})
                        for paramName, paramValue in extendedOimObject.get("parameters",{}).items():
                            if paramName in oimParameters and oimParameters[paramName] != paramValue:
                                error("xbrlce:illegalReportParameterRedefinition", 
                                      _("Report parameter %(name)s redefined in file %(file)s, extended value %(value1)s, extending value %(value2)s"),
                                      file=extendedFile, name=paramName, value1=oimParameters[paramName], value2=paramValue)
                            else:
                                oimParameters[paramName] = paramValue
                    for parent, extendedParent, excludedObjectNames in (
                        (documentInfo, extendedDocumentInfo, {"documentType", "extends"}),
                        (oimObject, extendedOimObject, {"documentInfo", "parameters", "parameterURL"})):
                        for objectName in extendedParent.keys() - excludedObjectNames:
                            if extendedFinal.get(objectName, False) and objectName in parent:
                                error("{}:extendedFinalObject".format(errPrefix), 
                                      _("Extended file %(extendedFile)s redefines final object %(finalObjectName)s"),
                                      extendedFile=extendedFile, finalObjectName=objectName)
                                if objectName in extendedParent:
                                    parent[objectName] = extendedParent[objectName] # ignore post-final extensions
                            elif objectName in csvExtensibleObjects:
                                for extProp, extPropValue in extendedParent.get(objectName,EMPTY_DICT).items():
                                    if extProp in parent.get(objectName,EMPTY_DICT):
                                        error("{}:extendedObjectDuplicate".format(errPrefix), 
                                              _("Extended file %(extendedFile)s redefines object %(objectName)s property %(property)s"),
                                              extendedFile=extendedFile, objectName=objectName, property=extProp)
                                    else:
                                        if objectName not in parent:
                                            parent[objectName] = {}
                                        parent[objectName][extProp] = extPropValue
                            elif objectName in parent:
                                if objectName == "taxonomy":
                                    for extPropValue in extendedParent["taxonomy"]:
                                        if extPropValue not in parent["taxonomy"]:
                                            parent["taxonomy"].append(extPropValue)
                                else:
                                    error("{}:extendedObjectDuplicate".format(errPrefix), 
                                          _("Extended file %(extendedFile)s redefines object %(objectName)s"),
                                          extendedFile=extendedFile, objectName=objectName)
                            else:
                                parent[objectName] = extendedParent[objectName]
                                
            if extendingFile is None: # entry oimFile
                if ("taxonomy" in documentInfo or isCSV) and not documentInfo.get("taxonomy",()):
                    error("oime:noTaxonomy",
                          _("The list of taxonomies MUST NOT be empty."))
                if  len(modelXbrl.errors) > numErrorsBeforeJsonCheck:
                    raise OIMException()
    
                oimObject["=entryParameters"] = (isJSON, isCSV, isXL, isCSVorXL, oimWb, documentInfo, documentType, documentBase)
                
            return oimObject
        
        errorIndexBeforeLoadOim = len(modelXbrl.errors)
        oimObject = loadOimObject(oimFile, None)
        isJSON, isCSV, isXL, isCSVorXL, oimWb, oimDocumentInfo, documentType, documentBase = oimObject["=entryParameters"]
        del oimObject["=entryParameters"]
        
        currentAction = "identifying Metadata objects"
        taxonomyRefs = oimDocumentInfo.get("taxonomy", EMPTY_LIST)
        namespaces = oimDocumentInfo.get("namespaces", EMPTY_DICT)
        linkTypes = oimDocumentInfo.get("linkTypes", EMPTY_DICT)
        linkGroups = oimDocumentInfo.get("linkGroups", EMPTY_DICT)
        featuresDict = oimDocumentInfo.get("features", EMPTY_DICT)
        canonicalValuesFeature = False
        if isJSON:
            errPrefix = "xbrlje"
            NSReservedAliasURIs.update(JSONNSReservedAliasURIs)
            factItems = oimObject.get("facts",{}).items()
            footnotes = oimObject.get("facts",{}).values() # shares this object
            canonicalValuesFeature = featuresDict.get("xbrl:canonicalValues") in (True, "true")
        else: # isCSVorXL
            errPrefix = "xbrlce"
            NSReservedAliasURIs.update(CSVNSReservedAliasURIs)
            reportDimensions = oimObject.get("dimensions", EMPTY_DICT)
            reportDecimals = oimObject.get("decimals", None)
            reportParameters = oimObject.get("parameters", {}) # fresh empty dict because csv-loaded parameters get added
            reportParametersUsed = set()
            tableTemplates = oimObject.get("tableTemplates", EMPTY_DICT)
            tables = oimObject.get("tables", EMPTY_DICT)
            footnotes = (oimObject.get("links", {}), )
            final = oimObject.get("final", EMPTY_DICT)
            
            # check reportParameterNames
            for reportParameterName in reportParameters.keys():
                if not IdentifierPattern.match(reportParameterName):
                    error("xbrlce:invalidParameterName", 
                          _("Report parameter name is not a valid identifier: %(identifier)s, in file %(file)s"),
                          identifier=reportParameterName, file=oimFile)
            
        allowedDuplicatesFeature = ALL
        v = featuresDict.get("xbrl:allowedDuplicates")
        if v is not None:
            if v in AllowedDuplicatesFeatureValues:
                allowedDuplicatesFeature = AllowedDuplicatesFeatureValues[v]
            else:
                error("{}:invalidJSONStructure".format(errPrefix), 
                      _("The xbbrl:allowedDuplicates feature has an invalid value: %(value)s"),
                      value=v)
                    
        # check features
        for featureSQName, isActive in featuresDict.items():
            featurePrefix = featureSQName.partition(":")[0]
            if featurePrefix not in namespaces:
                error("oimce:unboundPrefix",
                      _("The feature QName prefix was not defined in namespaces: %(feature)s."),
                      modelObject=modelXbrl, feature=featureSQName)
                continue

        # check maps
        for alias, uris in NSReservedAliasURIs.items():
            for uri in uris:
                NSReservedURIAlias[uri] = alias
                
        for map in ("namespaces", "linkTypes", "linkGroups"):
            for key, value in oimDocumentInfo.get(map, EMPTY_DICT).items():
                if key in OIMReservedAliasURIs[map] and value not in OIMReservedAliasURIs[map][key]:
                    error("oimce:invalidURIForReservedAlias",
                          _("The %(map)s URI \"%(uri)s\" is used on standard alias \"%(alias)s\" which requires URI \"%(standardUri)s\"."),
                          modelObject=modelXbrl, map=map, alias=key, uri=value, standardUri=OIMReservedAliasURIs[map][key][0])
                elif value in OIMReservedURIAlias[map] and key != OIMReservedURIAlias[map][value]:
                    error("oimce:invalidAliasForReservedURI",
                          _("The %(map)s URI \"%(uri)s\" is bound to alias \"%(key)s\" instead of standard alias \"%(alias)s\"."),
                          modelObject=modelXbrl, map=key, key=key, uri=value, alias=OIMReservedURIAlias[map][value])
                
        if isCSVorXL:
            currentAction = "loading CSV facts tables"
            _dir = os.path.dirname(oimFile)

            def csvFacts():
                for tableId, table in tables.items():
                    _file = tablePath = None
                    try: # note that decoder errors may occur late during streaming of rows
                        tableTemplateId = table.get("template", tableId)
                        if tableTemplateId not in tableTemplates:
                            raise OIMException("xbrlce:missingTableTemplate", 
                                               _("Referenced template missing: %(missing)s"),
                                               missing=tableTemplateId)
                        tableTemplate = tableTemplates[tableTemplateId]
                        # tableIsTransposed = tableTemplate.get("transposed", False)
                        tableDecimals = tableTemplate.get("decimals")
                        tableDimensions = tableTemplate.get("dimensions", EMPTY_DICT)
                        tableIsOptional = table.get("optional", False)
                        tableParameters = table.get("parameters", EMPTY_DICT)
                        tableParametersUsed = set()
                        rowIdColName = tableTemplate.get("rowIdColumn")
                        tableUrl = table["url"]
                        tableParameterColNames = set()
                        hasHeaderError = False # set to true blocks handling file beyond header row
                        for tableParameterName in tableParameters:
                            if not IdentifierPattern.match(tableParameterName):
                                error("xbrlce:invalidParameterName", 
                                      _("Table %(table)s parameter name is not a valid identifier: %(identifier)s, url: %(url)s"),
                                      table=tableId, identifier=tableParameterName, url=tableUrl)
                                
                        # compile column dependencies
                        factDimensions = {} # keys are column, values are dimensions object
                        factDecimals = {} # keys are column
                        colDefaults = {}
                        propertyGroups = {}
                        propertiesFrom = {}
                        for colId, colProperties in tableTemplate["columns"].items():
                            factDimensions[colId] = colProperties.get("dimensions")
                            factDecimals[colId] = colProperties.get("decimals")
                            if factDecimals[colId] is not None:
                                if factDimensions[colId] is None:
                                    hasHeaderError = True
                                    error("xbrlce:misplacedDecimalsOnNonFactColumn", 
                                          _("Table %(table)s column %(column)s has decimals but dimensions is absent"),
                                          table=tableId, column=colId)
                            if "default" in colProperties:
                                colDefaults[colId] = colProperties["default"]
                            if "propertyGroups" in colProperties:
                                propertyGroups[colId] = colProperties["propertyGroups"]
                            if "propertiesFrom" in colProperties:
                                propertiesFrom[colId] = colProperties["propertiesFrom"]
                            if "decimals" in colProperties and ("dimensions" not in colProperties and "propertiesFrom" not in colProperties):
                                error("xbrlce:misplacedDecimalsOnNonFactColumn", 
                                      _("Table %(table)s has decimals on a non-fact column %(column)s"),
                                      table=tableId, column=colId)
                        if rowIdColName and rowIdColName not in factDecimals:
                            raise OIMException("xbrlce:undefinedRowIdColumn", 
                                  _("Table %(table)s row id column %(column)s is not defined in columns"),
                                  table=tableId, column=rowIdColName)
                        if propertiesFrom:
                            for col, propertiesFromCol in propertiesFrom.items():
                                if propertiesFromCol not in propertyGroups:
                                    raise OIMException("xbrlce:invalidPropertyGroupColumnReference", 
                                          _("Table %(table)s row id column %(column)s propertiesFrom reference %(propertiesFrom)s does not define a property groups column."),
                                          table=tableId, column=col, propertiesFrom=propertiesFromCol)
                        # check table parameters
                        tableParameterReferenceNames = set()
                        factColReferenceNames = defaultdict(set)
                        def checkParamRef(paramValue, factColName=None):
                            if isinstance(paramValue, str) and paramValue.startswith("$") and not paramValue.startswith("$$"):
                                paramName = paramValue[1:].partition("@")[0]
                                tableParameterReferenceNames.add(paramName)
                                if factColName:
                                    factColReferenceNames[factColName].add(paramName)
                        hasNoteIdDimension = False
                        for factColName, colDims in factDimensions.items():
                            if colDims is not None:
                                factDims = set()
                                for inheritedDims in (colDims.items(), tableDimensions.items(), reportDimensions.items()):
                                    for dimName, dimValue in inheritedDims:
                                        if dimName not in factDims:
                                            checkParamRef(dimValue, factColName)
                                            factDims.add(dimName)
                                        if dimName == "noteId":
                                            hasNoteIdDimension = True
                                for _factDecimals in (factDecimals.get(factColName), tableDecimals, reportDecimals):
                                    if "decimals" not in factDims:
                                        checkParamRef(_factDecimals, factColName)
                        if hasNoteIdDimension:
                            hasHeaderError = True
                            error("xbrlce:invalidNoteIdDimension", 
                                  _("Table %(table)s noteId dimension must not be explicitly defined, url: %(url)s"),
                                  table=tableId, url=tableUrl)
                        for dimName, dimValue in tableParameters.items():
                            if not IdentifierPattern.match(dimName):
                                error("xbrlce:invalidParameterName", 
                                      _("Table %(table)s parameter name is not a valid identifier: %(identifier)s, url: %(url)s"),
                                      table=tableId, identifier=dimName, url=tableUrl)
              
                        # determine whether table is a CSV file or an Excel range.  
                        # Local range can be sheetname! or !rangename
                        # url to workbook with range must be url#sheet! or url#!range or url!range (unencoded !)
                        tableWb = None
                        _file = None
                        _rowIterator = None
                        _cellValue = None
                        if isXL and not ("#" in tableUrl or ".xlsx" in tableUrl or ".csv" in tableUrl):
                            # local Workbook range
                            tableWb = oimWb
                            _cellValue = xlValue
                            xlSheetName, _sep, xlNamedRange = tableUrl.partition('!')
                        else: 
                            # check if there's a reference to an Excel workbook file
                            if "#" in tableUrl:
                                tableUrl, _sep, sheetAndRange = tableUrl.partition("#")
                                xlSheetName, _sep, xlNamedRange = sheetAndRange.partition('!')
                            tablePath = os.path.join(_dir, tableUrl)
                            if not modelXbrl.fileSource.exists(tablePath):
                                if not tableIsOptional:
                                    error("xbrlce:missingRequiredCSVFile", 
                                          _("Table %(table)s missing, url: %(url)s"),
                                          table=tableId, url=tableUrl)
                                continue
                            if tableUrl.endswith(".xlsx"):
                                _file, = modelXbrl.fileSource.file(tablePath, binary=True)
                                tableWb = load_workbook(_file, data_only=True)
                                _cellValue = xlValue
                            else:
                                # must be CSV
                                _rowIterator = openCsvReader(tablePath)
                                _cellValue = csvCellValue
                                # if tableIsTransposed:
                                #    _rowIterator = transposer(_rowIterator)
                        if tableWb is not None:
                            hasSheetname = xlSheetName and xlSheetName in tableWb
                            hasNamedRange = xlNamedRange and xlNamedRange in tableWb.defined_names
                            if tableWb and not hasSheetname:
                                if tableIsOptional:
                                    continue
                                raise OIMException("xbrlwe:missingTable", 
                                                   _("Referenced table tab(s): %(missing)s"),
                                                   missing=tableUrl)
                            if xlNamedRange and not hasNamedRange:
                                if tableIsOptional:
                                    continue
                                raise OIMException("xbrlwe:missingTableNamedRange", 
                                                   _("Referenced named ranges tab(s): %(missing)s"),
                                                   missing=tableRangeName)
                            if hasNamedRange: # check type of range
                                defn = tableWb.defined_names[xlNamedRange]
                                if defn.type != "RANGE":
                                    raise OIMException("xbrlwe:unusableRange", 
                                                       _("Referenced range does not refer to a range: %(tableRange)s"),
                                                       tableRange=tableRangeName)
                            _rowIterator = []
                            if hasNamedRange:
                                for _tableName, _xlCellsRange in tableWb.defined_names[xlNamedRange].destinations:
                                    rows = tableWb[_tableName][_xlCellsRange]
                                    if isinstance(rows, Cell):
                                        _rowIterator.append((rows, ))
                                    else:
                                        _rowIterator.extend(rows)
                            else: # use whole table
                                _rowIterator = tableWb[xlSheetName]
                            # if tableIsTransposed:
                            #     _rowIterator = transposer(_rowIterator)
                        
                        rowIds = set()
                        paramRefColNames = set()
                        for rowIndex, row in enumerate(_rowIterator):
                            if rowIndex == 0:
                                header = [_cellValue(cell) for cell in row]
                                if isXL: # trim empty cells
                                    header = xlTrimHeaderRow(header)
                                colNameIndex = dict((name, colIndex) for colIndex, name in enumerate(header))
                                idColIndex = colNameIndex.get(rowIdColName)
                                for colIndex, colName in enumerate(header):
                                    if not IdentifierPattern.match(colName):
                                        hasHeaderError = True
                                        error("xbrlce:invalidHeaderValue", 
                                              _("Table %(table)s CSV file header column %(column)s is not a valid identifier: %(identifier)s, url: %(url)s"),
                                              table=tableId, column=colIndex+1, identifier=colName, url=tableUrl)
                                    elif colName not in factDimensions:
                                        hasHeaderError = True
                                        error("xbrlce:unknownColumn", 
                                              _("Table %(table)s CSV file header column %(column)s is not in table template definition: %(identifier)s, url: %(url)s"),
                                              table=tableId, column=colIndex+1, identifier=colName, url=tableUrl)
                                    elif colNameIndex[colName] != colIndex:
                                        error("xbrlce:repeatedColumnIdentifier", 
                                              _("Table %(table)s CSV file header columns %(column)s and %(column2)s repeat identifier: %(identifier)s, url: %(url)s"),
                                              table=tableId, column=colIndex+1, column2=colNameIndex[colName]+1, identifier=colName, url=tableUrl)
                                    elif factDimensions[colName] is not None:
                                        if idColIndex is not None and colIndex < idColIndex:
                                            error("xbrlce:invalidColumnOrder", 
                                                  _("Table %(table)s CSV fact column %(column)s, appears before row ID column %(rowIdColumn)s, url: %(url)s"),
                                                  table=tableId, column=colName, rowIdColumn=rowIdColName, url=tableUrl)
                                        followingParamColNames = [paramName
                                                                  for paramName in factColReferenceNames[colName]
                                                                  if colNameIndex.get(paramName,-1) > colIndex]
                                        if followingParamColNames:
                                            error("xbrlce:invalidColumnOrder", 
                                                  _("Table %(table)s CSV fact column %(column)s, appears before parameter columns %(paramColumns)s, url: %(url)s"),
                                                  table=tableId, column=colName, paramColumns=", ".join(sorted(followingParamColNames)), url=tableUrl)
                                    if colName in tableParameterReferenceNames:
                                        paramRefColNames.add(colName)
                                missingPropFromCols = propertiesFrom.values() - colNameIndex.keys()
                                if missingPropFromCols:
                                    raise OIMException("xbrlce:invalidPropertyGroupColumnReference", 
                                                  _("Table %(table)s propertyFrom %(propFromColumns)s column missing, url: %(url)s"),
                                                  table=tableId, propFromColumns=", ".join(sorted(missingPropFromCols)), url=tableUrl)
                                # check parameter references
                                checkedDims = set()
                                checkedParams = set()
                                def dimChecks():
                                    for colName, colDims in factDimensions.items():
                                        if colDims:
                                            yield colDims, "column {} dimension".format(colName)
                                    # no way to check parameterGroup dimensions at header-row processing time
                                    for dims, source in ((tableDimensions, "table dimension"), 
                                                         (reportDimensions, "report dimension"),
                                                         ):
                                        yield dims, source
                                    for colName, dec in factDecimals.items():
                                        yield {"decimals": dec}, "column {} decimals".format(colName)
                                    for dec, source in ((tableDecimals, "table decimals"),
                                                        (reportDecimals, "report decimals")):
                                        if source:
                                            yield {"decimals": dec}, source
                                for inheritedDims, dimSource in dimChecks():
                                    for dimName, dimValue in inheritedDims.items():
                                        if dimName not in checkedDims:
                                            dimValue = inheritedDims[dimName]
                                            # resolve column-relative dimensions
                                            if isinstance(dimValue, str) and dimValue.startswith("$"):
                                                dimValue = dimValue[1:]
                                                if not dimValue.startswith("$"):
                                                    dimValue, _sep, dimAttr = dimValue.partition("@")
                                                    if dimAttr and dimAttr not in ("start", "end"):
                                                        hasHeaderError = True
                                                        error("xbrlce:invalidPeriodSpecifier", 
                                                              _("Table %(table)s %(source)s %(dimension)s period-specifier invalid: %(target)s, url: %(url)s"),
                                                              table=tableId, source=dimSource, dimension=dimName, target=dimAttr, url=tableUrl)
                                                    if dimValue not in checkedParams:
                                                        checkedParams.add(dimValue)
                                                        if dimValue in ("rowNumber", ) or dimValue in header or dimValue in tableParameters or dimValue in reportParameters:
                                                            checkedDims.add(dimValue)
                                                        else:
                                                            hasHeaderError = True
                                                            error("xbrlce:invalidReferenceTarget", 
                                                                  _("Table %(table)s %(dimension)s target not in table columns, parameters or report parameters: %(target)s, url: %(url)s"),
                                                                  table=tableId, dimension=dimName, target=dimValue, url=tableUrl)
                                if hasHeaderError:
                                    break # stop processing table
                            else:
                                rowId = None
                                paramColsWithValue = set()
                                paramColsUsed = set()
                                if isXL and all(cell.value in (None, "") for cell in row): # skip empty excel rows
                                    continue
                                rowPropGroups = {} # colName, propGroupObject for property groups in this row
                                rowPropGroupsUsed = set() # colNames used by propertiesFrom of fact col producing a fact
                                for propGrpName, propGrpObjects in propertyGroups.items():
                                    propGrpColIndex = colNameIndex[propGrpName]
                                    if propGrpColIndex < len(row):
                                        propGrpColValue = _cellValue(row[propGrpColIndex])
                                        if propGrpColValue in propGrpObjects:
                                            rowPropGroups[propGrpName] = propGrpObjects[propGrpColValue]
                                        else:
                                            error("xbrlce:unknownPropertyGroup", 
                                                  _("Table %(table)s unknown property group row %(row)s column %(column)s group %(propertyGroup)s, url: %(url)s"),
                                                  table=tableId, row=rowIndex+1, column=rowIdColName, url=tableUrl, propertyGroup=propGrpName)
                                for colIndex, colValue in enumerate(row):
                                    if colIndex >= len(header):
                                        continue
                                    cellPropGroup = EMPTY_DICT
                                    colName = header[colIndex]
                                    propFromColName = propertiesFrom.get(colName)
                                    if propFromColName in rowPropGroups:
                                        cellPropGroup = rowPropGroups[propFromColName]
                                    if factDimensions[colName] is None:
                                        if colName in paramRefColNames:
                                            value = _cellValue(row[colNameIndex[colName]])
                                            if value:
                                                paramColsWithValue.add(colName)
                                        if not cellPropGroup:
                                            continue # not a fact column
                                    # assemble row and fact Ids
                                    if idColIndex is not None and not rowId:
                                        if idColIndex < len(row):
                                            rowId = _cellValue(row[idColIndex])
                                        if not rowId:
                                            error("xbrlce:missingRowIdentifier", 
                                                  _("Table %(table)s missing row %(row)s column %(column)s row identifier, url: %(url)s"),
                                                  table=tableId, row=rowIndex+1, column=rowIdColName, url=tableUrl)
                                        elif not IdentifierPattern.match(rowId):
                                            error("xbrlce:invalidRowIdentifier", 
                                                  _("Table %(table)s row %(row)s column %(column)s is not a valid identifier: %(identifier)s, url: %(url)s"),
                                                  table=tableId, row=rowIndex+1, column=rowIdColName, identifier=rowId, url=tableUrl)
                                        elif rowId in rowIds:
                                            error("xbrlce:repeatedRowIdentifier", 
                                                  _("Table %(table)s row %(row)s column %(column)s is a duplicate: %(identifier)s, url: %(url)s"),
                                                  table=tableId, row=rowIndex+1, column=rowIdColName, identifier=rowId, url=tableUrl)
                                        else:
                                            rowIds.add(rowId)
                                    if rowId is None:
                                        rowId = str(rowIndex)
                                    factId = "{}.{}.{}".format(tableId, rowId, colName)
                                    fact = {}
                                    # if this is an id column
                                    cellValue = _cellValue(colValue) # nil facts return None, #empty string is ""
                                    if cellValue == "": # no fact produced
                                        continue 
                                    if propFromColName and cellPropGroup:
                                        rowPropGroupsUsed.add(propFromColName)
                                    fact["value"] = cellValue
                                    fact["dimensions"] = colFactDims = {}
                                    noValueDimNames = set()
                                    for inheritedDims, dimSource in ((factDimensions[colName], "column dimension"), 
                                                                     (cellPropGroup.get("dimensions",EMPTY_DICT), "propertyGroup {}".format(propFromColName)),
                                                                     (tableDimensions, "table dimension"), 
                                                                     (reportDimensions, "report dimension")):
                                        for dimName, dimValue in inheritedDims.items():
                                            if dimName not in colFactDims and dimName not in noValueDimNames:
                                                dimValue = inheritedDims[dimName]
                                                dimAttr = None
                                                # resolve column-relative dimensions
                                                if isinstance(dimValue, str) and dimValue.startswith("$"):
                                                    dimValue = dimValue[1:]
                                                    if not dimValue.startswith("$"):
                                                        paramName, _sep, dimAttr = dimValue.partition("@")
                                                        if paramName == "rowNumber":
                                                            dimValue = str(rowIndex)
                                                        elif paramName in colNameIndex:
                                                            paramColsUsed.add(paramName)
                                                            dimValue = _cellValue(row[colNameIndex[paramName]])
                                                            if dimValue == "": # csv file empty string is #none
                                                                if paramName in colDefaults:
                                                                    dimValue = colDefaults[paramName]
                                                                else:
                                                                    dimValue = "#none"
                                                        elif paramName in tableParameters:
                                                            tableParametersUsed.add(paramName)
                                                            dimValue = tableParameters[paramName]
                                                        elif paramName in reportParameters:
                                                            reportParametersUsed.add(paramName)
                                                            dimValue = reportParameters[paramName]
                                                # else if in parameters?
                                                if dimName == "period":
                                                    _dimValue = csvPeriod(dimValue, dimAttr)
                                                    if _dimValue == "referenceTargetNotDuration":
                                                        error("xbrlce:referenceTargetNotDuration", 
                                                              _("Table %(table)s row %(row)s column %(column)s has instant date with period reference \"%(date)s\", from %(source)s, url: %(url)s"),
                                                              table=tableId, row=rowIndex+1, column=colName, date=dimValue, url=tableUrl, source=dimSource)
                                                        dimValue = "#none"
                                                    elif _dimValue == None: # bad format
                                                        error("xbrlce:invalidJSONStructure", 
                                                              _("Table %(table)s row %(row)s column %(column)s has lexical syntax issue with date \"%(date)s\", from %(source)s, url: %(url)s"),
                                                              table=tableId, row=rowIndex+1, column=colName, date=dimValue, url=tableUrl, source=dimSource)
                                                        dimValue = "#none"
                                                    else:
                                                        dimValue = _dimValue
                                                if dimValue == "#none":
                                                    noValueDimNames.add(dimName)
                                                else:
                                                    colFactDims[dimName] = dimValue
                                    if factDecimals.get(colName) is not None:
                                        dimValue = factDecimals[colName]
                                        dimSource = "column decimals"
                                    elif "decimals" in cellPropGroup:
                                        dimValue = cellPropGroup["decimals"]
                                        dimSource = "propertyGroup " + propFromColName
                                    elif tableDecimals is not None:
                                        dimValue = tableDecimals
                                        dimSource = "table decimals"
                                    elif reportDecimals is not None:
                                        dimValue = reportDecimals
                                        dimSource = "report decimals"
                                    else:
                                        dimValue = None
                                        dimSource = "absent"
                                    if dimValue is not None:
                                        validCsvCell = False
                                        if isinstance(dimValue, str) and dimValue.startswith("$"):
                                            paramName = dimValue[1:]
                                            if paramName in colNameIndex:
                                                dimSource += " from CSV column " + paramName
                                                paramColsUsed.add(paramName)
                                                dimValue = _cellValue(row[colNameIndex[paramName]])
                                                if dimValue == "" and paramName in colDefaults:
                                                    dimValue = colDefaults[paramName]
                                                validCsvCell = integerPattern.match(dimValue or "") is not None # is None if is_XL
                                            elif paramName in tableParameters:
                                                dimSource += " from table parameter " + paramName
                                                tableParametersUsed.add(paramName)
                                                dimValue = tableParameters[paramName]
                                            elif paramName in reportParameters:
                                                reportParametersUsed.add(paramName)
                                                dimSource += " from report parameter " + paramName
                                                dimValue = reportParameters[paramName]
                                            else:
                                                dimValue = "$" + paramName # for error reporting
                                        if dimValue not in ("", "#none"):
                                            if isinstance(dimValue, int) or validCsvCell:                                          
                                                fact["decimals"] = dimValue
                                            else:
                                                error("xbrlce:invalidDecimalsValue", 
                                                      _("Fact %(FactId)S has invalid decimals \"%(decimals)s\", from %(source)s, url: %(url)s"),
                                                      table=tableId, row=rowIndex+1, column=colName, decimals=dimValue, url=tableUrl, source=dimSource)
                                    yield (factId, fact)
                                unmappedParamCols = paramColsWithValue - paramColsUsed
                                if unmappedParamCols:
                                    error("xbrlce:unmappedCellValue", 
                                          _("Table %(table)s row %(row)s unmapped parameter columns %(columns)s, url: %(url)s"),
                                          table=tableId, row=rowIndex+1, columns=", ".join(sorted(unmappedParamCols)), url=tableUrl)
                                unmappedPropGrps = rowPropGroups.keys() - rowPropGroupsUsed
                                if unmappedPropGrps:
                                    error("xbrlce:unmappedCellValue", 
                                          _("Table %(table)s row %(row)s unmapped property group columns %(columns)s, url: %(url)s"),
                                          table=tableId, row=rowIndex+1, columns=", ".join(sorted(unmappedPropGrps)), url=tableUrl)
                        unmappedTableParams = tableParameters.keys() - tableParametersUsed
                        if unmappedTableParams:
                            error("xbrlce:unmappedTableParameter", 
                                  _("Table %(table)s unmapped table parameters %(parameters)s, url: %(url)s"),
                                  table=tableId, row=rowIndex, parameters=", ".join(sorted(unmappedTableParams)), url=tableUrl)
                    except UnicodeDecodeError as ex:
                        raise OIMException("{}:invalidJSON".format(errPrefix),
                              _("File MUST use utf-8 encoding: %(file)s, error %(error)s"),
                              file=tablePath, error=str(ex))
                    tableWb = None # dereference
                    _rowIterator = None # dereference
                    if _file is not None:
                        _file.close()

            factItems = csvFacts()

        currentAction = "identifying default dimensions"
        if modelXbrl is not None:
            ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl) # needs dimension defaults 
        
        currentAction = "validating OIM"
        
        # create the instance document
        currentAction = "creating instance document"
        if modelXbrl: # pull loader implementation
            modelXbrl.blockDpmDBrecursion = True
            modelXbrl.modelDocument = _return = createModelDocument(
                  modelXbrl, 
                  Type.INSTANCE,
                  instanceFileName,
                  schemaRefs=taxonomyRefs,
                  isEntry=True,
                  initialComment="extracted from OIM {}".format(mappedUri),
                  documentEncoding="utf-8",
                  base=documentBase)
            modelXbrl.modelDocument.inDTS = True
        else: # API implementation
            modelXbrl = ModelXbrl.create(
                cntlr.modelManager, 
                Type.INSTANCE, 
                instanceFileName, 
                schemaRefs=taxonomyRefs, 
                isEntry=True, 
                initialComment="extracted from OIM {}".format(mappedUri),
                base=documentBase)
            _return = modelXbrl.modelDocument
        
        firstCntxUnitFactElt = None
            
        cntxTbl = {}
        unitTbl = {}
        xbrlNoteTbl = {} # fact ID: note fact
        noteFactIDsNotReferenced = set()
            
        currentAction = "creating facts"
        factNum = 0 # for synthetic fact number
        if isJSON:
            syntheticFactFormat = "_f{{:0{}}}".format(int(math.log10(len(factItems) or 1))) #want 
        else:
            syntheticFactFormat = "_f{}" #want 
        
        numFactCreationXbrlErrors = 0
        
        for id, fact in factItems:
            
            dimensions = fact.get("dimensions", EMPTY_DICT)
            if "concept" not in dimensions:
                error("oime:missingConceptDimension",
                      _("The concept core dimension MUST be present on fact: %(id)s."),
                      modelObject=modelXbrl, id=id)
                continue
            if not id:
                id = syntheticFactFormat.format(factNum)
                factNum += 1
            conceptSQName = dimensions["concept"]
            conceptPrefix = conceptSQName.partition(":")[0]
            if conceptSQName == "xbrl:note":
                xbrlNoteTbl[id] = fact
                if "language" not in dimensions:
                    error("oime:missingLanguageForNoteFact",
                          _("Missing language dimension for footnote fact %(id)s"),
                          modelObject=modelXbrl, id=id)
                if isCSVorXL:
                    dimensions["noteId"] = id # infer this dimension
                elif "noteId" not in dimensions:
                    error("oime:missingNoteIDDimension",
                          _("Missing noteId dimension for footnote fact %(id)s"),
                          modelObject=modelXbrl, id=id)                        
                elif dimensions.get("noteId") != id:
                    error("oime:invalidNoteIDValue",
                          _("The noteId dimension value, %(noteId)s, must be the same as footnote fact id, %(id)s"),
                          modelObject=modelXbrl, id=id, noteId=dimensions["noteId"])
                else:
                    noteFactIDsNotReferenced.add(id)
                if dimensions.get("unit") and not isCSVorXL:
                    error("oime:misplacedUnitDimension",
                          _("The unit core dimension MUST NOT be present on footnote fact %(id)s: %(unit)s."),
                          modelObject=modelXbrl, id=id, unit=dimensions.get("unit"))
                if fact.get("decimals") and not isCSVorXL:
                    error("oime:misplacedDecimalsProperty",
                          _("The decimals property MUST NOT be present on footnote fact %(id)s: %(decimals)s"),
                          modelObject=modelXbrl, id=id, decimals=decimals)
                unexpectedDimensions = [d for d in dimensions if d in ("entity", "period") or ":" in d]
                if unexpectedDimensions:
                    error("oime:misplacedNoteFactDimension",
                          _("Unexpected dimension(s) for footnote fact %(id)s: %(dimensions)s"),
                          modelObject=modelXbrl, id=id, dimensions=", ".join(sorted(unexpectedDimensions)))
                try:
                    unacceptableTopElts = set()
                    unacceptablePrefixes = set()
                    valueXhtmlElts = etree.XML(htmlBodyTemplate.format(fact.get("value","")))
                    for elt in valueXhtmlElts.iterchildren():
                        if not elt.tag.startswith(xhtmlTagPrefix):
                            unacceptableTopElts.add(elt.tag)
                    for elt in valueXhtmlElts.iter():
                        for prefix, ns in elt.nsmap.items():
                            if prefix and ns == xhtml:
                                unacceptablePrefixes.add(prefix)
                    if unacceptableTopElts:
                        error("oime:invalidXHTMLFragment",
                              _("xbrl:note MUST have xhtml top level elements in the default xhtml namespace, fact %(id)s, elements %(elements)s"),
                              modelObject=modelXbrl, id=id, elements=", ".join(sorted(unacceptableTopElts)))
                    if unacceptablePrefixes:
                        error("oime:xhtmlElementInNonDefaultNamespace",
                              _("xbrl:note MUST have xhtml elements in the default xhtml namespace, fact %(id)s, non-default prefixes: %(prefixes)s"),
                              modelObject=modelXbrl, id=id, prefixes=", ".join(sorted(unacceptablePrefixes)))
                except (etree.XMLSyntaxError,
                        UnicodeDecodeError) as err:
                    error("oime:invalidXHTMLFragment",
                          _("Xhtml error for footnote fact %(id)s: %(error)s"),
                          modelObject=modelXbrl, id=id, error=str(err))
                continue
            elif "noteId" in dimensions:
                error("oime:misplacedNoteIDDimension",
                      _("Unexpected noteId dimension on non-footnote fact, id %(id)s"),
                      modelObject=modelXbrl, id=id, noteId=dimensions["noteId"])
            if conceptPrefix not in namespaces:
                error("oimce:unboundPrefix",
                      _("The concept QName prefix was not defined in namespaces: %(concept)s."),
                      modelObject=modelXbrl, concept=conceptSQName)
                continue
            conceptQn = qname(conceptSQName, namespaces)
            concept = modelXbrl.qnameConcepts.get(conceptQn)
            if concept is None:
                error("oime:unknownConcept",
                      _("The concept QName could not be resolved with available DTS: %(concept)s."),
                      modelObject=modelXbrl, concept=conceptQn)
                continue
            attrs = {}
            if concept.isItem:
                if concept.isAbstract:
                    error("oime:valueForAbstractConcept",
                          _("Value provided for abstract concept by fact %(factId)s, concept %(concept)s."),
                          modelObject=modelXbrl, factId=id, concept=conceptSQName)
                    continue # skip creating fact because context would be bad
                if "language" in dimensions:
                    lang = dimensions["language"]
                    if not concept.type.isOimTextFactType:
                        error("oime:misplacedLanguageDimension",
                              _("Language \"%(lang)s\" provided for non-text concept by fact %(factId)s, concept %(concept)s."),
                              modelObject=modelXbrl, factId=id, concept=conceptSQName, lang=lang)
                        continue # skip creating fact because language would be bad
                    elif isJSON and not lang.islower():
                        error("xbrlje:invalidLanguageCodeCase",
                              _("Language MUST be lower case: \"%(lang)s\", fact %(factId)s, concept %(concept)s."),
                              modelObject=modelXbrl, factId=id, concept=conceptSQName, lang=lang)
                    attrs["{http://www.w3.org/XML/1998/namespace}lang"] = lang
                entityAsQn = ENTITY_NA_QNAME
                entitySQName = dimensions.get("entity")
                if entitySQName is not None:
                    entityPrefix = entitySQName.partition(":")[0]
                    if entityPrefix not in namespaces:
                        error("oimce:unboundPrefix",
                              _("The entity QName prefix was not defined in namespaces: %(entity)s."),
                              modelObject=modelXbrl, entity=entitySQName)
                    else:
                        entityAsQn = qname(entitySQName, namespaces)
                if "xbrl:start" in dimensions and "xbrl:end" in dimensions:
                    # CSV/XL format
                    period = dimensions["xbrl:start"]
                    if period != dimensions["xbrl:end"]:
                        period += "/" + dimensions["xbrl:end"]
                elif "period" in dimensions:
                    period = dimensions["period"]
                    if period is None:
                        period = "forever"
                    elif not PeriodPattern.match(period):
                        error("oimce:invalidPeriodRepresentation",
                              _("The fact %(factId)s, concept %(element)s has a lexically invalid period dateTime %(periodError)s"),
                              modelObject=modelXbrl, factId=id, element=conceptQn, periodError=period)
                        continue
                else:
                    period = "forever"
                cntxKey = ( # hashable context key
                    ("periodType", concept.periodType),
                    ("entity", entityAsQn),
                    ("period", period)) + tuple(sorted(
                        (dimName, dimVal["value"] if isinstance(dimVal,dict) else dimVal) 
                        for dimName, dimVal in dimensions.items()
                        if ":" in dimName))
                _start, _sep, _end = period.rpartition('/')
                if period == "forever":
                    _periodType = "forever"
                elif _start == _end or not _start:
                    _periodType = "instant"
                else:
                    _periodType = "duration"
                if concept.periodType == "instant" and _periodType == "forever":
                    error("oime:missingPeriodDimension",
                          _("Missing period for %(periodType)s fact %(factId)s."),
                          modelObject=modelXbrl, factId=id, periodType=concept.periodType, period=period)
                    continue # skip creating fact because context would be bad
                elif ((concept.periodType == "duration" and (_periodType != "forever" and (not _start or _start == _end))) or
                      (concept.periodType == "instant" and _start and _start != _end)):
                    error("oime:invalidPeriodDimension",
                          _("Invalid period for %(periodType)s fact %(factId)s period %(period)s."),
                          modelObject=modelXbrl, factId=id, periodType=concept.periodType, period=period)
                    continue # skip creating fact because context would be bad
                elif cntxKey in cntxTbl:
                    _cntx = cntxTbl[cntxKey]
                else:
                    cntxId = 'c-{:02}'.format(len(cntxTbl) + 1)
                    qnameDims = {}
                    for dimName, dimVal in dimensions.items():
                        if ":" in dimName:
                            dimQname = qname(dimName, namespaces)
                            dimConcept = modelXbrl.qnameConcepts.get(dimQname)
                            if dimConcept is None:
                                error("oime:unknownDimension",
                                      _("Fact %(factId)s taxonomy-defined dimension QName not be resolved with available DTS: %(qname)s."),
                                      modelObject=modelXbrl, factId=id, qname=dimQname)
                                continue
                            if dimVal is None:
                                memberAttrs = {"{http://www.w3.org/2001/XMLSchema-instance}nil": "true"}
                            else:
                                memberAttrs = None
                            if isinstance(dimVal, dict):
                                dimVal = dimVal["value"]
                            elif dimVal is not None:
                                dimVal = str(dimVal) # may be int or boolean
                            if dimConcept.isExplicitDimension:
                                mem = qname(dimVal, namespaces)
                                if mem is None:
                                    error("oime:invalidDimensionValue",
                                          _("Fact %(factId)s taxonomy-defined explicit dimension value is invalid: %(memberQName)s."),
                                          modelObject=modelXbrl, factId=id, memberQName=dimVal)
                                    continue
                            elif dimConcept.isTypedDimension:
                                # a modelObject xml element is needed for all of the instance functions to manage the typed dim
                                if dimConcept.typedDomainElement.type is not None and dimConcept.typedDomainElement.type.localName == "complexType":
                                    error("oime:unsupportedDimensionDataType",
                                          _("Fact %(factId)s taxonomy-defined typed dimension value is complex: %(memberQName)s."),
                                          modelObject=modelXbrl, factId=id, memberQName=dimVal)
                                    continue
                                if (canonicalValuesFeature and dimVal is not None and 
                                    not CanonicalXmlTypePattern.get(dimConcept.typedDomainElement.baseXsdType, NoCanonicalPattern).match(dimVal)):
                                    error("xbrlje:nonCanonicalValue",
                                          _("Numeric typed dimension must have canonical %(type)s value \"%(value)s\": %(concept)s."),
                                          modelObject=modelXbrl, type=dimConcept.typedDomainElement.baseXsdType, concept=dimConcept, value=dimVal)
                                mem = addChild(modelXbrl.modelDocument, dimConcept.typedDomainElement.qname, text=dimVal, attributes=memberAttrs, appendChild=False)
                            else:
                                mem = None # absent typed dimension
                            if mem is not None:
                                qnameDims[dimQname] = DimValuePrototype(modelXbrl, None, dimQname, mem, "segment")
                    try:
                        _start, _sep, _end = period.rpartition('/')
                        if period == "forever":
                            startDateTime = endDateTime = None
                        elif _start == _end or not _start:
                            startDateTime = None
                            endDateTime = dateTime(_end, type=DATETIME)
                        else:
                            startDateTime = dateTime(_start, type=DATETIME)
                            endDateTime = dateTime(_end, type=DATETIME)
                        numFactCreationXbrlErrors -= len(modelXbrl.errors) # track any xbrl validation errors
                        prevErrLen = len(modelXbrl.errors)
                        _cntx = modelXbrl.createContext(
                                                entityAsQn.namespaceURI,
                                                entityAsQn.localName,
                                                _periodType,
                                                startDateTime,
                                                endDateTime,
                                                None, # no dimensional validity checking (like formula does)
                                                qnameDims, [], [],
                                                id=cntxId)
                        if len(modelXbrl.errors) > prevErrLen:
                            numFactCreationXbrlErrors += sum(err != "xmlSchema:valueError" for err in modelXbrl.errors[prevErrLen:])
                            if any(err == "xmlSchema:valueError" for err in modelXbrl.errors[prevErrLen:]):
                                error("oime:invalidDimensionValue",
                                      _("Fact %(factId)s taxonomy-defined dimension value errors noted above."),
                                      modelObject=modelXbrl, factId=id)
                                continue
                    except ValueError as err:
                        error("oimce:invalidPeriodRepresentation",
                              _("Invalid period for fact %(factId)s period %(period)s, %(error)s."),
                              modelObject=modelXbrl, factId=id, period=period, error=err)
                        continue
                    cntxTbl[cntxKey] = _cntx
                    if firstCntxUnitFactElt is None:
                        firstCntxUnitFactElt = _cntx
                unitKey = dimensions.get("unit")
                if concept.isNumeric:
                    if unitKey is not None:
                        if unitKey == "xbrli:pure":
                            error("oime:illegalPureUnit",
                                  _("Unit MUST NOT have single numerator measure xbrli:pure with no denominators."),
                                  modelObject=modelXbrl, unit=unitKey)
                    else:
                        unitKey = "xbrli:pure" # default unit
                        if "xbrli" not in namespaces:
                            namespaces["xbrli"] = XbrlConst.xbrli
                    if unitKey in unitTbl:
                        _unit = unitTbl[unitKey]
                    else:
                        _unit = None
                        # validate unit
                        unitKeySub = PrefixedQName.sub(UnitPrefixedQNameSubstitutionChar, unitKey)
                        if not UnitPattern.match(unitKeySub):
                            error("oimce:invalidUnitStringRepresentation",
                                  _("Unit string representation is lexically invalid, %(unit)s"),
                                  modelObject=modelXbrl, unit=unitKey)
                        else:
                            _mul, _sep, _div = unitKey.partition('/')
                            if _mul.startswith('('):
                                _mul = _mul[1:-1]
                            _muls = [u for u in _mul.split('*') if u]
                            if _div.startswith('('):
                                _div = _div[1:-1]
                            _divs = [u for u in _div.split('*') if u]
                            if _muls != sorted(_muls) or _divs != sorted(_divs):
                                error("oimce:invalidUnitStringRepresentation",
                                      _("Unit string representation measures are not in alphabetical order, %(unit)s"),
                                      modelObject=modelXbrl, unit=unitKey)
                            try:
                                mulQns = [qname(u, namespaces, prefixException=OIMException("oimce:unboundPrefix",
                                                                                          _("Unit prefix is not declared: %(unit)s"),
                                                                                          unit=u)) 
                                          for u in _muls]
                                divQns = [qname(u, namespaces, prefixException=OIMException("oimce:unboundPrefix",
                                                                                          _("Unit prefix is not declared: %(unit)s"),
                                                                                          unit=u))
                                          for u in _divs]
                                unitId = 'u-{:02}'.format(len(unitTbl) + 1)
                                for _measures in mulQns, divQns:
                                    for _measure in _measures:
                                        addQnameValue(modelXbrl.modelDocument, _measure)
                                _unit = modelXbrl.createUnit(mulQns, divQns, id=unitId)
                                if firstCntxUnitFactElt is None:
                                    firstCntxUnitFactElt = _unit
                            except OIMException as ex:
                                error(ex.code, ex.message, modelObject=modelXbrl, **ex.msgArgs)
                        unitTbl[unitKey] = _unit
                else:
                    _unit = None
                    if unitKey is not None and not isCSVorXL:
                        error("oime:misplacedUnitDimension",
                              _("The unit core dimension MUST NOT be present on non-numeric facts: %(concept)s, unit %(unit)s."),
                              modelObject=modelXbrl, concept=conceptSQName, unit=unitKey)
            
                attrs["contextRef"] = _cntx.id
        
                if fact.get("value") is None:
                    if not concept.isNillable:
                        error("oime:invalidFactValue",
                              _("Nil value applied to non-nillable concept: %(concept)s."),
                              modelObject=modelXbrl, concept=conceptSQName)
                        continue
                    attrs[XbrlConst.qnXsiNil] = "true"
                    text = None
                elif concept.isEnumeration2Item:
                    qnames = fact["value"].split(" ")
                    expandedNames = set()
                    if canonicalValuesFeature and not all(qnames[i] < qnames[i+1] for i in range(len(qnames)-1)):
                        error("xbrlje:nonCanonicalValue",
                              _("Enumeration item must be canonically ordered, %(value)s: %(concept)s."),
                              modelObject=modelXbrl, concept=conceptSQName, value=fact["value"])
                    isFactValid = True
                    for qn in qnames:
                        if not PrefixedQName.match(qn):
                            isFactValid = False
                        else:
                            _qname = qname(qn, namespaces)
                            if not _qname:
                                isFactValid = False
                            else:
                                expandedNames.add(_qname.expandedName)
                    if isFactValid:
                        text = " ".join(sorted(expandedNames))
                    else:
                        error("oime:invalidFactValue",
                              _("Enumeration item must be %(canonicalOrdered)slist of QNames: %(concept)s."),
                              modelObject=modelXbrl, concept=conceptSQName, canonicalOrdered="a canonical ordered " if canonicalValuesFeature else "")
                        continue
                else:
                    text = fact["value"]
                    if (canonicalValuesFeature and text is not None and 
                        not CanonicalXmlTypePattern.get(concept.baseXsdType, NoCanonicalPattern).match(text)):
                        error("xbrlje:nonCanonicalValue",
                              _("Item must have canonical %(type)s value \"%(value)s\": %(concept)s."),
                              modelObject=modelXbrl, type=concept.baseXsdType, concept=conceptSQName, value=text)
                    
                decimals = fact.get("decimals")
                if concept.isNumeric:
                    if isCSVorXL and isinstance(text, str): # don't check for suffix if not CSV/XL or None or int
                        text, _sep, _decimals = text.partition("d")
                        if _sep:
                            if decimalsSuffixPattern.match(_decimals):
                                decimals = _decimals
                            else:
                                error("xbrlce:invalidDecimalsValue", 
                                      _("Fact %(factId)s has invalid decimals \"%(decimals)s\""),
                                      modelObject=modelXbrl, factId=id, decimals=_sep+_decimals)
                    if _unit is None:
                        continue # skip creating fact because unit was invalid
                    attrs["unitRef"] = _unit.id
                    if text is not None: # no decimals for nil value
                        attrs["decimals"] = decimals if decimals is not None else "INF"
                elif decimals is not None and not isCSVorXL:
                    error("oime:misplacedDecimalsProperty",
                          _("The decimals property MUST NOT be present on non-numeric facts: %(concept)s, decimals %(decimals)s"),
                          modelObject=modelXbrl, concept=conceptSQName, decimals=decimals)
            else:
                text = None #tuple
                    
            attrs["id"] = id
            if "id" not in fact: # needed for footnote generation
                fact["id"] = id
                    
            # is value a QName?
            if concept.baseXbrliType == "QNameItemType": # renormalize prefix of instance fact
                text = addQnameValue(modelXbrl.modelDocument, qname(text.strip(), namespaces))
    
            prevErrLen = len(modelXbrl.errors) # track any xbrl validation errors
            f = modelXbrl.createFact(conceptQn, attributes=attrs, text=text, validate=False)
            if firstCntxUnitFactElt is None:
                firstCntxUnitFactElt = f
            
            xmlValidate(modelXbrl, f)
            if len(modelXbrl.errors) > prevErrLen:
                numFactCreationXbrlErrors += sum(err != "xmlSchema:valueError" for err in modelXbrl.errors[prevErrLen:])
                if any(err == "xmlSchema:valueError" for err in modelXbrl.errors[prevErrLen:]):
                    error("oime:invalidFactValue",
                          _("Fact %(factId)s value error noted above."),
                          modelObject=modelXbrl, factId=id)
            
        if isCSVorXL: # check report parameters used
            unmappedReportParams = reportParameters.keys() - reportParametersUsed
            if unmappedReportParams:
                error("xbrlce:unmappedReportParameter", 
                      _("Report unmapped parameters %(parameters)s"),
                      parameters=", ".join(sorted(unmappedReportParams)))

                    
        currentAction = "creating footnotes"
        footnoteLinks = OrderedDict() # ELR elements
        factLocs = {} # index by (linkrole, factId)
        footnoteLinkNotes = defaultdict(set) # linkrole: noteIds
        # footnoteNbr = 0
        locNbr = 0
        definedInstanceRoles = set()
        undefinedFootnoteTypes = set()
        undefinedFootnoteGroups = set()
        undefinedLinkTargets = set()
        footnotesIdTargets = set()
        for factOrFootnote in footnotes:
            if isJSON:
                for ftGroups in factOrFootnote.get("links", {}).values():
                    for ftTgtIds in ftGroups.values():
                        for tgtId in ftTgtIds:
                            if tgtId in xbrlNoteTbl:
                                footnotesIdTargets.add(tgtId)
            elif isCSVorXL: # footnotes contains footnote objects
                for ftGroups in factOrFootnote.values():
                    for ftSrcIdTgtIds in ftGroups.values():
                        for ftTgtIds in ftSrcIdTgtIds.values():
                            for tgtId in ftTgtIds:
                                footnotesIdTargets.add(tgtId)
        for factOrFootnote in footnotes:
            if isJSON:
                factFootnotes = []
                for ftType, ftGroups in factOrFootnote.get("links", {}).items():
                    ftSrcId = factOrFootnote.get("id")
                    if ftSrcId is None:
                        ftSrcId = factOrFootnote.get("dimensions",EMPTY_DICT).get("noteId")
                    if ftType not in linkTypes:
                        undefinedFootnoteTypes.add(ftType)
                    else:
                        for ftGroup, ftTgtIds in ftGroups.items():
                            if ftGroup not in linkGroups:
                                undefinedFootnoteGroups.add(ftGroup)
                            else:
                                footnote = {"id": ftSrcId,
                                            "footnoteGroup": linkGroups[ftGroup],
                                            "footnoteType": linkTypes[ftType]}
                                for tgtId in ftTgtIds:
                                    if tgtId in xbrlNoteTbl:
                                        footnote.setdefault("noteRefs", []).append(tgtId)
                                    elif tgtId in modelXbrl.modelDocument.idObjects:
                                        footnote.setdefault("factRefs", []).append(tgtId)
                                    else:
                                        undefinedLinkTargets.add(tgtId)
                                factFootnotes.append(footnote)
            elif isCSVorXL: # footnotes contains footnote objects
                factFootnotes = []
                for ftType, ftGroups in factOrFootnote.items():
                    if ftType not in linkTypes:
                        undefinedFootnoteTypes.add(ftType)
                    else:
                        for ftGroup, ftSrcIdTgtIds in ftGroups.items():
                            if ftGroup not in linkGroups:
                                undefinedFootnoteGroups.add(ftGroup)
                            else:
                                for ftSrcId, ftTgtIds in ftSrcIdTgtIds.items():
                                    footnote = {"id": ftSrcId,
                                                "footnoteGroup": linkGroups[ftGroup],
                                                "footnoteType": linkTypes[ftType]}
                                    for tgtId in ftTgtIds:
                                        if tgtId in factItems:
                                            footnote.setdefault("noteRefs" if tgtId in xbrlNoteTbl else "factRefs", []).append(tgtId)
                                        else:
                                            undefinedLinkTargets.add(tgtId)
                                    factFootnotes.append(footnote)
            for footnote in factFootnotes:
                factId = footnote["id"]
                linkrole = footnote["footnoteGroup"]
                arcrole = footnote["footnoteType"]
                skipThisFootnote = False
                if not factId or not linkrole or not arcrole or not (
                    footnote.get("factRefs") or footnote.get("footnote") is not None or footnote.get("noteRefs") is not None):
                    if not linkrole:
                        warning("xbrlje:unknownLinkGroup",
                                        _("FootnoteId has no linkrole %(footnoteId)s."),
                                        modelObject=modelXbrl, footnoteId=footnote.get("footnoteId"))
                    if not arcrole:
                        warning("xbrlje:unknownLinkType",
                                        _("FootnoteId has no arcrole %(footnoteId)s."),
                                        modelObject=modelXbrl, footnoteId=footnote.get("footnoteId"))
                    continue
                for refType, refValue, roleTypes in (("role", linkrole, modelXbrl.roleTypes),
                                                     ("arcrole", arcrole, modelXbrl.arcroleTypes)):
                    if not (XbrlConst.isStandardRole(refValue) or XbrlConst.isStandardArcrole(refValue)):
                        if refValue not in definedInstanceRoles:
                            if refValue in roleTypes:
                                definedInstanceRoles.add(refValue)
                                hrefElt = roleTypes[refValue][0]
                                href = hrefElt.modelDocument.uri + "#" + hrefElt.id
                                elt = addChild(modelXbrl.modelDocument.xmlRootElement, 
                                               qname(link, refType+"Ref"), 
                                               attributes=(("{http://www.w3.org/1999/xlink}href", href),
                                                           ("{http://www.w3.org/1999/xlink}type", "simple")),
                                               beforeSibling=firstCntxUnitFactElt)
                                href = modelXbrl.modelDocument.discoverHref(elt)
                                if href:
                                    _elt, hrefDoc, hrefId = href
                                    _defElt = hrefDoc.idObjects.get(hrefId)
                                    if _defElt is not None:
                                        _uriAttrName = refType + "URI"
                                        _uriAttrValue = _defElt.get(_uriAttrName)
                                        if _uriAttrValue:
                                            elt.set(_uriAttrName, _uriAttrValue)
                            else:
                                error("xbrlxe:nonStandardRoleDefinitionNotInDTS",
                                      _("Footnote %(sourceId)s %(roleType)s %(role)s not defined in DTS"),
                                      modelObject=modelXbrl, sourceId=factId, roleType=refType, role=refValue)
                                skipThisFootnote = True
                if skipThisFootnote:
                    continue
                if linkrole not in footnoteLinks:
                    footnoteLinks[linkrole] = addChild(modelXbrl.modelDocument.xmlRootElement, 
                                                       XbrlConst.qnLinkFootnoteLink, 
                                                       attributes={"{http://www.w3.org/1999/xlink}type": "extended",
                                                                   "{http://www.w3.org/1999/xlink}role": linkrole})
                footnoteLink = footnoteLinks[linkrole]
                factIDs = (factId,)
                if factId in xbrlNoteTbl: # factId is a note, not a fact
                    fromLabel = "f_{}".format(factId)
                    factLocs[(linkrole, factIDs)] = fromLabel
                elif (linkrole, factIDs) not in factLocs:
                    locNbr += 1
                    locLabel = "l_{:02}".format(locNbr)
                    factLocs[(linkrole, factIDs)] = locLabel
                    addChild(footnoteLink, XbrlConst.qnLinkLoc, 
                             attributes={XLINKTYPE: "locator",
                                         XLINKHREF: "#" + factId,
                                         XLINKLABEL: locLabel})
                locFromLabel = factLocs[(linkrole, factIDs)]
                if "noteRefs" in footnote:
                    # footnoteNbr += 1
                    # footnoteToLabel = "f_{:02}".format(footnoteNbr)
                    for noteId in footnote.get("noteRefs"):
                        footnoteToLabel = "f_{}".format(noteId)
                        noteFactIDsNotReferenced.discard(noteId)
                        if noteId not in footnoteLinkNotes[linkrole]:
                            footnoteLinkNotes[linkrole].add(noteId)
                            xbrlNote = xbrlNoteTbl[noteId]
                            attrs = {XLINKTYPE: "resource",
                                     XLINKLABEL: footnoteToLabel,
                                     "id": idDeduped(modelXbrl, noteId),
                                     "oimNoteId": noteId
                                     }
                            #if noteId in footnotesIdTargets: # footnote resource is target of another footnote loc
                            #    attrs["id"] = noteId
                            try:
                                if "dimensions" in xbrlNote:
                                    attrs[XMLLANG] = xbrlNote["dimensions"]["language"]
                                elif "aspects" in xbrlNote:
                                    attrs[XMLLANG] = xbrlNote["aspects"]["language"]
                            except KeyError:
                                pass
                            tgtElt = addChild(footnoteLink, XbrlConst.qnLinkFootnote, attributes=attrs)
                            srcElt = etree.fromstring("<footnote xmlns=\"http://www.w3.org/1999/xhtml\">{}</footnote>"
                                                      .format(xbrlNote["value"]), parser=modelXbrl.modelDocument.parser)
                            if srcElt.__len__() > 0: # has html children
                                setXmlns(modelXbrl.modelDocument, "xhtml", "http://www.w3.org/1999/xhtml")
                            copyIxFootnoteHtml(srcElt, tgtElt, withText=True, isContinChainElt=False)
                        footnoteArc = addChild(footnoteLink, 
                                               XbrlConst.qnLinkFootnoteArc, 
                                               attributes={XLINKTYPE: "arc",
                                                           XLINKARCROLE: arcrole,
                                                           XLINKFROM: locFromLabel,
                                                           XLINKTO: footnoteToLabel})
                if "factRefs" in footnote:
                    factRef = footnote.get("factRefs")
                    fact2IDs = tuple(sorted(factRef))
                    if (linkrole, fact2IDs) not in factLocs:
                        locNbr += 1
                        locLabel = "l_{:02}".format(locNbr)
                        factLocs[(linkrole, fact2IDs)] = locLabel
                        for factId in fact2IDs:
                            addChild(footnoteLink, XbrlConst.qnLinkLoc, 
                                     attributes={XLINKTYPE: "locator",
                                                 XLINKHREF: "#" + factId,
                                                 XLINKLABEL: locLabel})
                    footnoteToLabel = factLocs[(linkrole, fact2IDs)]
                    footnoteArc = addChild(footnoteLink, 
                                           XbrlConst.qnLinkFootnoteArc, 
                                           attributes={XLINKTYPE: "arc",
                                                       XLINKARCROLE: arcrole,
                                                       XLINKFROM: locFromLabel,
                                                       XLINKTO: footnoteToLabel})
                    if arcrole == factFootnote:
                        error("oime:illegalStandardFootnoteTarget",
                              _("Standard footnote %(sourceId)s targets must be an xbrl:note, targets %(targetIds)s."),
                              modelObject=modelXbrl, sourceId=factId, targetIds=", ".join(fact2IDs))
        if noteFactIDsNotReferenced:
            error("oime:unusedNoteFact",
                    _("Note facts MUST be referenced by at least one link group, IDs: %(noteFactIds)s."),
                    modelObject=modelXbrl, noteFactIds=", ".join(sorted(noteFactIDsNotReferenced)))
        if footnoteLinks:
            modelXbrl.modelDocument.linkbaseDiscover(footnoteLinks.values(), inInstance=True)
            
        if undefinedLinkTargets:
            error("xbrlje:unknownLinkTarget",
                  _("These link targets are not defined in facts: %(ftTargets)s."),
                  modelObject=modelXbrl, ftTargets=", ".join(sorted(undefinedLinkTargets)))
        if undefinedFootnoteTypes:
            error("xbrlje:unknownLinkType",
                  _("These footnote types are not defined in footnoteTypes: %(ftTypes)s."),
                  modelObject=modelXbrl, ftTypes=", ".join(sorted(undefinedFootnoteTypes)))
        if undefinedFootnoteGroups:
            error("xbrlje:unknownLinkGroup",
                  _("These footnote groups are not defined in footnoteGroups: %(ftGroups)s."),
                  modelObject=modelXbrl, ftGroups=", ".join(sorted(undefinedFootnoteGroups)))
            
        checkForDuplicates(modelXbrl, allowedDuplicatesFeature, footnotesIdTargets)
                    
        currentAction = "done loading facts and footnotes"
        
        if numFactCreationXbrlErrors:
            error("oime:invalidXBRL",
                  _("%(count)s XBRL errors noted above."),
                  modelObject=modelXbrl, count=numFactCreationXbrlErrors)
            
        
        #cntlr.addToLog("Completed in {0:.2} secs".format(time.time() - startedAt),
        #               messageCode="loadFromExcel:info")
    except NotOIMException as ex:
        _return = ex # not an OIM document
    except Exception as ex:
        _return = ex
        if isinstance(ex, OIMException):
            if ex.code and ex.message:
                error(ex.code, ex.message, modelObject=modelXbrl, **ex.msgArgs)
        else:
            error("arelleOIMloader:error",
                    "Error while %(action)s, error %(error)s\n traceback %(traceback)s",
                    modelObject=modelXbrl, action=currentAction, error=ex,
                    traceback=traceback.format_tb(sys.exc_info()[2]))
    
    global lastFilePath, lastFilePath
    lastFilePath = None
    lastFilePathIsOIM = False
    return _return

lastFilePath = None
lastFilePathIsOIM = False

def isOimLoadable(modelXbrl, mappedUri, normalizedUri, filepath, **kwargs):
    global lastFilePath, lastFilePathIsOIM
    lastFilePath = filepath
    lastFilePathIsOIM = False
    _ext = os.path.splitext(filepath)[1]
    if _ext in (".csv", ".json", ".xlsx", ".xls"):
        lastFilePathIsOIM = True
    elif isHttpUrl(normalizedUri) and '?' in _ext: # query parameters and not .json, may be JSON anyway
        with io.open(filepath, 'rt', encoding='utf-8') as f:
            _fileStart = f.read(4096)
        if _fileStart and re_match(r"\s*\{\s*\"documentType\":\s*\"http:\\+/\\+/www.xbrl.org\\+/WGWD\\+/YYYY-MM-DD\\+/xbrl-json\"", _fileStart):
            lastFilePathIsOIM = True
    return lastFilePathIsOIM

def oimLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    if filepath != lastFilePath or not lastFilePathIsOIM:
        return None # not an OIM file

    cntlr = modelXbrl.modelManager.cntlr
    cntlr.showStatus(_("Loading OIM file: {0}").format(os.path.basename(filepath)))
    doc = loadFromOIM(cntlr, modelXbrl.error, modelXbrl.warning, modelXbrl, filepath, mappedUri)
    if doc is None:
        return None # not an OIM file
    modelXbrl.loadedFromOIM = True
    modelXbrl.loadedFromOimErrorCount = len(modelXbrl.errors)
    return doc

def guiXbrlLoaded(cntlr, modelXbrl, attach, *args, **kwargs):
    if cntlr.hasGui and getattr(modelXbrl, "loadedFromOIM", False):
        from arelle import ModelDocument
        from tkinter.filedialog import askdirectory
        instanceFile = cntlr.uiFileDialog("save",
                title=_("arelle - Save XBRL instance document"),
                initialdir=cntlr.config.setdefault("outputInstanceDir","."),
                filetypes=[(_("XBRL file .xbrl"), "*.xbrl"), (_("XBRL file .xml"), "*.xml")],
                defaultextension=".xbrl")
        if not instanceFile:
            return False
        cntlr.config["outputInstanceDir"] = os.path.dirname(instanceFile)
        cntlr.saveConfig()
        if instanceFile:
            modelXbrl.modelDocument.save(instanceFile, updateFileHistory=False)
            cntlr.showStatus(_("Saving XBRL instance: {0}").format(os.path.basename(instanceFile)))
        cntlr.showStatus(_("OIM loading completed"), 3500)

def cmdLineXbrlLoaded(cntlr, options, modelXbrl, *args, **kwargs):
    if options.saveOIMinstance and getattr(modelXbrl, "loadedFromOIM", False):
        doc = modelXbrl.modelDocument
        cntlr.showStatus(_("Saving XBRL instance: {0}").format(doc.basename))
        responseZipStream = kwargs.get("responseZipStream")
        if responseZipStream is not None:
            _zip = zipfile.ZipFile(responseZipStream, "a", zipfile.ZIP_DEFLATED, True)
        else:
            _zip = None
        doc.save(options.saveOIMinstance, _zip)
        if responseZipStream is not None:
            _zip.close()
            responseZipStream.seek(0)
            
def validateFinally(val, *args, **kwargs):
    modelXbrl = val.modelXbrl
    if getattr(modelXbrl, "loadedFromOIM", False):
        if modelXbrl.loadedFromOimErrorCount < len(modelXbrl.errors):
            modelXbrl.error("oime:invalidXBRL",
                                _("XBRL validation errors were logged for this instance."),
                                modelObject=modelXbrl)
    else:
        # validate xBRL-XML instances
        dimContainers = set(rel.contextElement for rel in modelXbrl.relationshipSet((hc_all, hc_notAll)).modelRelationships)
        if len(dimContainers) > 1:
            modelXbrl.error("xbrlxe:inconsistentDimensionsContainer",
                            _("All hypercubes within the DTS of a report MUST be defined for use on the same container (either \"segment\" or \"scenario\")"),
                            modelObject=modelXbrl)
        contextsWithNonDimContent = set()
        contextsWithNonDimContainer = set()
        contextsWithComplexTypedDimensions = set()
        containersNotUsedForDimensions = {"segment", "scenario"} - dimContainers
        for context in modelXbrl.contexts.values():
            if context.nonDimValues("segment"):
                contextsWithNonDimContent.add(context)
                if "segment" in containersNotUsedForDimensions:
                    contextsWithNonDimContainer.add(context)
            if context.nonDimValues("scenario"):
                contextsWithNonDimContent.add(context)
                if "scenario" in containersNotUsedForDimensions:
                    contextsWithNonDimContainer.add(context)
            if context.dimValues("segment") and "segment" in containersNotUsedForDimensions:
                contextsWithNonDimContainer.add(context)
            if context.dimValues("scenario") and "scenario" in containersNotUsedForDimensions:
                contextsWithNonDimContainer.add(context)
            for modelDimension in context.qnameDims.values():
                if modelDimension.isTyped:
                    typedMember = modelDimension.typedMember
                    if isinstance(typedMember, ModelObject):
                        modelConcept = modelXbrl.qnameConcepts.get(typedMember.qname)
                        if modelConcept is not None and modelConcept.type is not None and modelConcept.type.localName == "complexType":
                            contextsWithComplexTypedDimensions.add(context)
        if contextsWithNonDimContent:
            modelXbrl.error("xbrlxe:nonDimensionalSegmentScenarioContent",
                            _("Contexts MUST not contain non-dimensional content: %(contexts)s"),
                            modelObject=contextsWithNonDimContent, 
                            contexts=", ".join(sorted(c.id for c in contextsWithNonDimContent)))
        if contextsWithNonDimContainer:
            modelXbrl.error("xbrlxe:unexpectedContextContent",
                            _("Contexts not used for dimensions must not contain content in %(containers)s: %(contexts)s"),
                            modelObject=contextsWithNonDimContainer, 
                            containers=" or ".join(sorted(containersNotUsedForDimensions)),
                            contexts=", ".join(sorted(c.id for c in contextsWithNonDimContainer)))
        if contextsWithComplexTypedDimensions:
            modelXbrl.error("oime:unsupportedDimensionDataType", # was: "xbrlxe:unsupportedComplexTypedDimension",
                            _("Instance has contexts with complex typed dimensions: %(contexts)s"),
                            modelObject=contextsWithNonDimContainer, 
                            contexts=", ".join(sorted(c.id for c in contextsWithComplexTypedDimensions)))
          
        unsupportedDataTypeFacts = []
        tupleFacts = [] 
        precisionZeroFacts = []     
        for f in modelXbrl.factsInInstance: # facts in document order (no sorting required for messages)
            concept = f.concept
            if concept is not None:
                if concept.isFraction:
                    unsupportedDataTypeFacts.append(f)
                if concept.isTuple:
                    tupleFacts.append(f)
                if concept.isNumeric and f.precision is not None and precisionZeroPattern.match(f.precision):
                    precisionZeroFacts.append(f)
        if unsupportedDataTypeFacts:
            modelXbrl.error("xbrlxe:unsupportedConceptDataType",
                            _("Instance has %(count)s fraction facts"),
                            modelObject=unsupportedDataTypeFacts, count=len(unsupportedDataTypeFacts))
        if tupleFacts:
            modelXbrl.error("xbrlxe:unsupportedTuple",
                            _("Instance has %(count)s tuple facts"),
                            modelObject=tupleFacts, count=len(tupleFacts))
        if precisionZeroFacts:
            modelXbrl.error("xbrlxe:unsupportedZeroPrecisionFact",
                            _("Instance has %(count)s precision zero facts"),
                            modelObject=precisionZeroFacts, count=len(precisionZeroFacts))
 
        footnoteRels = modelXbrl.relationshipSet("XBRL-footnotes")
        # ext group and link roles
        unsupportedExtRoleRefs = defaultdict(list) # role/arcrole and footnote relationship objects referencing it
        footnoteELRs = set()
        footnoteArcroles = set()
        roleDefiningDocs = defaultdict(set)
        def docInSchemaRefedDTS(thisdoc, roleTypeDoc, visited=None):
            if visited is None:
                visited = set()
            visited.add(thisdoc)
            for doc, docRef in thisdoc.referencesDocument.items():
                if not (docRef.referenceType in ("roleType", "arcroleType") and thisdoc.type == Type.INSTANCE):
                    if doc == roleTypeDoc or (doc not in visited and docInSchemaRefedDTS(doc, roleTypeDoc, visited)):
                        return True
            visited.remove(thisdoc)
            return False
        for rel in footnoteRels.modelRelationships:
            if not isStandardRole(rel.linkrole):
                footnoteELRs.add(rel.linkrole)
            if rel.arcrole != factFootnote:
                footnoteArcroles.add(rel.arcrole)
        for elr in footnoteELRs:
            for roleType in modelXbrl.roleTypes[elr]:
                roleDefiningDocs[elr].add(roleType.modelDocument)
        for arcrole in footnoteArcroles:
            for arcroleType in modelXbrl.arcroleTypes[arcrole]:
                roleDefiningDocs[arcrole].add(arcroleType.modelDocument)
        extRoles = set(role
                      for role, doc in roleDefiningDocs.items()
                      if not docInSchemaRefedDTS(modelXbrl.modelDocument, doc))
        if extRoles:
            modelXbrl.error("xbrlxe:unsupportedExternalRoleRef",
                            _("Role and arcrole definitions MUST be in standard or schemaRef discoverable sources"),
                            modelObject=modelXbrl, roles=", ".join(sorted(extRoles)))
        
        # todo: multi-document inline instances
        for elt in modelXbrl.modelDocument.xmlRootElement.iter("{http://www.xbrl.org/2003/linkbase}footnote", "{http://www.xbrl.org/2013/inlineXBRL}footnote"):
            if isinstance(elt, ModelResource) and getattr(elt, "xValid", 0) >= VALID:
                if not footnoteRels.toModelObject(elt):
                    modelXbrl.error("xbrlxe:unlinkedFootnoteResource",
                                    _("Unlinked footnote element %(label)s: %(value)s"),
                                    modelObject=elt, label=elt.xlinkLabel, value=elt.xValue[:100])
                if elt.role not in (None, "", footnote):
                    modelXbrl.error("xbrlxe:nonStandardFootnoteResourceRole",
                                    _("Footnotes MUST have standard footnote resource role, %(role)s is disallowed, %(label)s: %(value)s"),
                                    modelObject=elt, role=elt.role, label=elt.xlinkLabel, value=elt.xValue[:100])
        # xml base on anything
        for elt in modelXbrl.modelDocument.xmlRootElement.getroottree().iterfind("//{*}*[@{http://www.w3.org/XML/1998/namespace}base]"):
            modelXbrl.error("xbrlxe:unsupportedXmlBase",
                            _("Instance MUST NOT contain xml:base attributes: element %(qname)s, xml:base %(base)s"),
                            modelObject=elt, qname=elt.qname if isinstance(elt, ModelObject) else elt.tag, 
                            base=elt.get("{http://www.w3.org/XML/1998/namespace}base"))
        # todo: multi-document inline instances 
        if modelXbrl.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET):
            for doc in modelXbrl.modelDocument.referencesDocument.keys():
                if doc.type == Type.LINKBASE:
                    val.modelXbrl.error("xbrlxe:unsupportedLinkbaseReference",
                                        _("Linkbase reference not allowed from instance document."),
                                        modelObject=(modelXbrl.modelDocument,doc))

def excelLoaderOptionExtender(parser, *args, **kwargs):
    parser.add_option("--saveOIMinstance", 
                      action="store", 
                      dest="saveOIMinstance", 
                      help=_("Save a instance loaded from OIM into this file name."))
    
__pluginInfo__ = {
    'name': 'Load From OIM',
    'version': '1.2',
    'description': "This plug-in loads XBRL instance data from OIM (JSON, CSV or Excel) and saves the resulting XBRL Instance.",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2016 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'ModelDocument.IsPullLoadable': isOimLoadable,
    'ModelDocument.PullLoader': oimLoader,
    'CntlrWinMain.Xbrl.Loaded': guiXbrlLoaded,
    'CntlrCmdLine.Options': excelLoaderOptionExtender,
    'CntlrCmdLine.Xbrl.Loaded': cmdLineXbrlLoaded,
    'Validate.XBRL.Finally': validateFinally
}
