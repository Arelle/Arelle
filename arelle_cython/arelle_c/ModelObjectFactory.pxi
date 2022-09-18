# model object creators

ctypedef RefHashTableOf[void,StringHasher] PyClassHashTable
ctypedef RefHashTableOf[PyClassHashTable,StringHasher] PyNamespaceClassHashTable

cdef PyNamespaceClassHashTable *objectFactoryNamespaces = NULL # registered classes

# call with (sunicode pyNs, unicode pyLn, ModelObject modelObjectClass):
# or with (QName, ModelObject modelObjectClass
def registerModelObjectClass(*args):
    cdef unicode pyNs, pyLn
    cdef object modelObjectClass
    cdef bytes bytesNs
    cdef bytes bytesLn
    cdef const char* chNs
    cdef const char* chLn
    cdef XMLCh* xmlchNs
    cdef XMLCh* xmlchLn
    cdef void* modelObjectClassPtr
    cdef PyClassHashTable* pyClassTbl
    global objectFactoryNamespaces
    
    assureXercesIsInitialized() # may be called during loading before Cntlr is started up
    if len(args) == 2:
        pyNs = <unicode>args[0].namespaceURI
        pyLn = args[0].localName
        modelObjectClass = args[1]
    elif len(args) == 3:
        pyNs = <unicode>args[0]
        pyLn = args[1]
        modelObjectClass = args[2]
    assert pyLn is not None and len(pyLn) > 0, "ModelObjectFactory: Class constructor QName must have a localName"

    if pyNs is None: # no namespace is an empty string namespace for Xerces
        pyNs = uEmptyStr
    bytesNs = pyNs.encode("utf-8")
    bytesLn = pyLn.encode("utf-8")
    chNs = bytesNs
    chLn = bytesLn
    pyChNs = chNs
    pyChLn = chLn
    xmlchNs = transcode(chNs)
    xmlchLn = transcode(chLn)
    modelObjectClassPtr = <void*>modelObjectClass
    if objectFactoryNamespaces == NULL:
        objectFactoryNamespaces = new PyNamespaceClassHashTable(255, <bool>False)
    pyClassTbl = objectFactoryNamespaces.get(xmlchNs)
    if pyClassTbl != NULL:
        release(&xmlchNs) # can be released because it's not stored in the hash table
    else:
        pyClassTbl = new PyClassHashTable(255, <bool>False)
        objectFactoryNamespaces.put(xmlchNs, pyClassTbl) # can't release xmlchNs, remains in the hash table
    pyClassTbl.put(xmlchLn, modelObjectClassPtr) # can't release because key continuse to exist for the class table
    #print("registered class ns {} ln {} cls {} nsCt {} clsCt {}".format(pyNs, pyLn, modelObjectClass, objectFactoryNamespaces.getCount(), pyClassTbl.getCount()))
    bytesNs = bytesLn = pyNs = pyLn = None # deref python bytes buffers
    
cdef void* registeredModelObjectClassPtr(const XMLCh *xmlchNs, const XMLCh *xmlchLn):
    cdef PyClassHashTable* pyClassTbl
    if objectFactoryNamespaces != NULL:
        pyClassTbl = objectFactoryNamespaces.get(xmlchNs)
        if pyClassTbl != NULL:
            return pyClassTbl.get(xmlchLn)
    return NULL
    
cdef class ModelObjectFactory:
    def registerClass(self, *args):
        registerModelObjectClass(*args)
