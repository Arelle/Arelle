'''
Inline XBRL Document Set plug-in.

Supports opening manifest file that identifies inline documents of a document set.

Saves extracted instance document.

(Does not currently support multiple target instance documents in a document set.)

(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
from arelle import ModelXbrl, ValidateXbrlDimensions, XbrlConst
from arelle.PrototypeDtsObject import LocPrototype, ArcPrototype
from arelle.ModelInstanceObject import ModelInlineFootnote
from arelle.ModelDocument import ModelDocument, ModelDocumentReference, Type, load
from arelle.UrlUtil import isHttpUrl
from arelle.ValidateFilingText import CDATApattern
from arelle.XmlUtil import addChild, copyIxFootnoteHtml, elementFragmentIdentifier
import os, zipfile
from optparse import SUPPRESS_HELP
from lxml.etree import XML, XMLSyntaxError
from collections import defaultdict

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

def saveTargetDocument(modelXbrl, targetDocumentFilename, targetDocumentSchemaRefs, outputZip=None, filingFiles=None):
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
            addChild(targetInstance.modelDocument.xmlRootElement, roleRefElt.qname, 
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
        for fact in facts:
            if fact.isItem:
                attrs = {"contextRef": fact.contextID}
                if fact.id:
                    attrs["id"] = fact.id
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
                if filingFiles and fact.concept is not None and fact.concept.isTextBlock:
                    # check for img and other filing references
                    for xmltext in [text] + CDATApattern.findall(text):
                        try:
                            for elt in XML("<body>\n{0}\n</body>\n".format(xmltext)):
                                if elt.tag in ("a", "img") and not isHttpUrl(attrValue) and not os.path.isabs(attrvalue):
                                    for attrTag, attrValue in elt.items():
                                        if attrTag in ("href", "src"):
                                            filingFiles.add(attrValue)
                        except (XMLSyntaxError, UnicodeDecodeError):
                            pass
            elif fact.isTuple:
                newTuple = targetInstance.createFact(fact.qname, parent=parent)
                newFactForOldObjId[fact.objectIndex] = newTuple
                createFacts(fact.modelTupleFacts, newTuple)
                
    createFacts(modelXbrl.facts, None)
    # footnote links
    footnoteIdCount = {}
    modelXbrl.modelManager.showStatus(_("Creating and validating footnotes & relationships"))
    HREF = "{http://www.w3.org/1999/xlink}href"
    footnoteLinks = defaultdict(list)
    for linkKey, linkPrototypes in modelXbrl.baseSets.items():
        arcrole, linkrole, linkqname, arcqname = linkKey
        if (linkrole and linkqname and arcqname and # fully specified roles
            arcrole != "XBRL-footnotes" and
            any(lP.modelDocument.type == Type.INLINEXBRL for lP in linkPrototypes)):
            for linkPrototype in linkPrototypes:
                if linkPrototype not in footnoteLinks[linkrole]:
                    footnoteLinks[linkrole].append(linkPrototype)
    for linkrole in sorted(footnoteLinks.keys()):
        for linkPrototype in footnoteLinks[linkrole]:
            newLink = addChild(targetInstance.modelDocument.xmlRootElement, 
                               linkPrototype.qname, 
                               attributes=linkPrototype.attributes)
            for linkChild in linkPrototype:
                attributes = linkChild.attributes
                if isinstance(linkChild, LocPrototype):
                    if HREF not in linkChild.attributes:
                        linkChild.attributes[HREF] = \
                        "#" + elementFragmentIdentifier(newFactForOldObjId[linkChild.dereference().objectIndex])
                    addChild(newLink, linkChild.qname, 
                             attributes=attributes)
                elif isinstance(linkChild, ArcPrototype):
                    addChild(newLink, linkChild.qname, attributes=attributes)
                elif isinstance(linkChild, ModelInlineFootnote):
                    idUseCount = footnoteIdCount.get(linkChild.footnoteID, 0) + 1
                    if idUseCount > 1: # if footnote with id in other links bump the id number
                        attributes = linkChild.attributes.copy()
                        attributes["id"] = "{}_{}".format(attributes["id"], idUseCount)
                    footnoteIdCount[linkChild.footnoteID] = idUseCount
                    newChild = addChild(newLink, linkChild.qname, 
                                        attributes=attributes)
                    copyIxFootnoteHtml(linkChild, newChild, withText=True)
                    if filingFiles and linkChild.textValue:
                        footnoteHtml = XML("<body/>")
                        copyIxFootnoteHtml(linkChild, footnoteHtml)
                        for elt in footnoteHtml.iter():
                            if elt.tag in ("a", "img"):
                                for attrTag, attrValue in elt.items():
                                    if attrTag in ("href", "src") and not isHttpUrl(attrValue) and not os.path.isabs(attrvalue):
                                        filingFiles.add(attrValue)
        
    targetInstance.saveInstance(overrideFilepath=targetUrl, outputZip=outputZip)
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
                     command=lambda: runSaveTargetDocumentMenuCommand(cntlr, runInBackground=True) )

def runSaveTargetDocumentMenuCommand(cntlr, runInBackground=False, saveTargetFiling=False):
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
        if fileext not in (".xml", ".xbrl"):
            fileext = ".xbrl"
        targetFilename = filepath + fileext
        targetSchemaRefs = set(modelDocument.relativeUri(referencedDoc.uri)
                               for referencedDoc in modelDocument.referencesDocument.keys()
                               if referencedDoc.type == Type.SCHEMA)
    if runInBackground:
        import threading
        thread = threading.Thread(target=lambda _x = modelDocument.modelXbrl, _f = targetFilename, _s = targetSchemaRefs:
                                        saveTargetDocument(_x, _f, _s))
        thread.daemon = True
        thread.start()
    else:
        if saveTargetFiling:
            targetFilename = os.path.basename(targetFilename)
            filingZip = zipfile.ZipFile(saveTargetFiling, 'w', zipfile.ZIP_DEFLATED, True)
            filingFiles = set()
            # copy referencedDocs to two levels
            def addRefDocs(doc):
                for refDoc in doc.referencesDocument.keys():
                    if refDoc.uri not in filingFiles:
                        filingFiles.add(refDoc.uri)
                        addRefDocs(refDoc)
            addRefDocs(modelDocument)
        else:
            filingZip = None
            filingFiles = None
        saveTargetDocument(modelDocument.modelXbrl, targetFilename, targetSchemaRefs, filingZip, filingFiles)
        if saveTargetFiling:
            instDir = os.path.dirname(modelDocument.uri)
            for refFile in filingFiles:
                if refFile.startswith(instDir):
                    filingZip.write(refFile, modelDocument.relativeUri(refFile))
            

def saveTargetDocumentCommandLineOptionExtender(parser):
    # extend command line options with a save DTS option
    parser.add_option("--saveInstance", 
                      action="store_true", 
                      dest="saveTargetInstance", 
                      help=_("Save target instance document"))
    parser.add_option("--saveinstance",  # for WEB SERVICE use
                      action="store", 
                      dest="saveTargetInstance", 
                      help=SUPPRESS_HELP)
    parser.add_option("--saveFiling", 
                      action="store", 
                      dest="saveTargetFiling", 
                      help=_("Save instance and DTS in zip"))
    parser.add_option("--savefiling",  # for WEB SERVICE use
                      action="store", 
                      dest="saveTargetFiling", 
                      help=SUPPRESS_HELP)

def saveTargetDocumentCommandLineXbrlRun(cntlr, options, modelXbrl, *args):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "saveTargetInstance", False) or getattr(options, "saveTargetFiling", False):
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None or not (   
            isinstance(cntlr.modelManager.modelXbrl.modelDocument, ModelInlineXbrlDocumentSet)
            or cntlr.modelManager.modelXbrl.modelDocument.type == Type.INLINEXBRL):
            cntlr.addToLog("No inline XBRL document or manifest loaded.")
            return
        runSaveTargetDocumentMenuCommand(cntlr, 
                                         runInBackground=False,
                                         saveTargetFiling=getattr(options, "saveTargetFiling", False))


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
