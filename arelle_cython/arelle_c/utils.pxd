from arelle_c.xerces_sax2 cimport Attributes
from xerces_sax cimport InputSource, ErrorHandler, SAXParseException, Locator
from arelle_c.xerces_framework cimport LocalFileInputSource, MemBufInputSource
from arelle_c.xerces_sax2 cimport ContentHandler, LexicalHandler
from arelle_c.xerces_util cimport XMLCh, XMLSize_t

cdef cppclass TemplateSAX2Handler(ErrorHandler, LexicalHandler, ContentHandler, PSVIHandler):
    # document handlers
    void characters(const XMLCh* chars, const XMLSize_t length)
    void endDocument()
    void endElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname)
    void ignorableWhitespace(const XMLCh* chars, const XMLSize_t length)
    void processingInstruction(const XMLCh* target, const XMLCh* data)
    void setDocumentLocator(const Locator* const locator)
    void startDocument()
    void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs)
    void startPrefixMapping(const XMLCh* prefix, const XMLCh* uri)
    void handleAttributesPSVI(const XMLCh* localName, const XMLCh* uri, PSVIAttributeList* psviAttributes)
    void handleElementPSVI(const XMLCh* localName, const XMLCh* uri, PSVIElement* ei)
    void endPrefixMapping(const XMLCh* prefix)
    void skippedEntity(const XMLCh* name)
    void comment(const XMLCh* chars, const XMLSize_t length)
    void endCDATA()
    void endDTD()
    void endEntity(const XMLCh* name)
    void startCDATA()
    void startDTD(const XMLCh* name, const XMLCh* publicId, const XMLCh* systemId)
    void startEntity(const XMLCh* name)
    void elementDecl(const XMLCh* name, const XMLCh* model)
    # error handlers
    void logError(const SAXParseException& exc, level)
    void error(const SAXParseException& exc)
    void fatalError(const SAXParseException& exc)
    void warning(const SAXParseException& exc)
    void resetErrors()
