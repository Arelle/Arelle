from arelle_c.xerces_ctypes cimport XMLCh, XMLSize_t, XMLFileLoc
from arelle_c.xerces_framework cimport XSModel, XSAnnotation, XMLElementDecl, XSAnnotation, XSAnnotationList, \
        XMLPScanToken, XSNamespaceItemList, XSNamespaceItem, XSNamedMap, XSObject, StringList, \
        ELEMENT_DECLARATION, TYPE_DEFINITION, COMPONENT_TYPE
from arelle_c.xerces_parsers cimport XercesDOMParser
from arelle_c.xerces_sax cimport SAXParseException, ErrorHandler, EntityResolver, \
        InputSource, DocumentHandler, ErrorHandler, SAXParseException, Locator
from arelle_c.xerces_sax2 cimport createXMLReader, SAX2XMLReader, SAX2XMLReaderImpl, ContentHandler, LexicalHandler, DefaultHandler, \
        Attributes
from arelle_c.xerces_uni cimport fgSAX2CoreNameSpaces, fgSAX2CoreValidation, fgXercesDynamic, fgXercesLoadSchema, fgXercesSchema, \
        fgXercesSchemaFullChecking, fgSGXMLScanner, fgSAX2CoreNameSpacePrefixes, fgXercesValidateAnnotations, \
        fgXercesScannerName, fgXercesGenerateSyntheticAnnotations, fgXercesSchemaExternalSchemaLocation, \
        fgXercesCacheGrammarFromParse, fgXercesCalculateSrcOfs, fgXercesLoadExternalDTD, fgXercesSkipDTDValidation, \
        fgXercesHandleMultipleImports, fgXercesDisableDefaultEntityResolution, fgXercesUseCachedGrammarInParse
from arelle_c.xerces_util cimport equals, startsWith, transcode, trim, release, replicate, PtrHasher, \
        XMLResourceIdentifier, XMLEntityResolver, ResourceIdentifierType, patternMatch, moveChars
from arelle_c.xerces_validators cimport SchemaGrammar, GrammarType
from arelle.ModelDocument import Type as arelleModelDocumentType
from arelle.PythonUtil import OrderedSet
from arelle.XbrlConst import standardLabel
from cython.operator cimport dereference as deref
from libcpp cimport bool
from libcpp.vector cimport vector
from cpython.mem cimport PyMem_Malloc, PyMem_Realloc, PyMem_Free
from collections import defaultdict, OrderedDict

cdef struct Namespace:
    void* pyNamespaceUri
    int   xercesUriId

ctypedef RefHashTableOf[void,PtrHasher] XSHashTable

cdef XMLCh* replaceXsNamespace(XMLCh* annotationXml):
    cdef XMLCh* xml = annotationXml
    #cdef XMLCh* xmlReplacedNS = NULL
    #cdef XMLCh* priorAlloc
    cdef int offset = 0
    cdef int p
    while True:
        p = patternMatch(&xml[offset], xmlchNsXsdQuoted1) # try dbl quotes
        if p < 0:
            p = patternMatch(&xml[offset], xmlchNsXsdQuoted2) # try sgl quotes
        if p < 0:
            break
        p += offset
        # replace the ns in place, persists to subsequent accesses of the annotation
        moveChars(&xml[p+1], nsXsSyntheticAnnotation, lenNsXsd)
        #priorAlloc = xmlReplacedNS
        #xmlReplacedNS = <XMLCh*>fgMemoryManager.allocate((stringLen(xml) - lenNsXsd + lenNsXsd_annotation + 200)*sizeof(XMLCh))
        #moveChars(xmlReplacedNS, xml, p+1)
        #moveChars(&xmlReplacedNS[p+1], nsXsd_annotation, lenNsXsd_annotation)
        #copyString(&xmlReplacedNS[p+1+lenNsXsd_annotation], &xml[p+1+lenNsXsd])
        #if priorAlloc is not NULL:
        #    fgMemoryManager.deallocate(priorAlloc)
        offset += 2 + lenNsXsd
        #xml = xmlReplacedNS
    return xml

cdef class ModelXbrl:
    cdef readonly object modelManager
    cdef readonly object cntlr
    cdef readonly dict urlDocs # ModelDocument indexed by normalizedUrl
    cdef readonly object targetNamespaceDocs # ModelDocument indexed by namespaceURI
    cdef readonly dict mappedUrls # document urls normalizedUrl indexed by filename system id
    cdef readonly dict qnameConcepts # indexed by qname of element
    cdef readonly object nameConcepts # defaultdict contains ModelConcepts by name
    cdef readonly dict qnameTypes # contains ModelTypes by qname key of type
    cdef readonly object arcroleTypes # list of all created modelObject references
    cdef readonly object roleTypes # list of all created modelObject references
    cdef readonly set langs # list of langs used by label resources
    cdef readonly set labelroles # list of label rules used by label resources
    cdef readonly object baseSets
    cdef readonly list modelObjects # list of all created modelObject references
    cdef readonly list facts
    cdef readonly object factsInInstance
    cdef readonly list undefinedFacts # elements presumed to be facts but not defined
    cdef readonly dict contexts
    cdef readonly dict units
    cdef readonly bool hasXDT
    cdef dict internedStrings # index by string of it's intern'ed (unique) value
    cdef dict internedQNames # index by clarkName of QName objects
    cdef XSHashTable *xsTypeDefinitionQNames # contains XSObject QNames by pointer of XSObject (elements, types)
    cdef XSHashTable *qnameXsTypeDefinitions # contains xsTypeDefinition pointer by interned QName 
    cdef XSHashTable *xsElementDeclarationQNames # contains XSObject QNames by pointer of XSObject (elements, types)
    cdef StringHashTable *xmlchNamespacePrefixes # namepace prefixes
    cdef SAX2XMLReaderImpl* sax2_parser
    cdef XercesDOMParser* dom_parser
    cdef SAX2XMLReaderImpl* schema_attr_parser
    cdef XMLGrammarPool* xerces_grammar_pool # must have separate grammar pool per modelXbrl because namespaces may be different txonomies in test cases
    cdef bool checkForGrammarPoolModelChange # resolved namespace may imply a model change
    cdef XSModel* xsModel                    # xsModel after loading more schema components
    cdef XSModel* priorXsModel               # prior generation xsModel
    cdef readonly unsigned int xsModelGeneration # increases for each new xsModel (which would invalidate prior generation)
    cdef unsigned long numModelObjects # number of allocated model objects
    # used for validation when loading schema appinfos
    cdef unicode ixdsTarget
    
    
    def __init__(self, modelManager):
        self.xerces_grammar_pool = new XMLGrammarPoolImpl(fgMemoryManager)
        self.modelManager = modelManager
        self.cntlr = modelManager.cntlr
        self.urlDocs = dict()
        self.targetNamespaceDocs = defaultdict(list)
        self.mappedUrls = dict()
        self.qnameConcepts = dict()
        self.nameConcepts = defaultdict(list) 
        self.qnameTypes = dict()
        self.arcroleTypes = defaultdict(list)
        self.roleTypes = defaultdict(list)
        self.langs = {self.modelManager.defaultLang}
        self.labelroles = {standardLabel}
        self.baseSets = defaultdict(list) # contains ModelLinks for keys arcrole, arcrole#linkrole
        self.modelObjects = list()
        self.facts = list()
        self.factsInInstance = set()
        self.undefinedFacts = list()
        self.contexts = dict()
        self.units = dict()
        self.internedStrings = dict()
        self.internedQNames = dict()
        self.xsTypeDefinitionQNames = new XSHashTable(103, <bool>False)
        self.qnameXsTypeDefinitions = new XSHashTable(103, <bool>False)
        self.xsElementDeclarationQNames = new XSHashTable(103, <bool>False)
        self.xmlchNamespacePrefixes = new StringHashTable(103, <bool>True) # this table owns its xmlch strings
        self.ixdsTarget = None
        self.xsModel = NULL
        self.priorXsModel = NULL
        self.xsModelGeneration = 0
        self.hasXDT = False
        
        # need faked ModelDocument for xmlschema.xsd
        cdef ModelDocument xsdFakeDoc = ModelDocument(self, arelleModelDocumentType.SCHEMA, uHrefXsd, uHrefXsd)
        xsdFakeDoc.targetNamespace = uNsXsd
        self.targetNamespaceDocs[uNsXsd].append(xsdFakeDoc)
        self.xmlchNamespacePrefixes.put(nsXsd, replicate(prefixXsd)) # owns prefix strings and has to decallocate them

                
    def close(self):
        if self.sax2_parser is not NULL:
            del self.sax2_parser
            self.sax2_parser = NULL
            self.urlDocs.clear()
            self.targetNamespaceDocs.clear()
            self.mappedUrls.clear()
            self.qnameConcepts.clear()
            self.nameConcepts.clear()
            self.qnameTypes.clear()
            self.arcroleTypes.clear()
            self.roleTypes.clear()
            self.langs.clear()
            self.labelroles.clear()
            self.baseSets.clear()
            del self.modelObjects[:]
            del self.facts[:]
            self.factsInInstance.clear()
            del self.undefinedFacts[:]
            self.contexts.clear()
            self.units.clear()
            self.internedStrings.clear()
            self.internedQNames.clear()
            self.xsTypeDefinitionQNames.removeAll()
            self.qnameXsTypeDefinitions.removeAll()
            self.xsElementDeclarationQNames.removeAll()
            self.xmlchNamespacePrefixes.removeAll()
            self.xerces_grammar_pool.clear()
        
    cdef unicode internXMLChString(self, XMLCh* str):
        return internXMLChString(self.internedStrings, str)
        
    cpdef unicode internString(self, unicode str):
        return internString(self.internedStrings, str)

    cpdef QName internQName(self, unicode clarkName):
        return internQName(self.internedQNames, self.internedStrings, clarkName)
            
    cdef QName xmlchQName(self, const XMLCh *uri, const XMLCh *prefix, const XMLCh *localName):
        if prefix is NULL and self.xmlchNamespacePrefixes.containsKey(uri):
            prefix = self.xmlchNamespacePrefixes.get(uri)
        return internQName(self.internedQNames, self.internedStrings, self.internClarkName(uri, prefix, localName))
            
    cdef unicode internClarkName(self, const XMLCh *uri, const XMLCh *prefix, const XMLCh *localName):
        cdef unicode pyClarkName = clarkName(uri, prefix, localName)
        return self.internedStrings.setdefault(pyClarkName, pyClarkName)
    
    cdef unicode internAttrValue(self, const Attributes& attrs, XMLCh* uri, XMLCh* localName):
        return self.internString(getAttrValue(attrs, uri, localName))
    
    cdef dict internAttrsDict(self, const Attributes& attrs):
        cdef XMLSize_t i
        cdef dict pyAttrs = dict()
        for i in range(attrs.getLength()):
            pyAttrs[self.internClarkName(<XMLCh*>attrs.getURI(i), NULL, <XMLCh*>attrs.getLocalName(i))] = self.internXMLChString(<XMLCh*>attrs.getValue(i))
        return pyAttrs
    
    cdef QName xsTypeDefinitionQName(self, XSTypeDefinition *xsTypeDefinition):
        cdef QName qnType
        cdef void* qnamePtr
        cdef const XMLCh* xmlChNs
        cdef XMLCh* xmlChPrefix
        if xsTypeDefinition is NULL:
            return None
        if self.xsTypeDefinitionQNames.containsKey(xsTypeDefinition):
            qnamePtr = self.xsTypeDefinitionQNames.get(xsTypeDefinition)
            qnType = <QName>qnamePtr
            return qnType
        else: # not a declared type
            xmlChNs = xsTypeDefinition.getNamespace()
            qnType = self.xmlchQName(xmlChNs, NULL, xsTypeDefinition.getName()) # must be interned else it goes out of existence on return from here
            qnamePtr = <void*>qnType
            self.xsTypeDefinitionQNames.put(xsTypeDefinition, qnamePtr)
            return qnType
    
    cdef ModelType xsTypeDefinitionType(self, XSTypeDefinition *xsTypeDefinition):
        cdef QName qnType
        cdef list modelDocuments
        cdef ModelType modelType
        if xsTypeDefinition is NULL:
            return None
        qnType = self.xsTypeDefinitionQName(xsTypeDefinition)
        modelType = self.qnameTypes.get(qnType)
        if modelType is not None:
            if modelType.xsTypeDefinition != xsTypeDefinition: # may be nulled during model change
                modelType.xsTypeDefinition = xsTypeDefinition
            return modelType
        modelDocuments = self.targetNamespaceDocs.get(qnType.namespaceURI)
        if not modelDocuments: # may not have been loaded in discovery process yet
            if traceToStdout: print("no document discovered for namespace " + qnType.namespaceURI)
            return None
        modelType = newModelType(modelDocuments[0], xsTypeDefinition, qnType)
        if traceToStdout: print("xsTypeDefType Trace 3 {}".format(modelType.qname))
        self.qnameTypes[qnType] = modelType
        return modelType
        
    cdef ModelType qnameType(self, QName qnType): # get or create ModelType if no ModelType (e.g., if not in DTS)
        if qnType in self.qnameTypes:
            return self.qnameTypes[qnType]
        cdef XSTypeDefinition *xsTypeDefinition
        xsTypeDefinition = self.qnameXsTypeDefinition(qnType)
        if xsTypeDefinition is not NULL:
            return self.xsTypeDefinitionType(xsTypeDefinition)
        return None
    
    cdef XSTypeDefinition* qnameXsTypeDefinition(self, QName qnType): # get xsModel's xsTypeDefinition
        cdef bytes bNs
        cdef bytes bName
        cdef char *chNs
        cdef char *chName
        cdef XMLCh *xmlChNs
        cdef XMLCh *xmlChName
        cdef XSTypeDefinition *xsTypeDefinition
        bNs = qnType.namespaceURI.encode("utf-8")
        chNs = bNs
        xmlChNs = transcode(chNs)
        bName = qnType.localName.encode("utf-8")
        chName = bName
        xmlChName = transcode(chName)
        xsTypeDefinition = self.xsModel.getTypeDefinition(xmlChName, xmlChNs)
        release(&xmlChName)
        release(&xmlChNs)
        bNs = None # deref bytes
        bName = None
        return xsTypeDefinition
    
    cdef QName xsElementDeclarationQName(self, XSElementDeclaration *xsElementDeclaration):
        cdef QName qnConcept
        cdef void* qnamePtr
        if xsElementDeclaration is NULL:
            return None
        if self.xsElementDeclarationQNames.containsKey(xsElementDeclaration):
            qnamePtr = self.xsElementDeclarationQNames.get(xsElementDeclaration)
            qnConcept = <QName>qnamePtr
            return qnConcept
        else: # not a declared type
            qnConcept = self.xmlchQName(xsElementDeclaration.getNamespace(), NULL, xsElementDeclaration.getName()) # must be interned else it goes out of existence on return from here
            qnamePtr = <void*>qnConcept
            self.xsElementDeclarationQNames.put(xsElementDeclaration, qnamePtr)
            return qnConcept
        
    cdef ModelConcept xsElementDeclarationConcept(self, XSElementDeclaration *xsElementDeclaration):
        cdef QName qnConcept
        cdef list modelDocuments
        cdef ModelConcept modelConcept
        if xsElementDeclaration is NULL:
            return None
        qnConcept = self.xsElementDeclarationQName(xsElementDeclaration)
        if qnConcept in self.qnameConcepts:
            return self.qnameConcepts[qnConcept]
        # create ModelConcept wrapper for element declaration
        if qnConcept.namespaceURI in self.targetNamespaceDocs: # targetNamespace is defined
            modelDocuments = self.targetNamespaceDocs.get(qnConcept.namespaceURI)
            if modelDocuments:
                modelConcept = newModelConcept(modelDocuments[0], xsElementDeclaration, qnConcept)
                self.qnameConcepts[qnConcept] = modelConcept
                self.nameConcepts[qnConcept.localName].append(modelConcept)
            return modelConcept
        return None

    cdef XSElementDeclaration* qnameXsElementDeclaration(self, QName qnConcept): # get xsModel's xsElementDeclaration
        cdef bytes bNs
        cdef bytes bName
        cdef char *chNs
        cdef char *chName
        cdef XMLCh *xmlChNs
        cdef XMLCh *xmlChName
        cdef XSElementDeclaration *xsElementDeclaration
        bNs = qnConcept.namespaceURI.encode("utf-8")
        chNs = bNs
        xmlChNs = transcode(chNs)
        bName = qnConcept.localName.encode("utf-8")
        chName = bName
        xmlChName = transcode(chName)
        xsElementDeclaration = self.xsModel.getElementDeclaration(xmlChName, xmlChNs)
        release(&xmlChName)
        release(&xmlChNs)
        bNs = None # deref bytes
        bName = None
        return xsElementDeclaration
 
    cpdef bool testXercesIntegrity(self, logPrompt) except +:
        cdef ModelConcept c
        cdef ModelType modelType
        cdef XSTypeDefinition * t
        cdef bool headerShown, test, result
        cdef int num, i, cat
        cdef QName qName
        cdef XSModel* xsModel
        cdef bool mdlChanged = 0 # true if this is a first time call and a new model is created
        cdef bool* mdlChangedPtr = &mdlChanged
        xsModel = self.xerces_grammar_pool.getXSModel(<bool&>mdlChangedPtr)
        if self.xsModel != xsModel:
            if not headerShown:
                headerShown = True
                print("Testing Xerces integrity {}".format(logPrompt))
            print("Testing Xerces integrity model changed, bool={}".format(mdlChanged))
            return False
        num = len(self.qnameConcepts)
        i = 0
        '''
        for c in self.qnameConcepts.values():
            i += 1
            test = 0 <= c.xsElementDeclaration.getScope() <= 2 and 0 <= c.xsElementDeclaration.getConstraintType() <= 2
            if not test:
                if traceToStdout:
                    if not headerShown:
                        headerShown = True
                        print("Testing Xerces integrity {}".format(logPrompt))
                    print("IntegrityError: ModelConcept {} of {} Xerces element declaration corrupted: {}".format(i,num,c.qname))
            else:
                qName = self.xmlchQName(c.xsElementDeclaration.getNamespace(), NULL, c.xsElementDeclaration.getName())
                test = c.qname == qName
                if not test:
                    if traceToStdout:
                        if not headerShown:
                            headerShown = True
                            print("Testing Xerces integrity {}".format(logPrompt))
                        print("IntegrityError: ModelConcept {} of {} QName {} doesn't match Xerces QName {}".format(i,num,c.qname, qName))
                else:
                    t = c.xsElementDeclaration.getTypeDefinition()
                    cat = t.getTypeCategory()
                    test = 15 <= cat <= 16
                    if not test:
                        if traceToStdout:
                            if not headerShown:
                                headerShown = True
                                print("Testing Xerces integrity {}".format(logPrompt))
                            print("IntegrityError: ModelConcept {} of {} Xerces type definition corrupted: {} typeCategory {}".format(i,num,c.qname,cat))
                    else:
                        qName = self.xmlchQName(t.getNamespace(), NULL, t.getName())
                        # if traceToStdout: print("Testing Xerces integrity {} concept {} type {}".format(logPrompt,c.qname,qName))
                        modelType = c.modelType()
                        if modelType is not None: # may be none if not yet discovered in loading process
                            test = modelType.qname == qName
                            if not test:
                                if traceToStdout:
                                    if not headerShown:
                                        headerShown = True
                                        print("Testing Xerces integrity {}".format(logPrompt))
                                    print("IntegrityError: ModelConcept ModelType QName {} doesn't match Xerces ModelType QName {}".format(c.qname, qName))
                        
            if not test:
                return False
        '''
        num = len(self.qnameTypes)
        i = 0
        for modelType in self.qnameTypes.values():
            i += 1
            t = modelType.xsTypeDefinition
            if t is NULL:
                if modelType.isAnonymous:
                    continue # anon types may be re-linked when referenced
                test = False
                if not headerShown:
                    headerShown = True
                    print("Testing Xerces integrity {}".format(logPrompt))
                print("IntegrityError: ModelType Xerces type definition {} of {} NULL: {} ".format(i,num,modelType.qname))
            elif not modelType.isAnonymous and not t.getAnonymous():
                cat = t.getTypeCategory()
                test = 15 <= cat <= 16
                if not test:
                    if not headerShown:
                        headerShown = True
                        print("Testing Xerces integrity {}".format(logPrompt))
                    print("IntegrityError: ModelType Xerces type definition {} of {} corrupted: {} typeCategory {}".format(i,num,modelType.qname,cat))
                else:
                    qName = self.xmlchQName(t.getNamespace(), NULL, t.getName())
                    # if traceToStdout: print("Testing Xerces integrity {} type {} cat {}".format(logPrompt,modelType.qname,cat))
                    test = modelType.qname == qName
                    if not test:
                        if not headerShown:
                            headerShown = True
                            print("Testing Xerces integrity {}".format(logPrompt))
                        print("IntegrityError: ModelType {} of {} QName {} doesn't match Xerces ModelType QName {}".format(i,num,modelType.qname, qName))
            if not test:
                return False
        return True
    
    cpdef object getUrlDoc(self, url): # get url doc whether mapped or not
        return self.urlDocs.get(self.mappedUrls.get(url,url))
            
    # @@@@ moved to ModelDocument
    #def loadSchema(self, object modelDocument, object pyFileDesc):
    #    self.openSax2Parser()
    #    cdef void* modelDocumentPtr = <void*>modelDocument
    #    cdef ModelXbrlSAX2Handler* SAX2Handler = <ModelXbrlSAX2Handler*>self.sax2_parser.getContentHandler()
    #    SAX2Handler.setModelDocument(modelDocumentPtr)
    #    cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
    #    cdef SchemaGrammar* schemaGrammar = <SchemaGrammar*>self.sax2_parser.loadGrammar( deref( inpSrc ), GrammarType.SchemaGrammarType, True)
    #    assert schemaGrammar is not NULL, "arelle:loadSchema schema grammar not loaded, null results"
    #    cdef XMLCh* xmlChTargetNS = <XMLCh*>schemaGrammar.getTargetNamespace()
    #    cdef char* targetNs = transcode(xmlChTargetNS)
    #    modelDocument.targetNamespace = targetNs
    #    release(&targetNs)
        
        
        
    #    SAX2Handler.setModelDocument(NULL) # dereference modelDocument
        
    
    
    #def loadXml(self, object modelDocument, object pyFileDesc, object schemaLocationsList):
    #    self.openSax2Parser()
    #    cdef void* modelDocumentPtr = <void*>modelDocument
    #    cdef ModelXbrlSAX2Handler* SAX2Handler = <ModelXbrlSAX2Handler*>self.sax2_parser.getContentHandler()
    #    SAX2Handler.setModelDocument(modelDocumentPtr)
    #    cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
    #    byte_s = " ".join(schemaLocationsList).encode("utf-8")
    #    cdef char* c_s = byte_s
    #    cdef XMLCh* xmlChSchemaLocation = transcode(c_s)
    #    self.sax2_parser.setProperty(fgXercesSchemaExternalSchemaLocation, xmlChSchemaLocation)
    #    self.sax2_parser.parse(deref(inpSrc))
    #    release(&xmlChSchemaLocation)
    
    #    SAX2Handler.setModelDocument(NULL) # dereference modelDocument
    
    def identifyXmlFile(self, pyFileDesc):
        # open a minimal parser for examining elements without any schema or further checking
        cdef SAX2XMLReader* parser = createXMLReader()
        cdef unicode pyStr
        cdef bytes bytesStr
        cdef char *chStr
        cdef XMLCh *xmlchNs
        cdef XMLCh *xmlchPrefix
        parser.setFeature(fgXercesLoadSchema, False)
        parser.setFeature(fgSAX2CoreNameSpacePrefixes, True)
        cdef object pyIdentificationResults = genobj(type=u"unknown XML",
                                                     ixdsTarget=self.ixdsTarget,
                                                     schemaRefs=OrderedSet(), 
                                                     linkbaseRefs=OrderedSet(), 
                                                     nonDtsSchemaRefs=OrderedSet(),
                                                     targetNamespace=None,
                                                     targetNamespacePrefix=None,
                                                     elementDeclIds=dict(),
                                                     annotationInfos=list(), # of genobj's of base, starting line no, sequence no.
                                                     namespacePrefixes=dict(),
                                                     hasXmlBase=False,
                                                     schemaXmlBase=None,
                                                     errors=[])
        cdef void* pyIdentificationResultsPtr = <void*>pyIdentificationResults
        cdef ModelXbrlIdentificationSAX2Handler * identificationSax2Handler = new ModelXbrlIdentificationSAX2Handler(pyIdentificationResultsPtr)
        parser.setErrorHandler(identificationSax2Handler)
        parser.setContentHandler(identificationSax2Handler)
        parser.setLexicalHandler(identificationSax2Handler)
        cdef void* modelXbrlPtr = <void*>self
        cdef ModelXbrlEntityResolver * modelXbrlEntityResolver = new ModelXbrlEntityResolver(modelXbrlPtr)
        cdef SAX2XMLReaderImpl* sax2parser = <SAX2XMLReaderImpl*>parser
        sax2parser.setXMLEntityResolver(modelXbrlEntityResolver)
        cdef XMLPScanToken* token = new XMLPScanToken()
        cdef bool result
        cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
        result = parser.parseFirst(deref(inpSrc), deref(token) ) # may raise an exception, such as if file does not exist
        while result:
            if identificationSax2Handler.isIdentified: # short cut to stop parsing after identified
                parser.parseReset(deref(token))
                token = NULL
                break
            result = parser.parseNext(deref(token))
        del parser
        identificationSax2Handler.close()
        del identificationSax2Handler
        modelXbrlEntityResolver.close()
        del modelXbrlEntityResolver
        # add namespace prefixes to modelXbrl (usually from instance first)
        for pyNs, pyPrefix in pyIdentificationResults.namespacePrefixes.items():
            bytesStr = pyNs.encode("utf-8")
            chStr = bytesStr
            xmlchNs = transcode(chStr)
            if not self.xmlchNamespacePrefixes.containsKey(xmlchNs):
                bytesStr = pyPrefix.encode("utf-8")
                chStr = bytesStr
                self.xmlchNamespacePrefixes.put(xmlchNs, transcode(chStr)) # hashmap owns both strings
            else:
                release(&xmlchNs)
            bytesStr = None
        return pyIdentificationResults
    
    def loadSchemaGrammar(self):
        # find any newly-discovered namespaces in schemaGrammar to load elements and types
        cdef XSModel* xsModel
        cdef bool mdlChanged = 0 # true if this is a first time call and a new model is created
        cdef bool* mdlChangedPtr = &mdlChanged
        cdef StringList *namespaces
        cdef const StringList *namespaceDocumentLocations
        cdef XSNamespaceItemList *namespaceItems
        cdef XSNamespaceItem* namespaceItem
        cdef XMLSize_t namespacesSize, annotationsSize
        cdef list namespacesInfo
        cdef XSNamedMap[XSObject]* xsObjects
        cdef XSObject *xsObject
        cdef XSTypeDefinition *xsTypeDefinition
        cdef XSElementDeclaration *xsElement
        cdef unsigned int i
        cdef const XMLCh* xmlchStr
        cdef XMLCh* xmlChNs
        cdef char* chStr
        cdef bytes bytesStr
        cdef unicode pyStr
        cdef unicode ns
        cdef unicode nsPrefix
        cdef unicode clarkNsPrefix
        cdef unicode pyClarkName
        cdef unicode docUrl
        cdef XMLSize_t j, k
        cdef list modelDocuments
        cdef set annotationDocumentsLoaded
        cdef ModelDocument modelDocument, annotationDoc
        cdef bool modelDocumentInDTS
        cdef ModelType modelType
        cdef ModelConcept modelConcept
        cdef XSAnnotationList* annotations
        cdef XSAnnotation* annotation
        cdef XMLCh* annotationText
        cdef XMLCh* annotationTextReplacedNS
        cdef dict annotationMdlDocIndex
        cdef tuple annotationInfo
        cdef object nsmap
        cdef object schemaDocFileDesc
        cdef dict attrs
        cdef QName qName
        cdef void* pyQNamePtr
        cdef bool priorSAX2CoreValidation
        cdef tuple elementDeclId
        annotationMdlDocIndex = dict()
        if traceToStdout: print("loadSchema1")
        # self.testXercesIntegrity("after loadSchema1")
        xsModel = self.getXsModel()
        if traceToStdout: print("loadSchema1 mdlChanged={} generation={}".format(mdlChanged, self.xsModelGeneration))
        if xsModel is not NULL:
            if self.xsModel != self.priorXsModel: # model changed
                self.priorXsModel = self.xsModel
                if traceToStdout: print("loadSchema1 xsModel ptr changed")
                self.xsTypeDefinitionQNames.removeAll() # prior pointers may have changed
                self.qnameXsTypeDefinitions.removeAll()
                self.xsElementDeclarationQNames.removeAll()
                for modelType in self.qnameTypes.values():
                    modelType.xsTypeDefinition = NULL # no longer valid, may be an anonymous type
                #for modelConcept in self.qnameConcepts.values():
                #    modelConcept.xsElementDeclaration = NULL # no longer valid, may be an anonymous type
            #self.testXercesIntegrity("after loadSchema2")
            namespaceItems = xsModel.getNamespaceItems()
            namespacesSize = namespaceItems.size()
            namespacesInfo = [None for i in range(namespacesSize)]
            if traceToStdout: print("loadSchema2 num of NS {}".format(namespacesSize))
            # identify type definitions
            for i in range(namespacesSize):
                namespaceItem = namespaceItems.elementAt(i)
                if namespaceItem is NULL:
                    continue
                xmlChNs = <XMLCh*>namespaceItem.getSchemaNamespace()
                ns = self.internXMLChString(xmlChNs)
                modelDocuments = list()
                docUrl = None
                namespaceDocumentLocations = namespaceItem.getDocumentLocations()
                if namespaceDocumentLocations is not NULL:
                    for j in range(namespaceDocumentLocations.size()):
                        xmlchStr = namespaceDocumentLocations.elementAt(j)
                        if xmlchStr is not NULL:
                            chStr = transcode(xmlchStr)
                            docUrl = chStr
                            modelDocument = self.getUrlDoc(docUrl)
                            if modelDocument is not None:
                                modelDocuments.append(modelDocument)
                            release(&chStr)
                # must have a modelDocument to proceed
                if traceToStdout: print("loadSchema3 {} doc {} files {} chkGrmrPool={}".format(ns, docUrl, [d.basename for d in modelDocuments],self.checkForGrammarPoolModelChange))
                #self.testXercesIntegrity("after loadSchema3")
                if not ns or not modelDocuments:
                    continue
                modelDocument = modelDocuments[0] # use first one
                modelDocumentInDTS = modelDocument.inDTS
                if modelDocumentInDTS and ns == uNsXbrldt:
                    self.hasXDT = True
                #if modelDocument.isGrammarLoadedIntoModel:
                #    if traceToStdout: print("skipping load schema grammar ns {} doc {}".format(ns, docUrl))
                #    continue
                if not modelDocumentInDTS:
                    if traceToStdout: print("skipping non-DTS schema concepts and assertions for ns {} doc {}".format(ns, docUrl))
                if traceToStdout: print("load schema grammar ns {} doc {} inDTS {}".format(ns, docUrl, modelDocumentInDTS))
                # get ns prefix
                nsPrefix = modelDocument.targetNamespacePrefix
                if traceToStdout: print("nsprefix none {} blank {}".format(nsPrefix is None, nsPrefix == ""))
                #self.testXercesIntegrity("after nsprefix")
                if nsPrefix:
                    clarkNsPrefix = "{{{}}}{}:".format(ns, nsPrefix)
                    bytesStr = nsPrefix.encode("utf-8")
                    chStr = bytesStr
                    if not self.xmlchNamespacePrefixes.containsKey(xmlChNs): # prefer entry doc prefixes to declaring schema prefixes
                        self.xmlchNamespacePrefixes.put(xmlChNs, transcode(chStr))
                    bytesStr = None
                elif self.xmlchNamespacePrefixes.containsKey(xmlChNs): # check if prefix from earlier document identification such as the entry document (maybe an instance)
                    chStr = transcode(self.xmlchNamespacePrefixes.get(xmlChNs))
                    nsPrefix = chStr
                    release(&chStr)
                    clarkNsPrefix = "{{{}}}{}:".format(ns, nsPrefix)
                else:
                    clarkNsPrefix = "{{{}}}".format(ns)
                if traceToStdout: print("schema nsPrefix={}".format(nsPrefix))
                if nsPrefix is None:
                    if traceToStdout: print("no doc prefix {}".format(ns))
                namespacesInfo[i] = (ns, clarkNsPrefix, modelDocumentInDTS, modelDocuments)
                xsObjects = xsModel.getComponentsByNamespace(TYPE_DEFINITION, xmlChNs)
                #self.testXercesIntegrity("before loadSchemaGrammar types")
                if traceToStdout: print("number of types {}".format(xsObjects.getLength()))
                if xsObjects is not NULL and xsObjects.getLength() > 0:
                    for j in range(xsObjects.getLength()):
                        xsTypeDefinition = <XSTypeDefinition *>xsObjects.item(j)
                        ''' only works for simple types, no apparent need for custom attrs on type
                        annotation = xsTypeDefinition.getAnnotation()
                        annotationText = NULL
                        if annotation is not NULL:
                            annotationText = annotation.getAnnotationString()
                        nsmap, attrs = self.getSchemaAttrs(annotationText)
                        '''
                        if traceToStdout: print("type {} {} {}".format(j, "SIMPLE" if xsTypeDefinition.getTypeCategory() == 16 else "COMPLEX", transcode(xsTypeDefinition.getName())))
                        xmlchStr = xsTypeDefinition.getName()
                        chStr = transcode(xmlchStr)
                        pyStr = chStr
                        pyClarkName = clarkNsPrefix + pyStr
                        qName = self.internedQNames.get(pyClarkName) # None if qname wasn't yet interned
                        if qName and qName in self.qnameTypes: # new entry would not be there
                            modelType = self.qnameTypes[qName]
                            if modelType.xsTypeDefinition != xsTypeDefinition and traceToStdout:
                                print("xsTypeDefinition changed")
                            modelType.xsTypeDefinition = xsTypeDefinition # pointer may have changed
                        elif modelDocumentInDTS: # only pre-create types which are in-DTS, rest are lazy-created as needed
                            if not qName: # intern qName
                                qName = self.internQName(pyClarkName)
                            modelType = newModelType(modelDocument, xsTypeDefinition, qName)
                            if pyStr:  # don't index elements with ref and no name
                                self.qnameTypes.setdefault(qName, modelType) # don't redefine types nested in anonymous types
                        release(&chStr)
                        if qName: # skip non-DTS types which haven't yet been referenced
                            pyQNamePtr = <void*>qName
                            self.xsTypeDefinitionQNames.put(xsTypeDefinition, pyQNamePtr)
            # identify concept definitions
            for i in range(namespacesSize):
                namespaceItem = namespaceItems.elementAt(i)
                if namespacesInfo[i] is None:
                    continue
                xmlChNs = <XMLCh*>namespaceItem.getSchemaNamespace()
                ns, clarkNsPrefix, modelDocumentInDTS, modelDocuments = namespacesInfo[i]
                #self.testXercesIntegrity("after loadSchemaGrammar types")
                xsObjects = xsModel.getComponentsByNamespace(ELEMENT_DECLARATION, xmlChNs)
                if traceToStdout: print("number of elements {} ns {}".format(xsObjects.getLength(),ns))
                if xsObjects is not NULL and xsObjects.getLength() > 0:
                    for j in range(xsObjects.getLength()):
                        # these are top level elements (not any nested elements in type definition particles)
                        xsElement = <XSElementDeclaration *>xsObjects.item(j)
                        annotation = xsElement.getAnnotation()
                        annotationText = NULL
                        if annotation is not NULL:
                            annotationText = annotation.getAnnotationString()
                        xmlchStr = xsElement.getName()
                        chStr = transcode(xmlchStr)
                        pyStr = chStr
                        pyClarkName = clarkNsPrefix + pyStr
                        qName = self.internedQNames.get(pyClarkName) # None if qname wasn't yet interned
                        # if traceToStdout: print("elements {}".format(pyClarkName))
                        if qName and qName in self.qnameConcepts: # new entry would not be there
                            # if traceToStdout: print("in qnameConcepts")
                            #modelConcept = self.qnameConcepts[qName]
                            #modelConcept.xsElementDeclaration = xsElement # pointer may have changed
                            pass
                        elif modelDocumentInDTS: # only pre-create concepts which are in-DTS, rest are lazy-created as needed (such as for substitution group)
                            if not qName: # intern qName
                                qName = self.internQName(pyClarkName)
                            # find which modelDocument has name (reversed so first is default if not found)
                            for modelDocument in reversed(modelDocuments):
                                if pyStr in modelDocument.elementDeclIds:
                                    break
                            # if traceToStdout: print("new modelConcept")
                            modelConcept = newModelConcept(modelDocument, xsElement, qName)
                            if modelDocument.elementDeclIds is not None and pyStr in modelDocument.elementDeclIds:
                                elementDeclId = modelDocument.elementDeclIds[pyStr]
                                modelConcept.setValue(nsNoNamespace, lnId, elementDeclId[0], SPECIFIED_ATTRIBUTE)
                                modelConcept.setSourceLineCol(elementDeclId[1], elementDeclId[2])
                                modelConcept.setValue(nElementSequence, NULL, elementDeclId[3], OBJECT_PROPERTY)
                            #if traceToStdout: print("element annotation {}".format(transcode(annotationText)))
                            if annotationText is not NULL:
                                annotationTextReplacedNS = replaceXsNamespace(annotationText)
                                self.getSchemaAttrs(annotationTextReplacedNS, modelConcept, xmlchSchemaLocationsForXsdElements, skipValidation=False)
                            if pyStr:  # don't index elements with ref and no name
                                # if traceToStdout: print("added to qnameConcepts {}".format(qName))
                                self.qnameConcepts[qName] = modelConcept
                                self.nameConcepts[pyStr].append(modelConcept)
                        release(&chStr)
                        if qName: # skip non-DTS concepts which haven't yet been referenced such as by substitution group from an in-DTS concept
                            pyQNamePtr = <void*>qName
                            self.xsElementDeclarationQNames.put(xsElement, pyQNamePtr)
            # check for anonymous types
            '''
            for modelConcept in self.qnameConcepts.values():
                if modelConcept._modelTypeIsSet:
                    modelType = modelConcept.modelType()
                    if modelType.xsTypeDefinition is NULL: # no longer valid, may be an anonymous type, only top level types were set above
                        modelType.xsTypeDefinition = elementSubstitutionComplexHeadType(modelConcept.xsElementDeclaration)
                        if modelType.xsTypeDefinition is NULL:
                            if traceToStdout: print("loadSchemaGramma unable to get concept {} xsTypeDefinition for {}".format(modelConcept.qnme,modelType.qname))
            '''
            # check for non-DTS types (such as xmlSchema which is "built-in" xerces
            for modelType in self.qnameTypes.values():
                if modelType.xsTypeDefinition is NULL: # no longer valid, may be a out-of-DTS type
                    xsTypeDefinition = self.qnameXsTypeDefinition(modelType.qname)
                    if xsTypeDefinition is not NULL:
                        modelType.xsTypeDefinition = xsTypeDefinition
                    elif not modelType.isAnonymous:
                        if traceToStdout: print("loadSchemaGramma unable to get xsTypeDefinition for {}".format(modelType.qname))
            # process annotations, model may change on each namespace
            for i in range(namespacesSize):
                namespaceItem = self.getXsModel().getNamespaceItems().elementAt(i) # xsModel may have changed
                xmlChNs = <XMLCh*>namespaceItem.getSchemaNamespace()
                ns = self.internXMLChString(xmlChNs)
                annotationDocumentsLoaded = set()
                annotations = namespaceItem.getAnnotations()
                if annotations is not NULL:
                    if traceToStdout: print("loadSchema4 ns {} annotations size {}".format(ns,annotations.size()))
                    #priorSAX2CoreValidation = self.sax2_parser.getFeature(fgSAX2CoreValidation)
                    #self.sax2_parser.setFeature(fgSAX2CoreValidation, False) # validated when schema read, block re-validation now
                    #if traceToStdout: print("   annotation prior validation {}".format(priorSAX2CoreValidation))
                    annotationsSize = annotations.size()
                    for j in range(annotationsSize):
                        #if traceToStdout: print("   annotation #{} start  size {} ptr {}".format(j, annotations.size(), <long long>annotation))
                        annotation = <XSAnnotation*>self.getXsModel().getNamespaceItems().elementAt(i).getAnnotations().elementAt(j) # xsModel may have changed
                        while (annotation is not NULL):
                            xmlchStr = annotation.getSystemId()
                            if xmlchStr is not NULL:
                                chStr = transcode(xmlchStr)
                                docUrl = chStr
                                release(&chStr)
                            if not docUrl or self.mappedUrls.get(docUrl,docUrl) not in self.urlDocs:
                                continue
                            schemaDocFileDesc = genobj(filepath=docUrl) # fake FileDesc for opening input source on annotations
                            annotationDoc = self.getUrlDoc(docUrl)
                            k = annotationMdlDocIndex.setdefault(annotationDoc, 0)
                            if k < len(annotationDoc.annotationInfos):
                                annotationInfo = annotationDoc.annotationInfos[k]
                            else:
                                annotationInfo = None
                            annotationMdlDocIndex[annotationDoc] = k + 1
                            if traceToStdout: print("   annot info {} doc {} file {}".format(annotationInfo, annotationDoc.basename, docUrl))
                            #if traceToStdout: print("   annotation #{}  ptr {} before get string size {}".format(j, <long long>annotation, annotations.size()))
                            annotationText = annotation.getAnnotationString()
                            #if traceToStdout: print("   annotation #{} after get string size {}".format(k, annotations.size()))
                            if annotationText is not NULL and annotationDoc.inDTS and not annotationDoc.isGrammarLoadedIntoModel:
                                annotationDocumentsLoaded.add(annotationDoc)
                                annotationTextReplacedNS = replaceXsNamespace(annotationText)
                                if traceToStdout: print("   annot w/link text {}".format(transcode(annotationTextReplacedNS))) # [:80]))
                                annotationDoc.loadXmlXMLChSource(schemaDocFileDesc, annotationTextReplacedNS, annotationInfo, xmlchSchemaLocationsForXsdFileLinkbases)
                                #if annotationTextReplacedNS != annotationText: 
                                #    if traceToStdout: print("   annot w/link text {}".format(transcode(annotationTextReplacedNS))) # [:80]))
                                #    annotationDoc.loadXmlXMLChSource(schemaDocFileDesc, annotationTextReplacedNS, annotationInfo, xmlchSchemaLocationsForXsdFileLinkbases)
                                #    fgMemoryManager.deallocate(annotationTextReplacedNS)
                                #else:
                                #    if traceToStdout: print("   annot text {}".format(transcode(annotationText))) ##[:80]))
                                #    annotationDoc.loadXmlXMLChSource(schemaDocFileDesc, annotationText, annotationInfo, NULL, skipValidation=True)
                            #if traceToStdout: print("   annotation #{} processed size {}".format(j, annotations.size()))
                            annotation = annotation.getNext()
                            #if traceToStdout: print("   annotation next {}".format(annotation is not NULL))
                            break # seems to be recursive between annotations and getNext links
                    #self.sax2_parser.setFeature(fgSAX2CoreValidation, priorSAX2CoreValidation)
                    #self.testXercesIntegrity("after loadSchemaGrammar annotations")
                for annotationDoc in annotationDocumentsLoaded:
                    annotationDoc.isGrammarLoadedIntoModel = True
                schemaDocFileDesc = None # dereference
            if traceToStdout: print("loadSchemaGrammar done for annotations xsModelChange={}".format(self.xsModel != self.xerces_grammar_pool.getXSModel(<bool&>mdlChangedPtr)))

            annotationMdlDocIndex = None
            modelDocuments = None
            annotationDocumentsLoaded = None
            namespacesInfo = None
                    
        if traceToStdout: print("loadSchema9")
        if self.xsModel != self.xerces_grammar_pool.getXSModel(<bool&>mdlChangedPtr):
            if traceToStdout: print("loadSchema9 model changed {} generation {}".format(mdlChanged, self.xsModelGeneration))

            
    cdef XSModel* getXsModel(self):
        cdef bool mdlChanged = 0 # true if this is a first time call and a new model is created
        cdef bool* mdlChangedPtr = &mdlChanged
        cdef XSModel* xsModel
        xsModel = self.xerces_grammar_pool.getXSModel(<bool&>mdlChangedPtr)
        if self.checkForGrammarPoolModelChange or xsModel != self.xsModel:
            self.xsModel = xsModel
            self.checkForGrammarPoolModelChange = False
            self.xsModelGeneration = self.xsModelGeneration + 1
        return self.xsModel
            
                
    cdef traceNamespacesInModel(self):
        cdef bool mdlChanged = 0 # true if this is a first time call and a new model is created
        cdef bool* mdlChangedPtr = &mdlChanged
        cdef XSNamespaceItemList *namespaceItems = self.xerces_grammar_pool.getXSModel(<bool&>mdlChangedPtr).getNamespaceItems() # self.xsModel.getNamespaceItems()
        #cdef XSNamespaceItemList *namespaceItems = self.xsModel.getNamespaceItems()
        cdef XMLSize_t namespacesSize = namespaceItems.size()
        cdef unsigned int i
        cdef XSNamespaceItem* namespaceItem
        cdef XMLCh* xmlChNs
        if mdlChanged and traceToStdout: print("trace model was changed")
        for i in range(namespacesSize):
            namespaceItem = namespaceItems.elementAt(i)
            if namespaceItem is NULL:
                continue
            xmlChNs = <XMLCh*>namespaceItem.getSchemaNamespace()
            if traceToStdout: print("trace namespaces in model {}".format(transcode(xmlChNs)))
    
    cdef getSchemaAttrs(self, XMLCh* annotationText, object modelObject, XMLCh* xmlChSchemaLocations=NULL, bool skipValidation=True):
        cdef SAX2XMLReaderImpl* parser = self.schema_attr_parser
        cdef SchemaAttrSAX2Handler* schemaAttrSax2Handler
        cdef ModelXbrlEntityResolver* modelXbrlEntityResolver
        cdef void* modelXbrlPtr = <void*>self
        cdef void* modelObjectPtr = <void*>modelObject
        cdef bool doValidation = not skipValidation
        if annotationText is NULL:
            return
        cdef char* annotation_bytes = transcode(annotationText)
        #if traceToStdout: print("annotation {}".format(annotation_bytes))
        if parser is NULL:
            #parser = createXMLReader()
            parser = new SAX2XMLReaderImpl(fgMemoryManager, self.xerces_grammar_pool)
            self.schema_attr_parser = parser
            parser.setProperty(fgXercesScannerName, <void *>fgSGXMLScanner)
            parser.setFeature(fgSAX2CoreNameSpaces, True)
            parser.setFeature(fgXercesSchema, True)
            parser.setFeature(fgXercesLoadExternalDTD, False)
            parser.setFeature(fgXercesSkipDTDValidation, True)
            parser.setFeature(fgXercesHandleMultipleImports, True)
            parser.setFeature(fgXercesSchemaFullChecking, True)
            parser.setFeature(fgSAX2CoreNameSpacePrefixes, True)
            parser.setFeature(fgXercesDynamic, True)
            parser.setFeature(fgXercesGenerateSyntheticAnnotations, True)
            parser.setFeature(fgXercesCacheGrammarFromParse, True)
            parser.setFeature(fgXercesUseCachedGrammarInParse, True)
            parser.setFeature(fgXercesCalculateSrcOfs, True)
            parser.setFeature(fgXercesDisableDefaultEntityResolution, True)
            parser.setFeature(fgSAX2CoreValidation, doValidation)
            schemaAttrSax2Handler = new SchemaAttrSAX2Handler(modelXbrlPtr)
            parser.setErrorHandler(schemaAttrSax2Handler)
            parser.setContentHandler(schemaAttrSax2Handler)
            parser.setLexicalHandler(schemaAttrSax2Handler)
            modelXbrlEntityResolver = new ModelXbrlEntityResolver(modelXbrlPtr)
            # (incompatible with grammar pool?) self.sax2_parser.setPSVIHandler(SAX2Handler)
            parser.setXMLEntityResolver(modelXbrlEntityResolver)
        else:
            schemaAttrSax2Handler = <SchemaAttrSAX2Handler*>parser.getContentHandler()
            parser.setFeature(fgSAX2CoreValidation, doValidation)
        if xmlChSchemaLocations is not NULL:
            parser.setProperty(fgXercesSchemaExternalSchemaLocation, xmlChSchemaLocations)
        schemaAttrSax2Handler.modelObjectPtr = modelObjectPtr
        schemaAttrSax2Handler.isDone = False
        schemaAttrSax2Handler.lineNumberOffset = modelObject.sourceline - 1 # one line less because artifical annotation isn't really in the source file
        
        cdef XMLPScanToken* token = new XMLPScanToken()
        cdef bool result
        cdef bytes bytesBufId
        cdef const char* chBufId # file name
        bytesBufId = modelObject.modelDocument.url.encode("utf-8")
        chBufId = bytesBufId
        cdef InputSource* inpSrc = new MemBufInputSource( <XMLByte*>annotation_bytes, stringLen(annotationText), chBufId, False)
        result = parser.parseFirst(deref(inpSrc), deref(token) )
        while result:
            if schemaAttrSax2Handler.isDone:
                parser.parseReset(deref(token))
                token = NULL
                schemaAttrSax2Handler.resetHandler()
                break
            result = parser.parseNext(deref(token))
        token = NULL
        schemaAttrSax2Handler.modelObjectPtr = NULL
        bytesBufId = None # deref python bytes buffer ID and chBufId (which references bytesBufId)
        release(&annotation_bytes)

    def openSax2Parser(self):
        if self.sax2_parser is not NULL:
            return
        assert self.dom_parser is NULL, "setupSAX2parser: DOM parser is already set up"
        cdef void* modelXbrlPtr = <void*>self
        self.sax2_parser = new SAX2XMLReaderImpl(fgMemoryManager, self.xerces_grammar_pool)
        self.sax2_parser.setProperty(fgXercesScannerName, <void *>fgSGXMLScanner)
        self.sax2_parser.setFeature(fgSAX2CoreNameSpaces, True)
        self.sax2_parser.setFeature(fgXercesSchema, True)
        self.sax2_parser.setFeature(fgXercesLoadExternalDTD, False)
        self.sax2_parser.setFeature(fgXercesSkipDTDValidation, True)
        self.sax2_parser.setFeature(fgXercesHandleMultipleImports, True)
        self.sax2_parser.setFeature(fgXercesSchemaFullChecking, True)
        self.sax2_parser.setFeature(fgSAX2CoreNameSpacePrefixes, True)
        self.sax2_parser.setFeature(fgSAX2CoreValidation, True)
        self.sax2_parser.setFeature(fgXercesDynamic, True)
        self.sax2_parser.setFeature(fgXercesValidateAnnotations, False) # block because annotations validated later due to https://issues.apache.org/jira/browse/XERCESC-2193?page=com.atlassian.jira.plugin.system.issuetabpanels%3Acomment-tabpanel&focusedCommentId=17072932#
        self.sax2_parser.setFeature(fgXercesGenerateSyntheticAnnotations, True)
        self.sax2_parser.setFeature(fgXercesCacheGrammarFromParse, True) # must be true for schemaLocation to cause grammar to be visible in model
        self.sax2_parser.setFeature(fgXercesUseCachedGrammarInParse, True)
        self.sax2_parser.setFeature(fgXercesCalculateSrcOfs, True)
        self.sax2_parser.setFeature(fgXercesDisableDefaultEntityResolution, True)
        cdef ModelDocumentSAX2Handler* SAX2Handler = new ModelDocumentSAX2Handler(modelXbrlPtr)
        self.sax2_parser.setErrorHandler(SAX2Handler)
        self.sax2_parser.setContentHandler(SAX2Handler)
        self.sax2_parser.setLexicalHandler(SAX2Handler)
        cdef ModelXbrlEntityResolver* modelXbrlEntityResolver = new ModelXbrlEntityResolver(modelXbrlPtr)
        # (incompatible with grammar pool?) self.sax2_parser.setPSVIHandler(SAX2Handler)
        self.sax2_parser.setXMLEntityResolver(modelXbrlEntityResolver)
        
    cdef SchemaGrammar* sax2LoadGrammar(self, const InputSource& source, const GrammarType grammarType, const bool toCache) except +:
        # wrapped sax2 function to catch c++ exceptions
        cdef SchemaGrammar* schemaGrammar
        schemaGrammar = <SchemaGrammar*>self.sax2_parser.loadGrammar(source, grammarType, toCache)
        return schemaGrammar
        
cdef cppclass ModelXbrlErrorHandler(TemplateSAX2Handler):
    void* _modelXbrl
    EltDesc* eltDescs
    list eltModelObjects
    unsigned int eltDepthMax, eltDepth
    int lineNumberOffset, annotationSequence, appinfoSequence # set for ModelDocumentSAX2Handler

    ModelXbrlErrorHandler():
        cdef EltDesc* eltDesc
        cdef unsigned int i
        this.eltDepthMax = 1000
        this.eltDescs = <EltDesc*>fgMemoryManager.allocate(this.eltDepthMax * sizeof(EltDesc))
        if traceToStdout: print("init ModelXbrlErrorHandler {} eltDescs {}".format(<uint64_t>this, <uint64_t>this.eltDescs))
        this.eltModelObjects = list()
        for i in range(this.eltDepthMax):
            eltDesc = &this.eltDescs[i]
            eltDesc.prefixNsMap = NULL
            eltDesc.nsPrefixMap = NULL
            this.resetEltDesc(eltDesc)
            this.eltModelObjects.append(None)
        this.eltDepth = 0
        
    void resetEltDesc(EltDesc* eltDesc):
        eltDesc.xmlchQName = NULL
        eltDesc.xmlchChars = NULL
        eltDesc.hashQName = 0
        eltDesc.eltDecl = NULL
        eltDesc.hasError = False
        if eltDesc.prefixNsMap is not NULL: # should be empty at this point
            eltDesc.prefixNsMap.removeAll()
        if eltDesc.nsPrefixMap is not NULL: # should be empty at this point
            eltDesc.nsPrefixMap.removeAll()
        
    void resetHandler():
        cdef EltDesc* eltDesc
        while True:
            eltDesc = &this.eltDescs[this.eltDepth]
            this.resetEltDesc(eltDesc)
            if eltDesc.prefixNsMap is not NULL:
                del eltDesc.prefixNsMap
                eltDesc.prefixNsMap = NULL
            if eltDesc.nsPrefixMap is not NULL:
                del eltDesc.nsPrefixMap
                eltDesc.nsPrefixMap = NULL
            this.eltModelObjects[this.eltDepth] = None
            if this.eltDepth == 0:
                break
            this.eltDepth -= 1
            
    void close():
        if traceToStdout: print("close ModelXbrlErrorHandler {} eltDescs {} depth {}".format(<uint64_t>this, <uint64_t>this.eltDescs, this.eltDepth))
        this.resetHandler()
        fgMemoryManager.deallocate(this.eltDescs)
        this.eltDescs = NULL
        del this.eltModelObjects[:]
        this.eltModelObjects = None
    
    # document handlers
    void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs):
        #if traceToStdout: print("mdl xbrl start elt")
        #return
        cdef EltDesc* eltDesc
        this.eltDepth += 1
        eltDesc = &this.eltDescs[this.eltDepth]
        eltDesc.xmlchQName = <XMLCh*>qname
        #if traceToStdout: print("ModelXbrlErrorHandler.startElement dpth {}".format(this.eltDepth))

    void endElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname):
        #return
        cdef EltDesc* eltDesc = &this.eltDescs[this.eltDepth]
        this.resetEltDesc(eltDesc)
        this.eltModelObjects[this.eltDepth] = None
        this.eltDepth -= 1
        #if traceToStdout: print("ModelXbrlErrorHandler.endElement dpth {}".format(this.eltDepth))

    # error handlers
    void logError(const SAXParseException& exc, level):
        cdef EltDesc* eltDesc = &this.eltDescs[this.eltDepth]
        cdef const XMLCh* msg = exc.getMessage()
        cdef XMLFileLoc lineNumber = exc.getLineNumber() + this.lineNumberOffset
        cdef XMLFileLoc colNumber = exc.getColumnNumber()
        cdef char* msgText
        cdef char* fileName
        cdef char* url = NULL
        cdef char* eltQn
        if msg is not NULL:
            msgText = transcode(msg)
        else:
            msgText = b"null"
        cdef const XMLCh* _file = exc.getSystemId()
        if _file is not NULL:
            fileName = transcode(_file)
        else:
            fileName = b"null"
        if eltDesc.xmlchQName is not NULL:
            eltQn = transcode(eltDesc.xmlchQName)
        else:
            eltQn = b""
        if traceToStdout: print("xerces err msg: {} line: {} col: {}".format(msgText,lineNumber,colNumber))
        pyError = genobj(level=level,
                         message=msgText,
                         line=lineNumber,
                         column=colNumber,
                         file=fileName,
                         element=eltQn)
        cdef const XMLCh* _url = exc.getPublicId()
        if _url is not NULL:
            url = transcode(_file)
            pyError.url = url
        this.handlePyError(pyError)
        if msg is not NULL:
            release(&msgText)
        if _file is not NULL:
            release(&fileName)
        if eltDesc.xmlchQName is not NULL:
            release(&eltQn)
        if url is not NULL:
            release(&url)
    void error(const SAXParseException& exc):
        cdef EltDesc* eltDesc = &this.eltDescs[this.eltDepth]
        eltDesc.hasError = True
        this.logError(exc, u"ERROR") # values for logging._checkLevel acceptability
    void fatalError(const SAXParseException& exc):
        cdef EltDesc* eltDesc = &this.eltDescs[this.eltDepth]
        eltDesc.hasError = True
        this.logError(exc, u"CRITICAL")
    void warning(const SAXParseException& exc):
        this.logError(exc, u"WARNING")
        
    void handlePyError(object pyError):
        pass # implement in subclasses
        
cdef cppclass ModelXbrlIdentificationSAX2Handler(ModelXbrlErrorHandler):
    void* pyIdentificationResultsPtr
    bool isXbrl, isXsd, isHtml, isInline, isIdentified
    bool hasIxNamespace, hasIx11Namespace, hasLinkElement
    bool inTargetedReferences
    Locator* saxLocator
    int elementSequence[1000]
    
    ModelXbrlIdentificationSAX2Handler(void* pyIdentificationResultsPtr):
        this.pyIdentificationResultsPtr = pyIdentificationResultsPtr
        this.isXbrl = this.isXsd = this.isHtml = this.isInline = this.isIdentified = False
        this.hasIxNamespace = this.hasIx11Namespace = this.hasLinkElement = False
        this.inTargetedReferences = False
        cdef int i
        for i in range(1000):
            this.elementSequence[i] = 0
    void close():
        this.pyIdentificationResultsPtr = NULL
        ModelXbrlErrorHandler.close()

    # document handlers
    void setDocumentLocator(const Locator* const locator):
        this.saxLocator = <Locator*>locator
    
    void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs):
        cdef object pyIdentificationResults
        cdef EltDesc* eltDesc
        cdef XMLSize_t i, n
        cdef object attrValue, idValue, nameValue, v
        cdef const XMLCh* xmlchQn
        cdef const XMLCh* xmlchNs
        cdef XMLCh* xmlchBase
        cdef char* chStr
        
        pyIdentificationResults = <object>this.pyIdentificationResultsPtr
        eltDesc = &this.eltDescs[this.eltDepth] # enclosing element nesting level
        if this.eltDepth < 1000:
            this.elementSequence[this.eltDepth] += 1
        xmlchBase = <XMLCh*>attrs.getValue(nsXml, lnBase)
        if xmlchBase is not NULL:
            eltDesc.xmlchChars = replicate(xmlchBase) # use .xmlchChars for base attributes
            pyIdentificationResults.hasXmlBase = True
        if not isInline and not isXsd and equals(uri, nsXbrli): # instance can be in appinfo of schema file
            if equals(localname, lnXbrl):
                this.isXbrl = True
                pyIdentificationResults.type = u"instance"
        elif equals(uri, nsXsd):
            if equals(localname, lnSchema):
                this.isXsd = True
                pyIdentificationResults.type = u"schema"
                attrValue = getAttrValue(attrs, nsNoNamespace, lnTargetNamespace)
                if attrValue is not None:
                    pyIdentificationResults.targetNamespace = attrValue
                    xmlchNs = attrs.getValue(nsNoNamespace, lnTargetNamespace)
                    # find any non-default xmlns for this namespace
                    n = attrs.getLength()
                    for i in range(n):
                        xmlchQn = <XMLCh*>attrs.getQName(i)
                        if xmlchQn is not NULL and startsWith(xmlchQn, xmlnsPrefix):
                            xmlchQn = <XMLCh*>attrs.getValue(i)
                            if equals(xmlchQn, xmlchNs):
                                xmlchQn = <XMLCh*>attrs.getLocalName(i)
                                chStr = transcode(xmlchQn)
                                pyIdentificationResults.targetNamespacePrefix = chStr
                                release(&chStr)
                                break
                pyIdentificationResults.schemaXmlBase = this.xmlBase()
            elif this.isXsd and this.eltDepth == 1:
                if equals(localname, lnElement):
                    # find any @id attribute
                    idValue = getAttrValue(attrs, nsNoNamespace, lnId)
                    if idValue is not None:
                        nameValue = getAttrValue(attrs, nsNoNamespace, lnName)
                        if nameValue is not None:
                            pyIdentificationResults.elementDeclIds[nameValue] = (idValue, this.saxLocator.getLineNumber(), this.saxLocator.getColumnNumber(), this.elementSequence[this.eltDepth])
                elif equals(localname, lnAnnotation): # level 1 annotation element
                    pyIdentificationResults.annotationInfos.append( (this.saxLocator.getLineNumber()-1, this.elementSequence[this.eltDepth]) )
                elif equals(localname, lnImport) or equals(localname, lnInclude):
                    attrValue = getAttrValue(attrs, nsNoNamespace, lnSchemaLocation)
                    if attrValue is not None:
                        addBasedHref(pyIdentificationResults.schemaRefs, attrValue)                 
        elif equals(uri, nsXhtml):
            if equals(localname, lnXhtml) or equals(localname, lnHtml):
                if this.hasIx11Namespace:
                    pyIdentificationResults.type = u"inline XBRL instance"
                    addBasedHref(pyIdentificationResults.nonDtsSchemaRefs, uHrefIx11)
                    this.isInline = True
                elif this.hasIxNamespace:
                    pyIdentificationResults.type = u"inline XBRL instance"
                    addBasedHref(pyIdentificationResults.nonDtsSchemaRefs, uHrefIx10)
                    this.isInline = True
                else:
                    pyIdentificationResults.type = u"xhtml"
                this.isHtml = True
                # not ready to set isIdentified here, need to keep looking for schemaRef's 
        elif equals(uri, nsLink):
            if not this.hasLinkElement:
                this.hasLinkElement = True
                addBasedHref(pyIdentificationResults.nonDtsSchemaRefs, uHrefLink)
            if this.isXbrl or (this.isInline and this.inTargetedReferences):
                if equals(localname, lnSchemaRef):
                    attrValue = getAttrValue(attrs, nsXlink, lnHref)
                    if attrValue is not None:
                        addBasedHref(pyIdentificationResults.schemaRefs, attrValue)
                elif equals(localname, lnLinkbaseRef):
                    attrValue = getAttrValue(attrs, nsXlink, lnHref)
                    if attrValue is not None:
                        addBasedHref(pyIdentificationResults.linkbaseRefs, attrValue)
                elif equals(localname, lnRoleRef) or equals(localname, lnArcroleRef):
                    attrValue = getAttrValue(attrs, nsXlink, lnHref)
                    if attrValue is not None:
                        addBasedHref(pyIdentificationResults.schemaRefs, attrValue.partition("#")[0])
            elif equals(localname, lnLoc):
                attrValue = getAttrValue(attrs, nsXlink, lnHref)
                if attrValue is not None:
                    v = attrValue.partition("#")[0]
                    if v.endswith(".xsd"):
                        addBasedHref(pyIdentificationResults.schemaRefs, v)
                    else:
                        addBasedHref(pyIdentificationResults.linkbaseRefs, v)
            elif this.isXsd and equals(localname, lnLinkbaseRef):
                attrValue = getAttrValue(attrs, nsXlink, lnHref)
                if attrValue is not None:
                    addBasedHref(pyIdentificationResults.linkbaseRefs, attrValue)
            elif equals(localname, lnRoleRef) or equals(localname, lnArcroleRef): # can be in instance, linkbase, or schema annotation
                attrValue = getAttrValue(attrs, nsXlink, lnHref)
                if attrValue is not None:
                    v = attrValue.partition("#")[0]
                    if v.endswith(".xsd"):
                        addBasedHref(pyIdentificationResults.schemaRefs, v)
                    else:
                        addBasedHref(pyIdentificationResults.linkbaseRefs, v)
            elif this.eltDepth == 0 and equals(localname, lnLinkbase):
                # need to parse locs of linkbase... this.isIdentified = True # no need to parse further 
                pyIdentificationResults.type = u"linkbase"
        elif equals(uri, nsVer):
            if equals(localname, lnReport):
                this.isIdentified = True # no need to parse further 
                pyIdentificationResults.type = u"versioning report"
        elif (equals(uri, nsIxbrl) or equals(uri, nsIxbrl11)) and equals(localname, lnReferences):
            this.inTargetedReferences = pyIdentificationResults.ixdsTarget == getAttrValue(attrs, nsNoNamespace, lnTarget)
        elif this.eltDepth == 0:
            if equals(localname, lnTestcases) or equals(localname, lnDocumentation) or equals(localname, lnTestSuite):
                this.isIdentified = True # no need to parse further 
                pyIdentificationResults.type = u"testcases index"
            elif equals(localname, lnTestcase) or equals(localname, lnTestSet):
                this.isIdentified = True # no need to parse further 
                pyIdentificationResults.type = u"testcase"
            elif equals(localname, lnRss):
                this.isIdentified = True # no need to parse further 
                pyIdentificationResults.type = u"rss"
            elif equals(localname, lnPtvl):
                this.isIdentified = True # no need to parse further 
                pyIdentificationResults.type = u"arcs infoset"
            elif equals(localname, lnFacts):
                this.isIdentified = True # no need to parse further 
                pyIdentificationResults.type = u"fact dimensions infoset"
        elif this.isXbrl:
            this.isIdentified = True # no need to parse further 
        if this.eltDepth == 0:
            # add schemaLocations and no namespace schema location (especially for non-recotnized XML files)
            attrValue = getAttrValue(attrs, nsXsi, lnNoNamespaceSchemaLocation)
            if attrValue:
                addBasedHref(pyIdentificationResults.nonDtsSchemaRefs, attrValue)
        attrValue = getAttrValue(attrs, nsXsi, lnSchemaLocation) # may occur at any depth
        if attrValue is not None:
            for i, v in enumerate(attrValue.split()):
                if i & 1:
                    addBasedHref(pyIdentificationResults.nonDtsSchemaRefs, v)

        ModelXbrlErrorHandler.startElement(uri, localname, qname, attrs)

    void endElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname):
        cdef EltDesc* eltDesc
        if (equals(uri, nsIxbrl) or equals(uri, nsIxbrl11)) and equals(localname, lnReferences):
            this.inTargetedReferences = False
        if this.isInline and equals(localname, lnResources) and (equals(uri, nsIxbrl) or equals(uri, nsIxbrl11)):
            this.isIdentified = True # schemaRef's found, ok to stop parsing
        ModelXbrlErrorHandler.endElement(uri, localname, qname)
        eltDesc = &this.eltDescs[this.eltDepth] # enclosing element nesting level
        if eltDesc.xmlchChars is not NULL:
            release(&eltDesc.xmlchChars)
            eltDesc.xmlchChars = NULL # clear .xmlchChars of base attributes
        
    void startPrefixMapping(const XMLCh* prefix, const XMLCh* uri):
        cdef object pyIdentificationResults
        cdef const XMLCh* xmlCh
        cdef char* chStr
        cdef unicode pyNs, pyPrefix
        if equals(uri, nsIxbrl):
            this.hasIxNamespace = True
        elif equals(uri, nsIxbrl11):
            this.hasIx11Namespace = True
        if prefix is not NULL and (prefix[0] != chNull or equals(uri, nsXhtml)): # allow default prefix only on xhtml
            pyIdentificationResults = <object>this.pyIdentificationResultsPtr
            chStr = transcode(uri)
            pyNs = chStr
            release(&chStr)
            if pyNs not in pyIdentificationResults.namespacePrefixes:
                chStr = transcode(prefix)
                pyPrefix = chStr
                release(&chStr)
                pyIdentificationResults.namespacePrefixes[pyNs] = pyPrefix            
            
    void handlePyError(object pyError):
        pyIdentificationResults = <object>this.pyIdentificationResultsPtr
        pyIdentificationResults.errors.append(pyError)
        
    unicode xmlBase():
        cdef EltDesc* eltDesc
        cdef int i
        cdef char* chXmlBase
        cdef unicode base = uEmptyStr
        cdef unicode _xmlBase = None
        for i in range(this.eltDepth, -1, -1):
            eltDesc = &this.eltDescs[i]
            if eltDesc.xmlchChars is not NULL:
                chXmlBase = transcode(eltDesc.xmlchChars)
                _xmlBase = chXmlBase
                release(&chXmlBase)
                if _xmlBase:
                    base = _xmlBase + base
                    if base.startswith("/"):
                        break # absolute to authority or file path
        if base:
            return base
        return None
        
    void addBasedHref(object baseHrefsSet, unicode href):
        cdef unicode base = None
        if not isAbsoluteUrl(href):
            base = this.xmlBase()
        baseHrefsSet.add( (base, href) )
        
cdef cppclass ModelXbrlEntityResolver(XMLEntityResolver):
    void* modelXbrlPtr
    
    ModelXbrlEntityResolver(void* modelXbrlPtr):
        this.modelXbrlPtr = modelXbrlPtr
        
    close():
        this.modelXbrlPtr = NULL # dereference
        
    InputSource* resolveEntity(XMLResourceIdentifier* xmlri):
        cdef ResourceIdentifierType _type = xmlri.getResourceIdentifierType()
        cdef const XMLCh* publicId = xmlri.getPublicId()
        cdef const XMLCh* systemId = xmlri.getSystemId()
        cdef const XMLCh* schemaLocation = xmlri.getSchemaLocation()
        cdef const XMLCh* baseURL = xmlri.getBaseURI()
        cdef const XMLCh* nameSpace = xmlri.getNameSpace()
        cdef const Locator* locator = xmlri.getLocator()
        cdef const XMLCh* locatorPublicId = locator.getPublicId()
        cdef const XMLCh* locatorSystemId = locator.getSystemId()
        cdef char* _publicId
        cdef char* _systemId
        cdef char* _schemaLocation
        cdef char* _baseURL
        cdef char* _nameSpace
        cdef char* _locatorPublicId
        cdef char* _locatorSystemId
        cdef object pyPublicId, pySystemId, pySchemaLocation, pyBaseURL, pyNameSpace, pyLocatorPublicId, pyLocatorSystemId
        if publicId is not NULL and publicId[0] != 0:
            _publicId = transcode(publicId)
            pyPublicId = _publicId
            release(&_publicId)
        else:
            pyPublicId = None
        if systemId is not NULL:
            _systemId = transcode(systemId)
            pySystemId = _systemId
            release(&_systemId)
        else:
            pySystemId = None
        if schemaLocation is not NULL:
            _schemaLocation = transcode(schemaLocation)
            pySchemaLocation = _schemaLocation
            release(&_schemaLocation)
        else:
            pySchemaLocation = None
        if baseURL is not NULL:
            _baseURL = transcode(baseURL)
            pyBaseURL = _baseURL
            release(&_baseURL)
        else:
            pyBaseURL = None
        if nameSpace is not NULL:
            _nameSpace = transcode(nameSpace)
            pyNameSpace = _nameSpace
            release(&_nameSpace)
        else:
            pyNameSpace = None
        if locatorPublicId is not NULL:
            _locatorPublicId = transcode(locatorPublicId)
            pyLocatorPublicId = _locatorPublicId
            release(&_locatorPublicId)
        else:
            pyLocatorPublicId = None
        if locatorSystemId is not NULL:
            _locatorSystemId = transcode(locatorSystemId)
            pyLocatorSystemId = _locatorSystemId
            release(&_locatorSystemId)
        else:
            pyLocatorSystemId = None
        cdef object modelXbrl = <object>this.modelXbrlPtr
        pyFileDesc = modelXbrl.xerces_resolve_entity(_type, pyPublicId, pySystemId, pySchemaLocation, pyBaseURL, pyNameSpace, 
                                                     pyLocatorPublicId, pyLocatorSystemId,
                                                     locator.getLineNumber(), locator.getColumnNumber())
        modelXbrl.checkForGrammarPoolModelChange = True
        if pyFileDesc is None:
            return NULL
        cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
        return inpSrc
        
cdef cppclass SchemaAttrSAX2Handler(ModelXbrlErrorHandler):
    void* modelXbrlPtr
    void* modelObjectPtr
    bool  isDone
    
    SchemaAttrSAX2Handler(void* modelXbrlPtr):
        this.modelXbrlPtr = modelXbrlPtr
        
    void close():
        this.modelXbrlPtr = NULL
        ModelXbrlErrorHandler.close()

    # document handlers
    void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs):
        cdef dict pyDict
        cdef XMLSize_t i, n
        cdef XMLCh* xmlChValue
        cdef ModelXbrl modelXbrl
        cdef ModelObject modelObject
        
        if equals(localname, lnAnnotation):
            modelXbrl = <object>this.modelXbrlPtr
            modelObject = <ModelObject>this.modelObjectPtr
            n = attrs.getLength()
            for i in range(n):
                xmlChQn = <XMLCh*>attrs.getQName(i)
                if xmlChQn is not NULL and startsWith(xmlChQn, xmlnsPrefix):
                    pass
                elif equals(xmlChQn, xmlns):
                    pass
                else:
                    xmlChValue = replicate(attrs.getValue(i))
                    trim(xmlChValue)
                    modelObject.setValue(attrs.getURI(i), attrs.getLocalName(i), modelXbrl.internXMLChString(xmlChValue), SPECIFIED_ATTRIBUTE)
                    release(&xmlChValue)
        this.isDone = True
        ModelXbrlErrorHandler.startElement(uri, localname, qname, attrs)
            
    void handlePyError(object pyError):
        cdef object modelXbrl = <object>this.modelXbrlPtr
        modelXbrl.log(pyError.level, "xmlSchema:xerces",
                      pyError.message,
                      sourceFileLine=(pyError.file, pyError.line, 0), # pyError.column isn't useful because it's in the synthetic annotation
                      element=pyError.element)
        if traceToStdout: print("xmlSchema:xerces {} {} {}".format(pyError.level, pyError.file, pyError.message))
        