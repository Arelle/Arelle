from arelle_c.xerces_ctypes cimport XMLCh, XMLSize_t, XMLByte, XMLFileLoc
from arelle_c.xerces_util cimport Initialize, Terminate, XMLByte, transcode, release,  \
    fgMemoryManager, stringLen, release, RefHash3KeysIdPoolEnumerator, XMLEnumerator, StringHasher, \
    catString, copyString, startsWith, fgMemoryManager
from arelle_c.xerces_parsers cimport XercesDOMParser
from arelle_c.xerces_framework cimport MemBufInputSource, XSAnnotation, XMLElementDecl, XMLGrammarPool, XMLGrammarPoolImpl, \
    XSModel, StringList, XSNamedMap, XSObject, ELEMENT_DECLARATION, TYPE_DEFINITION, COMPONENT_TYPE, \
    XSElementDeclaration, XSTypeDefinition, LocalFileInputSource, XMLPScanToken, XSNamespaceItemList, XSNamespaceItem, \
    XSAnnotationList
from arelle_c.xerces_framework_memory_manager cimport MemoryManager
from arelle_c.xerces_dom cimport DOMDocument, DOMNode, DOMNodeList, DOMText, TEXT_NODE, ELEMENT_NODE, DOMImplementationLS, getDOMImplementation, MODE_ASYNCHRONOUS
from libcpp.string cimport string
from arelle_c.xerces_sax cimport SAXParseException, ErrorHandler, EntityResolver
from arelle_c.xerces_sax2 cimport createXMLReader, SAX2XMLReader, ContentHandler, LexicalHandler, DefaultHandler
from arelle_c.xerces_uni cimport fgSAX2CoreNameSpaces, fgXercesSchema, fgXercesHandleMultipleImports, \
    fgXercesSchemaFullChecking, fgSAX2CoreNameSpacePrefixes, fgSAX2CoreValidation, fgXercesDynamic, \
    fgXercesGenerateSyntheticAnnotations, fgXercesScannerName, fgSGXMLScanner, fgXercesCacheGrammarFromParse, \
    fgXercesCalculateSrcOfs, fgXercesUseCachedGrammarInParse, fgXercesSchemaExternalSchemaLocation, \
    fgXercesValidateAnnotations
from cython.operator cimport dereference as deref
from libcpp cimport bool
from arelle_c.xerces_sax cimport InputSource, DocumentHandler, ErrorHandler, SAXParseException, Locator
from arelle_c.xerces_sax2 cimport Attributes
from arelle_c.xerces_validators cimport SchemaGrammar, SchemaElementDecl, GrammarType
from time import time
from cpython.mem cimport PyMem_Malloc, PyMem_Realloc, PyMem_Free
from collections import OrderedDict

cdef bool _initialized = False, _terminated = False

def initialize():
    global _initialized
    assert not _initialized, "xerces already initialized"
    if not _initialized:
        Initialize()
        _initialized = True

def terminate():
    global _initialized, _terminated
    assert not _initialized, "xerces termination but not initialized"
    assert not _terminated, "xerces terminated or not started"
    if _initialized and not _terminated:
        Terminate()
        _terminated = True
        _initialized = False
        
cdef void* pyListTestPtr
cdef object _list = []
pyListTestPtr = <void*>_list

def QNtest():
    print("hash test abc {}".format(PyObject_Hash(u"abc")))
    print("hash test ns1,ln1 {}".format(PyObject_Hash((u"ns1",u"ln1"))))
    print("hash test abc {}".format(PyObject_Hash(u"abc")))
    print("qnTrace")
    cdef qName1 = QName(u"ns1", u"p1", u"ln1")
    cdef qName1a = QName(u"ns1", u"p1a", u"ln1")
    cdef qName2 = QName(u"ns2", u"p2", u"ln2")
    print("qn1 {} {}".format(qName1, qName1.clarkNotation, qName1.__hash__()))
    print("qn2 {}".format(qName1a.clarkNotation, qName1a.__hash__()))
    print("qn3 {}".format(qName2.clarkNotation, qName2.__hash__()))
    print("hash test qn1 {}".format(PyObject_Hash(qName1)))
    print("qn1 == qn1 {}".format(qName1 == qName1))
    print("qn1 == qn1a {}".format(qName1 == qName1a))
    print("qn1 == qn2 {}".format(qName1 == qName2))

def test():
    cdef object pyListTest
    global pyListTestPtr
    pyListTest = <object>pyListTestPtr
    print("size {} {}".format(sizeof(pyListTest), pyListTest))
    pyListTest.append("abcdefghi")
    print("size {} {}".format(sizeof(pyListTest), pyListTest))

cdef class _Element:
    cdef DOMNode* _c_node
    property tag:
        def __get__( self ):
            return transcode( self._c_node.getNodeName())

    property foo:
        def __get__( self ):
            print ("hello from Cython");
            print ("tag {}".format(transcode(self._c_node.getNodeName())));
            cdef XMLCh* locName
            locName = <XMLCh*>self._c_node.getLocalName()
            cdef char* _locName
            _locName = transcode(locName)
            print ("loc name {}".format(_locName))
            release(&_locName)
            cdef XMLCh* nsURI
            cdef char* _nsURI
            nsURI = <XMLCh*>self._c_node.getNamespaceURI()
            if nsURI != NULL:
                _nsURI = transcode(nsURI)
                print ("ns URI {}".format(_nsURI)); 
                release(&_nsURI)
            cdef DOMNode* text_node
            text_node = self._c_node.getFirstChild()
            cdef char* s = transcode( text_node.getNodeValue() )
            pyS = s
            print ( "transcoded value {}".format( pyS.decode("utf-8") ) );
            release(&s)

    property localName:
        def __get__( self ):
            return transcode( self._c_node.getLocalName() ).decode("utf-8")
    property namespaceURI:
        def __get__( self ):
            return transcode( self._c_node.getNamespaceURI() ).decode("utf-8")
    property clarkName:
        def __get__( self ):
            return b"{" + transcode( self._c_node.getNamespaceURI()) + b"}" + transcode( self._c_node.getLocalName())
    property text:
        def __get__( self ):
            cdef DOMText* text_node = <DOMText*>self._c_node.getFirstChild()
            if text_node == NULL:
                return None
            #return transcode( text_node.getNodeValue()).decode("utf-8")
            cdef const XMLCh* xmlStr = text_node.getWholeText()
            if xmlStr == NULL:
                return None
            return transcode( xmlStr ).decode("utf-8")
    property rawtext:
        def __get__( self ):
            cdef DOMNode* text_node = self._c_node.getFirstChild()
            if text_node == NULL:
                return None
            cdef const XMLCh* xmlStr = text_node.getNodeValue()
            if xmlStr == NULL:
                return None
            cdef char* xmlStrBytes = <char*>xmlStr
            cdef XMLSize_t strLen = stringLen(xmlStr)
            return xmlStrBytes[:strLen*2].decode("UTF_16LE")
    property timeconversion:
        def __get__( self ):
            cdef DOMNode* text_node = ( self._c_node.getFirstChild())
            cdef const XMLCh* xmlStr = text_node.getNodeValue()
            cdef char* xmlStrBytes
            cdef XMLSize_t
            cdef int i
            t1 = time()
            for i in range(2000000):
                xmlStrBytes = <char*>xmlStr
                strLen = stringLen(xmlStr)
                pyStr1 = xmlStrBytes[:strLen*2].decode("UTF_16LE")
            t2 = time()
            for i in range(2000000):
                xmlStrBytes = transcode(xmlStr)
                pyStr2 = xmlStrBytes.decode("utf-8")
                release(&xmlStrBytes)
            t3 = time()
            return "conversions strlen {} c1 {} c2 {} s1 {} s2 {}".format(strLen, t2-t1,t3-t2,pyStr1,pyStr2)
                
    property tail:
        def __get__( self ):
            cdef DOMNode* next = ( self._c_node.getNextSibling())
            if ( next is NULL or next.getNodeType() is not TEXT_NODE ):
                return None
            return transcode( next.getNodeValue())
    def __getitem__( self, x ):
        return _element( self._c_node.getChildNodes().item( x ))
    def getchildren( self ):
        result = []
        cdef DOMNodeList* child_nodes = ( self._c_node.getChildNodes())
        cdef XMLSize_t length = child_nodes.getLength()
        cdef DOMNode* child
        for i in range( length ):
            child = child_nodes.item( i )
            if ( child.getNodeType() == ELEMENT_NODE ):
                result.append( _element( child ))
        return result

    def lenchildren( self ):
        cdef DOMNodeList* child_nodes = ( self._c_node.getChildNodes())
        cdef XMLSize_t length = child_nodes.getLength()
        return length

cdef _element( DOMNode* node ):
    el = _Element()
    el._c_node = node
    return el

def fromstring( s ):
    cdef XercesDOMParser parser
    parser.setDoNamespaces( True )
    parser.setDoSchema( True )
    cdef string std_s = s
    print ("input string len {}".format(std_s.size()))
    cdef bool adoptBuffer = False
    cdef MemBufInputSource* inpSrc = ( new MemBufInputSource( <XMLByte*> std_s.c_str(), std_s.size(), nsNoNamespace, adoptBuffer ))
    parser.parse( deref( inpSrc ))
    cdef DOMDocument* doc = parser.getDocument()
    cdef DOMNode* root = doc.getDocumentElement()
    return _element( root ) 

def fromfile( s ):
    cdef XercesDOMParser parser
    parser.setDoNamespaces( True )
    parser.setDoSchema( True )
    byte_s = s.encode("utf-8")
    cdef const char* c_s = byte_s
    print("trace1 {}".format(c_s))
    cdef XMLCh* xmlChFile = transcode(c_s)
    print("trace2 {}".format(transcode(xmlChFile)))
    cdef LocalFileInputSource* inpSrc = ( new LocalFileInputSource( xmlChFile ))
    print("trace3")
    #release(&xmlChFile)
    parser.parse( deref( inpSrc ))    
    print("trace4")
    cdef DOMDocument* doc = parser.getDocument()
    cdef DOMNode* root = doc.getDocumentElement()
    return _element( root ) 

cdef char* lastParsedQName = NULL

cdef cppclass _ContentHandler(ContentHandler):
    int classVar
    
    _ContentHandler(int _classVar) except +:
        #global classVar
        this.classVar = _classVar
        print("_ContentHandler initialization {}".format(this.classVar))
    void characters(const XMLCh* chars, const XMLSize_t length):
        print("characters len: {} value: {}".format(length, transcode(chars))) #transcode(chars) if chars is not NULL else "null"))
    void endDocument():
        print("endDocument")
    void endElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname):
        cdef XMLCh* _uri
        cdef XMLCh* _localname
        cdef XMLCh* _qname
        #_uri = <XMLCh*>uri
        _localname = <XMLCh*>localname
        _qname = <XMLCh*>qname
        print("endElement")
        global lastParsedQName
        #print("endElement uri:  localname: {} qname: {}".format(#transcode(_uri) if _uri != NULL else "null",
        #                                                          transcode(_localname) if _localname != NULL else "null",
        #                                                          transcode(_qname) if _qname != NULL else "null"))
    void ignorableWhitespace(const XMLCh* chars, const XMLSize_t length):
        print("ignorableWhitespace")
    void processingInstruction(const XMLCh* target, const XMLCh* data):
        print("processingInstruction target: {} data: {}".format(transcode(target) if target is not NULL else "null", 
                                                                 transcode(data) if data is not NULL else "null"))
    void setDocumentLocator(const Locator* const locator):
        print("setDocumentLocator pubId: {} sysId: {} ".format(transcode(locator.getPublicId()) if locator.getPublicId() is not NULL else "null",
                                                       transcode(locator.getSystemId()) if locator.getSystemId() is not NULL else "null"))
    void startDocument():
        print("startDocument")
        print("classVar {}".format(this.classVar))
    void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs):
        cdef XMLCh* _uri
        cdef XMLCh* _localname
        cdef XMLCh* _qname
        cdef XMLCh* _value
        cdef XMLSize_t attrLen = attrs.getLength()
        cdef XMLSize_t i
        pyAttrs = {}
        for i in range(attrLen):
            _qname = <XMLCh*>attrs.getQName(i)
            _value = <XMLCh*>attrs.getValue(i)
            pyAttrs[transcode(_qname)] = transcode(_value)
        _uri = <XMLCh*>uri
        _localname = <XMLCh*>localname
        _qname = <XMLCh*>qname
        global lastParsedQName
        if lastParsedQName != NULL:
            release(&lastParsedQName)
        lastParsedQName = transcode(_qname)
        print("startElement trace1 localname raw {}".format(<char*>_localname))
        print("startElement uri: {} localname: {} qname: {} attrs: {}".format(
            transcode(_uri) if _uri is not NULL else "null",
            transcode(_localname) if _localname is not NULL else "null",
            transcode(_qname) if _qname is not NULL else "null",
            pyAttrs))
    void startPrefixMapping(const XMLCh* prefix, const XMLCh* uri):
        print("startPrefixMapping prefix: {} uri: {}".format(transcode(prefix),transcode(uri)))
    void endPrefixMapping(const XMLCh* prefix):
        print("endPrefixMapping prefix: {}".format(transcode(prefix)))
    void skippedEntity(const XMLCh* name):
        print("skippedEntity: {}".format(transcode(name)))

cdef cppclass _LexicalHandler(LexicalHandler):
    int classVar
    
    _LexicalHandler(int _classVar) except +:
        global classVar
        classVar = _classVar
        print("_LexicalHandler initialization {}".format(classVar))
    void comment(const XMLCh* chars, const XMLSize_t length):
        print("comment {}".format(transcode(chars) if chars is not NULL else "null"))
    void endCDATA():
        print("endCDATA")
    void endDTD():
        print("endDTD")
    void endEntity(const XMLCh* name):
        print("endEntity name: {}".format(transcode(name)))
    void startCDATA():
        print("startCDATA")
    void startDTD(const XMLCh* name, const XMLCh* publicId, const XMLCh* systemId):
        print("startDTD")
    void startEntity(const XMLCh* name):
        print("startEntity")
    void elementDecl(const XMLCh* name, const XMLCh* model):
        print("elementDecl")
        
cdef cppclass _ErrorHandler(ErrorHandler):
    _ErrorHandler() except +:
        print("_ErrorHandler initialization")
    void error(const SAXParseException& exc):
        cdef const XMLCh* msg = exc.getMessage()
        if msg != NULL:
            msgText = transcode(msg)
        else:
            msgText = "null"
        cdef const XMLCh* _file = exc.getSystemId()
        if _file != NULL:
            fileName = transcode(_file)
        else:
            fileName = "null"
        print("error msg={} line={} col={} file={}".format(msgText, exc.getLineNumber(),exc.getColumnNumber(),fileName))
    void fatalError(const SAXParseException& exc):
        cdef const XMLCh* msg = exc.getMessage()
        if msg != NULL:
            msgText = transcode(exc.getMessage())
        else:
            msgText = "null"
        print("fatal error msg={} line={} col={}".format(msgText, exc.getLineNumber(),exc.getColumnNumber()))
    void warning(const SAXParseException& exc):
        cdef const XMLCh* msg = exc.getMessage()
        if msg != NULL:
            msgText = transcode(msg)
        else:
            msgText = "null"
        cdef const XMLCh* _file = exc.getSystemId()
        if _file != NULL:
            fileName = transcode(_file)
        else:
            fileName = "null"
        print("warning msg={} line={} col={} file={}".format(msgText, exc.getLineNumber(),exc.getColumnNumber(),fileName))
    void resetErrors():
        print("resetErrors")

cdef struct eltDescEntry:
    XMLCh* lastElementQname
    char* lastEltPyQname
    XMLCh* lastChars
    XMLSize_t lastLength
    
cdef char* EMPTYSTR = b""

cdef cppclass _LXMLSAX2Handler(ErrorHandler, LexicalHandler, ContentHandler):
    #Attributes& lastElementAttrs
    unsigned int eltDepth
    eltDescEntry* eltDescs
    void* pyRootDictPtr
    
    _LXMLSAX2Handler(void* pyRootDictPtr) except +:
        global EMPTYSTR
        print("_LXMLSAX2Handler initialization")
        print("size {} {}".format(sizeof(eltDescEntry), 1000 * sizeof(eltDescEntry)))
        this.eltDescs = <eltDescEntry*>fgMemoryManager.allocate(1000 * sizeof(eltDescEntry))
        cdef eltDescEntry* eltDesc
        cdef int i
        for i in range(1000):
            eltDesc = &this.eltDescs[i]
            eltDesc.lastElementQname = NULL
            eltDesc.lastEltPyQname = EMPTYSTR
            eltDesc.lastChars = NULL
            eltDesc.lastLength = 0
        this.eltDepth = 0
        this.pyRootDictPtr = pyRootDictPtr
        print
        print("eltdescs {}".format(<unsigned long long> <void*>this.eltDescs))
    close():
        print("_LXMLSAX2Handler destructor")
        #PyMem_Free(this.lastElementQname)
        #this.lastElementQname = NULL
        #PyMem_Free(this.lastChars)
        #this.lastChars = NULL
        #PyMem_Free(this.lastLength)
        #this.lastLength = NULL
        fgMemoryManager.deallocate(this.eltDescs)
        this.eltDescs = NULL
        print("_LXMLSAX2Handler done")
    # document handlers
    void characters(const XMLCh* chars, const XMLSize_t length):
        if this.eltDescs[this.eltDepth].lastChars != NULL:
            i = length+1 + stringLen(this.eltDescs[this.eltDepth].lastChars)
            #this.lastChars[this.eltDepth] = <XMLCh*>PyMem_Realloc(this.lastChars[this.eltDepth], i * sizeof(XMLCh))
            this.eltDescs[this.eltDepth].lastChars = <XMLCh*>PyMem_Realloc(this.eltDescs[this.eltDepth].lastChars, i * sizeof(XMLCh))
            catString( this.eltDescs[this.eltDepth].lastChars, chars )
        else:
            this.eltDescs[this.eltDepth].lastChars = <XMLCh*>PyMem_Malloc((length+1) * sizeof(XMLCh))
            copyString(this.eltDescs[this.eltDepth].lastChars, chars)
        pass #print("characters len: {} value: {}".format(length, transcode(chars))) #transcode(chars) if chars is not NULL else "null"))
    void endDocument():
        pass #print("endDocument")
    void endElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname):
        cdef XMLCh* _uri
        cdef XMLCh* _localname
        cdef XMLCh* _qname
        cdef char* _text
        cdef object pyRootDict
        cdef eltDescEntry* eltDesc
        cdef unsigned int i
        eltDesc = &this.eltDescs[this.eltDepth]
        pyRootDict = <object>this.pyRootDictPtr
        pyDepthDict = pyRootDict
        for i from 1 <= i <= this.eltDepth:
            _depthPyQName = this.eltDescs[i].lastEltPyQname
            pyDepthDict = pyDepthDict[_depthPyQName]
        eltDesc.lastElementQname = NULL
        if eltDesc.lastChars != NULL:
            _text = transcode(eltDesc.lastChars)
            pyDepthDict[b"@text"] = _text
            release(&_text)
            PyMem_Free(eltDesc.lastChars)
        eltDesc.lastChars = NULL
        eltDesc.lastLength = 0
        release(&eltDesc.lastEltPyQname)
        eltDesc.lastEltPyQname = EMPTYSTR
        this.eltDepth -= 1

        #print("endElement uri:  localname: {} qname: {}".format(#transcode(_uri) if _uri != NULL else "null",
        #                                                          transcode(_localname) if _localname != NULL else "null",
        #                                                          transcode(_qname) if _qname != NULL else "null"))
    void ignorableWhitespace(const XMLCh* chars, const XMLSize_t length):
        pass #print("ignorableWhitespace")
    void processingInstruction(const XMLCh* target, const XMLCh* data):
        pass #print("processingInstruction target: {} data: {}".format(transcode(target) if target is not NULL else "null", 
        #                                                         transcode(data) if data is not NULL else "null"))
    void setDocumentLocator(const Locator* const locator):
        pass #print("setDocumentLocator pubId: {} sysId: {} ".format(transcode(locator.getPublicId()) if locator.getPublicId() is not NULL else "null",
        #                                               transcode(locator.getSystemId()) if locator.getSystemId() is not NULL else "null"))
    void startDocument():
        pass #print("startDocument")
        #print("classVar {}".format(this.classVar))
    void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs):
        cdef XMLCh* _uri
        cdef XMLCh* _localname
        cdef object pyDepthDict
        cdef char * _depthQName
        cdef eltDescEntry* eltDesc
        cdef object pyRootDict
        cdef unsigned int i
        cpdef char* _depthPyQName
        _uri = <XMLCh*>uri
        _localname = <XMLCh*>localname
        this.eltDepth += 1
        eltDesc = &this.eltDescs[this.eltDepth]
        eltDesc.lastElementQname = <XMLCh*>qname
        eltDesc.lastEltPyQname = transcode(qname)
        eltDesc.lastChars = NULL
        _depthPyQName = this.eltDescs[this.eltDepth].lastEltPyQname
        #print("eltDepth1qn {}".format(_depthPyQName))
        #this.lastElementAttrs = attrs
        #print("startElement trace1 localname raw {}".format(<char*>_localname))
        #print("startElement uri: {} localname: {} qname: {} attrs: tbd".format(
        #    transcode(_uri) if _uri is not NULL else "null",
        #    transcode(_localname) if _localname is not NULL else "null",
        #    transcode(_qname) if _qname is not NULL else "null"))
        pyRootDict = <object>this.pyRootDictPtr
        pyDepthDict = pyRootDict
        #print("trace 14c 0 {}".format(this.eltDescs[0].lastLength))
        #print("trace 14c 1 {}".format(this.eltDescs[1].lastLength))
        for i from 1 <= i <= this.eltDepth:
            eltDesc = &this.eltDescs[i]
            _depthPyQName = eltDesc.lastEltPyQname
            if _depthPyQName not in pyDepthDict:
                pyDepthDict[_depthPyQName] = OrderedDict()
            pyDepthDict = pyDepthDict[_depthPyQName]
    void startPrefixMapping(const XMLCh* prefix, const XMLCh* uri):
        pass #print("startPrefixMapping prefix: {} uri: {}".format(transcode(prefix),transcode(uri)))
    void endPrefixMapping(const XMLCh* prefix):
        pass #print("endPrefixMapping prefix: {}".format(transcode(prefix)))
    void skippedEntity(const XMLCh* name):
        pass #print("skippedEntity: {}".format(transcode(name)))    # lexical handlers
    void comment(const XMLCh* chars, const XMLSize_t length):
        pass #print("comment {}".format(transcode(chars) if chars is not NULL else "null"))
    void endCDATA():
        pass #print("endCDATA")
    void endDTD():
        pass #print("endDTD")
    void endEntity(const XMLCh* name):
        pass #print("endEntity name: {}".format(transcode(name)))
    void startCDATA():
        pass #print("startCDATA")
    void startDTD(const XMLCh* name, const XMLCh* publicId, const XMLCh* systemId):
        pass #print("startDTD")
    void startEntity(const XMLCh* name):
        pass #print("startEntity")
    void elementDecl(const XMLCh* name, const XMLCh* model):
        pass #print("elementDecl")
    # error handlers
    void error(const SAXParseException& exc):
        cdef const XMLCh* msg = exc.getMessage()
        cdef char* msgText
        cdef char* fileName
        cdef char* eltQn
        cdef char* eltVal
        if msg != NULL:
            msgText = transcode(msg)
        else:
            msgText = b"null"
        cdef const XMLCh* _file = exc.getSystemId()
        if _file != NULL:
            fileName = transcode(_file)
        else:
            fileName = b"null"
        if this.eltDescs[this.eltDepth].lastElementQname != NULL:
            eltQn = transcode(this.eltDescs[this.eltDepth].lastElementQname)
        else:
            eltQn = b""
        if this.eltDescs[this.eltDepth].lastChars != NULL:
            eltVal = transcode(this.eltDescs[this.eltDepth].lastChars)
        else:
            eltVal = b""
        _msg = "error msg={} line={} col={} file={} elt={} val={}".format(msgText, exc.getLineNumber(),exc.getColumnNumber(),fileName,eltQn,eltVal)
        print(_msg)
        if msg != NULL:
            release(&msgText)
        if _file != NULL:
            release(&fileName)
        if this.eltDescs[this.eltDepth].lastElementQname != NULL:
            release(&eltQn)
        if this.eltDescs[this.eltDepth].lastChars != NULL:
            release(&eltVal)
    void fatalError(const SAXParseException& exc):
        cdef const XMLCh* msg = exc.getMessage()
        cdef char* msgText
        if msg != NULL:
            msgText = transcode(exc.getMessage())
        else:
            msgText = "null"
        print("fatal error msg={} line={} col={}".format(msgText, exc.getLineNumber(),exc.getColumnNumber()))
        if msg != NULL:
            release(&msgText)
    void warning(const SAXParseException& exc):
        cdef const XMLCh* msg = exc.getMessage()
        cdef char* msgText
        cdef char* fileName
        cdef char* eltQn
        cdef char* eltVal
        if msg != NULL:
            msgText = transcode(msg)
        else:
            msgText = b"null"
        cdef const XMLCh* _file = exc.getSystemId()
        if _file != NULL:
            fileName = transcode(_file)
        else:
            fileName = b"null"
        if this.eltDescs[this.eltDepth].lastElementQname != NULL:
            eltQn = transcode(this.eltDescs[this.eltDepth].lastElementQname)
        else:
            eltQn = b""
        if this.eltDescs[this.eltDepth].lastChars != NULL:
            eltVal = transcode(this.eltDescs[this.eltDepth].lastChars)
        else:
            eltVal = b""
        _msg = "warning msg={} line={} col={} file={} elt={} val={}".format(msgText, exc.getLineNumber(),exc.getColumnNumber(),fileName,eltQn,eltVal)
        print(_msg)
        if msg != NULL:
            release(&msgText)
        if _file != NULL:
            release(&fileName)
        if this.eltDescs[this.eltDepth].lastElementQname != NULL:
            release(&eltQn)
        if this.eltDescs[this.eltDepth].lastChars != NULL:
            release(&eltVal)
    void resetErrors():
        print("resetErrors")
        
cdef cppclass _LXMLSAX2Resolver(EntityResolver):
    InputSource* resolveEntity(const XMLCh* const publicId, const XMLCh* const systemId):
        cdef char* _publicId
        if publicId != NULL:
            _publicId = transcode(publicId)
        else:
            _publicId = "null"
        cdef char* _systemId
        if systemId != NULL:
            _systemId = transcode(systemId)
        else:
            _systemId = "null"
        print("resolveEntity pub {} sys {}".format(_publicId, _systemId))
        cdef const XMLCh* http = transcode(b"http:")
        cdef const XMLCh* cachePath = transcode(b"/Users/hermf/Library/Caches/Arelle/http/")
        cdef XMLCh* localFile
        cdef InputSource* fileSource
        cdef LocalFileInputSource* inpSrc
        if systemId != NULL and startsWith(<const XMLCh*>systemId, http):
            localFile = <XMLCh*>PyMem_Malloc((2000) * sizeof(XMLCh))
            copyString(localFile, cachePath)
            catString(localFile, systemId + 7) 
            print("  revectored file {}".format(transcode(localFile)))
            fileSource = new LocalFileInputSource( localFile )
            fileSource.setPublicId(systemId)
            #PyMem_Free(localFile)
            localFile = NULL
            return fileSource
        return NULL
        
def testschema( s ):
    print("trace1")
    cdef XMLGrammarPool* grammarPool = new XMLGrammarPoolImpl(fgMemoryManager)
    cdef SAX2XMLReader * parser = createXMLReader(fgMemoryManager, grammarPool)
    parser.setProperty(fgXercesScannerName, <void *>fgSGXMLScanner)
    parser.setFeature(fgSAX2CoreNameSpaces, True)
    parser.setFeature(fgXercesSchema, True)
    parser.setFeature(fgXercesSchemaFullChecking, True)
    parser.setFeature(fgXercesCacheGrammarFromParse, True)
    parser.setFeature(fgXercesUseCachedGrammarInParse, True)
    parser.setFeature(fgSAX2CoreNameSpacePrefixes, True)
    parser.setFeature(fgSAX2CoreValidation, True)
    parser.setFeature(fgXercesDynamic, True)
    parser.setFeature(fgXercesValidateAnnotations, True)
    parser.setFeature(fgXercesGenerateSyntheticAnnotations, True)
    cdef _ErrorHandler * errorHandler = new _ErrorHandler()
    parser.setErrorHandler(errorHandler)
    cdef _LXMLSAX2Resolver * lxmlSaxResolver = new _LXMLSAX2Resolver()
    parser.setEntityResolver(lxmlSaxResolver)
    print("trace2")
    cdef string std_s = s
    cdef bool adoptBuffer = False
    cdef MemBufInputSource* inpSrc = ( new MemBufInputSource( <XMLByte*> std_s.c_str(), std_s.size(), nsNoNamespace, adoptBuffer ))
    print("trace3")
    cdef SchemaGrammar* schemaGrammar = <SchemaGrammar*>parser.loadGrammar( deref( inpSrc ), GrammarType.SchemaGrammarType, True)
    cdef XMLCh* targetNS
    targetNS = <XMLCh*>schemaGrammar.getTargetNamespace()
    if schemaGrammar == NULL:
        print("null grammar")
        return
    print("target namespace {}".format(transcode(targetNS)))
    print("trace4")
    cdef XSAnnotationList* annotations
    cdef XSAnnotation* annotation = schemaGrammar.getAnnotation()
    cdef XMLCh* annotationText
    while (annotation != NULL):
        annotationText = annotation.getAnnotationString()
        if annotationText == NULL:
            print("null annotation text")
        else:
            print("annotation={}".format(transcode(annotationText)))
        annotation = annotation.getNext()
    cdef XSElementDeclaration *xsElement
    cdef XSTypeDefinition *xsTypeDefinition
    cdef unsigned int nsNbr
    cdef bool modelWasChanged = 0 # true if this is a first time call and a new model is created
    cdef XSModel* xsModel = grammarPool.getXSModel(modelWasChanged)
    cdef StringList *namespaces
    cdef const StringList *namespaceDocumentLocations
    cdef XSNamespaceItemList *namespaceItems
    cdef XSNamespaceItem* namespaceItem
    cdef XMLSize_t namespacesSize
    cdef unsigned int i
    cdef const XMLCh *nameSpace
    cdef const XMLCh *nameSpaceDocLocation
    cdef XSNamedMap[XSObject]* xsObjects
    cdef XMLSize_t j
    if xsModel != NULL:
        namespaceItems = xsModel.getNamespaceItems()
        namespacesSize = namespaceItems.size()
        print("namespaces size {}".format(namespacesSize))
        for i in range(namespacesSize):
            namespaceItem = namespaceItems.elementAt(i)
            nameSpace = namespaceItem.getSchemaNamespace()
            ns = transcode(nameSpace)
            print("namespace {}".format(ns))
            namespaceDocumentLocations = namespaceItem.getDocumentLocations()
            if namespaceDocumentLocations == NULL:
                print("namespace locations list null")
            else:
                for j in range(namespaceDocumentLocations.size()):
                    nameSpaceDocLocation = namespaceDocumentLocations.elementAt(j)
                    if nameSpaceDocLocation == NULL:
                        print("namespace doc null")
                    else:
                        ns = transcode(nameSpaceDocLocation)
                        print("namespace doc {}".format(ns))
            #if "xbrl.org" in ns or "fasb" in ns or "w3c.org" in ns:
            #    continue
            annotations = namespaceItem.getAnnotations()
            print("namespace {} annotations {}".format(i, annotations.size()))
            for j in range(0, annotations.size()):
                annotation = annotations.elementAt(j)
                if annotation == NULL:
                    print("annotation {} is NULL".format(j))
                while (annotation != NULL):
                    annotationText = annotation.getAnnotationString()
                    if annotationText != NULL:
                        print("    annotation{} ={}".format(j, transcode(annotationText)))
                    else:
                        print("    null annotation string {}".format(j))
                    annotation = annotation.getNext()
            for j in range(1,15):
                xsObjects = xsModel.getComponentsByNamespace(<COMPONENT_TYPE>j, nameSpace)
                print("object {} count {}".format(j, xsObjects.getLength() if xsObjects != NULL else None))
            xsObjects = xsModel.getComponentsByNamespace(ELEMENT_DECLARATION, nameSpace)
            if xsObjects == NULL or xsObjects.getLength() == 0:
                print("no elements")
            else:
                for j in range(xsObjects.getLength()):
                    xsElement = <XSElementDeclaration *>xsObjects.item(j)
                    print("element {} {}".format(j, transcode(xsElement.getName())))
                    annotation = xsElement.getAnnotation()
                    if annotation == NULL:
                        print("annotation is NULL")
                    while (annotation != NULL):
                        annotationText = annotation.getAnnotationString()
                        if annotationText != NULL:
                            print("    annotation={}".format(transcode(annotationText)))
                        else:
                            print("    null annotation string")
                        annotation = annotation.getNext()
                    xsTypeDefinition = xsElement.getTypeDefinition()
                    if xsTypeDefinition != NULL:
                        print("   type {}".format(transcode(xsTypeDefinition.getName())))
            xsObjects = xsModel.getComponentsByNamespace(TYPE_DEFINITION, nameSpace)
            if xsObjects == NULL or xsObjects.getLength() == 0:
                print("no types")
            else:
                for j in range(xsObjects.getLength()):
                    xsTypeDefinition = <XSTypeDefinition *>xsObjects.item(j)
                    print("type {} {} {}".format(j,
                                                 "SIMPLE" if xsTypeDefinition.getTypeCategory() == 16 else "COMPLEX",
                                                 transcode(xsTypeDefinition.getName())))
            

    else:
        print ("xsModel is null")
    
def testschemaDOM( s ):
    print("trace1")
    cdef XMLGrammarPool* grammarPool = new XMLGrammarPoolImpl(fgMemoryManager)
    cdef char* implFeatures = b"LS"
    cdef XMLCh* _implFeatures = transcode(implFeatures)
    cdef DOMImplementationLS* domImpl = getDOMImplementation(_implFeatures)
    print ("trace2 domImpl is {}".format("not null" if domImpl != NULL else "null"))
    if domImpl == NULL:
        return
    cdef XercesDOMParser* parser = new XercesDOMParser()
    cdef bool bTrue = True
    parser.setDoNamespaces( bTrue )
    parser.setDoSchema( bTrue )
    parser.setLoadSchema( bTrue )
    parser.setGenerateSyntheticAnnotations( bTrue )
    parser.setValidationSchemaFullChecking( bTrue )
    parser.setCalculateSrcOfs( bTrue )
    parser.cacheGrammarFromParse( bTrue )
    parser.useCachedGrammarInParse( bTrue )
    parser.setCreateSchemaInfo( bTrue )
    parser.setCreateCommentNodes( bTrue )
    cdef _ErrorHandler * errorHandler = new _ErrorHandler()
    parser.setErrorHandler(errorHandler)
    print("trace2")
    cdef string std_s = s
    cdef bool adoptBuffer = False
    cdef MemBufInputSource* inpSrc = ( new MemBufInputSource( <XMLByte*> std_s.c_str(), std_s.size(), nsNoNamespace, adoptBuffer ))
    print("trace3")
    cdef SchemaGrammar* schemaGrammar = <SchemaGrammar*>parser.loadGrammar( deref( inpSrc ), GrammarType.SchemaGrammarType, bTrue)
    if schemaGrammar == NULL:
        print("null grammar")
        return
    print("target namespace {}".format(transcode(schemaGrammar.getTargetNamespace())))
    print("trace4")
    cdef XSAnnotation* annotation = schemaGrammar.getAnnotation()
    cdef XMLCh* annotationText
    while (annotation != NULL):
        annotationText = annotation.getAnnotationString()
        if annotationText == NULL:
            print("null annotation text")
        else:
            print("annotation={}".format(transcode(annotationText)))
        annotation = annotation.getNext()
    
    cdef bool updatedXSModel = 0
    cdef XSModel* xsModel = grammarPool.getXSModel(updatedXSModel)
    cdef StringList *namespaces
    cdef XMLSize_t namespacesSize
    cdef unsigned int i
    cdef const XMLCh *nameSpace
    cdef XSNamedMap[XSObject]* xsObjects
    cdef XMLSize_t j
    cdef XSElementDeclaration *xsElement
    cdef XSTypeDefinition *xsTypeDefinition
    if xsModel != NULL:
        namespaces = xsModel.getNamespaces()
        namespacesSize = namespaces.size()
        print("namespaces size {}".format(namespacesSize))
        for i in range(namespacesSize):
            nameSpace = namespaces.elementAt(i)
            ns = transcode(nameSpace)
            print("namespace {}".format(ns))
            if "xbrl.org" in ns or "fasb" in ns or "www.w3.org" in ns:
                continue
            xsObjects = xsModel.getComponentsByNamespace(ELEMENT_DECLARATION, nameSpace)
            if xsObjects == NULL or xsObjects.getLength() == 0:
                print("no elements")
            else:
                for j in range(xsObjects.getLength()):
                    xsElement = <XSElementDeclaration *>xsObjects.item(j)
                    print("element {} {}".format(j, transcode(xsElement.getName())))
                    annotation = xsElement.getAnnotation()
                    while (annotation != NULL):
                        annotationText = annotation.getAnnotationString()
                        if annotationText != NULL:
                            print("    annotation={}".format(transcode(annotationText)))
                        else:
                            print("    null annotation string")
                        annotation = annotation.getNext()
            xsObjects = xsModel.getComponentsByNamespace(TYPE_DEFINITION, nameSpace)
            if xsObjects == NULL or xsObjects.getLength() == 0:
                print("no types")
            else:
                for j in range(xsObjects.getLength()):
                    xsTypeDefinition = <XSTypeDefinition *>xsObjects.item(j)
                    print("type {} {} {}".format(j,
                                                 "SIMPLE" if xsTypeDefinition.getTypeCategory() == 16 else "COMPLEX",
                                                 transcode(xsTypeDefinition.getName())))
            

    else:
        print ("xsModel is null")
        
def testsax2( s ):
    global _initialized, _terminated
    print("initialized flag {} terminated flag {}".format(_initialized, _terminated));

    cdef SAX2XMLReader * parser = createXMLReader()
    parser.setFeature(fgSAX2CoreValidation, True)
    parser.setFeature(fgSAX2CoreNameSpaces, True)
    parser.setFeature(fgXercesSchema, True)
    parser.setFeature(fgXercesSchemaFullChecking, True)
    cdef _ContentHandler * contentHandler = new _ContentHandler(999891)
    cdef _LexicalHandler * lexicalHandler = new _LexicalHandler(999891)
    cdef _ErrorHandler * errorHandler = new _ErrorHandler()
    print("trace5")
    parser.setContentHandler(contentHandler)
    parser.setLexicalHandler(lexicalHandler)
    print("trace6")
    parser.setErrorHandler(errorHandler)
    print("trace7")
    cdef string std_s = s
    print("trace8")
    cdef bool adoptBuffer = False
    cdef MemBufInputSource* inpSrc = ( new MemBufInputSource( <XMLByte*> std_s.c_str(), std_s.size(), nsNoNamespace, adoptBuffer ))
    parser.parse( deref( inpSrc ))
    print("trace10")
    
def testsax2incremental( ignore, instDocFile, ignore2 ):
    global lastParsedQName
    cdef SAX2XMLReader * parser = createXMLReader()
    cdef _ContentHandler * contentHandler = new _ContentHandler(999891)
    cdef _LexicalHandler * lexicalHandler = new _LexicalHandler(999891)
    cdef _ErrorHandler * errorHandler = new _ErrorHandler()
    parser.setContentHandler(contentHandler)
    parser.setLexicalHandler(lexicalHandler)
    parser.setErrorHandler(errorHandler)
    byte_s = instDocFile.encode("utf-8")
    cdef const char* c_s = byte_s
    cdef XMLCh* xmlChFile = transcode(c_s)
    cdef LocalFileInputSource* inpSrc = ( new LocalFileInputSource( xmlChFile ))
    cdef XMLPScanToken* token = new XMLPScanToken()
    cdef bool result
    result = parser.parseFirst(deref( inpSrc ), deref(token) )
    print("parse first {}".format(result))
    while result:
        if lastParsedQName == NULL:
            print("lastParsedToken null")
        else:
            c_s = lastParsedQName
            print("lastParsedToken {}".format(c_s))
            if lastParsedQName[0] not in (b'x', b'l'):
                parser.parseReset(deref(token))
                token = NULL
                break
        result = parser.parseNext(deref(token))
    print("doneParsedToken {}".format(lastParsedQName))
    
def validate( txmyFile, instFile, schemaLocation ):
    cdef XMLGrammarPool* grammarPool = new XMLGrammarPoolImpl(fgMemoryManager)
    cdef SAX2XMLReader * parser = createXMLReader(fgMemoryManager, grammarPool)
    parser.setFeature(fgSAX2CoreNameSpaces, True)
    parser.setFeature(fgXercesSchema, True)
    parser.setFeature(fgXercesHandleMultipleImports, True)
    parser.setFeature(fgXercesSchemaFullChecking, True)
    parser.setFeature(fgSAX2CoreNameSpacePrefixes, True)
    parser.setFeature(fgSAX2CoreValidation, True)
    parser.setFeature(fgXercesDynamic, True)
    parser.setFeature(fgXercesGenerateSyntheticAnnotations, True)
    parser.setFeature(fgXercesCacheGrammarFromParse, True)
    parser.setFeature(fgXercesCalculateSrcOfs, True)
    parser.setProperty(fgXercesScannerName, <void *>fgSGXMLScanner)
    #cdef _ErrorHandler * errorHandler = new _ErrorHandler()
    cdef object pyRootDict
    pyRootDict = OrderedDict()
    cdef void * pyRootDictPtr
    pyRootDictPtr = <void*>pyRootDict
    cdef _LXMLSAX2Handler * lxmlSaxHandler = new _LXMLSAX2Handler(pyRootDictPtr)
    parser.setErrorHandler(lxmlSaxHandler)
    parser.setContentHandler(lxmlSaxHandler)
    parser.setLexicalHandler(lxmlSaxHandler)
    cdef _LXMLSAX2Resolver * lxmlSaxResolver = new _LXMLSAX2Resolver()
    parser.setEntityResolver(lxmlSaxResolver)
    print("loadGrammar start")
    byte_s = txmyFile.encode("utf-8")
    cdef const char* c_s = byte_s
    cdef XMLCh* xmlChFile = transcode(c_s)
    cdef LocalFileInputSource* inpSrc = ( new LocalFileInputSource( xmlChFile ))
    cdef SchemaGrammar* schemaGrammar = <SchemaGrammar*>parser.loadGrammar( deref( inpSrc ), GrammarType.SchemaGrammarType, True)
    print("loadGrammar completed")
    cdef bool updatedXSModel = 0
    cdef XSModel* xsModel = grammarPool.getXSModel(updatedXSModel)
    cdef StringList *namespaces
    cdef XMLSize_t namespacesSize
    cdef unsigned int i
    cdef const XMLCh *nameSpace
    if xsModel != NULL:
        namespaces = xsModel.getNamespaces()
        namespacesSize = namespaces.size()
        for i in range(namespacesSize):
            nameSpace = namespaces.elementAt(i)
            xsObjects = xsModel.getComponentsByNamespace(ELEMENT_DECLARATION, nameSpace)
            if xsObjects == NULL or xsObjects.getLength() == 0:
                print("namespace {} no elements".format(transcode(nameSpace)))
            else:
                print("namespace {} {} elements".format(transcode(nameSpace), xsObjects.getLength()))
    print("parsing instance")
    byte_s = instFile.encode("utf-8")
    c_s = byte_s
    xmlChFile = transcode(c_s)
    inpSrc = ( new LocalFileInputSource( xmlChFile ))
    parser.setFeature(fgXercesUseCachedGrammarInParse, True)
    byte_s = schemaLocation.encode("utf-8")
    c_s = byte_s
    cdef XMLCh* xmlChSchemaLocation = transcode(c_s)
    parser.setProperty(fgXercesSchemaExternalSchemaLocation, xmlChSchemaLocation)
    parser.parse( deref( inpSrc ))
    del parser
    lxmlSaxHandler.close()
    del lxmlSaxHandler
    # print("pyRootList {}".format(pyRootDict))
    print("done")

