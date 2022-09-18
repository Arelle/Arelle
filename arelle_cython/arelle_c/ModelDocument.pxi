from cython.operator cimport dereference as deref
from decimal import Decimal, InvalidOperation
from arelle_c.xerces_uni cimport fgXercesSchemaExternalSchemaLocation
from arelle_c.xerces_framework cimport PSVIItem, DataType, SIMPLE_TYPE, getDataType, \
    dt_string, dt_boolean, dt_decimal, dt_float, dt_double, dt_duration, dt_dateTime, \
    dt_time, dt_date, dt_gYearMonth, dt_gYear, dt_gMonthDay, dt_gDay, dt_gMonth, \
    dt_hexBinary, dt_base64Binary, dt_anyURI, dt_QName, dt_NOTATION, dt_normalizedString, \
    dt_token, dt_language, dt_NMTOKEN, dt_NMTOKENS, dt_Name, dt_NCName, dt_ID, dt_IDREF, \
    dt_IDREFS, dt_ENTITY, dt_ENTITIES, dt_integer, dt_nonPositiveInteger, dt_negativeInteger, \
    dt_long, dt_int, dt_short, dt_byte, dt_nonNegativeInteger, dt_unsignedLong, \
    dt_unsignedInt, dt_unsignedShort, dt_unsignedByte, dt_positiveInteger, dt_MAXCOUNT, \
    XSTypeDefinition, XSSimpleTypeDefinition, XSElementDeclaration, XSAttributeDeclaration, \
    XSAttributeUseList, XSAttributeUse, XSParticle, XSModelGroup, XSParticleList, \
    TERM_TYPE, TERM_ELEMENT, TERM_MODELGROUP, CONTENTTYPE_MIXED, \
    VALUE_CONSTRAINT, VALUE_CONSTRAINT_DEFAULT, VALUE_CONSTRAINT_FIXED, VARIETY_LIST
from arelle_c.xerces_validators cimport fgDT_STRING, fgWS_COLLAPSE, fgWS_REPLACE
from arelle_c.xerces_util cimport replicate, indexOf, collapseWS, replaceWS, tokenizeString, BaseRefVectorOf
from arelle import ModelValue, UrlUtil
from arelle.ModelDocument import Type as arelleModelDocumentType
from gettext import gettext as _    

cdef DataType dt_xbrliDateunion = <DataType>(dt_MAXCOUNT + 1)
cdef DataType dt_xbrliEndDate = <DataType>(dt_MAXCOUNT + 2)

ctypedef BaseRefVectorOf[XMLCh] XMLChVector

cdef class ModelDocument:
    cdef readonly ModelXbrl modelXbrl
    cdef readonly int type
    cdef readonly unicode url
    cdef readonly unicode filepath
    cdef public bool isGrammarLoadedIntoModel, inDTS
    cdef public unicode targetNamespace
    cdef public unicode targetNamespacePrefix
    cdef public unicode schemaXmlBase
    cdef public ModelObject xmlRootElement
    cdef readonly list topLinkElements # root-most link elements in schema annotations or root-most link/xl elements in instance
    cdef public dict idObjects
    cdef public dict elementDeclIds
    cdef dict elementSequenceObjects # used for schema Concepts and annotation objects
    cdef public list annotationInfos # starting line number of each schema file annotation element
    cdef readonly dict hrefs # indexed by modelHref
    cdef readonly list linkbaseObjects
    cdef dict linkbaseRoleRefs
    
    def __init__(self, ModelXbrl modelXbrl, int type, unicode url, unicode filepath):
        self.modelXbrl = modelXbrl
        self.type = type
        self.url = url
        self.filepath = filepath
        self.idObjects = dict()
        self.hrefs = dict()
        self.linkbaseObjects = list()
        self.topLinkElements = list()
        self.elementSequenceObjects = dict()
        
    def close(self):
        self.idObjects.clear()
        self.hrefs.clear()
        del self.linkbaseObjects[:]
                
    def loadSchema(self, object pyFileDesc, bool isIncluded, object pyIncludingNamespace):
        # wrap to catch exceptions
        self._loadSchema(pyFileDesc, isIncluded, pyIncludingNamespace) 
    
    cdef void _loadSchema(self, object pyFileDesc, bool isIncluded, object pyIncludingNamespace) except *:
        if traceToStdout: print("start loadSchema {}".format(pyFileDesc.url))
        cdef ModelXbrl modelXbrl = self.modelXbrl
        modelXbrl.openSax2Parser()
        cdef void* modelDocumentPtr = <void*>self
        cdef ModelDocumentSAX2Handler* sax2Handler = <ModelDocumentSAX2Handler*>modelXbrl.sax2_parser.getContentHandler()
        sax2Handler.setModelDocument(modelDocumentPtr)
        cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
        cdef SchemaGrammar* schemaGrammar = modelXbrl.sax2LoadGrammar( deref( inpSrc ), GrammarType.SchemaGrammarType, True)
        assert schemaGrammar is not NULL, "arelle:loadSchemaGrammarNull schema grammar not loaded, null results"
        cdef XMLCh* xmlChTargetNS = <XMLCh*>schemaGrammar.getTargetNamespace()
        cdef char* targetNs = transcode(xmlChTargetNS)
        cdef unicode pyNs = targetNs
        cdef list targetNamespaceDocsList
        if pyIncludingNamespace and not pyNs:
            self.targetNamespace = pyIncludingNamespace
        elif self.targetNamespace or pyNs: # don't test if both are either None or blank
            assert self.targetNamespace == pyNs, "arelle:loadSchemaNamespaceConflict schema grammar namespace {} discovery namespace {} file {}".format(self.targetNamespace, pyNs, pyFileDesc.url)
        if self.targetNamespace:
            targetNamespaceDocsList = modelXbrl.targetNamespaceDocs[self.targetNamespace]
            if self not in targetNamespaceDocsList:
                targetNamespaceDocsList.append(self)
        release(&targetNs)
        if traceToStdout: print("end loadSchema {}".format(pyFileDesc.url))
        sax2Handler.setModelDocument(NULL) # dereference modelDocument

    def loadXml(self, object pyFileDesc, object schemaLocationsList=None, bool skipValidation=False):
        self._loadXml(pyFileDesc, schemaLocationsList, skipValidation)

    cdef void _loadXml(self, object pyFileDesc, object schemaLocationsList, bool skipValidation) except *:
        cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc)
        cdef bytes bSchemaLocations
        cdef char *chSchemalocations
        cdef XMLCh *xmlChSchemaLocations = NULL
        if schemaLocationsList:
            bSchemaLocations = " ".join(schemaLocationsList).encode("utf-8")
            chSchemalocations = bSchemaLocations
            xmlChSchemaLocations = transcode(chSchemalocations)
        self.loadXmlInputSource(xmlChSchemaLocations, inpSrc, None, skipValidation)
        if schemaLocationsList:
            release(&xmlChSchemaLocations)
        
    cdef void* loadXmlXMLChSource(self, object pyFileDesc, XMLCh *xmlchXmlSource, tuple annotationInfo=None, XMLCh *xmlChSchemaLocations=NULL, bool skipValidation=False):
        cdef char* chXmlSrc = transcode(xmlchXmlSource)
        cdef InputSource* inpSrc = fileDescInputSource(pyFileDesc, chXmlSrc=chXmlSrc)
        self.loadXmlInputSource(xmlChSchemaLocations, inpSrc, annotationInfo, skipValidation)
        release(&chXmlSrc)
        
    cdef void* loadXmlInputSource(self, XMLCh *xmlChSchemaLocations, InputSource* inpSrc, tuple annotationInfo=None, bool skipValidation=False) except *:
        cdef ModelXbrl modelXbrl = self.modelXbrl
        modelXbrl.openSax2Parser()
        cdef void* modelDocumentPtr = <void*>self
        cdef bool priorValidationProperty
        cdef ModelDocumentSAX2Handler* sax2Handler = <ModelDocumentSAX2Handler*>modelXbrl.sax2_parser.getContentHandler()
        sax2Handler.setModelDocument(modelDocumentPtr)
        if annotationInfo is not None:
            assert len(annotationInfo) == 2, "AnnotationInfo from ModelXbrl.identifyXmlFile must be a list of 2 elements"
            sax2Handler.lineNumberOffset = annotationInfo[0]
            sax2Handler.annotationSequence = annotationInfo[1]
            sax2Handler.appinfoSequence = 0
            sax2Handler.isSchemaAnnotation = True
            # create schema element if none
            if self.xmlRootElement is None:
                self.xmlRootElement = ModelObject(self)
                self.xmlRootElement.setValue(nElementQName, NULL, qnXsdSchema, OBJECT_PROPERTY)
                if self.schemaXmlBase:
                    self.xmlRootElement.setValue(nsXml, lnBase, self.schemaXmlBase, SPECIFIED_ATTRIBUTE)
        if xmlChSchemaLocations is not NULL:
            modelXbrl.sax2_parser.setProperty(fgXercesSchemaExternalSchemaLocation, xmlChSchemaLocations)
        if skipValidation:
            priorValidationProperty = modelXbrl.sax2_parser.getFeature(fgSAX2CoreValidation)
            modelXbrl.sax2_parser.setFeature(fgSAX2CoreValidation, False)
        # assert modelXbrl.xsModel is not NULL, "loadXmlInputSource: xsModel is NULL (no grammar pool set up)"
        modelXbrl.sax2_parser.parse(deref(inpSrc))
        sax2Handler.setModelDocument(NULL) # dereference modelDocument
        if sax2Handler.isSchemaAnnotation:
            sax2Handler.lineNumberOffset = sax2Handler.annotationSequence = sax2Handler.appinfoSequence = 0
            sax2Handler.isSchemaAnnotation = False
        if skipValidation:
            modelXbrl.sax2_parser.setFeature(fgSAX2CoreValidation, priorValidationProperty)
        
    cdef modelHref(self, unicode urlWithoutFragment, unicode baseForElement, bool inDTS):
        cdef object _modelHref = ModelHref(urlWithoutFragment, baseForElement, inDTS)
        _modelHref = self.hrefs.setdefault(_modelHref, _modelHref) # if not in hrefs, adds this href, otherwise returns prior one
        return _modelHref
    
    def fragmentObject(self, unicode fragmentIdentifier):
        cdef object node
        # is it an ID?
        if not fragmentIdentifier: # whole document
            return self.xmlRootElement
        node = self.idObjects.get(fragmentIdentifier)
        if node is not None:
            return node
        cdef object matches, iter
        cdef unicode scheme, parenPart, path, id
        cdef int i, childNbr, eltNbr
        # handle as an element pointer
        matches = pXpointerFragmentIdentifierPattern.findall(fragmentIdentifier)
        if matches is None:
            return None
        # try element schemes until one of them works
        if traceToStdout: print("fragmentObject match loop")
        for scheme, parenPart, path in matches:
            if traceToStdout: print("frgmentObject match scheme {} parentPart {} path {}".format(scheme, parenPart, path))
            if scheme and (parenPart is None or len(parenPart) == 0): # shorthand id notation
                node = self.idObjects.get(scheme)
                if node is not None:
                    return node    # shorthand pointer is found
            elif scheme == "element" and parenPart and path:
                pathParts = path.split("/")
                if len(pathParts) >= 1 and len(pathParts[0]) > 0 and not pathParts[0].isnumeric():
                    id = pathParts[0]
                    if id in self.idObjects:
                        node = self.idObjects.get(id) # starting point for element sequences counting
                    if node is None:
                        continue    # this scheme fails
                elif self.type == arelleModelDocumentType.SCHEMA:
                    if len(pathParts) != 3 or pathParts[1] != "1": # only global element declarations are supported
                        continue # try next element scheme in sequence
                    node = self.elementSequenceObjects.get(int(pathParts[2]))
                    if node is not None:
                        return node
                    continue # try next sequence
                elif self.xmlRootElement: # won't work for schema files
                    node = self.xmlRootElement
                    iter = (node,)
                else:
                    node = None
                    iter = ()
                i = 1
                while i < len(pathParts):
                    childNbr = int(pathParts[i])
                    eltNbr = 1
                    parent = node
                    node = None
                    for child in iter:
                        if isinstance(child,ModelObject):
                            if childNbr == eltNbr:
                                node = child
                                break
                            eltNbr += 1
                    if node is None:
                        break   # not found in this scheme, scheme fails
                    iter = node.iterchildren()
                    i += 1
                if node is not None:    # found
                    return node
        return None

cdef XSElementDeclaration *particleElementDeclaration(XSParticle *particle, const XMLCh* uri, const XMLCh* localname):
    cdef TERM_TYPE particleTermType
    cdef XSElementDeclaration *eltDecl
    cdef XSModelGroup *modelGroupTerm
    cdef XSParticleList *groupParticlesList
    cdef XMLSize_t i
    if particle is NULL:
        return NULL
    particleTermType = particle.getTermType()
    if particleTermType == TERM_ELEMENT:
        eltDecl = particle.getElementTerm()
        if eltDecl is not NULL and equals(uri, eltDecl.getNamespace()) and equals(localname, eltDecl.getName()):
            return eltDecl
        return NULL
    if particleTermType == TERM_MODELGROUP:
        modelGroupTerm = particle.getModelGroupTerm()
        if modelGroupTerm is not NULL:
            groupParticlesList = modelGroupTerm.getParticles()
            for i in range(groupParticlesList.size()):
                eltDecl = particleElementDeclaration(groupParticlesList.elementAt(i), uri, localname)
                if eltDecl is not NULL:
                    return eltDecl
    return NULL
        
cdef XSElementDeclaration *childElementDeclaration(XSElementDeclaration* parentEltDecl, const XMLCh* uri, const XMLCh* localname):
    cdef XSTypeDefinition *parentEltTypeDef
    if parentEltDecl is NULL:
        return NULL
    parentEltTypeDef = parentEltDecl.getTypeDefinition()
    if parentEltTypeDef is NULL or parentEltTypeDef.getTypeCategory() != COMPLEX_TYPE:
        return NULL # need complex type with particles to find child element declarations
    return particleElementDeclaration( (<XSComplexTypeDefinition *>parentEltTypeDef).getParticle(), uri, localname)

cdef const XMLCh *xmlSchemaType(XSSimpleTypeDefinition *simpleTypeDef):
    cdef XSTypeDefinition* baseTypeDef
    if simpleTypeDef is NULL:
        return NULL
    if equals(nsXsd, (<XSTypeDefinition*>simpleTypeDef).getNamespace()):
        return (<XSTypeDefinition*>simpleTypeDef).getName()
    if simpleTypeDef.getVariety() == VARIETY_LIST:
        baseTypeDef = simpleTypeDef.getItemType()
    else:
        baseTypeDef = (<XSTypeDefinition*>simpleTypeDef).getBaseType()
    if baseTypeDef is not NULL and baseTypeDef.getTypeCategory() == SIMPLE_TYPE and baseTypeDef != simpleTypeDef:
        return xmlSchemaType(<XSSimpleTypeDefinition *>baseTypeDef)
    
        
cdef cppclass ModelDocumentSAX2Handler(ModelXbrlErrorHandler):
    void* modelXbrlPtr
    void* modelDocumentPtr
    int modelDocumentType
    bool warnInlineSelfClosingTags
    Locator* saxLocator
    bool isSchemaAnnotation
    XMLFileLoc startEventLineNumber, startEventColumnNumber; # for detecting self-closed elements

    
    ModelDocumentSAX2Handler(void* modelXbrlPtr):
        if traceToStdout: print("init ModelDocumentSAX2Handler {} eltDescs {}".format(<uint64_t>this, <uint64_t>this.eltDescs))
        this.modelXbrlPtr = modelXbrlPtr
        cdef EltDesc* eltDesc = &this.eltDescs[0]
        eltDesc.hashQName = hRootElement
        this.isSchemaAnnotation = False
        this.warnInlineSelfClosingTags = False
        
    void resetHandler():
        ModelXbrlErrorHandler.resetHandler()
        this.modelDocumentPtr = NULL
        this.isSchemaAnnotation = False
        this.warnInlineSelfClosingTags = False
    
    void setModelDocument(void* modelDocumentPtr):
        cdef ModelDocument modelDocument
        this.modelDocumentPtr = modelDocumentPtr
        if modelDocumentPtr is not NULL:
            modelDocument = <ModelDocument>modelDocumentPtr
            this.modelDocumentType = modelDocument.type
            this.warnInlineSelfClosingTags = (
                modelDocumentType == arelleModelDocumentType.INLINEXBRL and
                modelDocument.modelXbrl.modelManager.disclosureSystem.warnInlineSelfClosingTags)
        else:
            this.modelDocumentType = arelleModelDocumentType.UnknownXML
            this.warnInlineSelfClosingTags = False

    void close():
        this._modelXbrl = NULL # dereference
        this.saxLocator = NULL
        ModelXbrlErrorHandler.close()
        
    XMLCh* prefixNamespace(XMLCh* xmlchPrefix):
        cdef XMLCh* xmlchNs = nsNoNamespace
        cdef EltDesc* eltDesc
        cdef int i
        cdef StringHashTableEnumerator *prefixMapEnum
        cdef const XMLCh *attrLn
        for i in range(this.eltDepth, -1, -1):
            eltDesc = &this.eltDescs[i]
            #if traceToStdout: print("prefixNamespace trace level {}".format(i))
            #if eltDesc.prefixNsMap is not NULL:
            #    prefixMapEnum = new StringHashTableEnumerator(eltDesc.prefixNsMap)
            #    while prefixMapEnum.hasMoreElements():
            #        attrLn = <XMLCh*>prefixMapEnum.nextElementKey()
            #        if eltDesc.prefixNsMap.containsKey(attrLn):
            #            if traceToStdout: print("  prefix \"{}\" {}".format(transcode(attrLn), transcode(eltDesc.prefixNsMap.get(attrLn))))
            #        else:
            #            if traceToStdout: print("  prefix  not in map \"{}\"".format(transcode(attrLn)))
            if eltDesc.prefixNsMap is not NULL and eltDesc.prefixNsMap.containsKey(xmlchPrefix):
                xmlchNs = eltDesc.prefixNsMap.get(xmlchPrefix)
                break
        return xmlchNs

    XMLCh* namespacePrefix(XMLCh* xmlchNs):
        cdef XMLCh* xmlchPrefix = NULL
        cdef EltDesc* eltDesc
        cdef int i
        for i in range(this.eltDepth, -1, -1):
            eltDesc = &this.eltDescs[i]
            if eltDesc.nsPrefixMap is not NULL and eltDesc.nsPrefixMap.containsKey(xmlchNs):
                xmlchPrefix = eltDesc.nsPrefixMap.get(xmlchNs)
                break
        return xmlchPrefix


    void setDocumentLocator(const Locator* const locator):
        this.saxLocator = <Locator*>locator
    

    void startElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs):
        startElement2(uri, localname, qname, attrs)
    void startElement2(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname, const Attributes& attrs) except *:
        #if traceToStdout: print("mdl doc start elt")
        #ModelXbrlErrorHandler.startElement(uri, localname, qname, attrs)
        #return # HF TESTING
        cdef XSModel* xsModel
        cdef EltDesc* eltDesc
        cdef XSTypeDefinition *eltTypeDef = NULL
        cdef object _pyValue
        cdef const XMLCh* xmlchNs = uri
        cdef const XMLCh* xmlchLn = localname
        cdef const XMLCh* xmlchPrefix = NULL
        cdef XMLCh* xmlchVal
        cdef char* chStr
        cdef unicode attrValue
        cdef dict attrDict
        cdef ModelXbrl modelXbrl
        cdef ModelDocument modelDocument, referencedDocument
        cdef XMLSize_t hObjectType
        cdef ModelObject eltModelObject = None
        cdef ModelObject parentModelObject
        cdef XMLSize_t i
        cdef int attrIndex
        cdef void* modelObjectClassPtr
        cdef ModelObject modelObjectClass
        cdef XSElementDeclaration *eltDecl
        cdef bool modelWasChanged = 0        
        if traceToStdout: print("startElt0 ns {} ln {} dpth {} line {}".format(transcode(uri), transcode(localname), this.eltDepth, this.lineNumberOffset + this.saxLocator.getLineNumber()))
        # any text of prior level is the prior level's .text
        eltDesc = &this.eltDescs[this.eltDepth] # enclosing element nesting level
        if eltDesc.xmlchChars is not NULL:
            eltModelObject = this.eltModelObjects[this.eltDepth]
            if eltModelObject is not None:
                if traceToStdout: print("xmlchChars {}".format(transcode(eltDesc.xmlchChars)))
                if eltModelObject._lastChild is None: # text content for eltModelObject
                    if eltDesc.eltDecl is not NULL:
                        eltTypeDef = eltDesc.eltDecl.getTypeDefinition()
                    if modelDocumentType == arelleModelDocumentType.INLINEXBRL: # store text separately from pyValue (do before typed value does whitespace collapse
                        _pyValue = this.pyValue(NULL, uri, localname, eltDesc.xmlchChars, False) # untyped string value
                        if traceToStdout: print("pyValue {}".format(_pyValue))
                        eltModelObject.setValue(nElementText, NULL, _pyValue, OBJECT_VALUE)
                    _pyValue = this.pyValue(eltTypeDef, uri, localname, eltDesc.xmlchChars, False) # might ws collapse xmlChars
                    eltModelObject.setValue(uri, localname, _pyValue, OBJECT_VALUE)
                    _pyValue = None # dereference
                else: # this is tail for lastChild
                    eltModelObject._lastChild.setValue(nElementTail, NULL, this.pyValue(NULL, uri, localname, eltDesc.xmlchChars, False), OBJECT_VALUE)
            PyMem_Free(eltDesc.xmlchChars)
            eltDesc.xmlchChars = NULL # accumulate tail after returning from current nested element
            eltModelObject = None # dereference before assigning new eltModelObject
        ModelXbrlErrorHandler.startElement(uri, localname, qname, attrs)
        eltDesc = &this.eltDescs[this.eltDepth] # current element nesting level

        modelXbrl = <ModelXbrl>this.modelXbrlPtr
        modelDocument = <ModelDocument>this.modelDocumentPtr
        xsModel = modelXbrl.getXsModel()
        if xsModel is not NULL:
            eltDesc.eltDecl = xsModel.getElementDeclaration(localname, uri)
        else:
            eltDesc.eltDecl = NULL
        # may be declared in parent element
        if eltDesc.eltDecl is NULL and this.eltDepth > 0:
            if traceToStdout: print("start elt parent has elt decl")
            eltDesc.eltDecl = childElementDeclaration(this.eltDescs[this.eltDepth-1].eltDecl, uri, localname)
        if traceToStdout: print("start elt has elt decl {}".format(eltDesc.eltDecl is not NULL))
        while(True): # find defining type or what it substitute for
            if traceToStdout: print("startElt ns {} ln {}".format(transcode(xmlchNs), transcode(xmlchLn)))
            if equals(xmlchNs, nsXbrli):
                if equals(xmlchLn, lnTuple):                 
                    eltDesc.hashQName = hFactTuple
                    eltModelObject = newModelFact(modelDocument, True)   
                    break
                elif equals(xmlchLn, lnItem):
                    eltDesc.hashQName = hFactItem
                    eltModelObject = newModelFact(modelDocument, False)
                    break
                elif equals(xmlchLn, lnContext):
                    eltDesc.hashQName = hContext
                    eltModelObject = newModelContext(modelDocument)
                    break
                elif equals(xmlchLn, lnUnit):
                    eltDesc.hashQName = hUnit
                    eltModelObject = newModelUnit(modelDocument)
                    break
                else: # any other xbrli element, such as xbrli, schemaRef, etc.
                    eltModelObject = ModelObject(modelDocument)
                    break
            elif equals(xmlchNs, nsXsd):
                if not (equals(xmlchLn, lnAnnotation) or equals(xmlchLn, lnAppinfo)):
                    break # schema elements are created by ModelXbrl.loadSchemaGrammar, never parsed as xml
            elif equals(xmlchNs, nsLink):
                if equals(xmlchLn, lnRoleType):
                    eltDesc.hashQName = hRoleType
                    eltModelObject = ModelRoleType(modelDocument, False)
                    break
                elif equals(xmlchLn, lnArcroleType):
                    eltDesc.hashQName = hArcroleType
                    eltModelObject = ModelRoleType(modelDocument, True)
                    break
                elif equals(xmlchLn, lnRoleRef):
                    eltDesc.hashQName = hRoleRef
                    eltModelObject = ModelRoleRef(modelDocument, False)
                    break
                elif equals(xmlchLn, lnArcroleRef):
                    eltDesc.hashQName = hArcroleRef
                    eltModelObject = ModelRoleRef(modelDocument, True)
                    break
                elif equals(xmlchLn, lnDefinition) or equals(xmlchLn, lnUsedOn):
                    break # these elements are captured in the roleType or arcroleType element, not separate element
                elif equals(xmlchLn, lnLinkbase):
                    eltModelObject = ModelObject(modelDocument)
                    modelDocument.linkbaseObjects.append(eltModelObject)
                    modelDocument.linkbaseRoleRefs = dict() # for load-time validation
                    break
                # any other link element goes for underlying substitution element
            elif equals(xmlchNs, nsXl):
                # is it an extended link, locator, or resource?
                if equals(xmlchLn, lnSimple) or equals(xmlchLn, lnTitle):
                    eltDesc.hashQName = hSimple
                    eltModelObject = ModelXlinkSimple(modelDocument)
                    break
                elif equals(xmlchLn, lnExtended):
                    eltDesc.hashQName = hExtended
                    eltModelObject = ModelXlinkExtended(modelDocument)
                    break
                elif equals(xmlchLn, lnLocator):
                    eltDesc.hashQName = hLocator
                    eltModelObject = ModelXlinkLocator(modelDocument)
                    break
                elif equals(xmlchLn, lnResource):
                    eltDesc.hashQName = hResource
                    eltModelObject = ModelXlinkResource(modelDocument)
                    break
                elif equals(xmlchLn, lnArc):
                    eltDesc.hashQName = hArc
                    eltModelObject = ModelXlinkArc(modelDocument)
                    break
                else: # any other xl element without type, such as xl:documentation
                    eltModelObject = ModelObject(modelDocument)
                break
            elif equals(xmlchNs, nsXbrldi):
                if equals(xmlchLn, lnExplicitMember) or equals(xmlchLn, lnTypedMember):
                    eltDesc.hashQName = hDimension
                    eltModelObject = newModelDimensionValue(modelDocument)
                else: # any other xl element without type
                    eltModelObject = ModelObject(modelDocument)
                break

            if traceToStdout: print("startElt before modelObjectClassPtr")
            modelObjectClassPtr = registeredModelObjectClassPtr(xmlchNs, xmlchLn)
            if modelObjectClassPtr is not NULL:
                modelObjectClass = <ModelObject>modelObjectClassPtr
                if traceToStdout: print("obj class {}".format(modelObjectClass))
                eltModelObject = modelObjectClass(modelDocument)
                break
            if traceToStdout: print("startElt before get elt decl")
            if xsModel is not NULL:
                eltDecl = xsModel.getElementDeclaration(xmlchLn, xmlchNs)
            else:
                eltDec = NULL
            if traceToStdout: print("startElt before got elt decl {}".format(<long long>eltDecl))
            if eltDecl is NULL:
                # modelXbrl.traceNamespacesInModel()
                eltModelObject = ModelObject(modelDocument) # undeclared element, create undeclared ModelObject
                break
            eltDecl = eltDecl.getSubstitutionGroupAffiliation()
            if traceToStdout: print("startElt before sub elt decl {}".format(<long long>eltDecl))
            if eltDecl is NULL:
                eltModelObject = ModelObject(modelDocument) # no substitution declared, create non xbrli ModelObject
                break
            xmlchLn = eltDecl.getName()
            xmlchNs = eltDecl.getNamespace()
                            
        if eltModelObject is not None:
            if equals(uri, nsXhtml):
                xmlchPrefix = nsNoPrefix # use no prefix for xhtml elements, rest use xsd prefix
            eltModelObject.setValue(nElementQName, NULL, modelXbrl.internQName(clarkName(uri, xmlchPrefix, qname)), OBJECT_PROPERTY)
            eltModelObject.setSourceLineCol(this.lineNumberOffset + this.saxLocator.getLineNumber(), this.saxLocator.getColumnNumber())
            if traceToStdout: print("startElt2 qn {}".format(eltModelObject.qname))
            if this.eltDepth == 1 and modelDocument.xmlRootElement is None:
                modelDocument.xmlRootElement = eltModelObject
            this.eltModelObjects[this.eltDepth] = eltModelObject
            parentModelObject = this.getParentModelObject(modelDocument)
            if parentModelObject is not None:
                if traceToStdout: print("parent {} dpth {}".format(parentModelObject.qname.localName, this.eltDepth))
                parentModelObject.append(eltModelObject)
                if ((modelDocumentType == arelleModelDocumentType.INSTANCE and this.eltDepth == 2) or
                    (modelDocumentType == arelleModelDocumentType.SCHEMA and this.eltDepth == 3) or
                    (modelDocumentType == arelleModelDocumentType.INLINEXBRL and parentModelObject.qname == qnIxbrl11Hidden)
                    ) and (equals(xmlchNs, nsLink) or equals(xmlchNs, nsXl)): # simple link or linkbase element
                    modelDocument.topLinkElements.append(eltModelObject) # top link elements in schema annotations or instances
                parentModelObject = None # dereference
            else:
                if (modelDocumentType == arelleModelDocumentType.LINKBASE and this.eltDepth == 1
                    ) and (equals(xmlchNs, nsLink) or equals(xmlchNs, nsXl)): # simple link or linkbase element
                    modelDocument.topLinkElements.append(eltModelObject) # root-most link elements in schema annotations or instances
                else:
                    if traceToStdout: print("no parent")
            this.setObjectAttributes(eltDesc, eltModelObject, attrs) # may use _parent of object
            if traceToStdout: print("attributes set")
            eltModelObject = None # dereference
            
        this.startEventLineNumber = this.saxLocator.getLineNumber() # used by self-closed element detection
        this.startEventColumnNumber = this.saxLocator.getColumnNumber()


    # document handlers
    void characters(const XMLCh* chars, const XMLSize_t length):
        cdef EltDesc* eltDesc = &this.eltDescs[this.eltDepth]
        cdef XMLSize_t i
        if eltDesc.xmlchChars is not NULL:
            i = length+1 + stringLen(eltDesc.xmlchChars)
            eltDesc.xmlchChars = <XMLCh*>PyMem_Realloc(eltDesc.xmlchChars, i * sizeof(XMLCh))
            catString(eltDesc.xmlchChars, chars)
        else:
            eltDesc.xmlchChars = <XMLCh*>PyMem_Malloc((length+1) * sizeof(XMLCh))
            copyString(eltDesc.xmlchChars, chars)

    void endElement(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname):
        this.endElement2(uri, localname, qname)
    void endElement2(const XMLCh* uri, const XMLCh* localname, const XMLCh* qname) except *:
        if traceToStdout: print("endElt dpth {} qn {} ".format(this.eltDepth, transcode(localname)))
        cdef EltDesc* eltDesc = &this.eltDescs[this.eltDepth]
        if traceToStdout: print("endElt2")
        cdef XSTypeDefinition *eltTypeDef = NULL
        cdef ModelObject eltModelObject = this.getModelObject(localname, uri)
        cdef ModelXbrl modelXbrl
        cdef ModelDocument modelDocument
        cdef object _pyValue
        #if eltModelObject is not None:
        #    if traceToStdout: print("endElt dpth {} ln {} elt {} id {} propV {} txt {}".format(this.eltDepth, transcode(localname), eltModelObject, eltModelObject.id, 
        #                                                                     eltModelObject.propertyView,
        #                                                                     transcode(eltDesc.xmlchChars) if eltDesc.xmlchChars is not NULL else ""))
        if traceToStdout: 
            print("endElt3")
            if eltDesc.hasError: print ("has error")
            print("endElt4 mdlObj type {}".format(type(eltModelObject).__name__))
        if eltModelObject is not None:
            if traceToStdout: print("   modelObj {} {}".format(eltModelObject, type(eltModelObject).__name__))
            # TBD: add fixed and default here
            if eltDesc.hasError:
                eltModelObject.setValue(nValidity, NULL, INVALID, OBJECT_PROPERTY)
            elif eltModelObject.xValid != INVALID:
                if eltModelObject.id is not None:
                    eltModelObject.setValue(nValidity, NULL, VALID_ID, OBJECT_PROPERTY)
                else:
                    eltModelObject.setValue(nValidity, NULL, VALID, OBJECT_PROPERTY)
            if eltDesc.xmlchChars is not NULL:
                if not eltDesc.hasError:
                    if traceToStdout: print("xmlchChars {}".format(transcode(eltDesc.xmlchChars)))
                    # accumulate tail as plain string
                    #if eltDesc.eltDecl is not NULL:
                    #    eltTypeDef = eltDesc.eltDecl.getTypeDefinition()
                    if eltModelObject._lastChild is None: # text content for eltModelObject
                        if traceToStdout: print("trace1")
                        if eltDesc.eltDecl is not NULL:
                            eltTypeDef = eltDesc.eltDecl.getTypeDefinition()
                        if traceToStdout: print("pyValue")
                        if modelDocumentType == arelleModelDocumentType.INLINEXBRL: # store text separately from pyValue (do before typed value does whitespace collapse
                            _pyValue = this.pyValue(NULL, uri, localname, eltDesc.xmlchChars, False) # untyped string value
                            eltModelObject.setValue(nElementText, NULL, _pyValue, OBJECT_VALUE)
                        _pyValue = this.pyValue(eltTypeDef, uri, localname, eltDesc.xmlchChars, False) # might ws collapse xmlChars
                        eltModelObject.setValue(uri, localname, _pyValue, OBJECT_VALUE)
                        _pyValue = None # dereference
                    else: # this is tail for lastChild
                        eltModelObject._lastChild.setValue(nElementTail, NULL, this.pyValue(NULL, uri, localname, eltDesc.xmlchChars, False), OBJECT_VALUE)
                PyMem_Free(eltDesc.xmlchChars)
                eltDesc.xmlchChars = NULL
            
            if not isInheritedQName(localname, uri):
                eltModelObject.setup() # parsing has set attributes and values
            
            # check for inline self-closed elements
            if (warnInlineSelfClosingTags and
                this.startEventLineNumber == this.saxLocator.getLineNumber() and 
                this.startEventColumnNumber == this.saxLocator.getColumnNumber() and
                eltModelObject.localName not in inlineElementsWithNoContent):
                modelXbrl = <ModelXbrl>this.modelXbrlPtr
                modelXbrl.warning("ixbrl:selfClosedTagWarning",
                                  _("Self-closed element \"%(element)s\" may contain text or other elements and should not use self-closing tag syntax (/>) when empty; change these to end-tags."),
                                  modelObject=eltModelObject, element=eltModelObject.qname.prefixedName)
        if traceToStdout: print("endElt5")
        if equals(uri, nsLink) and equals(localname, lnLinkbase):
            modelDocument = <ModelDocument>this.modelDocumentPtr
            modelDocument.linkbaseRoleRefs = None
        if traceToStdout: print("endElt6 dpth {} qn {} ".format(this.eltDepth, transcode(localname)))
        ModelXbrlErrorHandler.endElement(uri, localname, qname)

    void comment(const XMLCh* chars, const XMLSize_t length):
        if traceToStdout: print("comment dpth {} comment {}".format(this.eltDepth, transcode(chars)))
        cdef ModelXbrl modelXbrl = <ModelXbrl>this.modelXbrlPtr
        cdef EltDesc* eltDesc = &this.eltDescs[this.eltDepth]
        cdef ModelObject eltModelObject = this.getModelObject(NULL, NULL)
        cdef ModelComment modelComment
        cdef XMLCh *xmlchVal = <XMLCh*>chars
        cdef unicode pyVal = modelXbrl.internXMLChString(xmlchVal)
        
        modelComment = ModelComment(<ModelDocument>this.modelDocumentPtr, pyVal)

    void processingInstruction(const XMLCh* target, const XMLCh* data):
        cdef ModelXbrl modelXbrl = <ModelXbrl>this.modelXbrlPtr
        if traceToStdout: print("processingInstruction dpth {} target {} data {}".format(this.eltDepth, transcode(target), transcode(data)))
        cdef EltDesc* eltDesc = &this.eltDescs[this.eltDepth]
        cdef ModelObject eltModelObject = this.getModelObject(NULL, NULL)
        cdef ModelProcessingInstruction modelPI
        cdef unicode pyTargetVal, pyDataVal
        cdef XMLCh *xmlchVal
        
        xmlchVal = <XMLCh*>target
        pyTargetVal = modelXbrl.internXMLChString(xmlchVal)
        xmlchVal = <XMLCh*>data
        pyDataVal = modelXbrl.internXMLChString(xmlchVal)
        
        modelPI = ModelProcessingInstruction(<ModelDocument>this.modelDocumentPtr, pyTargetVal, pyDataVal)
        
    void startPrefixMapping(const XMLCh* prefix, const XMLCh* uri):
        cdef ModelXbrl modelXbrl = <ModelXbrl>this.modelXbrlPtr
        #return # HF TESTING
        cdef EltDesc* eltDesc = &this.eltDescs[this.eltDepth]
        if eltDesc.prefixNsMap is NULL:
            eltDesc.prefixNsMap = new StringHashTable(103, <bool>True)
            if traceToStdout: print("+new prefix map level {}".format(this.eltDepth))
        if eltDesc.nsPrefixMap is NULL:
            eltDesc.nsPrefixMap = new StringHashTable(103, <bool>True)
        eltDesc.prefixNsMap.put(replicate(prefix), replicate(uri)) # must adopt replication of value because it may be deallocated after this call
        eltDesc.nsPrefixMap.put(replicate(uri), replicate(prefix))
        #if traceToStdout: print("+prefix level {} pfx {} ns {}".format(this.eltDepth, transcode(prefix), transcode(uri)))
        #if traceToStdout: print("+map contains key {}".format(eltDesc.prefixNsMap.containsKey(<void*>prefix)))
        #cdef StringHashTableEnumerator *prefixMapEnum = new StringHashTableEnumerator(eltDesc.prefixNsMap)
        #cdef const XMLCh *attrLn
        #while prefixMapEnum.hasMoreElements():
        #    attrLn = <XMLCh*>prefixMapEnum.nextElementKey()
        #    if eltDesc.prefixNsMap.containsKey(attrLn):
        #        if traceToStdout: print("  prefix \"{}\" {}".format(transcode(attrLn), transcode(eltDesc.prefixNsMap.get(attrLn))))
        #    else:
        #        if traceToStdout: print("  prefix  not in map \"{}\"".format(transcode(attrLn)))
        
    void endPrefixMapping(const XMLCh* prefix):
        #return # HF TESTING
        cdef EltDesc* eltDesc = &this.eltDescs[this.eltDepth]
        cdef XMLCh* _uri
        cdef bool wasInTableP = False
        cdef bool wasInTableU = False
        if eltDesc.prefixNsMap.containsKey(prefix):
            _uri = eltDesc.prefixNsMap.get(prefix)
            wasInTableP = True
            if eltDesc.nsPrefixMap.containsKey(_uri):
                eltDesc.nsPrefixMap.removeKey(_uri) # deallocates table-owned replicate prefix
                wasInTableU = True
            eltDesc.prefixNsMap.removeKey(prefix) # deallocates table owned replicate uri
        #if traceToStdout: print("-prefix level {} pfx {} wasInTableP {} asInTableU {}".format(this.eltDepth, transcode(prefix), wasInTableP, wasInTableU))
          
    bool isInheritedQName(const XMLCh* localName, const XMLCh* uri):
        return equals(uri, nsLink) and (equals(localName, lnDefinition) or equals(localName, lnUsedOn))
           
    ModelObject getModelObject(const XMLCh* localName, const XMLCh* uri):
        cdef EltDesc* eltDesc = &this.eltDescs[this.eltDepth]
        cdef ModelObject eltModelObject = None
        if isInheritedQName(localName, uri):
            eltDesc = &this.eltDescs[this.eltDepth - 1]
            if eltDesc.hashQName in (hRoleType, hArcroleType):
                eltModelObject = this.eltModelObjects[this.eltDepth-1]
        if eltModelObject is None:
            eltModelObject = this.eltModelObjects[this.eltDepth]
        return eltModelObject

    ModelObject getParentModelObject(ModelDocument modelDocument):
        cdef ModelObject eltModelObject = None
        cdef unsigned int eltDepth = this.eltDepth
        if this.isSchemaAnnotation and eltDepth == 1:
            return modelDocument.xmlRootElement
        while eltDepth > 1 and eltModelObject is None:
            eltDepth -= 1
            eltModelObject = this.eltModelObjects[this.eltDepth-1]
        return eltModelObject
    
                
    # PSVI handlers
    # these seem incompatible with use of grammar pool
    #
    #void handleAttributesPSVI2(const XMLCh* const localName, const XMLCh* const uri, PSVIAttributeList * psviAttributes):
    #    cdef ModelObject eltModelObject = this.getModelObject(localName, uri)
    #    cdef XMLSize_t l = psviAttributes.getLength()
    #    cdef XMLSize_t i
    #    cdef PSVIItem *pi
    #    if eltModelObject is not None and l > 0:
    #        for i in range(l):
    #            pi = psviAttributes.getAttributePSVIAtIndex(i)
    #            eltModelObject.setValue(psviAttributes.getAttributeNamespaceAtIndex(i), 
    #                                    psviAttributes.getAttributeNameAtIndex(i), 
    #                                    <PSVIItem*>pi, this.PSVIValue(pi), SPECIFIED_ATTRIBUTE)
        
    #void handleElementPSVI2(const XMLCh* const localName, const XMLCh* const uri, PSVIElement * elementInfo):
    #    cdef ModelObject eltModelObject = this.getModelObject(localName, uri)
    #    if eltModelObject is not None:
    #        eltModelObject.setValue(uri, localName, <PSVIItem*>ei, this.PSVIValue(ei), OBJECT_VALUE)

    #void handlePartialElementPSVI2(const XMLCh* const localName, const XMLCh* const uri, PSVIElement * elementInfo):
    #    return
            
    void handlePyError(object pyError):
        cdef object modelXbrl = <object>this.modelXbrlPtr
        modelXbrl.log(pyError.level, "xmlSchema:xerces",
                      pyError.message,
                      sourceFileLine=(pyError.file, pyError.line, pyError.column),
                      element=pyError.element)
        if traceToStdout: print("xmlSchema:xerces {} {} {}".format(pyError.level, pyError.file, pyError.message))

    object pyValue(XSTypeDefinition *typeDef, const XMLCh* uri, const XMLCh* localname, const XMLCh* xmlchText, bool isAttr): # might raise ValueError
        cdef ModelXbrl modelXbrl = <ModelXbrl>this.modelXbrlPtr
        cdef XSSimpleTypeDefinition *simpleTypeDef
        cdef XSComplexTypeDefinition *complexTypeDef
        cdef XSSimpleTypeDefinition *unionSimpleTypeDef
        cdef XSTypeDefinition *baseTypeDef
        cdef XSTypeDefinition *primitiveType
        cdef XSSimpleTypeDefinitionList *unionTypesList
        cdef list dataTypes
        cdef DataType dt = dt_string
        cdef const XMLCh *typeName = fgDT_STRING
        cdef const XMLCh *facetVal
        cdef bool isWsCollapse = True
        cdef bool isWsReplace = False
        cdef bool isList = False
        cdef XMLCh *xmlchVal
        cdef XMLCh *xmlchVal2
        cdef XMLCh *xmlchVal3
        cdef XMLChVector *xmlchVector
        cdef char *charVal
        cdef unicode strVal
        cdef object pyVal = None
        cdef list pyList = None
        cdef int i, j
        cdef XMLSize_t k, vSize
        cdef bool hasLexicalError = False
        cdef bool isMixed = False
        
        dataTypes = list()
        if typeDef is not NULL:
            if typeDef.getTypeCategory() == SIMPLE_TYPE:
                simpleTypeDef = <XSSimpleTypeDefinition *>typeDef
            else:
                complexTypeDef = <XSComplexTypeDefinition *>typeDef
                simpleTypeDef = complexTypeDef.getSimpleType()
                if complexTypeDef.getContentType() == CONTENTTYPE_MIXED:
                    isMixed = True
            if simpleTypeDef is not NULL:
                if simpleTypeDef.getVariety() == VARIETY_LIST:
                    isList = True
                    if traceToStdout: print("is list type")
                if typeDef.derivedFrom(nsXbrli, lnDateUnion):
                    if equals(uri, nsXbrli) and (equals(localname, lnEndDate) or equals(localname, lnInstant)):
                        dataTypes.append(dt_xbrliEndDate)
                    else:
                        dataTypes.append(dt_xbrliDateunion) #dateunion special type
                    if traceToStdout: print("dateunion type {}".format(dataTypes))
                elif simpleTypeDef.getVariety() == VARIETY_UNION:
                    unionTypesList = simpleTypeDef.getMemberTypes()
                    for k in range(unionTypesList.size()):
                        typeName = xmlSchemaType(unionTypesList.elementAt(k))
                        if typeName is not NULL:
                            if traceToStdout: print("   union type {}".format(transcode(typeName)))
                            dataTypes.append(getDataType(typeName))
                    if traceToStdout: print("xmlunion type {}".format(dataTypes))
                else:
                    typeName = xmlSchemaType(simpleTypeDef)
                    if typeName is not NULL:
                        if traceToStdout: print("simpleType type {}".format(getDataType(typeName)))
                        dataTypes.append(getDataType(typeName))
                xmlchVal = NULL
                if simpleTypeDef.isDefinedFacet(FACET_WHITESPACE):
                    facetVal = simpleTypeDef.getLexicalFacetValue(FACET_WHITESPACE)
                    isWsCollapse = equals(facetVal,fgWS_COLLAPSE)
                    isWsReplace = equals(facetVal,fgWS_REPLACE)
            elif isMixed: # generally for HTML and text elements
                dataTypes.append(dt_string)
            else:
                if traceToStdout: print("no simple type")
        elif equals(uri, nsXml):
            if equals(localname, lnLang):
                isWsCollapse = True
                dataTypes.append(dt_language)
            elif equals(localname, lnBase):
                isWsCollapse = True
                dataTypes.append(dt_anyURI)
        elif equals(uri, nsXbrldi) and equals(localname, lnExplicitMember):
            isWsCollapse = True # treat undeclared dimensions as qname
            dataTypes.append(dt_QName)
        else: # no declaration, treat as string
            dataTypes.append(dt_string) 
            isWsCollapse = False # prevent html from removing inter-word inter-element whitespace
        if not dataTypes and isMixed: # mixed or anyType
            if traceToStdout: print("no type {} typename {} mixed {}".format(transcode(localname), transcode(typeName), isMixed))
            dataTypes.append(dt_string)

        xmlchVal = <XMLCh*>xmlchText
        if isList:
            pyList = list()
            xmlchVector = tokenizeString(<XMLCh*>xmlchText)
            vSize = xmlchVector.size()
        else:
            vSize = 1
        for k in range(vSize):
            if isList:
                xmlchVal = xmlchVector.elementAt(k)
            else:
                xmlchVal = <XMLCh*>xmlchText
            if isWsCollapse:
                collapseWS(xmlchVal) # assumed in temporary buffer
            elif isWsReplace:
                replaceWS(xmlchVal) # assumed in temporary buffer
            for dt in dataTypes:
                if dt in (dt_string, dt_normalizedString, dt_language, dt_token, dt_NMTOKEN, dt_Name, dt_NCName, dt_IDREF, dt_ENTITY, dt_ID):
                    pyVal = modelXbrl.internXMLChString(xmlchVal)
                elif dt == dt_anyURI:
                    pyVal = AnyURI(UrlUtil.anyUriQuoteForPSVI(modelXbrl.internXMLChString(xmlchVal)))
                elif dt == dt_boolean:
                    if equals(xmlchVal, xmlchTrue) or equals(xmlchVal, xmlchOne):
                        pyVal = True
                    elif equals(xmlchVal, xmlchFalse) or equals(xmlchVal, xmlchZero):
                        pyVal = False
                    else:
                        pyVal = None
                elif dt == dt_QName:
                    xmlchVal2 = replicate(xmlchVal) # to extract prefix
                    i = indexOf(xmlchVal, <XMLCh>chColon)
                    if i == -1: # no prefix
                        xmlchVal2[0] = chNull 
                    else:
                        xmlchVal2[i] = chNull # terminate string on prefix
                    xmlchVal3 = this.prefixNamespace(xmlchVal2)
                    if traceToStdout: print("pyValue QName value {} prefix {} ns {}".format(transcode(xmlchVal), transcode(xmlchVal2), transcode(xmlchVal3)))
                    pyVal = QName(modelXbrl.internXMLChString(xmlchVal3), modelXbrl.internXMLChString(xmlchVal2), modelXbrl.internXMLChString(xmlchVal + i + 1))
                    release(&xmlchVal2)
                elif dt == dt_MAXCOUNT: # unrecognized primitive data type
                    pyVal = None
                else: # these operations require a python string
                    charVal = transcode(xmlchVal)
                    strVal = charVal
                    try:
                        if dt == dt_decimal:
                            if pValidateDecimalPattern.match(strVal) is None:
                                raise ValueError(uLexicalPatternMismatch)
                            pyVal = Decimal(strVal)
                        elif dt in (dt_float, dt_double):
                            if pValidateFloatPattern.match(strVal) is None:
                                raise ValueError(uLexicalPatternMismatch)
                            pyVal = float(strVal)
                        elif dt in (dt_integer, dt_nonPositiveInteger, dt_negativeInteger, dt_long, dt_int, dt_short, dt_byte, dt_nonNegativeInteger, dt_unsignedLong, dt_unsignedInt, dt_unsignedShort, dt_unsignedByte, dt_positiveInteger):
                            if pValidateIntegerPattern.match(strVal) is None:
                                raise ValueError(uLexicalPatternMismatch)
                            pyVal = int(strVal)
                        elif dt == dt_xbrliDateunion:
                            pyVal = ModelValue.dateTime(strVal, type=ModelValue.DATEUNION)
                        elif dt == dt_xbrliEndDate:
                            pyVal = ModelValue.dateTime(strVal, type=ModelValue.DATEUNION, addOneDay=True)
                        elif dt == dt_dateTime:
                            pyVal = ModelValue.dateTime(strVal, type=ModelValue.DATETIME)
                        elif dt == dt_date:
                            pyVal = ModelValue.dateTime(strVal, type=ModelValue.DATE)
                        elif dt == dt_time:
                            pyVal = ModelValue.time(strVal)
                        elif dt == dt_duration:
                            pyVal = ModelValue.isoDuration(strVal)
                        elif dt == dt_gYearMonth:
                            pyVal = ModelValue.gYearMonth(strVal)
                        elif dt == dt_gYear:
                            pyVal = ModelValue.gYear(strVal)
                        elif dt == dt_gMonthDay:
                            pyVal = ModelValue.gMonthDay(strVal)
                        elif dt == dt_gDay:
                            pyVal = ModelValue.gDay(strVal)
                        elif dt == dt_gMonth:
                            pyVal = ModelValue.gMonth(strVal)
                        elif dt in (dt_NOTATION, dt_NMTOKENS, dt_IDREFS, dt_hexBinary, dt_base64Binary, dt_ENTITIES):
                            pyVal = strVal # don't split list at this time
                        else:
                            pyVal = None
                    except (ValueError, InvalidOperation) as err:
                        hasLexicalError = True
                        pyVal = None
                    release(&charVal)
                if not hasLexicalError: # if lexical error, continue to try more union data types
                    break
            if isList:
                pyList.append(pyVal)
        if isList:
            del xmlchVector
            pyVal = pyList
        #if traceToStdout: print("pi ln {} dt  {} {} pyVal {}".format(transcode(localname),transcode(typeName),dt,pyVal))
        return pyVal
    
    void setObjectAttributes(EltDesc* eltDesc, ModelObject eltModelObject, const Attributes& attrs):
        cdef ModelXbrl modelXbrl
        cdef XMLSize_t attrsLen = attrs.getLength()
        cdef XMLSize_t i
        cdef int attrsIndex
        cdef XSTypeDefinition *typeDef = NULL
        cdef XSComplexTypeDefinition *complexTypeDef
        cdef XSSimpleTypeDefinition *simpleTypeDef
        cdef XSAttributeUseList *attributeUseList
        cdef XSAttributeUse *attributeUse
        cdef XSAttributeDeclaration *attrDecl
        cdef const XMLCh *attrNS
        cdef const XMLCh *attrLn
        cdef const XMLCh *attrText
        cdef const XMLCh *vNS
        cdef const XMLCh *vLn
        cdef const XMLCh *defaultAttrText
        cdef const XMLCh **nsmapNs
        cdef VALUE_CONSTRAINT constraintType
        cdef StringHashTableEnumerator *prefixMapEnum 
        cdef int isAttribute
        cdef bool attributeIsSet[256] # attribute has been set
        assert attrsLen < 256, "setObjectAttributes over 256 attributes, excess will be unvalidated" 
        if traceToStdout: print("set attrs {} len {}".format(transcode(eltDesc.xmlchQName), attrsLen))
        modelXbrl = <ModelXbrl>this.modelXbrlPtr
        for i in range(attrsLen):
            attributeIsSet[i] = False
        if eltDesc is not NULL and eltDesc.eltDecl is not NULL:
            if traceToStdout: print("set attributes has elt decl")
            typeDef = eltDesc.eltDecl.getTypeDefinition()
            if traceToStdout: print("has type decl {}".format(typeDef.getTypeCategory() if typeDef is not NULL else "(none)"))
        else:
            if traceToStdout: print("no type decl for attributes")
        if typeDef is not NULL and typeDef.getTypeCategory() == COMPLEX_TYPE:
            complexTypeDef = <XSComplexTypeDefinition *>typeDef
            attributeUseList = complexTypeDef.getAttributeUses()
            if traceToStdout: print("complex type {} attr use list {}".format(complexTypeDef.getContentType(), attributeUseList is not NULL))
            if attributeUseList is not NULL:
                for i in range(attributeUseList.size()):
                    attributeUse = attributeUseList.elementAt(i)
                    attrDecl = attributeUse.getAttrDeclaration()
                    constraintType = attributeUse.getConstraintType()
                    attrNS = attrDecl.getNamespace()
                    attrLn = attrDecl.getName()
                    simpleTypeDef = attrDecl.getTypeDefinition()
                    attrsIndex = attrs.getIndex(attrNS, attrLn)
                    attrText = NULL
                    if attrsIndex >= 0: # this attribute is reported
                        attributeIsSet[attrsIndex] = True
                        attrText = attrs.getValue(attrsIndex)
                        isAttribute = SPECIFIED_ATTRIBUTE
                    defaultAttrText = NULL
                    if constraintType == VALUE_CONSTRAINT_DEFAULT or constraintType == VALUE_CONSTRAINT_FIXED:
                        defaultAttrText = attributeUse.getConstraintValue()
                        if attrText is NULL:
                            attrText = defaultAttrText
                            isAttribute = DEFAULTED_ATTRIBUTE
                        elif equals(attrText, defaultAttrText):
                            isAttribute = DEFAULTED_ATTRIBUTE
                    if attrText is not NULL:
                        if traceToStdout: print("  attruse ndx {} ns {} ln {} val {} rpt {} def {}".format(attrsIndex, transcode(attrNS), transcode(attrLn), transcode(attrText), isAttribute, "NULL" if defaultAttrText is NULL else transcode(defaultAttrText)))
                        eltModelObject.setValue(attrNS, attrLn, this.pyValue(simpleTypeDef, attrNS, attrLn, attrText, True), isAttribute)
        # attributes not set above
        for i in range(attrsLen):
            if not attributeIsSet[i]:
                attrNS = attrs.getURI(i)
                attrLn = attrs.getLocalName(i)
                attrText = attrs.getValue(i)
                if traceToStdout: print("  attrs i not set by attr use list {} ns {} ln {} val {}".format(i, transcode(attrNS), transcode(attrLn), transcode(attrText)))
                if ((attrNS[0] == chNull and equals(attrLn, lnXmlns) or
                    equals(attrNS, nsXmlns) or
                    (equals(attrNS, nsXsi) and equals(attrLn, lnSchemaLocation)))):
                     continue
                # is there a global definition of this attribute?
                attrDecl = modelXbrl.xsModel.getAttributeDeclaration(attrLn, attrNS)
                if attrDecl is not NULL:
                    typeDef = attrDecl.getTypeDefinition()
                    vNS = attrNS # have a type, use attrNS and Ln to get right type
                    vLn = attrLn
                elif eltDesc.hashQName == hDimension and attrNS[0] == chNull and equals(attrLn, lnDimension):
                    typeDev = NULL # for some reason dimension is not loaded to schema
                    vNS = nsXbrldi # constants to force conversion to a QName value despite lack of typeDef
                    vLn = lnExplicitMember
                else:
                    typeDef = NULL
                    vNS = attrNS # just default to string value if not special cased in pyValue
                    vLn = attrLn
                if traceToStdout: print("  attruse ndx {} ns {} ln {} val {} type {}".format(i, transcode(attrNS), transcode(attrLn), transcode(attrText),
                            "no type" if typeDef is NULL else transcode(typeDef.getName())))
                eltModelObject.setValue(attrNS, attrLn, this.pyValue(typeDef, vNS, vLn, attrText, True), SPECIFIED_ATTRIBUTE)
                attributeIsSet[i] = True
        # set any nsmap entries
        eltDesc = eltDesc - 1 # prior eltDesc has prefixes for this level
        if traceToStdout: print("before prefix enum {}".format(eltDesc.prefixNsMap is not NULL))
        if eltDesc.prefixNsMap is not NULL:
            prefixMapEnum = new StringHashTableEnumerator(eltDesc.prefixNsMap)
            while prefixMapEnum.hasMoreElements():
                attrLn = <XMLCh*>prefixMapEnum.nextElementKey()
                if not equals(attrLn, lnXmlns) and eltDesc.prefixNsMap.containsKey(attrLn):
                    attrNS = eltDesc.prefixNsMap.get(attrLn) # namespaceURI
                    if traceToStdout: print("  prefix \"{}\" {}".format(transcode(attrLn), transcode(attrNS)))
                    eltModelObject.setValue(nNsmap, attrLn, this.pyValue(NULL, NULL, NULL, attrNS, True), OBJECT_PROPERTY)
    
        '''
    object PSVIValue(PSVIItem* pi): # might raise ValueError
        cdef ModelXbrl modelXbrl = <ModelXbrl>this.modelXbrlPtr
        cdef EltDesc* eltDesc
        cdef XSTypeDefinition *typeDef = pi.getTypeDefinition()
        cdef XSSimpleTypeDefinition *simpleTypeDef = pi.getMemberTypeDefinition()
        cdef XSTypeDefinition *baseTypeDef
        cdef XSTypeDefinition *primitiveType
        cdef DataType dt
        cdef const XMLCh *typeName
        cdef XMLCh *xmlchVal
        cdef XMLCh *xmlchVal2
        cdef XMLCh *xmlchVal3
        cdef char *charVal
        cdef unicode strVal
        cdef object pyVal
        cdef int i, j
        #if traceToStdout: print("PSVIValue1 typeDef cat {}".format("NULL" if typeDef==NULL else typeDef.getTypeCategory()))
        if simpleTypeDef is NULL:
            if typeDef.getTypeCategory() == SIMPLE_TYPE:
                simpleTypeDef = <XSSimpleTypeDefinition *>typeDef
            else:
                simpleTypeDef = (<XSComplexTypeDefinition *>typeDef).getSimpleType()
        if simpleTypeDef is not NULL:
            baseTypeDef = simpleTypeDef
            primitiveType = simpleTypeDef.getPrimitiveType()
            typeName = primitiveType.getName()
            dt = getDataType(typeName)
            xmlchVal = <XMLCh*>pi.getSchemaNormalizedValue()
            if dt in (dt_string, dt_normalizedString, dt_language, dt_token, dt_NMTOKEN, dt_Name, dt_NCName, dt_IDREF, dt_ENTITY, dt_ID):
                pyVal = modelXbrl.internXMLChString(xmlchVal)
            elif dt == dt_anyURI:
                pyVal = AnyURI(UrlUtil.anyUriQuoteForPSVI(modelXbrl.internXMLChString(xmlchVal)))
            elif dt == dt_boolean:
                if equals(xmlchVal, xmlchTrue) or equals(xmlchVal, xmlchOne):
                    pyVal = True
                elif equals(xmlchVal, xmlchTrue) or equals(xmlchVal, xmlchOne):
                    pyVal = False
                else:
                    pyVal = None
            elif dt == dt_QName:
                xmlchVal2 = replicate(xmlchVal) # to extract prefix
                i = indexOf(xmlchVal, <XMLCh>chColon)
                if i == -1: # no prefix
                    xmlchVal2[0] = chNull 
                else:
                    xmlchVal2[i] = chNull # terminate string on prefix
                xmlchVal3 = nsNoNamespace
                for j in range(this.eltDepth, -1, -1):
                    eltDesc = &this.eltDescs[j]
                    if eltDesc.prefixNsMap is not NULL and eltDesc.prefixNsMap.containsKey(xmlchVal2):
                        xmlchVal3 = eltDesc.prefixNsMap.get(xmlchVal2)
                        break
                pyVal = QName(modelXbrl.internXMLChString(xmlchVal3), modelXbrl.internXMLChString(xmlchVal2), modelXbrl.internXMLChString(xmlchVal + i + 1))
                release(&xmlchVal2)
            elif dt == dt_MAXCOUNT: # unrecognized primitive data type
                pyVal = None
            else: # these operations require a python string
                charVal = transcode(xmlchVal)
                strVal = charVal
                if dt == dt_decimal:
                    pyVal = Decimal(strVal)
                elif dt in (dt_float, dt_double):
                    pyVal = float(strVal)
                elif dt in (dt_integer, dt_nonPositiveInteger, dt_negativeInteger, dt_long, dt_int, dt_short, dt_byte, dt_nonNegativeInteger, dt_unsignedLong, dt_unsignedInt, dt_unsignedShort, dt_unsignedByte, dt_positiveInteger):
                    pyVal = int(strVal)
                elif dt == dt_dateTime:
                    if typeDef.derivedFrom(nsXbrli, lnDateUnion): # it's a dateTime with a date-only value
                        pyVal = ModelValue.dateTime(strVal, type=ModelValue.DATEUNION)
                    else: # it's just a dateTime
                        pyVal = ModelValue.dateTime(strVal, type=ModelValue.DATETIME)
                elif dt == dt_date:
                    if typeDef.derivedFrom(nsXbrli, lnDateUnion): # it's a dateTime with a date-only value
                        pyVal = ModelValue.dateTime(strVal, type=ModelValue.DATEUNION)
                    else: # it's just a date
                        pyVal = ModelValue.dateTime(strVal, type=ModelValue.DATE)
                elif dt == dt_time:
                    pyVal = ModelValue.time(strVal)
                elif dt == dt_duration:
                    pyVal = ModelValue.isoDuration(strVal)
                elif dt == dt_gYearMonth:
                    pyVal = ModelValue.gMonthDay(strVal)
                elif dt == dt_gYear:
                    pyVal = ModelValue.gYear(strVal)
                elif dt == dt_gMonthDay:
                    pyVal = ModelValue.time(strVal)
                elif dt == dt_gDay:
                    pyVal = ModelValue.gDay(strVal)
                elif dt == dt_gMonth:
                    pyVal = ModelValue.gMonth(strVal)
                elif dt in (dt_NOTATION, dt_NMTOKENS, dt_IDREFS, dt_hexBinary, dt_base64Binary, dt_ENTITIES):
                    pyVal = strVal # don't split list at this time
                else:
                    pyVal = None
                release(&charVal)
        else:
            pyVal = None
        #if traceToStdout: print("pi pyVal {}".format(pyVal))
        return pyVal
        '''
                
cdef class ModelHref:
    cdef public ModelDocument modelDocument
    cdef readonly unicode baseForElement
    cdef readonly hash_t hrefHash
    cdef readonly bool inDTS
    cdef readonly unicode urlWithoutFragment

    def __init__(self, unicode urlWithoutFragment, unicode baseForElement, bool inDTS):
        self.baseForElement = baseForElement
        self.inDTS = inDTS
        self.urlWithoutFragment = urlWithoutFragment
        self.hrefHash = PyObject_Hash( (urlWithoutFragment, baseForElement) )
    def __hash__(self):
        return self.hrefHash
    def __repr__(self):
        return self.__str__() 
    def __str__(self):
        return "{}#{}".format(self.urlWithoutFragment, self.baseForElement)
    def __richcmp__(self, other, op):
        if op == 0: # lt
            return ((self.urlWithoutFragment < other.urlWithoutFragment) or \
                    (self.urlWithoutFragment == other.urlWithoutFragment and self.baseForElement < other.baseForElement))
        elif op == 1: # le
            return ((self.urlWithoutFragment < other.urlWithoutFragment) or \
                    (self.urlWithoutFragment == other.urlWithoutFragment and self.baseForElement <= other.baseForElement))
        elif op == 2: # eq
            return (self.urlWithoutFragment == other.urlWithoutFragment and self.baseForElement == other.baseForElement)
        elif op == 3: # ne
            return not self.__eq__(other)
        elif op == 4: # gt
            return ((self.urlWithoutFragment > other.urlWithoutFragment) or \
                    (self.urlWithoutFragment == other.urlWithoutFragment and self.baseForElement > other.baseForElement))
        elif op == 5: # ge
            return ((self.urlWithoutFragment > other.urlWithoutFragment) or \
                    (self.urlWithoutFragment == other.urlWithoutFragment and self.baseForElement >= other.baseForElement))
        else: # no such op
            return False # bad operation