from arelle_c.xerces_ctypes cimport XMLCh, XMLSize_t
from arelle_c.xerces_util cimport compareString, compareIString, transcode, release,  \
        XMLResourceIdentifier, XMLEntityResolver, ResourceIdentifierType
from arelle_c.xerces_sax cimport SAXParseException, ErrorHandler, EntityResolver
from arelle_c.xerces_framework cimport XMLPScanToken
from arelle_c.xerces_parsers cimport XercesDOMParser
from arelle_c.xerces_sax2 cimport createXMLReader, SAX2XMLReader, SAX2XMLReaderImpl, ContentHandler, LexicalHandler, DefaultHandler
from arelle_c.xerces_sax cimport InputSource, DocumentHandler, ErrorHandler, SAXParseException, Locator
from arelle_c.xerces_sax2 cimport Attributes
from arelle_c.xerces_uni cimport fgSAX2CoreNameSpaces, fgSAX2CoreValidation, fgXercesDynamic, fgXercesLoadSchema, fgXercesSchema, \
        fgXercesSchemaFullChecking, fgSGXMLScanner, fgSAX2CoreNameSpacePrefixes, fgXercesValidateAnnotations, \
        fgXercesScannerName, fgXercesGenerateSyntheticAnnotations, fgXercesSchemaExternalSchemaLocation, \
        fgXercesCacheGrammarFromParse, fgXercesCalculateSrcOfs
from arelle_c.xerces_validators cimport SchemaGrammar, GrammarType
from cython.operator cimport dereference as deref
from libcpp cimport bool
from libcpp.vector cimport vector
from libc.stdlib cimport malloc, free
from cpython.mem cimport PyMem_Malloc, PyMem_Realloc, PyMem_Free

cdef struct Namespace:
    void* pyNamespaceUri
    int   xercesUriId

cdef class ModelXbrl:
    cdef readonly object modelManager
    cdef readonly object cntlr
    cdef readonly dict urlDocs # ModelDocument indexbed by normalizedUrl
    cdef readonly dict mappedUrls # document urls normalizedUrl indexed by filename system id
    cdef SAX2XMLReader* sax2_parser
    cdef XercesDOMParser* dom_parser
    cdef vector[Namespace*] namespaces # namespace unicode strings known to dts
    cdef dict internedStrings # index by string of it's intern'ed (unique) value
    
    
    def __init__(self, modelManager):
        self.modelManager = modelManager
        self.cntlr = modelManager.cntlr
        self.sax2_parser = NULL
        self.dom_parser = NULL
        self.internedStrings = dict()
        self.urlDocs = dict()
        self.mappedUrls = dict()
                
    def close(self):
        if self.sax2_parser != NULL:
            del self.sax2_parser
            self.sax2_parser = NULL
        self.internStrings.clear()
        
    cpdef internString(self, unicode str):
        if str is None:
            return None
        # if string is in internStrings return an interned version of str, otherwise intern str
        return self.internedStrings.setdefault(str, str)
            
    
    # @@@@ moved to ModelDocument
    #def loadSchema(self, object modelDocument, object pyFileDesc):
    #    self.openSax2Parser()
    #    cdef void* modelDocumentPtr = <void*>modelDocument
    #    cdef ModelXbrlSAX2Handler* SAX2Handler = <ModelXbrlSAX2Handler*>self.sax2_parser.getContentHandler()
    #    SAX2Handler.setModelDocument(modelDocumentPtr)
    #    cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
    #    cdef SchemaGrammar* schemaGrammar = <SchemaGrammar*>self.sax2_parser.loadGrammar( deref( inpSrc ), GrammarType.SchemaGrammarType, True)
    #    assert schemaGrammar != NULL, "arelle:loadSchema schema grammar not loaded, null results"
    #    cdef XMLCh* xmlChTargetNS = <XMLCh*>schemaGrammar.getTargetNamespace()
    #    cdef char* targetNs = transcode(xmlChTargetNS)
    #    modelDocument.targetNamespace = targetNs
    #    release(&targetNs)
        
        
        
    #    SAX2Handler.setModelDocument(NULL) # dereference modelDocument
        
    
    
    #def loadXml(self, object modelDocument, object pyFileDesc, object schemaLocationsList):
    #    self.openSax2Parser()
    #    cdef void* modelDocumentPtr = <void*>modelDocument
    #    cdef ModelXbrlSAX2Handler* SAX2Handler = <ModelXbrlSAX2Handler*>self.sax2_parser.getContentHandler()
    #    SAX2Handler.setModelDocument(modelDocumentPtr)
    #    cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
    #    byte_s = " ".join(schemaLocationsList).encode("utf-8")
    #    cdef char* c_s = byte_s
    #    cdef XMLCh* xmlChSchemaLocation = transcode(c_s)
    #    self.sax2_parser.setProperty(fgXercesSchemaExternalSchemaLocation, xmlChSchemaLocation)
    #    self.sax2_parser.parse(deref(inpSrc))
    #    release(&xmlChSchemaLocation)
        
    #    SAX2Handler.setModelDocument(NULL) # dereference modelDocument
        
    def identifyXmlFile(self, pyFileDesc):
        
        # open a minimal parser for examining elements without any schema or further checking
        cdef SAX2XMLReader* parser = createXMLReader()
        parser.setFeature(fgXercesLoadSchema, False)
        parser.setFeature(fgSAX2CoreNameSpacePrefixes, True)
        cdef object pyIdentificationResults = genobj(type=u"unknown XML", 
                                                     schemaRefs=set(), 
                                                     linkbaseRefs=set(), 
                                                     nonDtsSchemaRefs=set(),
                                                     targetNamespace=None,
                                                     targetNamespacePrefix=None,
                                                     errors=[])
        cdef void* pyIdentificationResultsPtr = <void*>pyIdentificationResults
        cdef ModelXbrlIdentificationSAX2Handler * identificationSax2Handler = new ModelXbrlIdentificationSAX2Handler(pyIdentificationResultsPtr)
        parser.setErrorHandler(identificationSax2Handler)
        parser.setContentHandler(identificationSax2Handler)
        parser.setLexicalHandler(identificationSax2Handler)
        cdef void* modelXbrlPtr = <void*>self
        cdef ModelXbrlEntityResolver * modelXbrlEntityResolver = new ModelXbrlEntityResolver(modelXbrlPtr)
        cdef SAX2XMLReaderImpl* sax2parser = <SAX2XMLReaderImpl*>parser
        sax2parser.setXMLEntityResolver(modelXbrlEntityResolver)
        cdef XMLPScanToken* token = new XMLPScanToken()
        cdef bool result
        cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
        result = parser.parseFirst(deref(inpSrc), deref(token) )
        while result:
            if identificationSax2Handler.isIdentified:
                parser.parseReset(deref(token))
                token = NULL
                break
            result = parser.parseNext(deref(token))
        del parser
        identificationSax2Handler.close()
        del identificationSax2Handler
        modelXbrlEntityResolver.close()
        del modelXbrlEntityResolver
        return pyIdentificationResults

    def loadSchemaGrammar(self):
        # find any newly-discovered namespaces in schemaGrammar to load elements and types
        cdef bool modelWasChanged = 0 # true if this is a first time call and a new model is created
        cdef XSModel* xsModel = xerces_grammar_pool.getXSModel(modelWasChanged)
        cdef StringList *namespaces
        cdef const StringList *namespaceDocumentLocations
        cdef XSNamespaceItemList *namespaceItems
        cdef XSNamespaceItem* namespaceItem
        cdef XMLSize_t namespacesSize
        cdef unsigned int i
        cdef const XMLCh* xmlChStr
        cdef char* chStr
        cdef unicode ns
        cdef unicode docUrl
        cdef XSNamedMap[XSObject]* xsObjects
        cdef XMLSize_t j
        cdef ModelDocument modelDocument
        if xsModel != NULL:
            namespaceItems = xsModel.getNamespaceItems()
            namespacesSize = namespaceItems.size()
            for i in range(namespacesSize):
                namespaceItem = namespaceItems.elementAt(i)
                if namespaceItem == NULL:
                    continue
                chStr = transcode(namespaceItem.getSchemaNamespace())
                ns = chStr
                release(&chStr)
                docUrl = None
                namespaceDocumentLocations = namespaceItem.getDocumentLocations()
                if namespaceDocumentLocations != NULL:
                    for j in range(namespaceDocumentLocations.size()):
                        xmlChStr = namespaceDocumentLocations.elementAt(j)
                        if xmlChStr != NULL:
                            chStr = transcode(xmlChStr)
                            docUri = chStr
                            release(&chStr)
                # must have a modelDocument to proceed
                if not ns or not docUrl or self.mappedUrls.get(docUrl,docUrl) not in self.urlDocs:
                    continue
                modelDocument = self.urlDocs[self.mappedUrls.get(docUri,docUri)]
                if modelDocument.isGrammarLoadedIntoModel:
                    print("skipping load schema grammar ns {} doc {}".format(ns, docUrl))
                    continue
                print("load schema grammar ns {} doc {}".format(ns, docUrl))
                # load element defintions

                # end of namespace
    
    def openSax2Parser(self):
        if self.sax2_parser != NULL:
            return
        assert self.dom_parser == NULL, "setupSAX2parser: DOM parser is already set up"
        cdef void* modelXbrlPtr = <void*>self
        self.sax2_parser = createXMLReader(fgMemoryManager, xerces_grammar_pool)
        self.sax2_parser.setProperty(fgXercesScannerName, <void *>fgSGXMLScanner)
        self.sax2_parser.setFeature(fgSAX2CoreNameSpaces, True)
        self.sax2_parser.setFeature(fgXercesSchema, True)
        self.sax2_parser.setFeature(fgXercesSchemaFullChecking, True)
        self.sax2_parser.setFeature(fgSAX2CoreNameSpacePrefixes, True)
        self.sax2_parser.setFeature(fgSAX2CoreValidation, True)
        self.sax2_parser.setFeature(fgXercesDynamic, True)
        self.sax2_parser.setFeature(fgXercesValidateAnnotations, True)
        self.sax2_parser.setFeature(fgXercesGenerateSyntheticAnnotations, True)
        self.sax2_parser.setFeature(fgXercesCacheGrammarFromParse, True)
        self.sax2_parser.setFeature(fgXercesCalculateSrcOfs, True)
        cdef ModelDocumentSAX2Handler* SAX2Handler = new ModelDocumentSAX2Handler(modelXbrlPtr)
        self.sax2_parser.setErrorHandler(SAX2Handler)
        self.sax2_parser.setContentHandler(SAX2Handler)
        self.sax2_parser.setLexicalHandler(SAX2Handler)
        cdef ModelXbrlEntityResolver* modelXbrlEntityResolver = new ModelXbrlEntityResolver(modelXbrlPtr)
        cdef SAX2XMLReaderImpl* sax2xmlRdrImpl = <SAX2XMLReaderImpl*>self.sax2_parser
        sax2xmlRdrImpl.setXMLEntityResolver(modelXbrlEntityResolver)
        
cdef cppclass ModelXbrlErrorHandler(TemplateSAX2Handler):
    void* _modelXbrl
    XMLCh** eltQNames
    unsigned int eltDepth

    ModelXbrlErrorHandler():
        this.eltQNames = <XMLCh**>malloc(1000 * sizeof(XMLCh*))
        this.eltDepth = 0
    
    # error handlers
    void logError(const SAXParseException& exc, level):
        cdef const XMLCh* msg = exc.getMessage()
        cdef char* msgText
        cdef char* fileName
        cdef char* url = NULL
        cdef char* eltQn
        if msg != NULL:
            msgText = transcode(msg)
        else:
            msgText = b"null"
        cdef const XMLCh* _file = exc.getSystemId()
        if _file != NULL:
            fileName = transcode(_file)
        else:
            fileName = b"null"
        if this.eltQNames[this.eltDepth] != NULL:
            eltQn = transcode(this.eltQNames[this.eltDepth])
        else:
            eltQn = b""
        pyError = genobj(level=level,
                         message=msgText,
                         line=exc.getLineNumber(),
                         column=exc.getColumnNumber(),
                         file=fileName,
                         element=eltQn)
        cdef const XMLCh* _url = exc.getPublicId()
        if _url != NULL:
            url = transcode(_file)
            pyError.url = url
        this.handlePyError(pyError)
        if msg != NULL:
            release(&msgText)
        if _file != NULL:
            release(&fileName)
        if this.eltQNames[this.eltDepth] != NULL:
            release(&eltQn)
        if url != NULL:
            release(&url)
    void error(const SAXParseException& exc):
        this.logError(exc, u"ERROR") # values for logging._checkLevel acceptability
    void fatalError(const SAXParseException& exc):
        this.logError(exc, u"CRITICAL")
    void warning(const SAXParseException& exc):
        this.logError(exc, u"WARNING")
        
    void handlePyError(object pyError):
        pass # implement in subclasses
        
cdef cppclass ModelXbrlIdentificationSAX2Handler(ModelXbrlErrorHandler):
    void* pyIdentificationResultsPtr
    bool isXbrl, isXsd, isHtml, isInline, isIdentified
    bool hasIxNamespace, hasIx11Namespace
    
    ModelXbrlIdentificationSAX2Handler(void* pyIdentificationResultsPtr) except +:
        this.pyIdentificationResultsPtr = pyIdentificationResultsPtr
        this.isXbrl = this.isXsd = this.isHtml = this.isInline = this.isIdentified = False
        this.hasIxNamespace = this.hasIx11Namespace = False
    void close():
        this.pyIdentificationResultsPtr = NULL
        free(this.eltQNames)
        this.eltQNames = NULL

    # document handlers
    void endElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname):
        this.eltQNames[this.eltDepth] = NULL
        this.eltDepth -= 1
    void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs):
        cdef object pyIdentificationResults
        cdef XMLSize_t i, n
        cdef object attrValue
        cdef const XMLCh* xmlCh
        cdef const XMLCh* xmlChNs
        cdef char* chStr
        
        pyIdentificationResults = <object>this.pyIdentificationResultsPtr
        if compareIString(uri, nsXbrli) == 0:
            if compareString(localname, lnXbrl) == 0:
                this.isXbrl = True
                pyIdentificationResults.type = u"instance"
        elif compareIString(uri, nsXsd) == 0:
            if compareString(localname, lnSchema) == 0:
                this.isXsd = True
                pyIdentificationResults.type = u"schema"
                attrValue = getAttrValue(attrs, nsNoNamespace, lnTargetNamespace)
                if attrValue is not None:
                    pyIdentificationResults.targetNamespace = attrValue
                    xmlChNs = attrs.getValue(nsNoNamespace, lnTargetNamespace)
                    # find any non-default xmlns for this namespace
                    n = attrs.getLength()
                    for i in range(n):
                        xmlCh = attrs.getQName(i)
                        if xmlCh != NULL and startsWith(xmlCh, xmlnsPrefix):
                            xmlCh = attrs.getValue(i)
                            if compareString(xmlCh, xmlChNs) == 0:
                                xmlCh = attrs.getLocalName(i)
                                chStr = transcode(xmlCh)
                                pyIdentificationResults.targetNamespacePrefix = chStr
                                release(&chStr)
                                break
        elif compareIString(uri, nsXhtml) == 0:
            if compareString(localname, lnXhtml) == 0 or compareString(localname, lnHtml) == 0:
                if this.hasIx11Namespace:
                    pyIdentificationResults.type = u"inline XBRL instance"
                    pyIdentificationResults.schemaRefs.add("http://www.xbrl.org/2013/inlineXBRL/xhtml-inlinexbrl-1_1.xsd")
                elif this.hasIxNamespace:
                    pyIdentificationResults.type = u"inline XBRL instance"
                    pyIdentificationResults.schemaRefs.add("http://www.xbrl.org/2008/inlineXBRL/xhtml-inlinexbrl-1_0.xsd")
                else:
                    pyIdentificationResults.type = u"xhtml"
                this.isHtml = True
                this.isIdentified = True # no need to parse further 
        elif compareString(uri, nsLink) == 0:
            if this.isXbrl or this.isInline:
                if compareString(localname, lnSchemaRef) == 0:
                    attrValue = getAttrValue(attrs, nsXlink, lnHref)
                    if attrValue is not None:
                        pyIdentificationResults.schemaRefs.add(attrValue)
                elif compareString(localname, lnLinkbaseRef) == 0:
                    attrValue = getAttrValue(attrs, nsXlink, lnHref)
                    if attrValue is not None:
                        pyIdentificationResults.linkbaseRefs.add(attrValue)
                elif compareString(localname, lnRoleRef) == 0 or compareString(localname, lnArcroleRef) == 0:
                    attrValue = getAttrValue(attrs, nsXlink, lnHref)
                    if attrValue is not None:
                        pyIdentificationResults.schemaRefs.add(attrValue.partition("#")[0])
            elif this.eltDepth == 0 and compareString(localname, lnLinkbase) == 0:
                this.isIdentified = True # no need to parse further 
                pyIdentificationResults.type = u"linkbase"
        elif compareIString(uri, nsVer) == 0:
            if compareString(localname, lnReport) == 0:
                this.isIdentified = True # no need to parse further 
                pyIdentificationResults.type = u"versioning report"
            elif this.eltDepth == 0:
                if compareIString(localname, lnTestcases) == 0 or compareIString(localname, lnDocumentation) == 0 or compareIString(localname, lnTestSuite) == 0:
                    this.isIdentified = True # no need to parse further 
                    pyIdentificationResults.type = u"testcases index"
                elif compareIString(localname, lnTestcase) == 0 or compareIString(localname, lnTestSet) == 0:
                    this.isIdentified = True # no need to parse further 
                    pyIdentificationResults.type = u"testcase"
        elif this.eltDepth == 0 and compareString(localname, lnRss) == 0:
            this.isIdentified = True # no need to parse further 
            pyIdentificationResults.type = u"rss"
        elif this.isXbrl:
            this.isIdentified = True # no need to parse further 
        #for i in range(attrs.getLength()):
        #    print("attribute {} = {}".format(i, transcode(attrs.getQName(i))))
        this.eltDepth += 1
        this.eltQNames[this.eltDepth] = <XMLCh*>qname

    void startPrefixMapping(const XMLCh* prefix, const XMLCh* uri):
        if compareString(uri, nsIxbrl) == 0:
            this.hasIxNamespace = True
        elif compareString(uri, nsIxbrl11) == 0:
            this.hasIx11Namespace = True
            
    void handlePyError(object pyError):
        pyIdentificationResults = <object>this.pyIdentificationResultsPtr
        pyIdentificationResults.errors.append(pyError)
        
cdef cppclass ModelXbrlEntityResolver(XMLEntityResolver):
    void* modelXbrlPtr
    
    ModelXbrlEntityResolver(void* modelXbrlPtr) except +:
        this.modelXbrlPtr = modelXbrlPtr
        
    close():
        this.modelXbrlPtr = NULL # dereference
        
    InputSource* resolveEntity(XMLResourceIdentifier* xmlri):
        cdef ResourceIdentifierType _type = xmlri.getResourceIdentifierType()
        cdef const XMLCh* publicId = xmlri.getPublicId()
        cdef const XMLCh* systemId = xmlri.getSystemId()
        cdef const XMLCh* schemaLocation = xmlri.getPublicId()
        cdef const XMLCh* baseURL = xmlri.getPublicId()
        cdef const XMLCh* nameSpace = xmlri.getPublicId()
        cdef const Locator* locator = xmlri.getLocator()
        cdef const XMLCh* locatorPublicId = locator.getPublicId()
        cdef const XMLCh* locatorSystemId = locator.getSystemId()
        cdef char* _publicId
        cdef char* _systemId
        cdef char* _schemaLocation
        cdef char* _baseURL
        cdef char* _nameSpace
        cdef char* _locatorPublicId
        cdef char* _locatorSystemId
        cdef object pyPublicId, pySystemId, pySchemaLocation, pyBaseURL, pyNameSpace, pyLocatorPublicId, pyLocatorSystemId
        if publicId != NULL and publicId[0] != 0:
            _publicId = transcode(publicId)
            pyPublicId = _publicId
            release(&_publicId)
        else:
            pyPublicId = None
        if systemId != NULL:
            _systemId = transcode(systemId)
            pySystemId = _systemId
            release(&_systemId)
        else:
            pySystemId = None
        if schemaLocation != NULL:
            _schemaLocation = transcode(schemaLocation)
            pySchemaLocation = _schemaLocation
            release(&_schemaLocation)
        else:
            pySchemaLocation = None
        if baseURL != NULL:
            _baseURL = transcode(baseURL)
            pyBaseURL = _baseURL
            release(&_baseURL)
        else:
            pyBaseURL = None
        if nameSpace != NULL:
            _nameSpace = transcode(nameSpace)
            pyNameSpace = _nameSpace
            release(&_nameSpace)
        else:
            pyNameSpace = None
        if locatorPublicId != NULL:
            _locatorPublicId = transcode(locatorPublicId)
            pyLocatorPublicId = _locatorPublicId
            release(&_locatorPublicId)
        else:
            pyLocatorPublicId = None
        if locatorSystemId != NULL:
            _locatorSystemId = transcode(locatorSystemId)
            pyLocatorSystemId = _locatorSystemId
            release(&_locatorSystemId)
        else:
            pyLocatorSystemId = None
        cdef object modelXbrl = <object>this.modelXbrlPtr
        pyFileDesc = modelXbrl.xerces_resolve_entity(_type, pyPublicId, pySystemId, pySchemaLocation, pyBaseURL, pyNameSpace, 
                                                     pyLocatorPublicId, pyLocatorSystemId,
                                                     locator.getLineNumber(), locator.getColumnNumber())
        if pyFileDesc is None:
            return NULL
        cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
        return inpSrc
        

        