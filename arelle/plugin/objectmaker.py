# -*- coding: utf-8 -*-
'''
objectmaker.py is a plug-in that will draw diagrams from linkbases

ObjectMaker(r) is a registered trademark of Mark V Systems Limited

This product uses graphviz, which must be installed separately on the platform.

(c) Copyright 2017 Mark V Systems Limited, All rights reserved.
'''
import os, io, time, re
from arelle import ModelDocument, XmlUtil


def drawDiagram(modelXbrl, diagramFile, viewDiagram=False):
    try:
        from graphviz import Digraph
    except ImportError:
        modelXbrl.error("objectmaker:missingLibrary",
                        "Missing library, please install graphviz for python importing",
                        modelXbrl=modelXbrl)
        return
    
    graphName = os.path.splitext(modelXbrl.modelDocument.basename)[0]
    mdl = Digraph(comment=graphName)
    mdl.attr("graph")
    mdl.node('node_title', graphName, shape="none", fontname="Bitstream Vera Sans")
    mdl.attr('node', shape="record")
    mdl.attr('node', fontname="Bitstream Vera Sans")
    mdl.attr('node', fontsize="8")
    
    propertiesRelationshipSet = modelXbrl.relationshipSet("http://xbrl.us/arcrole/Property")
    if not propertiesRelationshipSet:
        modelXbrl.modelManager.addToLog(_("no relationships for {0}").format(arcroleName))
        return False

    def node(mdl, id, modelObject):
        if modelObject is not None:
            _properties = "".join("+{} {}\l".format(rel.toModelObject.qname.localName, rel.toModelObject.niceType)
                                                    for rel in propertiesRelationshipSet.fromModelObject(modelObject)
                                                    if rel.toModelObject is not None)
            mdl.attr("node", style="") # white classes
            mdl.node(id, "{{{}|{}}}".format(modelObject.qname.localName, _properties))
    
    nodes = set()
    edges = set()

    for arcrole in ("http://xbrl.us/arcrole/Aggregation", "http://xbrl.us/arcrole/Composition", "http://xbrl.us/arcrole/Inheritance"):
        relationshipType = arcrole.rpartition("/")[2].lower()
        graphRelationshipSet = modelXbrl.relationshipSet(arcrole)
        if not graphRelationshipSet:
            continue
        for rel in graphRelationshipSet.modelRelationships:
            parent = rel.fromModelObject
            parentName = parent.qname.localName
            child = rel.toModelObject
            if child is None:
                continue
            childName = child.qname.localName
            if parentName not in nodes:
                node(mdl, parentName, parent)
                nodes.add(parentName)
            if childName not in nodes:
                node(mdl, childName, child)
                nodes.add(childName)
            edgeKey = (relationshipType, parentName, childName)
            if edgeKey not in edges:
                edges.add(edgeKey)
                arrowType = {"inheritance": "empty", "aggregation": "odiamond", "composition": "diamond"}[relationshipType]
                mdl.edge(parentName, childName, arrowtail=arrowType, dir="back")
            
    mdl.format = "pdf"
    mdl.render(diagramFile.replace(".pdf", ".gv"), view=viewDiagram) 

def objectmakerMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Draw Diagram", 
                     underline=0, 
                     command=lambda: objectmakerMenuCommand(cntlr) )

def objectmakerMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No taxonomy loaded.")
        return
        # get file name into which to save log file while in foreground thread
    diagramFile = cntlr.uiFileDialog("save",
            title=_("objectmaker - Save Diagram"),
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
                                        drawDiagram(_modelXbrl, _diagramFile, True))
    thread.daemon = True
    thread.start()
    
def objectmakerCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options with a save DTS option
    parser.add_option("--save-diagram", 
                      action="store", 
                      dest="saveDiagram", 
                      help=_("Save Diagram file"))

def objectmakerCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    diagramFile = getattr(options, "saveDiagram", None)
    if diagramFile:
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        drawDiagram(cntlr.modelManager.modelXbrl, diagramFile)

__pluginInfo__ = {
    'name': 'ObjectMaker',
    'version': '0.9',
    'description': "ObjectMaker(r) diagrams XBRL relationship graphs.",
    'license': 'Apache-2 (ObjectMaker), Eclipse (Graphviz)',
    'author': 'Mark V Systems Limited',
    'copyright': 'ObjectMaker (c) Copyright 2017 Mark V Systems Limited, All rights reserved.'
                  'Graphviz (c) 2011 AT&T',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': objectmakerMenuEntender,
    'CntlrCmdLine.Options': objectmakerCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': objectmakerCommandLineXbrlRun,
}
