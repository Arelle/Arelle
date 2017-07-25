from xerces_ctypes cimport XMLCh, XMLSize_t
from xerces_framework cimport XSAnnotation, XMLElementDecl
from xerces_util cimport QName, RefHash3KeysIdPoolEnumerator, StringHasher
from libcpp cimport bool

cdef extern from "xercesc/validators/common/Grammar.hpp" namespace "xercesc::Grammar":
    ctypedef enum GrammarType:
        DTDGrammarType
        SchemaGrammarType
        UnKnown

cdef extern from "xercesc/validators/schema/SchemaGrammar.hpp" namespace "xercesc":
    cdef cppclass SchemaGrammar:
        GrammarType getGrammarType()
        const XMLCh* getTargetNamespace()
        #XMLElementDecl* findOrAddElemDecl(const unsigned int uriId
        #    , const XMLCh* const    baseName
        #    , const XMLCh* const    prefixName
        #    , const XMLCh* const    qName
        #    , unsigned int          scope
        #    ,       bool&           wasAdded
        #    )
        XMLSize_t getElemId(
            const   unsigned int    uriId
            , const XMLCh* const    baseName
            , const XMLCh* const    qName
            , unsigned int          scope
        )
        void setValidated(const bool newState)
        void reset()
        #XMLGrammarDescription*  getGrammarDescription()
        XSAnnotation* getAnnotation(const void* const key)
        XSAnnotation* getAnnotation()
        XMLElementDecl* getElemDecl (const unsigned int elemId)
        RefHash3KeysIdPoolEnumerator[SchemaElementDecl,StringHasher] getElemEnumerator()

cdef extern from "xercesc/validators/schema/SchemaElementDecl.hpp" namespace "xercesc::SchemaElementDecl":
    ctypedef enum ModelTypes:
        Empty
        Any
        Mixed_Simple
        Mixed_Complex
        Children
        Simple
        ElementOnlyEmpty
        ModelTypes_Count

cdef extern from "xercesc/validators/schema/SchemaElementDecl.hpp" namespace "xercesc":
    cdef cppclass SchemaElementDecl:
        ModelTypes getModelType()
        const XMLCh* getBaseName()
        const QName* getElementName()
        const XMLCh* getFullName()
        
"""        
        const XMLElementDecl* getElemDecl(
            const   unsigned int    uriId
            , const XMLCh* const    baseName
            , const XMLCh* const    qName
            , unsigned int          scope
        )
        const XMLElementDecl* getElemDecl(
            const   unsigned int    uriId
            , const XMLCh* const    baseName
            , const XMLCh* const    qName
            , unsigned int          scope
        )
        const XMLElementDecl* getElemDecl(
            const   unsigned int    elemId
        )
        const XMLNotationDecl* getNotationDecl(
            const   XMLCh* const    notName
        )
        XMLNotationDecl* getNotationDecl(
            const   XMLCh* const    notName
        )
        void     storeGrammar(XSerializeEngine&        serEng
                               , Grammar* const        grammar)
"""