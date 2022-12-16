# -*- coding: utf-8 -*-

'''
saveLoadableOIM.py is an example of a plug-in that will save a re-loadable JSON or CSV instance.

When run from GUI a save-as dialog defaults to save .json but can also save .csv and .xlsx files.

When run from command line interface in single-instance mode (a single instance is loaded):
   --saveLoadableOIM oim-file-path
   specifies file name or full path to save with .json, .csv or .xlsx sufffix
When used to augment test case operation to save oim files when running a test suite
   --saveTestcaseOimFileSuffix oim-file-suffix
   specifies characters to add to read-me-first file when saving oim file

CSV saving produces a single row-per-fact table.

Extensions can be added to the results in the following manner:

    extensionPrefixes - optional dict of prefix/name pairs to extend saved metadata
    extensionReportObjects - optional dict of extension report objects
    extensionFactPropertiesMethod - method to add extension properties to oimFact
    extensionReportFinalizeMethod - (JSON only) method to finalize json object, for example change facts from object to array.

See COPYRIGHT.md for copyright information.
'''
import sys, os, io, time, regex as re, json, csv, zipfile
from decimal import Decimal
from math import isinf, isnan
from collections import defaultdict, OrderedDict
from arelle import ModelDocument, XbrlConst
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import (qname, QName, DateTime, YearMonthDuration, tzinfoStr,
                               dayTimeDuration, DayTimeDuration, yearMonthDayTimeDuration, Time,
                               gYearMonth, gMonthDay, gYear, gMonth, gDay, IsoDuration)
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.UrlUtil import relativeUri
from arelle.ValidateXbrlCalcs import inferredDecimals
from arelle.Version import authorLabel, copyrightLabel
from arelle.XmlUtil import dateunionValue, elementIndex, xmlstring
from collections import defaultdict
from numbers import Number

nsOim = "https://xbrl.org/2021"
qnOimConceptAspect = qname("concept", noPrefixIsNoNamespace=True)
qnOimLangAspect = qname("language", noPrefixIsNoNamespace=True)
qnOimPeriodAspect = qname("period", noPrefixIsNoNamespace=True)
qnOimEntityAspect = qname("entity", noPrefixIsNoNamespace=True)
qnOimUnitAspect = qname("unit", noPrefixIsNoNamespace=True)

ONE = Decimal(1)
TEN = Decimal(10)
NILVALUE = "nil"
SCHEMA_LB_REFS = {qname("{http://www.xbrl.org/2003/linkbase}schemaRef"),
                  # qname("{http://www.xbrl.org/2003/linkbase}linkbaseRef")
                  }
ROLE_REFS = {qname("{http://www.xbrl.org/2003/linkbase}roleRef"),
             qname("{http://www.xbrl.org/2003/linkbase}arcroleRef")}
ENTITY_NA_QNAME = ("https://xbrl.org/entities", "NA")
csvOpenMode = 'w'
csvOpenNewline = ''


def saveLoadableOIM(modelXbrl, oimFile, outputZip=None,
                    # arguments to add extension features to OIM document
                    extensionPrefixes=None,
                    extensionReportObjects=None,
                    extensionFactPropertiesMethod=None,
                    extensionReportFinalizeMethod=None):

    isJSON = oimFile.endswith(".json")
    isCSV = oimFile.endswith(".csv")
    isXL = oimFile.endswith(".xlsx")
    isCSVorXL = isCSV or isXL
    if not isJSON and not isCSVorXL:
        return

    namespacePrefixes = {nsOim: "xbrl"}
    prefixNamespaces = {}
    if extensionPrefixes:
        for extensionPrefix, extensionNamespace in extensionPrefixes.items():
            namespacePrefixes[extensionNamespace] = extensionPrefix
            prefixNamespaces[extensionPrefix] = extensionNamespace
    linkTypeAliases = {}
    groupAliases = {}
    linkTypePrefixes = {}
    linkTypeUris = {}
    linkGroupPrefixes = {}
    linkGroupUris = {}
    def compileQname(qname):
        if qname.namespaceURI not in namespacePrefixes:
            namespacePrefixes[qname.namespaceURI] = qname.prefix or ""

    aspectsDefined = {
        qnOimConceptAspect,
        qnOimEntityAspect,
        qnOimPeriodAspect}

    def oimValue(object, decimals=None):
        if isinstance(object, QName):
            if object.namespaceURI not in namespacePrefixes:
                if object.prefix:
                    namespacePrefixes[object.namespaceURI] = object.prefix
                else:
                    _prefix = "_{}".format(sum(1 for p in namespacePrefixes if p.startswith("_")))
                    namespacePrefixes[object.namespaceURI] = _prefix
            return "{}:{}".format(namespacePrefixes[object.namespaceURI], object.localName)
        if isinstance(object, (float, Decimal)):
            try:
                if isinf(object):
                    return "-INF" if object < 0 else "INF"
                elif isnan(object):
                    return "NaN"
                else:
                    if isinstance(object, Decimal) and object == object.to_integral():
                        object = object.quantize(ONE) # drop any .0
                    return "{}".format(object)
            except:
                return str(object)
        if isinstance(object, bool):
            return "true" if object else "false"
        if isinstance(object, (DateTime, YearMonthDuration, DayTimeDuration, Time,
                               gYearMonth, gMonthDay, gYear, gMonth, gDay,
                               IsoDuration, int)):
            return str(object)
        return object

    def oimPeriodValue(cntx):
        if cntx.isStartEndPeriod:
            s = cntx.startDatetime
            e = cntx.endDatetime
        else: # instant
            s = e = cntx.instantDatetime
        return({str(qnOimPeriodAspect):
                ("{0:04}-{1:02}-{2:02}T{3:02}:{4:02}:{5:02}{6}/".format(
                         s.year, s.month, s.day, s.hour, s.minute, s.second, tzinfoStr(s))
                    if cntx.isStartEndPeriod else "") +
                "{0:04}-{1:02}-{2:02}T{3:02}:{4:02}:{5:02}{6}".format(
                         e.year, e.month, e.day, e.hour, e.minute, e.second, tzinfoStr(e))
                })

    hasId = False
    hasTuple = False
    hasType = True
    hasLang = False
    hasUnits = False
    hasNumeric = False

    footnotesRelationshipSet = ModelRelationshipSet(modelXbrl, "XBRL-footnotes")

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
        compileQname(fact.qname)
        if hasattr(fact, "xValue") and isinstance(fact.xValue, QName):
            compileQname(fact.xValue)
        unit = fact.unit
        if unit is not None:
            hasUnits = True
        if fact.modelTupleFacts:
            hasTuple = True
    if hasTuple:
        modelXbrl.error("arelleOIMsaver:tuplesNotAllowed",
                        "Tuples are not allowed in an OIM document",
                        modelObject=modelXbrl)
        return

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

    if hasLang: aspectsDefined.add(qnOimLangAspect)
    if hasUnits: aspectsDefined.add(qnOimUnitAspect)

    for footnoteRel in footnotesRelationshipSet.modelRelationships:
        typePrefix = "ftTyp_" + os.path.basename(footnoteRel.arcrole)
        if footnoteRel.linkrole == XbrlConst.defaultLinkRole:
            groupPrefix = "ftGrp_default"
        else:
            groupPrefix = "ftGrp_" + os.path.basename(footnoteRel.linkrole)
        if footnoteRel.arcrole not in linkTypeAliases:
            linkTypeAliases[footnoteRel.arcrole] = typePrefix
        if groupPrefix not in groupAliases:
            groupAliases[footnoteRel.linkrole] = groupPrefix

    dtsReferences = set()
    baseUrl = modelXbrl.modelDocument.uri.partition("#")[0]
    for doc,ref in sorted(modelXbrl.modelDocument.referencesDocument.items(),
                              key=lambda _item:_item[0].uri):
        if ref.referringModelObject.qname in SCHEMA_LB_REFS:
            dtsReferences.add(relativeUri(baseUrl,doc.uri))
    for refType in ("role", "arcrole"):
        for refElt in sorted(modelXbrl.modelDocument.xmlRootElement.iterchildren(
                                "{{http://www.xbrl.org/2003/linkbase}}{}Ref".format(refType)),
                              key=lambda elt:elt.get(refType+"URI")
                              ):
            dtsReferences.add(refElt.get("{http://www.w3.org/1999/xlink}href").partition("#")[0])
    dtsReferences = sorted(dtsReferences) # turn into list
    footnoteFacts = set()

    def factFootnotes(fact, oimFact=None, csvLinks=None):
        footnotes = []
        if isJSON:
            oimLinks = {}
        elif isCSVorXL:
            oimLinks = csvLinks
        for footnoteRel in footnotesRelationshipSet.fromModelObject(fact):
            srcId = fact.id if fact.id else "f{}".format(fact.objectIndex)
            toObj = footnoteRel.toModelObject
            # json
            typePrefix = linkTypeAliases[footnoteRel.arcrole]
            groupPrefix = groupAliases[footnoteRel.linkrole]
            if typePrefix not in oimLinks:
                oimLinks[typePrefix] = OrderedDict()
            _link = oimLinks[typePrefix]
            if groupPrefix not in _link:
                if isJSON:
                    _link[groupPrefix] = []
                elif isCSVorXL:
                    _link[groupPrefix] = OrderedDict()
            if isJSON:
                tgtIdList = _link[groupPrefix]
            elif isCSVorXL:
                tgtIdList = _link[groupPrefix].setdefault(srcId, [])
            tgtId = toObj.id if toObj.id else "f{}".format(toObj.objectIndex)
            tgtIdList.append(tgtId)
            footnote = OrderedDict((("group", footnoteRel.linkrole),
                                    ("footnoteType", footnoteRel.arcrole)))
            if isinstance(toObj, ModelFact):
                footnote["factRef"] = tgtId
            else: # text footnotes
                footnote["id"] = tgtId
                footnote["footnote"] = toObj.viewText()
                if toObj.xmlLang:
                    footnote["language"] = toObj.xmlLang
                footnoteFacts.add(toObj)
                footnotes.append(footnote)
        if oimLinks:
            _links = OrderedDict((
                (typePrefix, OrderedDict((
                    (groupPrefix, idList)
                    for groupPrefix, idList in sorted(groups.items())
                    )))
                for typePrefix, groups in sorted(oimLinks.items())
                ))
            if isJSON:
                oimFact["links"] = _links

        return footnotes

    def factAspects(fact):
        oimFact = OrderedDict()
        aspects = OrderedDict()
        if isCSVorXL:
            oimFact["id"] = fact.id or "f{}".format(fact.objectIndex)
        parent = fact.getparent()
        concept = fact.concept
        aspects[str(qnOimConceptAspect)] = oimValue(concept.qname)
        if concept is not None:
            if concept.type.isOimTextFactType and fact.xmlLang:
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
                    if not isinf(_inferredDecimals): # accuracy omitted if infinite
                        oimFact["decimals"] = _inferredDecimals
        oimFact["dimensions"] = aspects
        cntx = fact.context
        if cntx is not None:
            if cntx.entityIdentifierElement is not None and cntx.entityIdentifier != ENTITY_NA_QNAME:
                aspects[str(qnOimEntityAspect)] = oimValue(qname(*cntx.entityIdentifier))
            if cntx.period is not None and not cntx.isForeverPeriod:
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
            if _sUnit != "xbrli:pure":
                aspects[str(qnOimUnitAspect)] = _sUnit
        # Tuples removed from xBRL-JSON
        #if parent.qname != XbrlConst.qnXbrliXbrl:
        #    aspects[str(qnOimTupleParentAspect)] = parent.id if parent.id else "f{}".format(parent.objectIndex)
        #    aspects[str(qnOimTupleOrderAspect)] = elementIndex(fact)

        if isJSON:
            factFootnotes(fact, oimFact=oimFact)
        return oimFact

    namespaces = OrderedDict((p,ns) for ns, p in sorted(namespacePrefixes.items(),
                                                      key=lambda item: item[1]))

    # common metadata
    oimReport = OrderedDict() # top level of oim json output
    oimReport["documentInfo"] = oimDocInfo = OrderedDict()
    oimDocInfo["documentType"] = nsOim + ("/xbrl-json" if isJSON else "/xbrl-csv")
    if isJSON:
        oimDocInfo["features"] = oimFeatures = OrderedDict()
    oimDocInfo["namespaces"] = namespaces
    if linkTypeAliases:
        oimDocInfo["linkTypes"] = OrderedDict((a,u) for u,a in sorted(linkTypeAliases.items(),
                                                                      key=lambda item: item[1]))
    if linkTypeAliases:
        oimDocInfo["linkGroups"] = OrderedDict((a,u) for u,a in sorted(groupAliases.items(),
                                                                   key=lambda item: item[1]))
    oimDocInfo["taxonomy"] = dtsReferences
    if isJSON:
        oimFeatures["xbrl:canonicalValues"] = True


    if isJSON:
        # save JSON
        oimReport["facts"] = oimFacts = OrderedDict()
        # add in report level extension objects
        if extensionReportObjects:
            for extObjQName, extObj in extensionReportObjects.items():
                oimReport[extObjQName] = extObj

        def saveJsonFacts(facts, oimFacts, parentFact):
            for fact in facts:
                oimFact = factAspects(fact)
                # add in fact level extension objects
                if extensionFactPropertiesMethod:
                    extensionFactPropertiesMethod(fact, oimFact)
                id = fact.id if fact.id else "f{}".format(fact.objectIndex)
                oimFacts[id] = oimFact
                if fact.modelTupleFacts:
                    saveJsonFacts(fact.modelTupleFacts, oimFacts, fact)

        saveJsonFacts(modelXbrl.facts, oimFacts, None)

        # add footnotes as pseudo facts
        for ftObj in footnoteFacts:
            ftId = ftObj.id if ftObj.id else "f{}".format(ftObj.objectIndex)
            oimFacts[ftId] = oimFact = OrderedDict()
            oimFact["value"] = ftObj.viewText()
            oimFact["dimensions"] = OrderedDict((("concept", "xbrl:note"),
                                              ("noteId", ftId)))
            if ftObj.xmlLang:
                oimFact["dimensions"]["language"] = ftObj.xmlLang.lower()

        # allow extension report final editing before writing json structure
        # (possible example, reorganize facts into array vs object)
        if extensionReportFinalizeMethod:
            extensionReportFinalizeMethod(oimReport)

        if outputZip:
            fh = io.StringIO()
        else:
            fh = open(oimFile, "w", encoding="utf-8")
        fh.write(json.dumps(oimReport, indent=1))
        if outputZip:
            fh.seek(0)
            outputZip.writestr(os.path.basename(oimFile),fh.read())
        fh.close()

    elif isCSVorXL:
        # save CSV
        oimReport["tables"] = oimTables = OrderedDict()
        oimReport["tableTemplates"] = csvTableTemplates = OrderedDict()
        oimTables["facts"] = csvTable = OrderedDict()
        csvTable["template"] = "facts"
        csvTable["url"] = "tbd"
        csvTableTemplates["facts"] = csvTableTemplate = OrderedDict()
        csvTableTemplate["rowIdColumn"] = "id"
        csvTableTemplate["dimensions"] = csvTableDimensions = OrderedDict()
        csvTableTemplate["columns"] = csvFactColumns = OrderedDict()
        if footnotesRelationshipSet.modelRelationships:
            csvLinks = OrderedDict()
            oimReport["links"] = csvLinks
        aspectQnCol = {}
        aspectsHeader = []
        factsColumns = []

        def addAspectQnCol(aspectQn):
            colQName = str(aspectQn).replace("xbrl:", "")
            colNCName = colQName.replace(":", "_")
            if colNCName not in aspectQnCol:
                aspectQnCol[colNCName] = len(aspectsHeader)
                aspectsHeader.append(colNCName)
                if colNCName == "value":
                    csvFactColumns[colNCName] = col = OrderedDict()
                    col["dimensions"] = OrderedDict()
                elif colNCName == "id":
                    csvFactColumns[colNCName] = {} # empty object
                elif colNCName == "decimals":
                    csvFactColumns[colNCName] = {} # empty object
                    csvTableTemplate[colQName] = "$" + colNCName
                else:
                    csvFactColumns[colNCName] = {} # empty object
                    csvTableDimensions[colQName] = "$" + colNCName


        # pre-ordered aspect columns
        #if hasId:
        addAspectQnCol("id")
        addAspectQnCol(qnOimConceptAspect)
        if hasNumeric:
            addAspectQnCol("decimals")
        if qnOimEntityAspect in aspectsDefined:
            addAspectQnCol(qnOimEntityAspect)
        if qnOimPeriodAspect in aspectsDefined:
            addAspectQnCol(qnOimPeriodAspect)
        if qnOimUnitAspect in aspectsDefined:
            addAspectQnCol(qnOimUnitAspect)
        for aspectQn in sorted(aspectsDefined, key=lambda qn: str(qn)):
            if aspectQn.namespaceURI != nsOim:
                addAspectQnCol(aspectQn)
        addAspectQnCol("value")

        def aspectCols(fact):
            cols = [None for i in range(len(aspectsHeader))]
            def setColValues(aspects):
                for aspectQn, aspectValue in aspects.items():
                    colQName = str(aspectQn).replace("xbrl:", "")
                    colNCName = colQName.replace(":", "_")
                    if isinstance(aspectValue, dict):
                        setColValues(aspectValue)
                    elif colNCName in aspectQnCol:
                        if aspectValue is None:
                            _aspectValue = "#nil"
                        elif aspectValue == "":
                            _aspectValue = "#empty"
                        elif isinstance(aspectValue, str) and aspectValue.startswith("#"):
                            _aspectValue = "#" + aspectValue
                        else:
                            _aspectValue = aspectValue
                        cols[aspectQnCol[colNCName]] = _aspectValue
            setColValues(factAspects(fact))
            return cols

        # metadata

        _open = _writerow = _close = None
        if isCSV:
            if oimFile.endswith("-facts.csv"): # strip -facts.csv if a prior -facts.csv file was chosen
                _baseURL = oimFile[:-10]
            elif oimFile.endswith(".csv"):
                _baseURL = oimFile[:-4]
            else:
                _baseURL = oimFile
            _csvinfo = {} # open file, writer
            def _open(filesuffix, tabname, csvTable=None):
                _filename = _baseURL + filesuffix
                if csvTable is not None:
                    csvTable["url"] = os.path.basename(_filename) # located in same directory with metadata
                _csvinfo["file"] = open(_filename, csvOpenMode, newline=csvOpenNewline, encoding='utf-8-sig')
                _csvinfo["writer"] = csv.writer(_csvinfo["file"], dialect="excel")
            def _writerow(row, header=False):
                _csvinfo["writer"].writerow(row)
            def _close():
                _csvinfo["file"].close()
                _csvinfo.clear()
        elif isXL:
            headerWidths = {"concept": 40, "decimals": 8, "language": 9, "value": 50,
                            "entity": 20, "period": 20, "unit": 20, "metadata": 100}
            from openpyxl import Workbook
            from openpyxl.cell.cell import WriteOnlyCell
            from openpyxl.styles import Font, PatternFill, Border, Alignment, Color, fills, Side
            from openpyxl.worksheet.dimensions import ColumnDimension
            hdrCellFill = PatternFill(patternType=fills.FILL_SOLID, fgColor=Color("00FFBF5F")) # Excel's light orange fill color = 00FF990
            workbook = Workbook()
            # remove pre-existing worksheets
            while len(workbook.worksheets)>0:
                workbook.remove(workbook.worksheets[0])
            _xlinfo = {} # open file, writer
            def _open(filesuffix, tabname, csvTable=None):
                if csvTable is not None:
                    csvTable["url"] = tabname + "!"
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
                        _ws.column_dimensions[colLetter].width = headerWidths.get(v, 40)

                    else:
                        cell.alignment = Alignment(horizontal="right" if isinstance(v, Number)
                                                   else "center" if isinstance(v, bool)
                                                   else "left",
                                                   vertical="top",
                                                   wrap_text=isinstance(v, str))
                    row.append(cell)
                _ws.append(row)
            def _close():
                _xlinfo.clear()


        # save facts
        _open("-facts.csv", "facts", csvTable)
        _writerow(aspectsHeader, header=True)

        def saveCSVfacts(facts):
            for fact in facts:
                _writerow(aspectCols(fact))
                saveCSVfacts(fact.modelTupleFacts)
        saveCSVfacts(modelXbrl.facts)
        _close()

        # save footnotes
        if footnotesRelationshipSet.modelRelationships:
            footnotes = sorted((footnote
                                for fact in modelXbrl.facts
                                for footnote in factFootnotes(fact, csvLinks=csvLinks)),
                               key=lambda footnote:footnote["id"])
            if footnotes: # text footnotes
                oimTables["footnotes"] = csvFtTable = OrderedDict()
                csvFtTable["url"] = "tbd"
                csvFtTable["tableDimensions"] = csvFtTableDimensions = OrderedDict()
                csvFtTable["factColumns"] = csvFtFactColumns = OrderedDict()
                csvFtFactColumns["footnote"] = csvFtValCol = OrderedDict()
                csvFtValCol["id"] = "$id"
                csvFtValCol["noteId"] = "$id"
                csvFtValCol["concept"] = "xbrl:note"
                csvFtValCol["language"] = "$language"
                _open("-footnotes.csv", "footnotes", csvFtTable)
                cols = ("id", "footnote", "language")
                _writerow(cols, header=True)
                for footnote in footnotes:
                    _writerow(tuple((footnote.get(col,"") for col in cols)))
                _close()

        # save metadata
        if isCSV:
            with open(_baseURL + "-metadata.json", "w", encoding="utf-8") as fh:
                fh.write(json.dumps(oimReport, ensure_ascii=False, indent=2, sort_keys=False))
        elif isXL:
            _open(None, "metadata")
            _writerow(["metadata"], header=True)
            _writerow([json.dumps(oimReport, ensure_ascii=False, indent=1, sort_keys=False)])
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
                                        saveLoadableOIM(_modelXbrl, _oimFile, None))
    thread.daemon = True
    thread.start()

def saveLoadableOIMCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options with a save DTS option
    parser.add_option("--saveLoadableOIM",
                      action="store",
                      dest="saveLoadableOIM",
                      help=_("Save Loadable OIM file (JSON, CSV or XLSX)"))
    parser.add_option("--saveTestcaseOIM",
                      action="store",
                      dest="saveTestcaseOimFileSuffix",
                      help=_("Save Testcase Variation OIM file (argument file suffix and type, such as -savedOim.csv"))

def saveLoadableOIMCaptureOptions(cntlr, options, *args, **kwargs):
    cntlr.modelManager.saveTestcaseOimFileSuffix = getattr(options, "saveTestcaseOimFileSuffix", None)

def saveLoadableOIMCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    oimFile = getattr(options, "saveLoadableOIM", None)
    if oimFile:
        if (modelXbrl is None or
            modelXbrl.modelDocument.type not in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET)):
            cntlr.addToLog("No XBRL instance has been loaded.")
            return
        try:
            responseZipStream = kwargs.get("responseZipStream")
            if responseZipStream is not None:
                _zip = zipfile.ZipFile(responseZipStream, "a", zipfile.ZIP_DEFLATED, True)
            else:
                _zip = None
            saveLoadableOIM(modelXbrl, oimFile, _zip)
            if responseZipStream is not None:
                _zip.close()
                responseZipStream.seek(0)
        except Exception as ex:
            cntlr.addToLog("Exception saving OIM {}".format(ex))

oimErrorPattern = re.compile("oime|oimce|xbrlje|xbrlce")

def saveLoadableOIMAfterTestcaseValidated(testcaseDTS, testInstanceDTS, extraErrors, *args, **kwargs):
    oimFileSuffix = getattr(testcaseDTS.modelManager, "saveTestcaseOimFileSuffix", None)
    if (oimFileSuffix and testInstanceDTS is not None and
        testInstanceDTS.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET) and
        not any(oimErrorPattern.match(error) for error in testInstanceDTS.errors)): # no OIM errors
        try:
            saveLoadableOIM(testInstanceDTS, testInstanceDTS.modelDocument.uri + oimFileSuffix)
        except Exception as ex:
            cntlr.addToLog("Exception saving OIM {}".format(ex))

__pluginInfo__ = {
    'name': 'Save Loadable OIM',
    'version': '1.2',
    'description': "This plug-in saves XBRL in OIM JSON, CSV or XLSX that can be re-loaded per se.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveLoadableOIMMenuEntender,
    'CntlrCmdLine.Options': saveLoadableOIMCommandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': saveLoadableOIMCaptureOptions,
    'CntlrCmdLine.Xbrl.Run': saveLoadableOIMCommandLineXbrlRun,
    'TestcaseVariation.Validated': saveLoadableOIMAfterTestcaseValidated,
    'SaveLoadableOim.Save': saveLoadableOIM,
}
