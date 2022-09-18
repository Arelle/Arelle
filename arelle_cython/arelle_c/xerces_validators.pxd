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

cdef extern from "xercesc/validators/schema/SchemaSymbols.hpp" namespace "xercesc::SchemaSymbols":
    cdef const XMLCh* fgURI_XSI
    cdef const XMLCh* fgURI_SCHEMAFORSCHEMA
    cdef const XMLCh* fgXSI_SCHEMALOCACTION
    cdef const XMLCh* fgXSI_NONAMESPACESCHEMALOCACTION
    cdef const XMLCh* fgXSI_SCHEMALOCATION
    cdef const XMLCh* fgXSI_NONAMESPACESCHEMALOCATION
    cdef const XMLCh* fgXSI_TYPE
    cdef const XMLCh* fgELT_ALL
    cdef const XMLCh* fgELT_ANNOTATION
    cdef const XMLCh* fgELT_ANY
    cdef const XMLCh* fgELT_WILDCARD
    cdef const XMLCh* fgELT_ANYATTRIBUTE
    cdef const XMLCh* fgELT_APPINFO
    cdef const XMLCh* fgELT_ATTRIBUTE
    cdef const XMLCh* fgELT_ATTRIBUTEGROUP
    cdef const XMLCh* fgELT_CHOICE
    cdef const XMLCh* fgELT_COMPLEXTYPE
    cdef const XMLCh* fgELT_CONTENT
    cdef const XMLCh* fgELT_DOCUMENTATION
    cdef const XMLCh* fgELT_DURATION
    cdef const XMLCh* fgELT_ELEMENT
    cdef const XMLCh* fgELT_ENCODING
    cdef const XMLCh* fgELT_ENUMERATION
    cdef const XMLCh* fgELT_FIELD
    cdef const XMLCh* fgELT_WHITESPACE
    cdef const XMLCh* fgELT_GROUP
    cdef const XMLCh* fgELT_IMPORT
    cdef const XMLCh* fgELT_INCLUDE
    cdef const XMLCh* fgELT_REDEFINE
    cdef const XMLCh* fgELT_KEY
    cdef const XMLCh* fgELT_KEYREF
    cdef const XMLCh* fgELT_LENGTH
    cdef const XMLCh* fgELT_MAXEXCLUSIVE
    cdef const XMLCh* fgELT_MAXINCLUSIVE
    cdef const XMLCh* fgELT_MAXLENGTH
    cdef const XMLCh* fgELT_MINEXCLUSIVE
    cdef const XMLCh* fgELT_MININCLUSIVE
    cdef const XMLCh* fgELT_MINLENGTH
    cdef const XMLCh* fgELT_NOTATION
    cdef const XMLCh* fgELT_PATTERN
    cdef const XMLCh* fgELT_PERIOD
    cdef const XMLCh* fgELT_TOTALDIGITS
    cdef const XMLCh* fgELT_FRACTIONDIGITS
    cdef const XMLCh* fgELT_SCHEMA
    cdef const XMLCh* fgELT_SELECTOR
    cdef const XMLCh* fgELT_SEQUENCE
    cdef const XMLCh* fgELT_SIMPLETYPE
    cdef const XMLCh* fgELT_UNION
    cdef const XMLCh* fgELT_LIST
    cdef const XMLCh* fgELT_UNIQUE
    cdef const XMLCh* fgELT_COMPLEXCONTENT
    cdef const XMLCh* fgELT_SIMPLECONTENT
    cdef const XMLCh* fgELT_RESTRICTION
    cdef const XMLCh* fgELT_EXTENSION
    cdef const XMLCh* fgATT_ABSTRACT
    cdef const XMLCh* fgATT_ATTRIBUTEFORMDEFAULT
    cdef const XMLCh* fgATT_BASE
    cdef const XMLCh* fgATT_ITEMTYPE
    cdef const XMLCh* fgATT_MEMBERTYPES
    cdef const XMLCh* fgATT_BLOCK
    cdef const XMLCh* fgATT_BLOCKDEFAULT
    cdef const XMLCh* fgATT_DEFAULT
    cdef const XMLCh* fgATT_ELEMENTFORMDEFAULT
    cdef const XMLCh* fgATT_SUBSTITUTIONGROUP
    cdef const XMLCh* fgATT_FINAL
    cdef const XMLCh* fgATT_FINALDEFAULT
    cdef const XMLCh* fgATT_FIXED
    cdef const XMLCh* fgATT_FORM
    cdef const XMLCh* fgATT_ID
    cdef const XMLCh* fgATT_MAXOCCURS
    cdef const XMLCh* fgATT_MINOCCURS
    cdef const XMLCh* fgATT_NAME
    cdef const XMLCh* fgATT_NAMESPACE
    cdef const XMLCh* fgATT_NILL
    cdef const XMLCh* fgATT_NILLABLE
    cdef const XMLCh* fgATT_PROCESSCONTENTS
    cdef const XMLCh* fgATT_REF
    cdef const XMLCh* fgATT_REFER
    cdef const XMLCh* fgATT_SCHEMALOCATION
    cdef const XMLCh* fgATT_SOURCE
    cdef const XMLCh* fgATT_SYSTEM
    cdef const XMLCh* fgATT_PUBLIC
    cdef const XMLCh* fgATT_TARGETNAMESPACE
    cdef const XMLCh* fgATT_TYPE
    cdef const XMLCh* fgATT_USE
    cdef const XMLCh* fgATT_VALUE
    cdef const XMLCh* fgATT_MIXED
    cdef const XMLCh* fgATT_VERSION
    cdef const XMLCh* fgATT_XPATH
    cdef const XMLCh* fgATTVAL_TWOPOUNDANY
    cdef const XMLCh* fgATTVAL_TWOPOUNDLOCAL
    cdef const XMLCh* fgATTVAL_TWOPOUNDOTHER
    cdef const XMLCh* fgATTVAL_TWOPOUNDTRAGETNAMESPACE
    cdef const XMLCh* fgATTVAL_POUNDALL
    cdef const XMLCh* fgATTVAL_BASE64
    cdef const XMLCh* fgATTVAL_BOOLEAN
    cdef const XMLCh* fgATTVAL_DEFAULT
    cdef const XMLCh* fgATTVAL_ELEMENTONLY
    cdef const XMLCh* fgATTVAL_EMPTY
    cdef const XMLCh* fgATTVAL_EXTENSION
    cdef const XMLCh* fgATTVAL_FALSE
    cdef const XMLCh* fgATTVAL_FIXED
    cdef const XMLCh* fgATTVAL_HEX
    cdef const XMLCh* fgATTVAL_ID
    cdef const XMLCh* fgATTVAL_LAX
    cdef const XMLCh* fgATTVAL_MAXLENGTH
    cdef const XMLCh* fgATTVAL_MINLENGTH
    cdef const XMLCh* fgATTVAL_MIXED
    cdef const XMLCh* fgATTVAL_NCNAME
    cdef const XMLCh* fgATTVAL_OPTIONAL
    cdef const XMLCh* fgATTVAL_PROHIBITED
    cdef const XMLCh* fgATTVAL_QNAME
    cdef const XMLCh* fgATTVAL_QUALIFIED
    cdef const XMLCh* fgATTVAL_REQUIRED
    cdef const XMLCh* fgATTVAL_RESTRICTION
    cdef const XMLCh* fgATTVAL_SKIP
    cdef const XMLCh* fgATTVAL_STRICT
    cdef const XMLCh* fgATTVAL_STRING
    cdef const XMLCh* fgATTVAL_TEXTONLY
    cdef const XMLCh* fgATTVAL_TIMEDURATION
    cdef const XMLCh* fgATTVAL_TRUE
    cdef const XMLCh* fgATTVAL_UNQUALIFIED
    cdef const XMLCh* fgATTVAL_URI
    cdef const XMLCh* fgATTVAL_URIREFERENCE
    cdef const XMLCh* fgATTVAL_SUBSTITUTIONGROUP
    cdef const XMLCh* fgATTVAL_SUBSTITUTION
    cdef const XMLCh* fgATTVAL_ANYTYPE
    cdef const XMLCh* fgWS_PRESERVE
    cdef const XMLCh* fgWS_COLLAPSE
    cdef const XMLCh* fgWS_REPLACE
    cdef const XMLCh* fgDT_STRING
    cdef const XMLCh* fgDT_TOKEN
    cdef const XMLCh* fgDT_LANGUAGE
    cdef const XMLCh* fgDT_NAME
    cdef const XMLCh* fgDT_NCNAME
    cdef const XMLCh* fgDT_INTEGER
    cdef const XMLCh* fgDT_DECIMAL
    cdef const XMLCh* fgDT_BOOLEAN
    cdef const XMLCh* fgDT_NONPOSITIVEINTEGER
    cdef const XMLCh* fgDT_NEGATIVEINTEGER
    cdef const XMLCh* fgDT_LONG
    cdef const XMLCh* fgDT_INT
    cdef const XMLCh* fgDT_SHORT
    cdef const XMLCh* fgDT_BYTE
    cdef const XMLCh* fgDT_NONNEGATIVEINTEGER
    cdef const XMLCh* fgDT_ULONG
    cdef const XMLCh* fgDT_UINT
    cdef const XMLCh* fgDT_USHORT
    cdef const XMLCh* fgDT_UBYTE
    cdef const XMLCh* fgDT_POSITIVEINTEGER
    cdef const XMLCh* fgDT_DATETIME
    cdef const XMLCh* fgDT_DATE
    cdef const XMLCh* fgDT_TIME
    cdef const XMLCh* fgDT_DURATION
    cdef const XMLCh* fgDT_DAY
    cdef const XMLCh* fgDT_MONTH
    cdef const XMLCh* fgDT_MONTHDAY
    cdef const XMLCh* fgDT_YEAR
    cdef const XMLCh* fgDT_YEARMONTH
    cdef const XMLCh* fgDT_BASE64BINARY
    cdef const XMLCh* fgDT_HEXBINARY
    cdef const XMLCh* fgDT_FLOAT
    cdef const XMLCh* fgDT_DOUBLE
    cdef const XMLCh* fgDT_URIREFERENCE
    cdef const XMLCh* fgDT_ANYURI
    cdef const XMLCh* fgDT_QNAME
    cdef const XMLCh* fgDT_NORMALIZEDSTRING
    cdef const XMLCh* fgDT_ANYSIMPLETYPE
    cdef const XMLCh* fgRegEx_XOption
    cdef const XMLCh* fgRedefIdentifier
    cdef const int fgINT_MIN_VALUE
    cdef const int fgINT_MAX_VALUE

    ctypedef enum SCHEMA_SYMBOLS:
        XSD_EMPTYSET = 0
        XSD_SUBSTITUTION = 1
        XSD_EXTENSION = 2
        XSD_RESTRICTION = 4
        XSD_LIST = 8
        XSD_UNION = 16
        XSD_ENUMERATION = 32

        # group orders
        XSD_CHOICE = 0
        XSD_SEQUENCE= 1
        XSD_ALL = 2

        XSD_UNBOUNDED = -1
        XSD_NILLABLE = 1
        XSD_ABSTRACT = 2
        XSD_FIXED = 4
