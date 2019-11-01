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
import os, sys, io, time, re, traceback, json, csv, logging, math, zipfile, datetime, isodate
from lxml import etree
from collections import defaultdict, OrderedDict
from arelle.ModelDocument import Type, create as createModelDocument
from arelle import XbrlConst, ModelDocument, ModelXbrl, PackageManager, ValidateXbrlDimensions
from arelle.ModelDocument import Type, create as createModelDocument
from arelle.ModelValue import qname, dateTime, DATETIME, yearMonthDuration, dayTimeDuration
from arelle.PrototypeInstanceObject import DimValuePrototype
from arelle.PythonUtil import attrdict
from arelle.UrlUtil import isHttpUrl
from arelle.XbrlConst import (qnLinkLabel, standardLabelRoles, qnLinkReference, standardReferenceRoles,
                              qnLinkPart, gen, link, defaultLinkRole,
                              conceptLabel, elementLabel, conceptReference
                              )
from arelle.XmlUtil import addChild, addQnameValue, copyIxFootnoteHtml, setXmlns
from arelle.XmlValidate import NCNamePattern, validate as xmlValidate

nsOim = "http://www.xbrl.org/CR/2018-12-12"
nsOims = (nsOim,
          "http://www.xbrl.org/WGWD/YYYY-MM-DD",
          "http://www.xbrl.org/PWD/2016-01-13/oim",
          "http://www.xbrl.org/WGWD/YYYY-MM-DD/oim",
          "http://www.xbrl.org/CR/2019-06-12"
         )
nsOimCes = (
        "http://www.xbrl.org/WGWD/YYYY-MM-DD/oim-common/error",
    )
jsonDocumentTypes = (
        "http://www.xbrl.org/WGWD/YYYY-MM-DD/xbrl-json",
        "http://www.xbrl.org/CR/2019-06-12/xbrl-json",
    )
csvDocumentTypes = (
        "http://www.xbrl.org/WGWD/YYYY-MM-DD/xbrl-csv",
        "http://xbrl.org/YYYY/xbrl-csv",
        "http://www.xbrl.org/{{status_date_uri}}/xbrl-csv", # allows loading of XII "template" test cases without CI production
        "http://www.xbrl.org/CR/2019-10-19/xbrl-csv"
    )
csvDocinfoObjects = {"documentType", "reportDimensions", "namespaces", "taxonomy", "decimals", "extends", "final"}
csvExtensibleObjects = {"namespaces", "linkTypes", "linkGroups", "tableTemplates", "tables", "reportDimensions", "final"}

         
reservedLinkTypes = {
        "footnote":         "http://www.xbrl.org/2003/arcrole/fact-footnote",
        "explanatoryFact":  "http://www.xbrl.org/2009/arcrole/fact-explanatoryFact"
    }
reservedLinkGroups = {
        "defaultGroup":     "http://www.xbrl.org/2003/role/link"
    }


XLINKTYPE = "{http://www.w3.org/1999/xlink}type"
XLINKLABEL = "{http://www.w3.org/1999/xlink}label"
XLINKARCROLE = "{http://www.w3.org/1999/xlink}arcrole"
XLINKFROM = "{http://www.w3.org/1999/xlink}from"
XLINKTO = "{http://www.w3.org/1999/xlink}to"
XLINKHREF = "{http://www.w3.org/1999/xlink}href"
XMLLANG = "{http://www.w3.org/XML/1998/namespace}lang"

JSONdocumentType = "http://www.xbrl.org/WGWD/YYYY-MM-DD/xbrl-json"

OIMReservedAliasURIs = {
    "xbrl": nsOims,
    "xsd": (XbrlConst.xsd,),
    "enum2": XbrlConst.enum2s,
    "oimce": nsOimCes,
    "xbrli": (XbrlConst.xbrli,),
    "xsd": (XbrlConst.xsd,),
    "xbrlje": [ns + "/xbrl-json/error" for ns in nsOims]
    }
OIMReservedURIAlias = dict(
    (uri, alias)
    for alias, uris in OIMReservedAliasURIs.items()
    for uri in uris)

ENTITY_NA_QNAME = qname("https://xbrl.org/entities", "NA")
EMPTY_DICT = {}
EMPTY_LIST = []

DUPJSONKEY = "!@%duplicateKeys%@!"
DUPJSONVALUE = "!@%duplicateValues%@!"

JSONmetadataPattern = re.compile(r"\s*\{.*\"documentInfo\"\s*:.*\}", re.DOTALL)
IdentifierPattern = re.compile(
                 "[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                  r"[_\-" 
                  "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*")

PrefixedQName = re.compile(
                 "[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                  r"[_\-\." 
                  "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*:"
                 "[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                  r"[_\-\." 
                  "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*")
UnitPrefixedQNameSubstitutionChar = "\x07" # replaces PrefixedQName in unit pattern
UnitPattern = re.compile(
                # QNames are replaced by \x07 in these expressions
                # numerator only (no parentheses)
                "(^\x07$)|(^\x07([*]\x07)+$)|"
                # numerator and optional denominator, with parentheses if more than one term in either
                "(^((\x07)|([(]\x07([*]\x07)+[)]))([/]((\x07)|([(]\x07([*]\x07)+[)])))?$)"
                )

xlUnicodePattern = re.compile("_x([0-9A-F]{4})_")

JsonTypes = {
    "columns": dict,
    "columnDimensions": dict,
    "decimals": (int,str), # can be a number of string column/parameter ref
    "documentInfo": dict,
    "documentType": str,
    "facts": dict, 
    "links": dict, 
    "optional": bool,
    "reportParameters": dict,
    "rowIdColumn": str,
    "tables": dict, 
    "tableDimensions": dict,
    "tableParameters": dict,
    "tableTemplates": dict,
    "taxonomy": list,
    "template": str,
    "transposed": bool,
    "url": str
    }

def jsonGet(tbl, key, default=None):
    if isinstance(tbl, dict):
        v = tbl.get(key)
        if isinstance(v, JsonTypes.get(key,())):
            return v
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
    return csvCellValue(v)

class OIMException(Exception):
    def __init__(self, code, message, **kwargs):
        self.code = code
        self.message = message
        self.msgArgs = kwargs
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception {1}').format(self.code, self.message % self.msgArgs)

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
    
periodForms = ((PER_ISO, re.compile("([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})?)$")),
               (PER_INCLUSIVE_DATES, re.compile("([0-9]{4}-[0-9]{2}-[0-9]{2})[.][.]([0-9]{4}-[0-9]{2}-[0-9]{2})$")),
               (PER_SINGLE_DAY, re.compile("([0-9]{4})-([0-9]{2})-([0-9]{2})$")),
               (PER_MONTH,  re.compile("([0-9]{4})-([0-9]{2})$")),
               (PER_YEAR, re.compile("([0-9]{4})$")),
               (PER_QTR, re.compile("([0-9]{4})Q([1-4])$")),
               (PER_HALF, re.compile("([0-9]{4})H([1-2])$")),
               (PER_WEEK, re.compile("([0-9]{4}W[1-5]?[0-9])$")))
def csvPeriod(cellValue, startOrEnd):
    if cellValue in ("", "#none"):
        return None
    isoDuration = None
    for perType, perFormMatch in periodForms:
        m = perFormMatch.match(cellValue)
        if m:
            try:
                if perType == PER_ISO:
                    return cellValue
                elif perType == PER_INCLUSIVE_DATES:
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(dateTime(m.group(1)), dateTime(m.group(2)) + ONE_DAY)
                elif perType == PER_SINGLE_DAY:
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(dateTime(m.group(1)), dateTime(m.group(1)) + ONE_DAY)
                elif perType == PER_MONTH:
                    moStart = dateTime(m.group(1) + "-00")
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(moStart, moStart + ONE_MONTH)
                elif perType == PER_YEAR:
                    yrStart = dateTime(m.group(1) + "-00-00")
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(yrStart, yrStart + ONE_YEAR)
                elif perType == PER_QTR:
                    qtrStart = dateTime(m.group(1) + "-{:02}-00".format(int(m.group(2))*3 - 3))
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(qtrStart, qtrStart + ONE_QTR)
                elif perType == PER_HALF:
                    qtrStart = dateTime(m.group(1) + "-{:02}-00".format(int(m.group(2))*6 - 6))
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(qtrStart, qtrStart + ONE_HALF)
                elif perType == PER_WEEK:
                    weekStart = dateTime(isodate.parse_date(m.group(1)))
                    isoDuration = "{}T00:00:00/{}T00:00:00".format(weekStart, qtrStart + datetime.timedelta(7))
            except ValueError:
                return None
        if isoDuration:
            if startOrEnd == "start":
                return isoDuration.partition("/")[0]
            elif startOrEnd == "end":
                return isoDuration.partition("/")[2]
            return isoDuration
    return None
    
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
        def loadDict(keyValuePairs):
            _dict = OrderedDict() # preserve fact order in resulting instance
            _valueKeyDict = {}
            for key, value in keyValuePairs:
                if isinstance(value, dict):
                    if DUPJSONKEY in value:
                        for _errKey, _errValue, _otherValue in value[DUPJSONKEY]:
                            if key in ("namespaces", "linkTypes", "linkGroups"):
                                error("oimce:multipleURIsForAlias",
                                                _("The %(map)s alias %(prefix)s is used on uri %(uri1)s and uri %(uri2)s"),
                                                modelObject=modelXbrl, map=key, prefix=_errKey, uri1=_errValue, uri2=_otherValue)
                            else:
                                error("xbrlje:invalidJSONStructure",
                                                _("The %(obj)s key %(key)s is used on multiple objects"),
                                                modelObject=modelXbrl, obj=key, key=_errKey)
                        del value[DUPJSONKEY]
                    if DUPJSONVALUE in value:
                        for _errValue, _errKey, _otherKey in value[DUPJSONVALUE]:
                            if key in ("namespaces", "linkTypes", "linkGroups"):
                                error("oimce:multipleAliasesForURI",
                                                _("The %(map)s value %(uri)s is used on alias %(alias1)s and alias %(alias2)s"),
                                                modelObject=modelXbrl, map=key, uri=_errValue, alias1=_errKey, alias2=_otherKey)
                        del value[DUPJSONVALUE]
                    if key in ("namespaces", "linkTypes", "linkGroups"):
                        for _key, _value in value.items():
                            if _key == "":
                                error("oimce:invalidEmptyURIAlias",
                                                _("The %(map)s empty string MUST NOT be used as a URI alias: uri %(uri)s"),
                                                modelObject=modelXbrl, map=key, prefix="", uri=_value)
                            elif key == "namespaces" and _key in OIMReservedAliasURIs and _value not in OIMReservedAliasURIs[_key]:
                                error("oimce:invalidURIForReservedAlias",
                                                _("The namespaces URI %(uri)s is used on standard alias %(alias)s which requires URI %(standardUri)s"),
                                                modelObject=modelXbrl, alias=_key, uri=_value, standardUri=OIMReservedAliaseURIs[_key][0])
                            elif key == "namespaces" and _value in OIMReservedURIAlias and _key != OIMReservedURIAlias[_value]:
                                error("oimce:invalidPrefixForURIWithReservedAlias",
                                                _("The namespaces URI %(uri)s is bound to alias %(key)s instead of standard alias %(alias)s"),
                                                modelObject=modelXbrl, key=_key, uri=_value, alias=OIMReservedURIAlias[_value])
                if key in _dict:
                    if DUPJSONKEY not in _dict:
                        _dict[DUPJSONKEY] = []
                    _dict[DUPJSONKEY].append((key, value, _dict[key]))
                elif isinstance(value, str) and value in _valueKeyDict:
                    if DUPJSONVALUE not in _dict:
                        _dict[DUPJSONVALUE] = []
                    _dict[DUPJSONVALUE].append((value, key, _valueKeyDict[value]))
                else:
                    _dict[key] = value
                    if isinstance(value, str):
                        _valueKeyDict[value] = key
            return _dict
        
        def loadOimObject(oimFile, extendingFile): # returns oimObject, oimWb
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
            if not isXL:
                _file, encoding = modelXbrl.fileSource.file(filepath, encoding='utf-8')
                with _file as f:
                    oimObject = json.load(f, object_pairs_hook=loadDict)
                # check for top-level key duplicates
                if isinstance(oimObject, dict) and DUPJSONKEY in oimObject:
                    for _errKey, _errValue, _otherValue in oimObject[DUPJSONKEY]:
                        error("xbrlje:invalidJSONStructure",
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
                oimObject = json.loads(_metadata, encoding='utf-8', object_pairs_hook=loadDict)
            documentInfo = jsonGet(oimObject, "documentInfo", {})
            documentType = jsonGet(documentInfo, "documentType")
            if documentType in jsonDocumentTypes:
                isCSV = False
                isJSON = True
                errPrefix = "xbrlje"
            elif documentType in csvDocumentTypes:
                isJSON = False
                if not isXL:
                    isCSV = True
                errPrefix = "xbrlce"
            else:
                raise OIMException("xbrlje:invalidJSONStructure", 
                                   _("documentInfo documentType is not recognized: %(documentType)s"),
                                   documentType=documentType)
            isCSVorXL = isCSV or isXL
            
            missing = [t 
                       for t in (("documentInfo", "facts") if isJSON else ("documentInfo", ) )
                       if t not in oimObject]
            missing += [t 
                        for t in (("documentType", "namespaces", "features", "taxonomy") if isJSON else ("documentType", ))
                        if t not in documentInfo]
            unexpected = [t
                          for t,v in oimObject.items()
                          if t not in {True:{"documentInfo", "facts", "links"},
                                       False:{"documentInfo", "tableTemplates", "tables", "reportParameters", "links"}
                                       }[isJSON]
                             or not isinstance(v, JsonTypes.get(t,()))
                         ]
            unexpected += [t
                           for t,v in documentInfo.items()
                           if t not in {True:{"documentType", "features", "namespaces", "taxonomy", "linkTypes", "linkTypes"},
                                       False:{"documentType", "reportDimensions", "namespaces", "taxonomy", "decimals", "extends", "final"}
                                       }[isJSON]
                           and (":" not in t or t.partition(":")[0] not in documentInfo.get("namespaces"),EMPTY_DICT)]
            unexpected += ["documentInfo final {}".format(t)
                           for t,v in documentInfo.get("final",EMPTY_DICT).items()
                           if t not in {"namespaces", "linkTypes", "linkGroups", "tableTemplates", "tables", "reportDimensions"}
                           or not isinstance(v, bool)]
            if isCSVorXL:
                for n,tbl in jsonGet(oimObject, "tableTemplates", {}).items():
                    for t in ("columns", "tableDimensions"): 
                        if t not in tbl:
                            missing.append("tableTemplates:{}:{}".format(n,t))
                    for t,tv in tbl.items():
                        if (t not in {"rowIdColumn", "columns", "decimals", "tableDimensions", "transposed"} or 
                            not isinstance(tv, JsonTypes.get(t,())) or
                            (t == "rowIdColumn" and not IdentifierPattern.match(tv))):
                            unexpected.append("tableTemplates:{}:{}".format(n,t))
                        elif t == "columns":
                            for nc, col in tv.items():
                                if not IdentifierPattern.match(nc) or not isinstance(col,dict):
                                    unexpected.append("tableTemplates:columns:{}".format(nc))
                                elif isinstance(col, dict):
                                    for t,cv in col.items():
                                        if t not in {"decimals", "columnDimensions"} or (
                                            t == "decimals" and ("columnDimensions" not in col)) or (
                                            not isinstance(cv, JsonTypes.get(t,()))):
                                            unexpected.append("tableTemplates:columns:{}:{}".format(nc,t))
                for n,tbl in oimObject.get("tables",{}).items():
                    for t in ("url", ):
                        if t not in tbl:
                            missing.append("tables:{}:{}".format(n,t))
                    for t,v in tbl.items():
                        if (t not in {"url", "template", "optional", "tableParameters"} or
                            not isinstance(v, JsonTypes.get(t,()))):
                            unexpected.append("tables:{}:{}".format(n,t))
            if missing or unexpected:
                msg = []
                if missing:
                    msg.append(_("Required element(s) are missing from metadata: %(missing)s"))
                if unexpected:
                    msg.append(_("Unexpected element(s) in metadata: %(unexpected)s"))
                raise OIMException("xbrlje:invalidJSONStructure", 
                                   "\n ".join(msg),
                                   missing=", ".join(missing), unexpected=", ".join(unexpected))
                
            if isCSVorXL and "extends" in documentInfo:
                # process extension
                extendedFile = documentInfo["extends"]
                extendedOimObject = loadOimObject(extendedFile, mappedUrl)
                # extended must be CSV
                extendedDocumentInfo = extendedOimObject.get("documentInfo", EMPTY_DICT)
                extendedDocumentType = extendedDocumentInfo.get("documentType")
                extendedFinal = extendedDocumentInfo.get("final", EMPTY_DICT)
                if extendedDocumentType != documentType:
                    error("{}:invalidExtendedDocumentType".format(errPrefix), 
                          _("Extended documentType %(extendedDocumentType)s must same as extending documentType %(documentType)s in file %(extendedFile)"),
                          extendedFile=extendedFile, extendedDocumentType=extendedDocumentType, documentType=documentType)
                    return EMPTY_DICT, None
                for parent, extendedParent, excludedObjectNames in (
                    (documentInfo, extendedDocumentInfo, {"documentType", "extends"}),
                    (oimObject, extendedOimObject, {"documentInfo"})):
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
                            error("{}:extendedObjectDuplicate".format(errPrefix), 
                                  _("Extended file %(extendedFile)s redefines object %(objectName)s"),
                                  extendedFile=extendedFile, objectName=objectName)
                        else:
                            parent[objectName] = extendedParent[objectName]
                                
            if extendingFile is None: # entry oimFile
                oimObject["=entryParameters"] = (isJSON, isCSV, isXL, isCSVorXL, oimWb, documentInfo, documentType)
                
            return oimObject
        
        oimObject = loadOimObject(oimFile, None)
        isJSON, isCSV, isXL, isCSVorXL, oimWb, oimDocumentInfo, documentType = oimObject["=entryParameters"]
        del oimObject["=entryParameters"]
        currentAction = "identifying Metadata objects"
        taxonomyRefs = oimDocumentInfo.get("taxonomy", EMPTY_LIST)
        namespaces = oimDocumentInfo.get("namespaces", EMPTY_DICT)
        linkTypes = oimDocumentInfo.get("linkTypes", EMPTY_DICT)
        linkGroups = oimDocumentInfo.get("linkGroups",EMPTY_DICT)
        if isJSON:
            errPrefix = "xbrlje"
            featuresDict = oimDocumentInfo["features"]
            factItems = oimObject["facts"].items()
            footnotes = oimObject["facts"].values() # shares this object
        else: # isCSVorXL
            errPrefix = "xbrlce"
            reportDimensions = oimDocumentInfo.get("reportDimensions", EMPTY_DICT)
            reportDecimals = oimDocumentInfo.get("decimals", None)
            reportParameters = oimObject.get("reportParameters", EMPTY_DICT)
            tableTemplates = oimObject.get("tableTemplates", EMPTY_DICT)
            tables = oimObject.get("tables", EMPTY_DICT)
            footnotes = (oimObject.get("links", {}), )
            final = oimObject.get("final", EMPTY_DICT)
            if sys.version[0] >= '3':
                csvOpenMode = 'w'
                csvOpenNewline = ''
            else:
                csvOpenMode = 'wb' # for 2.7
                csvOpenNewline = None
                
            # read reportParameters if in a CSV file relative to this file
            if isinstance(reportParameters, str):
                _file, encoding = modelXbrl.fileSource.file(os.path.join(os.path.dirname(oimFile),reportParameters), encoding='utf-8-sig')
                reportParameters = {}
                for row in csv.reader(_file):
                    if len(row) >= 2 and row[0]:
                        reportParameters[row[0]] = row[1]

        if isCSVorXL:
            currentAction = "loading CSV facts tables"
            _dir = os.path.dirname(oimFile)
            anonymousFootnoteId = 0 # integer always for anonymous (same row) footnotes

            def csvFacts():
                for tableId, table in tables.items():
                    tableTemplateId = table.get("template", tableId)
                    if tableTemplateId not in tableTemplates:
                        raise OIMException("xbrlce:missingTableTemplate", 
                                           _("Referenced template missing: %(missing)s"),
                                           missing=tableTemplateId)
                    tableTemplate = tableTemplates[tableTemplateId]
                    tableDecimals = tableTemplate.get("decimals", None)
                    tableDimensions = tableTemplate.get("tableDimensions", EMPTY_DICT)
                    tableIsOptional = tableTemplate.get("optional", False)
                    tableParameters = reportParameters.copy()
                    tableParameters.update( table.get("tableParameters", EMPTY_DICT) )
                    tableUrl = table["url"]
                    # compile column dependencies
                    factDimensions = {}
                    factDecimals = {}
                    for colId, colProperties in tableTemplate["columns"].items():
                        factDimensions[colId] = colProperties.get("columnDimensions", {})
                        if "decimals" in colProperties:
                            factDecimals[colId] = colProperties["decimals"]
                        
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
                        if tableIsOptional and not modelXbrl.fileSource.exists(tablePath):
                            continue
                        if tableUrl.endswith(".xlsx"):
                            _file, = modelXbrl.fileSource.file(tablePath, binary=True)
                            tableWb = load_workbook(_file, data_only=True)
                            _cellValue = xlValue
                        else:
                            # must be CSV
                            _file, encoding = modelXbrl.fileSource.file(tablePath, encoding='utf-8-sig')
                            _rowIterator = csv.reader(_file)
                            _cellValue = csvCellValue
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
                    
                    for rowIndex, row in enumerate(_rowIterator):
                        if rowIndex == 0:
                            header = [_cellValue(cell) for cell in row]
                            colNameIndex = dict((name, colIndex) for colIndex, name in enumerate(header))
                            idColIndex = colNameIndex.get(table.get("rowIdColumn"))
                        else:
                            for colIndex, colValue in enumerate(row):
                                if colIndex >= len(header):
                                    continue
                                colName = header[colIndex]
                                if colName not in factDimensions:
                                    continue # not a fact column
                                id = None
                                fact = {}
                                # if this is an id column
                                cellValue = _cellValue(colValue)
                                if cellValue not in (None, ""):
                                    fact["value"] = cellValue
                                    fact["dimensions"] = colFactDims = factDimensions[colName].copy()
                                    for inheritedDims in (tableDimensions, reportDimensions):
                                        for dimName, dimValue in inheritedDims.items():
                                            if dimName not in colFactDims:
                                                colFactDims[dimName] = inheritedDims[dimName]
                                    # resolve column-relative dimensions
                                    dimsNamesToRemove = []
                                    for dimName, dimValue in colFactDims.items():
                                        if isinstance(dimValue, str) and dimValue.startswith("$"):
                                            dimValue = dimValue[1:]
                                            if not dimValue.startswith("$"):
                                                dimValue, _sep, dimAttr = dimValue.partition("@")
                                                if dimValue in colNameIndex:
                                                    dimValue = _cellValue(row[colNameIndex[dimValue]])
                                                elif dimValue in tableDimensions:
                                                    dimValue = tableDimensions[dimValue]
                                                elif dimValue in reportDimensions:
                                                    dimValue = reportDimensions[dimValue]
                                                if dimName == "period":
                                                    dimValue = csvPeriod(dimValue, dimAttr)
                                            if dimValue in ("", "#none"):
                                                dimsNamesToRemove.append(dimName)
                                            else:
                                                colFactDims[dimName] = dimValue
                                        elif dimValue == "#none":
                                            dimsNamesToRemove.append(dimName)
                                    for dimName in dimsNamesToRemove:
                                        del colFactDims[dimName]
                                    if colName in factDecimals:
                                        dimValue = factDecimals[colName]
                                    elif tableDecimals is not None:
                                        dimValue = tableDecimals
                                    elif reportDecimals is not None:
                                        dimValue = reportDecimals
                                    else:
                                        dimValue = None
                                    if dimValue is not None:
                                        if isinstance(dimValue, str) and dimValue.startswith("$"):
                                            dimValue = dimValue[1:]
                                            if dimValue in colNameIndex:
                                                dimValue = _cellValue(row[colNameIndex[dimValue]])
                                            elif dimValue in tableParameters:
                                                dimValue = tableParameters[dimValue]
                                        if dimValue not in ("", "#none"):
                                            fact["decimals"] = dimValue
                                    id = "{}.{}.{}".format(
                                        tableId, 
                                        _cellValue(row[idColIndex]) if idColIndex is not None and idColIndex < len(row) else rowIndex, 
                                        colName)
                                    yield (id, fact)
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
                  documentEncoding="utf-8")
            modelXbrl.modelDocument.inDTS = True
        else: # API implementation
            modelXbrl = ModelXbrl.create(
                cntlr.modelManager, 
                Type.INSTANCE, 
                instanceFileName, 
                schemaRefs=taxonomyRefs, 
                isEntry=True, 
                initialComment="extracted from OIM {}".format(mappedUri))
            _return = modelXbrl.modelDocument
        
        firstCntxUnitFactElt = None
            
        cntxTbl = {}
        unitTbl = {}
        xbrlNoteTbl = {} # fact ID: note fact
            
        currentAction = "creating facts"
        factNum = 0 # for synthetic fact number
        if isJSON:
            syntheticFactFormat = "_f{{:0{}}}".format(int(math.log10(len(factItems)))) #want 
        else:
            syntheticFactFormat = "_f{}" #want 
        
        for id, fact in factItems:
            
            dimensions = fact.get("dimensions", EMPTY_DICT)
            if "concept" not in dimensions:
                error("{}:conceptQName".format(errPrefix),
                                _("The concept QName could not be determined, dimension \"concept\" is missing."),
                                modelObject=modelXbrl)
                return
            if not id:
                id = syntheticFactFormat.format(factNum)
                factNum += 1
            conceptSQName = dimensions["concept"]
            conceptPrefix = conceptSQName.rpartition(":")[0]
            if conceptSQName == "xbrl:note":
                xbrlNoteTbl[id] = fact
                continue
            elif not NCNamePattern.match(conceptPrefix):
                error("oimce:invalidSQNamePrefix",
                                _("The prefix of %(concept)s must match the NCName lexical pattern"),
                                modelObject=modelXbrl, concept=conceptSQName)
                continue
            elif conceptPrefix not in namespaces:
                error("oimce:unboundSQNamePrefix",
                      _("The concept SQName prefix was not defined in namespaces: %(concept)s."),
                      modelObject=modelXbrl, concept=conceptSQName)
                continue
            conceptQn = qname(conceptSQName, namespaces)
            concept = modelXbrl.qnameConcepts.get(conceptQn)
            if concept is None:
                error("xbrl:schemaImportMissing",
                      _("The concept QName could not be resolved with available DTS: %(concept)s."),
                      modelObject=modelXbrl, concept=conceptQn)
                return
            attrs = {}
            if concept.isItem:
                missingDimensions = []
                if "entity" not in dimensions: 
                    missingDimensions.append("entity")
                if "xbrl:start" in dimensions and "xbrl:end" in dimensions:
                    pass
                if missingDimensions:
                    error("{}:missingDimensions".format(errPrefix),
                                    _("The concept %(element)s is missing dimensions %(missingDimensions)s"),
                                    modelObject=modelXbrl, element=conceptQn, missingDimensions=", ".join(missingDimensions))
                    return
                if "language" in dimensions:
                    attrs["{http://www.w3.org/XML/1998/namespace}lang"] = dimensions["language"]
                if "entity" in dimensions:
                    entityAsQn = qname(dimensions["entity"], namespaces) or ENTITY_NA_QNAME
                else:
                    entityAsQn = ENTITY_NA_QNAME
                if "xbrl:start" in dimensions and "xbrl:end" in dimensions:
                    # CSV/XL format
                    period = dimensions["xbrl:start"]
                    if period != dimensions["xbrl:end"]:
                        period += "/" + dimensions["xbrl:end"]
                elif "period" in dimensions:
                    period = dimensions["period"]
                    if period is None:
                        period = "forever"
                    elif not re.match(r"\d{4,}-[0-1][0-9]-[0-3][0-9]T([0-1][0-9]:[0-5][0-9]:[0-5][0-9])"
                                      r"(/\d{4,}-[0-1][0-9]-[0-3][0-9]T([0-1][0-9]:[0-5][0-9]:[0-5][0-9]))?", period):
                        error("{}:periodDateTime".format(errPrefix),
                              _("The concept %(element)s has a lexically invalid period dateTime %(periodError)s"),
                              modelObject=modelXbrl, element=conceptQn, periodError=periodDate)
                else:
                    period = "forever"
                cntxKey = ( # hashable context key
                    ("periodType", concept.periodType),
                    ("entity", entityAsQn),
                    ("period", period)) + tuple(sorted(
                        (dimName, dimVal["value"] if isinstance(dimVal,dict) else dimVal) 
                        for dimName, dimVal in dimensions.items()
                        if ":" in dimName))
                if cntxKey in cntxTbl:
                    _cntx = cntxTbl[cntxKey]
                else:
                    cntxId = 'c-{:02}'.format(len(cntxTbl) + 1)
                    qnameDims = {}
                    for dimName, dimVal in dimensions.items():
                        if ":" in dimName:
                            dimQname = qname(dimName, namespaces)
                            dimConcept = modelXbrl.qnameConcepts.get(dimQname)
                            if dimConcept is None:
                                error("xbrl:schemaDefinitionMissing",
                                      _("The taxonomy defined aspect concept QName %(qname)s could not be determined"),
                                      modelObject=modelXbrl, qname=dimQname)
                                continue
                            if dimVal is None:
                                memberAttrs = {"{http://www.w3.org/2001/XMLSchema-instance}nil": "true"}
                            else:
                                memberAttrs = None
                            if isinstance(dimVal, dict):
                                dimVal = dimVal["value"]
                            else:
                                dimVal = str(dimVal) # may be int or boolean
                            if isinstance(dimVal,str) and ":" in dimVal and dimVal.partition(':')[0] in namespaces:
                                mem = qname(dimVal, namespaces) # explicit dim
                            elif dimConcept.isTypedDimension:
                                # a modelObject xml element is needed for all of the instance functions to manage the typed dim
                                mem = addChild(modelXbrl.modelDocument, dimConcept.typedDomainElement.qname, text=dimVal, attributes=memberAttrs, appendChild=False)
                            else:
                                mem = None # absent typed dimension
                            if mem is not None:
                                qnameDims[dimQname] = DimValuePrototype(modelXbrl, None, dimQname, mem, "segment")
                    _cntx = modelXbrl.createContext(
                                            entityAsQn.namespaceURI,
                                            entityAsQn.localName,
                                            "forever" if period == "forever" else concept.periodType,
                                            None if concept.periodType == "instant" or period == "forever" 
                                                else dateTime(period.rpartition('/')[0], type=DATETIME),
                                            None if period == "forever"
                                                else dateTime(period.rpartition('/')[2], type=DATETIME),
                                            None, # no dimensional validity checking (like formula does)
                                            qnameDims, [], [],
                                            id=cntxId)
                    cntxTbl[cntxKey] = _cntx
                    if firstCntxUnitFactElt is None:
                        firstCntxUnitFactElt = _cntx
                if concept.isNumeric:
                    if "unit" in dimensions and dimensions["unit"] is not None:
                        unitKey = dimensions["unit"]
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
                            error("xbrlje:invalidUnitString",
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
                                error("xbrlje:invalidUnitString",
                                      _("Unit string representation measures are not in alphabetical order, %(unit)s"),
                                      modelObject=modelXbrl, unit=unitKey)
                            try:
                                mulQns = [qname(u, namespaces, prefixException=OIMException("xbrlje:unboundPrefix",
                                                                                          _("Unit prefix is not declared: %(unit)s"),
                                                                                          unit=u)) 
                                          for u in _muls]
                                divQns = [qname(u, namespaces, prefixException=OIMException("xbrlje:unboundPrefix",
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
            
                attrs["contextRef"] = _cntx.id
        
                if fact.get("value") is None:
                    attrs[XbrlConst.qnXsiNil] = "true"
                    text = None
                else:
                    text = fact["value"]
                    
                if concept.isNumeric:
                    if _unit is None:
                        return # skip creating fact because unit was invalid
                    attrs["unitRef"] = _unit.id
                    if text is not None: # no decimals for nil value
                        decimals = fact.get("decimals")
                        attrs["decimals"] = decimals if decimals is not None else "INF"
            else:
                text = None #tuple
                    
            attrs["id"] = id
            if "id" not in fact: # needed for footnote generation
                fact["id"] = id
                    
            # is value a QName?
            if concept.baseXbrliType == "QNameItemType": # renormalize prefix of instance fact
                text = addQnameValue(modelXbrl.modelDocument, qname(text.strip(), namespaces))
    
            f = modelXbrl.createFact(conceptQn, attributes=attrs, text=text, validate=False)
            if firstCntxUnitFactElt is None:
                firstCntxUnitFactElt = f
            
            xmlValidate(modelXbrl, f)
                    
        currentAction = "creating footnotes"
        footnoteLinks = OrderedDict() # ELR elements
        factLocs = {} # index by (linkrole, factId)
        footnoteNbr = 0
        locNbr = 0
        definedInstanceRoles = set()
        footnoteIdsNotReferenced = set()
        undefinedFootnoteTypes = set()
        undefinedFootnoteGroups = set()
        for factOrFootnote in footnotes:
            if isJSON:
                factFootnotes = []
                for ftType, ftGroups in factOrFootnote.get("links", {}).items():
                    ftSrcId = factOrFootnote["id"]
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
                                    footnote.setdefault("noteRefs" if tgtId in xbrlNoteTbl else "factRefs", []).append(tgtId)
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
                                        footnote.setdefault("noteRefs" if tgtId in xbrlNoteTbl else "factRefs", []).append(tgtId)
                                    factFootnotes.append(footnote)
            for footnote in factFootnotes:
                factIDs = (footnote["id"], )
                linkrole = footnote["footnoteGroup"]
                arcrole = footnote["footnoteType"]
                if not factIDs or not linkrole or not arcrole or not (
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
                    if (not XbrlConst.isStandardRole(refValue) or XbrlConst.isStandardArcrole(refValue)
                        ) and refValue in roleTypes and refValue not in definedInstanceRoles:
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
                if linkrole not in footnoteLinks:
                    footnoteLinks[linkrole] = addChild(modelXbrl.modelDocument.xmlRootElement, 
                                                       XbrlConst.qnLinkFootnoteLink, 
                                                       attributes={"{http://www.w3.org/1999/xlink}type": "extended",
                                                                   "{http://www.w3.org/1999/xlink}role": linkrole})
                footnoteLink = footnoteLinks[linkrole]
                if (linkrole, factIDs) not in factLocs:
                    locNbr += 1
                    locLabel = "l_{:02}".format(locNbr)
                    factLocs[(linkrole, factIDs)] = locLabel
                    for factId in factIDs:
                        addChild(footnoteLink, XbrlConst.qnLinkLoc, 
                                 attributes={XLINKTYPE: "locator",
                                             XLINKHREF: "#" + factId,
                                             XLINKLABEL: locLabel})
                locFromLabel = factLocs[(linkrole, factIDs)]
                if "noteRefs" in footnote:
                    footnoteNbr += 1
                    footnoteToLabel = "f_{:02}".format(footnoteNbr)
                    for noteId in footnote.get("noteRefs"):
                        xbrlNote = xbrlNoteTbl[noteId]
                        attrs = {XLINKTYPE: "resource",
                                 XLINKLABEL: footnoteToLabel}
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
        if isCSV and footnoteIdsNotReferenced:
            warning("xbrlce:footnotesNotReferenced",
                    _("FootnoteId(s) not referenced %(footnoteIds)s."),
                    modelObject=modelXbrl, footnoteIds=", ".join(sorted(footnoteIdsNotReferenced)))
        if footnoteLinks:
            modelXbrl.modelDocument.linkbaseDiscover(footnoteLinks.values(), inInstance=True)

        if undefinedFootnoteTypes:
            error("xbrlje:unknownPrefix",
                  _("These footnote types are not defined in footnoteTypes: %(ftTypes)s."),
                  modelObject=modelXbrl, ftTypes=", ".join(sorted(undefinedFootnoteTypes)))
        if undefinedFootnoteGroups:
            error("xbrlje:unknownPrefix",
                  _("These footnote groups are not defined in footnoteGroups: %(ftGroups)s."),
                  modelObject=modelXbrl, ftGroups=", ".join(sorted(undefinedFootnoteGroups)))
                    
        currentAction = "done loading facts and footnotes"
        
        #cntlr.addToLog("Completed in {0:.2} secs".format(time.time() - startedAt),
        #               messageCode="loadFromExcel:info")
    except NotOIMException as ex:
        _return = ex # not an OIM document
    except json.JSONDecodeError as ex:
        _return = ex # not an OIM document
        error("arelleOIMloader:jsonFileError",
                "JSON error while %(action)s, error %(error)s",
                modelObject=modelXbrl, action=currentAction, error=ex)
    except Exception as ex:
        _return = ex
        if isinstance(ex, OIMException):
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
        if _fileStart and re.match(r"\s*\{\s*\"documentType\":\s*\"http:\\+/\\+/www.xbrl.org\\+/WGWD\\+/YYYY-MM-DD\\+/xbrl-json\"", _fileStart):
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
    'CntlrCmdLine.Xbrl.Loaded': cmdLineXbrlLoaded
}
