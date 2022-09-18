# -*- coding: utf-8 -*-

'''
loadFromExcel.py is an example of a plug-in that will load an extension taxonomy from Excel
input and optionally save an (extension) DTS.

(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
import os, io, time, re, traceback
from collections import defaultdict
from arelle import XbrlConst, ModelDocument
from arelle.ModelValue import qname
from arelle.XbrlConst import (qnLinkLabel, standardLabelRoles, qnLinkReference, standardReferenceRoles,
                              qnLinkPart, gen, link, defaultLinkRole,
                              conceptLabel, elementLabel, conceptReference,
                              )

importColumnHeaders = {
    "名前空間プレフィックス": "prefix",
    "prefix": "prefix",
    "要素名": "name",
    "name": "name",
    "type": "type",
    "typePrefix": "typePrefix", # usually part of type but optionally separate column
    "substitutionGroup": "substitutionGroup",
    "periodType": "periodType",
    "balance": "balance",
    "abstract": "abstract", # contains true if abstract
    "nillable": "nillable",
    "depth": "depth",
    "minLength": "minLength",
    "maxLength": "maxLength",
    "length": "length",
    "fixed": "fixed",
    "pattern": "pattern",
    "enumeration": "enumeration",
    "preferred label": "preferredLabel",
    "preferredLabel": "preferredLabel",
    "calculation parent": "calculationParent", # qname
    "calculation weight": "calculationWeight",
    # label col heading: ("label", role, lang [indented]),
    "標準ラベル（日本語）": ("label", XbrlConst.standardLabel, "ja", "indented"),
    "冗長ラベル（日本語）": ("label", XbrlConst.verboseLabel, "ja"),
    "標準ラベル（英語）": ("label", XbrlConst.standardLabel, "en"),
    "冗長ラベル（英語）": ("label", XbrlConst.verboseLabel, "en"),
    "用途区分、財務諸表区分及び業種区分のラベル（日本語）": ("labels", XbrlConst.standardLabel, "ja"),
    "用途区分、財務諸表区分及び業種区分のラベル（英語）": ("labels", XbrlConst.standardLabel, "en"),
    # label [, role [(lang)]] : ("label", http resource role, lang [indented|overridePreferred])
    "label": ("label", XbrlConst.standardLabel, "en", "indented"),
    "label, standard": ("label", XbrlConst.standardLabel, "en", "overridePreferred"),
    "label, terse": ("label", XbrlConst.terseLabel, "en"),
    "label, verbose": ("label", XbrlConst.verboseLabel, "en"),
    "label, documentation": ("label", XbrlConst.documentationLabel, "en"),
    "group": "linkrole",
    "linkrole": "linkrole",
    "ELR": "linkrole"
    # reference ("reference", reference http resource role, reference part QName)
    # reference, required": ("reference", "http://treasury.gov/dataact/role/taxonomyImplementationNote", qname("{http://treasury.gov/dataact/parts-2015-12-31}dataact-part:Required"))
    }

importColHeaderMap = defaultdict(list)
resourceParsePattern = re.compile(r"(label|reference),?\s*([\w][\w\s#+-]+[\w#+-])(\s*[(]([^)]+)[)])?$")

NULLENTRY = ({},)

def loadFromExcel(cntlr, excelFile):
    from openpyxl import load_workbook
    from arelle import ModelDocument, ModelXbrl, XmlUtil
    from arelle.ModelDocument import ModelDocumentReference
    from arelle.ModelValue import qname
    
    defaultLabelLang = "en"
    
    fatalLoadingErrors = []
    
    startedAt = time.time()
    
    if os.path.isabs(excelFile):
        # allow relative filenames to loading directory
        priorCWD = os.getcwd()
        os.chdir(os.path.dirname(excelFile))
    else:
        priorCWD = None
    importExcelBook = load_workbook(excelFile, data_only=True)
    sheetNames = importExcelBook.get_sheet_names()
    if "XBRL DTS" in sheetNames: 
        dtsWs = importExcelBook["XBRL DTS"]
    elif "DTS" in sheetNames: 
        dtsWs = importExcelBook["DTS"]
    elif "Sheet2" in sheetNames: 
        dtsWs = importExcelBook["Sheet2"]
    else:
        dtsWs = None
    imports = {"xbrli": ( ("namespace", XbrlConst.xbrli), 
                          ("schemaLocation", "http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd") )} # xml of imports
    importXmlns = {}
    linkbaseRefs = []
    labelLinkbases = []
    referenceLinkbases = []
    hasPreLB = hasCalLB = hasDefLB = hasRefLB = False
    # xxxLB structure [ (elr1, def1, "_ELR_", [roots]), (elr2, def2, "_ELR_", [rootw]) ...]
    #   roots = (rootHref, None, "_root_", [children])
    #   children = (childPrefix, childName, arcrole, [grandChildren])
    preLB = []
    defLB = []
    calLB = []
    refLB = []
    
    def lbDepthList(lbStruct, depth, parentList=None):
        if len(lbStruct) > 0:
            if depth == topDepth:
                return lbStruct[-1].childStruct
            return lbDepthList(lbStruct[-1].childStruct, depth-1, list)
        else:
            cntlr.addToLog("Depth error, Excel row: {excelRow}"
                           .format(excelRow=iRow),
                            messageCode="importExcel:depth")
            return None
    
    splitString = None # to split repeating groups (order, depth)
    extensionTypes = {} # attrs are name, base.  has facets in separate dict same as elements
    extensionElements = {}
    extensionRoles = {} # key is roleURI, value is role definition
    extensionLabels = {}  # key = (prefix, name, lang, role), value = label text
    extensionReferences = defaultdict(set) # key = (prefix, name, role) values = (partQn, text)
    extensionSchemaVersion = None # <schema @version>
    importFileName = None # for alternate import file
    importSheetName = None
    skipRows = []  # [(from,to),(from,to)]  row number starting at 1 
    
    def extensionHref(prefix, name):
        if prefix == extensionSchemaPrefix:
            filename = extensionSchemaFilename
        elif prefix in imports:
            filename = imports[prefix][1][1]
        else:
            return None
        return "{0}#{1}_{2}".format(filename, prefix, name)
            
    isUSGAAP = False
    for iRow, row in enumerate(dtsWs.rows if dtsWs else ()):
        try:
            if (len(row) < 1 or row[0].value is None):  # skip if col 1 is empty
                continue
            action = filetype = prefix = filename = namespaceURI = None
            if len(row) > 0: action = row[0].value
            if len(row) > 1: filetype = row[1].value
            if len(row) > 2: prefix = row[2].value
            if len(row) > 3: filename = row[5].value
            if len(row) > 4: namespaceURI = row[6].value
            lbType = lang = None
            if action == "import":
                if filetype == "role":
                    continue
                imports[prefix] = ( ("namespace", namespaceURI), ("schemaLocation", filename) )
                importXmlns[prefix] = namespaceURI
                if re.match(r"http://[^/]+/us-gaap/", namespaceURI):
                    isUSGAAP = True
            elif action in ("extension", "generate"):
                if filetype == "schema":
                    extensionSchemaPrefix = prefix
                    extensionSchemaFilename = filename
                    extensionSchemaNamespaceURI = namespaceURI
                elif filetype == "linkbase":
                    typeLang = prefix.split()
                    if len(typeLang) > 0:
                        lbType = typeLang[0]
                    else:
                        lbType = "unknown"
                    if len(typeLang) > 1:
                        lang = referenceRole = typeLang[1]
                    else:
                        lang = defaultLabelLang
                        referenceRole = XbrlConst.standardReference
                    if lbType in ("label", "generic-label"):
                        labelLinkbases.append((lbType, lang, filename))
                    elif lbType in ("reference", "generic-reference"):
                        hasRefLB = True
                        referenceLinkbases.append((lbType, referenceRole, filename))
                    elif lbType == "presentation":
                        hasPreLB = True
                    elif lbType == "definition":
                        hasDefLB = True
                    elif lbType == "calculation":
                        hasCalLB = True
                    linkbaseRefs.append( (lbType, filename) )
                elif filetype == "role" and namespaceURI:
                    extensionRoles[namespaceURI] = filename
                elif filetype == "schema-version" and filename:
                    extensionSchemaVersion = filename
                elif filetype == "table-style" and filename == "xbrl-us":
                    isUSGAAP = True
            elif action == "meta" and filetype == "table-style" and filename == "xbrl-us":
                isUSGAAP = True
            elif action == "workbook" and filename:
                importFileName = filename
            elif action == "worksheet" and filename:
                importSheetName = filename
            elif action == "colheader" and filename and namespaceURI:
                if namespaceURI == "split":
                    splitString = filename
                else:
                    importColHeaderMap[filename].append(namespaceURI)
                    if namespaceURI not in importColumnHeaders:
                        fatalLoadingErrors.append("colheader {} definition {} not recognized.".format(filename, namespaceURI))
            elif action == "skip rows" and filename:
                fromRow, _sep, toRow = filename.partition("-")
                try:
                    skipRows.append((int(fromRow), int(toRow) if toRow else int(fromRow)))
                except (ValueError, TypeError):
                    fatalLoadingErrors.append("Exception (at skip rows): {error}, Excel row: {excelRow}"
                                              .format(error=err, excelRow=iRow))
                
                
        except Exception as err:
            fatalLoadingErrors.append("Exception: {error}, Excel row: {excelRow}, Traceback: {traceback}"
                                      .format(error=err, excelRow=iRow, traceback=traceback.format_stack()))
            
    dtsWs = None # dereference
    
    if importFileName: # alternative workbook
        importExcelBook = load_workbook(importFileName, read_only=True, data_only=True)
        sheetNames = importExcelBook.get_sheet_names()
        
    if importSheetName not in sheetNames:
        for s in sheetNames:
            if s.endswith("Concepts"):
                importSheetName = s
                break
        if not importSheetName:   
            fatalLoadingErrors.append("Worksheet {} specified for Excel importing, but not present in workbook.".format(importSheetName))

            
    if not isUSGAAP: # need extra namespace declaration
        importXmlns["iod"] = "http://disclosure.edinet-fsa.go.jp/taxonomy/common/2013-03-31/iod"
    
    # find column headers row
    headerCols = {}
    hasLinkroleSeparateRow = True
    headerRows = set()
    topDepth = 999999
    
    if importSheetName in sheetNames:
        conceptsWs = importExcelBook[importSheetName]
    elif "Concepts" in sheetNames:
        conceptsWs = importExcelBook["Concepts"]
    elif "Sheet1" in sheetNames:
        conceptsWs = importExcelBook["Sheet1"]
    else:
        conceptsWs = None
    
    def setHeaderCols(row):
        headerCols.clear()
        for iCol, colCell in enumerate(row):
            v = colCell.value
            if isinstance(v,str):
                v = v.strip()
            if v in importColHeaderMap:
                for hdr in importColHeaderMap[v]:
                    if hdr in importColumnHeaders:
                        headerCols[importColumnHeaders[hdr]] = iCol
            elif v in importColumnHeaders:
                headerCols[importColumnHeaders[v]] = iCol
            elif isinstance(v,str) and (v.startswith("label,") or v.startswith("reference,")):
                m = resourceParsePattern.match(v)
                if m:
                    _resourceType = m.group(1)
                    _resourceRole = "/" + m.group(2) # last path seg of role
                    _resourceLangOrPart = m.group(4) # lang or part
                    headerCols[(_resourceType, _resourceRole, _resourceLangOrPart)] = iCol
    
    # find out which rows are header rows
    for iRow, row in enumerate(conceptsWs.rows if conceptsWs else ()):
        if any(fromRow <= iRow+1 <= toRow for fromRow,toRow in skipRows):
            continue
        
        for iCol, colCell in enumerate(row):
            setHeaderCols(row)
        if all(colName in headerCols
               for colName in ("name", "type", "depth")): # must have these to be a header col
            # it's a header col
            headerRows.add(iRow+1)
        if 'linkrole' in headerCols:
            hasLinkroleSeparateRow = False
        headerCols.clear()

    def cellHasValue(row, header, _type):
        if header in headerCols:
            iCol = headerCols[header]
            return iCol < len(row) and isinstance(row[iCol].value, _type)
        return False
    
    def cellValue(row, header, strip=False, nameChars=False, default=None):
        if header in headerCols:
            iCol = headerCols[header]
            if iCol < len(row):
                v = row[iCol].value
                if strip and isinstance(v, str):
                    v = v.strip()
                if nameChars and isinstance(v, str):
                    v = ''.join(c for c in v if c.isalnum() or c in ('.', '_', '-'))
                if v is None:
                    return default
                return v
        return default
        
    def checkImport(qname):
        prefix, sep, localName = qname.partition(":")
        if sep:
            if prefix not in imports:
                if prefix == "xbrldt":
                    imports["xbrldt"] = ("namespace", XbrlConst.xbrldt), ("schemaLocation", "http://www.xbrl.org/2005/xbrldt-2005.xsd")
                elif prefix == "nonnum":
                    imports["nonnum"] = ("namespace", "http://www.xbrl.org/dtr/type/non-numeric"), ("schemaLocation", "http://www.xbrl.org/dtr/type/nonNumeric-2009-12-16.xsd")
                elif prefix != extensionSchemaPrefix:
                    cntlr.addToLog("Warning: prefix schema file is not imported for: {qname}"
                           .format(qname=qname),
                            messageCode="importExcel:warning")

    # find top depth
    for iRow, row in enumerate(conceptsWs.rows if conceptsWs else ()):
        if (iRow + 1) in headerRows:
            setHeaderCols(row)
        elif not (hasLinkroleSeparateRow and (iRow + 1) in headerRows) and 'depth' in headerCols:
            depth = cellValue(row, 'depth')
            if isinstance(depth, int) and depth < topDepth:
                topDepth = depth

    # find header rows
    currentELR = currentELRdefinition = None
    for iRow, row in enumerate(conceptsWs.rows if conceptsWs else ()):
        useLabels = False
        if any(fromRow <= iRow+1 <= toRow for fromRow,toRow in skipRows):
            continue
        if (all(col is None for col in row) or 
            all(isinstance(row[i].value, str) and row[i].value.strip() == "n/a"
               for i in (headerCols.get("name"), headerCols.get("type"), headerCols.get("value"))
               if i)):
            continue # skip blank row
        try:
            isHeaderRow = (iRow + 1) in headerRows
            isELRrow = hasLinkroleSeparateRow and (iRow + 2) in headerRows
            if isHeaderRow:
                setHeaderCols(row)
            elif isELRrow:
                currentELR = currentELRdefinition = None
                for colCell in row:
                    v = str(colCell.value or '')
                    if v.startswith("http://"):
                        currentELR = v
                    elif not currentELRdefinition and v.endswith("　科目一覧"):
                        currentELRdefinition = v[0:-5]
                    elif not currentELRdefinition:
                        currentELRdefinition = v
                if currentELR or currentELRdefinition:
                    if hasPreLB:
                        preLB.append( LBentry(role=currentELR, name=currentELRdefinition, isELR=True) )
                    if hasDefLB:
                        defLB.append( LBentry(role=currentELR, name=currentELRdefinition, isELR=True) )
                    if hasCalLB:
                        calLB.append( LBentry(role=currentELR, name=currentELRdefinition, isELR=True) )
                        calRels = set() # prevent duplications when same rel in different parts of tree
            elif headerCols:
                if "linkrole" in headerCols and cellHasValue(row, 'linkrole', str):
                    v = cellValue(row, 'linkrole', strip=True)
                    _trialELR = _trialELRdefinition = None
                    if v.startswith("http://"):
                        _trialELR = v
                    elif v.endswith("　科目一覧"):
                        _trialELRdefinition = v[0:-5]
                    else:
                        _trialELRdefinition = v
                    if (_trialELR and _trialELR != currentELR) or (_trialELRdefinition and _trialELRdefinition != currentELRdefinition):
                        currentELR = _trialELR
                        currentELRdefinition = _trialELRdefinition
                        if currentELR or currentELRdefinition:
                            if hasPreLB:
                                preLB.append( LBentry(role=currentELR, name=currentELRdefinition, isELR=True) )
                            if hasDefLB:
                                defLB.append( LBentry(role=currentELR, name=currentELRdefinition, isELR=True) )
                            if hasCalLB:
                                calLB.append( LBentry(role=currentELR, name=currentELRdefinition, isELR=True) )
                                calRels = set() # prevent duplications when same rel in different parts of tree
                prefix = cellValue(row, 'prefix', nameChars=True) or extensionSchemaPrefix
                if cellHasValue(row, 'name', str):
                    name = cellValue(row, 'name', nameChars=True)
                else:
                    name = None
                if cellHasValue(row, 'depth', int):
                    depth = cellValue(row, 'depth')
                else:
                    depth = None
                subsGrp = cellValue(row, 'substitutionGroup')
                isConcept = subsGrp in ("xbrli:item", "xbrli:tuple", 
                                        "xbrldt:hypercubeItem", "xbrldt:dimensionItem")
                if (not prefix or prefix == extensionSchemaPrefix) and name not in extensionElements and name:
                    # elements row
                    eltType = cellValue(row, 'type')
                    eltTypePrefix = cellValue(row, 'typePrefix')
                    if not eltType:
                        eltType = 'xbrli:stringItemType'
                    elif eltTypePrefix and ':' not in eltType:
                        eltType = eltTypePrefix + ':' + eltType
                    elif ':' not in eltType and eltType.endswith("ItemType"):
                        eltType = 'xbrli:' + eltType
                    abstract = cellValue(row, 'abstract')
                    nillable = cellValue(row, 'nillable')
                    balance = cellValue(row, 'balance')
                    periodType = cellValue(row, 'periodType')
                    eltAttrs = {"name": name, "id": (prefix or "") + "_" + name}
                    if eltType:
                        eltAttrs["type"] = eltType
                        checkImport(eltType)
                    if subsGrp:
                        eltAttrs["substitutionGroup"] = subsGrp
                        checkImport(subsGrp)
                    if abstract or subsGrp in ("xbrldt:hypercubeItem", "xbrldt:dimensionItem"):
                        eltAttrs["abstract"] = abstract or "true"
                    if nillable:
                        eltAttrs["nillable"] = nillable
                    if balance:
                        eltAttrs["{http://www.xbrl.org/2003/instance}balance"] = balance
                    if periodType:
                        eltAttrs["{http://www.xbrl.org/2003/instance}periodType"] = periodType
                    eltFacets = None
                    if eltType not in ("nonnum:domainItemType", "xbrli:booleanItemType", "xbrli:positiveIntegerItemType", "xbrli:dateItemType",
                                       "xbrli:gYearItemType"):
                        for facet in ("minLength", "maxLength", "length", "fixed", "pattern", "enumeration"):
                            v = cellValue(row, facet)
                            if v is not None:
                                if facet == "enumeration" and v.startswith("See tab "): # check for local or tab-contained enumeration
                                    _tab = v.split()[2]
                                    if _tab in sheetNames:
                                        enumWs = importExcelBook[_tab]
                                        v = "\n".join(" = ".join(col.value for col in row if col.value)
                                                      for i, row in enumerate(enumWs.rows)
                                                      if i > 0) # skip heading row
                                if eltFacets is None: eltFacets = {}
                                eltFacets[facet] = v
                    # if extension type is this schema, add extensionType for facets
                    if eltType and eltType.startswith(extensionSchemaPrefix + ":"):
                        _typeName = eltType.rpartition(":")[2]
                        if _typeName.endswith("ItemType"):
                            _baseType = "xbrli:tokenItemType" # should be a column??
                        else:
                            _baseType = "xs:token"
                        if _typeName not in extensionTypes:
                            extensionTypes[_typeName] = ({"name":_typeName, "base":_baseType},eltFacets)
                        extensionElements[name] = (eltAttrs, None)
                    else:
                        extensionElements[name] = (eltAttrs, eltFacets)
                useLabels = True
                if depth is not None:
                    if name is None:
                        _label = None
                        for colCell in row:
                            if colCell.value is not None:
                                _label = colCell.value
                                break
                        print ("Row {} has relationships and no \"name\" field, label: {}".format(iRow+1, _label))
                    if hasPreLB:
                        entryList = lbDepthList(preLB, depth)
                        preferredLabel = cellValue(row, 'preferredLabel')
                        if entryList is not None and isConcept:
                            if depth == topDepth:
                                entryList.append( LBentry(prefix=prefix, name=name, isRoot=True) )
                            else:
                                entryList.append( LBentry(prefix=prefix, name=name, arcrole=XbrlConst.parentChild,
                                                          role=preferredLabel) )
                    if hasDefLB:
                        entryList = lbDepthList(defLB, depth)
                        if entryList is not None:
                            if depth == topDepth:
                                if isConcept:
                                    entryList.append( LBentry(prefix=prefix, name=name, isRoot=True) )
                            else:
                                if (not preferredLabel or # prevent start/end labels from causing duplicate dim-mem relationships
                                    not any(lbEntry.prefix == prefix and lbEntry.name == name
                                            for lbEntry in entryList)):
                                    # check if entry is a typed dimension
                                    if name in extensionElements:
                                        eltAttrs = extensionElements.get(name, NULLENTRY)[0]
                                    else:
                                        eltAttrs = {}
                                    parentLBentry = lbDepthList(defLB, depth - 1)[-1]
                                    
                                    parentElementAttrs = extensionElements.get(parentLBentry.name,NULLENTRY)[0]
                                    if (isUSGAAP and # check for typed dimensions
                                        parentElementAttrs.get("substitutionGroup") == "xbrldt:dimensionItem"
                                        and eltAttrs.get("type") != "nonnum:domainItemType"):
                                        # typed dimension, no LBentry
                                        typedDomainRef = "#" + eltAttrs.get("id", "")
                                        parentElementAttrs["{http://xbrl.org/2005/xbrldt}typedDomainRef"] = typedDomainRef
                                    elif isConcept:
                                        # explicit dimension
                                        entryList.append( LBentry(prefix=prefix, name=name, arcrole="_dimensions_") )
                    if hasCalLB:
                        calcParents = cellValue(row, 'calculationParent', default='').split()
                        calcWeights = str(cellValue(row, 'calculationWeight', default='')).split() # may be float or string
                        if calcParents and calcWeights:
                            # may be multiple parents split by whitespace
                            for i, calcParent in enumerate(calcParents):
                                calcWeight = calcWeights[i] if i < len(calcWeights) else calcWeights[-1]
                                calcParentPrefix, sep, calcParentName = calcParent.partition(":")
                                entryList = lbDepthList(calLB, topDepth)
                                if entryList is not None:
                                    calRel = (calcParentPrefix, calcParentName, prefix, name)
                                    if calRel not in calRels:
                                        entryList.append( LBentry(prefix=calcParentPrefix, name=calcParentName, isRoot=True, childStruct=
                                                                  [LBentry(prefix=prefix, name=name, arcrole=XbrlConst.summationItem, weight=calcWeight )]) )
                                        calRels.add(calRel)
                                    else:
                                        pass
                                    
            # accumulate extension labels and any reference parts
            if useLabels:
                prefix = cellValue(row, 'prefix', nameChars=True) or extensionSchemaPrefix
                name = cellValue(row, 'name', nameChars=True)
                if name is not None:
                    preferredLabel = cellValue(row, 'preferredLabel')
                    for colItem, iCol in headerCols.items():
                        if isinstance(colItem, tuple):
                            colItemType = colItem[0]
                            role = colItem[1]
                            lang = part = colItem[2] # lang for label, part for reference
                            cell = row[iCol]
                            v = cell.value
                            if v is None or (isinstance(v, str) and not v):
                                values = ()
                            else:
                                v = str(v) # may be an int or float instead of str
                                if colItemType in ("label", "reference"):
                                    values = (v,)
                                elif colItemType == "labels":
                                    values = v.split('\n')
                                
                            if preferredLabel and "indented" in colItem:  # indented column sets preferredLabel if any
                                role = preferredLabel
                            for value in values:
                                if colItemType == "label":
                                    if not isConcept:
                                        if role == XbrlConst.standardLabel:
                                            role = XbrlConst.genStandardLabel # must go in generic labels LB
                                        else:
                                            continue
                                    extensionLabels[prefix, name, lang, role] = value.strip()
                                elif hasRefLB and colItemType == "reference":
                                    if isConcept:
                                        extensionReferences[prefix, name, role].add((part, value.strip()))
                            
        except Exception as err:
            fatalLoadingErrors.append("Excel row: {excelRow}, error: {error}, Traceback: {traceback}"
                               .format(error=err, excelRow=iRow, traceback=traceback.format_stack()))            # uncomment to debug raise
            
    if not headerCols:
        if not conceptsWs:
            fatalLoadingErrors.append("Neither control worksheet (XBRL DTS tab) nor standard columns found, no DTS imported.")
        elif not currentELR:
            fatalLoadingErrors.append("Extended link role not found, no DTS imported.")
            
    if fatalLoadingErrors:
        raise Exception(",\n ".join(fatalLoadingErrors))
            
    if isUSGAAP and hasDefLB:
        # move line items above table
        def fixUsggapTableDims(lvl1Struct, level=0):
            foundTable = False
            emptyLinks = []
            foundHeadingItems = []
            foundLineItems = []
            for lvl1Entry in lvl1Struct:
                for lvl2Entry in lvl1Entry.childStruct:
                    if lvl2Entry.name.endswith("Table") or lvl2Entry.name.endswith("Cube"):
                        for lvl3Entry in lvl2Entry.childStruct:
                            if lvl3Entry.name.endswith("LineItems"):
                                foundLineItems.append((lvl1Entry, lvl2Entry, lvl3Entry))
                                foundTable = True
                                break
                    else:
                        foundHeadingItems.append((lvl1Entry, lvl2Entry))
                if not foundLineItems:
                    foundNestedTable = fixUsggapTableDims(lvl1Entry.childStruct, level+1)
                    if level == 0 and not foundNestedTable:
                        emptyLinks.append(lvl1Entry)
                    foundTable |= foundNestedTable
                    del foundHeadingItems[:]
            for lvl1Entry, lvl2Entry, lvl3Entry in foundLineItems:
                i1 = lvl1Entry.childStruct.index(lvl2Entry)
                lvl1Entry.childStruct.insert(i1, lvl3Entry)  # must keep lvl1Rel if it is __root__
                lvl3Entry.childStruct.insert(0, lvl2Entry)
                if lvl1Entry.name.endswith("Abstract") or lvl1Entry.name.endswith("Root"):
                    lvl1Entry.childStruct.remove(lvl2Entry)
                lvl2Entry.childStruct.remove(lvl3Entry)
            for lvl1Entry, lvl2Entry in foundHeadingItems:
                lvl1Entry.childStruct.remove(lvl2Entry)
            for emptyLink in emptyLinks:
                lvl1Struct.remove(emptyLink)
                
            return foundTable
                
        fixUsggapTableDims(defLB)
        
    dts = cntlr.modelManager.create(newDocumentType=ModelDocument.Type.SCHEMA,
                                    url=extensionSchemaFilename,
                                    isEntry=True,
                                    base='', # block pathname from becomming absolute
                                    initialXml='''
    <schema xmlns="http://www.w3.org/2001/XMLSchema" 
        targetNamespace="{targetNamespace}" 
        attributeFormDefault="unqualified" 
        elementFormDefault="qualified" 
        xmlns:xs="http://www.w3.org/2001/XMLSchema" 
        xmlns:{extensionPrefix}="{targetNamespace}"
        {importXmlns} 
        xmlns:nonnum="http://www.xbrl.org/dtr/type/non-numeric" 
        xmlns:link="http://www.xbrl.org/2003/linkbase" 
        xmlns:xbrli="http://www.xbrl.org/2003/instance" 
        xmlns:xlink="http://www.w3.org/1999/xlink" 
        xmlns:xbrldt="http://xbrl.org/2005/xbrldt" 
        {schemaVersion} />
    '''.format(targetNamespace=extensionSchemaNamespaceURI,
               extensionPrefix=extensionSchemaPrefix,
               importXmlns=''.join('xmlns:{0}="{1}"\n'.format(prefix, namespaceURI)
                                   for prefix, namespaceURI in importXmlns.items()),
               schemaVersion='version="{}" '.format(extensionSchemaVersion) if extensionSchemaVersion else '',
               )
                           )
    dtsSchemaDocument = dts.modelDocument
    dtsSchemaDocument.inDTS = True  # entry document always in DTS
    dtsSchemaDocument.targetNamespace = extensionSchemaNamespaceURI # not set until schemaDiscover too late otherwise
    schemaElt = dtsSchemaDocument.xmlRootElement
    
    #foreach linkbase
    annotationElt = XmlUtil.addChild(schemaElt, XbrlConst.xsd, "annotation")
    appinfoElt = XmlUtil.addChild(annotationElt, XbrlConst.xsd, "appinfo")
    
    # add linkbaseRefs
    appinfoElt = XmlUtil.descendant(schemaElt, XbrlConst.xsd, "appinfo")
    
    # don't yet add linkbase refs, want to process imports first to get roleType definitions
        
    # add imports
    for importAttributes in sorted(imports.values()):
        XmlUtil.addChild(schemaElt, 
                         XbrlConst.xsd, "import",
                         attributes=importAttributes)
        
    _enumNum = [1] # must be inside an object to be referenced in a nested procedure
    
    def addFacets(restrElt, facets):
        if facets:
            for facet, facetValue in facets.items():
                if facet == "enumeration":
                    for valLbl in facetValue.split("\n"):
                        val, _sep, _label = valLbl.partition("=")
                        val = val.strip()
                        if val == "(empty)":
                            val = ""
                        _label = _label.strip()
                        if len(val):
                            _attributes = {"value":val.strip()}
                            if _label:
                                _name = "enum{}".format(_enumNum[0])
                                _attributes["id"] = extensionSchemaPrefix + "_" + _name
                                _enumNum[0] += 1
                                extensionLabels[extensionSchemaPrefix, _name, defaultLabelLang, XbrlConst.genStandardLabel] = _label
                            XmlUtil.addChild(restrElt, XbrlConst.xsd, facet, attributes=_attributes)
                else:
                    XmlUtil.addChild(restrElt, XbrlConst.xsd, facet, attributes={"value":str(facetValue)})

    # add elements
    for eltName, eltDef in sorted(extensionElements.items(), key=lambda item: item[0]):
        eltAttrs, eltFacets = eltDef
        if eltFacets and "type" in eltAttrs:
            eltType = eltAttrs["type"]
            del eltAttrs["type"]
        isConcept = eltAttrs.get('substitutionGroup') in (
            "xbrli:item", "xbrli:tuple", "xbrldt:hypercubeItem", "xbrldt:dimensionItem")
        elt = XmlUtil.addChild(schemaElt, 
                               XbrlConst.xsd, "element",
                               attributes=eltAttrs)
        if elt is not None and eltFacets and isConcept:
            cmplxType = XmlUtil.addChild(elt, XbrlConst.xsd, "complexType")
            cmplxCont = XmlUtil.addChild(cmplxType, XbrlConst.xsd, "simpleContent")
            restrElt = XmlUtil.addChild(cmplxCont, XbrlConst.xsd, "restriction", attributes={"base": eltType})
            addFacets(restrElt, eltFacets)
            del eltType
    # add types
    for typeName, typeDef in sorted(extensionTypes.items(), key=lambda item: item[0]):
        typeAttrs, typeFacets = typeDef
        if typeName.endswith("ItemType"):
            cmplxType = XmlUtil.addChild(schemaElt, XbrlConst.xsd, "complexType", attributes={"name": typeAttrs["name"]})
            contElt = XmlUtil.addChild(cmplxType, XbrlConst.xsd, "simpleContent")
        else:
            contElt = XmlUtil.addChild(schemaElt, XbrlConst.xsd, "simpleType", attributes={"name": typeAttrs["name"]})
        restrElt = XmlUtil.addChild(contElt, XbrlConst.xsd, "restriction", attributes={"base": typeAttrs["base"]})
        addFacets(restrElt, typeFacets)

    # add role definitions (for discovery)
    for roleURI, roleDefinition in sorted(extensionRoles.items(), key=lambda rd: rd[1]):
        roleElt = XmlUtil.addChild(appinfoElt, XbrlConst.link, "roleType",
                                   attributes=(("roleURI",  roleURI),
                                               ("id", "roleType_" + roleURI.rpartition("/")[2])))
        if roleDefinition:
            XmlUtil.addChild(roleElt, XbrlConst.link, "definition", text=roleDefinition)
        if hasPreLB:
            XmlUtil.addChild(roleElt, XbrlConst.link, "usedOn", text="link:presentationLink")
        if hasDefLB:
            XmlUtil.addChild(roleElt, XbrlConst.link, "usedOn", text="link:definitionLink")
        if hasCalLB:
            XmlUtil.addChild(roleElt, XbrlConst.link, "usedOn", text="link:calculationLink")
        
    dtsSchemaDocument.schemaDiscover(schemaElt, False, extensionSchemaNamespaceURI)

    def addLinkbaseRef(lbType, lbFilename, lbDoc):
        role = "http://www.xbrl.org/2003/role/{0}LinkbaseRef".format(lbType)
        lbRefElt = XmlUtil.addChild(appinfoElt, XbrlConst.link, "linkbaseRef",
                                    attributes=(("{http://www.w3.org/1999/xlink}type",  "simple"),
                                                ("{http://www.w3.org/1999/xlink}href",  lbFilename),
                                                ("{http://www.w3.org/1999/xlink}arcrole",  "http://www.w3.org/1999/xlink/properties/linkbase"),
                                                # generic label ref has no role
                                                ) + (() if lbType.startswith("generic") else
                                                     (("{http://www.w3.org/1999/xlink}role",  role),))
                                    )
        dtsSchemaDocument.referencesDocument[lbDoc] = ModelDocumentReference("href", lbRefElt) 
        
    # find extension label roles, reference roles and parts
    extLabelRoles = {}
    extReferenceRoles = {}
    extReferenceParts = {}
    extReferenceSchemaDocs = {}
    for _headerColKey in headerCols:
        if isinstance(_headerColKey, tuple) and len(_headerColKey) >= 3 and not _headerColKey[1].startswith("http://"):
            _resourceType = _headerColKey[0]
            _resourceRole = _headerColKey[1]
            _resourceLangOrPart = _headerColKey[2]
            _resourceQName, _standardRoles = {
                    "label": (qnLinkLabel, standardLabelRoles), 
                    "reference": (qnLinkReference, standardReferenceRoles)
                    }[_resourceType]
            _resourceRoleURI = None
            # find resource role
            for _roleURI in _standardRoles:
                if _roleURI.endswith(_resourceRole):
                    _resourceRoleURI = _roleURI
                    break
            if _resourceRoleURI is None: # try custom roles
                _resourceRoleMatchPart = _resourceRole.partition("#")[0] # remove # part
                for _roleURI in dts.roleTypes:
                    if _roleURI.endswith(_resourceRoleMatchPart):
                        for _roleType in dts.roleTypes[_roleURI]:
                            if _resourceQName in _roleType.usedOns:
                                _resourceRoleURI = _roleURI
                                break
            if _resourceType == "label" and _resourceRoleURI:
                extLabelRoles[_resourceRole] = _resourceRoleURI
            elif _resourceType == "reference" and _resourceRoleURI:
                extReferenceRoles[_resourceRole] = _resourceRoleURI
                # find part QName
                for partConcept in dts.nameConcepts.get(_resourceLangOrPart, ()):
                    if partConcept is not None and partConcept.subGroupHeadQname == qnLinkPart:
                        extReferenceParts[_resourceLangOrPart] = partConcept.qname
                        extReferenceSchemaDocs[partConcept.qname.namespaceURI] = (
                            partConcept.modelDocument.uri if partConcept.modelDocument.uri.startswith("http://") else
                            partConcept.modelDocument.basename)
                        break

    # label linkbase
    for lbType, lang, filename in labelLinkbases:
        _isGeneric = lbType.startswith("generic")
        if _isGeneric and "http://xbrl.org/2008/label" not in dts.namespaceDocs:
            # must pre-load generic linkbases in order to create properly typed elements (before discovery because we're creating elements by lxml)
            ModelDocument.load(dts, "http://www.xbrl.org/2008/generic-link.xsd", isDiscovered=True)
            ModelDocument.load(dts, "http://www.xbrl.org/2008/generic-label.xsd", isDiscovered=True)
        lbDoc = ModelDocument.create(dts, ModelDocument.Type.LINKBASE, filename, base="", initialXml="""
        <linkbase 
            xmlns="http://www.xbrl.org/2003/linkbase" 
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
            xmlns:xlink="http://www.w3.org/1999/xlink" 
            xmlns:xbrli="http://www.xbrl.org/2003/instance"
            {}
            xsi:schemaLocation="http://www.xbrl.org/2003/linkbase 
            http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd{}" 
            >{}</linkbase>
        """.format("""
            xmlns:genlink="http://xbrl.org/2008/generic"
            xmlns:genlabel="http://xbrl.org/2008/label"
            """ if _isGeneric else "",
                   """
            http://xbrl.org/2008/generic  http://www.xbrl.org/2008/generic-link.xsd
            http://xbrl.org/2008/label  http://www.xbrl.org/2008/generic-label.xsd
            """ if _isGeneric else "",
            """
            <arcroleRef arcroleURI="http://xbrl.org/arcrole/2008/element-label" xlink:href="http://www.xbrl.org/2008/generic-label.xsd#element-label" xlink:type="simple"/>
            """ if _isGeneric else ""))
        lbDoc.inDTS = True
        addLinkbaseRef(lbType, filename, lbDoc)
        lbElt = lbDoc.xmlRootElement
        linkElt = XmlUtil.addChild(lbElt, 
                                   gen if _isGeneric else link, 
                                   "link" if _isGeneric else "labelLink",
                                   attributes=(("{http://www.w3.org/1999/xlink}type", "extended"),
                                               ("{http://www.w3.org/1999/xlink}role", defaultLinkRole)))
        firstLinkElt = linkElt
        locs = set()
        roleRefs = set()
        for labelKey, text in extensionLabels.items():
            prefix, name, labelLang, role = labelKey
            labelLang = labelLang or defaultLabelLang
            role = extLabelRoles.get(role, role) # get custom role, if any
            if lang == labelLang and _isGeneric == (role in (XbrlConst.genStandardLabel, XbrlConst.genDocumentationLabel)):
                locLabel = prefix + "_" + name
                if locLabel not in locs:
                    locs.add(locLabel)
                    XmlUtil.addChild(linkElt,
                                     XbrlConst.link, "loc",
                                     attributes=(("{http://www.w3.org/1999/xlink}type", "locator"),
                                                 ("{http://www.w3.org/1999/xlink}href", extensionHref(prefix, name)),
                                                 ("{http://www.w3.org/1999/xlink}label", locLabel)))        
                    XmlUtil.addChild(linkElt,
                                     gen if _isGeneric else link, 
                                     "arc" if _isGeneric else "labelArc",
                                     attributes=(("{http://www.w3.org/1999/xlink}type", "arc"),
                                                 ("{http://www.w3.org/1999/xlink}arcrole", elementLabel if _isGeneric else conceptLabel),
                                                 ("{http://www.w3.org/1999/xlink}from", locLabel), 
                                                 ("{http://www.w3.org/1999/xlink}to", "label_" + locLabel), 
                                                 ("order", 1.0)))
                XmlUtil.addChild(linkElt,
                                 XbrlConst.genLabel if _isGeneric else XbrlConst.link, 
                                 "label",
                                 attributes=(("{http://www.w3.org/1999/xlink}type", "resource"),
                                             ("{http://www.w3.org/1999/xlink}label", "label_" + locLabel),
                                             ("{http://www.w3.org/1999/xlink}role", role),
                                             ("{http://www.w3.org/XML/1998/namespace}lang", lang)),
                                 text=text)
                if role:
                    if role in dts.roleTypes:
                        roleType = dts.roleTypes[role][0]
                        roleRefs.add(("roleRef", role, roleType.modelDocument.uri + "#" + roleType.id))
                    elif role.startswith("http://www.xbrl.org/2009/role/negated"):
                        roleRefs.add(("roleRef", role, "http://www.xbrl.org/lrr/role/negated-2009-12-16.xsd#" + role.rpartition("/")[2]))
        # add arcrole references
        for roleref, roleURI, href in roleRefs:
            XmlUtil.addChild(lbElt,
                             XbrlConst.link, roleref,
                             attributes=(("arcroleURI" if roleref == "arcroleRef" else "roleURI", roleURI),
                                         ("{http://www.w3.org/1999/xlink}type", "simple"),
                                         ("{http://www.w3.org/1999/xlink}href", href)),
                             beforeSibling=firstLinkElt)
        lbDoc.linkbaseDiscover(lbElt)  
                     
    # reference linkbase
    for lbType, referenceRole, filename in referenceLinkbases:
        _isGeneric = lbType.startswith("generic")
        lbDoc = ModelDocument.create(dts, ModelDocument.Type.LINKBASE, filename, base="", initialXml="""
        <linkbase 
            xmlns="http://www.xbrl.org/2003/linkbase" 
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
            xmlns:xlink="http://www.w3.org/1999/xlink" 
            xmlns:xbrli="http://www.xbrl.org/2003/instance"
            {}
            xsi:schemaLocation="http://www.xbrl.org/2003/linkbase 
            http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd{}{}" 
            >{}</linkbase>
        """.format("""
            xmlns:genlink="http://xbrl.org/2008/generic"
            xmlns:genreference="http://xbrl.org/2008/rerference"
            """ if _isGeneric else "",
            "".join([" {} {}".format(_ns, _uri) for _ns, _uri in extReferenceSchemaDocs.items()]),
            """
            http://xbrl.org/2008/generic  http://www.xbrl.org/2008/generic-link.xsd
            http://xbrl.org/2008/reference  http://www.xbrl.org/2008/generic-reference.xsd
            """ if _isGeneric else "",
            """
            <roleRef roleURI="http://www.xbrl.org/2008/role/label" xlink:href="http://www.xbrl.org/2008/generic-label.xsd#standard-label" xlink:type="simple"/>
            <arcroleRef arcroleURI="http://xbrl.org/arcrole/2008/element-reference" xlink:href="http://xbrl.org/2008/generic-reference.xsd#element-reference" xlink:type="simple"/>
            """ if _isGeneric else ""))
        lbDoc.inDTS = True
        addLinkbaseRef(lbType, filename, lbDoc)
        lbElt = lbDoc.xmlRootElement
        linkElt = XmlUtil.addChild(lbElt, 
                                   XbrlConst.gen if _isGeneric else XbrlConst.link, 
                                   "link" if _isGeneric else "referenceLink",
                                   attributes=(("{http://www.w3.org/1999/xlink}type", "extended"),
                                               ("{http://www.w3.org/1999/xlink}role", defaultLinkRole)))
        firstLinkElt = linkElt
        locs = set()
        roleRefs = set()
        for referenceKey, references in extensionReferences.items():
            prefix, name, role = referenceKey
            role = extReferenceRoles.get(role, role) # get custom role, if any
            if role == referenceRole:
                locLabel = prefix + "_" + name
                if locLabel not in locs:
                    locs.add(locLabel)
                    XmlUtil.addChild(linkElt,
                                     XbrlConst.link, "loc",
                                     attributes=(("{http://www.w3.org/1999/xlink}type", "locator"),
                                                 ("{http://www.w3.org/1999/xlink}href", extensionHref(prefix, name)),
                                                 ("{http://www.w3.org/1999/xlink}label", locLabel)))        
                    XmlUtil.addChild(linkElt,
                                     XbrlConst.link, "referenceArc",
                                     attributes=(("{http://www.w3.org/1999/xlink}type", "arc"),
                                                 ("{http://www.w3.org/1999/xlink}arcrole", conceptReference),
                                                 ("{http://www.w3.org/1999/xlink}from", locLabel), 
                                                 ("{http://www.w3.org/1999/xlink}to", "label_" + locLabel), 
                                                 ("order", 1.0)))
                referenceResource = XmlUtil.addChild(linkElt,
                                 XbrlConst.genReference if _isGeneric else XbrlConst.link, 
                                 "reference",
                                 attributes=(("{http://www.w3.org/1999/xlink}type", "resource"),
                                             ("{http://www.w3.org/1999/xlink}label", "label_" + locLabel),
                                             ("{http://www.w3.org/1999/xlink}role", role)))
                for part, text in sorted(references):
                    partQn = extReferenceParts.get(part, part) # get part QName if any
                    XmlUtil.addChild(referenceResource, partQn, text=text)
                if role:
                    if role in dts.roleTypes:
                        roleType = dts.roleTypes[role][0]
                        roleRefs.add(("roleRef", role, roleType.modelDocument.uri + "#" + roleType.id))
                    elif role.startswith("http://www.xbrl.org/2009/role/negated"):
                        roleRefs.add(("roleRef", role, "http://www.xbrl.org/lrr/role/negated-2009-12-16.xsd#" + role.rpartition("/")[2]))
        # add arcrole references
        for roleref, roleURI, href in roleRefs:
            XmlUtil.addChild(lbElt,
                             XbrlConst.link, roleref,
                             attributes=(("arcroleURI" if roleref == "arcroleRef" else "roleURI", roleURI),
                                         ("{http://www.w3.org/1999/xlink}type", "simple"),
                                         ("{http://www.w3.org/1999/xlink}href", href)),
                             beforeSibling=firstLinkElt)
        lbDoc.linkbaseDiscover(lbElt)  
        
    def hrefConcept(prefix, name):
        qn = schemaElt.prefixedNameQname("{}:{}".format(prefix, name))
        if qn in dts.qnameConcepts:
            return dts.qnameConcepts[qn]
        return None
            
    def lbTreeWalk(lbType, parentElt, lbStruct, roleRefs, locs=None, arcsFromTo=None, fromPrefix=None, fromName=None):
        order = 1.0
        for lbEntry in lbStruct:
            if lbEntry.isELR:
                role = "unspecified"
                if lbEntry.role and lbEntry.role.startswith("http://"): # have a role specified
                    role = lbEntry.role
                elif lbEntry.name: #may be a definition
                    for linkroleUri, modelRoleTypes in dts.roleTypes.items():
                        definition = modelRoleTypes[0].definition
                        if lbEntry.name == definition:
                            role = linkroleUri
                            break
                if role == "unspecified":
                    print ("Role {} has no role definition".format(lbEntry.name))
                if role != XbrlConst.defaultLinkRole and role in dts.roleTypes: # add roleRef
                    roleType = modelRoleTypes[0]
                    roleRefs.add(("roleRef", role, roleType.modelDocument.uri + "#" + roleType.id))
                linkElt = XmlUtil.addChild(parentElt, 
                                           XbrlConst.link, lbType + "Link",
                                           attributes=(("{http://www.w3.org/1999/xlink}type", "extended"),
                                                       ("{http://www.w3.org/1999/xlink}role", role)))
                locs = set()
                arcsFromTo = set()
                lbTreeWalk(lbType, linkElt, lbEntry.childStruct, roleRefs, locs, arcsFromTo)
            else:
                toPrefix = lbEntry.prefix
                toName = lbEntry.name
                toHref = extensionHref(toPrefix, toName)
                toLabel = "{}_{}".format(toPrefix, toName)
                toLabelAlt = None
                if not lbEntry.isRoot:
                    fromLabel = "{}_{}".format(fromPrefix, fromName)
                    if (fromLabel, toLabel) in arcsFromTo:
                        # need extra loc to prevent arc from/to duplication in ELR
                        for i in range(1, 1000):
                            toLabelAlt = "{}_{}".format(toLabel, i)
                            if (fromLabel, toLabelAlt) not in arcsFromTo:
                                toLabel = toLabelAlt
                                break
                if toHref not in locs or toLabelAlt:
                    XmlUtil.addChild(parentElt,
                                     XbrlConst.link, "loc",
                                     attributes=(("{http://www.w3.org/1999/xlink}type", "locator"),
                                                 ("{http://www.w3.org/1999/xlink}href", toHref),
                                                 ("{http://www.w3.org/1999/xlink}label", toLabel)))        
                    locs.add(toHref)
                if not lbEntry.isRoot:
                    arcsFromTo.add( (fromLabel, toLabel) )
                    if lbType == "calculation" and lbEntry.weight is not None:
                        otherAttrs = ( ("weight", lbEntry.weight), )
                    elif lbType == "presentation" and lbEntry.role:
                        if not lbEntry.role.startswith("http://"):
                            # check if any defined labels for this role
                            _labelRoleMatchPart = "/" + lbEntry.role
                            for _roleURI in dts.roleTypes:
                                if _roleURI.endswith(_labelRoleMatchPart):
                                    for _roleType in dts.roleTypes[_roleURI]:
                                        if XbrlConst.qnLinkLabel in _roleType.usedOns:
                                            lbEntry.role = _roleURI
                                            break
                        if not lbEntry.role.startswith("http://"):
                            # default to built in label roles
                            lbEntry.role = "http://www.xbrl.org/2003/role/" + lbEntry.role
                        otherAttrs = ( ("preferredLabel", lbEntry.role), )
                        if lbEntry.role and lbEntry.role in dts.roleTypes:
                            roleType = dts.roleTypes[lbEntry.role][0]
                            roleRefs.add(("roleRef", lbEntry.role, roleType.modelDocument.uri + "#" + roleType.id))
                    else:
                        otherAttrs = ( )
                    if lbEntry.arcrole == "_dimensions_":  # pick proper consecutive arcrole
                        fromConcept = hrefConcept(fromPrefix, fromName)
                        toConcept = hrefConcept(toPrefix, toName)
                        if toConcept is not None and toConcept.isHypercubeItem:
                            arcrole = XbrlConst.all
                            otherAttrs += ( (XbrlConst.qnXbrldtContextElement, "segment"), )
                        elif toConcept is not None and toConcept.isDimensionItem:
                            arcrole = XbrlConst.hypercubeDimension
                        elif fromConcept is not None and fromConcept.isDimensionItem:
                            arcrole = XbrlConst.dimensionDomain
                        else:
                            arcrole = XbrlConst.domainMember
                    else:
                        arcrole = lbEntry.arcrole
                    XmlUtil.addChild(parentElt,
                                     XbrlConst.link, lbType + "Arc",
                                     attributes=(("{http://www.w3.org/1999/xlink}type", "arc"),
                                                 ("{http://www.w3.org/1999/xlink}arcrole", arcrole),
                                                 ("{http://www.w3.org/1999/xlink}from", fromLabel), 
                                                 ("{http://www.w3.org/1999/xlink}to", toLabel), 
                                                 ("order", order)) + otherAttrs )
                    order += 1.0
                if lbType != "calculation" or lbEntry.isRoot:
                    lbTreeWalk(lbType, parentElt, lbEntry.childStruct, roleRefs, locs, arcsFromTo, toPrefix, toName)
                    
    for hasLB, lbType, lbLB in ((hasPreLB, "presentation", preLB),
                                (hasDefLB, "definition", defLB),
                                (hasCalLB, "calculation", calLB)):
        if hasLB:
            for lbRefType, filename in linkbaseRefs:
                if lbType == lbRefType:
                    # output presentation linkbase
                    lbDoc = ModelDocument.create(dts, ModelDocument.Type.LINKBASE, filename, base='', initialXml="""
                    <linkbase 
                        xmlns="http://www.xbrl.org/2003/linkbase" 
                        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
                        xsi:schemaLocation="http://www.xbrl.org/2003/linkbase 
                        http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd" 
                        xmlns:xlink="http://www.w3.org/1999/xlink" 
                        xmlns:xbrli="http://www.xbrl.org/2003/instance"/>
                    """)
                    lbDoc.inDTS = True
                    addLinkbaseRef(lbRefType, filename, lbDoc)
                    lbElt = lbDoc.xmlRootElement
                    roleRefs = set()
                    if lbType == "definition":
                        roleRefs.update((("arcroleRef", XbrlConst.all, "http://www.xbrl.org/2005/xbrldt-2005.xsd#all"),
                                         ("arcroleRef", XbrlConst.dimensionDefault, "http://www.xbrl.org/2005/xbrldt-2005.xsd#dimension-default"),
                                         ("arcroleRef", XbrlConst.dimensionDomain, "http://www.xbrl.org/2005/xbrldt-2005.xsd#dimension-domain"),
                                         ("arcroleRef", XbrlConst.domainMember, "http://www.xbrl.org/2005/xbrldt-2005.xsd#domain-member"),
                                         ("arcroleRef", XbrlConst.hypercubeDimension, "http://www.xbrl.org/2005/xbrldt-2005.xsd#hypercube-dimension")))
                    lbTreeWalk(lbType, lbElt, lbLB, roleRefs)
                    firstLinkElt = None
                    for firstLinkElt in lbElt.iterchildren():
                        break
                    # add arcrole references
                    for roleref, roleURI, href in roleRefs:
                        XmlUtil.addChild(lbElt,
                                         link, roleref,
                                         attributes=(("arcroleURI" if roleref == "arcroleRef" else "roleURI", roleURI),
                                                     ("{http://www.w3.org/1999/xlink}type", "simple"),
                                                     ("{http://www.w3.org/1999/xlink}href", href)),
                                         beforeSibling=firstLinkElt)
                    lbDoc.linkbaseDiscover(lbElt)  
                    break
    
    #cntlr.addToLog("Completed in {0:.2} secs".format(time.time() - startedAt),
    #               messageCode="loadFromExcel:info")
    
    if priorCWD:
        os.chdir(priorCWD) # restore prior current working directory
    return dts

def modelManagerLoad(modelManager, fileSource, *args, **kwargs):
    # check if an excel file
    try:
        filename = fileSource.url # if a string has no url attribute
    except:
        filename = fileSource # may be just a string
        
    if not (filename.endswith(".xlsx") or filename.endswith(".xls")):
        return None # not an Excel file

    cntlr = modelManager.cntlr
    cntlr.showStatus(_("Loading Excel workbook: {0}").format(os.path.basename(filename)))
    dts = loadFromExcel(cntlr, filename)
    dts.loadedFromExcel = True
    return dts

def guiXbrlLoaded(cntlr, modelXbrl, attach, *args, **kwargs):
    if cntlr.hasGui and getattr(modelXbrl, "loadedFromExcel", False):
        from arelle import ModelDocument
        from tkinter.filedialog import askdirectory
        outputDtsDir = askdirectory(parent=cntlr.parent,
                                    initialdir=cntlr.config.setdefault("outputDtsDir","."),
                                    title='Please select a directory for output DTS Contents')
        cntlr.config["outputDtsDir"] = outputDtsDir
        cntlr.saveConfig()
        if outputDtsDir:
            def saveToFile(url):
                if os.path.isabs(url):
                    return url
                return os.path.join(outputDtsDir, url)
            # save entry schema
            dtsSchemaDocument = modelXbrl.modelDocument
            dtsSchemaDocument.save(saveToFile(dtsSchemaDocument.uri), updateFileHistory=False)
            cntlr.showStatus(_("Saving XBRL DTS: {0}").format(os.path.basename(dtsSchemaDocument.uri)))
            for lbDoc in dtsSchemaDocument.referencesDocument.keys():
                if lbDoc.inDTS and lbDoc.type == ModelDocument.Type.LINKBASE:
                    cntlr.showStatus(_("Saving XBRL DTS: {0}").format(os.path.basename(lbDoc.uri)))
                    lbDoc.save(saveToFile(lbDoc.uri), updateFileHistory=False)
        cntlr.showStatus(_("Excel loading completed"), 3500)

def cmdLineXbrlLoaded(cntlr, options, modelXbrl, *args, **kwargs):
    if options.saveExcelDTSdirectory and getattr(modelXbrl, "loadedFromExcel", False):
        from arelle import ModelDocument
        def saveToFile(url):
            if os.path.isabs(url):
                return url
            return os.path.join(options.saveExcelDTSdirectory, url)
        # save entry schema
        dtsSchemaDocument = modelXbrl.modelDocument
        dtsSchemaDocument.save(saveToFile(dtsSchemaDocument.uri))
        cntlr.showStatus(_("Saving XBRL DTS: {0}").format(os.path.basename(dtsSchemaDocument.uri)))
        for lbDoc in dtsSchemaDocument.referencesDocument.keys():
            if lbDoc.inDTS and lbDoc.type == ModelDocument.Type.LINKBASE:
                cntlr.showStatus(_("Saving XBRL DTS: {0}").format(os.path.basename(lbDoc.uri)))
                lbDoc.save(saveToFile(lbDoc.uri))

def excelLoaderOptionExtender(parser, *args, **kwargs):
    parser.add_option("--save-Excel-DTS-directory", 
                      action="store", 
                      dest="saveExcelDTSdirectory", 
                      help=_("Save a DTS loaded from Excel into this directory."))

class LBentry:
    __slots__ = ("prefix", "name", "arcrole", "role", "childStruct")
    def __init__(self, prefix=None, name=None, arcrole=None, role=None, weight=None, 
                 isELR=False, isRoot=False, childStruct=None):
        if childStruct is not None:
            self.childStruct = childStruct
        else:
            self.childStruct = []
        self.prefix = prefix
        self.name = name
        if isELR:
            self.arcrole = "_ELR_"
        elif isRoot:
            self.arcrole = "_root_"
        else:
            self.arcrole = arcrole
        if weight is not None:  # summationItem
            self.role = weight
        else:
            self.role = role
            
    @property
    def isELR(self):
        return self.arcrole == "_ELR_"
            
    @property
    def isRoot(self):
        return self.arcrole == "_root_"
    
    @property
    def weight(self):
        if self.arcrole == summationItem:
            return self.role
        return None
    
    def __repr__(self):
        return "LBentry(prefix={},name={})".format(self.prefix,self.name)
    
__pluginInfo__ = {
    'name': 'Load From Excel',
    'version': '0.9',
    'description': "This plug-in loads XBRL from Excel and saves the resulting XBRL DTS.",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2013 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'ModelManager.Load': modelManagerLoad,
    'CntlrWinMain.Xbrl.Loaded': guiXbrlLoaded,
    'CntlrCmdLine.Options': excelLoaderOptionExtender,
    'CntlrCmdLine.Xbrl.Loaded': cmdLineXbrlLoaded
}
