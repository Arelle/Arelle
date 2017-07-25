from xerces_ctypes cimport XMLSize_t

cdef extern from "xercesc/framework/MemoryManager.hpp" namespace "xercesc":
    cdef cppclass MemoryManager:
        void* allocate(XMLSize_t size)
        void* allocate(XMLSize_t size)

