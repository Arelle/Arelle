# -*- coding: utf-8 -*-
'''
saveOIMTaxonomy.py is a plug-in that saves an extension taxonomy in the json OIM taxonomy format

See COPYRIGHT.md for copyright information.
'''
import os, io, json
import regex as re
from lxml import etree
from arelle.ModelValue import qname
from arelle.Version import authorLabel, copyrightLabel
from arelle import XbrlConst
from collections import OrderedDict
from arelle.FunctionFn import lang

jsonDocumentType = "https://xbrl.org/2026/model"
jsonTxmyVersion = "1.0"
primaryLang = "en"

qnXbrl = qname("{https://xbrl.org/2025}xbrl:xbrl")

excludeImportNamespaces = {XbrlConst.xbrli, XbrlConst.xbrldt}

def saveOIMTaxonomy(dts, jsonFile):
    from arelle import ModelDocument, XmlUtil

    # identify extension schema
    namespacePrefixes = dict((ns, prefix) for prefix, ns in dts.prefixedNamespaces.items())
    namespacesInUse = set()
    extensionSchemaDoc = None
    if dts.modelDocument.type == ModelDocument.Type.SCHEMA:
        extensionSchemaDoc = dts.modelDocument
    elif dts.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET, ModelDocument.Type.LINKBASE):
        for doc, docReference in dts.modelDocument.referencesDocument.items():
            if ("href" in docReference.referenceTypes and doc.targetNamespace in namespacePrefixes and
                os.path.isabs(dts.modelDocument.uri) == os.path.isabs(doc.uri) and os.path.commonpath((dts.modelDocument.uri, doc.uri))):
                extensionSchemaDoc = doc
                break
    if extensionSchemaDoc:
        extensionPrefix = namespacePrefixes[extensionSchemaDoc.targetNamespace]
        namespacesInUse.add(extensionSchemaDoc.targetNamespace)
    if extensionSchemaDoc is None:
        dts.info("error:saveLoadableOIMTaxonomy",
         _("Unable to identify extension taxonomy."),
         modelObject=dts)
        return

    oimTxmy = OrderedDict()
    oimTxmy["documentInfo"] = docInfo = OrderedDict()
    docInfo["documentType"] = jsonDocumentType
    docInfo["namespaces"] = namespaces = OrderedDict()
    oimTxmy["xbrlModel"] = xbrlMdl = OrderedDict()

    # provide consistent order to taxonomy properties and objects
    xbrlMdl["name"] = f"{extensionPrefix}:{os.path.splitext(extensionSchemaDoc.basename)[0]}"
    xbrlMdl["namespace"] = extensionSchemaDoc.targetNamespace
    xbrlMdl["version"] = jsonTxmyVersion
    xbrlMdl["modelForm"] = "compiled" # all namespaces crammed together
    xbrlMdl["importedTaxonomies"] = imports = []
    xbrlMdl["abstracts"] = abstracts = []
    xbrlMdl["concepts"] = concepts = []
    xbrlMdl["cubes"] = cubes = []
    xbrlMdl["domains"] = domains = []
    xbrlMdl["domainClasses"] = domainClasses = []
    xbrlMdl["networks"] = networks = []
    xbrlMdl["labels"] = labels = []
    xbrlMdl["labelTypes"] = labelTypes = []
    sharedLabelRefs = {}
    xbrlMdl["references"] = references = []

    # taxonomy object
    extensionLinkbaseDocs = {doc
                             for doc, docReference in extensionSchemaDoc.referencesDocument.items()
                             if "href" in docReference.referenceTypes and docReference.referringModelObject.elementQname == XbrlConst.qnLinkLinkbaseRef}
    extensionLinkbaseDocs.add(extensionSchemaDoc)

    if any(c.balance for c in dts.qnameConcepts.values()):
        imports.append({
            "xbrlModelName": "xbrla:AccountingModel"})

    labelsRelationshipSet = dts.relationshipSet(XbrlConst.conceptLabel)

    # extended link roles defined in this document
    networkOrder = 0
    for roleURI, roleTypes in sorted(dts.roleTypes.items(),
            # sort on definition if any else URI
            key=lambda item: (item[1][0].definition if len(item[1]) and item[1][0].definition else item[0])):
        for roleType in roleTypes:
            if roleType.modelDocument == extensionSchemaDoc:
                name = f"{extensionPrefix}:_{os.path.basename(roleURI)}_"
                definition = roleType.definition
                ntwk = OrderedDict((
                    ("name", name),))
                networks.append( ntwk )
                networkOrder += 1
                if definition:
                    labels.append( OrderedDict((
                        ("relatedId", [name]),
                        ("language", primaryLang),
                        ("labelType", XbrlConst.standardLabel),
                        ("value", definition))))

    # cubes by linkrole
    domMemConcepts = set()
    for arcrole, linkrole, arcQN, linkQN in dts.baseSets.keys():
        if arcrole == XbrlConst.all and linkrole is not None and arcQN is None and linkQN is None:
            for rel in dts.relationshipSet(XbrlConst.all, linkrole).modelRelationships:
                if rel.modelDocument not in extensionLinkbaseDocs:
                    continue
                hc = rel.toModelObject
                priItem = rel.fromModelObject
                namespacesInUse.add(hc.qname.namespaceURI)
                namespacesInUse.add(priItem.qname.namespaceURI)
                if hc is not None and priItem is not None:
                    cubeDims = []
                    cubeDim = OrderedDict((("dimensionName", "xbrl:concept"),
                                           ("domainName", str(priItem.qname))))
                    cubeDims.append(cubeDim)
                    namespacesInUse.add(qnXbrl.namespaceURI)
                    namespacePrefixes[qnXbrl.namespaceURI] = qnXbrl.prefix
                    # priItem domains
                    rels = []
                    domName = f"{priItem.qname.prefix}:{priItem.qname.localName}_Domain"
                    domClsName = f"{priItem.qname.prefix}:{priItem.qname.localName}_DomainClass"
                    domains.append( OrderedDict((
                        ("name", domName),
                        ("root", domClsName),
                        ("relationships", rels)) ) )
                    for domRel in dts.relationshipSet(XbrlConst.domainMember, rel.consecutiveLinkrole).fromModelObject(priItem):
                        domObj = domRel.toModelObject
                        if domObj is not None:
                            rels.append( OrderedDict((
                                ("source", str(priItem.qname)),
                                ("target", str(domObj.qname)),
                                ("order", int(domRel.order)))) )
                    domainClasses.append( OrderedDict((
                        ("name", domClsName),) ) )
                    # dimension domains
                    for dimRel in dts.relationshipSet(XbrlConst.hypercubeDimension, rel.consecutiveLinkrole).fromModelObject(hc):
                        dimObj = dimRel.toModelObject
                        if dimObj is not None:
                            namespacesInUse.add(dimObj.qname.namespaceURI)
                            domName = f"{dimObj.qname.prefix}:{dimObj.qname.localName}_Domain"
                            domClsName = f"{dimObj.qname.prefix}:{dimObj.qname.localName}_DomainClass"
                            cubeDim = OrderedDict((
                                ("dimensionName", str(dimObj.qname)),
                                ("domainName", domName)))
                            cubeDims.append(cubeDim)
                            domRels = []
                            domains.append( OrderedDict((
                                ("name", domName),
                                ("root", domClsName),
                                ("relationships", domRels))) )
                            domainClasses.append( OrderedDict((
                                ("name", domClsName),) ) )
                            for domRel in dts.relationshipSet(XbrlConst.dimensionDomain, dimRel.consecutiveLinkrole).fromModelObject(dimObj):
                                domObj = domRel.toModelObject
                                if domObj is not None:
                                    if dts.qnameDimensionDefaults.get(dimObj.qname) == domObj.qname:
                                        cubeDim["allowDomainFacts"] = True
                                    namespacesInUse.add(domObj.qname.namespaceURI)
                                    domRels.append( OrderedDict((
                                        ("source", str(dimObj.qname)),
                                        ("target", str(domObj.qname)),
                                        ("order", int(domRel.order)))) )
                                    domMemConcepts.add(domObj)
                                    for memRel in dts.relationshipSet(XbrlConst.domainMember, domRel.consecutiveLinkrole).fromModelObject(dimObj):
                                        memObj = memRel.toModelObject
                                        if memObj is not None:
                                            namespacesInUse.add(memObj.qname.namespaceURI)
                                            domRels.append( OrderedDict((
                                                ("source", str(memRel.fromModelObject.qname)) if memRel.fromModelObject is not None else (),
                                                ("target", str(memObj.qname)),
                                                ("order", memRel.order))) )
                                            domMemConcepts.add(memObj)
                cubes.append( OrderedDict((
                    ("name", str(hc.qname)),
                    ("networkURI", rel.linkrole),
                    ("cubeDimensions", cubeDims))) )

    # domains

    # tree walk recursive function
    def treeWalk(depth, concept, arcrole, relSet, ntwk, visited):
        if concept is not None:
            if concept not in visited:
                visited.add(concept)
                for rel in relSet.fromModelObject(concept):
                    toConcept = rel.toModelObject
                    if toConcept is not None:
                        namespacesInUse.add(concept.qname.namespaceURI)
                        namespacesInUse.add(toConcept.qname.namespaceURI)
                        if True: # rel.modelDocument in extensionLinkbaseDocs:
                            ntwk["relationships"].append( OrderedDict((
                                ("source", str(concept.qname)),
                                ("target", str(toConcept.qname)),
                                ("order", rel.order),
                                ) ))
                            if arcrole in XbrlConst.summationItems:
                                ntwk["properties"] = [{"weight":rel.weight}]
                        treeWalk(depth + 1, toConcept, arcrole, relSet, ntwk, visited)
                visited.remove(concept)

    # use presentation relationships for conceptsWs
    for arcrole in (XbrlConst.parentChild,XbrlConst.domainMember) + XbrlConst.summationItems:
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
                # elr relationships for tree walk
                linkRelationshipSet = dts.relationshipSet(arcrole, linkroleUri)
                ntwk = OrderedDict((
                    ("name", f"{extensionPrefix}:_{os.path.basename(linkroleUri)}_"),
                    ("relationshipTypeName", "xbrl:parent-child" if arcrole == XbrlConst.parentChild else "xbrl:summation-item"),
                    ("roots", []),
                    ("relationships", [])))
                networks.append(ntwk)
                for rootConcept in linkRelationshipSet.rootConcepts:
                    ntwk["roots"].append(str(rootConcept.qname))
                    treeWalk(0, rootConcept, arcrole, linkRelationshipSet, ntwk, set())

    for concept in sorted(set(dts.qnameConcepts.values()), key=lambda c:c.name): # may be twice if unqualified, with and without namespace
        if concept.modelDocument == extensionSchemaDoc:
            c = OrderedDict()
            c["name"] = str(concept.qname)
            if concept.isHypercubeItem or concept.isDimensionItem or concept in domMemConcepts or concept.isTuple or not concept.isItem:
                continue # not recorded as concepts
            if concept.isAbstract:
                abstracts.append(c)
            else:
                concepts.append(c)
                if concept.typeQname: # may be absent
                    c["dataType"] = str(concept.typeQname)
                    namespacesInUse.add(concept.typeQname.namespaceURI)
                if concept.periodType:
                    c["periodType"] = concept.periodType
                if concept.balance:
                    c["properties"] = []
                    c["properties"].append({
                        "property": "xbrla:balance",
                        "value": concept.balance})
                c["nillable"] = concept.isNillable
        conceptLabels = dict(((lbl.role, lbl.xmlLang), lbl)
                             for rel in labelsRelationshipSet.fromModelObject(concept)
                             for lbl in (rel.toModelObject,)
                             if lbl is not None)
        for _key, label in sorted(conceptLabels.items(), key=lambda i:i[0]):
            labelDupKey = (label.xmlLang, label.role, label.textValue)
            if labelDupKey in sharedLabelRefs and False: # no more shared labels
                sharedLabelRefs[labelDupKey]["relatedName"].append(str(concept.qname))
            else:
                l = OrderedDict((
                    ("relatedName", str(concept.qname)),
                    ("language", label.xmlLang),
                    ("labelType", os.path.basename(label.role)),
                    ("value", label.textValue)))
                labels.append(l)
                sharedLabelRefs[labelDupKey] = l
        # TBD add references here

    # table linkbase
    if dts.hasTableRendering:
        # generate layout model
        tableLabelCustomRoles = set()
        from arelle.ViewFileRenderedLayout import ViewRenderedLayout
        from arelle.rendering.RenderingLayout import layoutTable
        from lxml import etree
        view = ViewRenderedLayout(dts, "nofile.xml", "en", None)
        layoutTable(view)
        view.view(view.lytMdlTblMdl)
        dataTables = []
        oimTxmy["layout"] = OrderedDict((
            ("name", xbrlMdl["name"] + "_layout"),
            ("xbrlModelName", xbrlMdl["name"]),
            ("dataTables", dataTables)))
        # xml layout etree is in view.tblElt
        def lblObj(text=None,span=1, rollup=False, role=None, lang=None):
            lbl = OrderedDict()
            if rollup:
                lbl["rollup"] = True
            else:
                if lang: 
                    lbl["language"] = lang
                lbl["value"] = text
                if role: 
                    lbl["labelType"] = f"{'xbrl' if role == 'label' else extensionPrefix}:{role}"
                    if role != "label" and role not in tableLabelCustomRoles:
                        tableLabelCustomRoles.add(role)
                        labelTypes.append({"name": f"{extensionPrefix}:{role}","dataType": "xs:string"})
            if span >= 2:
                lbl["span"] = span
            return lbl
        for tblSet in view.tblElt.iterchildren():
            tblName = None
            for tblSetCmnt in tblSet.iterchildren(etree.Comment):
                if tblSetCmnt.text.startswith("TableSet linkrole: "):
                    tblName = f"{extensionPrefix}:{tblSetCmnt.text.rpartition('/')[2]}"
                    # if there's only one cube use its name
            if tblName is None:
                dts.info("info:saveOIMTaxonomy",
                    _("Unable to identify Table Linkbase table role"),
                    modelXbrl=dts)
                continue
            dataTable = OrderedDict((
                ("name", tblName),
                ("xAxis", OrderedDict(((("axisLabels",[]),)))),
                ("yAxis", OrderedDict(((("axisLabels",[]),)))),
                ("zAxis", OrderedDict()),
                ))
            if len(cubes) == 1:
                cubeName = cubes[0]["name"]
                dataTable["cubeName"] = cubeName
            oimTxmy["layout"]["dataTables"].append(dataTable)
            for tblElt in tblSet.iterchildren("{http://xbrl.org/2014/table/model}table"):
                for hdrsElt in tblElt.iterchildren("{http://xbrl.org/2014/table/model}headers"):
                    axis = dataTable.get(hdrsElt.get("axis","") + "Axis")
                    if axis is None:
                        continue
                    if "axisLabels" not in axis:
                        axis["axisLabels"] = [] # z axis entry id only provided when there is a z axis
                    axisLbls = axis["axisLabels"]
                    for grpElt in hdrsElt.iterchildren("{http://xbrl.org/2014/table/model}group"):
                        rollupSpan = None
                        for hdrElt in grpElt.iterchildren("{http://xbrl.org/2014/table/model}header"):
                            firstLbl = len(axisLbls)
                            factDimCol = 0
                            rollupCol = None
                            labelsCnt = None
                            for cellElt in hdrElt.iterchildren("{http://xbrl.org/2014/table/model}cell"):
                                rollup = cellElt.get("rollup", "false") == "true"
                                span = int(cellElt.get("span", 1))
                                if rollup:
                                    if labelsCnt:
                                        for i in range(labelsCnt):
                                            while firstLbl + i + 1 > len(axisLbls):
                                                axisLbls.append([])
                                            axisLbls[firstLbl + i].append(lblObj(rollup=True,span=span))
                                    else:
                                        rollupSpan = span
                                    factDimCol += span
                                    continue
                                labelsCnt = 0
                                for i, lblElt in enumerate(cellElt.iterchildren("{http://xbrl.org/2014/table/model}label")):
                                    while firstLbl + i + 1 > len(axisLbls):
                                        axisLbls.append([])
                                    labelsCnt += 1
                                if rollupSpan:
                                    for i in range(labelsCnt):
                                        while firstLbl + i + 1 > len(axisLbls):
                                            axisLbls.append([])
                                        axisLbls[firstLbl + i].append(lblObj(rollup=True,span=rollupSpan))
                                    rollupSpan = None
                                for i, lblElt in enumerate(cellElt.iterchildren("{http://xbrl.org/2014/table/model}label")):
                                    commentElt = lblElt.getprevious()
                                    if isinstance(commentElt, etree._Comment):
                                        lblRoleLang = re.match("Label role: ([^,]+), lang: (.*)$", commentElt.text)
                                        role = lang = None
                                        if lblRoleLang:
                                            role, lang = lblRoleLang.groups()
                                    axisLbls[firstLbl + i].append(lblObj(text=lblElt.text, span=span, role=role, lang=lang))
                                for s in range(span):
                                    axisFactDims = axis.setdefault("factDimensions", [])
                                    if factDimCol + 1 > len(axisFactDims):
                                        axisFactDims.append(OrderedDict())
                                    factDims = axisFactDims[factDimCol]
                                    for i, constrtElt in enumerate(cellElt.iterchildren("{http://xbrl.org/2014/table/model}constraint")):
                                        aspect = constrtElt.findtext("{http://xbrl.org/2014/table/model}aspect")
                                        if aspect == "period":
                                            inst = start = end = None
                                            for e in constrtElt.iter("{http://www.xbrl.org/2003/instance}*"):
                                                if e.tag.endswith("instant"): inst = e.text
                                                elif e.tag.endswith("startDate"): start = e.text
                                                elif e.tag.endswith("endDate"): end = e.text
                                            if inst:
                                                value = f"{inst}/{inst}"
                                            elif start and end:
                                                value = f"{start}/{end}"
                                            else:
                                                value = None
                                        else:
                                            value = constrtElt.findtext("{http://xbrl.org/2014/table/model}value")
                                        if aspect and value:
                                            if aspect == "concept": aspect = "xbrl:concept"
                                            elif aspect == "period": aspect = "xbrl:period"
                                            factDims[aspect] = value
                                    factDimCol += 1

    for ns in sorted(namespacesInUse, key=lambda ns: namespacePrefixes[ns]):
        namespaces[namespacePrefixes[ns]] = ns

    try:
        with open(jsonFile, "w") as fh:
            fh.write(json.dumps(oimTxmy, indent=3))

        dts.info("info:saveOIMTaxonomy",
            _("Saved OIM Taxonomy file: %(excelFile)s"),
            excelFile=os.path.basename(jsonFile),
            modelXbrl=dts)
    except Exception as ex:
        dts.error("exception:saveOIMTaxonomy",
            _("File saving exception: %(error)s"), error=ex,
            modelXbrl=dts)

def saveOIMTaxonomyMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save OIM Taxonomy",
                     underline=0,
                     command=lambda: saveOIMTaxonomyMenuCommand(cntlr) )

def saveOIMTaxonomyMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No taxonomy loaded.")
        return
        # get file name into which to save log file while in foreground thread
    jsonFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save OIM Taxonomy file"),
            initialdir=cntlr.config.setdefault("OIMTaxonomyFileDir","."),
            filetypes=[(_("OIM Taxonomy .json"), "*.json")],
            defaultextension=".json")
    if not jsonFile:
        return False
    import os
    cntlr.config["OIMTaxonomyFileDir"] = os.path.dirname(jsonFile)
    cntlr.saveConfig()

    import threading
    thread = threading.Thread(target=lambda
                                  _dts=cntlr.modelManager.modelXbrl,
                                  _jsonFile=jsonFile:
                                        saveOIMTaxonomy(_dts, _jsonFile))
    thread.daemon = True
    thread.start()

def saveOIMTaxonomyCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options with a save DTS option
    parser.add_option("--save-OIM-taxonomy",
                      dest="saveOIMTaxonomy",
                      help=_("Save OIM Taxonomy file"))

def saveOIMTaxonomyCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    jsonFile = getattr(options, "saveOIMTaxonomy", None)
    if jsonFile:
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        saveOIMTaxonomy(cntlr.modelManager.modelXbrl, jsonFile)

__pluginInfo__ = {
    'name': 'Save OIM Taxonomy',
    'version': '0.9',
    'description': "This plug-in saves an OIM Taxonomy.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveOIMTaxonomyMenuEntender,
    'CntlrCmdLine.Options': saveOIMTaxonomyCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': saveOIMTaxonomyCommandLineXbrlRun,
}
