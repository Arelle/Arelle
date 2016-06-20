'''
loadFromExcel.py is an example of a plug-in that will load an extension taxonomy from Excel
input and optionally save an (extension) DTS.

(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
import os, sys, io, time, re, traceback, json, csv
from collections import defaultdict
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

XLINKTYPE = "{http://www.w3.org/1999/xlink}type"
XLINKLABEL = "{http://www.w3.org/1999/xlink}label"
XLINKARCROLE = "{http://www.w3.org/1999/xlink}arcrole"
XLINKFROM = "{http://www.w3.org/1999/xlink}from"
XLINKTO = "{http://www.w3.org/1999/xlink}to"
XLINKHREF = "{http://www.w3.org/1999/xlink}href"
XMLLANG = "{http://www.w3.org/XML/1998/namespace}lang"

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
            with io.open(oimFile, 'rt', encoding='utf-8') as f:
                oimObject = json.load(f)
            missing = [t for t in ("dtsReferences", "prefixes", "facts") if t not in oimObject]
            if missing:
                raise OIMException("oime:missingJSONelements", 
                                   _("The required elements %(missing)s {} in JSON input"),
                                   missing = ", ".join(missing))
            currentAction = "identifying JSON objects"
            dtsReferences = oimObject["dtsReferences"]
            prefixes = oimObject["prefixes"]
            facts = oimObject["facts"]
            footnotes = oimOject["facts"] # shares this object
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
                        oimFileBase = oimFile[:-length(suffix)]
                        break
            if oimFileBase is None:
                raise OIMException("oime:missingCSVtables", 
                                   _("Unable to identify CSV tables file name pattern"))
            if (not os.path.exists(oimFileBase + "-dtsReferences.csv") or
                not os.path.exists(oimFileBase + "-prefixes.csv")):
                raise OIMException("oime:missingCSVtables", 
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
            prefixes = {}
            with io.open(oimFileBase + "-prefixes.csv", 'rt', encoding='utf-8-sig') as f:
                csvReader = csv.reader(f)
                for i, row in enumerate(csvReader):
                    if i == 0:
                        header = dict((col,i) for i,col in enumerate(row))
                    else:
                        prefixes[row[header["prefix"]]] = row[header["URI"]]
            currentAction = "loading CSV defaults table"
            defaults = {}
            if os.path.exists(oimFileBase + "-defaults.csv"):
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
            for filename in os.listdir(_dir):
                filepath = os.path.join(_dir, filename)
                if "-facts" in filename and filepath.startswith(oimFileBase):
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
                                        if header[j].endswith("Value"):
                                            if col: # ignore empty columns (= null CSV value)
                                                fact["value"] = col
                                        else:
                                            fact[header[j]] = col
                                facts.append(fact)
            footnotes = []
            if os.path.exists(oimFileBase + "-footnotes.csv"):
                with io.open(oimFileBase + "-footnotes.csv", 'rt', encoding='utf-8-sig') as f:
                    csvReader = csv.reader(f)
                    for i, row in enumerate(csvReader):
                        if i == 0:
                            header = row
                        else:
                            footnotes.append(dict((header[j], col) for j, col in enumerate(row) if col))
        elif isXL:
            oimWb = load_workbook(oimFile, read_only=True, data_only=True)
            sheetNames = oimWb.get_sheet_names()
            if (not any(sheetName == "prefixes" for sheetName in sheetNames) or
                not any(sheetName == "dtsReferences" for sheetName in sheetNames) or
                not any("facts" in sheetName for sheetName in sheetNames)):
                if priorCWD: os.chdir(priorCWD)
                return None
            try:
                dtsReferences = []
                for i, row in oimWb["dtsReferences"]:
                    if i == 0:
                        header = [col.value for col in row]
                    else:
                        dtsReferences.append(dict((header[j], col.value) for j, col in enumerate(row)))
                prefixes = {}
                for i, row in oimWb["dtsReferences"]:
                    if i == 0:
                        header = dict((col.value,i) for i,col in enumerate(row))
                    else:
                        prefixes[row[header["prefix"]].value] = row[header["URI"].value]
                defaults = {}
                for i, row in oimW.get("defaults", ()):
                    if i == 0:
                        header = dict((col.value,i) for i,col in enumerate(row))
                        fileCol = header["file"]
                    else:
                        defaults[row[fileCol].value] = dict((header[j], col.value) for j, col in enumerate(row) if j != fileCol)
                facts = []
                _dir = os.path.dirpart(oimFileBase)
                for sheetName in sheetNames:
                    if sheetName == "facts" or "-facts" in sheetName:
                        for i, row in oimWb[sheetName]:
                            if i == 0:
                                header = [col.value for col in row]
                            else:
                                fact = {}
                                fact.update(tableDefaults)
                                for j, col in enumerate(row):
                                    if col.value is not None:
                                        if header[j].endswith("Value"):
                                            fact["value"] = str(col.value)
                                        else:
                                            fact[header[j]] = str(col.value)
                                facts.append(fact)
                footnotes = []
                for i, row in oimWb.get("footnotes", ()):
                    if i == 0:
                        header = dict((col.value,i) for i,col in enumerate(row) if col.value)
                    else:
                        footnotes.append(dict((header[j], col.value) for j, col in enumerate(row) if col.value))
            except Exception as ex:
                if priorCWD: os.chdir(priorCWD)
                return None
    
        ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl) # needs dimension defaults 
            
        # create the instance document
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
        for fact in facts:
            conceptQn = qname(fact["oim:concept"], prefixes)
            concept = modelXbrl.qnameConcepts.get(conceptQn)
            entityAsQn = qname(fact["oim:entity"], prefixes)
            if "oim:period" in fact:
                periodStart = fact["oim:period"]["start"]
                periodEnd = fact["oim:period"]["end"]
            else:
                periodStart = fact["oim:periodStart"]
                periodEnd = fact["oim:periodEnd"]
            cntxKey = ( # hashable context key
                ("periodType", concept.periodType),
                ("entity", entityAsQn),
                ("periodStart", periodStart),
                ("periodEnd", periodEnd)) + tuple(sorted(
                    (dimName, dimVal) 
                    for dimName, dimVal in fact.items()
                    if ":" in dimName and not dimName.startswith("oim:")))
            if cntxKey in cntxTbl:
                _cntx = cntxTbl[cntxKey]
            else:
                cntxId = 'c-{:02}'.format(len(cntxTbl) + 1)
                qnameDims = {}
                for dimName, dimVal in fact.items():
                    if ":" in dimName and not dimName.startswith("oim:"):
                        dimQname = qname(dimName, prefixes)
                        dimConcept = modelXbrl.qnameConcepts.get(dimQname)
                        if ":" in dimVal and dimVal.partition[':'][0] in prefixes:
                            mem = qname(dimVal, prefixes) # explicit dim
                        elif dimConcept.isTypedDimension:
                            # a modelObject xml element is needed for all of the instance functions to manage the typed dim
                            mem = addChild(modelXbrl.modelDocument, dimConcept.typedDomainElement.qname, text=dimVal, appendChild=False)
                        qnameDims[dimQname] = DimValuePrototype(modelXbrl, None, dimQname, mem, "segment")
                _cntx = modelXbrl.createContext(
                                        entityAsQn.namespaceURI,
                                        entityAsQn.localName,
                                        concept.periodType,
                                        None if concept.periodType == "instnat" else dateTime(periodStart, type=DATETIME),
                                        dateTime(periodEnd, type=DATETIME),
                                        None, # no dimensional validity checking (like formula does)
                                        qnameDims, [], [],
                                        id=cntxId)
                cntxTbl[cntxKey] = _cntx
            if "oim:unit" in fact:
                unitKey = fact["oim:unit"]
                if unitKey in unitTbl:
                    _unit = unitTbl[unitKey]
                else:
                    _mul, _sep, _div = unitKey.partition('/')
                    if _mul.startswith('('):
                        _mul = _mul[1:-1]
                    mulQns = [qname(u, prefixes) for u in _mul.split('*') if u]
                    if _div.startswith('('):
                        _div = _div[1:-1]
                    divQns = [qname(u, prefixes) for u in _div.split('*') if u]
                    unitId = 'u-{:02}'.format(len(unitTbl) + 1)
                    for _measures in mulQns, divQns:
                        for _measure in _measures:
                            addQnameValue(modelXbrl.modelDocument, _measure)
                    _unit = modelXbrl.createUnit(mulQns, divQns, id=unitId)
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
                if _unit is not None:
                    attrs["unitRef"] = _unit.id
                if "accuracy" in fact:
                    attrs["decimals"] = fact["accuracy"]
                    
            # is value a QName?
            if concept.baseXbrliType == "QName":
                addQnameValue(modelXbrl.modelDocument, qname(text.strip(), prefixes))
    
            f = modelXbrl.createFact(conceptQn, attributes=attrs, text=text)
            
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
                    
        
        #cntlr.addToLog("Completed in {0:.2} secs".format(time.time() - startedAt),
        #               messageCode="loadFromExcel:info")
    except Exception as ex:
        if ex is OIMException:
            modelXbrl.error(ex.code, ex.message, modelObject=modelXbrl, **ex.msgArgs)
        else:
            modelXbrl.error("Error while %(action)s, error %(error)s",
                            modelObject=modelXbrl, action=currentAction, error=ex)
    
    if priorCWD:
        os.chdir(priorCWD) # restore prior current working directory
    return modelXbrl.modelDocument

def oimLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    if not any(filepath.endswith(suffix) for suffix in (".csv", ".json", ".xslx", ".xls")):
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
        if not excelFile:
            return False
        cntlr.config["outputInstanceDir"] = os.path.dirname(instanceFile)
        cntlr.saveConfig()
        if instanceFile:
            modelXbrl.modelDocument.save(saveToFile(instanceFile), updateFileHistory=False)
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
    'ModelDocument.PullLoader': oimLoader,
    'CntlrWinMain.Xbrl.Loaded': guiXbrlLoaded,
    'CntlrCmdLine.Options': excelLoaderOptionExtender,
    'CntlrCmdLine.Xbrl.Loaded': cmdLineXbrlLoaded
}
