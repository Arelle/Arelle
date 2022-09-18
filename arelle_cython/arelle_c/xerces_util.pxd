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
    cdef struct PtrHasher:
        XMLSize_t getHashVal(const void* key, XMLSize_t mod)
        bool equals(const void *const key1, const void *const key2)
        
cdef extern from "xercesc/util/Hash2KeysSetOf.hpp" namespace "xercesc":
    cdef cppclass Hash2KeysSetOf[THasher]:
        Hash2KeysSetOf(const XMLSize_t modulus)
        bool isEmpty()
        bool containsKey(const void* const key1, const int key2)
        void removeKey(const void* const key1, const int key2)
        void removeAll()
        void cleanup()
        XMLSize_t getCount()
        void put(void* key1, const int key2)

ctypedef Hash2KeysSetOf[StringHasher] StringHashSet

cdef extern from "xercesc/util/BaseRefVectorOf.hpp" namespace "xercesc":
    cdef cppclass BaseRefVectorOf[TElem]:
        const TElem* elementAt(const XMLSize_t getAt)
        XMLSize_t size()
        
cdef extern from "xercesc/util/RefArrayVectorOf.hpp" namespace "xercesc":
    cdef cppclass RefArrayVectorOf[TElem]: # ( BaseRefVectorOf[TElem] )
        const TElem* elementAt(const XMLSize_t getAt)
        XMLSize_t size()
    
cdef extern from "xercesc/util/RefHashTableOf.hpp" namespace "xercesc":
    cdef cppclass RefHashTableOf[TVal, THasher]:
        RefHashTableOf(const XMLSize_t modulus)
        RefHashTableOf(const XMLSize_t modulus, const bool adoptElems)
        bool isEmpty()
        bool containsKey(const void* const key)
        void removeKey(const void* const key)
        void removeAll()
        void cleanup()
        TVal* get(const void* const key)
        XMLSize_t getCount()
        void setAdoptElements(const bool aValue)
        void put(void* key, TVal* valueToAdopt)
    cdef cppclass RefHashTableOfEnumerator[TVal, THasher]:
        RefHashTableOfEnumerator(RefHashTableOf[TVal, THasher]* const toEnum)
        bool hasMoreElements() const
        TVal& nextElement()
        void Reset()
        void* nextElementKey()

ctypedef RefHashTableOf[XMLCh,StringHasher] StringHashTable
ctypedef RefHashTableOfEnumerator[XMLCh,StringHasher] StringHashTableEnumerator


cdef extern from "xercesc/util/RefVectorOf.hpp" namespace "xercesc":
    cdef cppclass RefVectorOf[TElem]: # ( BaseRefVectorOf[TElem] )
        RefVectorOf(const XMLSize_t maxElems, const bool adoptElems)
        const TElem* elementAt(const XMLSize_t getAt)
        XMLSize_t size()
        void addElement(TElem* toAdd)
        void removeAllElements()

cdef extern from "xercesc/util/ValueHashTableOf.hpp" namespace "xercesc":
    cdef cppclass ValueHashTableOf[TVal]: 
        ValueHashTableOf(const XMLSize_t modulus)
        bool isEmpty()
        bool containsKey(const void* const key)
        void removeKey(const void* const key)
        void removeAll()
        TVal& get(const void* const key)
        void put(void* key, const TVal& valueToAdopt)

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
    void trim(char* const toTrim)
    void trim(XMLCh* const toTrim)
    void replaceWS(XMLCh *toConvert)
    void collapseWS(XMLCh *toConvert)
    void release( char** )
    void release( XMLCh** )
    XMLSize_t stringLen(const XMLCh* const src)
    XMLSize_t stringLen(const char *const src)
    void catString(XMLCh *const target, const XMLCh *const src)
    void copyString(XMLCh *const target, const XMLCh *const src)
    void moveChars(XMLCh *const targetStr, const XMLCh *const srcStr, const XMLSize_t count)    
    bool startsWith(const XMLCh *const toTest, const XMLCh *const prefix)
    int compareString(const XMLCh *const str1, const XMLCh *const str2)
    int compareString(const char *const str1, const char *const str2)
    int compareIString(const XMLCh *const str1, const XMLCh *const str2)
    int compareIString(const char *const str1, const char *const str2)
    int compareNString(const XMLCh *const str1, const XMLCh *const str2, const XMLSize_t count)
    int compareNString(const char *const str1, const char *const str2, const XMLSize_t count)
    int compareNIString(const XMLCh *const str1, const XMLCh *const str2, const XMLSize_t count)
    int compareNIString(const char *const str1, const char *const str2, const XMLSize_t count)
    bool equals(const XMLCh *const str1, const XMLCh *const str2)
    bool equals(const char *const str1, const char *const str2)
    bool equalsN(const XMLCh *const str1, const XMLCh *const str2, XMLSize_t n)
    bool equalsJ(const char *const str1, const char *const str2, XMLSize_t n)
    int indexOf(const XMLCh* const toSearch, const XMLCh ch)
    int indexOf(const char* const toSearch, const char ch)
    int patternMatch(XMLCh *const toSearch, const XMLCh *const pattern)
    BaseRefVectorOf[XMLCh]* tokenizeString(const XMLCh *const tokenizeSrc)
    XMLSize_t hash(const XMLCh* const src, const XMLSize_t hashModulus)
    XMLSize_t hash(const char* const src, const XMLSize_t hashModulus)
    XMLCh* replicate(const XMLCh* const toRep) # use release to delete
    char* replicate(const char* const toRep) # use release to delete
    
cdef extern from "xercesc/util/XercesVersion.hpp":
    cdef const char* gXercesFullVersionStr
    cdef const unsigned int gXercesMajVersion
    cdef const unsigned int gXercesMinVersion
    cdef const unsigned int gXercesRevision
        
