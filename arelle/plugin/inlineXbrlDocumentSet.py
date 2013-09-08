'''
Inline XBRL Document Set plug-in.

Supports opening manifest file that identifies inline documents of a document set.

Saves extracted instance document.

(Does not currently support multiple target instance documents in a document set.)

(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
from arelle import ModelXbrl, ValidateXbrlDimensions, XmlUtil, XbrlConst
from arelle.PrototypeDtsObject import LocPrototype
from arelle.ModelDocument import ModelDocument, ModelDocumentReference, Type, load
import os

class ModelInlineXbrlDocumentSet(ModelDocument):
        
    def discoverInlineXbrlDocumentSet(self):
        for instanceElt in self.xmlRootElement.iter(tag="{http://disclosure.edinet-fsa.go.jp/2013/manifest}instance"):
            targetId = instanceElt.id
            self.targetDocumentId = targetId
            self.targetDocumentPreferredFilename = instanceElt.get('preferredFilename')
            self.targetDocumentSchemaRefs = set()  # union all the instance schemaRefs
            for ixbrlElt in instanceElt.iter(tag="{http://disclosure.edinet-fsa.go.jp/2013/manifest}ixbrl"):
                uri = ixbrlElt.textValue.strip()
                if uri:
                    doc = load(self.modelXbrl, uri, base=self.filepath, referringElement=instanceElt)
                    if doc is not None and doc not in self.referencesDocument:
                        referencedDocument = ModelDocumentReference("inlineDocument", instanceElt)
                        referencedDocument.targetId = targetId
                        self.referencesDocument[doc] = referencedDocument
                        for referencedDoc in doc.referencesDocument.keys():
                            if referencedDoc.type == Type.SCHEMA:
                                self.targetDocumentSchemaRefs.add(doc.relativeUri(referencedDoc.uri))
        return True

def saveTargetDocument(modelXbrl, targetDocumentFilename, targetDocumentSchemaRefs):
    targetUrl = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(targetDocumentFilename, modelXbrl.modelDocument.filepath)
    targetUrlParts = targetUrl.rpartition(".")
    targetUrl = targetUrlParts[0] + "_extracted." + targetUrlParts[2]
    modelXbrl.modelManager.showStatus(_("Extracting instance ") + os.path.basename(targetUrl))
    targetInstance = ModelXbrl.create(modelXbrl.modelManager, 
                                      newDocumentType=Type.INSTANCE,
                                      url=targetUrl,
                                      schemaRefs=targetDocumentSchemaRefs,
                                      isEntry=True)
    ValidateXbrlDimensions.loadDimensionDefaults(targetInstance) # need dimension defaults 
    # roleRef and arcroleRef (of each inline document)
    for sourceRefs in (modelXbrl.targetRoleRefs, modelXbrl.targetArcroleRefs):
        for roleRefElt in sourceRefs.values():
            XmlUtil.addChild(targetInstance.modelDocument.xmlRootElement, roleRefElt.qname, 
                             attributes=roleRefElt.items())
    
    # contexts
    for context in modelXbrl.contexts.values():
        newCntx = targetInstance.createContext(context.entityIdentifier[0],
                                               context.entityIdentifier[1],
                                               'instant' if context.isInstantPeriod else
                                               'duration' if context.isStartEndPeriod
                                               else 'forever',
                                               context.startDatetime,
                                               context.endDatetime,
                                               None, 
                                               context.qnameDims, [], [],
                                               id=context.id)
    for unit in modelXbrl.units.values():
        measures = unit.measures
        newUnit = targetInstance.createUnit(measures[0], measures[1], id=unit.id)

    modelXbrl.modelManager.showStatus(_("Creating and validating facts"))
    newFactForOldObjId = {}
    def createFacts(facts, parent):
        for fact in modelXbrl.facts:
            if fact.isItem:
                attrs = {"contextRef": fact.contextID}
                if fact.isNumeric:
                    attrs["unitRef"] = fact.unitID
                    if fact.get("decimals"):
                        attrs["decimals"] = fact.get("decimals")
                    if fact.get("precision"):
                        attrs["precision"] = fact.get("precision")
                if fact.isNil:
                    attrs[XbrlConst.qnXsiNil] = "true"
                    text = None
                else:
                    text = fact.xValue if fact.xValid else fact.textValue
                newFact = targetInstance.createFact(fact.qname, attributes=attrs, text=text, parent=parent)
                newFactForOldObjId[fact.objectIndex] = newFact
            elif fact.isTuple:
                newTuple = targetInstance.createFact(fact.qname, parent=parent)
                newFactForOldObjId[fact.objectIndex] = newTuple
                createFacts(fact.modelTupleFacts, newTuple)
                
    createFacts(modelXbrl.facts, None)
    # footnote links
    modelXbrl.modelManager.showStatus(_("Creating and validating footnotes & relationships"))
    for linkKey, linkPrototypes in modelXbrl.baseSets.items():
        arcrole, linkrole, linkqname, arcqname = linkKey
        if (linkrole and linkqname and arcqname and # fully specified roles
            any(lP.modelDocument.type == Type.INLINEXBRL for lP in linkPrototypes)):
            for linkPrototype in linkPrototypes:
                newLink = XmlUtil.addChild(targetInstance.modelDocument.xmlRootElement, linkqname, 
                                           attributes=linkPrototype.attributes)
                for linkChild in linkPrototype:
                    if isinstance(linkChild, LocPrototype) and "{http://www.w3.org/1999/xlink}href" not in linkChild.attributes:
                        linkChild.attributes["{http://www.w3.org/1999/xlink}href"] = \
                        "#" + XmlUtil.elementFragmentIdentifier(newFactForOldObjId[linkChild.dereference().objectIndex])
                    XmlUtil.addChild(newLink, linkChild.qname, 
                                     attributes=linkChild.attributes,
                                     text=linkChild.textValue)
            
    targetInstance.saveInstance(overrideFilepath=targetUrl)
    modelXbrl.modelManager.showStatus(_("Saved extracted instance"), 5000)

def identifyInlineXbrlDocumentSet(modelXbrl, rootNode, filepath):
    for manifestElt in rootNode.iter(tag="{http://disclosure.edinet-fsa.go.jp/2013/manifest}manifest"):
        # it's an edinet fsa manifest of an inline XBRL document set
        return (Type.INLINEXBRLDOCUMENTSET, ModelInlineXbrlDocumentSet, manifestElt)
    return None # not a document set

def discoverInlineXbrlDocumentSet(modelDocument):
    if isinstance(modelDocument, ModelInlineXbrlDocumentSet):
        return modelDocument.discoverInlineXbrlDocumentSet()        
    return False  # not discoverable by this plug-in

def saveTargetDocumentMenuEntender(cntlr, menu):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save target document", 
                     underline=0, 
                     command=lambda: backgroundSaveTargetDocumentMenuCommand(cntlr) )

def backgroundSaveTargetDocumentMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if (cntlr.modelManager is None or 
        cntlr.modelManager.modelXbrl is None or 
        not (isinstance(cntlr.modelManager.modelXbrl.modelDocument, ModelInlineXbrlDocumentSet) or
             cntlr.modelManager.modelXbrl.modelDocument.type == Type.INLINEXBRL)):
        cntlr.addToLog("No inline XBRL document manifest loaded.")
        return
    modelDocument = cntlr.modelManager.modelXbrl.modelDocument
    if isinstance(modelDocument, ModelInlineXbrlDocumentSet):
        targetFilename = modelDocument.targetDocumentPreferredFilename
        targetSchemaRefs = modelDocument.targetDocumentSchemaRefs
    else:
        filepath, fileext = os.path.splitext(modelDocument.filepath)
        targetFilename = filepath + "_instance." + fileext
        targetSchemaRefs = set(modelDocument.relativeUri(referencedDoc.uri)
                               for referencedDoc in modelDocument.referencesDocument.keys()
                               if referencedDoc.type == Type.SCHEMA)
    import threading
    thread = threading.Thread(target=lambda _x = modelDocument.modelXbrl, _f = targetFilename, _s = targetSchemaRefs:
                                    saveTargetDocument(_x, _f, _s))
    thread.daemon = True
    thread.start()

def saveTargetDocumentCommandLineOptionExtender(parser):
    # extend command line options with a save DTS option
    parser.add_option("--save-instance", 
                      action="store_true", 
                      dest="saveTargetInstance", 
                      help=_("Save target instance document"))

def saveTargetDocumentCommandLineXbrlRun(cntlr, options, modelXbrl):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "saveTargetInstance", False):
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None or not isinstance(cntlr.modelManager.modelXbrl.modelDocument, ModelInlineXbrlDocumentSet):
            cntlr.addToLog("No inline XBRL document manifest loaded.")
            return
        cntlr.modelManager.modelXbrl.modelDocument.saveTargetDocument()


__pluginInfo__ = {
    'name': 'Inline XBRL Document Set',
    'version': '0.9',
    'description': "This plug-in adds a feature to read manifest files of inline XBRL document sets "
                    " and to save the embedded XBRL instance document.  "
                    "Support single target instance documents in a single document set.  ",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2013 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveTargetDocumentMenuEntender,
    'CntlrCmdLine.Options': saveTargetDocumentCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': saveTargetDocumentCommandLineXbrlRun,
    'ModelDocument.IdentifyType': identifyInlineXbrlDocumentSet,
    'ModelDocument.Discover': discoverInlineXbrlDocumentSet,
}
