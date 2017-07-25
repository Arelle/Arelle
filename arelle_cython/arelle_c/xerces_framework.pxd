from xerces_util cimport QName, XMLCh, XMemory, XMLByte, XMLSize_t, RefArrayVectorOf, RefVectorOf
from xerces_sax cimport InputSource
from xerces_sax2 cimport ContentHandler
from xerces_framework_memory_manager cimport MemoryManager
from libcpp cimport bool

ctypedef RefVectorOf[XSAnnotation] XSAnnotationList
ctypedef RefVectorOf[XSAttributeUse] XSAttributeUseList
ctypedef RefVectorOf[XSFacet] XSFacetList
ctypedef RefVectorOf[XSMultiValueFacet] XSMultiValueFacetList
ctypedef RefVectorOf[XSNamespaceItem] XSNamespaceItemList
ctypedef RefVectorOf[XSParticle] XSParticleList
ctypedef RefVectorOf[XSSimpleTypeDefinition] XSSimpleTypeDefinitionList
ctypedef RefArrayVectorOf[XMLCh] StringList

cdef extern from "xercesc/framework/LocalFileInputSource.hpp" namespace "xercesc":
    cdef cppclass LocalFileInputSource( InputSource ):
        LocalFileInputSource( const XMLCh* const filePath )

cdef extern from "xercesc/framework/MemBufInputSource.hpp" namespace "xercesc":
    cdef cppclass MemBufInputSource( InputSource ):
        MemBufInputSource( XMLByte*, XMLSize_t, XMLCh*, bool )

cdef extern from "xercesc/framework/XMLPScanToken.hpp" namespace "xercesc":
    cdef cppclass XMLPScanToken:
        XMLPScanToken()

cdef extern from "xercesc/framework/psvi/PSVIAttribute.hpp" namespace "xercesc":
    cdef cppclass PSVIAttribute:
        PSVIAttribute()
        XSAttributeDeclaration *getAttributeDeclaration()
        XSTypeDefinition *getTypeDefinition()
        XSSimpleTypeDefinition *getMemberTypeDefinition()

cdef extern from "xercesc/framework/psvi/PSVIAttributeList.hpp" namespace "xercesc":
    cdef cppclass PSVIAttributeList:
        PSVIAttributeList()
        XMLSize_t getLength() const
        const XMLCh *getAttributeNamespaceAtIndex(const XMLSize_t index)
        PSVIAttribute *getAttributePSVIByName(const XMLCh *attrName, const XMLCh * attrNamespace)
        
cdef extern from "xercesc/framework/psvi/PSVIElement.hpp" namespace "xercesc":
    cdef cppclass PSVIElement:
        PSVIElement()
        XSElementDeclaration *getElementDeclaration()
        XSNotationDeclaration *getNotationDeclaration()
        XSModel *getSchemaInformation()
        XSTypeDefinition *getTypeDefinition()
        XSSimpleTypeDefinition *getMemberTypeDefinition()
        
cdef extern from "xercesc/framework/psvi/PSVIHandler.hpp" namespace "xercesc":
    cdef cppclass PSVIHandler:
        PSVIHandler()
        void handleElementPSVI(const XMLCh* const localName, const XMLCh* const uri, PSVIElement * elementInfo)
        void handlePartialElementPSVI(const XMLCh* const localName, const XMLCh* const uri, PSVIElement * elementInfo)
        void handleAttributesPSVI(const XMLCh* const localName, const XMLCh* const uri, PSVIAttributeList * psviAttributes)

cdef extern from "xercesc/framework/psvi/XSAnnotation.hpp" namespace "xercesc":
    cdef cppclass XSAnnotation:
        const XMLCh* getAnnotationString()
        void writeAnnotation(ContentHandler* handler)
        XSAnnotation* getNext()
        
cdef extern from "xercesc/framework/psvi/XSObject.hpp" namespace "xercesc":
    cdef cppclass XSObject:
        const XMLCh* getName()
        const XMLCh* getNamespace()
        XSNamespaceItem *getNamespaceItem()
        XMLSize_t getId()

cdef extern from "xercesc/framework/psvi/XSComplexTypeDefinition.hpp" namespace "xercesc::XSComplexTypeDefinition":
    ctypedef enum CONTENT_TYPE:
        CONTENTTYPE_EMPTY         = 0
        CONTENTTYPE_SIMPLE        = 1
        CONTENTTYPE_ELEMENT       = 2
        CONTENTTYPE_MIXED         = 3

cdef extern from "xercesc/framework/psvi/XSConstants.hpp" namespace "xercesc::XSConstants":
    ctypedef enum COMPONENT_TYPE:
        ATTRIBUTE_DECLARATION     = 1
        ELEMENT_DECLARATION       = 2
        TYPE_DEFINITION           = 3
        ATTRIBUTE_USE             = 4
        ATTRIBUTE_GROUP_DEFINITION= 5
        MODEL_GROUP_DEFINITION    = 6
        MODEL_GROUP               = 7
        PARTICLE                  = 8
        WILDCARD                  = 9
        IDENTITY_CONSTRAINT       = 10
        NOTATION_DECLARATION      = 11
        ANNOTATION                = 12
        FACET_                    = 13 # conflicts with type FACET
        MULTIVALUE_FACET          = 14
    ctypedef enum DERIVATION_TYPE:
        DERIVATION_NONE           = 0
        DERIVATION_EXTENSION      = 1
        DERIVATION_RESTRICTION    = 2
        DERIVATION_SUBSTITUTION   = 4
        DERIVATION_UNION          = 8
        DERIVATION_LIST           = 16
    ctypedef enum SCOPE:
        SCOPE_ABSENT              = 0
        SCOPE_GLOBAL              = 1
        SCOPE_LOCAL               = 2
    ctypedef enum VALUE_CONSTRAINT:
        VALUE_CONSTRAINT_NONE     = 0
        VALUE_CONSTRAINT_DEFAULT  = 1
        VALUE_CONSTRAINT_FIXED    = 2

cdef extern from "xercesc/framework/psvi/XSModelGroup.hpp" namespace "xercesc::XSModelGroup":
    ctypedef enum COMPOSITOR_TYPE:
        COMPOSITOR_SEQUENCE       = 1
        COMPOSITOR_CHOICE         = 2
        COMPOSITOR_ALL            = 3

cdef extern from "xercesc/framework/psvi/XSParticle.hpp" namespace "xercesc::XSParticle":
    ctypedef enum TERM_TYPE:
        TERM_EMPTY          = 0
        TERM_ELEMENT        = ELEMENT_DECLARATION
        TERM_MODELGROUP     = MODEL_GROUP_DEFINITION
        TERM_WILDCARD       = WILDCARD

cdef extern from "xercesc/framework/psvi/XSSimpleTypeDefinition.hpp" namespace "xercesc::XSSimpleTypeDefinition":
    ctypedef enum VARIETY:
        VARIETY_ABSENT            = 0
        VARIETY_ATOMIC            = 1
        VARIETY_LIST              = 2
        VARIETY_UNION             = 3
    ctypedef enum FACET:
        FACET_NONE                = 0
        FACET_LENGTH              = 1
        FACET_MINLENGTH           = 2
        FACET_MAXLENGTH           = 4
        FACET_PATTERN             = 8
        FACET_WHITESPACE          = 16
        FACET_MAXINCLUSIVE        = 32
        FACET_MAXEXCLUSIVE        = 64
        FACET_MINEXCLUSIVE        = 128
        FACET_MININCLUSIVE        = 256
        FACET_TOTALDIGITS         = 512
        FACET_FRACTIONDIGITS      = 1024
        FACET_ENUMERATION         = 2048
    ctypedef enum ORDERING:
        ORDERED_FALSE             = 0
        ORDERED_PARTIAL           = 1
        ORDERED_TOTAL             = 2
        
cdef extern from "xercesc/framework/psvi/XSWildcard.hpp" namespace "xercesc::XSWildcard":
    ctypedef enum NAMESPACE_CONSTRAINT:
        NSCONSTRAINT_ANY             = 1
        NSCONSTRAINT_NOT             = 2
        NSCONSTRAINT_DERIVATION_LIST = 3
    ctypedef enum PROCESS_CONTENTS:
        PC_STRICT                    = 1
        PC_SKIP                      = 2
        PC_LAX                       = 3

cdef extern from "xercesc/framework/psvi/XSTypeDefinition.hpp" namespace "xercesc::XSTypeDefinition":
    ctypedef enum TYPE_CATEGORY:
        COMPLEX_TYPE              = 15
        SIMPLE_TYPE               = 16

cdef extern from "xercesc/framework/psvi/XSAttributeDeclaration.hpp" namespace "xercesc":
    cdef cppclass XSAttributeDeclaration( XSObject ):
        const XMLCh* getName()
        const XMLCh* getNamespace()
        XSNamespaceItem* getNamespaceItem()
        XSSimpleTypeDefinition *getTypeDefinition()
        SCOPE getScope()
        XSComplexTypeDefinition *getEnclosingCTDefinition()
        VALUE_CONSTRAINT getConstraintType()
        const XMLCh *getConstraintValue()
        XSAnnotation *getAnnotation()
        bool getRequired()
        
cdef extern from "xercesc/framework/psvi/XSAttributeGroupDefinition.hpp" namespace "xercesc":
        cdef cppclass XSAttributeGroupDefinition( XSObject ):
            const XMLCh* getName()
            const XMLCh* getNamespace()
            XSNamespaceItem* getNamespaceItem()
            XSAttributeUseList *getAttributeUses()
            XSWildcard *getAttributeWildcard()
            XSAnnotation *getAnnotation()

cdef extern from "xercesc/framework/psvi/XSAttributeUse.hpp" namespace "xercesc":
    cdef cppclass XSAttributeUse( XSObject ):
        bool getRequired()
        XSAttributeDeclaration *getAttrDeclaration()
        VALUE_CONSTRAINT getConstraintType()
        const XMLCh *getConstraintValue()

cdef extern from "xercesc/framework/psvi/XSComplexTypeDefinition.hpp" namespace "xercesc":
    cdef cppclass XSComplexTypeDefinition( XSObject ):
        DERIVATION_TYPE getDerivationMethod()
        bool getAbstract()
        XSAttributeUseList *getAttributeUses()
        XSWildcard *getAttributeWildcard()
        CONTENT_TYPE getContentType()
        XSSimpleTypeDefinition *getSimpleType()
        XSParticle *getParticle()
        bool isProhibitedSubstitution(DERIVATION_TYPE toTest)
        short getProhibitedSubstitutions()
        XSAnnotationList *getAnnotations()
        const XMLCh* getName()
        const XMLCh* getNamespace()
        XSNamespaceItem *getNamespaceItem()
        bool getAnonymous()
        XSTypeDefinition *getBaseType()
        bool derivedFromType(const XSTypeDefinition* const ancestorType)

cdef extern from "xercesc/framework/psvi/XSElementDeclaration.hpp" namespace "xercesc":
    cdef cppclass XSElementDeclaration( XSObject ):
        XSTypeDefinition *getTypeDefinition()
        SCOPE getScope()
        #XSComplexTypeDefinition *getEnclosingCTDefinition()
        VALUE_CONSTRAINT getConstraintType()
        const XMLCh *getConstraintValue()
        bool getNillable()
        #XSNamedMap[XSIDCDefinition] *getIdentityConstraints()
        XSElementDeclaration *getSubstitutionGroupAffiliation()
        bool isSubstitutionGroupExclusion(DERIVATION_TYPE exclusion)
        short getSubstitutionGroupExclusions()
        bool isDisallowedSubstitution(DERIVATION_TYPE disallowed)
        short getDisallowedSubstitutions()
        bool getAbstract()
        XSAnnotation *getAnnotation()
        void setTypeDefinition(XSTypeDefinition* typeDefinition)

cdef extern from "xercesc/framework/psvi/XSFacet.hpp" namespace "xercesc":
    cdef cppclass XSFacet( XSObject ):
        FACET getFacetKind()
        const XMLCh *getLexicalFacetValue()
        bool isFixed()
        XSAnnotation *getAnnotation()
        
cdef extern from "xercesc/framework/psvi/XSModelGroup.hpp" namespace "xercesc":
    cdef cppclass XSModelGroup( XSObject ):
        COMPOSITOR_TYPE getCompositor()
        XSParticleList *getParticles()
        XSAnnotation *getAnnotation()

cdef extern from "xercesc/framework/psvi/XSModelGroupDefinition.hpp" namespace "xercesc":
    cdef cppclass XSModelGroupDefinition( XSObject ):
        const XMLCh* getName()
        const XMLCh* getNamespace()
        XSNamespaceItem *getNamespaceItem()
        XSModelGroup *getModelGroup()
        XSAnnotation *getAnnotation()

cdef extern from "xercesc/framework/psvi/XSMultiValueFacet.hpp" namespace "xercesc":
    cdef cppclass XSMultiValueFacet( XSObject ):
        FACET getFacetKind()
        StringList *getLexicalFacetValues()
        bool isFixed()
        XSAnnotationList *getAnnotations()


cdef extern from "xercesc/framework/psvi/XSNamedMap.hpp" namespace "xercesc":
    cdef cppclass XSNamedMap[TVal]:
        XMLSize_t getLength()
        TVal* item(XMLSize_t index)
        TVal* itemByName(const XMLCh *compNamespace, const XMLCh *localName)
        void addElement(TVal* const toAdd, const XMLCh* key1, const XMLCh* key2)

cdef extern from "xercesc/framework/psvi/XSNotationDeclaration.hpp" namespace "xercesc":
    cdef cppclass XSNotationDeclaration( XSObject ):
        const XMLCh* getName()
        const XMLCh* getNamespace()
        XSNamespaceItem *getNamespaceItem()
        const XMLCh *getSystemId()
        const XMLCh *getPublicId()
        XSAnnotation *getAnnotation()

cdef extern from "xercesc/framework/psvi/XSParticle.hpp" namespace "xercesc":
    cdef cppclass XSParticle( XSObject ):
        XMLSize_t getMinOccurs()
        XMLSize_t getMaxOccurs()
        bool getMaxOccursUnbounded()
        TERM_TYPE getTermType()
        XSElementDeclaration *getElementTerm()
        XSModelGroup *getModelGroupTerm()
        XSWildcard *getWildcardTerm()

cdef extern from "xercesc/framework/psvi/XSTypeDefinition.hpp" namespace "xercesc":
    cdef cppclass XSTypeDefinition( XSObject ):
        XSNamespaceItem *getNamespaceItem()
        TYPE_CATEGORY getTypeCategory()
        XSTypeDefinition *getBaseType()
        bool isFinal(short toTest)
        short getFinal()
        bool getAnonymous()
        bool derivedFromType(const XSTypeDefinition* const ancestorType)
        bool derivedFrom(const XMLCh* typeNamespace, const XMLCh* name)

cdef extern from "xercesc/framework/psvi/XSSimpleTypeDefinition.hpp" namespace "xercesc":
    cdef cppclass XSSimpleTypeDefinition( XSTypeDefinition ):
        VARIETY getVariety()
        XSSimpleTypeDefinition *getPrimitiveType()
        XSSimpleTypeDefinition *getItemType()
        XSSimpleTypeDefinitionList *getMemberTypes()
        int getDefinedFacets()
        bool isDefinedFacet(FACET facetName)
        int getFixedFacets()
        bool isFixedFacet(FACET facetName)
        const XMLCh *getLexicalFacetValue(FACET facetName)
        StringList *getLexicalEnumeration()
        StringList *getLexicalPattern()
        ORDERING getOrdered()
        bool getFinite()
        bool getBounded()
        bool getNumeric()
        XSAnnotationList *getAnnotations()
        XSFacetList *getFacets()
        XSMultiValueFacetList *getMultiValueFacets()
        const XMLCh* getName()
        const XMLCh* getNamespace()
        XSNamespaceItem *getNamespaceItem()
        bool getAnonymous()
        XSTypeDefinition *getBaseType()
        bool derivedFromType(const XSTypeDefinition* const ancestorType)
        #inline DatatypeValidator* getDatatypeValidator()

cdef extern from "xercesc/framework/psvi/XSWildcard.hpp" namespace "xercesc":
    cdef cppclass XSWildcard( XSObject ):
        NAMESPACE_CONSTRAINT getConstraintType()
        StringList *getNsConstraintList()
        PROCESS_CONTENTS getProcessContents()
        XSAnnotation *getAnnotation()

cdef extern from "xercesc/framework/XMLElementDecl.hpp" namespace "xercesc":
    cdef cppclass XMLElementDecl:
        const XMLCh* getBaseName()
        const QName* getElementName()
        const XMLCh* getFullName()

cdef extern from "xercesc/framework/XMLGrammarPool.hpp" namespace "xercesc":
    cdef cppclass XMLGrammarPool:
        XMLGrammarPoolImpl(MemoryManager* const memMgr)
        XSModel *getXSModel(bool& XSModelWasChanged)
        
cdef extern from "xercesc/framework/XMLGrammarPoolImpl.hpp" namespace "xercesc":
    cdef cppclass XMLGrammarPoolImpl(XMLGrammarPool):
        XMLGrammarPoolImpl(MemoryManager* const memMgr)
        
cdef extern from "xercesc/framework/psvi/XSModel.hpp" namespace "xercesc":
    cdef cppclass XSModel:
        StringList *getNamespaces()
        XSNamespaceItemList *getNamespaceItems()
        XSNamedMap[XSObject] *getComponents(COMPONENT_TYPE objectType)
        XSNamedMap[XSObject] *getComponentsByNamespace(COMPONENT_TYPE objectType, const XMLCh *compNamespace)
        XSAnnotationList *getAnnotations()
        XSElementDeclaration *getElementDeclaration(const XMLCh *name, const XMLCh *compNamespace)
        XSAttributeDeclaration *getAttributeDeclaration(const XMLCh *name, const XMLCh *compNamespace)
        XSTypeDefinition *getTypeDefinition(const XMLCh *name, const XMLCh *compNamespace)
        XSAttributeGroupDefinition *getAttributeGroup(const XMLCh *name, const XMLCh *compNamespace)
        XSModelGroupDefinition *getModelGroupDefinition(const XMLCh *name, const XMLCh *compNamespace)
        XSNotationDeclaration *getNotationDeclaration(const XMLCh *name, const XMLCh *compNamespace)
        XSObject *getXSObjectById(XMLSize_t compId, COMPONENT_TYPE compType)

cdef extern from "xercesc/framework/psvi/XSNamespaceItem.hpp" namespace "xercesc":
    cdef cppclass XSNamespaceItem: # ( XMemory ):
        const XMLCh *getSchemaNamespace()
        XSNamedMap[XSObject] *getComponents(COMPONENT_TYPE objectType)
        XSAnnotationList *getAnnotations()
        XSElementDeclaration *getElementDeclaration(const XMLCh *name)
        XSAttributeDeclaration *getAttributeDeclaration(const XMLCh *name)
        XSTypeDefinition *getTypeDefinition(const XMLCh *name)
        XSAttributeGroupDefinition *getAttributeGroup(const XMLCh *name)
        XSModelGroupDefinition *getModelGroupDefinition(const XMLCh *name)
        XSNotationDeclaration *getNotationDeclaration(const XMLCh *name)
        const StringList *getDocumentLocations()
        
cdef extern from "xercesc/framework/psvi/XSValue.hpp" namespace "xercesc::XSValue":
    ctypedef enum DataType:
        dt_string               = 0
        dt_boolean              = 1
        dt_decimal              = 2
        dt_float                = 3
        dt_double               = 4
        dt_duration             = 5
        dt_dateTime             = 6
        dt_time                 = 7
        dt_date                 = 8
        dt_gYearMonth           = 9
        dt_gYear                = 10
        dt_gMonthDay            = 11
        dt_gDay                 = 12
        dt_gMonth               = 13
        dt_hexBinary            = 14
        dt_base64Binary         = 15
        dt_anyURI               = 16
        dt_QName                = 17
        dt_NOTATION             = 18
        dt_normalizedString     = 19
        dt_token                = 20
        dt_language             = 21
        dt_NMTOKEN              = 22
        dt_NMTOKENS             = 23
        dt_Name                 = 24
        dt_NCName               = 25
        dt_ID                   = 26
        dt_IDREF                = 27
        dt_IDREFS               = 28
        dt_ENTITY               = 29
        dt_ENTITIES             = 30
        dt_integer              = 31
        dt_nonPositiveInteger   = 32
        dt_negativeInteger      = 33
        dt_long                 = 34
        dt_int                  = 35
        dt_short                = 36
        dt_byte                 = 37
        dt_nonNegativeInteger   = 38
        dt_unsignedLong         = 39
        dt_unsignedInt          = 40
        dt_unsignedShort        = 41
        dt_unsignedByte         = 42
        dt_positiveInteger      = 43
        dt_MAXCOUNT             = 44
    ctypedef enum XMLVersion:
        ver_10
        ver_11
    ctypedef enum Status:
        st_Init
        st_NoContent
        st_NoCanRep
        st_NoActVal
        st_NotSupported
        st_CantCreateRegEx
        st_FOCA0002        # invalid lexical value
        st_FOCA0001        # input value too large/too small for decimal
        st_FOCA0003        # input value too large for integer
        st_FODT0003        # invalid timezone value
        st_UnknownType
    ctypedef enum DataGroup:
        dg_numerics
        dg_datetimes
        dg_strings
    ctypedef enum DoubleFloatType:
        DoubleFloatType_NegINF
        DoubleFloatType_PosINF
        DoubleFloatType_NaN
        DoubleFloatType_Zero
        DoubleFloatType_Normal
        
cdef extern from "xercesc/framework/psvi/XSValue.hpp" namespace "xercesc":
    cdef cppclass XSValue # ( XMemory )

