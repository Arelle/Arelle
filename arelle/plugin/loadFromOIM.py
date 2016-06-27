'''
loadFromExcel.py is an example of a plug-in that will load an extension taxonomy from Excel
input and optionally save an (extension) DTS.

(c) Copyright 2016 Mark V Systems Limited, All rights reserved.
'''
import os, sys, io, time, re, traceback, json, csv
from collections import defaultdict, OrderedDict
from arelle.ModelDocument import Type, create as createModelDocument
from arelle import XbrlConst, ModelDocument, ValidateXbrlDimensions
from arelle.ModelDocument import Type, create as createModelDocument
from arelle.ModelValue import qname, dateTime, DATETIME
from arelle.PrototypeInstanceObject import DimValuePrototype
from arelle.XbrlConst import (qnLinkLabel, standardLabelRoles, qnLinkReference, standardReferenceRoles,
                              qnLinkPart, gen, link, defaultLinkRole,
                              conceptLabel, elementLabel, conceptReference,
                              )
from arelle.XmlUtil import addChild, addQnameValue
from arelle.XmlValidate import NCNamePattern

nsOim = {"http://www.xbrl.org/WGWD/YYYY-MM-DD/oim",
         "http://www.xbrl.org/PWD/2016-01-13/oim"
         }
         


XLINKTYPE = "{http://www.w3.org/1999/xlink}type"
XLINKLABEL = "{http://www.w3.org/1999/xlink}label"
XLINKARCROLE = "{http://www.w3.org/1999/xlink}arcrole"
XLINKFROM = "{http://www.w3.org/1999/xlink}from"
XLINKTO = "{http://www.w3.org/1999/xlink}to"
XLINKHREF = "{http://www.w3.org/1999/xlink}href"
XMLLANG = "{http://www.w3.org/XML/1998/namespace}lang"

DUPJSONKEY = "!@%duplicates%@!"

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

class OIMException(Exception):
    def __init__(self, code, message, **kwargs):
        self.code = code
        self.message = message
        self.msgArgs = kwargs
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception {1}').format(self.code, self.message % self.msgArgs)


def loadFromOIM(cntlr, modelXbrl, oimFile, mappedUri):
    from openpyxl import load_workbook
    from arelle import ModelDocument, ModelXbrl, XmlUtil
    from arelle.ModelDocument import ModelDocumentReference
    from arelle.ModelValue import qname
    
    try:
        currentAction = "initializing"
        startingErrorCount = len(modelXbrl.errors)
        startedAt = time.time()
        
        if os.path.isabs(oimFile):
            # allow relative filenames to loading directory
            priorCWD = os.getcwd()
            os.chdir(os.path.dirname(oimFile))
        else:
            priorCWD = None
            
        currentAction = "determining file type"
        isJSON = oimFile.endswith(".json") and not oimFile.endswith("-metadata.json")
        isCSV = oimFile.endswith(".csv") or oimFile.endswith("-metadata.json")
        isXL = oimFile.endswith(".xlsx") or oimFile.endswith(".xls")
        isCSVorXL = isCSV or isXL
        instanceFileName = os.path.splitext(oimFile)[0] + ".xbrl"
        
        if isJSON:
            currentAction = "loading and parsing JSON OIM file"
            def loadDict(keyValuePairs):
                _dict = OrderedDict() # preserve fact order in resulting instance
                for key, value in keyValuePairs:
                    if isinstance(value, dict):
                        if DUPJSONKEY in value:
                            for _errKey, _errValue, _otherValue in value[DUPJSONKEY]:
                                if key == "prefixes":
                                    modelXbrl.error("oime:duplicatedPrefix",
                                                    _("The prefix %(prefix)s is used on uri %(uri1)s and uri %(uri2)s"),
                                                    modelObject=modelXbrl, prefix=_errKey, uri1=_errValue, uri2=_otherValue)
                            del value[DUPJSONKEY]
                    if key in _dict:
                        if DUPJSONKEY not in _dict:
                            _dict[DUPJSONKEY] = []
                        _dict[DUPJSONKEY].append((key, value, _dict[key]))
                    else:
                        _dict[key] = value
                return _dict
            with io.open(oimFile, 'rt', encoding='utf-8') as f:
                oimObject = json.load(f, object_pairs_hook=loadDict)
            missing = [t for t in ("dtsReferences", "prefixes", "facts") if t not in oimObject]
            if missing:
                raise OIMException("oime:missingJSONElements", 
                                   _("Required element(s) are missing from JSON input: %(missing)s"),
                                   missing = ", ".join(missing))
            currentAction = "identifying JSON objects"
            dtsReferences = oimObject["dtsReferences"]
            prefixesList = oimObject["prefixes"].items()
            facts = oimObject["facts"]
            footnotes = oimObject["facts"] # shares this object
        elif isCSV:
            currentAction = "identifying CSV input tables"
            if sys.version[0] >= '3':
                csvOpenMode = 'w'
                csvOpenNewline = ''
            else:
                csvOpenMode = 'wb' # for 2.7
                csvOpenNewline = None
                
            oimFileBase = None
            if "-facts" in oimFile:
                oimFileBase = oimFile.partition("-facts")[0]
            else:
                for suffix in ("-dtsReferences.csv", "-defaults.csv", "-prefixes.csv", "-footnotes.csv", "-metadata.json"):
                    if oimFile.endswith(suffix):
                        oimFileBase = oimFile[:-len(suffix)]
                        break
            if oimFileBase is None:
                raise OIMException("oime:missingCSVTables", 
                                   _("Unable to identify CSV tables file name pattern"))
            if (not os.path.exists(oimFileBase + "-dtsReferences.csv") or
                not os.path.exists(oimFileBase + "-prefixes.csv")):
                raise OIMException("oime:missingCSVTables", 
                                   _("Unable to identify CSV tables for dtsReferences or prefixes"))
            instanceFileName = oimFileBase + ".xbrl"
            currentAction = "loading CSV dtsReferences table"
            dtsReferences = []
            with io.open(oimFileBase + "-dtsReferences.csv", 'rt', encoding='utf-8-sig') as f:
                csvReader = csv.reader(f)
                for i, row in enumerate(csvReader):
                    if i == 0:
                        header = row
                    else:
                        dtsReferences.append(dict((header[j], col) for j, col in enumerate(row)))
            currentAction = "loading CSV prefixes table"
            prefixesList = []
            with io.open(oimFileBase + "-prefixes.csv", 'rt', encoding='utf-8-sig') as f:
                csvReader = csv.reader(f)
                for i, row in enumerate(csvReader):
                    if i == 0:
                        header = dict((col,i) for i,col in enumerate(row))
                    else:
                        prefixesList.append((row[header["prefix"]], row[header["URI"]]))
            defaults = {}
            if os.path.exists(oimFileBase + "-defaults.csv"):
                currentAction = "loading CSV defaults table"
                with io.open(oimFileBase + "-defaults.csv", 'rt', encoding='utf-8-sig') as f:
                    csvReader = csv.reader(f)
                    for i, row in enumerate(csvReader):
                        if i == 0:
                            header = row
                            fileCol = row.index("file")
                        else:
                            defaults[row[fileCol]] = dict((header[j], col) for j, col in enumerate(row) if j != fileCol)
            currentAction = "loading CSV facts tables"
            facts = []
            _dir = os.path.dirname(oimFileBase)
            factsFileBasename = os.path.basename(oimFileBase) + "-facts"
            for filename in os.listdir(_dir):
                filepath = os.path.join(_dir, filename)
                if filename.startswith(factsFileBasename):
                    currentAction = "loading CSV facts table {}".format(filename)
                    tableDefaults = defaults.get(filename, {})
                    with io.open(filepath, 'rt', encoding='utf-8-sig') as f:
                        csvReader = csv.reader(f)
                        for i, row in enumerate(csvReader):
                            if i == 0:
                                header = row
                            else:
                                fact = {}
                                fact.update(tableDefaults)
                                for j, col in enumerate(row):
                                    if col is not None:
                                        if header[j]: # skip cols with no header
                                            if header[j].endswith("Value"):
                                                if col: # ignore empty columns (= null CSV value)
                                                    fact["value"] = col
                                            else:
                                                fact[header[j]] = col
                                facts.append(fact)
            footnotes = []
            if os.path.exists(oimFileBase + "-footnotes.csv"):
                currentAction = "loading CSV footnotes table"
                with io.open(oimFileBase + "-footnotes.csv", 'rt', encoding='utf-8-sig') as f:
                    csvReader = csv.reader(f)
                    for i, row in enumerate(csvReader):
                        if i == 0:
                            header = row
                        else:
                            footnotes.append(dict((header[j], col) for j, col in enumerate(row) if col))
        elif isXL:
            currentAction = "identifying workbook input worksheets"
            oimWb = load_workbook(oimFile, read_only=True, data_only=True)
            sheetNames = oimWb.get_sheet_names()
            if (not any(sheetName == "prefixes" for sheetName in sheetNames) or
                not any(sheetName == "dtsReferences" for sheetName in sheetNames) or
                not any("facts" in sheetName for sheetName in sheetNames)):
                raise OIMException("oime:missingWorkbookWorksheets", 
                                   _("Unable to identify worksheet tabs for dtsReferences, prefixes or facts"))
            currentAction = "loading worksheet: dtsReferences"
            dtsReferences = []
            for i, row in enumerate(oimWb["dtsReferences"]):
                if i == 0:
                    header = [col.value for col in row]
                else:
                    dtsReferences.append(dict((header[j], col.value) for j, col in enumerate(row)))
            currentAction = "loading worksheet: prefixes"
            prefixesList = []
            for i, row in enumerate(oimWb["prefixes"]):
                if i == 0:
                    header = dict((col.value,i) for i,col in enumerate(row))
                else:
                    prefixesList.append((row[header["prefix"]].value, row[header["URI"]].value))
            defaults = {}
            if "defaults" in sheetNames:
                currentAction = "loading worksheet: defaults"
                for i, row in enumerate(oimWb["defaults"]):
                    if i == 0:
                        header = dict((col.value,i) for i,col in enumerate(row))
                        fileCol = header["file"]
                    else:
                        defaults[row[fileCol].value] = dict((header[j], col.value) for j, col in enumerate(row) if j != fileCol)
            facts = []
            for sheetName in sheetNames:
                if sheetName == "facts" or "-facts" in sheetName:
                    currentAction = "loading worksheet: {}".format(sheetName)
                    tableDefaults = defaults.get(sheetName, {})
                    for i, row in enumerate(oimWb[sheetName]):
                        if i == 0:
                            header = [col.value for col in row]
                        else:
                            fact = {}
                            fact.update(tableDefaults)
                            for j, col in enumerate(row):
                                if col.value is not None:
                                    if header[j]: # skip cols with no header
                                        if header[j].endswith("Value"):
                                            fact["value"] = str(col.value)
                                        else:
                                            fact[header[j]] = str(col.value)
                            facts.append(fact)
            footnotes = []
            if "footnotes" in sheetNames:
                currentAction = "loading worksheet: footnotes"
                for i, row in enumerate(oimWb["footnotes"]):
                    if i == 0:
                        header = dict((col.value,i) for i,col in enumerate(row) if col.value)
                    else:
                        footnotes.append(dict((header[j], col.value) for j, col in enumerate(row) if col.value))
    
        currentAction = "identifying default dimensions"
        ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl) # needs dimension defaults 
        
        currentAction = "validating OIM"
        prefixes = {}
        prefixedUris = {}
        for _prefix, _uri in prefixesList:
            if not _prefix:
                modelXbrl.error("oime:emptyPrefix",
                                _("The empty string must not be used as a prefix, uri %(uri)s"),
                                modelObject=modelXbrl, uri=_uri)
            elif not NCNamePattern.match(_prefix):
                modelXbrl.error("oime:prefixPattern",
                                _("The prefix %(prefix)s must match the NCName lexical pattern, uri %(uri)s"),
                                modelObject=modelXbrl, prefix=_prefix, uri=_uri)
            elif _prefix in prefixes:
                modelXbrl.error("oime:duplicatedPrefix",
                                _("The prefix %(prefix)s is used on uri %(uri1)s and uri %(uri2)s"),
                                modelObject=modelXbrl, prefix=_prefix, uri1=prefixes[_prefix], uri2=_uri)
            elif _uri in prefixedUris:
                modelXbrl.error("oime:duplicatedUri",
                                _("The uri %(uri)s is used on prefix %(prefix1)s and prefix %(prefix2)s"),
                                modelObject=modelXbrl, uri=_uri, prefix1=prefixedUris[_uri], prefix2=_prefix)
            else:
                prefixes[_prefix] = _uri
                prefixedUris[_uri] = _prefix
                
        oimPrefix = None
        for _nsOim in nsOim:
            if _nsOim in prefixedUris:
                oimPrefix = prefixedUris[_nsOim]
        if not oimPrefix:
            raise OIMException("oime:noOimPrefix",
                               _("The oim namespace must have a declared prefix"))
        oimConcept = "{}:concept".format(oimPrefix)
        oimEntity = "{}:entity".format(oimPrefix)
        oimPeriod = "{}:period".format(oimPrefix)
        oimPeriodStart = "{}:periodStart".format(oimPrefix)
        oimPeriodEnd = "{}:periodEnd".format(oimPrefix)
        oimUnit = "{}:unit".format(oimPrefix)
        oimPrefix = "{}:".format(oimPrefix)
            
        # create the instance document
        currentAction = "creating instance document"
        modelXbrl.blockDpmDBrecursion = True
        modelXbrl.modelDocument = createModelDocument(
              modelXbrl, 
              Type.INSTANCE,
              instanceFileName,
              schemaRefs=[dtsRef["href"] for dtsRef in dtsReferences if dtsRef["type"] == "schema"],
              isEntry=True,
              initialComment="extracted from OIM {}".format(mappedUri),
              documentEncoding="utf-8")
        cntxTbl = {}
        unitTbl = {}
        currentAction = "creating facts"
        for fact in facts:
            conceptQn = qname(fact[oimConcept], prefixes)
            concept = modelXbrl.qnameConcepts.get(conceptQn)
            entityAsQn = qname(fact[oimEntity], prefixes)
            if oimPeriod in fact:
                periodStart = fact[oimPeriod]["start"]
                periodEnd = fact[oimPeriod]["end"]
            else:
                periodStart = fact[oimPeriodStart]
                periodEnd = fact[oimPeriodEnd]
            cntxKey = ( # hashable context key
                ("periodType", concept.periodType),
                ("entity", entityAsQn),
                ("periodStart", periodStart),
                ("periodEnd", periodEnd)) + tuple(sorted(
                    (dimName, dimVal) 
                    for dimName, dimVal in fact.items()
                    if ":" in dimName and not dimName.startswith(oimPrefix)))
            if cntxKey in cntxTbl:
                _cntx = cntxTbl[cntxKey]
            else:
                cntxId = 'c-{:02}'.format(len(cntxTbl) + 1)
                qnameDims = {}
                for dimName, dimVal in fact.items():
                    if ":" in dimName and not dimName.startswith(oimPrefix) and dimVal:
                        dimQname = qname(dimName, prefixes)
                        dimConcept = modelXbrl.qnameConcepts.get(dimQname)
                        if ":" in dimVal and dimVal.partition(':')[0] in prefixes:
                            mem = qname(dimVal, prefixes) # explicit dim
                        elif dimConcept.isTypedDimension:
                            # a modelObject xml element is needed for all of the instance functions to manage the typed dim
                            mem = addChild(modelXbrl.modelDocument, dimConcept.typedDomainElement.qname, text=dimVal, appendChild=False)
                        qnameDims[dimQname] = DimValuePrototype(modelXbrl, None, dimQname, mem, "segment")
                _cntx = modelXbrl.createContext(
                                        entityAsQn.namespaceURI,
                                        entityAsQn.localName,
                                        concept.periodType,
                                        None if concept.periodType == "instant" else dateTime(periodStart, type=DATETIME),
                                        dateTime(periodEnd, type=DATETIME),
                                        None, # no dimensional validity checking (like formula does)
                                        qnameDims, [], [],
                                        id=cntxId)
                cntxTbl[cntxKey] = _cntx
            if oimUnit in fact:
                unitKey = fact[oimUnit]
                if unitKey in unitTbl:
                    _unit = unitTbl[unitKey]
                else:
                    _unit = None
                    # validate unit
                    unitKeySub = PrefixedQName.sub(UnitPrefixedQNameSubstitutionChar, unitKey)
                    if not UnitPattern.match(unitKeySub):
                        modelXbrl.error("oime:unitStringRepresentation",
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
                            modelXbrl.error("oime:unitStringRepresentation",
                                            _("Unit string representation measures are not in alphabetical order, %(unit)s"),
                                            modelObject=modelXbrl, unit=unitKey)
                        try:
                            mulQns = [qname(u, prefixes, prefixException=OIMException("oime:unitPrefix",
                                                                                      _("Unit prefix is not declared: %(unit)s"),
                                                                                      unit=u)) 
                                      for u in _muls]
                            divQns = [qname(u, prefixes, prefixException=OIMException("oime:unitPrefix",
                                                                                      _("Unit prefix is not declared: %(unit)s"),
                                                                                      unit=u))
                                      for u in _divs]
                            unitId = 'u-{:02}'.format(len(unitTbl) + 1)
                            for _measures in mulQns, divQns:
                                for _measure in _measures:
                                    addQnameValue(modelXbrl.modelDocument, _measure)
                            _unit = modelXbrl.createUnit(mulQns, divQns, id=unitId)
                        except OIMException as ex:
                            modelXbrl.error(ex.code, ex.message, modelObject=modelXbrl, **ex.msgArgs)
                    unitTbl[unitKey] = _unit
            else:
                _unit = None
            
            attrs = {"contextRef": _cntx.id}
    
            if fact.get("value") is None:
                attrs[XbrlConst.qnXsiNil] = "true"
                text = None
            else:
                text = fact["value"]
                
            if fact.get("id"):
                attrs["id"] = fact["id"]
                
            if concept.isNumeric:
                if _unit is None:
                    continue # skip creating fact because unit was invalid
                attrs["unitRef"] = _unit.id
                if "accuracy" in fact:
                    attrs["decimals"] = fact["accuracy"]
                    
            # is value a QName?
            if concept.baseXbrliType == "QName":
                addQnameValue(modelXbrl.modelDocument, qname(text.strip(), prefixes))
    
            f = modelXbrl.createFact(conceptQn, attributes=attrs, text=text)
            
        currentAction = "creating footnotes"
        footnoteLinks = {} # ELR elements
        factLocs = {} # index by (linkrole, factId)
        footnoteNbr = 0
        locNbr = 0
        for factOrFootnote in footnotes:
            if "factId" in factOrFootnote:
                factId = factOrFootnote["factId"]
                factFootnotes = (factOrFootnote,) # CSV or XL
            elif "id" in factOrFootnote and "footnotes" in factOrFootnote:
                factId = factOrFootnote["id"]
                factFootnotes = factOrFootnote["footnotes"]
            else:
                factFootnotes = ()
            for footnote in factFootnotes:
                linkrole = footnote.get("group")
                arcrole = footnote.get("footnoteType")
                if not factId or not linkrole or not arcrole or not (
                    footnote.get("factRef") or footnote.get("footnote")):
                    # invalid footnote
                    continue
                if linkrole not in footnoteLinks:
                    footnoteLinks[linkrole] = addChild(modelXbrl.modelDocument.xmlRootElement, 
                                                       XbrlConst.qnLinkFootnoteLink, 
                                                       attributes={"{http://www.w3.org/1999/xlink}type": "extended",
                                                                   "{http://www.w3.org/1999/xlink}role": linkrole})
                footnoteLink = footnoteLinks[linkrole]
                if (linkrole, factId) not in factLocs:
                    locNbr += 1
                    locLabel = "l_{:02}".format(locNbr)
                    factLocs[(linkrole, factId)] = locLabel
                    addChild(footnoteLink, XbrlConst.qnLinkLoc, 
                             attributes={XLINKTYPE: "locator",
                                         XLINKHREF: "#" + factId,
                                         XLINKLABEL: locLabel})
                locLabel = factLocs[(linkrole, factId)]
                if footnote.get("footnote"):
                    footnoteNbr += 1
                    footnoteLabel = "f_{:02}".format(footnoteNbr)
                    attrs = {XLINKTYPE: "resource",
                             XLINKLABEL: footnoteLabel}
                    if footnote.get("language"):
                        attrs[XMLLANG] = footnote["language"]
                    # note, for HTML will need to build an element structure
                    addChild(footnoteLink, XbrlConst.qnLinkFootnote, attributes=attrs, text=footnote["footnote"])
                elif footnote.get("factRef"):
                    factRef = footnote.get("factRef")
                    if (linkrole, factRef) not in factLocs:
                        locNbr += 1
                        locLabel = "f_{:02}".format(footnoteNbr)
                        factLoc[(linkrole, factRef)] = locLabel
                        addChild(footnoteLink, XbrlConst.qnLinkLoc, 
                                 attributes={XLINKTYPE: "locator",
                                             XLINKHREF: "#" + factRef,
                                             XLINKLABEL: locLabel})
                    footnoteLabel = factLoc[(linkrole, factId)]
                footnoteArc = addChild(footnoteLink, 
                                       XbrlConst.qnLinkFootnoteArc, 
                                       attributes={XLINKTYPE: "arc",
                                                   XLINKARCROLE: arcrole,
                                                   XLINKFROM: locLabel,
                                                   XLINKTO: footnoteLabel})
                    
        currentAction = "done loading facts and footnotes"
        
        #cntlr.addToLog("Completed in {0:.2} secs".format(time.time() - startedAt),
        #               messageCode="loadFromExcel:info")
    except Exception as ex:
        if isinstance(ex, OIMException):
            modelXbrl.error(ex.code, ex.message, modelObject=modelXbrl, **ex.msgArgs)
        else:
            modelXbrl.error("arelleOIMloader:error",
                            "Error while %(action)s, error %(error)s\ntraceback %(traceback)s",
                            modelObject=modelXbrl, action=currentAction, error=ex,
                            traceback=traceback.format_tb(sys.exc_info()[2]))
    
    if priorCWD:
        os.chdir(priorCWD) # restore prior current working directory            startingErrorCount = len(modelXbrl.errors)
        
    if startingErrorCount < len(modelXbrl.errors):
        # had errors, don't allow ModelDocument.load to continue
        return OIMException("arelleOIMloader:unableToLoad", "Unable to load due to reported errors")

    return getattr(modelXbrl, "modelDocument", None) # none if returning from exception

def isOimLoadable(modelXbrl, mappedUri, normalizedUri, **kwargs):
    return os.path.splitext(mappedUri)[1] in (".csv", ".json", ".xlsx", ".xls")

def oimLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    if os.path.splitext(filepath)[1] not in (".csv", ".json", ".xlsx", ".xls"):
        return None # not an OIM file

    cntlr = modelXbrl.modelManager.cntlr
    cntlr.showStatus(_("Loading OIM file: {0}").format(os.path.basename(filepath)))
    doc = loadFromOIM(cntlr, modelXbrl, filepath, mappedUri)
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
        doc.save(options.saveOIMinstance)
        cntlr.showStatus(_("Saving XBRL instance: {0}").format(doc.basename))

def excelLoaderOptionExtender(parser, *args, **kwargs):
    parser.add_option("--saveOIMinstance", 
                      action="store", 
                      dest="saveOIMinstance", 
                      help=_("Save a instance loaded from OIM into this file name."))

    
__pluginInfo__ = {
    'name': 'Load From OIM',
    'version': '0.9',
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
