# -*- coding: utf-8 -*-

'''
loadFromExcel.py is an example of a plug-in that will load an extension taxonomy from Excel
input and optionally save an (extension) DTS.

(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
import os, io, time, re
from collections import defaultdict
from arelle import XbrlConst

headerWidths = {
        "label": 40,
        "prefix": 20,
        "name": 36,
        "type": 24,
        "abstract": 10,
        "substitutionGroup": 30,
        "periodType": 10,
        "balance": 10,
        "depth": 6,
        "preferredLabel": 16,
        "calculationParent": 20,
        "calculationWeight": 12
        }

headersStyles = (
    # ELR match string, font (size: 20 * pt size)
    (r"http://[^/]+\.edinet-fsa\.go\.jp", "font: name MS UI Gothic, height 180; ", (
        # (display string, content, label role, lang [,indented])
        ("標準ラベル（日本語）", "label", XbrlConst.standardLabel, "ja", "indented"),
        ("冗長ラベル（日本語）", "label", XbrlConst.verboseLabel, "ja"),
        ("標準ラベル（英語）", "label", XbrlConst.standardLabel, "en"),
        ("冗長ラベル（英語）", "label", XbrlConst.verboseLabel, "en"),
        ("名前空間プレフィックス", "prefix"),
        ("要素名", "name"),
        ("type", "type"),
        ("substitutionGroup", "substitutionGroup"),
        ("periodType", "periodType"),
        ("balance", "balance"),
        ("abstract", "abstract"),
        ("depth", "depth"),
        ("preferred label", "preferredLabel"),
        ("calculation parent", "calculationParent"), # qname
        ("calculation weight", "calculationWeight")
        )),
    (r"http://[^/]+/us-gaap/", "font: name Calibri, height 180; ", (
        ("label", "label", XbrlConst.standardLabel, "en-US", "indented"),
        ("label, terse", "label", XbrlConst.terseLabel, "en-US"),
        ("prefix", "prefix"),
        ("name", "name"),
        ("type", "type"),
        ("substitutionGroup", "substitutionGroup"),
        ("periodType", "periodType"),
        ("balance", "balance"),
        ("abstract", "abstract"),
        ("depth", "depth"),
        ("preferred label", "preferredLabel"),
        ("calculation parent", "calculationParent"), # qname
        ("calculation weight", "calculationWeight"),
        )),
    # generic pattern taxonomy
    (r"http://[^/]+/us-gaap/", "font: name Calibri, height 180; ", (
        ("label", "label", XbrlConst.standardLabel, "en", "indented"),
        ("prefix", "prefix"),
        ("name", "name"),
        ("type", "type"),
        ("substitutionGroup", "substitutionGroup"),
        ("periodType", "periodType"),
        ("balance", "balance"),
        ("abstract", "abstract"),
        ("depth", "depth"),
        ("preferred label", "preferredLabel"),
        ("calculation parent", "calculationParent"), # qname
        ("calculation weight", "calculationWeight"),
        )),
    )

sheet2Headers = (
    ("specification", 14),
    ("file type", 12),
    ("prefix (schema)\ntype (linkbase)\nargument (other)", 20),
    ("file, href or role definition", 60),
    ("namespace URI", 60),
    )

def saveLoadableExcel(dts, excelFile):
    from arelle import ModelDocument, XmlUtil, xlwt
    
    workbook = xlwt.Workbook(encoding="utf-8")
    sheet1 = workbook.add_sheet("Sheet1")
    sheet2 = workbook.add_sheet("Sheet2")
    
    # identify type of taxonomy
    sheet1Headers = None
    cellFont = None
    for doc in dts.urlDocs.values():
        if doc.type == ModelDocument.Type.SCHEMA and doc.inDTS:
            for i in range(len(headersStyles)):
                if re.match(headersStyles[i][0], doc.targetNamespace):
                    cellFont = headersStyles[i][1]
                    sheet1Headers = headersStyles[i][2]
                    break
    if sheet1Headers is None:
        dts.info("error:saveLoadableExcel",
         _("Referenced taxonomy style not identified, assuming general pattern."),
         modelObject=dts)
        cellFont = headersStyles[-1][1]
        sheet1Headers = headersStyles[-1][2]
        
    hdrCellFmt = xlwt.easyxf(cellFont + 
                             "align: wrap on, vert center, horiz center; " 
                             "pattern: pattern solid_fill, fore_color light_orange; " 
                             "border: top thin, right thin, bottom thin, left thin; ")
    
    # sheet 1 col widths
    for i, hdr in enumerate(sheet1Headers):
        sheet1.col(i).width = 256 * headerWidths.get(hdr[1], 40)
        
    # sheet 2 headers
    for i, hdr in enumerate(sheet2Headers):
        sheet2.col(i).width = 256 * hdr[1]
        sheet2.write(0, i, hdr[0], hdrCellFmt) 
        
    # referenced taxonomies
    sheet1row = 0
    sheet2row = 2
    
    cellFmt = xlwt.easyxf(cellFont + 
                          "border: top thin, right thin, bottom thin, left thin; "
                          "align: wrap on, vert top, horiz left;")
    cellFmtIndented = dict((i, xlwt.easyxf(cellFont + 
                                           "border: top thin, right thin, bottom thin, left thin; "
                                           "align: wrap on, vert top, horiz left, indent {0};"
                                           .format(i)))
                           for i in range(16))

    # identify extension schema
    extensionSchemaDoc = None
    if dts.modelDocument.type == ModelDocument.Type.SCHEMA:
        extensionSchemaDoc = dts.modelDocument
    elif dts.modelDocument.type == ModelDocument.Type.INSTANCE:
        for doc, docReference in dts.modelDocument.referencesDocument.items():
            if docReference.referenceType == "href":
                extensionSchemaDoc = doc
                break
    if extensionSchemaDoc is None:
        dts.info("error:saveLoadableExcel",
         _("Unable to identify extension taxonomy."),
         modelObject=dts)
        return
            
    for doc, docReference in extensionSchemaDoc.referencesDocument.items():
        if docReference.referenceType == "import" and doc.targetNamespace != XbrlConst.xbrli:
            sheet2.write(sheet2row, 0, "import", cellFmt) 
            sheet2.write(sheet2row, 1, "schema", cellFmt) 
            sheet2.write(sheet2row, 2, XmlUtil.xmlnsprefix(doc.xmlRootElement, doc.targetNamespace), cellFmt) 
            sheet2.write(sheet2row, 3, doc.uri, cellFmt) 
            sheet2.write(sheet2row, 4, doc.targetNamespace, cellFmt) 
            sheet2row += 1
                
    sheet2row += 1
    
    doc = extensionSchemaDoc
    sheet2.write(sheet2row, 0, "extension", cellFmt) 
    sheet2.write(sheet2row, 1, "schema", cellFmt) 
    sheet2.write(sheet2row, 2, XmlUtil.xmlnsprefix(doc.xmlRootElement, doc.targetNamespace), cellFmt) 
    sheet2.write(sheet2row, 3, os.path.basename(doc.uri), cellFmt) 
    sheet2.write(sheet2row, 4, doc.targetNamespace, cellFmt) 
    sheet2row += 1

    for doc, docReference in extensionSchemaDoc.referencesDocument.items():
        if docReference.referenceType == "href" and doc.type == ModelDocument.Type.LINKBASE:
            linkbaseType = ""
            role = docReference.referringModelObject.get("{http://www.w3.org/1999/xlink}role") or ""
            if role.startswith("http://www.xbrl.org/2003/role/") and role.endswith("LinkbaseRef"):
                linkbaseType = os.path.basename(role)[0:-11]
            sheet2.write(sheet2row, 0, "extension", cellFmt) 
            sheet2.write(sheet2row, 1, "linkbase", cellFmt) 
            sheet2.write(sheet2row, 2, linkbaseType, cellFmt) 
            sheet2.write(sheet2row, 3, os.path.basename(doc.uri), cellFmt) 
            sheet2.write(sheet2row, 4, "", cellFmt) 
            sheet2row += 1
            
    sheet2row += 1

    # extended link roles defined in this document
    for roleURI, roleTypes in sorted(dts.roleTypes.items(), 
                                     # sort on definition if any else URI
                                     key=lambda item: (item[1][0].definition or item[0])):
        for roleType in roleTypes:
            if roleType.modelDocument == extensionSchemaDoc:
                sheet2.write(sheet2row, 0, "extension", cellFmt) 
                sheet2.write(sheet2row, 1, "role", cellFmt) 
                sheet2.write(sheet2row, 2, "", cellFmt) 
                sheet2.write(sheet2row, 3, roleType.definition, cellFmt) 
                sheet2.write(sheet2row, 4, roleURI, cellFmt) 
                sheet2row += 1
                
    # tree walk recursive function
    def treeWalk(row, depth, concept, preferredLabel, arcrole, preRelSet, visited):
        if concept is not None:
            # calc parents
            calcRelSet = dts.relationshipSet(XbrlConst.summationItem, preRelSet.linkrole)
            calcRel = None
            for modelRel in calcRelSet.toModelObject(concept):
                calcRel = modelRel
                break
            for i, hdr in enumerate(sheet1Headers):
                colType = hdr[1]
                value = ""
                if colType == "name":
                    value = str(concept.name)
                elif colType == "prefix" and concept.qname is not None:
                    value = concept.qname.prefix
                elif colType == "type" and concept.type is not None:
                    value = str(concept.type.qname)
                elif colType == "substitutionGroup":
                    value = str(concept.substitutionGroupQname)
                elif colType == "abstract":
                    value = "true" if concept.isAbstract else "false"
                elif colType == "periodType":
                    value = concept.periodType
                elif colType == "balance":
                    value = concept.balance
                elif colType == "label":
                    role = hdr[2]
                    lang = hdr[3]
                    value = concept.label(preferredLabel if role == XbrlConst.standardLabel else role,
                                          linkroleHint=preRelSet.linkrole,
                                          lang=lang)
                elif colType == "preferredLabel" and preferredLabel:
                    if preferredLabel.startswith("http://www.xbrl.org/2003/role/"):
                        value = os.path.basename(preferredLabel)
                    else:
                        value = preferredLabel
                elif colType == "calculationParent" and calcRel is not None:
                    calcParent = calcRel.fromModelObject
                    if calcParent is not None:
                        value = str(calcParent.qname)
                elif colType == "calculationWeight" and calcRel is not None:
                    value = calcRel.weight
                elif colType == "depth":
                    value = depth
                if "indented" in hdr:
                    style = cellFmtIndented[min(depth, len(cellFmtIndented) - 1)]
                else:
                    style = cellFmt
                sheet1.write(row, i, value, style) 
            row += 1
            if concept not in visited:
                visited.add(concept)
                for modelRel in preRelSet.fromModelObject(concept):
                    if modelRel.toModelObject is not None:
                        row = treeWalk(row, depth + 1, modelRel.toModelObject, modelRel.preferredLabel, arcrole, preRelSet, visited)
                visited.remove(concept)
        return row
    
    # use presentation relationships for Sheet1
    arcrole = XbrlConst.parentChild
    # sort URIs by definition
    linkroleUris = []
    relationshipSet = dts.relationshipSet(arcrole)
    if relationshipSet:
        for linkroleUri in relationshipSet.linkRoleUris:
            modelRoleTypes = dts.roleTypes.get(linkroleUri)
            if modelRoleTypes:
                roledefinition = (modelRoleTypes[0].genLabel(strip=True) or modelRoleTypes[0].definition or linkroleUri)                    
            else:
                roledefinition = linkroleUri
            linkroleUris.append((roledefinition, linkroleUri))
        linkroleUris.sort()
    
        # for each URI in definition order
        for roledefinition, linkroleUri in linkroleUris:
            # write linkrole
            sheet1.write(sheet1row, 0, 
                         (roledefinition or linkroleUri), 
                         xlwt.easyxf(cellFont))  # ELR has no boarders, just font specified
            sheet1row += 1
            # write header row
            for i, hdr in enumerate(sheet1Headers):
                sheet1.write(sheet1row, i, hdr[0], hdrCellFmt)
            sheet1row += 1
            # elr relationships for tree walk
            linkRelationshipSet = dts.relationshipSet(arcrole, linkroleUri)
            for rootConcept in linkRelationshipSet.rootConcepts:
                sheet1row = treeWalk(sheet1row, 0, rootConcept, None, arcrole, linkRelationshipSet, set())
            sheet1row += 1 # double space rows between tables
    else:
        # write header row
        for i, hdr in enumerate(sheet1Headers):
            sheet1.write(sheet1row, i, hdr[0], hdrCellFmt)
        sheet1row += 1
        # get lang
        lang = None
        for i, hdr in enumerate(sheet1Headers):
            colType = hdr[1]
            if colType == "label":
                lang = hdr[3]
                if colType == "label":
                   role = hdr[2]
                   lang = hdr[3]
        lbls = defaultdict(list)        
        for concept in set(dts.qnameConcepts.values()): # may be twice if unqualified, with and without namespace
            lbls[concept.label(role,lang=lang)].append(concept.objectId())
        srtLbls = sorted(lbls.keys())
        excludedNamespaces = XbrlConst.ixbrlAll.union(
            (XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl,
             XbrlConst.xbrldt,
             XbrlConst.xhtml))
        for label in srtLbls:
            for objectId in lbls[label]:
                concept = dts.modelObject(objectId)
                if concept.modelDocument.targetNamespace not in excludedNamespaces:
                    for i, hdr in enumerate(sheet1Headers):
                        colType = hdr[1]
                        value = ""
                        if colType == "name":
                            value = str(concept.qname.localName)
                        elif colType == "prefix":
                            value = concept.qname.prefix
                        elif colType == "type":
                            value = str(concept.type.qname)
                        elif colType == "substitutionGroup":
                            value = str(concept.substitutionGroupQname)
                        elif colType == "abstract":
                            value = "true" if concept.isAbstract else "false"
                        elif colType == "periodType":
                            value = concept.periodType
                        elif colType == "balance":
                            value = concept.balance
                        elif colType == "label":
                            role = hdr[2]
                            lang = hdr[3]
                            value = concept.label(role, lang=lang)
                        elif colType == "depth":
                            value = 0
                        if "indented" in hdr:
                            style = cellFmtIndented[min(0, len(cellFmtIndented) - 1)]
                        else:
                            style = cellFmt
                        sheet1.write(sheet1row, i, value, style) 
                    sheet1row += 1
    
    try: 
        workbook.save(excelFile)
        dts.info("info:saveLoadableExcel",
            _("Saved Excel file: %(excelFile)s"), 
            excelFile=os.path.basename(excelFile),
            modelXbrl=dts)
    except Exception as ex:
        dts.error("exception:saveLoadableExcel",
            _("File saving exception: %(error)s"), error=ex,
            modelXbrl=dts)

def saveLoadableExcelMenuEntender(cntlr, menu):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save Loadable Excel", 
                     underline=0, 
                     command=lambda: saveLoadableExcelMenuCommand(cntlr) )

def saveLoadableExcelMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No taxonomy loaded.")
        return
        # get file name into which to save log file while in foreground thread
    excelFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save Loadable Excel file"),
            initialdir=cntlr.config.setdefault("loadableExcelFileDir","."),
            filetypes=[(_("Excel file .xls"), "*.xls")],
            defaultextension=".xls")
    if not excelFile:
        return False
    import os
    cntlr.config["loadableExcelFileDir"] = os.path.dirname(excelFile)
    cntlr.saveConfig()

    import threading
    thread = threading.Thread(target=lambda 
                                  _dts=cntlr.modelManager.modelXbrl,
                                  _excelFile=excelFile: 
                                        saveLoadableExcel(_dts, _excelFile))
    thread.daemon = True
    thread.start()
    
def saveLoadableExcelCommandLineOptionExtender(parser):
    # extend command line options with a save DTS option
    parser.add_option("--save-loadable-excel", 
                      action="store_true", 
                      dest="saveLoadableExcel", 
                      help=_("Save Loadable Excel file"))

def saveLoadableExcelCommandLineXbrlRun(cntlr, options, modelXbrl):
    # extend XBRL-loaded run processing for this option
    excelFile = getattr(options, "saveLoadableExcel", None)
    if excelFile:
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        saveLoadableExcel(cntlr.modelManager.modelXbrl, excelFile)

__pluginInfo__ = {
    'name': 'Save Loadable Excel',
    'version': '0.9',
    'description': "This plug-in saves XBRL in Excel that can be loaded as an extension DTS.",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2013 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveLoadableExcelMenuEntender,
    'CntlrCmdLine.Options': saveLoadableExcelCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': saveLoadableExcelCommandLineXbrlRun,
}
