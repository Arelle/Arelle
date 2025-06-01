# -*- coding: utf-8 -*-
'''
saveOIMTaxonomy.py is a plug-in that saves an extension taxonomy in the json OIM taxonomy format

See COPYRIGHT.md for copyright information.
'''
import os, io, json
from arelle.Version import authorLabel, copyrightLabel
from arelle import XbrlConst
from collections import OrderedDict

jsonDocumentType = "https://xbrl.org/PWD/2023-05-17/cti"
jsonTxmyVersion = "1.0"
primaryLang = "en"

excludeImportNamespaces = {XbrlConst.xbrli, XbrlConst.xbrldt}

def saveOIMTaxonomy(dts, jsonFile):
    from arelle import ModelDocument, XmlUtil

    # identify extension schema
    namespacePrefixes = dict((ns, prefix) for prefix, ns in dts.prefixedNamespaces.items())
    namespacesInUse = set()
    extensionSchemaDoc = None
    if dts.modelDocument.type == ModelDocument.Type.SCHEMA:
        extensionSchemaDoc = dts.modelDocument
    elif dts.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET):
        for doc, docReference in dts.modelDocument.referencesDocument.items():
            if "href" in docReference.referenceTypes:
                extensionSchemaDoc = doc
                extensionPrefix = namespacePrefixes[extensionSchemaDoc.targetNamespace]
                namespacesInUse.add(extensionSchemaDoc.targetNamespace)
                break
    if extensionSchemaDoc is None:
        dts.info("error:saveLoadableOIMTaxonomy",
         _("Unable to identify extension taxonomy."),
         modelObject=dts)
        return

    oimTxmy = OrderedDict()
    oimTxmy["documentInfo"] = docInfo = OrderedDict()
    docInfo["documentType"] = jsonDocumentType
    docInfo["namespaces"] = namespaces = []
    oimTxmy["taxonomy"] = txmy = OrderedDict()

    # provide consistent order to taxonomy properties and objects
    txmy["name"] = os.path.splitext(extensionSchemaDoc.basename)[0]
    txmy["namespace"] = extensionSchemaDoc.targetNamespace
    txmy["version"] = jsonTxmyVersion
    txmy["entryPoint"] = os.path.basename(jsonFile)
    txmy["importedTaxonomies"] = imports = []
    txmy["concepts"] = concepts = []
    txmy["cubes"] = cubes = []
    txmy["domains"] = domains = []
    txmy["networks"] = networks = []
    txmy["relationships"] = relationships = []
    txmy["labels"] = labels = []
    sharedLabelRefs = {}
    txmy["references"] = references = []

    # taxonomy object
    extensionLinkbaseDocs = {doc
                             for doc, docReference in extensionSchemaDoc.referencesDocument.items()
                             if "href" in docReference.referenceTypes and docReference.referringModelObject.elementQname == XbrlConst.qnLinkLinkbaseRef}
    extensionLinkbaseDocs.add(extensionSchemaDoc)

    labelsRelationshipSet = dts.relationshipSet(XbrlConst.conceptLabel)
    for concept in sorted(set(dts.qnameConcepts.values()), key=lambda c:c.name): # may be twice if unqualified, with and without namespace
        if concept.modelDocument == extensionSchemaDoc:
            c = OrderedDict()
            concepts.append(c)
            c["name"] = str(concept.qname)
            if concept.typeQname: # may be absent
                c["dataType"] = str(concept.typeQname)
            if concept.substitutionGroupQname:
                c["substitutionGroup"] = str(concept.substitutionGroupQname)
            if concept.periodType:
                c["periodType"] = concept.periodType
            if concept.balance:
                c["balance"] = concept.balance
            c["abstract"] = str(concept.abstract).lower()
            c["nillable"] = str(concept.nillable).lower()
        conceptLabels = dict(((lbl.role, lbl.xmlLang), lbl)
                             for rel in labelsRelationshipSet.fromModelObject(concept)
                             for lbl in (rel.toModelObject,)
                             if lbl is not None)
        for _key, label in sorted(conceptLabels.items(), key=lambda i:i[0]):
            labelDupKey = (label.xmlLang, label.role, label.textValue)
            if labelDupKey in sharedLabelRefs:
                sharedLabelRefs[labelDupKey]["relatedId"].append(str(concept.qname))
            else:
                l = OrderedDict((
                    ("relatedId", [str(concept.qname)]),
                    ("language", label.xmlLang),
                    ("labelType", os.path.basename(label.role)),
                    ("value", label.textValue)))
                labels.append(l)
                sharedLabelRefs[labelDupKey] = l
        # TBD add references here

    # extended link roles defined in this document
    networkOrder = 0
    for roleURI, roleTypes in sorted(dts.roleTypes.items(),
            # sort on definition if any else URI
            key=lambda item: (item[1][0].definition if len(item[1]) and item[1][0].definition else item[0])):
        for roleType in roleTypes:
            if roleType.modelDocument == extensionSchemaDoc:
                name = f"{extensionPrefix}:_{os.path.basename(roleURI)}_"
                definition = roleType.definition
                # define network concept (not in XBRL 2.1
                c = OrderedDict((("name", name),
                                 ("dataType","dtr:networkItemType"),
                                 ("periodType", "duration"),
                                 ("substitutionGroup", "xbrli:item"),
                                 ("abstract", True),
                                 ("nillable", True)))
                concepts.append(c)
                networks.append( OrderedDict((
                    ("networkURI", roleType.roleURI),
                    ("name", name))))
                networkOrder += 1
                relationships.append( OrderedDict((
                    ("source", "xbrli:networkConcept"),
                    ("target", name),
                    ("order", networkOrder),
                    ("networkURI", "https://www.xbrl.org/Network"),
                    ("relationshipType", "root-child"))))
                if definition:
                    labels.append( OrderedDict((
                        ("relatedId", [name]),
                        ("language", primaryLang),
                        ("labelType", XbrlConst.standardLabel),
                        ("value", definition))))

    # cubes by linkrole
    for arcrole, linkrole, arcQN, linkQN in dts.baseSets.keys():
        if arcrole == XbrlConst.all and linkrole is not None and arcQN is None and linkQN is None:
            for rel in dts.relationshipSet(XbrlConst.all, linkrole).modelRelationships:
                if rel.modelDocument not in extensionLinkbaseDocs:
                    continue
                hc = rel.toModelObject
                priItem = rel.fromModelObject
                if hc is not None and priItem is not None:
                    dims = []
                    dim = OrderedDict((("dimensionConcept", "xbrl:PrimaryDimension"),
                                       ("domainID", priItem.name),
                                       ("dimensionType", "xbrl:concept")))
                    dims.append(dim)
                    # priItem domains
                    rels = []
                    domains.append( OrderedDict((
                        ("domainId", priItem.name),
                        ("domainConcept", str(priItem.qname)),
                        ("networkURI", rel.linkrole),
                        ("relationships", rels))) )
                    for domRel in dts.relationshipSet(XbrlConst.domainMember, rel.consecutiveLinkrole).fromModelObject(priItem):
                        domObj = domRel.toModelObject
                        if domObj is not None:
                            rels.append( OrderedDict((
                                ("source", str(priItem.qname)),
                                ("target", str(domObj.qname)),
                                ("order", domRel.order))) )
                    # dimension domains
                    for dimRel in dts.relationshipSet(XbrlConst.hypercubeDimension, rel.consecutiveLinkrole).fromModelObject(hc):
                        dimObj = dimRel.toModelObject
                        if dimObj is not None:
                            dim = OrderedDict((("dimensionConcept", str(dimObj.qname)),
                                               ("domainId", dimObj.name),
                                               ("dimensionType", "explicit")))
                            dims.append(dim)
                            domRels = []
                            domains.append( OrderedDict((
                                ("domainId", dimObj.name),
                                ("domainConcept", str(dimObj.qname)),
                                ("networkURI", rel.linkrole),
                                ("relationships", domRels))) )
                            for domRel in dts.relationshipSet(XbrlConst.dimensionDomain, rel.consecutiveLinkrole).fromModelObject(dimObj):
                                domObj = domRel.toModelObject
                                if domObj is not None:
                                    domRels.append( OrderedDict((
                                        ("source", str(dimObj.qname)),
                                        ("target", str(domObj.qname)),
                                        ("order", domRel.order))) )
                cubes.append( OrderedDict((
                    ("name", str(hc.qname)),
                    ("networkURI", rel.linkrole),
                    ("cubeType", "aggregate"),
                    ("dimensions", dims))) )

    # domains

    # tree walk recursive function
    def treeWalk(depth, concept, arcrole, relSet, visited):
        if concept is not None:
            if concept not in visited:
                visited.add(concept)
                for rel in relSet.fromModelObject(concept):
                    toConcept = rel.toModelObject
                    if toConcept is not None:
                        namespacesInUse.add(concept.qname.namespaceURI)
                        namespacesInUse.add(toConcept.qname.namespaceURI)
                        if rel.modelDocument in extensionLinkbaseDocs:
                            relationships.append( OrderedDict((
                                ("source", str(concept.qname)),
                                ("target", str(toConcept.qname)),
                                ("order", rel.order),
                                ("networkURI", rel.linkrole),
                                ("relationshipType", os.path.basename(rel.arcrole))) +
                                ((("weight", rel.weight),) if rel.weight is not None else ())
                                ) )
                        row = treeWalk(depth + 1, toConcept, arcrole, relSet, visited)
                visited.remove(concept)

    # use presentation relationships for conceptsWs
    for arcrole in (XbrlConst.parentChild,) + XbrlConst.summationItems:
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
                for rootConcept in linkRelationshipSet.rootConcepts:
                    # is root child required?
                    treeWalk(0, rootConcept, arcrole, linkRelationshipSet, set())

    for ns in sorted(namespacesInUse, key=lambda ns: namespacePrefixes[ns]):
        namespaces.append(OrderedDict((("prefix", namespacePrefixes[ns]),
                                       ("uri", ns))))

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
