'''
Save CHComponentFile is an example of a plug-in to both GUI menu and command line/web service
that will save the presentation tree of concepts in Charlie Hoffman's Component schema.

See COPYRIGHT.md for copyright information.
'''

from arelle.ModelDtsObject import ModelConcept, ModelRelationship
from arelle import XbrlConst
from arelle.Version import authorLabel, copyrightLabel
from lxml import etree

def generateCHComponent(dts, componentFile):
    if dts.fileSource.isArchive:
        return
    import os, io
    from arelle import XmlUtil, XbrlConst
    file = io.StringIO('''
<nsmap>
  <Component/>
</nsmap>
'''
     )
    from arelle.ModelObjectFactory import parser
    parser, parserLookupName, parserLookupClass = parser(dts,None)
    xmlDocument = etree.parse(file,parser=parser,base_url=componentFile)
    file.close()
    for componentElt in  xmlDocument.iter(tag="Component"):
        break

    # use presentation relationships for broader and narrower concepts
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
            elt = etree.SubElement(componentElt, "Network", attrib={
                                        "identifier": linkroleUri,
                                        "label": roledefinition})
            linkRelationshipSet = dts.relationshipSet(arcrole, linkroleUri)
            for rootConcept in linkRelationshipSet.rootConcepts:
                genConcept(dts, elt, rootConcept, None, arcrole, linkRelationshipSet, set())

    fh = open(componentFile, "w", encoding="utf-8")
    XmlUtil.writexml(fh, xmlDocument, encoding="utf-8")
    fh.close()

    dts.info("info:saveCHComponentFile",
             _("Component file for %(entryFile)s in file %(componentOutputFile)s."),
             modelObject=dts,
             entryFile=dts.uri, componentOutputFile=componentFile)

def xbrliType(type):
    if type is not None:
        if type.qname.namespaceURI == XbrlConst.xbrli:
            return type.qname
        qnameDerivedFrom = type.qnameDerivedFrom
        if isinstance(qnameDerivedFrom,list): # union
            if qnameDerivedFrom == XbrlConst.qnDateUnionXsdTypes:
                return "xbrli:dateTimeItemType"
        elif qnameDerivedFrom is not None:
            if qnameDerivedFrom.namespaceURI == XbrlConst.xbrli:  # xbrli type
                return qnameDerivedFrom
            return xbrliType(type.modelXbrl.qnameTypes.get(qnameDerivedFrom))
    return ""

def genConcept(dts, parentElt, concept, preferredLabel, arcrole, relationshipSet, visited):
    try:
        if concept is not None:
            attrs = {"name": str(concept.qname),
                     "label": concept.label(preferredLabel,linkroleHint=relationshipSet.linkrole),
                     "prefix": concept.qname.prefix}
            if concept.isHypercubeItem:
                tag = "Table"
            elif concept.isDimensionItem:
                tag = "Axis"
            elif concept.name.endswith("Domain"):
                tag = "Domain"
            elif concept.name.endswith("Member"):
                tag = "Member"
            else:
                if concept.name.endswith("LineItems"):
                    tag = "LineItems"
                else:
                    tag = "Concept"
                attrs["dataType"] = str(concept.type.qname)
                attrs["baseDataType"] = str(xbrliType(concept.type))
                attrs["abstract"] = str(concept.isAbstract).lower()
                attrs["periodType"] = concept.periodType

            elt = etree.SubElement(parentElt, tag, attrib=attrs)
            if concept not in visited:
                visited.add(concept)
                for modelRel in relationshipSet.fromModelObject(concept):
                    genConcept(dts, elt, modelRel.toModelObject, modelRel.preferredLabel, arcrole, relationshipSet, visited)
                visited.remove(concept)
    except AttributeError: #  bad relationship
        return

def saveCHComponentMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save CH Component file",
                     underline=0,
                     command=lambda: saveCHComponentMenuCommand(cntlr) )

def saveCHComponentMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No taxonomy loaded.")
        return

        # get file name into which to save log file while in foreground thread
    componentFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save Component file"),
            initialdir=cntlr.config.setdefault("chComponentFileDir","."),
            filetypes=[(_("Component file .xml"), "*.xml")],
            defaultextension=".xml")
    if not componentFile:
        return False
    import os
    cntlr.config["chComponentFileDir"] = os.path.dirname(componentFile)
    cntlr.saveConfig()

    try:
        generateCHComponent(cntlr.modelManager.modelXbrl, componentFile)
    except Exception as ex:
        dts = cntlr.modelManager.modelXbrl
        dts.error("exception",
            _("Component file generation exception: %(error)s"), error=ex,
            modelXbrl=dts,
            exc_info=True)

def saveCHComponentCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options with a save DTS option
    parser.add_option("--save-CH-component",
                      action="store",
                      dest="chComponentFile",
                      help=_("Save Charlie Hoffman Component semantic definition in specified xml file."))

def saveCHComponentCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "chComponentFile", False):
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        generateCHComponent(cntlr.modelManager.modelXbrl, options.chComponentFile)


__pluginInfo__ = {
    'name': 'Save CH Component',
    'version': '0.9',
    'description': "This plug-in adds a feature to output a Charlie Hoffman Component file. "
                   "This provides a semantic definition of taxonomy contents.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveCHComponentMenuEntender,
    'CntlrCmdLine.Options': saveCHComponentCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': saveCHComponentCommandLineXbrlRun,
}
