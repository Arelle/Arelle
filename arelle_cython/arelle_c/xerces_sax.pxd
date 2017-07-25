from xerces_ctypes cimport XMLCh, XMLSize_t, XMLFileLoc
from libcpp cimport bool

cdef extern from "xercesc/sax/InputSource.hpp" namespace "xercesc":
    cdef cppclass InputSource:
        InputSource()
        const XMLCh* getEncoding()
        const XMLCh* getPublicId()
        const XMLCh* getSystemId()
        bool getIssueFatalErrorIfNotFound()
        void setEncoding(const XMLCh* const encodingStr)
        void setPublicId(const XMLCh* const publicId)
        void setSystemId(const XMLCh* const systemId)
        void setIssueFatalErrorIfNotFound(const bool flag)

cdef extern from "xercesc/sax/SAXException.hpp" namespace "xercesc":
    cdef cppclass SAXParseException:
        SAXParseException()
        const XMLCh* getMessage()
        XMLFileLoc getColumnNumber()
        XMLFileLoc getLineNumber()
        const XMLCh* getPublicId()
        const XMLCh* getSystemId()
        
cdef extern from "xercesc/sax/AttributeList.hpp" namespace "xercesc":
    cdef cppclass AttributeList:
        AttributeList()
        XMLSize_t getLength()
        XMLCh* getName(XMLSize_t index)
        XMLCh* getType(XMLSize_t index)
        XMLCh* getValue(XMLSize_t index)
        XMLCh* getType(XMLCh* name)
        XMLCh* getValue(XMLCh* name)
        XMLCh* getValue(char* name)
        
cdef extern from "xercesc/sax/Locator.hpp" namespace "xercesc":
    cdef cppclass Locator:
        XMLCh* getPublicId()
        XMLCh* getSystemId()
        XMLFileLoc getLineNumber()
        XMLFileLoc getColumnNumber()
        
cdef extern from "xercesc/sax/DocumentHandler.hpp" namespace "xercesc":
    cdef cppclass DocumentHandler:
        DocumentHandler() except +
        void characters(XMLCh* chars, XMLSize_t length)
        void endDocument()
        void endElement(XMLCh* uri, XMLCh* localname, XMLCh* qname)
        void ignorableWhitespace(XMLCh* chars, XMLSize_t length)
        void processingInstruction(XMLCh* target, XMLCh* data)
        void resetDocument()
        void setDocumentLocator(Locator* locator)
        void startDocument()
        void startElement(XMLCh* name, AttributeList&  attrs)

cdef extern from "xercesc/sax/EntityResolver.hpp" namespace "xercesc":
    cdef cppclass EntityResolver:
        EntityResolver() except +
        InputSource* resolveEntity(const XMLCh* const publicId, const XMLCh* const systemId)

cdef extern from "xercesc/sax/ErrorHandler.hpp" namespace "xercesc":
    cdef cppclass ErrorHandler:
        ErrorHandler() except +
        void error(const SAXParseException& exc)
        void fatalError(const SAXParseException& exc)
        void warning(const SAXParseException& exc)
        void resetErrors()
