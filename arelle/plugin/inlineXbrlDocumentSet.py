'''
Inline XBRL Document Set plug-in.

Supports opening manifest file that identifies inline documents of a document set.

Saves extracted instance document.

(Does not currently support multiple target instance documents in a document set.)

(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
from arelle import ModelXbrl, ValidateXbrlDimensions, XbrlConst
from arelle.ModelDocument import ModelDocument, ModelDocumentReference, Type, load
import os

class ModelInlineXbrlDocumentSet(ModelDocument):

    def saveTargetDocument(self):
        targetUrl = self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(self.targetDocumentPreferredFilename, self.filepath)
        targetUrlParts = targetUrl.rpartition(".")
        targetUrl = targetUrlParts[0] + "_extracted." + targetUrlParts[2]
        self.modelXbrl.modelManager.showStatus(_("Extracting instance ") + os.path.basename(targetUrl))
        targetInstance = ModelXbrl.create(self.modelXbrl.modelManager, 
                                          newDocumentType=Type.INSTANCE,
                                          url=targetUrl,
                                          schemaRefs=self.targetDocumentSchemaRefs,
                                          isEntry=True)
        ValidateXbrlDimensions.loadDimensionDefaults(targetInstance) # need dimension defaults 
        for context in self.modelXbrl.contexts.values():
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
        for unit in self.modelXbrl.units.values():
            measures = unit.measures
            newUnit = targetInstance.createUnit(measures[0], measures[1], id=unit.id)

        self.modelXbrl.modelManager.showStatus(_("Creating and validating facts"))
        for fact in self.modelXbrl.facts:
            if fact.isItem:
                attrs = [("contextRef", fact.contextID)]
                if fact.isNumeric:
                    attrs.append(("unitRef", fact.unitID))
                    if fact.get("decimals"):
                        attrs.append(("decimals", fact.get("decimals")))
                    if fact.get("precision"):
                        attrs.append(("precision", fact.get("precision")))
                if fact.isNil:
                    attrs.append((XbrlConst.qnXsiNil,"true"))
                    text = None
                else:
                    text = fact.xValue if fact.xValid else fact.elementText
                newFact = targetInstance.createFact(fact.qname, attributes=attrs, text=text)
        targetInstance.saveInstance(overrideFilepath=targetUrl)
        self.modelXbrl.modelManager.showStatus(_("Saved extracted instance"), 5000)
        
    def discoverInlineXbrlDocumentSet(self):
        for instanceElt in self.xmlRootElement.iter(tag="{http://disclosure.edinet-fsa.go.jp/2013/manifest}instance"):
            targetId = instanceElt.id
            self.targetDocumentId = targetId
            self.targetDocumentPreferredFilename = instanceElt.get('preferredFilename')
            self.targetDocumentSchemaRefs = set()  # union all the instance schemaRefs
            for ixbrlElt in instanceElt.iter(tag="{http://disclosure.edinet-fsa.go.jp/2013/manifest}ixbrl"):
                uri = ixbrlElt.elementText.strip()
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
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None or not isinstance(cntlr.modelManager.modelXbrl.modelDocument, ModelInlineXbrlDocumentSet):
        cntlr.addToLog("No inline XBRL document manifest loaded.")
        return
    import threading
    thread = threading.Thread(target=lambda _cntlr=cntlr:
                                _cntlr.modelManager.modelXbrl.modelDocument.saveTargetDocument())
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
