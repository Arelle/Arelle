# -*- coding: utf-8 -*-
'''
objectmaker.py is a plug-in that will draw diagrams from linkbases

ObjectMaker(r) is a registered trademark of Workiva, Inc.

This product uses graphviz, which must be installed separately on the platform.

See COPYRIGHT.md for copyright information.
'''
import os, io, time
from tkinter import Menu
from arelle import ModelDocument, XmlUtil, XbrlConst
from arelle.ModelDtsObject import ModelConcept
from arelle.Version import authorLabel, copyrightLabel

diagramNetworks = {
    "uml": ("http://xbrl.us/arcrole/Aggregation", "http://xbrl.us/arcrole/Composition", "http://xbrl.us/arcrole/Inheritance"),
    "dts": (),
    "pre": (XbrlConst.parentChild,),
    "cal": (XbrlConst.summationItem,),
    "def": (XbrlConst.essenceAlias, XbrlConst.similarTuples, XbrlConst.requiresElement, XbrlConst.generalSpecial,
            XbrlConst.all, XbrlConst.notAll, XbrlConst.hypercubeDimension, XbrlConst.dimensionDomain,
            XbrlConst.domainMember, XbrlConst.dimensionDefault),
    "anc": (XbrlConst.widerNarrower,)
    }

# graphviz attributes: http://www.graphviz.org/doc/info/attrs.html

networkEdgeTypes = {
    "uml": {
        "inheritance": {"dir": "back", "arrowtail": "empty"},
        "aggregation": {"dir": "back", "arrowtail": "odiamond"},
        "composition": {"dir": "back", "arrowtail": "diamond"}
        },
    "dts": {
        "all-types": {"dir": "forward", "arrowhead": "normal"}
        },
    "pre": {
        "parent-child": {"dir": "forward", "arrowhead": "normal"}
        },
    "cal": {
        "summation-item": {"dir": "forward", "arrowhead": "normal"}
        },
    "def": {
        "essence-alias": {"dir": "forward", "arrowhead": "normal"},
        "similar-tuples": {"dir": "forward", "arrowhead": "normal"},
        "requires-element": {"dir": "forward", "arrowhead": "normal"},
        "general-special": {"dir": "forward", "arrowhead": "normal"},
        "all": {"dir": "forward", "arrowhead": "normal"},
        "notall": {"dir": "forward", "arrowhead": "normal"}, # arc roles are lower-cased here
        "hypercube-dimension": {"dir": "forward", "arrowhead": "normal"},
        "dimension-domain": {"dir": "forward", "arrowhead": "normal"},
        "domain-member": {"dir": "forward", "arrowhead": "normal"},
        "dimension-default": {"dir": "forward", "arrowhead": "normal"}
        },
    "anc": {
        "wider-narrower": {"dir": "forward", "arrowhead": "normal"}
        },
    }

def drawDiagram(modelXbrl, diagramFile, diagramNetwork=None, viewDiagram=False):
    if diagramNetwork not in diagramNetworks:
        modelXbrl.error("objectmaker:diagramNetwork",
                        "Diagram network %(diagramNetwork)s not recognized, please specify one of %(recognizedDiagramNetworks)s",
                        modelXbrl=modelXbrl, diagramNetwork=diagramNetwork, recognizedDiagramNetworks=", ".join(diagramNetworks))
        return

    try:
        from graphviz import Digraph, backend
    except ImportError:
        modelXbrl.error("objectmaker:missingLibrary",
                        "Missing library, please install graphviz for python importing",
                        modelXbrl=modelXbrl)
        return

    isUML = diagramNetwork == "uml"
    isBaseSpec = diagramNetwork in ("pre", "cal", "def", "anch")
    graphName = os.path.splitext(modelXbrl.modelDocument.basename)[0]
    mdl = Digraph(comment=graphName)
    mdl.attr("graph")
    mdl.node('node_title', graphName, shape="none", fontname="Bitstream Vera Sans")
    mdl.attr('node', shape="record")
    mdl.attr('node', fontname="Bitstream Vera Sans")
    mdl.attr('node', fontsize="8")

    if isUML:
        arcroleName = "http://xbrl.us/arcrole/Property"
        propertiesRelationshipSet = modelXbrl.relationshipSet(arcroleName)
        if not propertiesRelationshipSet:
            modelXbrl.modelManager.addToLog(_("no relationships for {0}").format(arcroleName))
            return False

    def node(mdl, id, modelObject):
        if modelObject is not None:
            mdl.attr("node", style="") # white classes
            if isUML:
                _properties = "".join(r"+{} {}\l".format(rel.toModelObject.qname.localName, rel.toModelObject.niceType)
                                                        for rel in propertiesRelationshipSet.fromModelObject(modelObject)
                                                        if rel.toModelObject is not None)
                mdl.node(id, "{{{}|{}}}".format(modelObject.qname.localName, _properties))
            elif isBaseSpec and isinstance(modelObject, ModelConcept):
                concept = modelObject
                if concept.isHypercubeItem:
                    _properties = "Hypercube"
                elif concept.isExplicitDimension:
                    _properties = "Dimension, Explicit"
                elif concept.isExplicitDimension:
                    _properties = "Dimension, Typed ({} {})".format(typedDomainElement.qname, typedDomainElement.niceType)
                elif concept.isEnumeration:
                    _properties = "Enumeration ({})".format(concept.enumDomain.qname)
                else:
                    _properties = "{}{}".format("Abstract " if modelObject.isAbstract else "",
                                                modelObject.niceType)
                mdl.node(id, "{{{}|{}}}".format(modelObject.qname.localName, _properties))
            elif isinstance(modelObject, ModelDocument.ModelDocument):
                mdl.node(id, "{{{}|{}}}".format(modelObject.basename, modelObject.gettype()))
            elif isinstance(modelObject, str): # linkrole definition
                mdl.node(id, "{{{}}}".format(modelObject))
            else:
                mdl.node(id, "{{{}}}".format(modelObject.qname.localName))

    nodes = set()
    edges = set()
    arcroles = diagramNetworks[diagramNetwork]

    lang = None # from parameter for override

    # sort URIs by definition
    linkroleUris = set()
    if isBaseSpec:
        for arcrole in arcroles:
            graphRelationshipSet = modelXbrl.relationshipSet(arcrole)
            for linkroleUri in graphRelationshipSet.linkRoleUris:
                modelRoleTypes = modelXbrl.roleTypes.get(linkroleUri)
                if modelRoleTypes:
                    roledefinition = (modelRoleTypes[0].genLabel(lang=lang, strip=True) or modelRoleTypes[0].definition or linkroleUri)
                else:
                    roledefinition = linkroleUri
                linkroleUris.add((roledefinition, linkroleUri))
    else:
        linkroleUris.add((None, None))

    for roledefinition, linkroleUri in sorted(linkroleUris):
        for arcrole in arcroles:
            relationshipType = arcrole.rpartition("/")[2].lower()
            edgeType = networkEdgeTypes[diagramNetwork].get(relationshipType)
            if edgeType is None:
                modelXbrl.warning("objectmaker:unrecognizedArcrole",
                                  "Arcrole missing from networkEdgeTypes: %(arcrole)s:",
                                  modelXbrl=modelXbrl, arcrole=arcrole)
                continue
            graphRelationshipSet = modelXbrl.relationshipSet(arcrole, linkroleUri)
            roleprefix = (linkroleUri.replace("/","_").replace(":","_") + "_") if linkroleUri else ""
            if not graphRelationshipSet:
                continue
            if linkroleUri is not None:
                node(mdl, roleprefix, roledefinition or roleUri)
                for rootConcept in graphRelationshipSet.rootConcepts:
                    childName = roleprefix + rootConcept.qname.localName
                    node(mdl, childName, rootConcept)
                    nodes.add(childName)
                    mdl.edge(roleprefix, childName,
                             dir=edgeType.get("dir"), arrowhead=edgeType.get("arrowhead"), arrowtail=edgeType.get("arrowtail"))
            for rel in graphRelationshipSet.modelRelationships:
                parent = rel.fromModelObject
                child = rel.toModelObject
                if parent is None or child is None:
                    continue
                parentName = roleprefix + parent.qname.localName
                childName = roleprefix + child.qname.localName
                if parentName not in nodes:
                    node(mdl, parentName, parent)
                    nodes.add(parentName)
                if childName not in nodes:
                    node(mdl, childName, child)
                    nodes.add(childName)
                edgeKey = (relationshipType, parentName, childName)
                if edgeKey not in edges:
                    edges.add(edgeKey)
                    mdl.edge(parentName, childName,
                             dir=edgeType.get("dir"), arrowhead=edgeType.get("arrowhead"), arrowtail=edgeType.get("arrowtail"))

    if diagramNetwork == "dts":
        def viewDtsDoc(modelDoc, parentDocName, grandparentDocName):
            docName = modelDoc.basename
            docType = modelDoc.gettype()
            if docName not in nodes:
                node(mdl, docName, modelDoc)
            if parentDocName:
                edgeKey = (parentDocName, docType, docName)
                if edgeKey in edges:
                    return
                edges.add(edgeKey)
                edgeType = networkEdgeTypes[diagramNetwork]["all-types"]
                mdl.edge(parentDocName, docName,
                         dir=edgeType.get("dir"), arrowhead=edgeType.get("arrowhead"), arrowtail=edgeType.get("arrowtail"))
            for referencedDoc in modelDoc.referencesDocument.keys():
                if referencedDoc.basename != parentDocName: # skip reverse linkbase ref
                    viewDtsDoc(referencedDoc, docName, parentDocName)

        viewDtsDoc(modelXbrl.modelDocument, None, None)

    mdl.format = "pdf"
    try:
        mdl.render(diagramFile.replace(".pdf", ".gv"), view=viewDiagram)
    except backend.ExecutableNotFound as ex:
        modelXbrl.warning("objectmaker:graphvizExecutable",
                        "Diagram saving requires installation of graphviz, error: %(error)s:",
                        modelXbrl=modelXbrl, error=ex)


def objectmakerMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    drawDiagMenu = Menu(cntlr.menubar, tearoff=0)
    menu.add_cascade(label="Draw Diagram", underline=0, menu=drawDiagMenu)
    drawDiagMenu.add_command(label=_("DTS"), underline=0, command=lambda: objectmakerMenuCommand(cntlr, "dts") )
    drawDiagMenu.add_command(label=_("Presentation"), underline=0, command=lambda: objectmakerMenuCommand(cntlr, "pre") )
    drawDiagMenu.add_command(label=_("Calculation"), underline=0, command=lambda: objectmakerMenuCommand(cntlr, "cal") )
    drawDiagMenu.add_command(label=_("Definition"), underline=0, command=lambda: objectmakerMenuCommand(cntlr, "def") )
    drawDiagMenu.add_command(label=_("UML"), underline=0, command=lambda: objectmakerMenuCommand(cntlr, "uml") )

def objectmakerMenuCommand(cntlr, diagramNetwork):
    # save DTS menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No taxonomy loaded.")
        return
        # get file name into which to save log file while in foreground thread
    diagramFile = cntlr.uiFileDialog("save",
            title=_("objectmaker - Save {} diagram").format(diagramNetwork),
            initialdir=cntlr.config.setdefault("diagramFileDir","."),
            filetypes=[(_("Diagram file .pdf"), "*.pdf")],
            defaultextension=".pdf")
    if not diagramFile:
        return False
    import os
    cntlr.config["diagramFileDir"] = os.path.dirname(diagramFile)
    cntlr.saveConfig()

    import threading
    thread = threading.Thread(target=lambda
                                  _modelXbrl=cntlr.modelManager.modelXbrl,
                                  _diagramFile=diagramFile:
                                        drawDiagram(_modelXbrl, _diagramFile, diagramNetwork, True))
    thread.daemon = True
    thread.start()

def objectmakerCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options with a save DTS option
    parser.add_option("--save-diagram",
                      action="store",
                      dest="saveDiagram",
                      help=_("Save Diagram file"))
    parser.add_option("--diagram-network",
                      action="store",
                      dest="diagramNetwork",
                      help=_("Network to diagram: dts, pre, cal, def, uml"))
    parser.add_option("--view-diagram",
                      action="store_true",
                      dest="viewDiagram",
                      help=_("Show diagram in GUI viewer"))

def objectmakerCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    diagramFile = getattr(options, "saveDiagram", None)
    if diagramFile:
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        diagramNetwork = getattr(options, "diagramNetwork")
        viewDiagram = getattr(options, "viewDiagram", False)
        drawDiagram(cntlr.modelManager.modelXbrl, diagramFile, diagramNetwork, viewDiagram)

__pluginInfo__ = {
    'name': 'ObjectMaker',
    'version': '1.0',
    'description': "ObjectMaker(r) diagrams XBRL relationship graphs.",
    'license': 'Apache-2 (ObjectMaker), Eclipse (Graphviz)',
    'author': authorLabel,
    'copyright': copyrightLabel + ' Graphviz (c) 2011 AT&T',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': objectmakerMenuEntender,
    'CntlrCmdLine.Options': objectmakerCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': objectmakerCommandLineXbrlRun,
}
