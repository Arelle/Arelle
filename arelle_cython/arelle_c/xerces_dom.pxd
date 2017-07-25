from xerces_ctypes cimport XMLCh, XMLSize_t
from xerces_parsers cimport XercesDOMParser
from xerces_framework_memory_manager cimport MemoryManager
from xerces_framework cimport XMLGrammarPool

cdef extern from "xercesc/dom/DOM.hpp" namespace "xercesc":
    cdef cppclass DOMDocument:
        DOMNode* getDocumentElement()
    cdef cppclass DOMNode:
        const XMLCh* getNodeName()
        const XMLCh* getLocalName()
        const XMLCh* getNamespaceURI()
        const XMLCh* getPrefix()
        const XMLCh* getNodeValue()
        DOMNode* getFirstChild()
        DOMNodeList* getChildNodes()
        DOMNode* getNextSibling()
        NodeType getNodeType()

    cdef cppclass DOMNodeList:
        DOMNode* item( XMLSize_t index )
        XMLSize_t getLength()
    cdef cppclass DOMElement(DOMNode):
        XMLCh* getTagName()
    cdef cppclass DOMText(DOMNode):
        const XMLCh* getWholeText()

cdef extern from "xercesc/dom/DOM.hpp" namespace "xercesc::DOMNode":
    ctypedef enum NodeType:
        ELEMENT_NODE                = 1
        ATTRIBUTE_NODE              = 2
        TEXT_NODE                   = 3
        CDATA_SECTION_NODE          = 4
        ENTITY_REFERENCE_NODE       = 5
        ENTITY_NODE                 = 6
        PROCESSING_INSTRUCTION_NODE = 7
        COMMENT_NODE                = 8
        DOCUMENT_NODE               = 9
        DOCUMENT_TYPE_NODE          = 10
        DOCUMENT_FRAGMENT_NODE      = 11
        NOTATION_NODE               = 12

cdef extern from "xercesc/dom/DOMImplementationRegistry.hpp" namespace "xercesc::DOMImplementationRegistry":
    DOMImplementationLS* getDOMImplementation(const XMLCh* features)
        
cdef extern from "xercesc/dom/DOMImplementationLS.hpp" namespace "xercesc::DOMImplementationLS":
    ctypedef enum DOMImplementationLSMode:
        MODE_SYNCHRONOUS = 1,
        MODE_ASYNCHRONOUS = 2
        
cdef extern from "xercesc/dom/DOMImplementationLS.hpp" namespace "xercesc":
    cdef cppclass DOMImplementationLS:
        XercesDOMParser* createLSParser(const DOMImplementationLSMode mode,
                                        const XMLCh* const     schemaType,
                                        MemoryManager* const   manager,
                                        XMLGrammarPool*  const gramPool)
        XercesDOMParser* createLSParser(const DOMImplementationLSMode mode,
                                        const XMLCh* const     schemaType)

