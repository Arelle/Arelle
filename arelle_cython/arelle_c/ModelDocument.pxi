from cython.operator cimport dereference as deref
from arelle_c.xerces_uni cimport fgXercesSchemaExternalSchemaLocation

cdef class ModelDocument:
    cdef readonly ModelXbrl modelXbrl
    cdef readonly int type
    cdef readonly unicode url
    cdef readonly unicode filepath
    cdef public bool isGrammarLoadedIntoModel
    cdef public unicode targetNamespace
    cdef public unicode targetNamespacePrefix
    cdef public object xmlRootElement
    
    def __init__(self, ModelXbrl modelXbrl, int type, unicode url, unicode filepath):
        self.modelXbrl = modelXbrl
        self.type = type
        self.url = url
        self.filepath = filepath
        self.targetNamespace = None
        self.targetNamespacePrefix = None
        self.xmlRootElement = None
        self.isGrammarLoadedIntoModel = False
                
    def loadSchema(self, object pyFileDesc):
        cdef ModelXbrl modelXbrl = self.modelXbrl
        modelXbrl.openSax2Parser()
        cdef void* modelDocumentPtr = <void*>self
        cdef ModelDocumentSAX2Handler* sax2Handler = <ModelDocumentSAX2Handler*>modelXbrl.sax2_parser.getContentHandler()
        sax2Handler.setModelDocument(modelDocumentPtr)
        cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
        cdef SchemaGrammar* schemaGrammar = <SchemaGrammar*>modelXbrl.sax2_parser.loadGrammar( deref( inpSrc ), GrammarType.SchemaGrammarType, True)
        assert schemaGrammar != NULL, "arelle:loadSchemaGrammarNull schema grammar not loaded, null results"
        cdef XMLCh* xmlChTargetNS = <XMLCh*>schemaGrammar.getTargetNamespace()
        cdef char* targetNs = transcode(xmlChTargetNS)
        cdef unicode pyNs = targetNs
        assert self.targetNamespace == pyNs, "arelle:loadSchemaNamespaceConflict schema grammar namespace {} discovery namespace {}".format(self.targetNamespace, pyNs)
        release(&targetNs)
        
        sax2Handler.setModelDocument(NULL) # dereference modelDocument

    def loadXml(self, object pyFileDesc, object schemaLocationsList):
        cdef ModelXbrl modelXbrl = self.modelXbrl
        modelXbrl.openSax2Parser()
        cdef void* modelDocumentPtr = <void*>self
        cdef ModelDocumentSAX2Handler* sax2Handler = <ModelDocumentSAX2Handler*>modelXbrl.sax2_parser.getContentHandler()
        sax2Handler.setModelDocument(modelDocumentPtr)
        cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
        byte_s = " ".join(schemaLocationsList).encode("utf-8")
        cdef char* c_s = byte_s
        cdef XMLCh* xmlChSchemaLocation = transcode(c_s)
        modelXbrl.sax2_parser.setProperty(fgXercesSchemaExternalSchemaLocation, xmlChSchemaLocation)
        modelXbrl.sax2_parser.parse(deref(inpSrc))
        release(&xmlChSchemaLocation)
        
        sax2Handler.setModelDocument(NULL) # dereference modelDocument
        
        
cdef cppclass ModelDocumentSAX2Handler(ModelXbrlErrorHandler):
    void* modelXbrlPtr
    void* modelDocumentPtr
    Locator* saxLocator
    
    ModelDocumentSAX2Handler(void* modelXbrlPtr) except +:
        this.modelXbrlPtr = modelXbrlPtr
        
    void setModelDocument(void* modelDocumentPtr):
        this.modelDocumentPtr = modelDocumentPtr

    void close():
        this._modelXbrl = NULL # dereference

    void setDocumentLocator(const Locator* const locator):
        this.saxLocator = <Locator*>locator
    
    void handlePyError(object pyError):
        cdef object modelXbrl = <object>this.modelXbrlPtr
        modelXbrl.log(pyError.level, "arelle:xerces",
                      pyError.message,
                      line=pyError.line,
                      column=pyError.column,
                      file=pyError.file, # url if public ID available?
                      element=pyError.element)
