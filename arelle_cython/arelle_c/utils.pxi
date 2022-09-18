from arelle_c.xerces_sax2 cimport Attributes
from arelle_c.xerces_util cimport XMLCh, XMLSize_t, XMLByte, stringLen, copyString, catString, StringHasher, RefHashTableOf, RefHashTableOfEnumerator
from arelle_c.xerces_framework cimport LocalFileInputSource, MemBufInputSource, PSVIHandler, PSVIAttributeList, PSVIElement, XSElementDeclaration
from arelle_c.xerces_sax cimport InputSource, ErrorHandler, SAXParseException, Locator
from arelle_c.xerces_sax2 cimport ContentHandler, LexicalHandler
from libcpp.string cimport string
from libcpp cimport bool

cdef class attrdict(dict):
    """ utility to simulate an dictionary with named fields from the kwargs """
    cdef dict __dict__
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.__dict__ = self

cdef class genobj:
    """ utility to simulate an generic object with named fields from the kwargs """
    cdef dict __dict__
    def __init__(self, **kwargs):
        self.__dict__ = kwargs
    def __repr__(self):
        return str(self.__dict__)

cdef InputSource* fileDescInputSource( pyFileDesc, const char* chXmlSrc=NULL ) except *:
    cdef const char* chXml
    cdef const char* chBufId # file name
    cdef XMLCh* xmlchFile
    cdef bytes bytesBufId
    cdef InputSource* inpSrc = NULL
    cdef bool adoptBuffer = False
    cdef char* charStr
    cdef XMLByte* xmlByteStr
    
    if hasattr(pyFileDesc, "filepath"): 
        bytesBufId = pyFileDesc.filepath.encode("utf-8")
    else:
        bytesBufId = b"(in memory, no filename provided, no xml base or relative hrefs possible)"
    chBufId = bytesBufId
    if chXmlSrc != NULL: # char* direct input
        inpSrc = new MemBufInputSource( <const XMLByte*>chXmlSrc, stringLen(chXmlSrc), chBufId, adoptBuffer )
    elif hasattr(pyFileDesc, "bytes"):
        # print("fileDescInputSrc has bytes")
        chXml = <bytes>pyFileDesc.bytes # fast operation, pointer is tied to life time of python bytes string in fileDesc object
        # print("fileDescInputSrc bytes: {}".format(chXml))
        inpSrc = new MemBufInputSource( <const XMLByte*>chXml, stringLen(chXml), chBufId, adoptBuffer )
    elif hasattr(pyFileDesc, "filepath"):
        xmlchFile = transcode(chBufId)
        inpSrc = ( new LocalFileInputSource( xmlchFile ))
        release(&xmlchFile)
    bytesBufId = None # deref python bytes buffer ID and chBufId (which references bytesBufId)
    return inpSrc

ctypedef RefHashTableOf[XMLCh,StringHasher] StringHashTable
ctypedef RefHashTableOfEnumerator[XMLCh,StringHasher] StringHashTableEnumerator

cdef struct EltDesc:
    XMLCh* xmlchQName
    XMLCh* xmlchChars
    hash_t hashQName
    StringHashTable *prefixNsMap
    StringHashTable *nsPrefixMap
    XSElementDeclaration *eltDecl
    XMLFileLoc sourceLine, sourceCol
    bool hasError
    
cdef cppclass TemplateSAX2Handler(ErrorHandler, LexicalHandler, ContentHandler, PSVIHandler):
    # document handlers
    void characters(const XMLCh* chars, const XMLSize_t length):
        return # needed if any analyzed element contents were to be significant
    void endDocument():
        return 
    void endElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname):
        return
    void ignorableWhitespace(const XMLCh* chars, const XMLSize_t length):
        return
    void processingInstruction(const XMLCh* target, const XMLCh* data):
        return
    void setDocumentLocator(const Locator* const locator):
        return
    void startDocument():
        return
    void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs):
        return
    void startPrefixMapping(const XMLCh* prefix, const XMLCh* uri):
        return
    void endPrefixMapping(const XMLCh* prefix):
        return
    void skippedEntity(const XMLCh* name):
        return
    void comment(const XMLCh* chars, const XMLSize_t length):
        return
    void endCDATA():
        return
    void endDTD():
        return #print("endDTD")
    void endEntity(const XMLCh* name):
        return #print("endEntity name: {}".format(transcode(name)))
    void startCDATA():
        return #print("startCDATA")
    void startDTD(const XMLCh* name, const XMLCh* publicId, const XMLCh* systemId):
        return #print("startDTD")
    void startEntity(const XMLCh* name):
        return #print("startEntity")
    void elementDecl(const XMLCh* name, const XMLCh* model):
        return #print("elementDecl")
    # psvi handlers
    void handleElementPSVI(const XMLCh* const localName, const XMLCh* const uri, PSVIElement * elementInfo):
        return
    void handlePartialElementPSVI(const XMLCh* const localName, const XMLCh* const uri, PSVIElement * elementInfo):
        return
    void handleAttributesPSVI(const XMLCh* const localName, const XMLCh* const uri, PSVIAttributeList * psviAttributes):
        return
    # error handlers
    void logError(const SAXParseException& exc, level):
        return
    void error(const SAXParseException& exc):
        return
    void fatalError(const SAXParseException& exc):
        return
    void warning(const SAXParseException& exc):
        return
    void resetErrors():
        return  

cdef cppclass TemplatePSVIHandler(PSVIHandler):
    # psvi handlers
    void handleElementPSVI(const XMLCh* const localName, const XMLCh* const uri, PSVIElement * elementInfo):
        return
    void handlePartialElementPSVI(const XMLCh* const localName, const XMLCh* const uri, PSVIElement * elementInfo):
        return
    void handleAttributesPSVI(const XMLCh* const localName, const XMLCh* const uri, PSVIAttributeList * psviAttributes):
        return

cdef unicode getAttrValue(const Attributes& attrs, XMLCh* uri, XMLCh* localName):
    cdef const XMLCh* xmlchVal = attrs.getValue(uri, localName)
    cdef char* chVal
    cdef unicode pyVal
    if xmlchVal == NULL:
        return None
    chVal = transcode(xmlchVal)
    pyVal = chVal
    release(&chVal)
    return pyVal

cdef unicode clarkName(const XMLCh* uri, const XMLCh* prefix, const XMLCh* localName):
    cdef XMLCh* xmlchClarkName
    cdef char* chClarkName
    cdef unicode pyClarkName
    cdef int len
    if localName == NULL:
        return None
    if uri != NULL and uri[0] != chNull:
        len = stringLen(uri) + stringLen(localName) + 3
        if prefix != NULL:
            len += stringLen(prefix) + 1
        xmlchClarkName = <XMLCh*>PyMem_Malloc(len * sizeof(XMLCh))
        copyString(xmlchClarkName, xmlchLBrace)
        catString(xmlchClarkName, uri)
        catString(xmlchClarkName, xmlchRBrace)
        if prefix != NULL:
            catString(xmlchClarkName, prefix)
            catString(xmlchClarkName, xmlchColon)
        catString(xmlchClarkName, localName)
    else:
        xmlchClarkName = <XMLCh*>localName
    chClarkName = transcode(xmlchClarkName)
    if uri != NULL and uri[0] != chNull:
        PyMem_Free(xmlchClarkName)
    pyClarkName = chClarkName
    release(&chClarkName)
    return pyClarkName

cdef unicode internString(dict internedStrings, unicode pyStr):
    if pyStr is None:
        return None
    # if string is in internStrings return an interned version of str, otherwise intern str
    return internedStrings.setdefault(pyStr, pyStr)

cdef unicode internXMLChString(dict internedStrings, XMLCh* xmlchStr):
    cdef char* chStr
    cdef unicode pyStr
    if xmlchStr == NULL:
        return None
    chStr = transcode(xmlchStr)
    pyStr = chStr
    release(&chStr)
    return internString(internedStrings, pyStr)
    
cdef QName internQName(dict internedQNames, dict internedStrings, unicode pyClarkName):
    cdef unicode ns = None
    cdef unicode prefix = None
    cdef unicode ln = None
    cdef unicode _sep
    if pyClarkName is None:
        return None
    try:
        return internedQNames[pyClarkName]
    except KeyError:
        if pyClarkName.startswith("{"): # clark name
            ns, _sep, ln = pyClarkName[1:].partition('}')
            prefix, _sep, ln = ln.rpartition(":")
            if not _sep:
                prefix = None
        else:
            ln = pyClarkName
        return internedQNames.setdefault(pyClarkName, 
            QName(internString(internedStrings, ns), internString(internedStrings, prefix), internString(internedStrings, ln)))

cdef bool isAbsoluteUrl(object url):
    cdef unicode scheme, _sep, path
    if url:
        scheme, _sep, path = url.partition("#")[0].partition(":")
        if scheme == "http" or scheme == "https" or scheme == "ftp":
            return path.startswith("//")
        if scheme == "urn":
            return True
    return False



