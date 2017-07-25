from arelle_c.xerces_sax2 cimport Attributes
from arelle_c.xerces_util cimport XMLCh, XMLSize_t, XMLByte
from arelle_c.xerces_framework cimport LocalFileInputSource, MemBufInputSource
from arelle_c.xerces_sax cimport InputSource, ErrorHandler, SAXParseException, Locator
from arelle_c.xerces_sax2 cimport ContentHandler, LexicalHandler, DefaultHandler
from libcpp.string cimport string

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

cdef InputSource* fileDescInputSource( pyFileDesc ):
    cdef const char* c_s
    #cdef string std_s
    cdef XMLCh* xmlChFile
    cdef XMLCh* xmlChUrl
    cdef InputSource* inpSrc = NULL
    cdef bool adoptBuffer
    cdef bytes b_str
    cdef XMLByte* xmlByteStr
    if hasattr(pyFileDesc, "bytes"):
        b_str = pyFileDesc.bytes
        c_s = b_str # fast operation, pointer is tied to life time of python bytes string in fileDesc object
        xmlByteStr = <XMLByte*>c_s # avoid copying byte content to another buffer and depend on fileDesc lifetime for contents
        if hasattr(pyFileDesc, "filepath"): 
            byte_s = pyFileDesc.filepath.encode("utf-8")
        else:
            byte_s = b"(in memory, no filename provided, no xml base or relative hrefs possible)"
        c_s = byte_s
        xmlChFile = transcode(c_s)
        adoptBuffer = False
        inpSrc = ( new MemBufInputSource( xmlByteStr, len(b_str), xmlChFile, adoptBuffer ))
        release(&xmlChFile)
    elif hasattr(pyFileDesc, "filepath"): 
        byte_s = pyFileDesc.filepath.encode("utf-8")
        c_s = byte_s
        xmlChFile = transcode(c_s)
        inpSrc = ( new LocalFileInputSource( xmlChFile ))
        release(&xmlChFile)
    byte_s = None
    return inpSrc

cdef cppclass TemplateSAX2Handler(ErrorHandler, LexicalHandler, ContentHandler):
    # document handlers
    void characters(const XMLCh* chars, const XMLSize_t length):
        pass # needed if any analyzed element contents were to be significant
    void endDocument():
        pass 
    void endElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname):
        pass
    void ignorableWhitespace(const XMLCh* chars, const XMLSize_t length):
        pass
    void processingInstruction(const XMLCh* target, const XMLCh* data):
        pass
    void setDocumentLocator(const Locator* const locator):
        pass
    void startDocument():
        pass
    void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs):
        pass
    void startPrefixMapping(const XMLCh* prefix, const XMLCh* uri):
        pass
    void endPrefixMapping(const XMLCh* prefix):
        pass
    void skippedEntity(const XMLCh* name):
        pass
    void comment(const XMLCh* chars, const XMLSize_t length):
        pass
    void endCDATA():
        pass
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
    void logError(const SAXParseException& exc, level):
        pass
    void error(const SAXParseException& exc):
        pass
    void fatalError(const SAXParseException& exc):
        pass
    void warning(const SAXParseException& exc):
        pass
    void resetErrors():
        pass  

cdef getAttrValue(const Attributes& attrs, XMLCh* uri, XMLCh* localName):
    cdef object _pyValue
    cdef const XMLCh* _XmlValue = attrs.getValue(uri, localName)
    cdef char* _charValue
    if _XmlValue == NULL:
        return None
    _charValue = transcode(_XmlValue)
    _pyValue = _charValue
    release(&_charValue)
    return _pyValue