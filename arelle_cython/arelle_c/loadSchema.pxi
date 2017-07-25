from arelle_c.xerces_util cimport compareString, compareIString, transcode, release, XMLCh, XMLSize_t
from arelle_c.xerces_sax cimport SAXParseException, ErrorHandler
from arelle_c.xerces_framework cimport XMLPScanToken
from arelle_c.xerces_sax2 cimport createXMLReader, SAX2XMLReader, ContentHandler, LexicalHandler, DefaultHandler
from cython.operator cimport dereference as deref
from libcpp cimport bool
from arelle_c.xerces_sax cimport InputSource, DocumentHandler, ErrorHandler, SAXParseException, Locator
from arelle_c.xerces_sax2 cimport Attributes
from arelle_c.xerces_uni cimport fgSAX2CoreNameSpacePrefixes
from libc.stdlib cimport malloc, free
#from arelle_c.utils cimport templateSAX2Handler

cdef cppclass _LoadSchemaSAX2Handler(templateSAX2Handler):
    unsigned int eltDepth
    XMLCh** eltQNames
    void* pyIdentificationResultsPtr
    bool isXbrl, isXsd, isHtml, isInline, isIdentified
    bool hasIxNamespace, hasIx11Namespace
    
    _IdentificationSAX2Handler(void* pyIdentificationResultsPtr) except +:
        this.eltQNames = <XMLCh**>malloc(1000 * sizeof(XMLCh*))
        this.eltDepth = 0
        this.pyIdentificationResultsPtr = pyIdentificationResultsPtr
        this.isXbrl = this.isXsd = this.isHtml = this.isInline = this.isIdentified = False
        this.hasIxNamespace = this.hasIx11Namespace = False
    close():
        this.pyIdentificationResultsPtr = NULL
        free(this.eltQNames)
        this.eltQNames = NULL
    # document handlers
    void endElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname):
        this.eltQNames[this.eltDepth] = NULL
        this.eltDepth -= 1
    void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs):
        cdef object pyIdentificationResults
        cdef XMLSize_t i
        cdef XMLCh* s
        cdef object attrValue
        
        print("start {} {}".format(transcode(uri), transcode(localname)))
        pyIdentificationResults = <object>this.pyIdentificationResultsPtr
        if compareIString(uri, nsXbrli) == 0:
            if compareString(localname, lnXbrl) == 0:
                this.isXbrl = True
                pyIdentificationResults.type = u"instance"
        elif compareIString(uri, nsXsd) == 0:
            if compareString(localname, lnSchema) == 0:
                this.isXsd = True
                pyIdentificationResults.type = u"schema"
        elif compareIString(uri, nsXhtml) == 0:
            if compareString(localname, lnXhtml) == 0 or compareString(localname, lnHtml) == 0:
                if this.hasIx11Namespace:
                    pyIdentificationResults.type = u"inline XBRL instance"
                    pyIdentificationResults.schemaRefs.append("http://www.xbrl.org/2013/inlineXBRL/xhtml-inlinexbrl-1_1.xsd")
                elif this.hasIxNamespace:
                    pyIdentificationResults.type = u"inline XBRL instance"
                    pyIdentificationResults.schemaRefs.append("http://www.xbrl.org/2008/inlineXBRL/xhtml-inlinexbrl-1_0.xsd")
                else:
                    pyIdentificationResults.type = u"xhtml"
                this.isHtml = True
                this.isIdentified = True # no need to parse further 
        elif compareString(uri, nsLink) == 0:
            if this.isXbrl or this.isInline:
                if compareString(localname, lnSchemaRef) == 0:
                    attrValue = getAttrValue(attrs, nsXlink, lnHref)
                    if attrValue is not None:
                        pyIdentificationResults.schemaRefs.append(attrValue)
                elif compareString(localname, lnLinkbaseRef) == 0:
                    attrValue = getAttrValue(attrs, nsXlink, lnHref)
                    if attrValue is not None:
                        pyIdentificationResults.linkbaseRefs.append(attrValue)
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
        for i in range(attrs.getLength()):
            print("attribute {} = {}".format(i, transcode(attrs.getQName(i))))
        this.eltDepth += 1
        this.eltQNames[this.eltDepth] = <XMLCh*>qname

    void startPrefixMapping(const XMLCh* prefix, const XMLCh* uri):
        if compareString(uri, nsIxbrl) == 0:
            this.hasIxNamespace = True
        elif compareString(uri, nsIxbrl11) == 0:
            this.hasIx11Namespace = True
    # error handlers
    void logError(const SAXParseException& exc, level):
        cdef const XMLCh* msg = exc.getMessage()
        cdef char* msgText
        cdef char* fileName
        cdef char* eltQn
        cdef object pyIdentificationResults
        pyIdentificationResults = <object>this.pyIdentificationResultsPtr
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
        pyError = {"message": msgText.decode("utf-8"),
                   "level": level,
                   "lineno": exc.getLineNumber(),
                   "colno": exc.getColumnNumber(),
                   "file": fileName.decode("utf-8"),
                   "element": eltQn.decode("utf-8")}
        pyIdentificationResults.errors.append(pyError)
        if msg != NULL:
            release(&msgText)
        if _file != NULL:
            release(&fileName)
        if this.eltQNames[this.eltDepth] != NULL:
            release(&eltQn)
    void error(const SAXParseException& exc):
        this.logError(exc, u"error")
    void fatalError(const SAXParseException& exc):
        this.logError(exc, u"fatal")
    void warning(const SAXParseException& exc):
        this.logError(exc, u"fatal")
        
def identifyXmlFile( pyFileDesc ):
    
    print("identify trace1")
    print("identify trace2 nsInst {} lnXbrl {}".format(transcode(nsXbrli), transcode(lnXbrl)))

    cdef SAX2XMLReader * parser = createXMLReader()
    cdef object pySchemaLoadingResults
    pyIdentificationResults = attrdict(type=u"unknown XML", 
                                       schemaRefs=[], 
                                       linkbaseRefs=[], 
                                       nonDtsSchemaRefs=[],
                                       errors=[])
    print("pyIdRes {}".format(pyIdentificationResults))
    cdef void * pySchemaResultsPtr
    pySchemaLoadingResultsPtr = <void*>pySchemaLoadingResults
    cdef _LoadSchemaSAX2Handler * loadSchemaSAX2Handler = new _LoadSchemaSAX2Handler(pySchemaLoadingResultsPtr)
    parser.setErrorHandler(loadSchemaSAX2Handler)
    parser.setContentHandler(loadSchemaSAX2Handler)
    parser.setLexicalHandler(loadSchemaSAX2Handler)
    cdef XMLPScanToken* token = new XMLPScanToken()
    cdef bool result
    cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
    result = parser.parseFirst(deref( inpSrc ), deref(token) )
    while result:
        if identificationSAX2Handler.isIdentified:
            parser.parseReset(deref(token))
            token = NULL
            break
        result = parser.parseNext(deref(token))
    print("results {} ".format(pyIdentificationResults))
    print("handler isXbrl {} isInline {} isIdentified {}".format(loadSchemaSAX2Handler.isXbrl, loadSchemaSAX2Handler.isInline, loadSchemaSAX2Handler.isIdentified))
    del parser
    loadSchemaSAX2Handler.close()
    del loadSchemaSAX2Handler
    return pySchemaLoadingResults

