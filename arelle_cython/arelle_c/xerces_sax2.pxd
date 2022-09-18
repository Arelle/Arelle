from xerces_ctypes cimport XMLCh, XMLSize_t
from xerces_framework cimport XMLGrammarPool, XMLPScanToken, PSVIHandler
from xerces_framework_memory_manager cimport MemoryManager
from xerces_sax cimport InputSource, DocumentHandler, ErrorHandler, EntityResolver, SAXParseException, Locator
from xerces_util cimport XMLEntityResolver
from xerces_validators cimport GrammarType, SchemaGrammar
from libcpp cimport bool

cdef extern from "xercesc/sax2/ContentHandler.hpp" namespace "xercesc":
    cdef cppclass ContentHandler:
        ContentHandler() except +
        void characters(const XMLCh* chars, const XMLSize_t length)
        void endDocument()
        void endElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname)
        void ignorableWhitespace(const XMLCh* chars, const XMLSize_t length)
        void processingInstruction(const XMLCh* target, const XMLCh* data)
        void setDocumentLocator(const Locator* const locator)
        void startDocument()
        void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs)
        void startPrefixMapping(const XMLCh* prefix, const XMLCh* uri)
        void endPrefixMapping(const XMLCh* prefix)
        void skippedEntity(const XMLCh* name)

cdef extern from "xercesc/sax2/LexicalHandler.hpp" namespace "xercesc":
    cdef cppclass LexicalHandler:
        LexicalHandler() except +
        void comment(const XMLCh* chars, const XMLSize_t length)
        void endCDATA()
        void endDTD()
        void endEntity(const XMLCh* name)
        void startCDATA()
        void startDTD(const XMLCh* name, const XMLCh* publicId, const XMLCh* systemId)
        void startEntity(const XMLCh* name)

cdef extern from "xercesc/sax2/Attributes.hpp" namespace "xercesc":
    cdef cppclass Attributes:
        const XMLSize_t getLength()
        const XMLCh* getURI(const XMLSize_t index)
        const XMLCh* getLocalName(const XMLSize_t index)
        const XMLCh* getQName(const XMLSize_t index)
        const XMLCh* getType(const XMLSize_t index)
        const XMLCh* getValue(const XMLSize_t index)
        bool getIndex(const XMLCh* uri, const XMLCh* localPart, const XMLSize_t& index)
        int getIndex(const XMLCh* uri, const XMLCh* localPart )
        bool getIndex(const XMLCh* qName, const XMLSize_t& index)
        int getIndex(const XMLCh* qName)
        const XMLCh* getType(const XMLCh* uri, const XMLCh* localPart )
        const XMLCh* getType(const XMLCh* qName)
        const XMLCh* getValue(const XMLCh* uri, const XMLCh* localPart )
        const XMLCh* getValue(const XMLCh* qName)

cdef extern from "xercesc/sax2/SAX2XMLReader.hpp" namespace "xercesc":
    cdef cppclass SAX2XMLReader:
        void setFeature(const XMLCh*, bool)
        bool getFeature(const XMLCh* const name)
        void setProperty(const XMLCh* const name, void* value)
        void setContentHandler( ContentHandler* )
        ContentHandler* getContentHandler()
        void setLexicalHandler( LexicalHandler* )
        void setErrorHandler( ErrorHandler* )
        void setEntityResolver( EntityResolver* )
        void parse( InputSource& )
        void parse( const XMLCh* )
        void parse( const char* )
        SchemaGrammar* loadGrammar(const InputSource& source, const GrammarType grammarType, const bool toCache)
        SchemaGrammar* getGrammar(const XMLCh* const nameSpaceKey)
        SchemaGrammar* getRootGrammar()
        bool parseFirst( const XMLCh* const systemId, XMLPScanToken& toFill) except +
        bool parseFirst( const char* const systemId, XMLPScanToken& toFill) except +
        bool parseFirst( const InputSource& source, XMLPScanToken& toFill) except +
        bool parseNext(XMLPScanToken& token)
        void parseReset(XMLPScanToken& token)

cdef extern from "xercesc/parsers/SAX2XMLReaderImpl.hpp" namespace "xercesc":
    cdef cppclass SAX2XMLReaderImpl:
        SAX2XMLReaderImpl()
        SAX2XMLReaderImpl(MemoryManager* const  manager, XMLGrammarPool* const gramPool) except +
        void setFeature( const XMLCh*, bool )
        bool getFeature(const XMLCh* const name)
        void setProperty(const XMLCh* const name, void* value)
        void setContentHandler( ContentHandler* )
        ContentHandler* getContentHandler()
        void setLexicalHandler( LexicalHandler* )
        void setErrorHandler( ErrorHandler* )
        void setEntityResolver( EntityResolver* )
        void setXMLEntityResolver( XMLEntityResolver* )
        void setPSVIHandler(PSVIHandler* const handler)
        void parse( InputSource& ) except +
        void parse( const XMLCh* ) except +
        void parse( const char* ) except +
        SchemaGrammar* loadGrammar(const InputSource& source, const GrammarType grammarType, const bool toCache)
        SchemaGrammar* getGrammar(const XMLCh* const nameSpaceKey)
        SchemaGrammar* getRootGrammar()
        bool parseFirst( const XMLCh* const systemId, XMLPScanToken& toFill) except +
        bool parseFirst( const char* const systemId, XMLPScanToken& toFill) except +
        bool parseFirst( const InputSource& source, XMLPScanToken& toFill) except +
        bool parseNext(XMLPScanToken& token)
        void parseReset(XMLPScanToken& token)
        #void installAdvDocHandler(XMLDocumentHandler* const toInstall)
        
cdef extern from "xercesc/sax2/XMLReaderFactory.hpp" namespace "xercesc::XMLReaderFactory":
    SAX2XMLReader * createXMLReader( )
    SAX2XMLReader * createXMLReader(  MemoryManager* const  manager, XMLGrammarPool* const gramPool)

cdef extern from "xercesc/sax2/DefaultHandler.hpp" namespace "xercesc":
    cdef cppclass DefaultHandler:
        DefaultHandler() except +
        void characters(const XMLCh* chars, const XMLSize_t length)
        void endDocument()
        void endElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname)
        void ignorableWhitespace(const XMLCh* chars, const XMLSize_t length)
        void processingInstruction(const XMLCh* target, const XMLCh* data)
        void resetDocument()
        void setDocumentLocator(Locator* locator)
        void startDocument()
        void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, Attributes& attrs)
        void startPrefixMapping(const XMLCh* prefix, const XMLCh* uri)
        void endPrefixMapping(const XMLCh* prefix)
        void skippedEntity(const XMLCh* name)
        InputSource* resolveEntity(const XMLCh* publicId, const XMLCh* systemId)
        void error(SAXParseException& exc)
        void fatalError(SAXParseException& exc)
        void warning(SAXParseException& exc)
        void resetErrors()
        void notationDecl(const XMLCh* name, const XMLCh* publicId, const XMLCh* systemId)
        void resetDocType()
        void unparsedEntityDecl(const XMLCh* name, const XMLCh* publicId, const XMLCh* systemId, const XMLCh* notationName)
        void comment(const XMLCh* chars, const XMLSize_t length)
        void endCDATA()
        void endDTD()
        void endEntity(const XMLCh* name)
        void startCDATA()
        void startDTD(const XMLCh* name, const XMLCh* publicId, const XMLCh* systemId)
        void startEntity(const XMLCh* name)
        void elementDecl(const XMLCh* name, const XMLCh* model)
        void attributeDecl(const XMLCh* eName, const XMLCh* aName, const XMLCh* type, const XMLCh* mode, const XMLCh* value)
        void internalEntityDecl(const XMLCh* name, const XMLCh* value)
        void externalEntityDecl(const XMLCh* name, const XMLCh* publicId, const XMLCh* systemId)
    

