'''
Created on Oct 3, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, sys
from lxml import etree
from xml.sax import SAXParseException
from arelle import (XbrlConst, XmlUtil, UrlUtil, ValidateFilingText, XmlValidate)
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname
from arelle.ModelDtsObject import ModelLink, ModelResource, ModelRelationship
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelObjectFactory import parser
from arelle.PluginManager import pluginClassMethods

def load(modelXbrl, uri, base=None, referringElement=None, isEntry=False, isDiscovered=False, isIncluded=None, namespace=None, reloadCache=False):
    """Returns a new modelDocument, performing DTS discovery for instance, inline XBRL, schema, 
    linkbase, and versioning report entry urls.
    
    :param uri: Identification of file to load by string filename or by a FileSource object with a selected content file.
    :type uri: str or FileSource
    :param referringElement: Source element causing discovery or loading of this document, such as an import or xlink:href
    :type referringElement: ModelObject
    :param isEntry: True for an entry document
    :type isEntry: bool
    :param isDiscovered: True if this document is discovered by XBRL rules, otherwise False (such as when schemaLocation and xmlns were the cause of loading the schema)
    :type isDiscovered: bool
    :param isIncluded: True if this document is the target of an xs:include
    :type isIncluded: bool
    :param namespace: The schema namespace of this document, if known and applicable
    :type namespace: str
    :param reloadCache: True if desired to reload the web cache for any web-referenced files.
    :type reloadCache: bool
    """
    if referringElement is None: # used for error messages
        referringElement = modelXbrl
    normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(uri, base)
    if isEntry:
        modelXbrl.entryLoadingUrl = normalizedUri   # for error loggiong during loading
        modelXbrl.uri = normalizedUri
        modelXbrl.uriDir = os.path.dirname(normalizedUri)
        for i in range(modelXbrl.modelManager.disclosureSystem.maxSubmissionSubdirectoryEntryNesting):
            modelXbrl.uriDir = os.path.dirname(modelXbrl.uriDir)
    if modelXbrl.modelManager.validateDisclosureSystem and \
       not normalizedUri.startswith(modelXbrl.uriDir) and \
       not modelXbrl.modelManager.disclosureSystem.hrefValid(normalizedUri):
        blocked = modelXbrl.modelManager.disclosureSystem.blockDisallowedReferences
        modelXbrl.error(("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06" if normalizedUri.startswith("http") else "SBR.NL.2.2.0.17"),
                _("Prohibited file for filings %(blockedIndicator)s: %(url)s"),
                modelObject=referringElement, url=normalizedUri, blockedIndicator=_(" blocked") if blocked else "")
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
    if isEntry:
        modelXbrl.entryLoadingUrl = mappedUri   # for error loggiong during loading
    if modelXbrl.fileSource.isInArchive(mappedUri):
        filepath = mappedUri
    else:
        filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(mappedUri, reload=reloadCache)
        if filepath:
            uri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(filepath)
    if filepath is None: # error such as HTTPerror is already logged
        modelXbrl.error("FileNotLoadable",
                _("File can not be loaded: %(fileName)s"),
                modelObject=referringElement, fileName=mappedUri)
        return None
    
    modelDocument = modelXbrl.urlDocs.get(mappedUri)
    if modelDocument:
        return modelDocument
    
    # load XML and determine type of model document
    modelXbrl.modelManager.showStatus(_("parsing {0}").format(uri))
    file = None
    try:
        if (modelXbrl.modelManager.validateDisclosureSystem and 
            modelXbrl.modelManager.disclosureSystem.validateFileText):
            file, _encoding = ValidateFilingText.checkfile(modelXbrl,filepath)
        else:
            file, _encoding = modelXbrl.fileSource.file(filepath)
        _parser, _parserLookupName, _parserLookupClass = parser(modelXbrl,filepath)
        xmlDocument = None
        isPluginParserDocument = False
        for pluginMethod in pluginClassMethods("ModelDocument.CustomLoader"):
            modelDocument = pluginMethod(modelXbrl, file, mappedUri, filepath)
            if modelDocument is not None:
                return modelDocument
        xmlDocument = etree.parse(file,parser=_parser,base_url=filepath)
        file.close()
    except (EnvironmentError, KeyError) as err:  # missing zip file raises KeyError
        if file:
            file.close()
        # retry in case of well known schema locations
        if not isIncluded and namespace and namespace in XbrlConst.standardNamespaceSchemaLocations and uri != XbrlConst.standardNamespaceSchemaLocations[namespace]:
            return load(modelXbrl, XbrlConst.standardNamespaceSchemaLocations[namespace], 
                        base, referringElement, isEntry, isDiscovered, isIncluded, namespace, reloadCache)
        modelXbrl.error("IOerror",
                _("%(fileName)s: file error: %(error)s"),
                modelObject=referringElement, fileName=os.path.basename(uri), error=str(err))
        return None
    except (etree.LxmlError,
            SAXParseException,
            ValueError) as err:  # ValueError raised on bad format of qnames, xmlns'es, or parameters
        if file:
            file.close()
        if not isEntry and str(err) == "Start tag expected, '<' not found, line 1, column 1":
            return ModelDocument(modelXbrl, Type.UnknownNonXML, mappedUri, filepath, None)
        else:
            modelXbrl.error("xmlSchema:syntax",
                    _("%(error)s, %(fileName)s, %(sourceAction)s source element"),
                    modelObject=referringElement, fileName=os.path.basename(uri), 
                    error=str(err), sourceAction=("including" if isIncluded else "importing"))
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
            if not isEntry and not isIncluded:
                # check if already loaded under a different url
                targetNamespace = rootNode.get("targetNamespace")
                if targetNamespace and modelXbrl.namespaceDocs.get(targetNamespace):
                    otherModelDoc = modelXbrl.namespaceDocs[targetNamespace][0]
                    if otherModelDoc.basename == os.path.basename(uri):
                        modelXbrl.urlDocs[uri] = otherModelDoc
                        modelXbrl.warning("info:duplicatedSchema",
                                _("Schema file with same targetNamespace %(targetNamespace)s loaded from %(fileName)s and %(otherFileName)s"),
                                modelObject=referringElement, targetNamespace=targetNamespace, fileName=uri, otherFileName=otherModelDoc.uri)
                        return otherModelDoc 
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
            type = Type.UnknownXML
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
        elif ln == "ptvl":
            type = Type.ARCSINFOSET
        elif ln == "facts":
            type = Type.FACTDIMSINFOSET
        else:
            type = Type.UnknownXML
            nestedInline = None
            for htmlElt in rootNode.iter(tag="{http://www.w3.org/1999/xhtml}html"):
                nestedInline = htmlElt
                break
            if nestedInline is None:
                for htmlElt in rootNode.iter(tag="{http://www.w3.org/1999/xhtml}xhtml"):
                    nestedInline = htmlElt
                    break
            if nestedInline is not None:
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
        modelDocument.parserLookupName = _parserLookupName
        modelDocument.parserLookupClass = _parserLookupClass
        modelDocument.xmlRootElement = rootNode
        modelDocument.schemaLocationElements.add(rootNode)
        modelDocument.documentEncoding = _encoding

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
    doc = load(modelXbrl, importSchemaLocation, isIncluded=False, isDiscovered=False, namespace=namespace, referringElement=element)
    if doc:
        doc.inDTS = False
    return doc
            
def create(modelXbrl, type, uri, schemaRefs=None, isEntry=False):
    """Returns a new modelDocument, created from scratch, with any necessary header elements 
    
    (such as the schema, instance, or RSS feed top level elements)
    :param type: type of model document (value of ModelDocument.Types, an integer)
    :type type: Types
    :param schemaRefs: list of URLs when creating an empty INSTANCE, to use to discover (load) the needed DTS modelDocument objects.
    :type schemaRefs: [str]
    :param isEntry is True when creating an entry (e.g., instance)
    :type isEntry: bool
    """
    normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(uri, None)
    if isEntry:
        modelXbrl.uri = normalizedUri
        modelXbrl.entryLoadingUrl = normalizedUri
        modelXbrl.uriDir = os.path.dirname(normalizedUri)
        for i in range(modelXbrl.modelManager.disclosureSystem.maxSubmissionSubdirectoryEntryNesting):
            modelXbrl.uriDir = os.path.dirname(modelXbrl.uriDir)
    filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri, filenameOnly=True)
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
        type = Type.UnknownXML
        Xml = '<nsmap/>'
    if Xml:
        import io
        file = io.StringIO(Xml)
        _parser, _parserLookupName, _parserLookupClass = parser(modelXbrl,filepath)
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
        modelDocument.parserLookupName = _parserLookupName
        modelDocument.parserLookupClass = _parserLookupClass
        modelDocument.documentEncoding = "utf-8"
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
        modelDocument.isQualifiedElementFormDefault = False
        modelDocument.isQualifiedAttributeFormDefault = False
    modelDocument.definesUTR = False
    return modelDocument

    
class Type:
    """
    .. class:: Type
    
    Static class of Enumerated type representing modelDocument type
    """
    UnknownXML=0
    UnknownNonXML=1
    UnknownTypes=1  # to test if any unknown type, use <= Type.UnknownTypes
    firstXBRLtype=2  # first filetype that is XBRL and can hold a linkbase, etc inside it
    SCHEMA=2
    LINKBASE=3
    INSTANCE=4
    INLINEXBRL=5
    lastXBRLtype=5  # first filetype that is XBRL and can hold a linkbase, etc inside it
    DTSENTRIES=6  # multiple schema/linkbase Refs composing a DTS but not from an instance document
    VERSIONINGREPORT=7
    TESTCASESINDEX=8
    TESTCASE=9
    REGISTRY=10
    REGISTRYTESTCASE=11
    RSSFEED=12
    ARCSINFOSET=13
    FACTDIMSINFOSET=14

    typeName = ("unknown XML",
                "unknown non-XML", 
                "schema", 
                "linkbase", 
                "instance", 
                "inline XBRL instance",
                "entry point set",
                "versioning report",
                "testcases index", 
                "testcase",
                "registry",
                "registry testcase",
                "RSS feed",
                "arcs infoset",
                "fact dimensions infoset")
    
# schema elements which end the include/import scah
schemaBottom = {"element", "attribute", "notation", "simpleType", "complexType", "group", "attributeGroup"}
fractionParts = {"{http://www.xbrl.org/2003/instance}numerator",
                 "{http://www.xbrl.org/2003/instance}denominator"}



class ModelDocument:
    """
    .. class:: ModelDocment(modelXbrl, type, uri, filepath, xmlDocument)

    The modelDocument performs discovery and initialization when loading documents.  
    For instances, schema and linkbase references are resolved, as well as non-DTS schema locations needed 
    to ensure PSVI-validated XML elements in the instance document (for formula processing).  
    For DTSes, schema includes and imports are resolved, linkbase references discovered, and 
    concepts made accessible by qname by the modelXbrl and ID at the modelDocument scope.  
    Testcase documents (and their indexing files) are loaded as modelDocument objects.
      
    Specialized modelDocuments are the versioning report, which must discover from and to DTSes, 
    and an RSS feed, which has a unique XML structure.

    :param modelXbrl: The ModelXbrl (DTS) object owning this modelDocument.
    :type modelXbrl: ModelXbrl
    :param uri:  The document's source entry URI (such as web site URL)
    :type uri: str
    :param filepath:  The file path of the source for the document (local file or web cache file name)
    :type filepath: str
    :param xmlDocument: lxml parsed xml document tree model of lxml proxy objects
    :type xmlDocument: lxml document

        .. attribute:: modelDocument
        
        Self (provided for consistency with modelObjects)

        .. attribute:: modelXbrl
        
        The owning modelXbrl

        .. attribute:: type
        
        The enumerated document type

        .. attribute:: uri

        Uri as discovered

        .. attribute:: filepath
        
        File path as loaded (e.g., from web cache on local drive)

        .. attribute:: basename
        
        Python basename (last segment of file path)

        .. attribute:: xmlDocument
        
        The lxml tree model of xml proxies

        .. attribute:: targetNamespace
        
        Target namespace (if a schema)

        .. attribute:: objectIndex
        
        Position in lxml objects table, for use as a surrogate

        .. attribute:: referencesDocument
        
        Dict of referenced documents, key is the modelDocument, value is why loaded (import, include, href)

        .. attribute:: idObjects
        
        Dict by id of modelObjects in document

        .. attribute:: modelObjects
        
        List of modelObjects discovered in document in document order

        .. attribute:: hrefObjects
        
        List of (modelObject, modelDocument, id) for each xlink:href

        .. attribute:: schemaLocationElements
        
        Set of modelObject elements that have xsi:schemaLocations

        .. attribute:: referencedNamespaces
        
        Set of referenced namespaces (by import, discovery, etc)

        .. attribute:: inDTS
        
        Qualifies as a discovered schema per XBRL 2.1
    """
    
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
        self.definesUTR = False

    def objectId(self,refId=""):
        return "_{0}_{1}".format(refId, self.objectIndex)
    
    
    def relativeUri(self, uri): # return uri relative to this modelDocument uri
        return UrlUtil.relativeUri(self.uri, uri)
        
    @property
    def modelDocument(self):
        return self # for compatibility with modelObject and modelXbrl

    @property
    def basename(self):
        return os.path.basename(self.filepath)
    
    @property
    def filepathdir(self):
        return os.path.dirname(self.filepath)

    @property
    def propertyView(self):
        return (("type", self.gettype()),
                ("uri", self.uri)) + \
                (("fromDTS", self.fromDTS.uri),
                 ("toDTS", self.toDTS.uri)
                 ) if self.type == Type.VERSIONINGREPORT else ()
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))

    def close(self, visited=None):
        if visited is None: visited = []
        visited.append(self)
        try:
            for referencedDocument in self.referencesDocument.keys():
                if referencedDocument not in visited:
                    referencedDocument.close(visited)
            if self.type == Type.VERSIONINGREPORT:
                if self.fromDTS:
                    self.fromDTS.close()
                if self.toDTS:
                    self.toDTS.close()
            xmlDocument = self.xmlDocument
            parser = self.parser
            for modelObject in self.modelObjects:
                modelObject.clear() # clear children
            self.parserLookupName.__dict__.clear()
            self.parserLookupClass.__dict__.clear()
            self.__dict__.clear() # dereference everything before clearing xml tree
            xmlDocument._setroot(parser.makeelement("{http://dummy}dummy"))
        except AttributeError:
            pass    # maybe already cloased
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
                self.modelXbrl.error("xmlSchema1.4.2.3:refSchemaNamespace",
                    _("Discovery of %(fileName)s expected namespace %(namespace)s found targetNamespace %(targetNamespace)s"),
                    modelObject=rootElement, fileName=self.basename,
                    namespace=namespace, targetNamespace=targetNamespace)
            if (self.modelXbrl.modelManager.validateDisclosureSystem and 
                self.modelXbrl.modelManager.disclosureSystem.disallowedHrefOfNamespace(self.uri, targetNamespace)):
                    self.modelXbrl.error(("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06" if self.uri.startswith("http") else "SBR.NL.2.2.0.17"),
                            _("Namespace: %(namespace)s disallowed schemaLocation %(schemaLocation)s"),
                            modelObject=rootElement, namespace=targetNamespace, schemaLocation=self.uri)

        else:
            if isIncluded == True and namespace:
                self.targetNamespace = namespace
                self.modelXbrl.namespaceDocs[targetNamespace].append(self)
        if targetNamespace == XbrlConst.xbrldt:
            # BUG: should not set this if obtained from schemaLocation instead of import (but may be later imported)
            self.modelXbrl.hasXDT = True
        self.isQualifiedElementFormDefault = rootElement.get("elementFormDefault") == "qualified"
        self.isQualifiedAttributeFormDefault = rootElement.get("attributeFormDefault") == "qualified"
        self.definesUTR = any(ns == XbrlConst.utr for ns in rootElement.nsmap.values())
        try:
            self.schemaDiscoverChildElements(rootElement)
        except (ValueError, LookupError) as err:
            self.modelXbrl.modelManager.addToLog("discovery: {0} error {1}".format(
                        self.basename,
                        err))
            
    def schemaDiscoverChildElements(self, parentModelObject):
        # find roleTypes, elements, and linkbases
        # must find import/include before processing linkbases or elements
        for modelObject in parentModelObject.iterchildren():
            if isinstance(modelObject,ModelObject):
                ln = modelObject.localName
                ns = modelObject.namespaceURI
                if modelObject.namespaceURI == XbrlConst.xsd and ln in {"import", "include"}:
                    self.importDiscover(modelObject)
                elif self.inDTS and ns == XbrlConst.link:
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
                    self.modelXbrl.error(("EFM.6.03.11", "GFM.1.1.7"),
                        _("Prohibited base attribute: %(attribute)s"),
                        modelObejct=element, attribute=baseAttr)
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
                self.modelXbrl.error(("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06" if importSchemaLocation.startswith("http") else "SBR.NL.2.2.0.17"),
                        _("Namespace: %(namespace)s disallowed schemaLocation blocked %(schemaLocation)s"),
                        modelObject=element, namespace=importNamespace, schemaLocation=importSchemaLocation)
                return
            doc = None
            importSchemaLocationBasename = os.path.basename(importNamespace)
            # is there an exact match for importNamespace and uri?
            for otherDoc in self.modelXbrl.namespaceDocs[importNamespace]:
                doc = otherDoc
                if otherDoc.uri == importSchemaLocation:
                    break
                elif isIncluded:
                    doc = None  # don't allow matching namespace lookup on include (NS is already loaded!)
                elif doc.basename != importSchemaLocationBasename:
                    doc = None  # different file (may have imported a file now being included)
            # if no uri match, doc will be some other that matched targetNamespace
            if doc is not None:
                if self.inDTS and not doc.inDTS:
                    doc.inDTS = True    # now known to be discovered
                    doc.schemaDiscoverChildElements(doc.xmlRootElement)
            else:
                doc = load(self.modelXbrl, importSchemaLocation, isDiscovered=self.inDTS, 
                           isIncluded=isIncluded, namespace=importNamespace, referringElement=element)
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
                            self.modelXbrl.error("xmlSchema:requiredAttribute",
                                    _("Linkbase reference for %(linkbaseRefElement)s href attribute missing or malformed"),
                                    modelObject=lbElement, linkbaseRefElement=lbLn)
                        else:
                            self.hrefObjects.append(href)
                        continue
                if lbElement.get("{http://www.w3.org/1999/xlink}type") == "extended":
                    if isinstance(lbElement, ModelLink):
                        self.schemalocateElementNamespace(lbElement)
                        arcrolesFound = set()
                        dimensionArcFound = False
                        formulaArcFound = False
                        tableRenderingArcFound = False
                        linkQn = qname(lbElement)
                        linkrole = lbElement.get("{http://www.w3.org/1999/xlink}role")
                        isStandardExtLink = XbrlConst.isStandardResourceOrExtLinkElement(lbElement)
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
                                        if isStandardExtLink:
                                            self.modelXbrl.error("xmlSchema:requiredAttribute",
                                                    _("Locator href attribute missing or malformed in standard extended link"),
                                                    modelObejct=linkElement)
                                        else:
                                            self.modelXbrl.warning("arelle:hrefWarning",
                                                    _("Locator href attribute missing or malformed in non-standard extended link"),
                                                    modelObejct=linkElement)
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
                                        if XbrlConst.isTableRenderingArcrole(arcrole) and not tableRenderingArcFound:
                                            baseSetKeys.append(("Table-rendering", None, None, None)) 
                                            baseSetKeys.append(("Table-rendering", linkrole, None, None)) 
                                            tableRenderingArcFound = True
                                            self.modelXbrl.hasTableRendering = True
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
                        self.modelXbrl.error("xbrl:schemaDefinitionMissing",
                                _("Linkbase extended link %(element)s missing schema definition"),
                                modelObject=lbElement, element=lbElement.prefixedName)
                
    def discoverHref(self, element, nonDTS=False):
        href = element.get("{http://www.w3.org/1999/xlink}href")
        if href:
            url, id = UrlUtil.splitDecodeFragment(href)
            if url == "":
                doc = self
            else:
                # href discovery only can happein within a DTS
                doc = load(self.modelXbrl, url, isDiscovered=not nonDTS, base=self.baseForElement(element), referringElement=element)
                if not nonDTS and doc is not None and self.referencesDocument.get(doc) is None:
                    self.referencesDocument[doc] = "href"
                    if not doc.inDTS and doc.type > Type.UnknownTypes:    # non-XBRL document is not in DTS
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
        XmlValidate.validate(self.modelXbrl, xbrlElement) # validate instance elements

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
                            #XmlValidate.validate(self.modelXbrl, sElt)
                            dimension = sElt.dimension
                            if dimension is not None and dimension not in containerDimValues:
                                containerDimValues[dimension] = sElt
                                modelContext.qnameDims[sElt.dimensionQname] = sElt # both seg and scen
                            else:
                                modelContext.errorDimValues.append(sElt)
                        else:
                            containerNonDimValues.append(sElt)
                            
    def unitDiscover(self, unitElement):
        self.modelXbrl.units[unitElement.id] = unitElement
                
    def inlineXbrlDiscover(self, htmlElement):
        if htmlElement.namespaceURI == XbrlConst.xhtml:  # must validate xhtml
            #load(self.modelXbrl, "http://www.w3.org/2002/08/xhtml/xhtml1-strict.xsd")
            XmlValidate.xhtmlValidate(self.modelXbrl, htmlElement)  # fails on prefixed content
        for inlineElement in htmlElement.iterdescendants(tag="{http://www.xbrl.org/2008/inlineXBRL}references"):
            self.schemaLinkbaseRefsDiscover(inlineElement)
            XmlValidate.validate(self.modelXbrl, inlineElement) # validate instance elements
        for inlineElement in htmlElement.iterdescendants(tag="{http://www.xbrl.org/2008/inlineXBRL}resources"):
            self.instanceContentsDiscover(inlineElement)
            XmlValidate.validate(self.modelXbrl, inlineElement) # validate instance elements
            
        tupleElements = []
        tuplesByTupleID = {}
        for modelInlineTuple in htmlElement.iterdescendants(tag="{http://www.xbrl.org/2008/inlineXBRL}tuple"):
            if isinstance(modelInlineTuple,ModelObject):
                modelInlineTuple.unorderedTupleFacts = []
                if modelInlineTuple.tupleID:
                    tuplesByTupleID[modelInlineTuple.tupleID] = modelInlineTuple
                tupleElements.append(modelInlineTuple)
        # hook up tuples to their container
        for tupleFact in tupleElements:
            self.inlineXbrlLocateFactInTuple(tupleFact, tuplesByTupleID)

        for tag in ("{http://www.xbrl.org/2008/inlineXBRL}nonNumeric", "{http://www.xbrl.org/2008/inlineXBRL}nonFraction", "{http://www.xbrl.org/2008/inlineXBRL}fraction"):
            for modelInlineFact in htmlElement.iterdescendants(tag=tag):
                if isinstance(modelInlineFact,ModelObject):
                    self.inlineXbrlLocateFactInTuple(modelInlineFact, tuplesByTupleID)
        # order tuple facts
        for tupleFact in tupleElements:
            tupleFact.modelTupleFacts = [
                 self.modelXbrl.modelObject(objectIndex) 
                 for order,objectIndex in sorted(tupleFact.unorderedTupleFacts)]
            
        # validate particle structure of elements after transformations and established tuple structure
        for rootModelFact in self.modelXbrl.facts:
            XmlValidate.validate(self.modelXbrl, rootModelFact, ixFacts=True)

                
    def inlineXbrlLocateFactInTuple(self, modelFact, tuplesByTupleID):
        tupleRef = modelFact.tupleRef
        tuple = None
        if tupleRef:
            if tupleRef not in tuplesByTupleID:
                self.modelXbrl.error("ix.13.1.2:tupleRefMissing",
                        _("Inline XBRL tupleRef %(tupleRef)s not found"),
                        modelObject=modelFact, tupleRef=tupleRef)
            else:
                tuple = tuplesByTupleID[tupleRef]
        else:
            for tupleParent in modelFact.iterancestors(tag="{http://www.xbrl.org/2008/inlineXBRL}tuple"):
                tuple = tupleParent
                break
        if tuple is not None:
            tuple.unorderedTupleFacts.append((modelFact.order, modelFact.objectIndex))
        else:
            self.modelXbrl.facts.append(modelFact)
                
    def factDiscover(self, modelFact, parentModelFacts=None, parentElement=None):
        if parentModelFacts is None: # may be called with parentElement instead of parentModelFacts list
            if isinstance(parentElement, ModelFact) and parentElement.isTuple:
                parentModelFacts = parentElement.modelTupleFacts
            else:
                parentModelFacts = self.modelXbrl.facts
        if isinstance(modelFact, ModelFact):
            parentModelFacts.append( modelFact )
            self.modelXbrl.factsInInstance.add( modelFact )
            for tupleElement in modelFact:
                if isinstance(tupleElement,ModelObject) and tupleElement.tag not in fractionParts:
                    self.factDiscover(tupleElement, modelFact.modelTupleFacts)
        else:
            self.modelXbrl.error("xbrl:schemaImportMissing",
                    _("Instance fact %(element)s missing schema definition "),
                    modelObject=modelFact, element=modelFact.prefixedName)
    
    def testcasesIndexDiscover(self, rootNode):
        for testcasesElement in rootNode.iter():
            if isinstance(testcasesElement,ModelObject) and testcasesElement.localName == "testcases":
                rootAttr = testcasesElement.get("root")
                if rootAttr:
                    base = os.path.join(os.path.dirname(self.filepath),rootAttr) + os.sep
                else:
                    base = self.filepath
                for testcaseElement in testcasesElement:
                    if isinstance(testcaseElement,ModelObject) and testcaseElement.localName == "testcase":
                        if testcaseElement.get("uri"):
                            uriAttr = testcaseElement.get("uri")
                            doc = load(self.modelXbrl, uriAttr, base=base, referringElement=testcaseElement)
                            if doc is not None and self.referencesDocument.get(doc) is None:
                                self.referencesDocument[doc] = "testcaseIndex"

    def testcaseDiscover(self, testcaseElement):
        isTransformTestcase = testcaseElement.namespaceURI == "http://xbrl.org/2011/conformance-rendering/transforms"
        if XmlUtil.xmlnsprefix(testcaseElement, XbrlConst.cfcn) or isTransformTestcase:
            self.type = Type.REGISTRYTESTCASE
        self.outpath = self.xmlRootElement.get("outpath") 
        self.testcaseVariations = []
        priorTransformName = None
        for modelVariation in XmlUtil.descendants(testcaseElement, testcaseElement.namespaceURI, "variation"):
            self.testcaseVariations.append(modelVariation)
            if isTransformTestcase and modelVariation.getparent().get("name") is not None:
                transformName = modelVariation.getparent().get("name")
                if transformName != priorTransformName:
                    priorTransformName = transformName
                    variationNumber = 1
                modelVariation._name = "{0} v-{1:02}".format(priorTransformName, variationNumber)
                variationNumber += 1
        if len(self.testcaseVariations) == 0:
            # may be a inline test case
            if XbrlConst.ixbrl in testcaseElement.values():
                self.testcaseVariations.append(testcaseElement)

    def registryDiscover(self, rootNode):
        base = self.filepath
        for entryElement in rootNode.iterdescendants(tag="{http://xbrl.org/2008/registry}entry"):
            if isinstance(entryElement,ModelObject): 
                uri = XmlUtil.childAttr(entryElement, XbrlConst.registry, "url", "{http://www.w3.org/1999/xlink}href")
                functionDoc = load(self.modelXbrl, uri, base=base, referringElement=entryElement)
                if functionDoc is not None:
                    testUriElt = XmlUtil.child(functionDoc.xmlRootElement, XbrlConst.function, "conformanceTest")
                    if testUriElt is not None:
                        testuri = testUriElt.get("{http://www.w3.org/1999/xlink}href")
                        testbase = functionDoc.filepath
                        if testuri is not None:
                            testcaseDoc = load(self.modelXbrl, testuri, base=testbase, referringElement=testUriElt)
                            if testcaseDoc is not None and self.referencesDocument.get(testcaseDoc) is None:
                                self.referencesDocument[testcaseDoc] = "registryIndex"
            
