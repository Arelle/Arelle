'''
Created on Oct 3, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import xml.dom.minidom, xml.parsers.expat, os
from arelle import (XbrlConst, XmlUtil, UrlUtil, ModelObject, ValidateFilingText, XmlValidate)
from arelle.ModelValue import (qname)

def load(modelXbrl, uri, base=None, isEntry=False, isIncluded=None, namespace=None, reloadCache=False):
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
        if modelXbrl.modelManager.validateDisclosureSystem:
            file = ValidateFilingText.checkfile(modelXbrl,filepath)
        else:
            file = modelXbrl.fileSource.file(filepath)
        xmlDocument = xml.dom.minidom.parse(file)
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
    except (xml.parsers.expat.ExpatError,
            xml.dom.DOMException,
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
    
    for rootNode in xmlDocument.childNodes:
        if rootNode.nodeType == 1: #element
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
                 ln == "html" or ln == "xhtml":
                type = Type.Unknown
                for i in range(len(rootNode.attributes)):
                    if rootNode.attributes.item(i).value == XbrlConst.ixbrl:
                        type = Type.INLINEXBRL
                        break
                XmlUtil.markIdAttributes(rootNode)  # required for minidom searchability
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
                nestedInline = XmlUtil.descendant(rootNode, XbrlConst.xhtml, ("html", "xhtml"))
                if nestedInline:
                    for i in range(len(nestedInline.attributes)):
                        if nestedInline.attributes.item(i).value == XbrlConst.ixbrl:
                            type = Type.INLINEXBRL
                            rootNode = nestedInline
                            break
                XmlUtil.markIdAttributes(rootNode)  # required for minidom searchability

            #create modelDocument object or subtype as identified
            if type == Type.VERSIONINGREPORT:
                from arelle.ModelVersReport import ModelVersReport
                modelDocument = ModelVersReport(modelXbrl, type, mappedUri, filepath, xmlDocument)
            elif type == Type.RSSFEED:
                from arelle.ModelRssObject import ModelRssObject 
                modelDocument = ModelRssObject(modelXbrl, type, mappedUri, filepath, xmlDocument)
            else:
                modelDocument = ModelDocument(modelXbrl, type, mappedUri, filepath, xmlDocument)
            modelDocument.xmlRootElement = rootNode
            if isEntry:
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
            break
    return modelDocument

def create(modelXbrl, type, uri, schemaRefs=None, isEntry=False):
    normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(uri, None)
    if isEntry:
        modelXbrl.uri = normalizedUri
        modelXbrl.uriDir = os.path.dirname(normalizedUri)
        for i in range(modelXbrl.modelManager.disclosureSystem.maxSubmissionSubdirectoryEntryNesting):
            modelXbrl.uriDir = os.path.dirname(modelXbrl.uriDir)
    filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri)
    if type == Type.INSTANCE:
        # modelXbrl.uriDir = os.path.dirname(normalizedUri)
        Xml = ('<?xml version="1.0" encoding="UTF-8"?>' 
               '<xbrl xmlns="http://www.xbrl.org/2003/instance"'
               ' xmlns:link="http://www.xbrl.org/2003/linkbase"'
               ' xmlns:xlink="http://www.w3.org/1999/xlink">')
        if schemaRefs:
            for schemaRef in schemaRefs:
                Xml += '<link:schemaRef xlink:type="simple" xlink:href="{0}"/>'.format(schemaRef.replace("\\","/"))
        Xml += '</xbrl>'
    elif type == Type.SCHEMA:
        Xml = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<schema xmlns="http://www.w3.org/2001/XMLSchema" />')
    elif type == Type.RSSFEED:
        Xml = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" />'
    elif type == Type.DTSENTRIES:
        Xml = None
    else:
        type = Type.Unknown
        Xml = '<?xml version="1.0" encoding="UTF-8"?>'
    if Xml:
        xmlDocument = xml.dom.minidom.parseString(Xml)
    else:
        xmlDocument = None
    if type == Type.RSSFEED:
        from arelle.ModelRssObject import ModelRssObject 
        modelDocument = ModelRssObject(modelXbrl, type, uri, filepath, xmlDocument)
    else:
        modelDocument = ModelDocument(modelXbrl, type, normalizedUri, filepath, xmlDocument)
    if xmlDocument:
        modelDocument.xmlRootElement = modelDocument.xmlDocument.documentElement
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

# constants for parsing
xsdModelObjects = {"element", "attribute", "simpleType", "complexType", "enumeration"}

class ModelDocument:
    
    def __init__(self, modelXbrl, type, uri, filepath, xmlDocument):
        self.modelXbrl = modelXbrl
        self.type = type
        self.uri = uri
        self.filepath = filepath
        self.xmlDocument = xmlDocument
        if xmlDocument: xmlDocument.modelDocument = self
        self.targetNamespace = None
        modelXbrl.urlDocs[uri] = self
        self.objectIndex = len(modelXbrl.modelObjects)
        modelXbrl.modelObjects.append(self)
        self.referencesDocument = {}
        self.idObjects = {}  # by id
        self.modelObjects = [] # all model objects
        self.hrefObjects = []
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
        if self.xmlDocument:
            del self.xmlDocument.modelDocument
            self.xmlDocument.unlink()
            self.xmlDocument = None
        visited.remove(self)
        
    def gettype(self):
        try:
            return Type.typeName[self.type]
        except AttributeError:
            return "unknown"
        
    
    def schemaDiscover(self, rootElement, isIncluded, namespace):
        targetNamespace = rootElement.getAttribute("targetNamespace")
        if rootElement.hasAttribute("targetNamespace") and targetNamespace != "":
            self.targetNamespace = targetNamespace
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
            self.modelXbrl.hasXDT = True
        try:
            self.schemaDiscoverChildElements(rootElement)
        except (ValueError, LookupError) as err:
            self.modelXbrl.modelManager.addToLog("discovery: {0} error {1}".format(
                        self.basename,
                        err))
            
    
    def schemaDiscoverChildElements(self, parentElement):
        for element in parentElement.childNodes:
            if element.nodeType == 1: #element
                ln = element.localName
                ns = element.namespaceURI
                modelObject = None
                if ns == XbrlConst.link:
                    if ln == "roleType":
                        modelObject = ModelObject.create(self, element)
                        self.modelXbrl.roleTypes[modelObject.roleURI].append(modelObject)
                    elif ln == "arcroleType":
                        modelObject = ModelObject.create(self, element)
                        self.modelXbrl.arcroleTypes[modelObject.arcroleURI].append(modelObject)
                    elif ln == "linkbaseRef":
                        self.schemaLinkbaseRefDiscover(element)
                    elif ln == "linkbase":
                        self.linkbaseDiscover(element)
                elif ns == XbrlConst.xsd:
                    if ln in xsdModelObjects:
                        modelObject = ModelObject.create(self, element)
                    elif ln == "import" or ln == "include":
                        self.importDiscover(element)
                # save document objects indexed by id
                if modelObject is not None and element.hasAttribute("id"):
                    self.idObjects[element.getAttribute("id")] = modelObject
                # recurse to children
                self.schemaDiscoverChildElements(element)
            
    def baseForElement(self, element):
        base = ""
        baseElt = element
        while baseElt.nodeType == 1:
            if baseElt.hasAttribute("xml:base"):
                if self.modelXbrl.modelManager.validateDisclosureSystem:
                    self.modelXbrl.error(
                        "Prohibited base attribute: {0}, in file {1}".format(
                                   baseElt.getAttribute("xml:base"), 
                                   os.path.basename(self.uri)), 
                        "err", "EFM.6.03.11", "GFM.1.1.7")
                else:
                    baseAttr = baseElt.getAttribute("xml:base")
                    if baseAttr.startswith("/"):
                        base = baseAttr
                    else:
                        base = baseAttr + base
            baseElt = baseElt.parentNode
        if base: # neither None nor ''
            if base.startswith('http://') or os.path.isabs(base):
                return base
            else:
                return os.path.dirname(self.filepath) + "/" + base
        return self.filepath
            
    def importDiscover(self, element):
        schemaLocation = element.getAttribute("schemaLocation")
        if element.localName == "include":
            importNamespace = self.targetNamespace
            isIncluded = True
        else:
            importNamespace = element.getAttribute("namespace")
            isIncluded = False
        if importNamespace != "" and schemaLocation != "":
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
                    doc.inDTS = True
                    break
            if doc is None:
                doc = load(self.modelXbrl, importSchemaLocation, 
                           isIncluded=isIncluded, namespace=importNamespace)
            if doc is not None and self.referencesDocument.get(doc) is None:
                self.referencesDocument[doc] = element.localName #import or include
                doc.inDTS = True
                
    def schemalocateElementNamespace(self, element):
        eltNamespace = element.namespaceURI 
        if eltNamespace not in self.modelXbrl.namespaceDocs:
            schemaLocation = XmlUtil.schemaLocation(element, eltNamespace)
            if schemaLocation:
                importSchemaLocation = self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(schemaLocation, self.baseForElement(element))
                doc = load(self.modelXbrl, importSchemaLocation, 
                           isIncluded=False, namespace=eltNamespace)
                if doc:
                    doc.inDTS = False
                
    def schemaLinkbaseRefsDiscover(self, tree):
        for refln in ("schemaRef", "linkbaseRef"):
            for element in tree.getElementsByTagNameNS(XbrlConst.link, refln):
                self.schemaLinkbaseRefDiscover(element)

    def schemaLinkbaseRefDiscover(self, element):
        return self.discoverHref(element)
    
    def linkbasesDiscover(self, tree):
        for linkbaseElement in tree.getElementsByTagNameNS(XbrlConst.link, "linkbase"):
            self.linkbaseDiscover(self, linkbaseElement)

    def linkbaseDiscover(self, linkbaseElement, inInstance=False):
        for lbElement in linkbaseElement.childNodes:
            if lbElement.nodeType == 1: #element
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
                if lbElement.getAttributeNS(XbrlConst.xlink, "type") == "extended":
                    self.schemalocateElementNamespace(lbElement)
                    arcrolesFound = set()
                    dimensionArcFound = False
                    formulaArcFound = False
                    euRenderingArcFound = False
                    linkQn = qname(lbElement)
                    linkrole = lbElement.getAttributeNS(XbrlConst.xlink, "role")
                    modelLink = ModelObject.createLink(self, lbElement)
                    if inInstance:
                        #index footnote links even if no arc children
                        baseSetKeys = (("XBRL-footnotes",None,None,None), 
                                       ("XBRL-footnotes",linkrole,None,None))
                        for baseSetKey in baseSetKeys:
                            self.modelXbrl.baseSets[baseSetKey].append(modelLink)
                    for linkElement in lbElement.childNodes:
                        if linkElement.nodeType == 1: #element
                            self.schemalocateElementNamespace(linkElement)
                            xlinkType = linkElement.getAttributeNS(XbrlConst.xlink, "type")
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
                                    modelResource = ModelObject.createLocator(self, linkElement, href)
                            elif xlinkType == "arc":
                                arcQn = qname(linkElement)
                                arcrole = linkElement.getAttributeNS(XbrlConst.xlink, "arcrole")
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
                                        self.modelXbrl.baseSets[baseSetKey].append(modelLink)
                                    arcrolesFound.add(arcrole)
                            elif xlinkType == "resource": 
                                # create resource and make accessible by id for document
                                modelResource = ModelObject.createResource(self, linkElement)
                            if modelResource is not None:
                                if linkElement.hasAttribute("id"):
                                    self.idObjects[linkElement.getAttribute("id")] = modelResource
                                modelLink.labeledResources[linkElement.getAttributeNS(XbrlConst.xlink, "label")] \
                                    .append(modelResource)
                            else:
                                XmlUtil.markIdAttributes(linkElement)
                    
                
    def discoverHref(self, element, nonDTS=False):
        if element.hasAttributeNS(XbrlConst.xlink, "href"):
            url, id = UrlUtil.splitDecodeFragment(element.getAttributeNS(XbrlConst.xlink, "href"))
            if url == "":
                doc = self
            else:
                doc = load(self.modelXbrl, url, base=self.baseForElement(element))
                if not nonDTS and doc is not None and self.referencesDocument.get(doc) is None:
                    self.referencesDocument[doc] = "href"
                    doc.inDTS = doc.type != Type.Unknown    # non-XBRL document is not in DTS
            href = (element, doc, id if len(id) > 0 else None)
            self.hrefObjects.append(href)
            return href
        return None
    
    def instanceDiscover(self, xbrlElement):
        self.schemaLinkbaseRefsDiscover(xbrlElement)
        self.linkbaseDiscover(xbrlElement,inInstance=True) # for role/arcroleRefs and footnoteLinks
        self.instanceContentsDiscover(xbrlElement)

    def instanceContentsDiscover(self,xbrlElement):
        for instElement in xbrlElement.childNodes:
            if instElement.nodeType == 1: #element
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
                    
    def contextDiscover(self, cntxElement):
        id = cntxElement.getAttribute("id")
        self.modelXbrl.contexts[id] = modelContext = ModelObject.createContext(self,cntxElement)
        for container in (("segment", modelContext.segDimValues, modelContext.segNonDimValues),
                          ("scenario", modelContext.scenDimValues, modelContext.scenNonDimValues)):
            containerName, containerDimValues, containerNonDimValues = container
            for containerElement in XmlUtil.descendants(cntxElement, XbrlConst.xbrli, containerName):
                for sElt in containerElement.childNodes:
                    if sElt.nodeType == 1:
                        if sElt.namespaceURI == XbrlConst.xbrldi and sElt.localName in ("explicitMember","typedMember"):
                            XmlValidate.validate(self.modelXbrl, sElt)
                            modelDimValue = ModelObject.createDimensionValue(self,sElt)
                            dimension = modelDimValue.dimension
                            if dimension and dimension not in containerDimValues:
                                containerDimValues[dimension] = modelDimValue
                            else:
                                modelContext.errorDimValues.append(modelDimValue)
                            modelContext.qnameDims[modelDimValue.dimensionQname] = modelDimValue # both seg and scen
                        else:
                            containerNonDimValues.append(sElt)
                            
    def unitDiscover(self, unitElement):
        id = unitElement.getAttribute("id")
        self.modelXbrl.units[id] = ModelObject.createUnit(self,unitElement)
                
    def inlineXbrlDiscover(self, htmlElement):
        self.schemaLinkbaseRefsDiscover(htmlElement)
        for inlineElement in htmlElement.getElementsByTagNameNS(XbrlConst.ixbrl, "resources"):
            self.instanceContentsDiscover(inlineElement)
            
        tuplesByElement = {}
        tuplesByTupleID = {}
        for inlineElement in htmlElement.getElementsByTagNameNS(XbrlConst.ixbrl, "tuple"):
            modelInlineFact = ModelObject.createInlineFact(self, inlineElement)
            modelInlineFact.unorderedTupleFacts = []
            if modelInlineFact.tupleID:
                tuplesByTupleID[modelInlineFact.tupleID] = modelInlineFact
            tuplesByElement[inlineElement] = modelInlineFact
        # hook up tuples to their container
        for tupleFact in tuplesByElement.values():
            self.inlineXbrlLocateFactInTuple(tupleFact, tuplesByTupleID, tuplesByElement)

        for ln in ("nonNumeric", "nonFraction", "fraction"):
            for inlineElement in htmlElement.getElementsByTagNameNS(XbrlConst.ixbrl, ln):
                modelInlineFact = ModelObject.createInlineFact(self, inlineElement)
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
            tuple = tuplesByElement.get(XmlUtil.ancestor(modelFact.element, XbrlConst.ixbrl, "tuple"))
        if tuple:
            tuple.unorderedTupleFacts.append((modelFact.order, modelFact.objectIndex))
        else:
            self.modelXbrl.facts.append(modelFact)
                
    def factDiscover(self, factElement, modelFacts):
        modelFact = ModelObject.createFact(self, factElement)
        modelFacts.append( modelFact )
        self.modelXbrl.factsInInstance.append( modelFact )
        id = modelFact.id
        if id is not None:
            self.idObjects[id] = modelFact
        for tupleElement in factElement.childNodes:
            if tupleElement.nodeType == 1: #element
                self.factDiscover(tupleElement, modelFact.modelTupleFacts)
                
        return modelFact
    
    def testcasesIndexDiscover(self, rootNode):
        for testcasesElement in rootNode.getElementsByTagName("testcases"):
            rootAttr = testcasesElement.getAttribute("root")
            if rootAttr != "":
                base = os.path.join(os.path.dirname(self.filepath),rootAttr) + os.sep
            else:
                base = self.filepath
            for testcaseElement in testcasesElement.childNodes:
                if testcaseElement.nodeType == 1 and testcaseElement.localName == "testcase":
                    if testcaseElement.hasAttribute("uri"):
                        uriAttr = testcaseElement.getAttribute("uri")
                        doc = load(self.modelXbrl, uriAttr, base=base)
                        if doc is not None and self.referencesDocument.get(doc) is None:
                            self.referencesDocument[doc] = "testcaseIndex"

    def testcaseDiscover(self, testcaseElement):
        if XmlUtil.xmlnsprefix(testcaseElement, XbrlConst.cfcn):
            self.type = Type.REGISTRYTESTCASE
        self.testcaseVariations = [ModelObject.createTestcaseVariation(self, variationElement)
                                   for variationElement in testcaseElement.getElementsByTagName("variation")]
        if len(self.testcaseVariations) == 0:
            # may be a inline test case
            for i in range(len(testcaseElement.attributes)):
                if testcaseElement.attributes.item(i).value == XbrlConst.ixbrl:
                    modelVariation = ModelObject.createTestcaseVariation(self, testcaseElement)
                    self.testcaseVariations.append(modelVariation)
                    break

    def registryDiscover(self, rootNode):
        base = self.filepath
        for entryElement in rootNode.getElementsByTagNameNS(XbrlConst.registry, "entry"):
            uri = XmlUtil.childAttr(entryElement, XbrlConst.registry, "url", "xlink:href")
            functionDoc = load(self.modelXbrl, uri, base=base)
            if functionDoc is not None:
                testuri = XmlUtil.childAttr(functionDoc.xmlRootElement, XbrlConst.function, "conformanceTest", "xlink:href")
                testbase = functionDoc.filepath
                testcaseDoc = load(self.modelXbrl, testuri, base=testbase)
                if testcaseDoc is not None and self.referencesDocument.get(testcaseDoc) is None:
                    self.referencesDocument[testcaseDoc] = "registryIndex"

