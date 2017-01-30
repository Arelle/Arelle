# -*- coding: utf-8 -*-

'''
saveLoadableOIM.py is an example of a plug-in that will save a re-loadable JSON or CSV instance.

(c) Copyright 2015 Mark V Systems Limited, All rights reserved.
'''
import sys, os, io, time, regex as re, json, csv
from decimal import Decimal
from math import isinf, isnan
from collections import defaultdict, OrderedDict
from arelle import ModelDocument, XbrlConst
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import (qname, QName, DateTime, YearMonthDuration, 
                               dayTimeDuration, DayTimeDuration, yearMonthDayTimeDuration, Time,
                               gYearMonth, gMonthDay, gYear, gMonth, gDay)
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ValidateXbrlCalcs import inferredDecimals
from arelle.XmlUtil import dateunionValue, elementIndex, xmlstring
from collections import defaultdict

nsOim = "http://www.xbrl.org/WGWD/YYYY-MM-DD/oim"
qnOimConceptAspect = qname(nsOim, "xbrl:concept")
qnOimLangAspect = qname(nsOim, "xbrl:language")
qnOimTupleParentAspect = qname(nsOim, "xbrl:tupleParent")
qnOimTupleOrderAspect = qname(nsOim, "xbrl:tupleOrder")
qnOimPeriodStartAspect = qname(nsOim, "xbrl:periodStart")
qnOimPeriodEndAspect = qname(nsOim, "xbrl:periodEnd")
qnOimEntityAspect = qname(nsOim, "xbrl:entity")
qnOimUnitAspect = qname(nsOim, "xbrl:unit")

ONE = Decimal(1)
TEN = Decimal(10)
NILVALUE = "nil"
SCHEMA_LB_REFS = {qname("{http://www.xbrl.org/2003/linkbase}schemaRef"), 
                  qname("{http://www.xbrl.org/2003/linkbase}linkbaseRef")}
ROLE_REFS = {qname("{http://www.xbrl.org/2003/linkbase}roleRef"), 
             qname("{http://www.xbrl.org/2003/linkbase}arcroleRef")}

baseTypes = {
    "integer": "decimal",
    "long": "decimal",
    "int": "decimal",
    "short": "decimal",
    "byte": "decimal",
    "nonNegativeInteger": "decimal",
    "positiveInteger": "decimal",
    "unsignedLong": "decimal",
    "unsignedInt": "decimal",
    "unsignedShort": "decimal",
    "unsignedByte": "decimal",
    "nonPositiveInteger": "decimal",
    "negativeInteger": "decimal",
    "normalizedString": "string",
    "token": "string",
    "language": "string",
    "Name": "string",
    "NMTOKEN": "string",
    "xml": "string",
    "html": "string",
    "json": "string",
    # xml schema 1.1 alias types supported by W3C metadata
    "any": "anyAtomicType",
    "binary": "base64Binary",
    "datetime": "dataTime"         
    }

if sys.version[0] >= '3':
    csvOpenMode = 'w'
    csvOpenNewline = ''
else:
    csvOpenMode = 'wb' # for 2.7
    csvOpenNewline = None
    
def saveLoadableOIM(modelXbrl, oimFile):
    
    isJSON = oimFile.endswith(".json")
    isCSV = oimFile.endswith(".csv")
    isXL = oimFile.endswith(".xlsx")
    isCSVorXL = isCSV or isXL
    if not isJSON and not isCSVorXL:
        return

    namespacePrefixes = {nsOim: "xbrl"}
    prefixNamespaces = {"xbrl": nsOim}
    def compileQname(qname):
        if qname.namespaceURI not in namespacePrefixes:
            namespacePrefixes[qname.namespaceURI] = qname.prefix or ""
            
    aspectsDefined = {
        qnOimConceptAspect,
        qnOimEntityAspect,
        qnOimPeriodStartAspect,
        qnOimPeriodEndAspect}
            
    def oimValue(object, decimals=None):
        if isinstance(object, QName):
            if object.namespaceURI not in namespacePrefixes:
                if object.prefix:
                    namespacePrefixes[object.namespaceURI] = object.prefix
                else:
                    _prefix = "_{}".format(sum(1 for p in namespacePrefixes if p.startswith("_")))
                    namespacePrefixes[object.namespaceURI] = _prefix
            return "{}:{}".format(namespacePrefixes[object.namespaceURI], object.localName)
        if isinstance(object, Decimal):
            try:
                if isinf(object):
                    return "-INF" if object < 0 else "INF"
                elif isnan(num):
                    return "NaN"
                else:
                    if object == object.to_integral():
                        object = object.quantize(ONE) # drop any .0
                    return "{}".format(object)
            except:
                return str(object)
        if isinstance(object, bool):
            return "true" if object else "false"
        if isinstance(object, (DateTime, YearMonthDuration, DayTimeDuration, Time,
                               gYearMonth, gMonthDay, gYear, gMonth, gDay)):
            return str(object)
        return object
    
    def oimPeriodValue(cntx):
        if cntx.isForeverPeriod:
            return OrderedDict() # not supported
        elif cntx.isStartEndPeriod:
            s = cntx.startDatetime
            e = cntx.endDatetime
        else: # instant
            s = e = cntx.instantDatetime
        return OrderedDict(((str(qnOimPeriodStartAspect), "{0:04n}-{1:02n}-{2:02n}T{3:02n}:{4:02n}:{5:02n}".format(
                             s.year, s.month, s.day, s.hour, s.minute, s.second)),
                            (str(qnOimPeriodEndAspect),   "{0:04n}-{1:02n}-{2:02n}T{3:02n}:{4:02n}:{5:02n}".format(
                             e.year, e.month, e.day, e.hour, e.minute, e.second))))
              
    hasId = False
    hasTuple = False
    hasType = True
    hasLang = False
    hasUnits = False
    hasNumeric = False 
    
    footnotesRelationshipSet = ModelRelationshipSet(modelXbrl, "XBRL-footnotes")
    factBaseTypes = set()
            
    #compile QNames in instance for OIM
    for fact in modelXbrl.factsInInstance:
        if (fact.id or fact.isTuple or 
            footnotesRelationshipSet.toModelObject(fact) or
            (isCSVorXL and footnotesRelationshipSet.fromModelObject(fact))):
            hasId = True
        concept = fact.concept
        if concept is not None:
            if concept.isNumeric:
                hasNumeric = True
            if concept.baseXbrliType in ("string", "normalizedString", "token") and fact.xmlLang:
                hasLang = True
            _baseXsdType = concept.baseXsdType
            if _baseXsdType == "XBRLI_DATEUNION":
                if getattr(fact.xValue, "dateOnly", False):
                    _baseXsdType = "date"
                else:
                    _baseXsdType = "dateTime"
            factBaseTypes.add(baseTypes.get(_baseXsdType,_baseXsdType))
        compileQname(fact.qname)
        if hasattr(fact, "xValue") and isinstance(fact.xValue, QName):
            compileQname(fact.xValue)
        unit = fact.unit
        if unit is not None:
            hasUnits = True
        if fact.modelTupleFacts:
            hasTuple = True
            
    entitySchemePrefixes = {}
    for cntx in modelXbrl.contexts.values():
        if cntx.entityIdentifierElement is not None:
            scheme = cntx.entityIdentifier[0]
            if scheme not in entitySchemePrefixes:
                if not entitySchemePrefixes: # first one is just scheme
                    if scheme == "http://www.sec.gov/CIK":
                        _schemePrefix = "cik"
                    elif scheme == "http://standard.iso.org/iso/17442":
                        _schemePrefix = "lei"
                    else:
                        _schemePrefix = "scheme"
                else:
                    _schemePrefix = "scheme{}".format(len(entitySchemePrefixes) + 1)
                entitySchemePrefixes[scheme] = _schemePrefix
                namespacePrefixes[scheme] = _schemePrefix
        for dim in cntx.qnameDims.values():
            compileQname(dim.dimensionQname)
            aspectsDefined.add(dim.dimensionQname)
            if dim.isExplicit:
                compileQname(dim.memberQname)
                
    for unit in modelXbrl.units.values():
        if unit is not None:
            for measures in unit.measures:
                for measure in measures:
                    compileQname(measure)
                    
    if XbrlConst.xbrli in namespacePrefixes and namespacePrefixes[XbrlConst.xbrli] != "xbrli":
        namespacePrefixes[XbrlConst.xbrli] = "xbrli" # normalize xbrli prefix
        namespacePrefixes[XbrlConst.xsd] = "xsd"

    if hasLang: aspectsDefined.add(qnOimLangAspect)
    if hasTuple: 
        aspectsDefined.add(qnOimTupleParentAspect)
        aspectsDefined.add(qnOimTupleOrderAspect)
    if hasUnits: aspectsDefined.add(qnOimUnitAspect)
                    
    # compile footnotes and relationships
    '''
    factRelationships = []
    factFootnotes = []
    for rel in modelXbrl.relationshipSet(modelXbrl, "XBRL-footnotes").modelRelationships:
        oimRel = {"linkrole": rel.linkrole, "arcrole": rel.arcrole}
        factRelationships.append(oimRel)
        oimRel["fromIds"] = [obj.id if obj.id 
                             else elementChildSequence(obj)
                             for obj in rel.fromModelObjects]
        oimRel["toIds"] = [obj.id if obj.id
                           else elementChildSequence(obj)
                           for obj in rel.toModelObjects]
        _order = rel.arcElement.get("order")
        if _order is not None:
            oimRel["order"] = _order
        for obj in rel.toModelObjects:
            if isinstance(obj, ModelResource): # footnote
                oimFootnote = {"role": obj.role,
                               "id": obj.id if obj.id
                                     else elementChildSequence(obj),
                                # value needs work for html elements and for inline footnotes
                               "value": xmlstring(obj, stripXmlns=True)}
                if obj.xmlLang:
                    oimFootnote["lang"] = obj.xmlLang
                factFootnotes.append(oimFootnote)
                oimFootnote
    '''
    dtsReferences = [
        {"type": "schema" if doc.type == ModelDocument.Type.SCHEMA
                 else "linkbase" if doc.type == ModelDocument.Type.LINKBASE
                 else "other",
         "href": doc.uri}
        for doc,ref in sorted(modelXbrl.modelDocument.referencesDocument.items(),
                              key=lambda _item:_item[0].uri)
        if ref.referringModelObject.qname in SCHEMA_LB_REFS
        ] + [{"type": refType,
              "href": refElt.get("{http://www.w3.org/1999/xlink}href")}
             for refType in ("role", "arcrole")
             for refElt in sorted(modelXbrl.modelDocument.xmlRootElement.iterchildren(
                                    "{{http://www.xbrl.org/2003/linkbase}}{}Ref".format(refType)),
                                  key=lambda elt:elt.get(refType+"URI")
                                  )
        ]
            
    def factFootnotes(fact):
        footnotes = []
        for footnoteRel in footnotesRelationshipSet.fromModelObject(fact):
            footnote = OrderedDict((("group", footnoteRel.linkrole),
                                    ("footnoteType", footnoteRel.arcrole)))
            footnotes.append(footnote)
            if isCSVorXL:
                footnote["factId"] = fact.id if fact.id else "f{}".format(fact.objectIndex)
            toObj = footnoteRel.toModelObject
            if isinstance(toObj, ModelFact):
                footnote["factRef"] = toObj.id if toObj.id else "f{}".format(toObj.objectIndex)
            else:
                footnote["footnote"] = toObj.viewText()
                if toObj.xmlLang:
                    footnote["language"] = toObj.xmlLang
        footnotes.sort(key=lambda f:(f["group"],f.get("factId",f.get("factRef")),f.get("language")))
        return footnotes

    def factAspects(fact): 
        oimFact = OrderedDict()
        aspects = OrderedDict()
        if hasId and fact.id:
            if fact.isTuple:
                oimFact["tupleId"] = fact.id
            else:
                oimFact["id"] = fact.id
        elif (fact.isTuple or 
              footnotesRelationshipSet.toModelObject(fact) or
              (isCSVorXL and footnotesRelationshipSet.fromModelObject(fact))):
            oimFact["id"] = "f{}".format(fact.objectIndex)
        parent = fact.getparent()
        concept = fact.concept
        aspects[str(qnOimConceptAspect)] = oimValue(concept.qname)
        _csvType = "Value"
        if not fact.isTuple:
            if concept is not None:
                _baseXsdType = concept.baseXsdType
                if _baseXsdType == "XBRLI_DATEUNION":
                    if getattr(fact.xValue, "dateOnly", False):
                        _baseXsdType = "date"
                    else:
                        _baseXsdType = "dateTime"
                _csvType = baseTypes.get(_baseXsdType,_baseXsdType) + "Value"
                if concept.baseXbrliType in ("stringItemType", "normalizedStringItemType") and fact.xmlLang:
                    aspects[str(qnOimLangAspect)] = fact.xmlLang
        if fact.isItem:
            if fact.isNil:
                _value = None
            else:
                _inferredDecimals = inferredDecimals(fact)
                _value = oimValue(fact.xValue, _inferredDecimals)
            oimFact["value"] = _value
            if fact.concept is not None and fact.concept.isNumeric:
                _numValue = fact.xValue
                if isinstance(_numValue, Decimal) and not isinf(_numValue) and not isnan(_numValue):
                    if _numValue == _numValue.to_integral():
                        _numValue = int(_numValue)
                    else:
                        _numValue = float(_numValue)
                if not fact.isNil:
                    if isinf(_inferredDecimals):
                        if isJSON: _accuracy = "infinity"
                        elif isCSVorXL: _accuracy = "INF"
                    else:
                        _accuracy = _inferredDecimals
                    oimFact["accuracy"] = _accuracy
        oimFact["aspects"] = aspects
        cntx = fact.context
        if cntx is not None:
            if cntx.entityIdentifierElement is not None:
                aspects[str(qnOimEntityAspect)] = oimValue(qname(*cntx.entityIdentifier))
            if cntx.period is not None:
                aspects.update(oimPeriodValue(cntx))
            for _qn, dim in sorted(cntx.qnameDims.items(), key=lambda item: item[0]):
                if dim.isExplicit:
                    dimVal = oimValue(dim.memberQname)
                else: # typed
                    if dim.typedMember.get("{http://www.w3.org/2001/XMLSchema-instance}nil") in ("true", "1"):
                        dimVal = None
                    else:
                        dimVal = dim.typedMember.stringValue
                aspects[str(dim.dimensionQname)] = dimVal
        unit = fact.unit
        if unit is not None:
            _mMul, _mDiv = unit.measures
            _sMul = '*'.join(oimValue(m) for m in sorted(_mMul, key=lambda m: oimValue(m)))
            if _mDiv:
                _sDiv = '*'.join(oimValue(m) for m in sorted(_mDiv, key=lambda m: oimValue(m)))
                if len(_mDiv) > 1:
                    if len(_mMul) > 1:
                        _sUnit = "({})/({})".format(_sMul,_sDiv)
                    else:
                        _sUnit = "{}/({})".format(_sMul,_sDiv)
                else:
                    if len(_mMul) > 1:
                        _sUnit = "({})/{}".format(_sMul,_sDiv)
                    else:
                        _sUnit = "{}/{}".format(_sMul,_sDiv)
            else:
                _sUnit = _sMul
            aspects[str(qnOimUnitAspect)] = _sUnit
        if parent.qname != XbrlConst.qnXbrliXbrl:
            aspects[str(qnOimTupleParentAspect)] = parent.id if parent.id else "f{}".format(parent.objectIndex)
            aspects[str(qnOimTupleOrderAspect)] = elementIndex(fact)
            
        if isJSON:
            _footnotes = factFootnotes(fact)
            if _footnotes:
                oimFact["footnotes"] = _footnotes
        return oimFact
    
    prefixes = OrderedDict((p,ns) for ns, p in sorted(namespacePrefixes.items(), 
                                                      key=lambda item: item[1]))
    
    if isJSON:
        # save JSON
        
        oimReport = OrderedDict() # top level of oim json output
            
        oimFacts = []
        oimReport["documentType"] = nsOim.replace("/oim", "/xbrl-json")
        oimReport["prefixes"] = prefixes
        oimReport["dtsReferences"] = dtsReferences
        oimReport["facts"] = oimFacts
            
        def saveJsonFacts(facts, oimFacts, parentFact):
            for fact in facts:
                oimFact = factAspects(fact)
                oimFacts.append(oimFact)
                if fact.modelTupleFacts:
                    saveJsonFacts(fact.modelTupleFacts, oimFacts, fact)
                
        saveJsonFacts(modelXbrl.facts, oimFacts, None)
            
        with open(oimFile, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(oimReport, indent=1))

    elif isCSVorXL:
        # save CSV
        
        aspectQnCol = {}
        aspectsHeader = []
        factsColumns = []
        
        def addAspectQnCol(aspectQn):
            aspectQnCol[str(aspectQn)] = len(aspectsHeader)
            _aspectQn = oimValue(aspectQn) 
            aspectsHeader.append(_aspectQn)
            _colName = _aspectQn.replace("xbrl:", "")
            _colDataType = {"id": "Name",
                            "concept": "QName",
                            "value": "string",
                            "accuracy": "decimal",
                            "entity": "QName",
                            "periodStart": "dateTime",
                            "periodEnd": "dateTime",
                            "unit": "string",
                            "tupleId": "Name",
                            "tupleParent": "Name",
                            "tupleOrder": "integer"
                            }.get(_colName, "string")
            col = OrderedDict((("name", _colName),
                               ("datatype", _colDataType)))
            if _aspectQn == "value":
                col["http://xbrl.org/YYYY/model#simpleFactAspects"] = {}
            elif _aspectQn == "tupleId":
                col["http://xbrl.org/YYYY/model#tupleFactAspects"] = {}
                col["http://xbrl.org/YYYY/model#tupleReferenceId"] = "true"
            else:
                col["http://xbrl.org/YYYY/model#columnAspect"] = _aspectQn
            factsColumns.append(col)
            
        # pre-ordered aspect columns
        #if hasId:
        #    addAspectQnCol("id")
        addAspectQnCol(qnOimConceptAspect)
        addAspectQnCol("value")
        if hasNumeric:
            addAspectQnCol("accuracy")
        if hasTuple:
            addAspectQnCol("tupleId")
            addAspectQnCol(qnOimTupleParentAspect)
            addAspectQnCol(qnOimTupleOrderAspect)
        if qnOimEntityAspect in aspectsDefined:
            addAspectQnCol(qnOimEntityAspect)
        if qnOimPeriodStartAspect in aspectsDefined:
            addAspectQnCol(qnOimPeriodStartAspect)
            addAspectQnCol(qnOimPeriodEndAspect)
        if qnOimUnitAspect in aspectsDefined:
            addAspectQnCol(qnOimUnitAspect)
        for aspectQn in sorted(aspectsDefined, key=lambda qn: str(qn)):
            if aspectQn.namespaceURI != nsOim:
                addAspectQnCol(aspectQn) 
        
        def aspectCols(fact):
            cols = [None for i in range(len(aspectsHeader))]
            def setColValues(aspects):
                for aspectQn, aspectValue in aspects.items():
                    if isinstance(aspectValue, dict):
                        setColValues(aspectValue)
                    elif aspectQn in aspectQnCol:
                        if aspectValue is None:
                            _aspectValue = "#nil"
                        elif aspectValue == "":
                            _aspectValue = "#empty"
                        elif isinstance(aspectValue, str) and aspectValue.startswith("#"):
                            _aspectValue = "#" + aspectValue
                        else:
                            _aspectValue = aspectValue
                        cols[aspectQnCol[aspectQn]] = _aspectValue
            setColValues(factAspects(fact))
            return cols
        
        # metadata
        csvTables = []
        csvMetadata = OrderedDict((("@context", "http://www.w3.org/ns/csvw"),
                                   ("http://xbrl.org/YYYY/model#metadata",
                                    OrderedDict((("documentType", "http://xbrl.org/YYYY/xbrl-csv"),
                                                 ("dtsReferences", dtsReferences),
                                                 ("prefixes", prefixes)))),
                                   ("tables", csvTables)))
        
        _open = _writerow = _close = None
        _tableinfo = {}
        if isCSV:
            if oimFile.endswith("-facts.csv"): # strip -facts.csv if a prior -facts.csv file was chosen
                _baseURL = oimFile[:-10]
            elif oimFile.endswith(".csv"):
                _baseURL = oimFile[:-4]
            else:
                _baseURL = oimFile
            _csvinfo = {} # open file, writer
            def _open(filesuffix, tabname):
                _filename = _tableinfo["url"] = _baseURL + filesuffix
                _csvinfo["file"] = open(_filename, csvOpenMode, newline=csvOpenNewline, encoding='utf-8-sig')
                _csvinfo["writer"] = csv.writer(_csvinfo["file"], dialect="excel")
            def _writerow(row, header=False):
                _csvinfo["writer"].writerow(row)
            def _close():
                _csvinfo["file"].close()
                _csvinfo.clear()
        elif isXL:
            headerWidths = {"href": 100, "xbrl:concept": 70, "accuracy": 8, "language": 9, "URI": 80,
                            "value": 60, 
                            "group": 60, "footnoteType": 40, "footnote": 70, "column": 20,
                            'conceptAspect': 40, 'tuple': 20, 'simpleFact': 20}
            from openpyxl import Workbook
            from openpyxl.writer.write_only import WriteOnlyCell
            from openpyxl.styles import Font, PatternFill, Border, Alignment, Color, fills, Side
            from openpyxl.worksheet.dimensions import ColumnDimension
            hdrCellFill = PatternFill(patternType=fills.FILL_SOLID, fgColor=Color("00FFBF5F")) # Excel's light orange fill color = 00FF990
            workbook = Workbook()
            # remove pre-existing worksheets
            while len(workbook.worksheets)>0:
                workbook.remove_sheet(workbook.worksheets[0])
            _xlinfo = {} # open file, writer
            def _open(filesuffix, tabname):
                _tableinfo["url"] = tabname
                _xlinfo["ws"] = workbook.create_sheet(title=tabname)
            def _writerow(rowvalues, header=False):
                row = []
                _ws = _xlinfo["ws"]
                for i, v in enumerate(rowvalues):
                    cell = WriteOnlyCell(_ws, value=v)
                    if header:
                        cell.fill = hdrCellFill
                        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                        colLetter = chr(ord('A') + i)
                        _ws.column_dimensions[colLetter] = ColumnDimension(_ws, customWidth=True)
                        _ws.column_dimensions[colLetter].width = headerWidths.get(v, 20)                                   

                    else:
                        cell.alignment = Alignment(horizontal="right" if isinstance(v, _NUM_TYPES)
                                                   else "center" if isinstance(v, bool)
                                                   else "left", 
                                                   vertical="top",
                                                   wrap_text=isinstance(v, str))
                    row.append(cell)
                _ws.append(row)
            def _close():
                _xlinfo.clear()

        
        # save facts
        _open("-facts.csv", "facts")
        _writerow(aspectsHeader, header=True)
        
        def saveCSVfacts(facts):
            for fact in facts:
                _writerow(aspectCols(fact))
                saveCSVfacts(fact.modelTupleFacts)
        saveCSVfacts(modelXbrl.facts)
        _close()
        factsTableSchema = OrderedDict((("columns",factsColumns),))
        csvTables.append(OrderedDict((("url",_tableinfo["url"]),
                                      ("http://xbrl.org/YYYY/model#tableType", "fact"),
                                      ("tableSchema",factsTableSchema))))
        
        # save footnotes
        if footnotesRelationshipSet.modelRelationships:
            _open("-footnotes.csv", "footnotes")
            cols = ("group", "footnoteType", "factId", "factRef", "footnote", "language")
            _writerow(cols, header=True)
            def saveCSVfootnotes(facts):
                for fact in facts:
                    for _footnote in factFootnotes(fact):
                        _writerow(tuple((_footnote.get(col,"") for col in cols)))
                        saveCSVfootnotes(fact.modelTupleFacts)
            saveCSVfootnotes(modelXbrl.facts)
            _close()
            footnoteTableSchema = OrderedDict((("columns",[OrderedDict((("name","group"),("datatype","anyURI"))),
                                                           OrderedDict((("name","footnoteType"),("datatype","Name"))),
                                                           OrderedDict((("name","factId"),("datatype","Name"))),
                                                           OrderedDict((("name","factRef"),("datatype","Name"))),
                                                           OrderedDict((("name","footnote"),("datatype","string"))),
                                                           OrderedDict((("name","language"),("datatype","language")))]),))
            csvTables.append(OrderedDict((("url",_tableinfo["url"]),
                                          ("http://xbrl.org/YYYY/model#tableType", "footnote"),
                                          ("tableSchema",footnoteTableSchema))))
            
        # save metadata
        if isCSV:
            with open(_baseURL + "-metadata.json", "w", encoding="utf-8") as fh:
                fh.write(json.dumps(csvMetadata, ensure_ascii=False, indent=1, sort_keys=False))
        elif isXL:
            _open(None, "metadata")
            hasColumnAspect = hasSimpleFact = hasTupleFact = False
            for table in csvTables:
                tablename = table["url"]
                for column in table["tableSchema"]["columns"]:
                    if "http://xbrl.org/YYYY/model#columnAspect" in column:
                        hasColumnAspect = True
                    if "http://xbrl.org/YYYY/model#simpleFactAspects" in column:
                        hasSimpleFact = True
                    if "http://xbrl.org/YYYY/model#tupleAspects" in column:
                        hasTupleFact = True
            metadataCols = ["table", "column", "datatype"]
            if hasColumnAspect:
                metadataCols.append("columnAspect")
            if hasSimpleFact:
                metadataCols.append("simpleFact")
            if hasTupleFact:
                metadataCols.append("tuple")
            _writerow(metadataCols, header=True)
            for table in csvTables:
                tablename = table["url"]
                for column in table["tableSchema"]["columns"]:
                    row = [tablename, column["name"], column["datatype"]]
                    if hasColumnAspect:
                        colAspect = column.get("http://xbrl.org/YYYY/model#columnAspect")
                        if isinstance(colAspect, str):
                            row.append(colAspect)
                        elif isinstance(colAspect, dict):
                            row.append("\n".join("{} [{}]".format(k, ", ".join(_v for _v in v))
                                                 for k, v in dict.items()))
                        else:
                            row.append(None)
                    if hasSimpleFact:
                        row.append("\u221a" if "http://xbrl.org/YYYY/model#simpleFactAspects" in column else None)
                    if hasTupleFact:
                        row.append("\u221a" if "http://xbrl.org/YYYY/model#tupleAspects" in column else None)
                    _writerow(row)
            _close()
                
        if isXL:
            workbook.save(oimFile)

def saveLoadableOIMMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save Loadable OIM", 
                     underline=0, 
                     command=lambda: saveLoadableOIMMenuCommand(cntlr) )

def saveLoadableOIMMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if (cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None or cntlr.modelManager.modelXbrl.modelDocument is None or
        cntlr.modelManager.modelXbrl.modelDocument.type not in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL)):
        return
        # get file name into which to save log file while in foreground thread
    oimFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save Loadable OIM file"),
            initialdir=cntlr.config.setdefault("loadableExcelFileDir","."),
            filetypes=[(_("JSON file .json"), "*.json"), (_("CSV file .csv"), "*.csv"), (_("XLSX file .xlsx"), "*.xlsx")],
            defaultextension=".json")
    if not oimFile:
        return False
    import os
    cntlr.config["loadableOIMFileDir"] = os.path.dirname(oimFile)
    cntlr.saveConfig()

    import threading
    thread = threading.Thread(target=lambda 
                                  _modelXbrl=cntlr.modelManager.modelXbrl,
                                  _oimFile=oimFile: 
                                        saveLoadableOIM(_modelXbrl, _oimFile))
    thread.daemon = True
    thread.start()
    
def saveLoadableOIMCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options with a save DTS option
    parser.add_option("--saveLoadableOIM", 
                      action="store", 
                      dest="saveLoadableOIM", 
                      help=_("Save Loadable OIM file (JSON, CSV or XLSX)"))

def saveLoadableOIMCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    oimFile = getattr(options, "saveLoadableOIM", None)
    if oimFile:
        if (modelXbrl is None or
            modelXbrl.modelDocument.type not in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL)):
            cntlr.addToLog("No XBRL instance has been loaded.")
            return
        try:
            saveLoadableOIM(modelXbrl, oimFile)
        except Exception as ex:
            cntlr.addToLog("Exception saving OIM {}".format(ex))

__pluginInfo__ = {
    'name': 'Save Loadable OIM',
    'version': '0.9',
    'description': "This plug-in saves XBRL in OIM JSON, CSV or XLSX that can be re-loaded per se.",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2015 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveLoadableOIMMenuEntender,
    'CntlrCmdLine.Options': saveLoadableOIMCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': saveLoadableOIMCommandLineXbrlRun,
}
