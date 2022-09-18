from libcpp cimport bool
from cpython.object cimport PyObject, PyObject_Hash, PyObject_Length
from urllib.parse import urldefrag, unquote, quote, urljoin

cdef class QName:
    cdef readonly hash_t qnameValueHash
    cdef readonly unicode namespaceURI
    cdef readonly unicode prefix
    cdef readonly unicode localName
    
    # prefix and namespaceURI should be dts-interned to preserve memory space, automatic when creating from xerces
    def __init__(self, object namespaceURI, unicode prefix, unicode localName):
        assert localName is not None and len(localName) > 0, "ModelValue: QName must have a localName"
        #print("QName ns {} pf {} ln {}".format(namespaceURI, prefix, localName))
        self.namespaceURI = <unicode>namespaceURI # may be a string or an AnyURI
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
    @property
    def prefixedName(self):
        if self.prefix and self.prefix != '':
            return self.prefix + ':' + self.localName
        else:
            return self.localName
    def __repr__(self):
        return self.__str__() 
    def __str__(self):
        if self.prefix is not None:
            if self.prefix != '':
                return self.prefix + ':' + self.localName
            else:
                return self.localName # needed for default prefix situations such as xhtml
        else:
            return self.clarkNotation # no prefix declared
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
            try: # raises AttributeError if other is not a QName
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
        return self.localName != None and len(self.localName) > 0
    
cdef class AnyURI(unicode):
    def __init__(self, unicode str):
        unicode.__init__(str)

    @property
    def urlWithoutFragment(self):
        """ returns (url-without-fragment, fragment) """
        return urldefrag(self)[0]
   
    @property
    def fragment(self):
        return unquote(urldefrag(self)[1], "utf-8", errors=None)
    
