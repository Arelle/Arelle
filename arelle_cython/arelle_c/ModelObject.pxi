
cdef class ModelObject:
    cdef readonly ModelDocument ModelDocument
    cdef readonly QName qname
    
    def __init__(self, ModelDocument modelDocument, QName qname):
        self.modelDocument = modelDocument
        self.qname = qname

cdef class ModelConcept(ModelObject):
    cdef XSElementDeclaration *xsElement
    
    def __init__(self, ModelDocument modelDocument, XSElementDeclaration *xsElement):
        self.modelDocument = modelDocument
        self.qname = qname

