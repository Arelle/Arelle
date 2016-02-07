# -*- coding: utf-8 -*-

'''
saveLoadableOIM.py is an example of a plug-in that will save a re-loadable JSON or CSV instance.

(c) Copyright 2015 Mark V Systems Limited, All rights reserved.
'''
import sys, os, io, time, re, json, csv
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

nsOim = "http://www.xbrl.org/DPWD/2016-01-13/oim"
qnOimConceptAspect = qname(nsOim, "oim:concept")
qnOimTypeAspect = qname(nsOim, "oim:type")
qnOimLangAspect = qname(nsOim, "oim:language")
qnOimTupleParentAspect = qname(nsOim, "oim:tupleParent")
qnOimTupleOrderAspect = qname(nsOim, "oim:tupleOrder")
qnOimPeriodAspect = qname(nsOim, "oim:period")
qnOimPeriodStartAspect = qname(nsOim, "oim:periodStart")
qnOimPeriodDurationAspect = qname(nsOim, "oim:periodDuration")
qnOimEntityAspect = qname(nsOim, "oim:entity")
qnOimUnitAspect = qname(nsOim, "oim:unit")
qnOimUnitNumeratorsAspect = qname(nsOim, "oim:unitNumerators")
qnOimUnitDenominatorsAspect = qname(nsOim, "oim:unitDenominators")

ONE = Decimal(1)
TEN = Decimal(10)
NILVALUE = "nil"
SCHEMA_LB_REFS = {qname("{http://www.xbrl.org/2003/linkbase}schemaRef"), 
                  qname("{http://www.xbrl.org/2003/linkbase}linkbaseRef")}
ROLE_REFS = {qname("{http://www.xbrl.org/2003/linkbase}roleRef"), 
             qname("{http://www.xbrl.org/2003/linkbase}arcroleRef")}

if sys.version[0] >= '3':
    csvOpenMode = 'w'
    csvOpenNewline = ''
else:
    csvOpenMode = 'wb' # for 2.7
    csvOpenNewline = None
    
def saveLoadableOIM(modelXbrl, oimFile):
    
    isJSON = oimFile.endswith(".json")
    isCSV = oimFile.endswith(".csv")

    namespacePrefixes = {}
    def compileQname(qname):
        if qname.namespaceURI not in namespacePrefixes:
            namespacePrefixes[qname.namespaceURI] = qname.prefix or ""
            
    aspectsDefined = {
        qnOimConceptAspect,
        qnOimEntityAspect,
        qnOimTypeAspect}
    if isJSON:
        aspectsDefined.add(qnOimPeriodAspect)
    elif isCSV:
        aspectsDefined.add(qnOimPeriodStartAspect)
        aspectsDefined.add(qnOimPeriodDurationAspect)
            
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
            return object
        if isinstance(object, (DateTime, YearMonthDuration, DayTimeDuration, Time,
                               gYearMonth, gMonthDay, gYear, gMonth, gDay)):
            return str(object)
        return object
    
    def oimPeriodValue(cntx):
        if cntx.isForeverPeriod:
            if isCSV:
                return "0000-01-01T00:00:00/P9999Y"
            return "forever"
        elif cntx.isStartEndPeriod:
            d = cntx.startDatetime
            duration = yearMonthDayTimeDuration(cntx.startDatetime, cntx.endDatetime)
        else: # instant
            d = cntx.instantDatetime
            duration = "PT0S"
        return "{0:04n}-{1:02n}-{2:02n}T{3:02n}:{4:02n}:{5:02n}/{6}".format(
                d.year, d.month, d.day, d.hour, d.minute, d.second,
                duration)
              
    hasId = False
    hasTuple = False
    hasType = True
    hasLang = False
    hasUnits = False      
    hasUnitMulMeasures = False
    hasUnitDivMeasures = False
    
    footnotesRelationshipSet = ModelRelationshipSet(modelXbrl, "XBRL-footnotes")
            
    #compile QNames in instance for OIM
    for fact in modelXbrl.factsInInstance:
        if (fact.id or fact.isTuple or 
            footnotesRelationshipSet.toModelObject(fact) or
            (isCSV and footnotesRelationshipSet.fromModelObject(fact))):
            hasId = True
        concept = fact.concept
        if concept is not None:
            if concept.baseXbrliType in ("string", "normalizedString", "token") and fact.xmlLang:
                hasLang = True
        compileQname(fact.qname)
        if hasattr(fact, "xValue") and isinstance(fact.xValue, QName):
            compileQname(fact.xValue)
        unit = fact.unit
        if unit is not None:
            hasUnits = True
            if unit.measures[0]:
                hasUnitMulMeasures = True
            if unit.measures[1]:
                hasUnitDivMeasures = True
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
            if unit.measures[0]:
                aspectsDefined.add(qnOimUnitNumeratorsAspect)
            if unit.measures[1]:
                aspectsDefined.add(qnOimUnitDenominatorsAspect)
                    
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
        for doc,ref in modelXbrl.modelDocument.referencesDocument.items()
        if ref.referringModelObject.qname in SCHEMA_LB_REFS]
    
    '''    
    roleTypes = [
        {"type": "role" if ref.referringModelObject.localName == "roleRef" else "arcroleRef",
         "href": ref.referringModelObject["href"]}
        for doc,ref in modelXbrl.modelDocument.referencesDocument.items()
        if ref.referringModelObject.qname in ROLE_REFS]
    '''
            
    def factFootnotes(fact):
        footnotes = []
        for footnoteRel in footnotesRelationshipSet.fromModelObject(fact):
            footnote = OrderedDict((("group", footnoteRel.arcrole),))
            footnotes.append(footnote)
            if isCSV:
                footnote["factId"] = fact.id if fact.id else "f{}".format(fact.objectIndex)
            toObj = footnoteRel.toModelObject
            if isinstance(toObj, ModelFact):
                footnote["factRef"] = toObj.id if toObj.id else "f{}".format(toObj.objectIndex)
            else:
                footnote["footnoteType"] = toObj.role
                footnote["footnote"] = xmlstring(toObj, stripXmlns=True, contentsOnly=True, includeText=True)
                if toObj.xmlLang:
                    footnote["language"] = toObj.xmlLang
        return footnotes

    def factAspects(fact): 
        aspects = OrderedDict()
        if hasId and fact.id:
            aspects["id"] = fact.id
        elif (fact.isTuple or 
              footnotesRelationshipSet.toModelObject(fact) or
              (isCSV and footnotesRelationshipSet.fromModelObject(fact))):
            aspects["id"] = "f{}".format(fact.objectIndex)
        parent = fact.getparent()
        concept = fact.concept
        if not fact.isTuple:
            if concept is not None:
                _baseXsdType = concept.baseXsdType
                if _baseXsdType == "XBRLI_DATEUNION":
                    if getattr(fact.xValue, "dateOnly", False):
                        _baseXsdType = "date"
                    else:
                        _baseXsdType = "dateTime"
                aspects["baseType"] = "xs:{}".format(_baseXsdType)
                if concept.baseXbrliType in ("string", "normalizedString", "token") and fact.xmlLang:
                    aspects[qnOimLangAspect] = fact.xmlLang
                aspects[qnOimTypeAspect] = concept.baseXbrliType
        if fact.isItem:
            if fact.isNil:
                _value = None
                _strValue = "nil"
            else:
                _inferredDecimals = inferredDecimals(fact)
                _value = oimValue(fact.xValue, _inferredDecimals)
                _strValue = str(_value)
            if not isCSV:
                aspects["value"] = _strValue
            if fact.concept is not None and fact.concept.isNumeric:
                _numValue = fact.xValue
                if isinstance(_numValue, Decimal) and not isinf(_numValue) and not isnan(_numValue):
                    if _numValue == _numValue.to_integral():
                        _numValue = int(_numValue)
                    else:
                        _numValue = float(_numValue)
                aspects["numericValue"] = _numValue
                if not fact.isNil:
                    if isinf(_inferredDecimals):
                        if isJSON: _accuracy = "infinity"
                        elif isCSV: _accuracy = "INF"
                    else:
                        _accuracy = _inferredDecimals
                    aspects["accuracy"] = _inferredDecimals
            elif isinstance(_value, bool):
                aspects["booleanValue"] = _value
            elif isCSV:
                aspects["stringValue"] = _strValue
        aspects[qnOimConceptAspect] = oimValue(fact.qname)
        cntx = fact.context
        if cntx is not None:
            if cntx.entityIdentifierElement is not None:
                aspects[qnOimEntityAspect] = oimValue(qname(*cntx.entityIdentifier))
            if cntx.period is not None:
                if isJSON:
                    aspects[qnOimPeriodAspect] = oimPeriodValue(cntx)
                elif isCSV:
                    _periodValue = oimPeriodValue(cntx).split("/") + ["", ""] # default blank if no value
                    aspects[qnOimPeriodStartAspect] = _periodValue[0]
                    aspects[qnOimPeriodDurationAspect] = _periodValue[1]
            for _qn, dim in sorted(cntx.qnameDims.items(), key=lambda item: item[0]):
                aspects[dim.dimensionQname] = (oimValue(dim.memberQname) if dim.isExplicit
                                               else None if dim.typedMember.get("{http://www.w3.org/2001/XMLSchema-instance}nil") in ("true", "1")
                                               else dim.typedMember.stringValue)
        unit = fact.unit
        if unit is not None:
            _mMul, _mDiv = unit.measures
            if isJSON:
                aspects[qnOimUnitAspect] = OrderedDict( # use tuple instead of list for hashability
                    (("numerators", tuple(oimValue(m) for m in sorted(_mMul, key=lambda m: oimValue(m)))),)
                )
                if _mDiv:
                    aspects[qnOimUnitAspect]["denominators"] = tuple(oimValue(m) for m in sorted(_mDiv, key=lambda m: oimValue(m)))
            else: # CSV
                if _mMul:
                    aspects[qnOimUnitNumeratorsAspect] = " ".join(oimValue(m)
                                                                  for m in sorted(_mMul, key=lambda m: str(m)))
                if _mDiv:
                    aspects[qnOimUnitDenominatorsAspect] = " ".join(oimValue(m)
                                                                    for m in sorted(_mDiv, key=lambda m: str(m)))
        if parent.qname != XbrlConst.qnXbrliXbrl:
            aspects[qnOimTupleParentAspect] = parent.id if parent.id else "f{}".format(parent.objectIndex)
            aspects[qnOimTupleOrderAspect] = elementIndex(fact)
            
        if isJSON:
            _footnotes = factFootnotes(fact)
            if _footnotes:
                aspects["footnotes"] = _footnotes
        return aspects
    
    if isJSON:
        # save JSON
        
        oimReport = OrderedDict() # top level of oim json output
            
        oimFacts = []
        oimReport["prefixes"] = OrderedDict((p,ns) for ns, p in sorted(namespacePrefixes.items(), 
                                                                       key=lambda item: item[1]))
        oimReport["dtsReferences"] = dtsReferences
        oimReport["facts"] = oimFacts
            
        def saveJsonFacts(facts, oimFacts, parentFact):
            for fact in facts:
                oimFact = factAspects(fact)
                oimFacts.append(OrderedDict((str(k),v) for k,v in oimFact.items()))
                if fact.modelTupleFacts:
                    saveJsonFacts(fact.modelTupleFacts, oimFacts, fact)
                
        saveJsonFacts(modelXbrl.facts, oimFacts, None)
            
        with open(oimFile, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(oimReport, ensure_ascii=False, indent=1, sort_keys=False))

    elif isCSV:
        # save CSV
        
        aspectQnCol = {}
        aspectsHeader = []
        factsColumns = []
        
        def addAspectQnCol(aspectQn):
            aspectQnCol[aspectQn] = len(aspectsHeader)
            _colName = oimValue(aspectQn)
            aspectsHeader.append(_colName)
            _colDataType = {"id": "Name",
                            "baseType": "Name",
                            "oim:concept": "Name",
                            "oim:periodStart": "dateTime", # forever is 0000-01-01T00:00:00
                            "oim:periodDuration": "duration", # forever is P9999Y
                            "oim:tupleOrder": "integer",
                            "numericValue": "decimal",
                            "accuracy": "decimal",
                            "booleanValue": "boolean",
                            "oim:unitNumerators": OrderedDict((("base","Name"), ("separator"," "))), 
                            "oim:unitDenominators": OrderedDict((("base","Name"), ("separator"," "))),
                            }.get(_colName, "string")
            factsColumns.append(OrderedDict((("name", _colName),
                                             ("datatype", _colDataType))))
            
        # pre-ordered aspect columns
        if hasId:
            addAspectQnCol("id")
        if hasType:
            addAspectQnCol("baseType")
        addAspectQnCol("stringValue")
        addAspectQnCol("numericValue")
        addAspectQnCol("accuracy")
        addAspectQnCol("booleanValue")
        if hasTuple:
            addAspectQnCol(qnOimTupleParentAspect)
            addAspectQnCol(qnOimTupleOrderAspect)
        addAspectQnCol(qnOimConceptAspect)
        if qnOimEntityAspect in aspectsDefined:
            addAspectQnCol(qnOimEntityAspect)
        if qnOimPeriodStartAspect in aspectsDefined:
            addAspectQnCol(qnOimPeriodStartAspect)
            addAspectQnCol(qnOimPeriodDurationAspect)
        if qnOimUnitNumeratorsAspect in aspectsDefined:
            addAspectQnCol(qnOimUnitNumeratorsAspect)
        if qnOimUnitDenominatorsAspect in aspectsDefined:
            addAspectQnCol(qnOimUnitDenominatorsAspect)
        for aspectQn in sorted(aspectsDefined, key=lambda qn: str(qn)):
            if aspectQn.namespaceURI != nsOim:
                addAspectQnCol(aspectQn) 
        
        def aspectCols(fact):
            cols = [None for i in range(len(aspectsHeader))]
            _factAspects = factAspects(fact)
            for aspectQn, aspectValue in _factAspects.items():
                if aspectQn in aspectQnCol:
                    cols[aspectQnCol[aspectQn]] = aspectValue
            return cols
        
        # metadata
        csvTables = []
        csvMetadata = OrderedDict((("@context",[ "http://www.w3.org/ns/csvw", { "@base": "./" }]),
                                   ("tables", csvTables)))
        
        if oimFile.endswith("-facts.csv"): # strip -facts.csv if a prior -facts.csv file was chosen
            _baseURL = oimFile[:-10]
        elif oimFile.endswith(".csv"):
            _baseURL = oimFile[:-4]
        else:
            _baseURL = oimFile
        
        # save facts
        _factsFile = _baseURL + "-facts.csv"
        csvFile = open(_factsFile, csvOpenMode, newline=csvOpenNewline, encoding='utf-8-sig')
        csvWriter = csv.writer(csvFile, dialect="excel")
        csvWriter.writerow(aspectsHeader)
        
        def saveCSVfacts(facts):
            for fact in facts:
                csvWriter.writerow(aspectCols(fact))
                saveCSVfacts(fact.modelTupleFacts)
        saveCSVfacts(modelXbrl.facts)
        csvFile.close()
        factsTableSchema = OrderedDict((("columns",factsColumns),))
        csvTables.append(OrderedDict((("url",os.path.basename(_factsFile)),
                                      ("tableSchema",factsTableSchema))))
        
        # save namespaces
        _nsFile = _baseURL + "-prefixes.csv"
        csvFile = open(_nsFile, csvOpenMode, newline=csvOpenNewline, encoding='utf-8-sig')
        csvWriter = csv.writer(csvFile, dialect="excel")
        csvWriter.writerow(("prefix", "URI"))
        for _URI, prefix in sorted(namespacePrefixes.items(), key=lambda item: item[1]):
            csvWriter.writerow((prefix, _URI))
        csvFile.close()
        nsTableSchema = OrderedDict((("columns",[OrderedDict((("prefix","string"),
                                                              ("URI","anyURI")))]),))
        csvTables.append(OrderedDict((("url",os.path.basename(_nsFile)),
                                      ("tableSchema",nsTableSchema))))
        
        # save dts references
        _dtsRefFile = _baseURL + "-dtsReferences.csv"
        csvFile = open(_dtsRefFile, csvOpenMode, newline=csvOpenNewline, encoding='utf-8-sig')
        csvWriter = csv.writer(csvFile, dialect="excel")
        csvWriter.writerow(("type", "href"))
        for oimRef in dtsReferences:
            csvWriter.writerow((oimRef["type"], oimRef["href"]))
        csvFile.close()
        dtsRefTableSchema = OrderedDict((("columns",[OrderedDict((("type","string"),
                                                              ("href","anyURI")))]),))
        csvTables.append(OrderedDict((("url",os.path.basename(_dtsRefFile)),
                                      ("tableSchema",dtsRefTableSchema))))
        
        # save footnotes
        if footnotesRelationshipSet.modelRelationships:
            _footnoteFile = oimFile.replace(".csv", "-footnotes.csv")
            csvFile = open(_footnoteFile, csvOpenMode, newline=csvOpenNewline, encoding='utf-8-sig')
            csvWriter = csv.writer(csvFile, dialect="excel")
            cols = ("group", "factId", "factRef", "footnoteType", "footnote", "language")
            csvWriter.writerow(cols)
            def saveCSVfootnotes(facts):
                for fact in facts:
                    for _footnote in factFootnotes(fact):
                        csvWriter.writerow(tuple((_footnote.get(col,"") for col in cols)))
                        saveCSVfootnotes(fact.modelTupleFacts)
            saveCSVfootnotes(modelXbrl.facts)
            csvFile.close()
            footnoteTableSchema = OrderedDict((("columns",[OrderedDict((("group","anyURI"),
                                                                        ("factId","Name"),
                                                                        ("factRef","Name"),
                                                                        ("footnoteType","Name"),
                                                                        ("footnote","string"),
                                                                        ("language","language")))]),))
            csvTables.append(OrderedDict((("url",os.path.basename(_footnoteFile)),
                                          ("tableSchema",footnoteTableSchema))))
            
        # save metadata
        with open(_baseURL + "-metadata.csv", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(csvMetadata, ensure_ascii=False, indent=1, sort_keys=False))

def saveLoadableOIMMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save Loadable OIM", 
                     underline=0, 
                     command=lambda: saveLoadableOIMMenuCommand(cntlr) )

def saveLoadableOIMMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if (cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None or
        cntlr.modelManager.modelXbrl.modelDocument.type not in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL)):
        return
        # get file name into which to save log file while in foreground thread
    oimFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save Loadable OIM file"),
            initialdir=cntlr.config.setdefault("loadableExcelFileDir","."),
            filetypes=[(_("JSON file .json"), "*.json"), (_("CSV file .csv"), "*.csv")],
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
                      help=_("Save Loadable OIM file (JSON or CSV)"))

def saveLoadableOIMCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    oimFile = getattr(options, "saveLoadableOIM", None)
    if oimFile:
        if (modelXbrl is None or
            modelXbrl.modelDocument.type not in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL)):
            cntlr.addToLog("No XBRL instance has been loaded.")
            return
        saveLoadableOIM(modelXbrl, oimFile)

__pluginInfo__ = {
    'name': 'Save Loadable OIM',
    'version': '0.9',
    'description': "This plug-in saves XBRL in OIM JSON or CSV that can be re-loaded per se.",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2015 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveLoadableOIMMenuEntender,
    'CntlrCmdLine.Options': saveLoadableOIMCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': saveLoadableOIMCommandLineXbrlRun,
}
