from xerces_ctypes cimport XMLCh
from xerces_sax cimport InputSource, ErrorHandler
from xerces_dom cimport DOMDocument, DOMNode
from xerces_validators cimport GrammarType, SchemaGrammar
from libcpp cimport bool

cdef extern from "xercesc/parsers/XercesDOMParser.hpp" namespace "xercesc:XercesDOMParser":
    cdef enum ValSchemes:
        Val_Never,
        Val_Always,
        Val_Auto

cdef extern from "xercesc/parsers/XercesDOMParser.hpp" namespace "xercesc":
    cdef cppclass XercesDOMParser:
        void setGenerateSyntheticAnnotations(const bool newValue)
        void setValidateAnnotations(const bool newValue)
        void setDoNamespaces(const bool newState)
        void setExitOnFirstFatalError(const bool newState)
        void setValidationConstraintFatal(const bool newState)
        void setCreateEntityReferenceNodes(const bool create)
        void setIncludeIgnorableWhitespace(const bool)
        void setValidationScheme(const ValSchemes newScheme)
        void setDoSchema(const bool newState)
        void setValidationSchemaFullChecking(const bool schemaFullChecking)
        void setIdentityConstraintChecking(const bool newState)
        void setExternalSchemaLocation(const XMLCh* const schemaLocation)
        void setExternalSchemaLocation(const char* const schemaLocation)
        void setExternalNoNamespaceSchemaLocation(const XMLCh* const noNamespaceSchemaLocation)
        void setExternalNoNamespaceSchemaLocation(const char* const noNamespaceSchemaLocation)
        void setLoadExternalDTD(const bool newState)
        void setLoadSchema(const bool newState)
        void setCreateCommentNodes(const bool create)
        void setCalculateSrcOfs(const bool newState)
        void setStandardUriConformant(const bool newState)
        void useScanner(const XMLCh* const scannerName)
        void useCachedGrammarInParse(const bool newState)
        void cacheGrammarFromParse(const bool newState)
        # void setPSVIHandler(PSVIHandler* const handler)
        void  setCreateSchemaInfo(const bool newState)
        void  setDoXInclude(const bool newState)
        void setIgnoreAnnotations(const bool newValue)
        void setDisableDefaultEntityResolution(const bool newValue)
        void setSkipDTDValidation(const bool newValue)
        void setHandleMultipleImports(const bool newValue)
        void setCurrentNode(DOMNode* toSet)
        void setDocument(DOMDocument* toSet)
        void setParseInProgress(const bool toSet)
        void setErrorHandler(ErrorHandler* const handler)
        void parse( InputSource& )
        DOMDocument* getDocument()
        SchemaGrammar* loadGrammar(const InputSource& source, const GrammarType grammarType, const bool toCache)
