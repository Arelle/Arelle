"""
See COPYRIGHT.md for copyright information.

## Overview

The Inline XBRL Document Set (IXDS) plugin facilitates the handling of inline XBRL documents.
It allows for opening and extracting XBRL data from document sets, either defined as an Inline XBRL Document Set or in a
manifest file (such as JP FSA) that identifies inline XBRL documents.

## Key Features

- **XBRL Document Set Detection**: Detect and load iXBRL documents from a zip file or directory.
- **Target Document Selection**: Load one or more Target Documents from an Inline Document Set.
- **Extract XML Instance**: Extract and save XML Instance of a Target Document.
- **Command Line Support**: Detailed syntax for file and target selection.
- **GUI Interaction**: Selection dialog for loading inline documents and saving target documents.

## Usage Instructions

### Command Line Usage

- **Loading Inline XBRL Documents from a Zip File**:
  ```bash
  python arelleCmdLine.py --plugins inlineXbrlDocumentSet --file '[{"ixds": [{"file": "filing-documents.zip"}]}]'
  ```
  This command loads all inline XBRL documents within a zip file as an Inline XBRL Document Set.

- **Loading Inline XBRL Documents from a Directory**:
  ```bash
  python arelleCmdLine.py --plugins inlineXbrlDocumentSet --file '[{"ixds": [{"file": "filing-documents-directory"}]}]'
  ```
  This command loads all inline XBRL documents within a specified directory.

- **Loading with Default Target Document**:
  ```bash
  python arelleCmdLine.py --plugins inlineXbrlDocumentSet --file '[{"ixds": [{"file1": "document-1.html", "file2": "document-2.html"}]}]'
  ```
  Load two inline XBRL documents using the default Target Document.

- **Specifying a Different Target Document**:
  ```bash
  python arelleCmdLine.py --plugins inlineXbrlDocumentSet --file '[{"ixds": [{"file1": "document-1.html", "file2": "document-2.html"}], "ixdsTarget": "DKGAAP"}]'
  ```
  Load two inline XBRL documents using the `DKGAAP` Target Document.

- **Loading Multiple Document Sets**:
  ```bash
  python arelleCmdLine.py --plugins inlineXbrlDocumentSet --file '[{"ixds": [{"file": "filing-documents-1.zip"}]}, {"ixds": [{"file": "filing-documents-2.zip"}]}]'
  ```
  Load two separate Inline XBRL Document Sets.

- **Extracting and Saving XML Instance**:
  ```bash
  python arelleCmdLine.py --plugins inlineXbrlDocumentSet --file '[{"ixds": [{"file": "filing-documents.zip"}]}] --saveInstance'
  ```
  Extract and save the XML Instance of the default Target Document from an Inline XBRL Document Set.

### GUI Usage

- **Loading Inline Documents as an IXDS**:
  1. Navigate to the `File` menu.
  2. Select `Open File Inline Doc Set`.
  3. Command/Control select multiple files to load them as an Inline XBRL Document Set.

- **Extracting and Saving XML Instance**:
  1. Load the Inline XBRL Document Set.
  2. Navigate to `Tools` in the menu.
  3. Select `Save target document` to save the XML Instance.

## Additional Notes

- Windows users must escape quotes and backslashes within the JSON file parameter structure:
`.\\arelleCmdLine.exe --plugins inlineXbrlDocumentSet --file "[{""ixds"":[{""file"":""C:\\\\filing-documents.zip""}], ""ixdsTarget"":""DKGAAP""}]" --package "C:\\taxonomy-package.zip"`
- If a JSON structure is specified in the `--file` option without an `ixdsTarget`, the default target is assumed.
- To specify a non-default target in the absence of a JSON file argument, use the formula parameter `ixdsTarget`.
- For EDGAR style encoding of non-ASCII characters, use the `--encodeSavedXmlChars` argument.
- Extracted XML instance is saved to the same directory as the IXDS with the suffix `_extracted.xbrl`.
"""
from __future__ import annotations

from arelle import FileSource, ModelXbrl, ValidateXbrlDimensions, XbrlConst, ValidateDuplicateFacts
from arelle.RuntimeOptions import RuntimeOptions
from arelle.ValidateDuplicateFacts import DeduplicationType

DialogURL = None # dynamically imported when first used
from arelle.CntlrCmdLine import filesourceEntrypointFiles
from arelle.PrototypeDtsObject import LocPrototype, ArcPrototype
from arelle.FileSource import archiveFilenameParts, archiveFilenameSuffixes
from arelle.ModelInstanceObject import ModelInlineFootnote
from arelle.ModelObject import ModelObject
from arelle.ModelDocument import ModelDocument, ModelDocumentReference, Type, load, create, inlineIxdsDiscover
from arelle.ModelValue import INVALIDixVALUE, qname
from arelle.PluginManager import pluginClassMethods
from arelle.PythonUtil import attrdict
from arelle.UrlUtil import isHttpUrl
from arelle.ValidateFilingText import CDATApattern
from arelle.Version import authorLabel, copyrightLabel
from arelle.XmlUtil import addChild, copyIxFootnoteHtml, elementFragmentIdentifier, elementChildSequence, xmlnsprefix, setXmlns
from arelle.XmlValidate import validate as xmlValidate, VALID
import os, zipfile
import regex as re
from optparse import SUPPRESS_HELP
from lxml.etree import XML, XMLSyntaxError
from collections import defaultdict

DEFAULT_TARGET = "(default)"
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
                        self.ixNS = doc.ixNS
        return True

def loadDTS(modelXbrl, modelIxdsDocument):
    for htmlElt in modelXbrl.ixdsHtmlElements:
        for ixRefElt in htmlElt.iterdescendants(tag=htmlElt.modelDocument.ixNStag + "references"):
            if ixRefElt.get("target") == modelXbrl.ixdsTarget:
                modelIxdsDocument.schemaLinkbaseRefsDiscover(ixRefElt)
                xmlValidate(modelXbrl, ixRefElt) # validate instance elements

# this loader is used for test cases of multi-ix doc sets
def inlineXbrlDocumentSetLoader(modelXbrl, normalizedUri, filepath, isEntry=False, namespace=None, **kwargs):
    if isEntry:
        try:
            if "entrypoint" in kwargs and "ixdsTarget" in kwargs["entrypoint"]:
                _target = kwargs["entrypoint"].get("ixdsTarget") # assume None if not specified in entrypoint
            elif "ixdsTarget" in kwargs: # passed from validate (multio test cases)
                _target = kwargs["ixdsTarget"]
            else:
                _target = modelXbrl.modelManager.formulaOptions.parameterValues["ixdsTarget"][1]
            modelXbrl.ixdsTarget = None if _target == DEFAULT_TARGET else _target or None
        except (KeyError, AttributeError, IndexError, TypeError):
            pass # set later in selectTargetDocument plugin method
    createIxdsDocset = False
    ixdocs = None
    if "ixdsHtmlElements" in kwargs: # loading supplemental modelXbrl with preloaded htmlElements
        createIxdsDocset = True
        ixdocs = []
        modelXbrl.ixdsDocUrls = []
        modelXbrl.ixdsHtmlElements = kwargs["ixdsHtmlElements"]
        for ixdsHtmlElement in modelXbrl.ixdsHtmlElements:
            modelDocument = ixdsHtmlElement.modelDocument
            ixdocs.append(modelDocument)
            modelXbrl.ixdsDocUrls.append(modelDocument.uri)
            modelXbrl.urlDocs[modelDocument.uri] = modelDocument
        docsetUrl = modelXbrl.uriDir + "/_IXDS"
    elif IXDS_SURROGATE in normalizedUri:
        createIxdsDocset = True
        modelXbrl.ixdsDocUrls = []
        schemeFixup = isHttpUrl(normalizedUri) # schemes after separator have // normalized to single /
        msUNCfixup = modelXbrl.modelManager.cntlr.isMSW and normalizedUri.startswith("\\\\") # path starts with double backslash \\
        if schemeFixup:
            defectiveScheme = normalizedUri.partition("://")[0] + ":/"
            fixupPosition = len(defectiveScheme)
        for i, url in enumerate(normalizedUri.split(IXDS_DOC_SEPARATOR)):
            if schemeFixup and url.startswith(defectiveScheme) and url[len(defectiveScheme)] != "/":
                url = url[:fixupPosition] + "/" + url[fixupPosition:]
            if i == 0:
                docsetUrl = url
            else:
                if msUNCfixup and not url.startswith("\\\\") and url.startswith("\\"):
                    url = "\\" + url
                modelXbrl.ixdsDocUrls.append(url)
    if createIxdsDocset:
        # create surrogate entry object for inline document set which references ix documents
        xml = ["<instances>\n"]
        for url in modelXbrl.ixdsDocUrls:
            xml.append("<instance>{}</instance>\n".format(url))
        xml.append("</instances>\n")
        ixdocset = create(modelXbrl, Type.INLINEXBRLDOCUMENTSET, docsetUrl, isEntry=True, initialXml="".join(xml))
        ixdocset.type = Type.INLINEXBRLDOCUMENTSET
        ixdocset.targetDocumentPreferredFilename = None # possibly no inline docs in this doc set
        for i, elt in enumerate(ixdocset.xmlRootElement.iter(tag="instance")):
            # load ix document
            if ixdocs:
                ixdoc = ixdocs[i]
            else:
                ixdoc = load(modelXbrl, elt.text, referringElement=elt, isDiscovered=True)
            if ixdoc is not None:
                if ixdoc.type == Type.INLINEXBRL:
                    # set reference to ix document in document set surrogate object
                    referencedDocument = ModelDocumentReference("inlineDocument", elt)
                    ixdocset.referencesDocument[ixdoc] = referencedDocument
                    ixdocset.ixNS = ixdoc.ixNS # set docset ixNS
                    if ixdocset.targetDocumentPreferredFilename is None:
                        ixdocset.targetDocumentPreferredFilename = os.path.splitext(ixdoc.uri)[0] + ".xbrl"
                    ixdoc.inDTS = True # behaves like an entry
                else:
                    modelXbrl.warning("arelle:nonIxdsDocument",
                                      _("Non-inline file is not loadable into an Inline XBRL Document Set."),
                                      modelObject=ixdoc)
        # correct uriDir to remove surrogate suffix
        if IXDS_SURROGATE in modelXbrl.uriDir:
            modelXbrl.uriDir = os.path.dirname(modelXbrl.uriDir.partition(IXDS_SURROGATE)[0])
        if hasattr(modelXbrl, "ixdsHtmlElements"): # has any inline root elements
            if ixdocs:
                loadDTS(modelXbrl, ixdocset)
                modelXbrl.isSupplementalIxdsTarget = True
            inlineIxdsDiscover(modelXbrl, ixdocset, bool(ixdocs)) # compile cross-document IXDS references
            return ixdocset
    return None

# baseXmlLang: set on root xbrli:xbrl element
# defaultXmlLang: if a fact/footnote has a different lang, provide xml:lang on it.
def createTargetInstance(
        modelXbrl,
        targetUrl,
        targetDocumentSchemaRefs,
        filingFiles,
        baseXmlLang=None,
        defaultXmlLang=None,
        skipInvalid=False,
        xbrliNamespacePrefix=None,
        deduplicationType: ValidateDuplicateFacts.DeduplicationType | None = None):
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
    targetInstance = ModelXbrl.create(modelXbrl.modelManager,
                                      newDocumentType=Type.INSTANCE,
                                      url=targetUrl,
                                      schemaRefs=targetDocumentSchemaRefs,
                                      isEntry=True,
                                      discover=False,  # don't attempt to load DTS
                                      xbrliNamespacePrefix=xbrliNamespacePrefix)
    ixTargetRootElt = modelXbrl.ixTargetRootElements[getattr(modelXbrl, "ixdsTarget", None)]
    langIsSet = False
    # copy ix resources target root attributes
    for attrName, attrValue in ixTargetRootElt.items():
        if attrName != "target": # ix:references target is not mapped to xbrli:xbrl
            targetInstance.modelDocument.xmlRootElement.set(attrName, attrValue)
        if attrName == "{http://www.w3.org/XML/1998/namespace}lang":
            langIsSet = True
            defaultXmlLang = attrValue
        if attrName.startswith("{"):
            ns, _sep, ln = attrName[1:].rpartition("}")
            if ns:
                prefix = xmlnsprefix(ixTargetRootElt, ns)
                if prefix not in (None, "xml"):
                    setXmlns(targetInstance.modelDocument, prefix, ns)

    if not langIsSet and baseXmlLang:
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
    invalidFacts = []
    duplicateFacts = frozenset()
    if deduplicationType is not None:
        modelXbrl.modelManager.showStatus(_("Deduplicating facts"))
        deduplicatedFacts = frozenset(ValidateDuplicateFacts.getDeduplicatedFacts(modelXbrl, deduplicationType))
        duplicateFacts = frozenset(f for f in modelXbrl.facts if f not in deduplicatedFacts)

    def createFacts(facts, parent):
        for fact in facts:
            if fact in duplicateFacts:
                ValidateDuplicateFacts.logDeduplicatedFact(modelXbrl, fact)
                continue
            if fact.xValid < VALID and skipInvalid:
                invalidFacts.append(fact)
            elif fact.isItem: # HF does not de-duplicate, which is currently-desired behavior
                modelConcept = fact.concept # isItem ensures concept is not None
                attrs = {"contextRef": fact.contextID}
                if fact.id:
                    attrs["id"] = fact.id
                if fact.isNumeric:
                    if fact.unitID:
                        attrs["unitRef"] = fact.unitID
                    if fact.get("decimals"):
                        attrs["decimals"] = fact.get("decimals")
                    if fact.get("precision"):
                        attrs["precision"] = fact.get("precision")
                if fact.isNil:
                    attrs[XbrlConst.qnXsiNil] = "true"
                    text = None
                elif ( not(modelConcept.baseXsdType == "token" and modelConcept.isEnumeration)
                       and fact.xValid >= VALID ):
                    text = fact.xValue
                # may need a special case for QNames (especially if prefixes defined below root)
                else:
                    text = fact.rawValue if fact.textValue == INVALIDixVALUE else fact.textValue
                for attrName, attrValue in fact.items():
                    if attrName.startswith("{"):
                        attrs[qname(attrName,fact.nsmap)] = attrValue # using qname allows setting prefix in extracted instance
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
                attrs = {}
                if fact.id:
                    attrs["id"] = fact.id
                if fact.isNil:
                    attrs[XbrlConst.qnXsiNil] = "true"
                for attrName, attrValue in fact.items():
                    if attrName.startswith("{"):
                        attrs[qname(attrName,fact.nsmap)] = attrValue
                newTuple = targetInstance.createFact(fact.qname, attributes=attrs, parent=parent)
                newFactForOldObjId[fact.objectIndex] = newTuple
                createFacts(fact.modelTupleFacts, newTuple)

    createFacts(modelXbrl.facts, None)
    if invalidFacts:
        modelXbrl.warning("arelle.invalidFactsSkipped",
                          _("Skipping %(count)s invalid facts in saving extracted instance document."),
                          modelObject=invalidFacts, count=len(invalidFacts))
        del invalidFacts[:] # dereference
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

def saveTargetDocument(
        modelXbrl,
        targetDocumentFilename,
        targetDocumentSchemaRefs,
        outputZip=None,
        filingFiles=None,
        xbrliNamespacePrefix=None,
        deduplicationType: DeduplicationType | None = None,
        *args, **kwargs):
    targetUrl = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(targetDocumentFilename, modelXbrl.modelDocument.filepath)
    targetUrlParts = targetUrl.rpartition(".")
    targetUrl = targetUrlParts[0] + "_extracted." + targetUrlParts[2]
    modelXbrl.modelManager.showStatus(_("Extracting instance ") + os.path.basename(targetUrl))
    htmlRootElt = modelXbrl.modelDocument.xmlRootElement
    # take baseXmlLang from <html> or <base>
    baseXmlLang = htmlRootElt.get("{http://www.w3.org/XML/1998/namespace}lang") or htmlRootElt.get("lang")
    for ixElt in modelXbrl.modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/1999/xhtml}body"):
        baseXmlLang = ixElt.get("{http://www.w3.org/XML/1998/namespace}lang") or htmlRootElt.get("lang") or baseXmlLang
    targetInstance = createTargetInstance(
        modelXbrl, targetUrl, targetDocumentSchemaRefs, filingFiles, baseXmlLang,
        xbrliNamespacePrefix=xbrliNamespacePrefix, deduplicationType=deduplicationType,
    )
    targetInstance.saveInstance(overrideFilepath=targetUrl, outputZip=outputZip, xmlcharrefreplace=kwargs.get("encodeSavedXmlChars", False))
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
    # install DialogURL for GUI menu operation of runOpenWebInlineDocumentSetMenuCommand
    global DialogURL
    from arelle import DialogURL
    # Extend menu with an item for the savedts plugin
    menu.insert_command(2, label="Open Web Inline Doc Set",
                        underline=0,
                        command=lambda: runOpenWebInlineDocumentSetMenuCommand(cntlr, runInBackground=True) )
    menu.insert_command(2, label="Open File Inline Doc Set",
                        underline=0,
                        command=lambda: runOpenFileInlineDocumentSetMenuCommand(cntlr, runInBackground=True) )

def saveTargetDocumentMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save target document",
                     underline=0,
                     command=lambda: runSaveTargetDocumentMenuCommand(cntlr, runInBackground=True) )

def runOpenFileInlineDocumentSetMenuCommand(cntlr, runInBackground=False, saveTargetFiling=False):
    filenames = cntlr.uiFileDialog("open",
                                   multiple=True,
                                   title=_("arelle - Multi-open inline XBRL file(s)"),
                                   initialdir=cntlr.config.setdefault("fileOpenDir","."),
                                   filetypes=[(_("XBRL files"), "*.*")],
                                   defaultextension=".xbrl")
    runOpenInlineDocumentSetMenuCommand(cntlr, filenames, runInBackground, saveTargetFiling)

def runOpenWebInlineDocumentSetMenuCommand(cntlr, runInBackground=False, saveTargetFiling=False):
    url = DialogURL.askURL(cntlr.parent, buttonSEC=True, buttonRSS=True)
    if url:
        runOpenInlineDocumentSetMenuCommand(cntlr, re.split(r",\s*|\s+", url), runInBackground, saveTargetFiling)

def runOpenInlineDocumentSetMenuCommand(cntlr, filenames, runInBackground=False, saveTargetFiling=False):
    if os.sep == "\\":
        filenames = [f.replace("/", "\\") for f in filenames]

    if not filenames:
        filename = ""
    elif len(filenames) == 1 and any(filenames[0].endswith(s) for s in archiveFilenameSuffixes):
        # get archive file names
        from arelle.FileSource import openFileSource
        filesource = openFileSource(filenames[0], cntlr)
        if filesource.isArchive:
            # identify entrypoint files
            try:
                entrypointFiles = filesourceEntrypointFiles(filesource, inlineOnly=True)
                l = len(filesource.baseurl) + 1 # len of the base URL of the archive
                selectFiles = [e["file"][l:] for e in entrypointFiles if "file" in e] + \
                              [e["file"][l:] for i in entrypointFiles if "ixds" in i for e in i["ixds"] if "file" in e]
            except FileSource.ArchiveFileIOError:
                selectFiles = None
            from arelle import DialogOpenArchive
            archiveEntries = DialogOpenArchive.askArchiveFile(cntlr, filesource, multiselect=True, selectFiles=selectFiles)
            if archiveEntries:
                ixdsFirstFile = archiveEntries[0]
                _archiveFilenameParts = archiveFilenameParts(ixdsFirstFile)
                if _archiveFilenameParts is not None:
                    ixdsDir = _archiveFilenameParts[0] # it's a zip or package, use zip file name as head of ixds
                else:
                    ixdsDir = os.path.dirname(ixdsFirstFile)
                docsetSurrogatePath = os.path.join(ixdsDir, IXDS_SURROGATE)
                filename = docsetSurrogatePath + IXDS_DOC_SEPARATOR.join(archiveEntries)
            else:
                filename = None
        else:
            filename = None
        filesource.close()
    elif len(filenames) >= MINIMUM_IXDS_DOC_COUNT:
        ixdsFirstFile = filenames[0]
        _archiveFilenameParts = archiveFilenameParts(ixdsFirstFile)
        if _archiveFilenameParts is not None:
            ixdsDir = _archiveFilenameParts[0] # it's a zip or package, use zip file name as head of ixds
        else:
            ixdsDir = os.path.dirname(ixdsFirstFile)
        docsetSurrogatePath = os.path.join(ixdsDir, IXDS_SURROGATE)
        filename = docsetSurrogatePath + IXDS_DOC_SEPARATOR.join(filenames)
    else:
        filename = filenames[0]
    if filename is not None:
        cntlr.fileOpenFile(filename)


def runSaveTargetDocumentMenuCommand(
        cntlr,
        runInBackground=False,
        saveTargetFiling=False,
        encodeSavedXmlChars=False,
        xbrliNamespacePrefix=None,
        deduplicationType: DeduplicationType | None = None):
    # skip if another class handles saving (e.g., EdgarRenderer)
    if saveTargetInstanceOverriden(deduplicationType):
        return
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
        if targetFilename is None:
            cntlr.addToLog("No inline XBRL document in the inline XBRL document set.")
            return
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
                                        saveTargetDocument(_x, _f, _s, deduplicationType=deduplicationType))
        thread.daemon = True
        thread.start()
    else:
        if saveTargetFiling:
            filingZip = zipfile.ZipFile(os.path.splitext(targetFilename)[0] + ".zip", 'w', zipfile.ZIP_DEFLATED, True)
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
        saveTargetDocument(modelDocument.modelXbrl, targetFilename, targetSchemaRefs, filingZip, filingFiles,
                           encodeSavedXmlChars=encodeSavedXmlChars, xbrliNamespacePrefix=xbrliNamespacePrefix,
                           deduplicationType=deduplicationType)
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
    parser.add_option("--encodeSavedXmlChars",
                      action="store_true",
                      dest="encodeSavedXmlChars",
                      help=_("Encode saved xml characters (&#x80; and above)"))
    parser.add_option("--encodesavedxmlchars",  # for WEB SERVICE use
                      action="store_true",
                      dest="encodeSavedXmlChars",
                      help=SUPPRESS_HELP)
    parser.add_option("--xbrliNamespacePrefix",
                      action="store",
                      dest="xbrliNamespacePrefix",
                      help=_("The namespace prefix to use for http://www.xbrl.org/2003/instance. It's used as the default namespace when unset."),
                      type="string")
    parser.add_option("--xbrlinamespaceprefix",  # for WEB SERVICE use
                      action="store",
                      dest="xbrliNamespacePrefix",
                      help=SUPPRESS_HELP,
                      type="string")
    parser.add_option("--deduplicateIxbrlFacts",
                      action="store",
                      choices=[a.value for a in ValidateDuplicateFacts.DeduplicationType],
                      dest="deduplicateIxbrlFacts",
                      help=_("Remove duplicate facts when extracting XBRL instance."))
    parser.add_option("--deduplicateixbrlfacts",  # for WEB SERVICE use
                      action="store",
                      choices=[a.value for a in ValidateDuplicateFacts.DeduplicationType],
                      dest="deduplicateIxbrlFacts",
                      help=SUPPRESS_HELP)

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
                if len(_files) == 1:
                    urlsByType = {}
                    if os.path.isfile(_files[0]) and any(_files[0].endswith(e) for e in (".zip", ".ZIP", ".tar.gz" )): # check if an archive file
                        filesource = FileSource.openFileSource(_files[0], cntlr)
                        if filesource.isArchive:
                            for _archiveFile in (filesource.dir or ()): # .dir might be none if IOerror
                                filesource.select(_archiveFile)
                                identifiedType = Type.identify(filesource, filesource.url)
                                if identifiedType in (Type.INSTANCE, Type.INLINEXBRL):
                                    urlsByType.setdefault(identifiedType, []).append(filesource.url)
                        filesource.close()
                    elif os.path.isdir(_files[0]):
                        _fileDir = _files[0]
                        for _localName in os.listdir(_fileDir):
                            _file = os.path.join(_fileDir, _localName)
                            if os.path.isfile(_file):
                                filesource = FileSource.openFileSource(_file, cntlr)
                                identifiedType = Type.identify(filesource, filesource.url)
                                if identifiedType in (Type.INSTANCE, Type.INLINEXBRL):
                                    urlsByType.setdefault(identifiedType, []).append(filesource.url)
                                filesource.close()
                    if urlsByType:
                        _files = []
                        # use inline instances, if any, else non-inline instances
                        for identifiedType in (Type.INLINEXBRL, Type.INSTANCE):
                            for url in urlsByType.get(identifiedType, []):
                                _files.append(url)
                            if _files:
                                break # found inline (or non-inline) entrypoint files, don't look for any other type
                if len(_files) > 0:
                    docsetSurrogatePath = os.path.join(os.path.dirname(_files[0]), IXDS_SURROGATE)
                    entrypointFile["file"] = docsetSurrogatePath + IXDS_DOC_SEPARATOR.join(_files)


def saveTargetInstanceOverriden(deduplicationType: DeduplicationType | None) -> bool:
    """
    Checks if another plugin implements instance extraction, and throws an exception
    if the provided arguments are not compatible.
    :param deduplicationType: The deduplication type to be used, if set.
    :return: True if instance extraction is overridden by another plugin.
    """
    for pluginXbrlMethod in pluginClassMethods('InlineDocumentSet.SavesTargetInstance'):
        if pluginXbrlMethod():
            if deduplicationType is not None:
                raise RuntimeError(_('Deduplication is enabled but could not be performed because instance '
                                   'extraction was performed by another plugin.'))
            return True
    return False


def commandLineXbrlRun(cntlr, options: RuntimeOptions, modelXbrl, *args, **kwargs):
    deduplicationTypeArg = getattr(options, "deduplicateIxbrlFacts", None)
    deduplicationType = None if deduplicationTypeArg is None else DeduplicationType(deduplicationTypeArg)
    # skip if another class handles saving (e.g., EdgarRenderer)
    if saveTargetInstanceOverriden(deduplicationType):
        return
    # extend XBRL-loaded run processing for this option
    if getattr(options, "saveTargetInstance", False) or getattr(options, "saveTargetFiling", False):
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None or (
            cntlr.modelManager.modelXbrl.modelDocument.type not in (Type.INLINEXBRL, Type.INLINEXBRLDOCUMENTSET)):
            cntlr.addToLog("No inline XBRL document or manifest loaded.")
            return
        runSaveTargetDocumentMenuCommand(cntlr,
                                         runInBackground=False,
                                         saveTargetFiling=getattr(options, "saveTargetFiling", False),
                                         encodeSavedXmlChars=getattr(options, "encodeSavedXmlChars", False),
                                         xbrliNamespacePrefix=getattr(options, "xbrliNamespacePrefix"),
                                         deduplicationType=deduplicationType)

def testcaseVariationReadMeFirstUris(modelTestcaseVariation):
    _readMeFirstUris = [os.path.join(modelTestcaseVariation.modelDocument.filepathdir,
                                     (elt.get("{http://www.w3.org/1999/xlink}href") or elt.text).strip())
                        for elt in modelTestcaseVariation.iterdescendants()
                        if isinstance(elt,ModelObject) and elt.get("readMeFirst") == "true"]
    if len(_readMeFirstUris) >= MINIMUM_IXDS_DOC_COUNT and all(
        Type.identify(modelTestcaseVariation.modelXbrl.fileSource, f) == Type.INLINEXBRL for f in _readMeFirstUris):
        docsetSurrogatePath = os.path.join(os.path.dirname(_readMeFirstUris[0]), IXDS_SURROGATE)
        modelTestcaseVariation._readMeFirstUris = [docsetSurrogatePath + IXDS_DOC_SEPARATOR.join(_readMeFirstUris)]
        return True

def testcaseVariationReportPackageIxds(filesource, lookOutsideReportsDirectory=False, combineIntoSingleIxds=False):
    # single report directory
    reportFiles = []
    ixdsDirFiles = defaultdict(list)
    reportDir = "*uninitialized*"
    reportDirLen = 0
    for f in filesource.dir:
        if f.endswith("/reports/") and reportDir == "*uninitialized*":
            reportDir = f
            reportDirLen = len(f)
        elif f.startswith(reportDir):
            if "/" not in f[reportDirLen:]:
                filesource.select(f)
                if Type.identify(filesource, filesource.url) in (Type.INSTANCE, Type.INLINEXBRL):
                    reportFiles.append(f)
            else:
                ixdsDir, _sep, ixdsFile = f.rpartition("/")
                if ixdsFile:
                    filesource.select(f)
                    if Type.identify(filesource, filesource.url) == Type.INLINEXBRL:
                        ixdsDirFiles[ixdsDir].append(f)
    if lookOutsideReportsDirectory:
        for f in filesource.dir:
            filesource.select(f)
            if Type.identify(filesource, filesource.url) in (Type.INSTANCE, Type.INLINEXBRL):
                reportFiles.append(f)
    if combineIntoSingleIxds and (reportFiles or len(ixdsDirFiles) > 1):
        docsetSurrogatePath = os.path.join(filesource.baseurl, IXDS_SURROGATE)
        for ixdsFiles in ixdsDirFiles.values():
            reportFiles.extend(ixdsFiles)
        return docsetSurrogatePath + IXDS_DOC_SEPARATOR.join(os.path.join(filesource.baseurl,f) for f in reportFiles)
    for ixdsDir, ixdsFiles in sorted(ixdsDirFiles.items()):
        # use the first ixds in report package
        docsetSurrogatePath = os.path.join(filesource.baseurl, ixdsDir, IXDS_SURROGATE)
        return docsetSurrogatePath + IXDS_DOC_SEPARATOR.join(os.path.join(filesource.baseurl,f) for f in ixdsFiles)
    for f in reportFiles:
        filesource.select(f)
        if Type.identify(filesource, filesource.url) in (Type.INSTANCE, Type.INLINEXBRL):
            # return the first inline doc
            return f
    return None


def testcaseVariationResultInstanceUri(modelTestcaseObject):
    if skipExpectedInstanceComparison:
        # block any comparison URIs
        return "" # block any testcase URIs
    return None # default behavior

def testcaseVariationArchiveIxds(val, filesource, entrypointFiles):
    commandLineFilingStart(val.modelXbrl.modelManager.cntlr,
                           attrdict(skipExpectedInstanceComparison=True),
                           filesource, entrypointFiles)


def inlineDocsetDiscovery(filesource, entrypointFiles): # [{"file":"url1"}, ...]
    if len(entrypointFiles): # return [{"ixds":[{"file":"url1"}, ...]}]
        # replace contents of entrypointFiles (array object), don't return a new object
        _entrypointFiles = entrypointFiles.copy()
        del entrypointFiles[:]
        entrypointFiles.append( {"ixds": _entrypointFiles} )

def inlineDocsetUrlSeparator():
    return IXDS_DOC_SEPARATOR

def discoverIxdsDts(modelXbrl):
    return hasattr(modelXbrl, "ixdsTarget") # if no target specified, block ixds discovery until all IX docs are loaded

class TargetChoiceDialog:
    def __init__(self,parent, choices):
        from tkinter import Toplevel, Label, Listbox, StringVar
        parentGeometry = re.match(r"(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))
        self.parent = parent
        self.t = Toplevel()
        self.t.transient(self.parent)
        self.t.geometry("+{0}+{1}".format(dialogX+200,dialogY+200))
        self.t.title(_("Select Target"))
        self.selection = choices[0] # default choice in case dialog is closed without selecting an entry
        self.lb = Listbox(self.t, height=10, width=30, listvariable=StringVar(value=choices))
        self.lb.grid(row=0, column=0)
        self.lb.focus_set()
        self.lb.bind("<<ListboxSelect>>", self.select)
        self.t.grab_set()
        self.t.wait_window(self.t)

    def select(self,event):
        self.parent.focus_set()
        self.selection = self.lb.selection_get()
        self.t.destroy()

def ixdsTargets(ixdsHtmlElements):
    return sorted(set(elt.get("target", DEFAULT_TARGET)
                              for htmlElt in ixdsHtmlElements
                              for elt in htmlElt.iterfind(f".//{{{htmlElt.modelDocument.ixNS}}}references")))

def selectTargetDocument(modelXbrl, modelIxdsDocument):
    if not hasattr(modelXbrl, "ixdsTarget"): # DTS discoverey deferred until all ix docs loaded
        # isolate any documents to separate IXDSes according to authority submission rules
        modelXbrl.targetIXDSesToLoad = [] # [[target,[ixdsHtmlElements], ...]
        for pluginXbrlMethod in pluginClassMethods('InlineDocumentSet.IsolateSeparateIXDSes'):
            separateIXDSesHtmlElements = pluginXbrlMethod(modelXbrl)
            if len(separateIXDSesHtmlElements) > 1: # [[ixdsHtml1, ixdsHtml2], [ixdsHtml3...] ...]
                for separateIXDSHtmlElements in separateIXDSesHtmlElements[1:]:
                    toLoadIXDS = [ixdsTargets(separateIXDSHtmlElements),[]]
                    modelXbrl.targetIXDSesToLoad.append(toLoadIXDS)
                    for ixdsHtmlElement in separateIXDSHtmlElements:
                        modelDoc = ixdsHtmlElement.modelDocument
                        toLoadIXDS[1].append(ixdsHtmlElement)
                        modelXbrl.ixdsHtmlElements.remove(ixdsHtmlElement)
                        del modelXbrl.urlDocs[modelDoc.uri]
                        if modelDoc in modelIxdsDocument.referencesDocument:
                            del modelIxdsDocument.referencesDocument[modelDoc]
                # the primary target  instance may have changed
                modelIxdsDocument.targetDocumentPreferredFilename = os.path.splitext(modelXbrl.ixdsHtmlElements[0].modelDocument.uri)[0] + ".xbrl"
        # find target attributes
        _targets = ixdsTargets(modelXbrl.ixdsHtmlElements)
        if len(_targets) == 0:
            _target = DEFAULT_TARGET
        elif len(_targets) == 1:
            _target = _targets[0]
        elif modelXbrl.modelManager.cntlr.hasGui:
            if True: # provide option to load all or ask user which target
                modelXbrl.targetIXDSesToLoad.insert(0, [_targets[1:],modelXbrl.ixdsHtmlElements])
                _target = _targets[0]
            else: # ask user which target
                dlg = TargetChoiceDialog(modelXbrl.modelManager.cntlr.parent, _targets)
                _target = dlg.selection
        else:
            # load all targets (supplemental are accessed from first via modelXbrl.loadedModelXbrls)
            modelXbrl.targetIXDSesToLoad.insert(0, [_targets[1:],modelXbrl.ixdsHtmlElements])
            _target = _targets[0]
            #modelXbrl.warning("arelle:unspecifiedTargetDocument",
            #                  _("Target document not specified, loading %(target)s, found targets %(targets)s"),
            #                  modelObject=modelXbrl, target=_target, targets=_targets)
        modelXbrl.ixdsTarget = None if _target == DEFAULT_TARGET else _target or None
        # load referenced schemas and linkbases (before validating inline HTML
        loadDTS(modelXbrl, modelIxdsDocument)
    # now that all ixds doc(s) references loaded, validate resource elements
    for htmlElt in modelXbrl.ixdsHtmlElements:
        for inlineElement in htmlElt.iterdescendants(tag=htmlElt.modelDocument.ixNStag + "resources"):
            xmlValidate(modelXbrl, inlineElement) # validate instance elements

def ixdsTargetDiscoveryCompleted(modelXbrl, modelIxdsDocument):
    targetIXDSesToLoad = getattr(modelXbrl, "targetIXDSesToLoad", False)
    if targetIXDSesToLoad:
        # load and discover additional targets
        modelXbrl.supplementalModelXbrls = []
        for targets, ixdsHtmlElements in targetIXDSesToLoad:
            for target in targets:
                modelXbrl.supplementalModelXbrls.append(
                    ModelXbrl.load(modelXbrl.modelManager, ixdsHtmlElements[0].modelDocument.uri,
                                   f"loading secondary target {target} {ixdsHtmlElements[0].modelDocument.uri}",
                                   useFileSource=modelXbrl.fileSource, ixdsTarget=target, ixdsHtmlElements=ixdsHtmlElements)
                )
        modelXbrl.modelManager.loadedModelXbrls.extend(modelXbrl.supplementalModelXbrls)
    # provide schema references for IXDS document
    modelIxdsDocument.targetDocumentSchemaRefs = set()  # union all the instance schemaRefs
    for referencedDoc in modelIxdsDocument.referencesDocument.keys():
        if referencedDoc.type == Type.SCHEMA:
            modelIxdsDocument.targetDocumentSchemaRefs.add(modelIxdsDocument.relativeUri(referencedDoc.uri))

__pluginInfo__ = {
    'name': 'Inline XBRL Document Set',
    'version': '1.1',
    'description': "This plug-in adds a feature to read manifest files of inline XBRL document sets "
                    " and to save the embedded XBRL instance document.  "
                    "Support single target instance documents in a single document set.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'InlineDocumentSet.Discovery': inlineDocsetDiscovery,
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
    'ModelDocument.DiscoverIxdsDts': discoverIxdsDts,
    'ModelDocument.SelectIxdsTarget': selectTargetDocument,
    'ModelDocument.IxdsTargetDiscovered': ixdsTargetDiscoveryCompleted,
    'ModelTestcaseVariation.ReadMeFirstUris': testcaseVariationReadMeFirstUris,
    'ModelTestcaseVariation.ArchiveIxds': testcaseVariationArchiveIxds,
    'ModelTestcaseVariation.ReportPackageIxds': testcaseVariationReportPackageIxds,
    'ModelTestcaseVariation.ResultXbrlInstanceUri': testcaseVariationResultInstanceUri,
}
