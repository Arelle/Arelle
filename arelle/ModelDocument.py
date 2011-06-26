'''
Created on Oct 3, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from lxml import etree
from arelle import (XbrlConst, XmlUtil, UrlUtil, ValidateFilingText, XmlValidate)
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname
from arelle.ModelDtsObject import ModelLink, ModelResource
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelObjectFactory import parser

def load(modelXbrl, uri, base=None, isEntry=False, isDiscovered=False, isIncluded=None, namespace=None, reloadCache=False):
    normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(uri, base)
    if isEntry:
        modelXbrl.uri = normalizedUri
        modelXbrl.uriDir = os.path.dirname(normalizedUri)
        for i in range(modelXbrl.modelManager.disclosureSystem.maxSubmissionSubdirectoryEntryNesting):
            modelXbrl.uriDir = os.path.dirname(modelXbrl.uriDir)
    if modelXbrl.modelManager.validateDisclosureSystem and \
       not normalizedUri.startswith(modelXbrl.uriDir) and \
       not modelXbrl.modelManager.disclosureSystem.hrefValid(normalizedUri):
        blocked = modelXbrl.modelManager.disclosureSystem.blockDisallowedReferences
        modelXbrl.error(
                "Prohibited file for filings{1}: {0}".format(normalizedUri, _(" blocked") if blocked else ""), 
                "err", "EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06")
        if blocked:
            return None
    if normalizedUri in modelXbrl.modelManager.disclosureSystem.mappedFiles:
        mappedUri = modelXbrl.modelManager.disclosureSystem.mappedFiles[normalizedUri]
    else:  # handle mapped paths
        mappedUri = normalizedUri
        for mapFrom, mapTo in modelXbrl.modelManager.disclosureSystem.mappedPaths:
            if normalizedUri.startswith(mapFrom):
                mappedUri = mapTo + normalizedUri[len(mapFrom):]
                break
    if modelXbrl.fileSource.isInArchive(mappedUri):
        filepath = mappedUri
    else:
        filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(mappedUri, reload=reloadCache)
        if filepath:
            uri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(filepath)
    if filepath is None: # error such as HTTPerror is already logged
        modelXbrl.error(
                "File can not be loaded: {0}".format(
                mappedUri),
                "err", "FileNotLoadable")
        type = Type.Unknown
        return None
    
    modelDocument = modelXbrl.urlDocs.get(mappedUri)
    if modelDocument:
        return modelDocument
    
    # load XML and determine type of model document
    modelXbrl.modelManager.showStatus(_("parsing {0}").format(uri))
    file = None
    try:
        if modelXbrl.modelManager.disclosureSystem.validateFileText:
            file = ValidateFilingText.checkfile(modelXbrl,filepath)
        else:
            file = modelXbrl.fileSource.file(filepath)
        _parser = parser(modelXbrl,filepath)
        xmlDocument = etree.parse(file,parser=_parser,base_url=filepath)
        file.close()
    except EnvironmentError as err:
        modelXbrl.error(
                "{0}: file error: {1}".format(
                os.path.basename(uri), err),
                "err", "IOerror")
        type = Type.Unknown
        if file:
            file.close()
        return None
    except (etree.LxmlError,
            ValueError) as err:  # ValueError raised on bad format of qnames, xmlns'es, or parameters
        modelXbrl.error(
                "{0}: import error: {1}".format(
                os.path.basename(uri), err),
                "err", "XMLsyntax")
        type = Type.Unknown
        if file:
            file.close()
        return None
    
    # identify document
    #modelXbrl.modelManager.addToLog("discovery: {0}".format(
    #            os.path.basename(uri)))
    modelXbrl.modelManager.showStatus(_("loading {0}").format(uri))
    modelDocument = None
    
    rootNode = xmlDocument.getroot()
    if rootNode is not None:
        ln = rootNode.localName
        ns = rootNode.namespaceURI
        
        # type classification
        if ns == XbrlConst.xsd and ln == "schema":
            type = Type.SCHEMA
        elif ns == XbrlConst.link:
            if ln == "linkbase":
                type = Type.LINKBASE
            elif ln == "xbrl":
                type = Type.INSTANCE
        elif ns == XbrlConst.xbrli:
            if ln == "xbrl":
                type = Type.INSTANCE
        elif ns == XbrlConst.xhtml and \
             (ln == "html" or ln == "xhtml"):
            type = Type.Unknown
            if XbrlConst.ixbrl in rootNode.nsmap.values():
                type = Type.INLINEXBRL
        elif ln == "report" and ns == XbrlConst.ver:
            type = Type.VERSIONINGREPORT
        elif ln == "testcases" or ln == "documentation":
            type = Type.TESTCASESINDEX
        elif ln == "testcase":
            type = Type.TESTCASE
        elif ln == "registry" and ns == XbrlConst.registry:
            type = Type.REGISTRY
        elif ln == "rss":
            type = Type.RSSFEED
        else:
            type = Type.Unknown
            nestedInline = None
            for htmlElt in rootNode.iter(tag="{http://www.w3.org/1999/xhtml}html"):
                nestedInline = htmlElt
                break
            if nestedInline is None:
                for htmlElt in rootNode.iter(tag="{http://www.w3.org/1999/xhtml}xhtml"):
                    nestedInline = htmlElt
                    break
            if nestedInline:
                if XbrlConst.ixbrl in nestedInline.nsmap.values():
                    type = Type.INLINEXBRL
                    rootNode = nestedInline

        #create modelDocument object or subtype as identified
        if type == Type.VERSIONINGREPORT:
            from arelle.ModelVersReport import ModelVersReport
            modelDocument = ModelVersReport(modelXbrl, type, mappedUri, filepath, xmlDocument)
        elif type == Type.RSSFEED:
            from arelle.ModelRssObject import ModelRssObject 
            modelDocument = ModelRssObject(modelXbrl, type, mappedUri, filepath, xmlDocument)
        else:
            modelDocument = ModelDocument(modelXbrl, type, mappedUri, filepath, xmlDocument)
        rootNode.init(modelDocument)
        modelDocument.parser = _parser # needed for XmlUtil addChild's makeelement 
        modelDocument.xmlRootElement = rootNode
        modelDocument.schemaLocationElements.add(rootNode)

        if isEntry or isDiscovered:
            modelDocument.inDTS = True
        
        # discovery (parsing)
        if type == Type.SCHEMA:
            modelDocument.schemaDiscover(rootNode, isIncluded, namespace)
        elif type == Type.LINKBASE:
            modelDocument.linkbaseDiscover(rootNode)
        elif type == Type.INSTANCE:
            modelDocument.instanceDiscover(rootNode)
        elif type == Type.INLINEXBRL:
            modelDocument.inlineXbrlDiscover(rootNode)
        elif type == Type.VERSIONINGREPORT:
            modelDocument.versioningReportDiscover(rootNode)
        elif type == Type.TESTCASESINDEX:
            modelDocument.testcasesIndexDiscover(xmlDocument)
        elif type == Type.TESTCASE:
            modelDocument.testcaseDiscover(rootNode)
        elif type == Type.REGISTRY:
            modelDocument.registryDiscover(rootNode)
        elif type == Type.VERSIONINGREPORT:
            modelDocument.versioningReportDiscover(rootNode)
        elif type == Type.RSSFEED:
            modelDocument.rssFeedDiscover(rootNode)
    return modelDocument

def loadSchemalocatedSchema(modelXbrl, element, relativeUrl, namespace, baseUrl):
    importSchemaLocation = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(relativeUrl, baseUrl)
    doc = load(modelXbrl, importSchemaLocation, isIncluded=False, isDiscovered=False, namespace=namespace)
    if doc:
        doc.inDTS = False
    return doc
            
def create(modelXbrl, type, uri, schemaRefs=None, isEntry=False):
    normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(uri, None)
    if isEntry:
        modelXbrl.uri = normalizedUri
        modelXbrl.uriDir = os.path.dirname(normalizedUri)
        for i in range(modelXbrl.modelManager.disclosureSystem.maxSubmissionSubdirectoryEntryNesting):
            modelXbrl.uriDir = os.path.dirname(modelXbrl.uriDir)
    filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri)
    # XML document has nsmap root element to replace nsmap as new xmlns entries are required
    if type == Type.INSTANCE:
        # modelXbrl.uriDir = os.path.dirname(normalizedUri)
        Xml = ('<nsmap>'
               '<xbrl xmlns="http://www.xbrl.org/2003/instance"'
               ' xmlns:link="http://www.xbrl.org/2003/linkbase"'
               ' xmlns:xlink="http://www.w3.org/1999/xlink">')
        if schemaRefs:
            for schemaRef in schemaRefs:
                Xml += '<link:schemaRef xlink:type="simple" xlink:href="{0}"/>'.format(schemaRef.replace("\\","/"))
        Xml += '</xbrl></nsmap>'
    elif type == Type.SCHEMA:
        Xml = ('<nsmap><schema xmlns="http://www.w3.org/2001/XMLSchema" /></nsmap>')
    elif type == Type.RSSFEED:
        Xml = '<nsmap><rss version="2.0" /></nsmap>'
    elif type == Type.DTSENTRIES:
        Xml = None
    else:
        type = Type.Unknown
        Xml = '<nsmap/>'
    if Xml:
        import io
        file = io.StringIO(Xml)
        _parser = parser(modelXbrl,filepath)
        xmlDocument = etree.parse(file,parser=_parser,base_url=filepath)
        file.close()
    else:
        xmlDocument = None
    if type == Type.RSSFEED:
        from arelle.ModelRssObject import ModelRssObject 
        modelDocument = ModelRssObject(modelXbrl, type, uri, filepath, xmlDocument)
    else:
        modelDocument = ModelDocument(modelXbrl, type, normalizedUri, filepath, xmlDocument)
    if Xml:
        modelDocument.parser = _parser # needed for XmlUtil addChild's makeelement 
        rootNode = xmlDocument.getroot()
        rootNode.init(modelDocument)
        if xmlDocument:
            for semanticRoot in rootNode.iterchildren():
                if isinstance(semanticRoot, ModelObject):
                    modelDocument.xmlRootElement = semanticRoot
                    break
    if type == Type.INSTANCE:
        modelDocument.instanceDiscover(modelDocument.xmlRootElement)
    elif type == Type.RSSFEED:
        modelDocument.rssFeedDiscover(modelDocument.xmlRootElement)
    elif type == Type.SCHEMA:
        modelDocument.targetNamespace = None
    return modelDocument

    
class Type:
    Unknown=0
    SCHEMA=1
    LINKBASE=2
    INSTANCE=3
    INLINEXBRL=4
    DTSENTRIES=5  # multiple schema/linkbase Refs composing a DTS but not from an instance document
    VERSIONINGREPORT=6
    TESTCASESINDEX=7
    TESTCASE=8
    REGISTRY=9
    REGISTRYTESTCASE=10
    RSSFEED=11

    typeName = ("unknown", 
                "schema", 
                "linkbase", 
                "instance", 
                "inline XBRL instance",
                "versioning report",
                "testcasesindex", 
                "testcase",
                "registry",
                "registry testcase")
    
# schema elements which end the include/import scah
schemaBottom = {"element", "attribute", "notation", "simpleType", "complexType", "group", "attributeGroup"}
fractionParts = {"{http://www.xbrl.org/2003/instance}numerator",
                 "{http://www.xbrl.org/2003/instance}denominator"}



class ModelDocument:
    
    def __init__(self, modelXbrl, type, uri, filepath, xmlDocument):
        self.modelXbrl = modelXbrl
        self.type = type
        self.uri = uri
        self.filepath = filepath
        self.xmlDocument = xmlDocument
        self.targetNamespace = None
        modelXbrl.urlDocs[uri] = self
        self.objectIndex = len(modelXbrl.modelObjects)
        modelXbrl.modelObjects.append(self)
        self.referencesDocument = {}
        self.idObjects = {}  # by id
        self.modelObjects = [] # all model objects
        self.hrefObjects = []
        self.schemaLocationElements = set()
        self.referencedNamespaces = set()
        self.inDTS = False

    def objectId(self,refId=""):
        return "_{0}_{1}".format(refId, self.objectIndex)
    
    
    def relativeUri(self, uri): # return uri relative to this modelDocument uri
        if uri.startswith('http://'):
            return uri
        else:
            return os.path.relpath(uri, os.path.dirname(self.uri)).replace('\\','/')
        
    @property
    def basename(self):
        return os.path.basename(self.filepath)

    @property
    def propertyView(self):
        return (("type", self.gettype()),
                ("uri", self.uri)) + \
                (("fromDTS", self.fromDTS.uri),
                 ("toDTS", self.toDTS.uri)
                 ) if self.type == Type.VERSIONINGREPORT else ()
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))

    def close(self, visited):
        visited.append(self)
        for referencedDocument in self.referencesDocument.keys():
            if visited.count(referencedDocument) == 0:
                referencedDocument.close(visited)
        if self.type == Type.VERSIONINGREPORT:
            if self.fromDTS:
                self.fromDTS.close()
                self.fromDTS = None
            if self.toDTS:
                self.toDTS.close()
                self.toDTS = None
        self.modelXbrl = None
        self.referencesDocument = {}
        self.idObjects = {}  # by id
        self.modelObjects = []
        self.hrefObjects = []
        self.schemaLocationElements = set()
        self.referencedNamespaces = set()
        self.xmlDocument = None
        visited.remove(self)
        
    def gettype(self):
        try:
            return Type.typeName[self.type]
        except AttributeError:
            return "unknown"
        
    
    def schemaDiscover(self, rootElement, isIncluded, namespace):
        targetNamespace = rootElement.get("targetNamespace")
        if targetNamespace:
            self.targetNamespace = targetNamespace
            self.referencedNamespaces.add(targetNamespace)
            self.modelXbrl.namespaceDocs[targetNamespace].append(self)
            if namespace and targetNamespace != namespace:
                self.modelXbrl.error(
                    "Discovery of {0} expected namespace {1} found targetNamespace {2}".format(
                    self.basename, namespace, targetNamespace),
                    "err", "xmlSchema1.4.2.3:refSchemaNamespace")
            if (self.modelXbrl.modelManager.validateDisclosureSystem and 
                self.modelXbrl.modelManager.disclosureSystem.disallowedHrefOfNamespace(self.uri, targetNamespace)):
                    self.modelXbrl.error(
                            "Namespace: {0} disallowed schemaLocation {1}".format(targetNamespace, self.uri), 
                            "err", "EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06")

        else:
            if isIncluded == True and namespace:
                self.targetNamespace = namespace
                self.modelXbrl.namespaceDocs[targetNamespace].append(self)
        if targetNamespace == XbrlConst.xbrldt:
            # BUG: should not set this if obtained from schemaLocation instead of import (but may be later imported)
            self.modelXbrl.hasXDT = True
        try:
            self.schemaImportElements(rootElement)
            if self.inDTS:
                self.schemaDiscoverChildElements(rootElement)
        except (ValueError, LookupError) as err:
            self.modelXbrl.modelManager.addToLog("discovery: {0} error {1}".format(
                        self.basename,
                        err))
            
    
    def schemaImportElements(self, parentModelObject):
        # must find import/include before processing linkbases or elements
        for modelObject in parentModelObject.iterchildren():
            if isinstance(modelObject,ModelObject) and modelObject.namespaceURI == XbrlConst.xsd:
                ln = modelObject.localName
                if ln == "import" or ln == "include":
                    self.importDiscover(modelObject)
                if ln in schemaBottom:
                    break

    def schemaDiscoverChildElements(self, parentModelObject):
        # find roleTypes, elements, and linkbases
        for modelObject in parentModelObject.iterchildren():
            if isinstance(modelObject,ModelObject):
                ln = modelObject.localName
                ns = modelObject.namespaceURI
                if ns == XbrlConst.link:
                    if ln == "roleType":
                        self.modelXbrl.roleTypes[modelObject.roleURI].append(modelObject)
                    elif ln == "arcroleType":
                        self.modelXbrl.arcroleTypes[modelObject.arcroleURI].append(modelObject)
                    elif ln == "linkbaseRef":
                        self.schemaLinkbaseRefDiscover(modelObject)
                    elif ln == "linkbase":
                        self.linkbaseDiscover(modelObject)
                # recurse to children
                self.schemaDiscoverChildElements(modelObject)
            
    def baseForElement(self, element):
        base = ""
        baseElt = element
        while baseElt is not None:
            baseAttr = baseElt.get("{http://www.w3.org/XML/1998/namespace}base")
            if baseAttr:
                if self.modelXbrl.modelManager.validateDisclosureSystem:
                    self.modelXbrl.error(
                        "Prohibited base attribute: {0}, in file {1}".format(baseAttr, os.path.basename(self.uri)), 
                        "err", "EFM.6.03.11", "GFM.1.1.7")
                else:
                    if baseAttr.startswith("/"):
                        base = baseAttr
                    else:
                        base = baseAttr + base
            baseElt = baseElt.getparent()
        if base: # neither None nor ''
            if base.startswith('http://') or os.path.isabs(base):
                return base
            else:
                return os.path.dirname(self.filepath) + "/" + base
        return self.filepath
            
    def importDiscover(self, element):
        schemaLocation = element.get("schemaLocation")
        if element.localName == "include":
            importNamespace = self.targetNamespace
            isIncluded = True
        else:
            importNamespace = element.get("namespace")
            isIncluded = False
        if importNamespace and schemaLocation:
            importSchemaLocation = self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(schemaLocation, self.baseForElement(element))
            if (self.modelXbrl.modelManager.validateDisclosureSystem and 
                    self.modelXbrl.modelManager.disclosureSystem.blockDisallowedReferences and
                    self.modelXbrl.modelManager.disclosureSystem.disallowedHrefOfNamespace(importSchemaLocation, importNamespace)):
                self.modelXbrl.error(
                        "Namespace: {0} disallowed schemaLocation blocked {1}".format(importNamespace, importSchemaLocation), 
                        "err", "EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06")
                return
            doc = None
            for otherDoc in self.modelXbrl.namespaceDocs[importNamespace]:
                if otherDoc.uri == importSchemaLocation:
                    doc = otherDoc
                    if self.inDTS and not doc.inDTS:
                        doc.inDTS = True    # now known to be discovered
                        doc.schemaDiscoverChildElements(doc.xmlRootElement)
                    break
            if doc is None:
                doc = load(self.modelXbrl, importSchemaLocation, isDiscovered=self.inDTS, 
                           isIncluded=isIncluded, namespace=importNamespace)
            if doc is not None and self.referencesDocument.get(doc) is None:
                self.referencesDocument[doc] = element.localName #import or include
                self.referencedNamespaces.add(importNamespace)
                
    def schemalocateElementNamespace(self, element):
        eltNamespace = element.namespaceURI 
        if eltNamespace not in self.modelXbrl.namespaceDocs and eltNamespace not in self.referencedNamespaces:
            schemaLocationElement = XmlUtil.schemaLocation(element, eltNamespace, returnElement=True)
            if schemaLocationElement is not None:
                self.schemaLocationElements.add(schemaLocationElement)
                self.referencedNamespaces.add(eltNamespace)

    def loadSchemalocatedSchemas(self):
        # schemaLocation requires loaded schemas for validation
        for elt in self.schemaLocationElements:
            schemaLocation = elt.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
            if schemaLocation:
                ns = None
                for entry in schemaLocation.split():
                    if ns is None:
                        ns = entry
                    else:
                        if ns not in self.modelXbrl.namespaceDocs:
                            loadSchemalocatedSchema(self.modelXbrl, elt, entry, ns, self.baseForElement(elt))
                        ns = None
                        
    def schemaLinkbaseRefsDiscover(self, tree):
        for refln in ("{http://www.xbrl.org/2003/linkbase}schemaRef", "{http://www.xbrl.org/2003/linkbase}linkbaseRef"):
            for element in tree.iterdescendants(tag=refln):
                if isinstance(element,ModelObject):
                    self.schemaLinkbaseRefDiscover(element)

    def schemaLinkbaseRefDiscover(self, element):
        return self.discoverHref(element)
    
    def linkbasesDiscover(self, tree):
        for linkbaseElement in tree.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}linkbase"):
            if isinstance(linkbaseElement,ModelObject):
                self.linkbaseDiscover(self, linkbaseElement)

    def linkbaseDiscover(self, linkbaseElement, inInstance=False):
        for lbElement in linkbaseElement.iterchildren():
            if isinstance(lbElement,ModelObject):
                lbLn = lbElement.localName
                lbNs = lbElement.namespaceURI
                if lbNs == XbrlConst.link:
                    if lbLn == "roleRef" or lbLn == "arcroleRef":
                        href = self.discoverHref(lbElement)
                        if href is None:
                            self.modelXbrl.error(
                                    "Linkbase in {0} {1} href attribute missing or malformed".format(
                                      os.path.basename(self.uri),
                                      lbLn),
                                    "err", "xbrl:hrefMissing")
                        else:
                            self.hrefObjects.append(href)
                        continue
                if lbElement.get("{http://www.w3.org/1999/xlink}type") == "extended":
                    if isinstance(lbElement, ModelLink):
                        self.schemalocateElementNamespace(lbElement)
                        arcrolesFound = set()
                        dimensionArcFound = False
                        formulaArcFound = False
                        euRenderingArcFound = False
                        linkQn = qname(lbElement)
                        linkrole = lbElement.get("{http://www.w3.org/1999/xlink}role")
                        if inInstance:
                            #index footnote links even if no arc children
                            baseSetKeys = (("XBRL-footnotes",None,None,None), 
                                           ("XBRL-footnotes",linkrole,None,None))
                            for baseSetKey in baseSetKeys:
                                self.modelXbrl.baseSets[baseSetKey].append(lbElement)
                        for linkElement in lbElement.iterchildren():
                            if isinstance(linkElement,ModelObject):
                                self.schemalocateElementNamespace(linkElement)
                                xlinkType = linkElement.get("{http://www.w3.org/1999/xlink}type")
                                modelResource = None
                                if xlinkType == "locator":
                                    nonDTS = linkElement.namespaceURI != XbrlConst.link or linkElement.localName != "loc"
                                    # only link:loc elements are discovered or processed
                                    href = self.discoverHref(linkElement, nonDTS=nonDTS)
                                    if href is None:
                                        self.modelXbrl.error(
                                                "Linkbase in {0} {1} href attribute missing or malformed".format(
                                                  os.path.basename(self.uri),
                                                  lbLn),
                                                "err", "xbrl:hrefMissing")
                                    else:
                                        linkElement.modelHref = href
                                        modelResource = linkElement
                                elif xlinkType == "arc":
                                    arcQn = qname(linkElement)
                                    arcrole = linkElement.get("{http://www.w3.org/1999/xlink}arcrole")
                                    if arcrole not in arcrolesFound:
                                        if linkrole == "":
                                            linkrole = XbrlConst.defaultLinkRole
                                        #index by both arcrole and linkrole#arcrole and dimensionsions if applicable
                                        baseSetKeys = [(arcrole, linkrole, linkQn, arcQn)]
                                        baseSetKeys.append((arcrole, linkrole, None, None))
                                        baseSetKeys.append((arcrole, None, None, None))
                                        if XbrlConst.isDimensionArcrole(arcrole) and not dimensionArcFound:
                                            baseSetKeys.append(("XBRL-dimensions", None, None, None)) 
                                            baseSetKeys.append(("XBRL-dimensions", linkrole, None, None))
                                            dimensionArcFound = True
                                        if XbrlConst.isFormulaArcrole(arcrole) and not formulaArcFound:
                                            baseSetKeys.append(("XBRL-formulae", None, None, None)) 
                                            baseSetKeys.append(("XBRL-formulae", linkrole, None, None))
                                            formulaArcFound = True
                                        if XbrlConst.isEuRenderingArcrole(arcrole) and not euRenderingArcFound:
                                            baseSetKeys.append(("EU-rendering", None, None, None)) 
                                            baseSetKeys.append(("EU-rendering", linkrole, None, None)) 
                                            euRenderingArcFound = True
                                            self.modelXbrl.hasEuRendering = True
                                        for baseSetKey in baseSetKeys:
                                            self.modelXbrl.baseSets[baseSetKey].append(lbElement)
                                        arcrolesFound.add(arcrole)
                                elif xlinkType == "resource": 
                                    # create resource and make accessible by id for document
                                    modelResource = linkElement
                                if modelResource is not None:
                                    lbElement.labeledResources[linkElement.get("{http://www.w3.org/1999/xlink}label")] \
                                        .append(modelResource)
                    else:
                        self.modelXbrl.error(
                                "Linkbase in {0} {1} extended link element missing schema import".format(
                                  os.path.basename(self.uri), lbElement.prefixedName),
                                "err", "xbrl:schemaImportMissing")
                        
                
    def discoverHref(self, element, nonDTS=False):
        href = element.get("{http://www.w3.org/1999/xlink}href")
        if href:
            url, id = UrlUtil.splitDecodeFragment(href)
            if url == "":
                doc = self
            else:
                # href discovery only can happein within a DTS
                doc = load(self.modelXbrl, url, isDiscovered=True, base=self.baseForElement(element))
                if not nonDTS and doc is not None and self.referencesDocument.get(doc) is None:
                    self.referencesDocument[doc] = "href"
                    if not doc.inDTS and doc.type != Type.Unknown:    # non-XBRL document is not in DTS
                        doc.inDTS = True    # now known to be discovered
                        if doc.type == Type.SCHEMA: # schema coming newly into DTS
                            doc.schemaDiscoverChildElements(doc.xmlRootElement)
            href = (element, doc, id if len(id) > 0 else None)
            self.hrefObjects.append(href)
            return href
        return None
    
    def instanceDiscover(self, xbrlElement):
        self.schemaLinkbaseRefsDiscover(xbrlElement)
        self.linkbaseDiscover(xbrlElement,inInstance=True) # for role/arcroleRefs and footnoteLinks
        self.instanceContentsDiscover(xbrlElement)

    def instanceContentsDiscover(self,xbrlElement):
        for instElement in xbrlElement.iterchildren():
            if isinstance(instElement,ModelObject):
                ln = instElement.localName
                ns = instElement.namespaceURI
                if ns == XbrlConst.xbrli:
                    if ln == "context":
                        self.contextDiscover(instElement)
                    elif ln == "unit":
                        self.unitDiscover(instElement)
                elif ns == XbrlConst.link:
                    pass
                else: # concept elements
                    self.factDiscover(instElement, self.modelXbrl.facts)
                    
    def contextDiscover(self, modelContext):
        id = modelContext.id
        self.modelXbrl.contexts[id] = modelContext
        for container in (("{http://www.xbrl.org/2003/instance}segment", modelContext.segDimValues, modelContext.segNonDimValues),
                          ("{http://www.xbrl.org/2003/instance}scenario", modelContext.scenDimValues, modelContext.scenNonDimValues)):
            containerName, containerDimValues, containerNonDimValues = container
            for containerElement in modelContext.iterdescendants(tag=containerName):
                for sElt in containerElement.iterchildren():
                    if isinstance(sElt,ModelObject):
                        if sElt.namespaceURI == XbrlConst.xbrldi and sElt.localName in ("explicitMember","typedMember"):
                            XmlValidate.validate(self.modelXbrl, sElt)
                            dimension = sElt.dimension
                            if dimension is not None and dimension not in containerDimValues:
                                containerDimValues[dimension] = sElt
                            else:
                                modelContext.errorDimValues.append(sElt)
                            modelContext.qnameDims[sElt.dimensionQname] = sElt # both seg and scen
                        else:
                            containerNonDimValues.append(sElt)
                            
    def unitDiscover(self, unitElement):
        self.modelXbrl.units[unitElement.id] = unitElement
                
    def inlineXbrlDiscover(self, htmlElement):
        self.schemaLinkbaseRefsDiscover(htmlElement)
        for inlineElement in htmlElement.getdescendants(tag="{http://www.xbrl.org/2008/inlineXBRL}resources"):
            self.instanceContentsDiscover(inlineElement)
            
        tuplesByElement = {}
        tuplesByTupleID = {}
        for modelInlineTuple in htmlElement.getdescendants(tag="{http://www.xbrl.org/2008/inlineXBRL}tuple"):
            if isinstance(modelInlineTuple,ModelObject):
                modelInlineTuple.unorderedTupleFacts = []
                if modelInlineTuple.tupleID:
                    tuplesByTupleID[modelInlineTuple.tupleID] = modelInlineTuple
                tuplesByElement[inlineElement] = modelInlineTuple
        # hook up tuples to their container
        for tupleFact in tuplesByElement.values():
            self.inlineXbrlLocateFactInTuple(tupleFact, tuplesByTupleID, tuplesByElement)

        for tag in ("{http://www.xbrl.org/2008/inlineXBRL}nonNumeric", "{http://www.xbrl.org/2008/inlineXBRL}nonFraction", "{http://www.xbrl.org/2008/inlineXBRL}fraction"):
            for modelInlineFact in htmlElement.getdescendants(tag=tag):
                if isinstance(modelInlineFact,ModelObject):
                    self.inlineXbrlLocateFactInTuple(modelInlineFact, tuplesByTupleID, tuplesByElement)
        # order tuple facts
        for tupleFact in tuplesByElement.values():
            tupleFact.modelTupleFacts = [
                 self.modelXbrl.modelObject(objectIndex) 
                 for order,objectIndex in sorted(tupleFact.unorderedTupleFacts)]
                
    def inlineXbrlLocateFactInTuple(self, modelFact, tuplesByTupleID, tuplesByElement):
        tupleRef = modelFact.tupleRef
        if tupleRef:
            if tupleRef not in tuplesByTupleID:
                self.modelXbrl.error(
                        "Inline XBRL {0} tupleRef {1} not found".format(
                          os.path.basename(self.uri), tupleRef),
                        "err", "ixerr:tupleRefMissing")
                tuple = None
            else:
                tuple = tuplesByTupleID[tupleRef]
        else:
            tuple = tuplesByElement.get(XmlUtil.ancestor(modelFact, XbrlConst.ixbrl, "tuple"))
        if tuple:
            tuple.unorderedTupleFacts.append((modelFact.order, modelFact.objectIndex))
        else:
            self.modelXbrl.facts.append(modelFact)
                
    def factDiscover(self, modelFact, parentModelFacts):
        if isinstance(modelFact, ModelFact):
            parentModelFacts.append( modelFact )
            self.modelXbrl.factsInInstance.append( modelFact )
            for tupleElement in modelFact.getchildren():
                if isinstance(tupleElement,ModelObject) and tupleElement.tag not in fractionParts:
                    self.factDiscover(tupleElement, modelFact.modelTupleFacts)
        else:
            self.modelXbrl.error(
                    "Instance {0} line {1} fact {2} missing schema definition ".format(
                      os.path.basename(self.uri), modelFact.sourceline, modelFact.prefixedName),
                    "err", "xbrl:schemaImportMissing")
    
    def testcasesIndexDiscover(self, rootNode):
        for testcasesElement in rootNode.iter():
            if isinstance(testcasesElement,ModelObject) and testcasesElement.localName == "testcases":
                rootAttr = testcasesElement.get("root")
                if rootAttr:
                    base = os.path.join(os.path.dirname(self.filepath),rootAttr) + os.sep
                else:
                    base = self.filepath
                for testcaseElement in testcasesElement.getchildren():
                    if isinstance(testcaseElement,ModelObject) and testcaseElement.localName == "testcase":
                        if testcaseElement.get("uri"):
                            uriAttr = testcaseElement.get("uri")
                            doc = load(self.modelXbrl, uriAttr, base=base)
                            if doc is not None and self.referencesDocument.get(doc) is None:
                                self.referencesDocument[doc] = "testcaseIndex"

    def testcaseDiscover(self, testcaseElement):
        if XmlUtil.xmlnsprefix(testcaseElement, XbrlConst.cfcn):
            self.type = Type.REGISTRYTESTCASE
        self.testcaseVariations = [modelVariation
                                   for modelVariation in XmlUtil.descendants(testcaseElement, testcaseElement.namespaceURI, "variation")
                                   if isinstance(modelVariation,ModelObject)]
        if len(self.testcaseVariations) == 0:
            # may be a inline test case
            if XbrlConst.ixbrl in testcaseElement.values():
                self.testcaseVariations.append(testcaseElement)

    def registryDiscover(self, rootNode):
        base = self.filepath
        for entryElement in rootNode.iterdescendants(tag="{http://xbrl.org/2008/registry}entry"):
            if isinstance(entryElement,ModelObject): 
                uri = XmlUtil.childAttr(entryElement, XbrlConst.registry, "url", "{http://www.w3.org/1999/xlink}href")
                functionDoc = load(self.modelXbrl, uri, base=base)
                if functionDoc is not None:
                    testuri = XmlUtil.childAttr(functionDoc.xmlRootElement, XbrlConst.function, "conformanceTest", "{http://www.w3.org/1999/xlink}href")
                    testbase = functionDoc.filepath
                    testcaseDoc = load(self.modelXbrl, testuri, base=testbase)
                    if testcaseDoc is not None and self.referencesDocument.get(testcaseDoc) is None:
                        self.referencesDocument[testcaseDoc] = "registryIndex"
            
