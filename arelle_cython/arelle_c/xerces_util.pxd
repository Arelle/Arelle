from xerces_ctypes cimport XMLByte, XMLCh, XMLSize_t, XMLFilePos, XMLFileLoc
from xerces_framework_memory_manager cimport MemoryManager
from xerces_sax cimport InputSource, Locator

from libcpp cimport bool

cdef extern from "xercesc/util/PlatformUtils.hpp" namespace "xercesc::XMLPlatformUtils":
    void Initialize()
    void Terminate()

cdef extern from "xercesc/util/Hashers.hpp" namespace "xercesc":
    cdef struct StringHasher:
        XMLSize_t getHashVal(const void* key, XMLSize_t mod)
        bool equals(const void *const key1, const void *const key2)
        
cdef extern from "xercesc/util/BaseRefVectorOf.hpp" namespace "xercesc":
    cdef cppclass BaseRefVectorOf[TElem]:
        const TElem* elementAt(const XMLSize_t getAt)
        XMLSize_t size()

cdef extern from "xercesc/util/RefArrayVectorOf.hpp" namespace "xercesc":
    cdef cppclass RefArrayVectorOf[TElem]: # ( BaseRefVectorOf[TElem] )
        const TElem* elementAt(const XMLSize_t getAt)
        XMLSize_t size()
    
cdef extern from "xercesc/util/RefVectorOf.hpp" namespace "xercesc":
    cdef cppclass RefVectorOf[TElem]: # ( BaseRefVectorOf[TElem] )
        const TElem* elementAt(const XMLSize_t getAt)
        XMLSize_t size()

cdef extern from "xercesc/util/XMLEntityResolver.hpp" namespace "xercesc":
    cdef cppclass XMLEntityResolver:
        InputSource* resolveEntity(XMLResourceIdentifier*)

cdef extern from "xercesc/util/XMLEnumerator.hpp" namespace "xercesc":
    cdef cppclass XMLEnumerator[TElem]:
        XMLEnumerator()
        #XMLEnumerator(const XMLEnumerator[TElem]&)
        bool hasMoreElements() const
        TElem& nextElement()
        void Reset()
        XMLSize_t size() const

cdef extern from "xercesc/util/XMLResourceIdentifier.hpp" namespace "xercesc::XMLResourceIdentifier":
    ctypedef enum ResourceIdentifierType:
        SchemaGrammar  = 0
        SchemaImport   = 1
        SchemaInclude  = 2
        SchemaRedefine = 3
        ExternalEntity = 4
        UnKnown        = 255

cdef extern from "xercesc/util/XMLResourceIdentifier.hpp" namespace "xercesc":
    cdef cppclass XMLResourceIdentifier:
        ResourceIdentifierType getResourceIdentifierType()
        const XMLCh* getPublicId()
        const XMLCh* getSystemId()
        const XMLCh* getSchemaLocation()
        const XMLCh* getBaseURI()
        const XMLCh* getNameSpace()
        const Locator* getLocator() 

cdef extern from "xercesc/util/XMemory.hpp" namespace "xercesc":
    cdef cppclass XMemory
        # overrides new, delete, which is not supported by cython

cdef extern from "xercesc/util/RefHash3KeysIdPool.hpp" namespace "xercesc":
    cdef cppclass RefHash3KeysIdPoolEnumerator[TVal,THasher] ( XMLEnumerator[TVal] ):
        RefHash3KeysIdPoolEnumerator(const RefHash3KeysIdPoolEnumerator[TVal, THasher]&)
        bool hasMoreElements() const
        TVal& nextElement()
        void Reset()
        XMLSize_t size() const

cdef extern from "xercesc/util/QName.hpp" namespace "xercesc":
    cdef cppclass QName:
        const XMLCh* getPrefix()
        const XMLCh* getLocalPart()
        unsigned int getURI()

cdef extern from "xercesc/util/PlatformUtils.hpp" namespace "xercesc::XMLPlatformUtils":
    cdef MemoryManager* fgMemoryManager

    cdef const XMLCh* fgAnyString

cdef extern from "xercesc/util/XMLString.hpp" namespace "xercesc::XMLString":
    const char* transcode( const XMLCh* )
    const XMLCh* transcode( const char* )
    void  release( char** )
    void  release( XMLCh** )
    XMLSize_t stringLen(const XMLCh* const src)
    void catString(XMLCh *const target, const XMLCh *const src)
    void copyString(XMLCh *const target, const XMLCh *const src)
    bool startsWith(const XMLCh *const toTest, const XMLCh *const prefix)
    int compareString(const XMLCh *const str1, const XMLCh *const str2)
    int compareString(const XMLCh *const str1, const XMLCh *const str2)
    int compareIString(const XMLCh *const str1, const XMLCh *const str2)
    int compareIString(const XMLCh *const str1, const XMLCh *const str2)
        
