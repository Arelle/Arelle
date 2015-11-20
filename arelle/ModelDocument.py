'''
Created on Oct 3, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, io, sys, traceback
from collections import defaultdict
from lxml import etree
from xml.sax import SAXParseException
from arelle import (PackageManager, XbrlConst, XmlUtil, UrlUtil, ValidateFilingText, 
                    XhtmlValidate, XmlValidate, XmlValidateSchema)
from arelle.ModelObject import ModelObject, ModelComment
from arelle.ModelValue import qname
from arelle.ModelDtsObject import ModelLink, ModelResource, ModelRelationship
from arelle.ModelInstanceObject import ModelFact, ModelInlineFact
from arelle.ModelObjectFactory import parser
from arelle.PrototypeDtsObject import LinkPrototype, LocPrototype, ArcPrototype, DocumentPrototype
from arelle.PluginManager import pluginClassMethods
creationSoftwareNames = None

def load(modelXbrl, uri, base=None, referringElement=None, isEntry=False, isDiscovered=False, isIncluded=None, namespace=None, reloadCache=False, **kwargs):
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
    :type isSupplemental: True if this document is supplemental (not discovered or in DTS but adds labels or instance facts)
    :type namespace: str
    :param reloadCache: True if desired to reload the web cache for any web-referenced files.
    :type reloadCache: bool
    """
    
    if referringElement is None: # used for error messages
        referringElement = modelXbrl
    normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(uri, base)
    modelDocument = modelXbrl.urlDocs.get(normalizedUri)
    if modelDocument:
        return modelDocument
    elif modelXbrl.urlUnloadableDocs.get(normalizedUri):  # only return None if in this list and marked True (really not loadable)
        return None

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
        if normalizedUri not in modelXbrl.urlUnloadableDocs:
            # HMRC note, HMRC.blockedFile should be in this list if hmrc-taxonomies.xml is maintained an dup to date
            modelXbrl.error(("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06" if normalizedUri.startswith("http") else "SBR.NL.2.2.0.17"),
                    _("Prohibited file for filings %(blockedIndicator)s: %(url)s"),
                    modelObject=referringElement, url=normalizedUri,
                    blockedIndicator=_(" blocked") if blocked else "",
                    messageCodes=("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06", "SBR.NL.2.2.0.17"))
            #modelXbrl.debug("EFM.6.22.02", "traceback %(traceback)s",
            #                modeObject=referringElement, traceback=traceback.format_stack())
            modelXbrl.urlUnloadableDocs[normalizedUri] = blocked
        if blocked:
            return None
    
    if modelXbrl.modelManager.skipLoading and modelXbrl.modelManager.skipLoading.match(normalizedUri):
        return None
    
    if modelXbrl.fileSource.isMappedUrl(normalizedUri):
        mappedUri = modelXbrl.fileSource.mappedUrl(normalizedUri)
    elif PackageManager.isMappedUrl(normalizedUri):
        mappedUri = PackageManager.mappedUrl(normalizedUri)
    else:
        mappedUri = modelXbrl.modelManager.disclosureSystem.mappedUrl(normalizedUri)
        
    if isEntry:
        modelXbrl.entryLoadingUrl = mappedUri   # for error loggiong during loading
        
    # don't try reloading if not loadable
    
    if any(pluginMethod(modelXbrl, mappedUri, normalizedUri, isEntry=isEntry, namespace=namespace, **kwargs)
           for pluginMethod in pluginClassMethods("ModelDocument.IsPullLoadable")):
        filePath = normalizedUri
    if modelXbrl.fileSource.isInArchive(mappedUri):
        filepath = mappedUri
    else:
        filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(mappedUri, reload=reloadCache)
        if filepath:
            uri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(filepath)
    if filepath is None: # error such as HTTPerror is already logged
        if modelXbrl.modelManager.abortOnMajorError and (isEntry or isDiscovered):
            modelXbrl.error("FileNotLoadable",
                    _("File can not be loaded: %(fileName)s \nLoading terminated."),
                    modelObject=referringElement, fileName=mappedUri)
            raise LoadingException()
        if normalizedUri not in modelXbrl.urlUnloadableDocs:
            modelXbrl.error("FileNotLoadable",
                    _("File can not be loaded: %(fileName)s"),
                    modelObject=referringElement, fileName=normalizedUri)
            modelXbrl.urlUnloadableDocs[normalizedUri] = True # always blocked if not loadable on this error
        return None
    
    if filepath.endswith(".xlsx") or filepath.endswith(".xls"):
        modelXbrl.error("FileNotLoadable",
                _("File can not be loaded, requires loadFromExcel plug-in: %(fileName)s"),
                modelObject=referringElement, fileName=normalizedUri)
        return None
    
    
    # load XML and determine type of model document
    modelXbrl.modelManager.showStatus(_("parsing {0}").format(uri))
    file = None
    try:
        for pluginMethod in pluginClassMethods("ModelDocument.PullLoader"):
            # assumes not possible to check file in string format or not all available at once
            modelDocument = pluginMethod(modelXbrl, normalizedUri, filepath, isEntry=isEntry, namespace=namespace, **kwargs)
            if isinstance(modelDocument, Exception):
                return None
            if modelDocument is not None:
                return modelDocument
        if (modelXbrl.modelManager.validateDisclosureSystem and 
            modelXbrl.modelManager.disclosureSystem.validateFileText):
            file, _encoding = ValidateFilingText.checkfile(modelXbrl,filepath)
        else:
            file, _encoding = modelXbrl.fileSource.file(filepath, stripDeclaration=True)
        xmlDocument = None
        isPluginParserDocument = False
        for pluginMethod in pluginClassMethods("ModelDocument.CustomLoader"):
            modelDocument = pluginMethod(modelXbrl, file, mappedUri, filepath)
            if modelDocument is not None:
                file.close()
                return modelDocument
        _parser, _parserLookupName, _parserLookupClass = parser(modelXbrl,filepath)
        xmlDocument = etree.parse(file,parser=_parser,base_url=filepath)
        for error in _parser.error_log:
            modelXbrl.error("xmlSchema:syntax",
                    _("%(error)s, %(fileName)s, line %(line)s, column %(column)s, %(sourceAction)s source element"),
                    modelObject=referringElement, fileName=os.path.basename(uri), 
                    error=error.message, line=error.line, column=error.column, sourceAction=("including" if isIncluded else "importing"))
        file.close()
    except (EnvironmentError, KeyError) as err:  # missing zip file raises KeyError
        if file:
            file.close()
        # retry in case of well known schema locations
        if not isIncluded and namespace and namespace in XbrlConst.standardNamespaceSchemaLocations and uri != XbrlConst.standardNamespaceSchemaLocations[namespace]:
            return load(modelXbrl, XbrlConst.standardNamespaceSchemaLocations[namespace], 
                        base, referringElement, isEntry, isDiscovered, isIncluded, namespace, reloadCache)
        if modelXbrl.modelManager.abortOnMajorError and (isEntry or isDiscovered):
            modelXbrl.error("IOerror",
                _("%(fileName)s: file error: %(error)s \nLoading terminated."),
                modelObject=referringElement, fileName=os.path.basename(uri), error=str(err))
            raise LoadingException()
        #import traceback
        #print("traceback {}".format(traceback.format_tb(sys.exc_info()[2])))
        modelXbrl.error("IOerror",
                _("%(fileName)s: file error: %(error)s"),
                modelObject=referringElement, fileName=os.path.basename(uri), error=str(err))
        modelXbrl.urlUnloadableDocs[normalizedUri] = True  # not loadable due to IO issue
        return None
    except (etree.LxmlError, etree.XMLSyntaxError,
            SAXParseException,
            ValueError) as err:  # ValueError raised on bad format of qnames, xmlns'es, or parameters
        if file:
            file.close()
        if not isEntry and str(err) == "Start tag expected, '<' not found, line 1, column 1":
            return ModelDocument(modelXbrl, Type.UnknownNonXML, normalizedUri, filepath, None)
        else:
            modelXbrl.error("xmlSchema:syntax",
                    _("Unrecoverable error: %(error)s, %(fileName)s, %(sourceAction)s source element"),
                    modelObject=referringElement, fileName=os.path.basename(uri), 
                    error=str(err), sourceAction=("including" if isIncluded else "importing"), exc_info=True)
            modelXbrl.urlUnloadableDocs[normalizedUri] = True  # not loadable due to parser issues
            return None
    except Exception as err:
        modelXbrl.error(type(err).__name__,
                _("Unrecoverable error: %(error)s, %(fileName)s, %(sourceAction)s source element"),
                modelObject=referringElement, fileName=os.path.basename(uri), 
                error=str(err), sourceAction=("including" if isIncluded else "importing"), exc_info=True)
        modelXbrl.urlUnloadableDocs[normalizedUri] = True  # not loadable due to exception issue
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
        _type = None
        _class = ModelDocument
        if ns == XbrlConst.xsd and ln == "schema":
            _type = Type.SCHEMA
            if not isEntry and not isIncluded:
                # check if already loaded under a different url
                targetNamespace = rootNode.get("targetNamespace")
                if targetNamespace and modelXbrl.namespaceDocs.get(targetNamespace):
                    otherModelDoc = modelXbrl.namespaceDocs[targetNamespace][0]
                    if otherModelDoc.basename == os.path.basename(uri):
                        if os.path.normpath(otherModelDoc.uri) != os.path.normpath(uri): # tolerate \ vs / or ../ differences
                            modelXbrl.urlDocs[uri] = otherModelDoc
                            modelXbrl.warning("info:duplicatedSchema",
                                    _("Schema file with same targetNamespace %(targetNamespace)s loaded from %(fileName)s and %(otherFileName)s"),
                                    modelObject=referringElement, targetNamespace=targetNamespace, fileName=uri, otherFileName=otherModelDoc.uri)
                        return otherModelDoc 
        elif (isEntry or isDiscovered or kwargs.get("isSupplemental", False)) and ns == XbrlConst.link:
            if ln == "linkbase":
                _type = Type.LINKBASE
            elif ln == "xbrl":
                _type = Type.INSTANCE
        elif isEntry and ns == XbrlConst.xbrli:
            if ln == "xbrl":
                _type = Type.INSTANCE
        elif ns == XbrlConst.xhtml and \
             (ln == "html" or ln == "xhtml"):
            _type = Type.UnknownXML
            if XbrlConst.ixbrlAll.intersection(rootNode.nsmap.values()):
                _type = Type.INLINEXBRL
        elif ln == "report" and ns == XbrlConst.ver:
            _type = Type.VERSIONINGREPORT
            from arelle.ModelVersReport import ModelVersReport
            _class = ModelVersReport
        elif ln in ("testcases", "documentation", "testSuite"):
            _type = Type.TESTCASESINDEX
        elif ln in ("testcase", "testSet"):
            _type = Type.TESTCASE
        elif ln == "registry" and ns == XbrlConst.registry:
            _type = Type.REGISTRY
        elif ln == "test-suite" and ns == "http://www.w3.org/2005/02/query-test-XQTSCatalog":
            _type = Type.XPATHTESTSUITE
        elif ln == "rss":
            _type = Type.RSSFEED
            from arelle.ModelRssObject import ModelRssObject 
            _class = ModelRssObject
        elif ln == "ptvl":
            _type = Type.ARCSINFOSET
        elif ln == "facts":
            _type = Type.FACTDIMSINFOSET
        elif XbrlConst.ixbrlAll.intersection(rootNode.nsmap.values()):
            # any xml document can be an inline document, only html and xhtml are found above
            _type = Type.INLINEXBRL
        else:
            for pluginMethod in pluginClassMethods("ModelDocument.IdentifyType"):
                _identifiedType = pluginMethod(modelXbrl, rootNode, filepath)
                if _identifiedType is not None:
                    _type, _class, rootNode = _identifiedType
                    break
            if _type is None:
                _type = Type.UnknownXML
                    
                nestedInline = None
                for htmlElt in rootNode.iter(tag="{http://www.w3.org/1999/xhtml}html"):
                    nestedInline = htmlElt
                    break
                if nestedInline is None:
                    for htmlElt in rootNode.iter(tag="{http://www.w3.org/1999/xhtml}xhtml"):
                        nestedInline = htmlElt
                        break
                if nestedInline is not None:
                    if XbrlConst.ixbrlAll.intersection(nestedInline.nsmap.values()):
                        _type = Type.INLINEXBRL
                        rootNode = nestedInline

        modelDocument = _class(modelXbrl, _type, normalizedUri, filepath, xmlDocument)
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
        if any(pluginMethod(modelDocument)
               for pluginMethod in pluginClassMethods("ModelDocument.Discover")):
            pass # discovery was performed by plug-in, we're done
        elif _type == Type.SCHEMA:
            modelDocument.schemaDiscover(rootNode, isIncluded, namespace)
        elif _type == Type.LINKBASE:
            modelDocument.linkbaseDiscover(rootNode)
        elif _type == Type.INSTANCE:
            modelDocument.instanceDiscover(rootNode)
        elif _type == Type.INLINEXBRL:
            modelDocument.inlineXbrlDiscover(rootNode)
        elif _type == Type.VERSIONINGREPORT:
            modelDocument.versioningReportDiscover(rootNode)
        elif _type == Type.TESTCASESINDEX:
            modelDocument.testcasesIndexDiscover(xmlDocument)
        elif _type == Type.TESTCASE:
            modelDocument.testcaseDiscover(rootNode)
        elif _type == Type.REGISTRY:
            modelDocument.registryDiscover(rootNode)
        elif _type == Type.XPATHTESTSUITE:
            modelDocument.xPathTestSuiteDiscover(rootNode)
        elif _type == Type.VERSIONINGREPORT:
            modelDocument.versioningReportDiscover(rootNode)
        elif _type == Type.RSSFEED:
            modelDocument.rssFeedDiscover(rootNode)
            
        if isEntry:
            for pi in modelDocument.processingInstructions:
                if pi.target == "arelle-unit-test":
                    modelXbrl.arelleUnitTests[pi.get("location")] = pi.get("action")
            while modelXbrl.schemaDocsToValidate:
                doc = modelXbrl.schemaDocsToValidate.pop()
                XmlValidateSchema.validate(doc, doc.xmlRootElement, doc.targetNamespace) # validate schema elements
            if hasattr(modelXbrl, "ixdsHtmlElements"):
                inlineIxdsDiscover(modelXbrl) # compile cross-document IXDS references

    return modelDocument

def loadSchemalocatedSchema(modelXbrl, element, relativeUrl, namespace, baseUrl):
    if namespace == XbrlConst.xhtml: # block loading xhtml as a schema (e.g., inline which is xsd validated instead)
        return None
    importSchemaLocation = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(relativeUrl, baseUrl)
    doc = load(modelXbrl, importSchemaLocation, isIncluded=False, isDiscovered=False, namespace=namespace, referringElement=element)
    if doc:
        if doc.targetNamespace != namespace:
            modelXbrl.error("xmlSchema1.4.2.3:refSchemaNamespace",
                _("SchemaLocation of %(fileName)s expected namespace %(namespace)s found targetNamespace %(targetNamespace)s"),
                modelObject=element, fileName=baseUrl,
                namespace=namespace, targetNamespace=doc.targetNamespace)
        else:
            doc.inDTS = False
    return doc
            
def create(modelXbrl, type, uri, schemaRefs=None, isEntry=False, initialXml=None, initialComment=None, base=None):
    """Returns a new modelDocument, created from scratch, with any necessary header elements 
    
    (such as the schema, instance, or RSS feed top level elements)
    :param type: type of model document (value of ModelDocument.Types, an integer)
    :type type: Types
    :param schemaRefs: list of URLs when creating an empty INSTANCE, to use to discover (load) the needed DTS modelDocument objects.
    :type schemaRefs: [str]
    :param isEntry is True when creating an entry (e.g., instance)
    :type isEntry: bool
    :param initialXml is initial xml content for xml documents
    :type isEntry: str
    """
    normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(uri, base)
    if isEntry:
        modelXbrl.uri = normalizedUri
        modelXbrl.entryLoadingUrl = normalizedUri
        modelXbrl.uriDir = os.path.dirname(normalizedUri)
        for i in range(modelXbrl.modelManager.disclosureSystem.maxSubmissionSubdirectoryEntryNesting):
            modelXbrl.uriDir = os.path.dirname(modelXbrl.uriDir)
    filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri, filenameOnly=True)
    if initialComment:
        initialComment = "<!--" + initialComment + "-->"
    # XML document has nsmap root element to replace nsmap as new xmlns entries are required
    if initialXml and type in (Type.INSTANCE, Type.SCHEMA, Type.LINKBASE, Type.RSSFEED):
        Xml = '<nsmap>{0}</nsmap>'.format(initialXml or '')
    elif type == Type.INSTANCE:
        # modelXbrl.uriDir = os.path.dirname(normalizedUri)
        Xml = ('<nsmap>{}'
               '<xbrl xmlns="http://www.xbrl.org/2003/instance"'
               ' xmlns:link="http://www.xbrl.org/2003/linkbase"'
               ' xmlns:xlink="http://www.w3.org/1999/xlink">').format(initialComment)
        if schemaRefs:
            for schemaRef in schemaRefs:
                Xml += '<link:schemaRef xlink:type="simple" xlink:href="{0}"/>'.format(schemaRef.replace("\\","/"))
        Xml += '</xbrl></nsmap>'
    elif type == Type.SCHEMA:
        Xml = ('<nsmap>{}<schema xmlns="http://www.w3.org/2001/XMLSchema" /></nsmap>').format(initialComment)
    elif type == Type.RSSFEED:
        Xml = '<nsmap><rss version="2.0" /></nsmap>'
    elif type == Type.DTSENTRIES:
        Xml = None
    else:
        type = Type.UnknownXML
        Xml = '<nsmap>{0}</nsmap>'.format(initialXml or '')
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
    INLINEXBRLDOCUMENTSET=7
    VERSIONINGREPORT=8
    TESTCASESINDEX=9
    TESTCASE=10
    REGISTRY=11
    REGISTRYTESTCASE=12
    XPATHTESTSUITE=13
    RSSFEED=14
    ARCSINFOSET=15
    FACTDIMSINFOSET=16
    
    TESTCASETYPES = (TESTCASESINDEX, TESTCASE, REGISTRY, REGISTRYTESTCASE, XPATHTESTSUITE)

    typeName = ("unknown XML",
                "unknown non-XML", 
                "schema", 
                "linkbase", 
                "instance", 
                "inline XBRL instance",
                "entry point set",
                "inline XBRL document set",
                "versioning report",
                "testcases index", 
                "testcase",
                "registry",
                "registry testcase",
                "xpath test suite",
                "RSS feed",
                "arcs infoset",
                "fact dimensions infoset")
    
    def identify(filesource, filepath):
        file, = filesource.file(filepath, stripDeclaration=True, binary=True)
        try:
            for _event, elt in etree.iterparse(file, events=("start",)):
                _type = {"{http://www.xbrl.org/2003/instance}xbrl": Type.INSTANCE,
                         "{http://www.xbrl.org/2003/linkbase}linkbase": Type.LINKBASE,
                         "{http://www.w3.org/2001/XMLSchema}schema": Type.SCHEMA}.get(elt.tag, Type.UnknownXML)
                if _type == Type.UnknownXML and elt.tag.endswith("html") and XbrlConst.ixbrlAll.intersection(elt.nsmap.values()):
                    _type = Type.INLINEXBRL
                break
        except Exception:
            _type = Type.UnknownXML
        file.close()
        return _type

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
        self.skipDTS = modelXbrl.skipDTS
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
        self.hrefObjects = []
        self.schemaLocationElements = set()
        self.referencedNamespaces = set()
        self.inDTS = False
        self.definesUTR = False


    def objectId(self,refId=""):
        return "_{0}_{1}".format(refId, self.objectIndex)
    
    # qname of root element of the document so modelDocument can be treated uniformly as modelObject
    @property
    def qname(self):
        try:
            return self._xmlRootElementQname
        except AttributeError:
            self._xmlRootElementQname = qname(self.xmlRootElement)
            return self._xmlRootElementQname

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

    def save(self, overrideFilepath=None, outputZip=None):
        """Saves current document file.
        
        :param overrideFilepath: specify to override saving in instance's modelDocument.filepath
        """
        if outputZip:
            fh = io.StringIO();
        else:
            fh = open( (overrideFilepath or self.filepath), "w", encoding='utf-8')
        XmlUtil.writexml(fh, self.xmlDocument, encoding="utf-8")
        if outputZip:
            fh.seek(0)
            outputZip.writestr(os.path.basename(overrideFilepath or self.filepath),fh.read())
        fh.close()
    
    def close(self, visited=None, urlDocs=None):
        if visited is None: visited = []
        visited.append(self)
        # note that self.modelXbrl has been closed/dereferenced already, do not use in plug in
        for pluginMethod in pluginClassMethods("ModelDocument.CustomCloser"):
            pluginMethod(self)
        try:
            for referencedDocument, modelDocumentReference in self.referencesDocument.items():
                if referencedDocument not in visited:
                    referencedDocument.close(visited=visited,urlDocs=urlDocs)
                modelDocumentReference.__dict__.clear() # dereference its contents
            self.referencesDocument.clear()
            if self.type == Type.VERSIONINGREPORT:
                if self.fromDTS:
                    self.fromDTS.close()
                if self.toDTS:
                    self.toDTS.close()
            urlDocs.pop(self.uri,None)
            xmlDocument = self.xmlDocument
            dummyRootElement = self.parser.makeelement("{http://dummy}dummy") # may fail for streaming
            for modelObject in self.xmlRootElement.iter():
                modelObject.__dict__.clear() # clear python variables of modelObjects (not lxml)
            self.xmlRootElement.clear() # clear entire lxml subtree
            self.parserLookupName.__dict__.clear()
            self.parserLookupClass.__dict__.clear()
            self.__dict__.clear() # dereference everything before clearing xml tree
            if dummyRootElement is not None:
                xmlDocument._setroot(dummyRootElement)
            del dummyRootElement
        except AttributeError:
            pass    # maybe already cloased
        if len(visited) == 1:  # outer call
            while urlDocs:
                urlDocs.popitem()[1].close(visited=visited,urlDocs=urlDocs)
        visited.remove(self)
        
    def gettype(self):
        try:
            return Type.typeName[self.type]
        except AttributeError:
            return "unknown"
        
    @property
    def creationSoftwareComment(self):
        try:
            return self._creationSoftwareComment
        except AttributeError:
            # first try for comments before root element
            initialComment = ''
            node = self.xmlRootElement
            while node.getprevious() is not None:
                node = node.getprevious()
                if isinstance(node, etree._Comment):
                    initialComment = node.text + '\n' + initialComment
            if initialComment:
                self._creationSoftwareComment = initialComment
            else:
                self._creationSoftwareComment = None
                for i, node in enumerate(self.xmlDocument.iter()):
                    if isinstance(node, etree._Comment):
                        self._creationSoftwareComment = node.text
                    if i > 10:  # give up, no heading comment
                        break
            return self._creationSoftwareComment
    
    @property
    def creationSoftware(self):
        global creationSoftwareNames
        if creationSoftwareNames is None:
            import json, re
            creationSoftwareNames = []
            try:
                with io.open(os.path.join(self.modelXbrl.modelManager.cntlr.configDir, "creationSoftwareNames.json"), 
                             'rt', encoding='utf-8') as f:
                    for key, pattern in json.load(f):
                        if key != "_description_":
                            creationSoftwareNames.append( (key, re.compile(pattern, re.IGNORECASE)) )
            except Exception as ex:
                self.modelXbrl.error("arelle:creationSoftwareNamesTable",
                                     _("Error loading creation software names table %(error)s"),
                                     modelObject=self, error=ex)
        creationSoftwareComment = self.creationSoftwareComment
        if not creationSoftwareComment:
            return "None"
        for productKey, productNamePattern in creationSoftwareNames:
            if productNamePattern.search(creationSoftwareComment):
                return productKey
        return creationSoftwareComment # "Other"
    
    @property
    def processingInstructions(self):
        try:
            return self._processingInstructions
        except AttributeError:
            self._processingInstructions = []
            node = self.xmlRootElement
            while node.getprevious() is not None:
                node = node.getprevious()
                if isinstance(node, etree._ProcessingInstruction):
                    self._processingInstructions.append(node)
            return self._processingInstructions
    
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
                            modelObject=rootElement, namespace=targetNamespace, schemaLocation=self.uri, url=self.uri,
                            messageCodes=("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06", "SBR.NL.2.2.0.17"))
            self.noTargetNamespace = False
        else:
            if isIncluded == True and namespace:
                self.targetNamespace = namespace
                self.modelXbrl.namespaceDocs[targetNamespace].append(self)
            self.noTargetNamespace = True
        if targetNamespace == XbrlConst.xbrldt:
            # BUG: should not set this if obtained from schemaLocation instead of import (but may be later imported)
            self.modelXbrl.hasXDT = True
        self.isQualifiedElementFormDefault = rootElement.get("elementFormDefault") == "qualified"
        self.isQualifiedAttributeFormDefault = rootElement.get("attributeFormDefault") == "qualified"
        # self.definesUTR = any(ns == XbrlConst.utr for ns in rootElement.nsmap.values())
        try:
            self.schemaDiscoverChildElements(rootElement)
        except (ValueError, LookupError) as err:
            self.modelXbrl.modelManager.addToLog("discovery: {0} error {1}".format(
                        self.basename,
                        err))
        if not isIncluded:
            if targetNamespace: 
                nsDocs = self.modelXbrl.namespaceDocs
                if targetNamespace in nsDocs and nsDocs[targetNamespace].index(self) == 0:
                    for doc in nsDocs[targetNamespace]: # includes self and included documents of this namespace
                        self.modelXbrl.schemaDocsToValidate.add(doc) # validate after all schemas are loaded
            else:  # no target namespace, no includes to worry about order of validation
                self.modelXbrl.schemaDocsToValidate.add(self) # validate schema elements

            
    def schemaDiscoverChildElements(self, parentModelObject):
        # find roleTypes, elements, and linkbases
        # must find import/include before processing linkbases or elements
        for modelObject in parentModelObject.iterchildren():
            if isinstance(modelObject,ModelObject):
                ln = modelObject.localName
                ns = modelObject.namespaceURI
                if modelObject.namespaceURI == XbrlConst.xsd and ln in {"import", "include", "redefine"}:
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
                    self.modelXbrl.error(("EFM.6.03.11", "GFM.1.1.7", "EBA.2.1", "EIOPA.2.1"),
                        _("Prohibited base attribute: %(attribute)s"),
                        modelObject=element, attribute=baseAttr, element=element.qname)
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
                return os.path.dirname(self.uri) + "/" + base
        return self.uri
            
    def importDiscover(self, element):
        schemaLocation = element.get("schemaLocation")
        if element.localName in ("include", "redefine"): # add redefine, loads but type definitons of redefine not processed yet (See below)
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
                        modelObject=element, namespace=importNamespace, schemaLocation=importSchemaLocation, url=importSchemaLocation,
                        messageCodes=("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06", "SBR.NL.2.2.0.17"))
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
            if doc is not None and doc not in self.referencesDocument:
                self.referencesDocument[doc] = ModelDocumentReference(element.localName, element)  #import or include
                self.referencedNamespaces.add(importNamespace)
            # future note: for redefine, if doc was just loaded, process redefine type definitions
                
    def schemalocateElementNamespace(self, element):
        if isinstance(element,ModelObject):
            eltNamespace = element.namespaceURI 
            if eltNamespace not in self.modelXbrl.namespaceDocs and eltNamespace not in self.referencedNamespaces:
                schemaLocationElement = XmlUtil.schemaLocation(element, eltNamespace, returnElement=True)
                if schemaLocationElement is not None:
                    self.schemaLocationElements.add(schemaLocationElement)
                    self.referencedNamespaces.add(eltNamespace)

    def loadSchemalocatedSchemas(self):
        # schemaLocation requires loaded schemas for validation
        if self.skipDTS:
            return
        for elt in self.schemaLocationElements:
            schemaLocation = elt.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
            if schemaLocation:
                ns = None
                for entry in schemaLocation.split():
                    if ns is None:
                        ns = entry
                    else:
                        if self.type == Type.INLINEXBRL and ns == XbrlConst.xhtml:
                            pass # skip schema validation of inline XBRL
                        elif ns not in self.modelXbrl.namespaceDocs:
                            loadSchemalocatedSchema(self.modelXbrl, elt, entry, ns, self.baseForElement(elt))
                        ns = None
                        
    def schemaLinkbaseRefsDiscover(self, tree):
        for refln in ("{http://www.xbrl.org/2003/linkbase}schemaRef", "{http://www.xbrl.org/2003/linkbase}linkbaseRef"):
            for element in tree.iterdescendants(tag=refln):
                if isinstance(element,ModelObject):
                    self.schemaLinkbaseRefDiscover(element)

    def schemaLinkbaseRefDiscover(self, element):
        return self.discoverHref(element, urlRewritePluginClass="ModelDocument.InstanceSchemaRefRewriter")
    
    def linkbasesDiscover(self, tree):
        for linkbaseElement in tree.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}linkbase"):
            if isinstance(linkbaseElement,ModelObject):
                self.linkbaseDiscover(self, linkbaseElement)

    def linkbaseDiscover(self, linkbaseElement, inInstance=False):
        # sequence linkbase elements for elementPointer efficiency
        lbElementSequence = 0
        for lbElement in linkbaseElement:
            if isinstance(lbElement,ModelObject):
                lbElementSequence += 1
                lbElement._elementSequence = lbElementSequence
                lbLn = lbElement.localName
                lbNs = lbElement.namespaceURI
                if lbNs == XbrlConst.link:
                    if lbLn == "roleRef" or lbLn == "arcroleRef":
                        href = self.discoverHref(lbElement)
                        if href is None:
                            self.modelXbrl.error("xmlSchema:requiredAttribute",
                                    _("Linkbase reference for %(linkbaseRefElement)s href attribute missing or malformed"),
                                    modelObject=lbElement, linkbaseRefElement=lbLn)
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
                        linkElementSequence = 0
                        for linkElement in lbElement.iterchildren():
                            if isinstance(linkElement,ModelObject):
                                linkElementSequence += 1
                                linkElement._elementSequence = linkElementSequence
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
                                                    _('Locator href attribute "%(href)s" missing or malformed in standard extended link'),
                                                    modelObject=linkElement, href=linkElement.get("{http://www.w3.org/1999/xlink}href"))
                                        else:
                                            self.modelXbrl.warning("arelle:hrefWarning",
                                                    _('Locator href attribute "%(href)s" missing or malformed in non-standard extended link'),
                                                    modelObject=linkElement, href=linkElement.get("{http://www.w3.org/1999/xlink}href"))
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
                                        if XbrlConst.isTableIndexingArcrole(arcrole):
                                            self.modelXbrl.hasTableIndexing = True
                                        for baseSetKey in baseSetKeys:
                                            self.modelXbrl.baseSets[baseSetKey].append(lbElement)
                                        arcrolesFound.add(arcrole)
                                elif xlinkType == "resource": 
                                    # create resource and make accessible by id for document
                                    modelResource = linkElement
                                    for resourceElt in linkElement.iter(): # check resource element schemaLocations
                                        self.schemalocateElementNamespace(resourceElt)
                                if modelResource is not None:
                                    lbElement.labeledResources[linkElement.get("{http://www.w3.org/1999/xlink}label")] \
                                        .append(modelResource)
                    else:
                        self.modelXbrl.error("xbrl:schemaDefinitionMissing",
                                _("Linkbase extended link %(element)s missing schema definition"),
                                modelObject=lbElement, element=lbElement.prefixedName)
                
    def discoverHref(self, element, nonDTS=False, urlRewritePluginClass=None):
        href = element.get("{http://www.w3.org/1999/xlink}href")
        if href:
            url, id = UrlUtil.splitDecodeFragment(href)
            if url == "":
                doc = self
            else:
                # href discovery only can happein within a DTS
                if self.skipDTS: # no discovery
                    _newDoc = DocumentPrototype
                else:
                    _newDoc = load
                if urlRewritePluginClass:
                    for pluginMethod in pluginClassMethods(urlRewritePluginClass):
                        url = pluginMethod(self, url)
                doc = _newDoc(self.modelXbrl, url, isDiscovered=not nonDTS, base=self.baseForElement(element), referringElement=element)
                if not nonDTS and doc is not None and doc not in self.referencesDocument:
                    self.referencesDocument[doc] = ModelDocumentReference("href", element)
                    if not doc.inDTS and doc.type > Type.UnknownTypes:    # non-XBRL document is not in DTS
                        doc.inDTS = True    # now known to be discovered
                        if doc.type == Type.SCHEMA and not self.skipDTS: # schema coming newly into DTS
                            doc.schemaDiscoverChildElements(doc.xmlRootElement)
            href = (element, doc, id if len(id) > 0 else None)
            if doc is not None:  # if none, an error would have already been reported, don't multiply report it
                self.hrefObjects.append(href)
            return href
        return None
    
    def instanceDiscover(self, xbrlElement):
        self.schemaLinkbaseRefsDiscover(xbrlElement)
        if not self.skipDTS:
            self.linkbaseDiscover(xbrlElement,inInstance=True) # for role/arcroleRefs and footnoteLinks
        XmlValidate.validate(self.modelXbrl, xbrlElement) # validate instance elements (xValid may be UNKNOWN if skipDTS)
        self.instanceContentsDiscover(xbrlElement)

    def instanceContentsDiscover(self,xbrlElement):
        nextUndefinedFact = len(self.modelXbrl.undefinedFacts)
        instElementSequence = 0
        for instElement in xbrlElement.iterchildren():
            if isinstance(instElement,ModelObject):
                instElementSequence += 1
                instElement._elementSequence = instElementSequence
                ln = instElement.localName
                ns = instElement.namespaceURI
                if ns == XbrlConst.xbrli:
                    if ln == "context":
                        self.contextDiscover(instElement)
                    elif ln == "unit":
                        self.unitDiscover(instElement)
                elif ns == XbrlConst.link:
                    pass
                elif ns in XbrlConst.ixbrlAll and ln=="relationship":
                    pass
                else: # concept elements
                    self.factDiscover(instElement, self.modelXbrl.facts)
        if len(self.modelXbrl.undefinedFacts) > nextUndefinedFact:
            undefFacts = self.modelXbrl.undefinedFacts[nextUndefinedFact:]
            self.modelXbrl.error("xbrl:schemaImportMissing",
                    _("Instance facts missing schema definition: %(elements)s"),
                    modelObject=undefFacts, 
                    elements=", ".join(sorted(set(str(f.prefixedName) for f in undefFacts))))
                    
    def contextDiscover(self, modelContext):
        if not self.skipDTS:
            XmlValidate.validate(self.modelXbrl, modelContext) # validation may have not completed due to errors elsewhere
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
                            modelContext.qnameDims[sElt.dimensionQname] = sElt # both seg and scen
                            if not self.skipDTS:
                                dimension = sElt.dimension
                                if dimension is not None and dimension not in containerDimValues:
                                    containerDimValues[dimension] = sElt
                                else:
                                    modelContext.errorDimValues.append(sElt)
                        else:
                            containerNonDimValues.append(sElt)
                            
    def unitDiscover(self, unitElement):
        if not self.skipDTS:
            XmlValidate.validate(self.modelXbrl, unitElement) # validation may have not completed due to errors elsewhere
        self.modelXbrl.units[unitElement.id] = unitElement
                
    def inlineXbrlDiscover(self, htmlElement):
        if htmlElement.namespaceURI == XbrlConst.xhtml:  # must validate xhtml
            #load(self.modelXbrl, "http://www.w3.org/2002/08/xhtml/xhtml1-strict.xsd")
            XhtmlValidate.xhtmlValidate(self.modelXbrl, htmlElement)  # fails on prefixed content
            # validate ix element
            #self.schemalocateElementNamespace(htmlElement) # schemaLocate ix/xhtml schemas
            #self.loadSchemalocatedSchemas() # load ix/html schemas
            #XmlValidate.validate(self.modelXbrl, htmlElement, ixFacts=False)
        ixNS = None
        conflictingNSelts = []
        # find namespace, only 1 namespace
        for inlineElement in htmlElement.iterdescendants():
            if isinstance(inlineElement,ModelObject) and inlineElement.namespaceURI in XbrlConst.ixbrlAll:
                if ixNS is None:
                    ixNS = inlineElement.namespaceURI
                elif ixNS != inlineElement.namespaceURI:
                    conflictingNSelts.append(inlineElement)
        if conflictingNSelts:
            self.modelXbrl.error("ix:multipleIxNamespaces",
                    _("Multiple ix namespaces were found"),
                    modelObject=conflictingNSelts)
        self.ixNStag = ixNStag = "{" + ixNS + "}"
        for inlineElement in htmlElement.iterdescendants(tag=ixNStag + "references"):
            self.schemaLinkbaseRefsDiscover(inlineElement)
            XmlValidate.validate(self.modelXbrl, inlineElement) # validate instance elements
        if not hasattr(self.modelXbrl, "targetRoleRefs"):
            self.modelXbrl.targetRoleRefs = {}
            self.modelXbrl.targetArcroleRefs = {}
        for inlineElement in htmlElement.iterdescendants(tag=ixNStag + "resources"):
            self.instanceContentsDiscover(inlineElement)
            XmlValidate.validate(self.modelXbrl, inlineElement) # validate instance elements
            for refElement in inlineElement.iterchildren("{http://www.xbrl.org/2003/linkbase}roleRef"):
                self.modelXbrl.targetRoleRefs[refElement.get("roleURI")] = refElement
            for refElement in inlineElement.iterchildren("{http://www.xbrl.org/2003/linkbase}arcroleRef"):
                self.modelXbrl.targetArcroleRefs[refElement.get("arcroleURI")] = refElement
     
        # subsequent inline elements have to be processed after all of the document set is loaded
        if not hasattr(self.modelXbrl, "ixdsHtmlElements"):
            self.modelXbrl.ixdsHtmlElements = []
        self.modelXbrl.ixdsHtmlElements.append(htmlElement)
        
                
    def factDiscover(self, modelFact, parentModelFacts=None, parentElement=None):
        if parentModelFacts is None: # may be called with parentElement instead of parentModelFacts list
            if isinstance(parentElement, ModelFact) and parentElement.isTuple:
                parentModelFacts = parentElement.modelTupleFacts
            else:
                parentModelFacts = self.modelXbrl.facts
        if isinstance(modelFact, ModelFact):
            parentModelFacts.append( modelFact )
            self.modelXbrl.factsInInstance.add( modelFact )
            tupleElementSequence = 0
            for tupleElement in modelFact:
                if isinstance(tupleElement,ModelObject):
                    tupleElementSequence += 1
                    tupleElement._elementSequence = tupleElementSequence
                    if tupleElement.tag not in fractionParts:
                        self.factDiscover(tupleElement, modelFact.modelTupleFacts)
        else:
            self.modelXbrl.undefinedFacts.append(modelFact)
    
    def testcasesIndexDiscover(self, rootNode):
        for testcasesElement in rootNode.iter():
            if isinstance(testcasesElement,ModelObject) and testcasesElement.localName in ("testcases", "testSuite"):
                rootAttr = testcasesElement.get("root")
                if rootAttr:
                    base = os.path.join(os.path.dirname(self.filepath),rootAttr) + os.sep
                else:
                    base = self.filepath
                for testcaseElement in testcasesElement:
                    if isinstance(testcaseElement,ModelObject) and testcaseElement.localName in ("testcase", "testSetRef"):
                        uriAttr = testcaseElement.get("uri") or testcaseElement.get("{http://www.w3.org/1999/xlink}href")
                        if uriAttr:
                            doc = load(self.modelXbrl, uriAttr, base=base, referringElement=testcaseElement)
                            if doc is not None and doc not in self.referencesDocument:
                                self.referencesDocument[doc] = ModelDocumentReference("testcaseIndex", testcaseElement)

    def testcaseDiscover(self, testcaseElement):
        isTransformTestcase = testcaseElement.namespaceURI == "http://xbrl.org/2011/conformance-rendering/transforms"
        if XmlUtil.xmlnsprefix(testcaseElement, XbrlConst.cfcn) or isTransformTestcase:
            self.type = Type.REGISTRYTESTCASE
        self.outpath = self.xmlRootElement.get("outpath") 
        self.testcaseVariations = []
        priorTransformName = None
        for modelVariation in XmlUtil.descendants(testcaseElement, testcaseElement.namespaceURI, ("variation", "testGroup")):
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
            if XbrlConst.ixbrlAll.intersection(testcaseElement.values()):
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
                            if testcaseDoc is not None and testcaseDoc not in self.referencesDocument:
                                self.referencesDocument[testcaseDoc] = ModelDocumentReference("registryIndex", testUriElt)
            
    def xPathTestSuiteDiscover(self, rootNode):
        # no child documents to reference
        pass
    
# inline document set level compilation
def inlineIxdsDiscover(modelXbrl):
    # compile inline result set
    footnoteRefs = defaultdict(list)
    tupleElements = []
    continuationElements = {}
    continuationReferences = defaultdict(set) # set of elements that have continuedAt source value
    tuplesByTupleID = {}
    for htmlElement in modelXbrl.ixdsHtmlElements:  
        mdlDoc = htmlElement.modelDocument
        for modelInlineTuple in htmlElement.iterdescendants(tag=mdlDoc.ixNStag + "tuple"):
            if isinstance(modelInlineTuple,ModelObject):
                modelInlineTuple.unorderedTupleFacts = []
                if modelInlineTuple.tupleID:
                    tuplesByTupleID[modelInlineTuple.tupleID] = modelInlineTuple
                tupleElements.append(modelInlineTuple)
                for r in modelInlineTuple.footnoteRefs:
                    footnoteRefs[r].append(modelInlineTuple)
        for elt in htmlElement.iterdescendants(tag=mdlDoc.ixNStag + "continuation"):
            if isinstance(elt,ModelObject) and elt.id:
                continuationElements[elt.id] = elt
                    
    def locateFactInTuple(modelFact, tuplesByTupleID, ixNStag):
        tupleRef = modelFact.tupleRef
        tuple = None
        if tupleRef:
            if tupleRef not in tuplesByTupleID:
                modelXbrl.error("ix:tupleRefMissing",
                                _("Inline XBRL tupleRef %(tupleRef)s not found"),
                                modelObject=modelFact, tupleRef=tupleRef)
            else:
                tuple = tuplesByTupleID[tupleRef]
        else:
            for tupleParent in modelFact.iterancestors(tag=ixNStag + "tuple"):
                tuple = tupleParent
                break
        if tuple is not None:
            tuple.unorderedTupleFacts.append((modelFact.order, modelFact.objectIndex))
        else:
            modelXbrl.modelXbrl.facts.append(modelFact)
            
    def locateContinuation(element, chain=None):
        contAt = element.get("continuedAt")
        if contAt:
            continuationReferences[contAt].add(element)
            if contAt not in continuationElements:
                if contAt in element.modelDocument.idObjects:
                    _contAtTarget = element.modelDocument.idObjects[contAt]
                    modelXbrl.error("ix:continuationTarget",
                                    _("continuedAt %(continuationAt)s target is an %(targetElement)s element instead of ix:continuation element."),
                                    modelObject=(element, _contAtTarget), continuationAt=contAt, targetElement=_contAtTarget.elementQname)
                else:
                    modelXbrl.error("ix:continuationMissing",
                                    _("Inline XBRL continuation %(continuationAt)s not found"),
                                    modelObject=element, continuationAt=contAt)
            else:
                if chain is None: chain = [element]
                contElt = continuationElements[contAt]
                if contElt in chain:
                    cycle = ", ".join(e.get("continuedAt") for e in chain)
                    chain.append(contElt) # makes the cycle clear
                    modelXbrl.error("ix:continuationCycle",
                                    _("Inline XBRL continuation cycle: %(continuationCycle)s"),
                                    modelObject=chain, continuationCycle=cycle)
                else:
                    chain.append(contElt)
                    element._continuationElement = contElt
                    locateContinuation(contElt, chain)
        elif chain: # end of chain
            # check if any chain element is descendant of another
            chainSet = set(chain)
            for chainElt in chain:
                for chainEltAncestor in chainElt.iterancestors(tag=chainElt.modelDocument.ixNStag + '*'):
                    if chainEltAncestor in chainSet:
                        if hasattr(chain[0], "_continuationElement"):
                            del chain[0]._continuationElement # break chain to prevent looping in chain
                        modelXbrl.error("ix:continuationChainNested",
                                        _("Inline XBRL continuation chain element %(ancestorElement)s has descendant element %(descendantElement)s"),
                                        modelObject=(chainElt,chainEltAncestor), 
                                        ancestorElement=chainEltAncestor.id or chainEltAncestor.get("name",chainEltAncestor.get("continuedAt")),
                                        descendantElement=chainElt.id or chainElt.get("name",chainElt.get("continuedAt")))
                        

    for htmlElement in modelXbrl.ixdsHtmlElements:  
        mdlDoc = htmlElement.modelDocument
        ixNStag = mdlDoc.ixNStag
        # hook up tuples to their container
        for tupleFact in tupleElements:
            locateFactInTuple(tupleFact, tuplesByTupleID, ixNStag)

        factTags = set(ixNStag + ln for ln in ("nonNumeric", "nonFraction", "fraction"))
        for tag in factTags:
            for modelInlineFact in htmlElement.iterdescendants(tag=tag):
                if isinstance(modelInlineFact,ModelInlineFact):
                    mdlDoc.modelXbrl.factsInInstance.add( modelInlineFact )
                    locateFactInTuple(modelInlineFact, tuplesByTupleID, ixNStag)
                    locateContinuation(modelInlineFact)
                    for r in modelInlineFact.footnoteRefs:
                        footnoteRefs[r].append(modelInlineFact)
        # order tuple facts
        for tupleFact in tupleElements:
            tupleFact.modelTupleFacts = [
                 mdlDoc.modelXbrl.modelObject(objectIndex) 
                 for order,objectIndex in sorted(tupleFact.unorderedTupleFacts)]
                        
        # validate particle structure of elements after transformations and established tuple structure
        for rootModelFact in modelXbrl.facts:
            # validate XBRL (after complete document set is loaded)
            XmlValidate.validate(modelXbrl, rootModelFact, ixFacts=True)
            
    footnoteLinkPrototypes = {}
    for htmlElement in modelXbrl.ixdsHtmlElements:  
        mdlDoc = htmlElement.modelDocument
        # inline 1.0 ixFootnotes, build resources (with ixContinuation)
        for modelInlineFootnote in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrlFootnote.clarkNotation):
            if isinstance(modelInlineFootnote,ModelObject):
                # link
                linkrole = modelInlineFootnote.get("footnoteLinkRole", XbrlConst.defaultLinkRole)
                arcrole = modelInlineFootnote.get("arcrole", XbrlConst.factFootnote)
                footnoteID = modelInlineFootnote.footnoteID or ""
                footnoteLocLabel = footnoteID + "_loc"
                if linkrole in footnoteLinkPrototypes:
                    linkPrototype = footnoteLinkPrototypes[linkrole]
                else:
                    linkPrototype = LinkPrototype(mdlDoc, mdlDoc.xmlRootElement, XbrlConst.qnLinkFootnoteLink, linkrole)
                    footnoteLinkPrototypes[linkrole] = linkPrototype
                    for baseSetKey in (("XBRL-footnotes",None,None,None), 
                                       ("XBRL-footnotes",linkrole,None,None),
                                       (arcrole,linkrole,XbrlConst.qnLinkFootnoteLink, XbrlConst.qnLinkFootnoteArc), 
                                       (arcrole,linkrole,None,None),
                                       (arcrole,None,None,None)):
                        modelXbrl.baseSets[baseSetKey].append(linkPrototype)
                # locs
                for modelFact in footnoteRefs[footnoteID]:
                    locPrototype = LocPrototype(mdlDoc, linkPrototype, footnoteLocLabel, modelFact)
                    linkPrototype.childElements.append(locPrototype)
                    linkPrototype.labeledResources[footnoteLocLabel].append(locPrototype)
                # resource
                linkPrototype.childElements.append(modelInlineFootnote)
                linkPrototype.labeledResources[footnoteID].append(modelInlineFootnote)
                # arc
                linkPrototype.childElements.append(ArcPrototype(mdlDoc, linkPrototype, XbrlConst.qnLinkFootnoteArc,
                                                                footnoteLocLabel, footnoteID,
                                                                linkrole, arcrole))
                
        # inline 1.1 link prototypes, one per link role (so only one extended link element is produced per link role)
        linkPrototypes = {}
        for modelInlineRel in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrl11Relationship.clarkNotation):
            if isinstance(modelInlineRel,ModelObject):
                linkrole = modelInlineRel.get("linkRole", XbrlConst.defaultLinkRole)
                if linkrole not in linkPrototypes:
                    linkPrototypes[linkrole] = LinkPrototype(mdlDoc, mdlDoc.xmlRootElement, XbrlConst.qnLinkFootnoteLink, linkrole) 
                    
        # inline 1.1 ixRelationships and ixFootnotes
        modelInlineFootnotesById = {}
        linkModelInlineFootnoteIds = defaultdict(set)
        linkModelLocIds = defaultdict(set)
        
        for modelInlineFootnote in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrl11Footnote.clarkNotation):
            if isinstance(modelInlineFootnote,ModelObject):
                locateContinuation(modelInlineFootnote)
                modelInlineFootnotesById[modelInlineFootnote.footnoteID] = modelInlineFootnote

        for modelInlineRel in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrl11Relationship.clarkNotation):
            if isinstance(modelInlineRel,ModelObject):
                linkrole = modelInlineRel.get("linkRole", XbrlConst.defaultLinkRole)
                arcrole = modelInlineRel.get("arcrole", XbrlConst.factFootnote)
                linkPrototype = linkPrototypes[linkrole]
                for baseSetKey in (("XBRL-footnotes",None,None,None), 
                                   ("XBRL-footnotes",linkrole,None,None),
                                   (arcrole,linkrole,XbrlConst.qnLinkFootnoteLink, XbrlConst.qnLinkFootnoteArc), 
                                   (arcrole,linkrole,None,None),
                                   (arcrole,None,None,None)):
                    if linkPrototype not in modelXbrl.baseSets[baseSetKey]: # only one link per linkrole
                        modelXbrl.baseSets[baseSetKey].append(linkPrototype)
                fromLabels = set()
                for fromId in modelInlineRel.get("fromRefs","").split():
                    fromLabels.add(fromId)
                    if fromId not in linkModelLocIds:
                        locPrototype = LocPrototype(mdlDoc, linkPrototype, fromId, fromId)
                        linkPrototype.childElements.append(locPrototype)
                        linkPrototype.labeledResources[fromId].append(locPrototype)
                toLabels = set()
                toFootnoteIds = set()
                toFactQnames = set()
                for toId in modelInlineRel.get("toRefs","").split():
                    toLabels.add(toId)
                    if toId in modelInlineFootnotesById:
                        toFootnoteIds.add(toId)
                        modelInlineFootnote = modelInlineFootnotesById[toId]
                        if toId not in linkModelInlineFootnoteIds[linkrole]:
                            linkPrototype.childElements.append(modelInlineFootnote)
                            linkModelInlineFootnoteIds[linkrole].add(toId)
                        linkPrototype.labeledResources[toId].append(modelInlineFootnote)
                    else:
                        locPrototype = LocPrototype(mdlDoc, linkPrototype, toId, toId)
                        toFactQnames.add(str(locPrototype.dereference().qname))
                        linkPrototype.childElements.append(locPrototype)
                        linkPrototype.labeledResources[toId].append(locPrototype)
                for fromLabel in fromLabels:
                    for toLabel in toLabels: 
                        linkPrototype.childElements.append(ArcPrototype(mdlDoc, linkPrototype, XbrlConst.qnLinkFootnoteArc,
                                                                        fromLabel, toLabel,
                                                                        linkrole, arcrole,
                                                                        modelInlineRel.get("order", "1")))
                if toFootnoteIds and toFactQnames:
                    modelXbrl.error("ix:relationshipReferencesMixed",
                                    _("Inline relationship references footnote(s) %(toFootnoteIds)s and thereby is not allowed to reference %(toFactQnames)s."),
                                    modelObject=modelInlineRel, toFootnoteIds=', '.join(sorted(toFootnoteIds)), 
                                    toFactQnames=', '.join(sorted(toFactQnames)))

        del linkPrototypes, modelInlineFootnotesById, linkModelInlineFootnoteIds # dereference
        
    # check for multiple use of continuation reference (same continuationAt on different elements)
    for _contAt, _contReferences in continuationReferences.items():
        if len(_contReferences) > 1:
            _refEltQnames = set(str(_contRef.elementQname) for _contRef in _contReferences)
            modelXbrl.error("ix:continuationReferences",
                            _("continuedAt %(continuedAt)s has %(referencesCount)s references on %(sourceElements)s elements, only one reference allowed."),
                            modelObject=_contReferences, continuedAt=_contAt, referencesCount=len(_contReferences), 
                            sourceElements=', '.join(str(qn) for qn in sorted(_refEltQnames)))
                
    del modelXbrl.ixdsHtmlElements # dereference
    
class LoadingException(Exception):
    pass

class ModelDocumentReference:
    def __init__(self, referenceType, referringModelObject=None):
        self.referenceType = referenceType
        self.referringModelObject = referringModelObject

