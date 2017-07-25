from libcpp cimport bool
from cpython.object cimport PyObject, PyObject_Hash, PyObject_Length

cdef class QName:
    cdef long qnameValueHash
    cdef readonly unicode namespaceURI
    cdef readonly unicode prefix
    cdef readonly unicode localName
    
    # prefix and namespaceURI should be dts-interned to preserve memory space, automatic when creating from xerces
    def __init__(self, unicode namespaceURI, unicode prefix, unicode localName):
        self.namespaceURI = namespaceURI
        self.prefix = prefix
        self.localName = localName
        self.qnameValueHash = PyObject_Hash( (namespaceURI, localName) )
    def __hash__(self):
        return self.qnameValueHash
    @property
    def clarkNotation(self):
        if self.namespaceURI:
            return '{{{}}}{}'.format(self.namespaceURI, self.localName)
        else:
            return self.localName
    def __repr__(self):
        return self.__str__() 
    def __str__(self):
        if self.prefix and self.prefix != '':
            return self.prefix + ':' + self.localName
        else:
            return self.localName
    def __richcmp__(self, other, op):
        if op == 0: # lt
            return (self.namespaceURI is None and other.namespaceURI) or \
                    (self.namespaceURI and other.namespaceURI and self.namespaceURI < other.namespaceURI) or \
                    (self.namespaceURI == other.namespaceURI and self.localName < other.localName)
        elif op == 1: # le
            return (self.namespaceURI is None and other.namespaceURI) or \
                    (self.namespaceURI and other.namespaceURI and self.namespaceURI < other.namespaceURI) or \
                    (self.namespaceURI == other.namespaceURI and self.localName <= other.localName)
        elif op == 2: # eq
            try:
                return (self.qnameValueHash == other.qnameValueHash and 
                        self.localName == other.localName and self.namespaceURI == other.namespaceURI)
            except AttributeError:
                return False
        elif op == 3: # ne
            return not self.__eq__(other)
        elif op == 4: # gt
            return (self.namespaceURI and other.namespaceURI is None) or \
                    (self.namespaceURI and other.namespaceURI and self.namespaceURI > other.namespaceURI) or \
                    (self.namespaceURI == other.namespaceURI and self.localName > other.localName)
        elif op == 5: # ge
            return (self.namespaceURI and other.namespaceURI is None) or \
                    (self.namespaceURI and other.namespaceURI and self.namespaceURI > other.namespaceURI) or \
                    (self.namespaceURI == other.namespaceURI and self.localName >= other.localName)
        else: # no such op
            return False # bad operation
    def __bool__(self):
        # QName object bool is false if there is no local name (even if there is a namespace URI).
        return self.localName is None or PyObject_Length(self.localName) == 0
