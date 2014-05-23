# -*- coding: utf-8 -*-

'''
loadFromExcel.py is an example of a plug-in that will load an extension taxonomy from Excel
input and optionally save an (extension) DTS.

(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
import os, io, time, re
from arelle import XbrlConst

importColumnHeaders = {
    "名前空間プレフィックス": "prefix",
    "prefix": "prefix",
    "要素名": "name",
    "name": "name",
    "type": "type",
    "substitutionGroup": "substitutionGroup",
    "periodType": "periodType",
    "balance": "balance",
    "abstract": "abstract",
    "nillable": "nillable",
    "depth": "depth",
    "preferred label": "preferredLabel",
    "calculation parent": "calculationParent", # qname
    "calculation weight": "calculationWeight",
    "標準ラベル（日本語）": ("label", XbrlConst.standardLabel, "ja", "indented"),
    "冗長ラベル（日本語）": ("label", XbrlConst.verboseLabel, "ja"),
    "標準ラベル（英語）": ("label", XbrlConst.standardLabel, "en"),
    "冗長ラベル（英語）": ("label", XbrlConst.verboseLabel, "en"),
    "用途区分、財務諸表区分及び業種区分のラベル（日本語）": ("labels", XbrlConst.standardLabel, "ja"),
    "用途区分、財務諸表区分及び業種区分のラベル（英語）": ("labels", XbrlConst.standardLabel, "en"),
    "label": ("label", XbrlConst.standardLabel, "en", "indented"),
    "label, standard": ("label", XbrlConst.standardLabel, "en", "overridePreferred"),
    "label, terse": ("label", XbrlConst.terseLabel, "en"),
    "label, verbose": ("label", XbrlConst.verboseLabel, "en"),
    }

def loadFromExcel(cntlr, excelFile):
    from arelle import xlrd
    from arelle.xlrd.sheet import empty_cell
    from arelle import ModelDocument, ModelXbrl, XmlUtil
    from arelle.ModelDocument import ModelDocumentReference
    from arelle.ModelValue import qname
    
    startedAt = time.time()
    
    importExcelBook = xlrd.open_workbook(excelFile)
    controlSheet = importExcelBook.sheet_by_index(1)
    imports = {"xbrli": ( ("namespace", XbrlConst.xbrli), 
                          ("schemaLocation", "http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd") )} # xml of imports
    importXmlns = {}
    linkbaseRefs = []
    labelLinkbases = []
    hasPreLB = hasCalLB = hasDefLB = False
    # xxxLB structure [ (elr1, def1, "_ELR_", [roots]), (elr2, def2, "_ELR_", [rootw]) ...]
    #   roots = (rootHref, None, "_root_", [children])
    #   children = (childPrefix, childName, arcrole, [grandChildren])
    preLB = []
    defLB = []
    calLB = []
    
    def lbDepthList(lbStruct, depth, parentList=None):
        if depth == 0:
            return lbStruct[-1].childStruct
        return lbDepthList(lbStruct[-1].childStruct, depth-1, list)
    
    extensionElements = {}
    extensionRoles = {} # key is roleURI, value is role definition
    extensionLabels = {}  # key = (prefix, name, lang, role), value = label text
    
    def extensionHref(prefix, name):
        if prefix == extensionSchemaPrefix:
            filename = extensionSchemaFilename
        elif prefix in imports:
            filename = imports[prefix][1][1]
        else:
            return None
        return "{0}#{1}_{2}".format(filename, prefix, name)
            
    isUSGAAP = False
    for iRow in range(1, controlSheet.nrows):
        try:
            row = controlSheet.row(iRow)
            if (row[0].ctype == xlrd.XL_CELL_EMPTY):  # skip if col 1 is empty
                continue
            action = row[0].value
            filetype = row[1].value
            prefix = row[2].value
            filename = row[3].value
            namespaceURI = row[4].value
            lbType = lang = None
            if action == "import":
                imports[prefix] = ( ("namespace", namespaceURI), ("schemaLocation", filename) )
                importXmlns[prefix] = namespaceURI
                if re.match(r"http://[^/]+/us-gaap/", namespaceURI):
                    isUSGAAP = True
            elif action == "extension":
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
                        lang = typeLang[1]
                    else:
                        lang = "en"
                    if lbType == "label":
                        labelLinkbases.append((lang, filename))
                    elif lbType == "presentation":
                        hasPreLB = True
                    elif lbType == "definition":
                        hasDefLB = True
                    elif lbType == "calculation":
                        hasCalLB = True
                    linkbaseRefs.append( (lbType, filename) )
                elif filetype == "role" and namespaceURI:
                    extensionRoles[namespaceURI] = filename
                
        except Exception as err:
            cntlr.addToLog("Exception: {error}, Excel row: {excelRow}"
                           .format(error=err,
                                   excelRow=iRow),
                            messageCode="importExcel:exception")
            
    if not isUSGAAP: # need extra namespace declaration
        importXmlns["iod"] = "http://disclosure.edinet-fsa.go.jp/taxonomy/common/2013-03-31/iod"
    
    importExcelSheet = importExcelBook.sheet_by_index(0)
    # find column headers row
    headerCols = {}
    headerRows = set()
    
    # find out which rows are header rows
    for iRow in range(0, importExcelSheet.nrows):
        row = importExcelSheet.row(iRow)
        for iCol, colCell in enumerate(row):
            v = colCell.value
            if v in importColumnHeaders:
                headerCols[importColumnHeaders[v]] = iCol
        if all(colName in headerCols
               for colName in ("name", "type", "depth")): # must have these to be a header col
            # it's a header col
            headerRows.add(iRow)
        headerCols.clear()
        
    def cellValue(row, header):
        if header in headerCols:
            iCol = headerCols[header]
            if iCol < len(row):
                return row[iCol].value
        return ''
    
    def checkImport(qname):
        prefix, sep, localName = qname.partition(":")
        if sep:
            if prefix not in imports:
                if prefix == "xbrldt":
                    imports["xbrldt"] = ("namespace", XbrlConst.xbrldt), ("schemaLocation", "http://www.xbrl.org/2005/xbrldt-2005.xsd")
                elif prefix == "nonnum":
                    imports["nonnum"] = ("namespace", "http://www.xbrl.org/dtr/type/non-numeric"), ("schemaLocation", "http://www.xbrl.org/dtr/type/nonNumeric-2009-12-16.xsd")
                else:
                    cntlr.addToLog("Warning: prefix schema file is not imported for: {qname}"
                           .format(qname=qname),
                            messageCode="importExcel:warning")

    
    # find header rows
    currentELR = currentELRdefinition = None
    for iRow in range(0, importExcelSheet.nrows):
        useLabels = False
        try:
            row = importExcelSheet.row(iRow)
            isHeaderRow = iRow in headerRows
            isELRrow = (iRow + 1) in headerRows
            if isHeaderRow:
                headerCols.clear()
                for iCol, colCell in enumerate(row):
                    v = colCell.value
                    if v in importColumnHeaders:
                        headerCols[importColumnHeaders[v]] = iCol
            elif isELRrow:
                currentELR = currentELRdefinition = None
                for colCell in row:
                    v = colCell.value
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
                prefix = cellValue(row, 'prefix').strip()
                name = cellValue(row, 'name').strip()
                if "depth" in headerCols:
                    try:
                        depth = int(cellValue(row, 'depth'))
                    except ValueError:
                        depth = None
                else:
                    depth = None
                if prefix == extensionSchemaPrefix and name not in extensionElements:
                    # elements row
                    eltType = cellValue(row, 'type')
                    subsGrp = cellValue(row, 'substitutionGroup')
                    abstract = cellValue(row, 'abstract')
                    nillable = cellValue(row, 'nillable')
                    balance = cellValue(row, 'balance')
                    periodType = cellValue(row, 'periodType')
                    newElt = [ ("name", name), ("id", prefix + "_" + name) ]                        
                    if eltType:
                        newElt.append( ("type", eltType) )
                        checkImport(eltType)
                    if subsGrp:
                        newElt.append( ("substitutionGroup", subsGrp) )
                        checkImport(subsGrp)
                    if abstract or subsGrp in ("xbrldt:hypercubeItem", "xbrldt:dimensionItem"):
                        newElt.append( ("abstract", abstract or "true") )
                    if nillable:
                        newElt.append( ("nillable", nillable) )
                    if balance:
                        newElt.append( ("{http://www.xbrl.org/2003/instance}balance", balance) )
                    if periodType:
                        newElt.append( ("{http://www.xbrl.org/2003/instance}periodType", periodType) )
                    extensionElements[name] = newElt
                useLabels = True
                if depth is not None:
                    if hasPreLB:
                        entryList = lbDepthList(preLB, depth)
                        preferredLabel = cellValue(row, 'preferredLabel')
                        if preferredLabel and not preferredLabel.startswith("http://"):
                            preferredLabel = "http://www.xbrl.org/2003/role/" + preferredLabel
                        if entryList is not None:
                            if depth == 0:
                                entryList.append( LBentry(prefix=prefix, name=name, isRoot=True) )
                            else:
                                entryList.append( LBentry(prefix=prefix, name=name, arcrole=XbrlConst.parentChild,
                                                          role=preferredLabel) )
                    if hasDefLB:
                        entryList = lbDepthList(defLB, depth)
                        if entryList is not None:
                            if depth == 0:
                                entryList.append( LBentry(prefix=prefix, name=name, isRoot=True) )
                            else:
                                if (not preferredLabel or # prevent start/end labels from causing duplicate dim-mem relationships
                                    not any(lbEntry.prefix == prefix and lbEntry.name == name
                                            for lbEntry in entryList)):
                                    entryList.append( LBentry(prefix=prefix, name=name, arcrole="_dimensions_") )
                    if hasCalLB:
                        calcParent = cellValue(row, 'calculationParent')
                        calcWeight = cellValue(row, 'calculationWeight')
                        if calcParent and calcWeight:
                            calcParentPrefix, sep, calcParentName = calcParent.partition(":")
                            entryList = lbDepthList(calLB, 0)
                            if entryList is not None:
                                calRel = (calcParentPrefix, calcParentName, prefix, name)
                                if calRel not in calRels:
                                    entryList.append( LBentry(prefix=calcParentPrefix, name=calcParentName, isRoot=True, childStruct=
                                                              [LBentry(prefix=prefix, name=name, arcrole=XbrlConst.summationItem, weight=calcWeight )]) )
                                    calRels.add(calRel)
                                else:
                                    pass
                                    
            # accumulate extension labels
            if useLabels:
                prefix = cellValue(row, 'prefix').strip()
                name = cellValue(row, 'name').strip()
                preferredLabel = cellValue(row, 'preferredLabel')
                if preferredLabel and not preferredLabel.startswith("http://"):
                    preferredLabel = "http://www.xbrl.org/2003/role/" + preferredLabel
                for colItem, iCol in headerCols.items():
                    if isinstance(colItem, tuple):
                        colItemType = colItem[0]
                        role = colItem[1]
                        lang = colItem[2]
                        cell = row[iCol]
                        if cell.ctype == xlrd.XL_CELL_EMPTY:
                            values = ()
                        elif colItemType == "label":
                            values = (cell.value,)
                        elif colItemType == "labels":
                            values = cell.value.split('\n')
                        else:
                            values = ()
                        if preferredLabel and "indented" in colItem:  # indented column sets preferredLabel if any
                            role = preferredLabel
                        for value in values:
                            extensionLabels[prefix, name, lang, role] = value.strip()
        except Exception as err:
            cntlr.addToLog("Exception: {error}, Excel row: {excelRow}"
                           .format(error=err,
                                   excelRow=iRow),
                            messageCode="importExcel:exception")
            
    if isUSGAAP and hasDefLB:
        # move line items above table
        def fixUsggapTableDims(lvl1Struct):
            foundLineItems = False
            for i1, lvl1Entry in enumerate(lvl1Struct):
                for i2, lvl2Entry in enumerate(lvl1Entry.childStruct):
                    for i3, lvl3Entry in enumerate(lvl2Entry.childStruct):
                        if lvl3Entry.name.endswith("LineItems") and lvl2Entry.name.endswith("Table"):
                            foundLineItems = True
                            break
                if foundLineItems:
                    break
                else:
                    fixUsggapTableDims(lvl1Entry.childStruct)
            if foundLineItems:
                lvl1Struct.insert(i1 + 1, LBentry(prefix=lvl3Entry.prefix, name=lvl3Entry.name, arcrole=lvl1Entry.arcrole, childStruct=lvl3Entry.childStruct))  # must keep lvl1Rel if it is __root__
                lvl3Entry.childStruct.insert(0, lvl2Entry)
                if lvl1Entry.name.endswith("Abstract"):
                    del lvl1Struct[i1]
                if i3 < len(lvl2Entry.childStruct):
                    del lvl2Entry.childStruct[i3]
                pass
                
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
        xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
        xmlns:{extensionPrefix}="{targetNamespace}"
        {importXmlns} 
        xmlns:nonnum="http://www.xbrl.org/dtr/type/non-numeric" 
        xmlns:link="http://www.xbrl.org/2003/linkbase" 
        xmlns:xbrli="http://www.xbrl.org/2003/instance" 
        xmlns:xlink="http://www.w3.org/1999/xlink" 
        xmlns:xbrldt="http://xbrl.org/2005/xbrldt"/>
    '''.format(targetNamespace=extensionSchemaNamespaceURI,
               extensionPrefix=extensionSchemaPrefix,
               importXmlns=''.join('xmlns:{0}="{1}"\n'.format(prefix, namespaceURI)
                                   for prefix, namespaceURI in importXmlns.items())
               )
                           )
    dtsSchemaDocument = dts.modelDocument
    dtsSchemaDocument.inDTS = True  # entry document always in DTS
    dtsSchemaDocument.targetNamespace = extensionSchemaNamespaceURI # not set until schemaDiscover too late otherwise
    schemaElt = dtsSchemaDocument.xmlRootElement
    
    #foreach linkbase
    annotationElt = XmlUtil.addChild(schemaElt, XbrlConst.xsd, "annotation")
    appinfoElt = XmlUtil.addChild(annotationElt, XbrlConst.xsd, "appinfo")
    
    for iRow in range(0, importExcelSheet.nrows):
        try:
            row = importExcelSheet.row(iRow)
            if (row[0].ctype == xlrd.XL_CELL_EMPTY):  # skip if col 1 is empty
                continue
            testDir = row[0].value
            uriFrom = row[1].value
            uriTo = row[2].value
        except Exception as err:
            cntlr.addToLog("Exception: {error}, Excel row: {excelRow}"
                           .format(error=err,
                                   excelRow=iRow),
                            messageCode="loadFromExcel:exception")
            
    # add linkbaseRefs
    appinfoElt = XmlUtil.descendant(schemaElt, XbrlConst.xsd, "appinfo")
    
    # don't yet add linkbase refs, want to process imports first to get roleType definitions
        
    # add imports
    for importAttributes in sorted(imports.values()):
        XmlUtil.addChild(schemaElt, 
                         XbrlConst.xsd, "import",
                         attributes=importAttributes)
        
    # add elements
    for eltName, eltAttrs in sorted(extensionElements.items(), key=lambda item: item[0]):
        XmlUtil.addChild(schemaElt, 
                         XbrlConst.xsd, "element",
                         attributes=eltAttrs)
        
    # add role definitions (for discovery)
    for roleURI, roleDefinition in extensionRoles.items():
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
                                                ("{http://www.w3.org/1999/xlink}role",  role),
                                                ("{http://www.w3.org/1999/xlink}arcrole",  "http://www.w3.org/1999/xlink/properties/linkbase"),
                                                ))
        dtsSchemaDocument.referencesDocument[lbDoc] = ModelDocumentReference("href", lbRefElt) 
    # label linkbase
    for lang, filename in labelLinkbases:
        lbDoc = ModelDocument.create(dts, ModelDocument.Type.LINKBASE, filename, base="", initialXml="""
        <link:linkbase 
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
            xsi:schemaLocation="http://www.xbrl.org/2003/linkbase 
            http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd" 
            xmlns:link="http://www.xbrl.org/2003/linkbase" 
            xmlns:xlink="http://www.w3.org/1999/xlink" 
            xmlns:xbrli="http://www.xbrl.org/2003/instance"/>
        """)
        lbDoc.inDTS = True
        addLinkbaseRef("label", filename, lbDoc)
        lbElt = lbDoc.xmlRootElement
        linkElt = XmlUtil.addChild(lbElt, 
                                   XbrlConst.link, "labelLink",
                                   attributes=(("{http://www.w3.org/1999/xlink}type", "extended"),
                                               ("{http://www.w3.org/1999/xlink}role", "http://www.xbrl.org/2003/role/link")))
        firstLinkElt = linkElt
        locs = set()
        roleRefs = set()
        for labelKey, text in extensionLabels.items():
            prefix, name, labelLang, role = labelKey
            if lang == labelLang:
                locLabel = prefix + "_" + name
                if locLabel not in locs:
                    locs.add(locLabel)
                    XmlUtil.addChild(linkElt,
                                     XbrlConst.link, "loc",
                                     attributes=(("{http://www.w3.org/1999/xlink}type", "locator"),
                                                 ("{http://www.w3.org/1999/xlink}href", extensionHref(prefix, name)),
                                                 ("{http://www.w3.org/1999/xlink}label", locLabel)))        
                    XmlUtil.addChild(linkElt,
                                     XbrlConst.link, "labelArc",
                                     attributes=(("{http://www.w3.org/1999/xlink}type", "arc"),
                                                 ("{http://www.w3.org/1999/xlink}arcrole", "http://www.xbrl.org/2003/arcrole/concept-label"),
                                                 ("{http://www.w3.org/1999/xlink}from", locLabel), 
                                                 ("{http://www.w3.org/1999/xlink}to", "label_" + locLabel), 
                                                 ("order", 1.0)))
                XmlUtil.addChild(linkElt,
                                 XbrlConst.link, "label",
                                 attributes=(("{http://www.w3.org/1999/xlink}type", "resource"),
                                             ("{http://www.w3.org/1999/xlink}label", "label_" + locLabel),
                                             ("{http://www.w3.org/1999/xlink}role", role),
                                             ("{http://www.w3.org/XML/1998/namespace}lang", lang)),
                                 text=text)
                if role and role in dts.roleTypes:
                    roleType = dts.roleTypes[role][0]
                    roleRefs.add(("roleRef", role, roleType.modelDocument.uri + "#" + roleType.id))
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
        qn = schemaElt.prefixedNameQname(prefix + ":" + name)
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
                toLabel = toPrefix + "_" + toName
                toLabelAlt = None
                if not lbEntry.isRoot:
                    fromLabel = fromPrefix + "_" + fromName
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
                    <link:linkbase 
                        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
                        xsi:schemaLocation="http://www.xbrl.org/2003/linkbase 
                        http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd" 
                        xmlns:link="http://www.xbrl.org/2003/linkbase" 
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
                                         XbrlConst.link, roleref,
                                         attributes=(("arcroleURI" if roleref == "arcroleRef" else "roleURI", roleURI),
                                                     ("{http://www.w3.org/1999/xlink}type", "simple"),
                                                     ("{http://www.w3.org/1999/xlink}href", href)),
                                         beforeSibling=firstLinkElt)
                    lbDoc.linkbaseDiscover(lbElt)  
                    break
    
    #cntlr.addToLog("Completed in {0:.2} secs".format(time.time() - startedAt),
    #               messageCode="loadFromExcel:info")
    
    return dts

def modelManagerLoad(modelManager, fileSource):
    # check if an excel file
    try:
        filename = fileSource.url # if a string has no url attribute
    except:
        filename = fileSource # may be just a string
        
    if not (filename.endswith(".xlsx") or filename.endswith(".xls")):
        return None # not an Excel file

    cntlr = modelManager.cntlr
    dts = loadFromExcel(cntlr, filename)
    dts.loadedFromExcel = True
    return dts

def guiXbrlLoaded(cntlr, modelXbrl, attach):
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
            dtsSchemaDocument.save(saveToFile(dtsSchemaDocument.uri))
            for lbDoc in dtsSchemaDocument.referencesDocument.keys():
                if lbDoc.inDTS and lbDoc.type == ModelDocument.Type.LINKBASE:
                    lbDoc.save(saveToFile(lbDoc.uri))

def cmdLineXbrlLoaded(cntlr, options, modelXbrl):
    if options.saveExcelDTSdirectory and getattr(modelXbrl, "loadedFromExcel", False):
        from arelle import ModelDocument
        def saveToFile(url):
            if os.path.isabs(url):
                return url
            return os.path.join(options.saveExcelDTSdirectory, url)
        # save entry schema
        dtsSchemaDocument = modelXbrl.modelDocument
        dtsSchemaDocument.save(saveToFile(dtsSchemaDocument.uri))
        for lbDoc in dtsSchemaDocument.referencesDocument.keys():
            if lbDoc.inDTS and lbDoc.type == ModelDocument.Type.LINKBASE:
                lbDoc.save(saveToFile(lbDoc.uri))

def excelLoaderOptionExtender(parser):
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
        if self.arcrole == XbrlConst.summationItem:
            return self.role
        return None
    
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
