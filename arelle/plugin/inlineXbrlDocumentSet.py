'''
Inline XBRL Document Set plug-in.

Supports opening manifest file that identifies inline documents of a document set or an
Inline XBRL Document Set ("IXDS") identified by multiple files.

Saves extracted instance document for the ixdsTarget (if specified) or default target (if no ixdsTarget).

(Does not simultaneously load/extract multiple target instance documents in a document set.)

CmdLine allows --file '[{"ixds":[{"file":file1},{"file":file2}...]}]'
            
If there are non-default target documents, the target document identifier can be specified by ixdsTarget

    --file '[{"ixds":[{"file":file1},{"file":file2}...],"ixdsTarget":"xyz"}]' 
      
For GUI operation specify a formula parameter named ixdsTarget of type xs:string (in formula tools->formula parameters).

If a ixdsTarget parameter is absent or has a value of an empty string it is the default target document and matches
ix facts and resources with no @target attribute.

(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
from arelle import ModelXbrl, ValidateXbrlDimensions, XbrlConst
from arelle.PrototypeDtsObject import LocPrototype, ArcPrototype
from arelle.ModelInstanceObject import ModelInlineFootnote
from arelle.ModelObject import ModelObject
from arelle.ModelDocument import ModelDocument, ModelDocumentReference, Type, load, create, inlineIxdsDiscover
from arelle.PluginManager import pluginClassMethods
from arelle.UrlUtil import isHttpUrl
from arelle.ValidateFilingText import CDATApattern
from arelle.XmlUtil import addChild, copyIxFootnoteHtml, elementFragmentIdentifier, elementChildSequence
import os, zipfile
from optparse import SUPPRESS_HELP
from lxml.etree import XML, XMLSyntaxError
from collections import defaultdict

IXDS_SURROGATE = "_IXDS#?#" # surrogate (fake) file name for inline XBRL doc set (IXDS)
IXDS_DOC_SEPARATOR = "#?#" # the files of the document set follow the above "surrogate" with these separators

MINIMUM_IXDS_DOC_COUNT = 2 # make this 2 to cause single-documents to be processed without a document set object

skipExpectedInstanceComparison = None

# class representing surrogate object for multi-document inline xbrl document set, references individual ix documents
class ModelInlineXbrlDocumentSet(ModelDocument):
        
    def discoverInlineXbrlDocumentSet(self):
        # for JP FSA inline document set manifest, acting as document set surrogate entry object, load referenced ix documents
        for instanceElt in self.xmlRootElement.iter(tag="{http://disclosure.edinet-fsa.go.jp/2013/manifest}instance"):
            targetId = instanceElt.id
            self.targetDocumentId = targetId
            self.targetDocumentPreferredFilename = instanceElt.get('preferredFilename')
            self.targetDocumentSchemaRefs = set()  # union all the instance schemaRefs
            for ixbrlElt in instanceElt.iter(tag="{http://disclosure.edinet-fsa.go.jp/2013/manifest}ixbrl"):
                uri = ixbrlElt.textValue.strip()
                if uri:
                    # load ix document
                    doc = load(self.modelXbrl, uri, base=self.filepath, referringElement=instanceElt)
                    if doc is not None and doc not in self.referencesDocument:
                        # set reference to ix document if not in circular reference
                        referencedDocument = ModelDocumentReference("inlineDocument", instanceElt)
                        referencedDocument.targetId = targetId
                        self.referencesDocument[doc] = referencedDocument
                        for referencedDoc in doc.referencesDocument.keys():
                            if referencedDoc.type == Type.SCHEMA:
                                self.targetDocumentSchemaRefs.add(doc.relativeUri(referencedDoc.uri))
        return True

# this loader is used for test cases of multi-ix doc sets
def inlineXbrlDocumentSetLoader(modelXbrl, normalizedUri, filepath, isEntry=False, namespace=None, **kwargs):
    if isEntry:
        try:
            if "entrypoint" in kwargs:
                _target = kwargs["entrypoint"]["ixdsTarget"]
            else:
                _target = modelXbrl.modelManager.formulaOptions.parameterValues.get("ixdsTarget")[1]
        except (KeyError, AttributeError, IndexError, TypeError):
            _target = None
        modelXbrl.ixdsTarget = _target or None # None if an empty string specified
    if IXDS_SURROGATE in normalizedUri:
        # create surrogate entry object for inline document set which references ix documents
        xml = ["<instances>\n"]
        for i, url in enumerate(normalizedUri.split(IXDS_DOC_SEPARATOR)):
            if i == 0:
                docsetUrl = url
            else:
                xml.append("<instance>{}</instance>\n".format(url))
        xml.append("</instances>\n")
        ixdocset = create(modelXbrl, Type.INLINEXBRLDOCUMENTSET, docsetUrl, isEntry=True, initialXml="".join(xml))
        ixdocset.type = Type.INLINEXBRLDOCUMENTSET
        ixdocset.targetDocumentSchemaRefs = set()  # union all the instance schemaRefs
        _firstdoc = True
        for elt in ixdocset.xmlRootElement.iter(tag="instance"):
            # load ix document
            ixdoc = load(modelXbrl, elt.text, referringElement=elt)
            if ixdoc is not None and ixdoc.type == Type.INLINEXBRL:
                # set reference to ix document in document set surrogate object
                referencedDocument = ModelDocumentReference("inlineDocument", elt)
                ixdocset.referencesDocument[ixdoc] = referencedDocument
                for referencedDoc in ixdoc.referencesDocument.keys():
                    if referencedDoc.type == Type.SCHEMA:
                        ixdocset.targetDocumentSchemaRefs.add(ixdoc.relativeUri(referencedDoc.uri))
                ixdocset.ixNS = ixdoc.ixNS # set docset ixNS
                if _firstdoc:
                    _firstdoc = False
                    ixdocset.targetDocumentPreferredFilename = os.path.splitext(ixdoc.uri)[0] + ".xbrl"
                ixdoc.inDTS = True # behaves like an entry
        if hasattr(modelXbrl, "ixdsHtmlElements"): # has any inline root elements
            inlineIxdsDiscover(modelXbrl, ixdocset) # compile cross-document IXDS references
            return ixdocset
    return None

# baseXmlLang: set on root xbrli:xbrl element
# defaultXmlLang: if a fact/footnote has a different lang, provide xml:lang on it.
def createTargetInstance(modelXbrl, targetUrl, targetDocumentSchemaRefs, filingFiles, baseXmlLang=None, defaultXmlLang=None):
    targetInstance = ModelXbrl.create(modelXbrl.modelManager,
                                      newDocumentType=Type.INSTANCE,
                                      url=targetUrl,
                                      schemaRefs=targetDocumentSchemaRefs,
                                      isEntry=True,
                                      discover=False) # don't attempt to load DTS
    if baseXmlLang:
        targetInstance.modelDocument.xmlRootElement.set("{http://www.w3.org/XML/1998/namespace}lang", baseXmlLang)
        if defaultXmlLang is None:
            defaultXmlLang = baseXmlLang # allows facts/footnotes to override baseXmlLang
    ValidateXbrlDimensions.loadDimensionDefaults(targetInstance) # need dimension defaults 
    # roleRef and arcroleRef (of each inline document)
    for sourceRefs in (modelXbrl.targetRoleRefs, modelXbrl.targetArcroleRefs):
        for roleRefElt in sourceRefs.values():
            addChild(targetInstance.modelDocument.xmlRootElement, roleRefElt.qname,
                     attributes=roleRefElt.items())
    
    # contexts
    for context in sorted(modelXbrl.contexts.values(), key=lambda c: c.objectIndex): # contexts may come from multiple IXDS files
        ignore = targetInstance.createContext(context.entityIdentifier[0],
                                               context.entityIdentifier[1],
                                               'instant' if context.isInstantPeriod else
                                               'duration' if context.isStartEndPeriod
                                               else 'forever',
                                               context.startDatetime,
                                               context.endDatetime,
                                               None,
                                               context.qnameDims, [], [],
                                               id=context.id)
    for unit in sorted(modelXbrl.units.values(), key=lambda u: u.objectIndex): # units may come from multiple IXDS files
        measures = unit.measures
        ignore = targetInstance.createUnit(measures[0], measures[1], id=unit.id)

    modelXbrl.modelManager.showStatus(_("Creating and validating facts"))
    newFactForOldObjId = {}
    def createFacts(facts, parent):
        for fact in facts:
            if fact.isItem: # HF does not de-duplicate, which is currently-desired behavior
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
                    if fact.concept is not None and fact.concept.baseXsdType in ("string", "normalizedString"): # default
                        xmlLang = fact.xmlLang
                        if xmlLang is not None and xmlLang != defaultXmlLang:
                            attrs["{http://www.w3.org/XML/1998/namespace}lang"] = xmlLang
                newFact = targetInstance.createFact(fact.qname, attributes=attrs, text=text, parent=parent)
                # if fact.isFraction, create numerator and denominator
                newFactForOldObjId[fact.objectIndex] = newFact
                if filingFiles is not None and fact.concept is not None and fact.concept.isTextBlock:
                    # check for img and other filing references so that referenced files are included in the zip.
                    for xmltext in [text] + CDATApattern.findall(text):
                        try:
                            for elt in XML("<body>\n{0}\n</body>\n".format(xmltext)).iter():
                                addLocallyReferencedFile(elt, filingFiles)
                        except (XMLSyntaxError, UnicodeDecodeError):
                            pass  # TODO: Why ignore UnicodeDecodeError?
            elif fact.isTuple:
                newTuple = targetInstance.createFact(fact.qname, parent=parent)
                newFactForOldObjId[fact.objectIndex] = newTuple
                createFacts(fact.modelTupleFacts, newTuple)
                
    createFacts(modelXbrl.facts, None)
    modelXbrl.modelManager.showStatus(_("Creating and validating footnotes and relationships"))
    HREF = "{http://www.w3.org/1999/xlink}href"
    footnoteLinks = defaultdict(list)
    footnoteIdCount = {}
    for linkKey, linkPrototypes in modelXbrl.baseSets.items():
        arcrole, linkrole, linkqname, arcqname = linkKey
        if (linkrole and linkqname and arcqname and  # fully specified roles
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
                    xmlLang = linkChild.xmlLang
                    if xmlLang is not None and xmlLang != defaultXmlLang: # default
                        newChild.set("{http://www.w3.org/XML/1998/namespace}lang", xmlLang)
                    copyIxFootnoteHtml(linkChild, newChild, targetModelDocument=targetInstance.modelDocument, withText=True)

                    if filingFiles and linkChild.textValue:
                        footnoteHtml = XML("<body/>")
                        copyIxFootnoteHtml(linkChild, footnoteHtml)
                        for elt in footnoteHtml.iter():
                            addLocallyReferencedFile(elt,filingFiles)
    return targetInstance

def saveTargetDocument(modelXbrl, targetDocumentFilename, targetDocumentSchemaRefs, outputZip=None, filingFiles=None, *args, **kwargs):
    targetUrl = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(targetDocumentFilename, modelXbrl.modelDocument.filepath)
    def addLocallyReferencedFile(elt,filingFiles):
        if elt.tag in ("a", "img"):
            for attrTag, attrValue in elt.items():
                if attrTag in ("href", "src") and not isHttpUrl(attrValue) and not os.path.isabs(attrValue):
                    attrValue = attrValue.partition('#')[0] # remove anchor
                    if attrValue: # ignore anchor references to base document
                        attrValue = os.path.normpath(attrValue) # change url path separators to host separators
                        file = os.path.join(sourceDir,attrValue)
                        if modelXbrl.fileSource.isInArchive(file, checkExistence=True) or os.path.exists(file):
                            filingFiles.add(file)
    targetUrlParts = targetUrl.rpartition(".")
    targetUrl = targetUrlParts[0] + "_extracted." + targetUrlParts[2]
    modelXbrl.modelManager.showStatus(_("Extracting instance ") + os.path.basename(targetUrl))
    rootElt = modelXbrl.modelDocument.xmlRootElement
    # take baseXmlLang from <html> or <base>
    baseXmlLang = rootElt.get("{http://www.w3.org/XML/1998/namespace}lang") or rootElt.get("lang")
    for ixElt in modelXbrl.modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/1999/xhtml}body"):
        baseXmlLang = ixElt.get("{http://www.w3.org/XML/1998/namespace}lang") or rootElt.get("lang") or baseXmlLang
    targetInstance = createTargetInstance(modelXbrl, targetUrl, targetDocumentSchemaRefs, filingFiles, baseXmlLang) 
    targetInstance.saveInstance(overrideFilepath=targetUrl, outputZip=outputZip)
    if getattr(modelXbrl, "isTestcaseVariation", False):
        modelXbrl.extractedInlineInstance = True # for validation comparison
    modelXbrl.modelManager.showStatus(_("Saved extracted instance"), 5000)
    
def identifyInlineXbrlDocumentSet(modelXbrl, rootNode, filepath):
    for manifestElt in rootNode.iter(tag="{http://disclosure.edinet-fsa.go.jp/2013/manifest}manifest"):
        # it's an edinet fsa manifest of an inline XBRL document set
        return (Type.INLINEXBRLDOCUMENTSET, ModelInlineXbrlDocumentSet, manifestElt)
    return None # not a document set

def discoverInlineXbrlDocumentSet(modelDocument, *args, **kwargs):
    if isinstance(modelDocument, ModelInlineXbrlDocumentSet):
        return modelDocument.discoverInlineXbrlDocumentSet()        
    return False  # not discoverable by this plug-in

def fileOpenMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.insert_command(2, label="Open Inline Doc Set", 
                        underline=0, 
                        command=lambda: runOpenInlineDocumentSetMenuCommand(cntlr, runInBackground=True) )

def saveTargetDocumentMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save target document", 
                     underline=0, 
                     command=lambda: runSaveTargetDocumentMenuCommand(cntlr, runInBackground=True) )

def runOpenInlineDocumentSetMenuCommand(cntlr, runInBackground=False, saveTargetFiling=False):
    filenames = cntlr.uiFileDialog("open",
                                   multiple=True,
                                   title=_("arelle - Multi-open inline XBRL file(s)"),
                                   initialdir=cntlr.config.setdefault("fileOpenDir","."),
                                   filetypes=[(_("XBRL files"), "*.*")],
                                   defaultextension=".xbrl")
    if os.sep == "\\":
        filenames = [f.replace("/", "\\") for f in filenames]

    if not filenames:
        filename = ""
    elif len(filenames) >= MINIMUM_IXDS_DOC_COUNT:
        docsetSurrogatePath = os.path.join(os.path.dirname(filenames[0]), IXDS_SURROGATE)
        filename = docsetSurrogatePath + IXDS_DOC_SEPARATOR.join(filenames)
    else:
        filename = filenames[0]
    cntlr.fileOpenFile(filename)


def runSaveTargetDocumentMenuCommand(cntlr, runInBackground=False, saveTargetFiling=False):
    # skip if another class handles saving (e.g., EdgarRenderer)
    for pluginXbrlMethod in pluginClassMethods('InlineDocumentSet.SavesTargetInstance'):
        if pluginXbrlMethod():
            return # saving of target instance is handled by another class
    # save DTS menu item has been invoked
    if (cntlr.modelManager is None or 
        cntlr.modelManager.modelXbrl is None or 
        cntlr.modelManager.modelXbrl.modelDocument.type not in (Type.INLINEXBRL, Type.INLINEXBRLDOCUMENTSET)):
        cntlr.addToLog("No inline XBRL document set loaded.")
        return
    modelDocument = cntlr.modelManager.modelXbrl.modelDocument
    if modelDocument.type == Type.INLINEXBRLDOCUMENTSET:
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
            instDir = os.path.dirname(modelDocument.uri.split(IXDS_DOC_SEPARATOR)[0])
            for refFile in filingFiles:
                if refFile.startswith(instDir):
                    filingZip.write(refFile, modelDocument.relativeUri(refFile))
            

def commandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options with a save DTS option
    parser.add_option("--saveInstance", 
                      action="store_true", 
                      dest="saveTargetInstance", 
                      help=_("Save target instance document"))
    parser.add_option("--saveinstance",  # for WEB SERVICE use
                      action="store_true", 
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
    parser.add_option("--skipExpectedInstanceComparison", 
                      action="store_true", 
                      dest="skipExpectedInstanceComparison", 
                      help=_("Skip inline XBRL testcases from comparing expected result instances"))
       
def commandLineFilingStart(cntlr, options, filesource, entrypointFiles, *args, **kwargs):
    global skipExpectedInstanceComparison
    skipExpectedInstanceComparison = getattr(options, "skipExpectedInstanceComparison", False)
    if isinstance(entrypointFiles, list):
        # check for any inlineDocumentSet in list
        for entrypointFile in entrypointFiles:
            _ixds = entrypointFile.get("ixds") 
            if isinstance(_ixds, list):
                # build file surrogate for inline document set
                _files = [e["file"] for e in _ixds if isinstance(e, dict)]
                if len(_files) > 0:
                    docsetSurrogatePath = os.path.join(os.path.dirname(_files[0]), IXDS_SURROGATE)
                    entrypointFile["file"] = docsetSurrogatePath + IXDS_DOC_SEPARATOR.join(_files)
                    

def commandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # skip if another class handles saving (e.g., EdgarRenderer)
    for pluginXbrlMethod in pluginClassMethods('InlineDocumentSet.SavesTargetInstance'):
        if pluginXbrlMethod():
            return # saving of target instance is handled by another class
    # extend XBRL-loaded run processing for this option
    if getattr(options, "saveTargetInstance", False) or getattr(options, "saveTargetFiling", False):
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None or (   
            cntlr.modelManager.modelXbrl.modelDocument.type not in (Type.INLINEXBRL, Type.INLINEXBRLDOCUMENTSET)):
            cntlr.addToLog("No inline XBRL document or manifest loaded.")
            return
        runSaveTargetDocumentMenuCommand(cntlr, 
                                         runInBackground=False,
                                         saveTargetFiling=getattr(options, "saveTargetFiling", False))
        
def testcaseVariationReadMeFirstUris(modelTestcaseVariation):
    _readMeFirstUris = [os.path.join(modelTestcaseVariation.modelDocument.filepathdir, elt.text.strip())
                        for elt in modelTestcaseVariation.iterdescendants()
                        if isinstance(elt,ModelObject) and elt.get("readMeFirst") == "true"]
    if len(_readMeFirstUris) >= MINIMUM_IXDS_DOC_COUNT and all(
        Type.identify(modelTestcaseVariation.modelXbrl.fileSource, f) == Type.INLINEXBRL for f in _readMeFirstUris):
        docsetSurrogatePath = os.path.join(os.path.dirname(_readMeFirstUris[0]), IXDS_SURROGATE)
        modelTestcaseVariation._readMeFirstUris = [docsetSurrogatePath + IXDS_DOC_SEPARATOR.join(_readMeFirstUris)]
        return True

def testcaseVariationResultInstanceUri(modelTestcaseObject):
    if skipExpectedInstanceComparison:
        # block any comparison URIs
        return "" # block any testcase URIs
    return None # default behavior

def inlineDocsetUrlSeparator():
    return IXDS_DOC_SEPARATOR

__pluginInfo__ = {
    'name': 'Inline XBRL Document Set',
    'version': '1.1',
    'description': "This plug-in adds a feature to read manifest files of inline XBRL document sets "
                    " and to save the embedded XBRL instance document.  "
                    "Support single target instance documents in a single document set.  ",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2013 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'InlineDocumentSet.Url.Separator': inlineDocsetUrlSeparator,
    'InlineDocumentSet.CreateTargetInstance': createTargetInstance,
    'CntlrWinMain.Menu.File.Open': fileOpenMenuEntender,
    'CntlrWinMain.Menu.Tools': saveTargetDocumentMenuEntender,
    'CntlrCmdLine.Options': commandLineOptionExtender,
    'CntlrCmdLine.Filing.Start': commandLineFilingStart,
    'CntlrCmdLine.Xbrl.Run': commandLineXbrlRun,
    'ModelDocument.PullLoader': inlineXbrlDocumentSetLoader,
    'ModelDocument.IdentifyType': identifyInlineXbrlDocumentSet,
    'ModelDocument.Discover': discoverInlineXbrlDocumentSet,
    'ModelTestcaseVariation.ReadMeFirstUris': testcaseVariationReadMeFirstUris,
    'ModelTestcaseVariation.ResultXbrlInstanceUri': testcaseVariationResultInstanceUri,
}
