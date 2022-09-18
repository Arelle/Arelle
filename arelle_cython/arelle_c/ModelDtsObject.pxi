from arelle_c.xerces_ctypes cimport uint64_t, XMLSize_t
from arelle_c.xerces_framework cimport XSElementDeclaration, XSTypeDefinition, SCOPE, VALUE_CONSTRAINT, \
    FACET_LENGTH, FACET_MINLENGTH, FACET_MAXLENGTH, FACET_PATTERN, FACET_WHITESPACE, FACET_MAXINCLUSIVE, \
    FACET_MAXEXCLUSIVE, FACET_MINEXCLUSIVE, FACET_MININCLUSIVE, FACET_TOTALDIGITS, FACET_FRACTIONDIGITS, \
    FACET_ENUMERATION, TYPE_CATEGORY, COMPLEX_TYPE, SIMPLE_TYPE, VARIETY_UNION, XSSimpleTypeDefinition, XSComplexTypeDefinition, \
    FACET, XSFacetList, XSFacet, XSAnnotation, PSVIItem, StringList, XSSimpleTypeDefinitionList, \
    XSParticle
from arelle_c.xerces_util cimport transcode, stringLen
from arelle.ModelDocument import Type
from arelle.XbrlConst import dimensionArcroles, formulaArcroles, tableRenderingArcroles, qnLinkLoc,\
    isStandardArcInExtLinkElement, qnGenArc
from arelle.XbrlUtil import sEqual
import decimal, os
from collections import defaultdict
from gettext import gettext as _    

cdef int NUM_FACETS = 12
cdef FACET facetXercesNames[12]
facetXercesNames[:] = [FACET_LENGTH, FACET_MINLENGTH, FACET_MAXLENGTH, FACET_PATTERN, FACET_WHITESPACE, FACET_MAXINCLUSIVE, 
                       FACET_MAXEXCLUSIVE, FACET_MINEXCLUSIVE, FACET_MININCLUSIVE, FACET_TOTALDIGITS, FACET_FRACTIONDIGITS, 
                       FACET_ENUMERATION]
facetPyNames = ["length", "minLength", "maxLength", "pattern", "whiteSpace", "maxInclusive",
                "maxExclusive", "minExclusive", "minInclusive", "totalDigits", "fractionDigits", "enumeration"]

from arelle import ModelDtsObject, XbrlConst

cdef class ModelRoleType(ModelObject):
    cpdef readonly bool isArcrole  # true for roleType, false for arcroleType
    cpdef readonly AnyURI roleURI
    cpdef readonly AnyURI arcroleURI
    cpdef readonly unicode cyclesAllowed
    cpdef readonly unicode definition
    cpdef readonly set usedOns
    
    def __init__(self, ModelDocument modelDocument, bool isArcrole):
        super().__init__(modelDocument)
        self.isArcrole = isArcrole
        self.roleURI = self.arcroleURI = None
        self.cyclesAllowed = self.definition = None
        self.usedOns = set()
        
    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        #if traceToStdout: print("mdlRlTy setV ln {} isAttr {} val {}".format(transcode(localName), isAttribute, psviValue))
        if isAttribute:
            if equals(localName, lnRoleURI):
                self.roleURI = pyValue
                return
            elif equals(localName, lnArcroleURI):
                self.arcroleURI = pyValue
                return
            elif equals(localName, lnCyclesAllowed):
                self.cyclesAllowed = pyValue
                return
        else:
            if equals(localName, lnDefinition):
                self.definition = pyValue
                return
            elif equals(localName, lnUsedOn) and isinstance(pyValue, QName): # may be spurious whitespace, etc
                if pyValue not in self.usedOns:
                    self.usedOns.add(pyValue)
                elif self.isArcrole:
                    self.modelXbrl.error("xbrl.5.1.4:usedOnDuplicate",
                        _("arcroleType %(roleURI)s usedOn %(value)s on has s-equal duplicate"),
                        modelObject=self, roleURI=self.arcroleURI, value=pyValue)
                else:
                    self.modelXbrl.error("xbrl.5.1.3:usedOnDuplicate",
                        _("roleType %(roleURI)s usedOn %(value)s on has s-equal duplicate"),
                        modelObject=self, roleURI=self.roleURI, value=pyValue)
                return
        ModelObject.setValue(self, namespace, localName, pyValue, isAttribute)
        
    cdef setup(self): # element has been set up
        cdef modelXbrl = self.modelDocument.modelXbrl
        if traceToStdout: print("setup roleType {} {} {} {}".format(self.qname, self.roleURI, self.arcroleURI, self.modelDocument.basename))
        if self.isArcrole:
            modelXbrl.arcroleTypes[self.arcroleURI].append(self)
        else:
            modelXbrl.roleTypes[self.roleURI].append(self)
                    
    def iterAttrs(self):
        if self.roleURI is not None:
            yield (uRoleURI, self.roleURI)
        if self.arcroleURI is not None:
            yield (uArcroleURI, self.arcroleURI)
        if self.cyclesAllowed is not None:
            yield (uCyclesAllowed, self.cyclesAllowed)
        ModelObject.iterAttrs()
        
    def isEqualTo(self, otherRoleType):
        if not (self.isArcrole == otherRoleType.isArcrole and 
                self.definition == otherRoleType.definition and
                not (self.usedOns ^ otherRoleType.usedOns)):
            return False             
        if self.isArcrole:
            return self.arcroleURI == otherRoleType.arcroleURI and self.cyclesAllowed == otherRoleType.cyclesAllowed
        else:
            return self.roleURI == otherRoleType.roleURI
        
    @property
    def tableCode(self):
        """ table code from structural model for presentable table by ELR"""
        if self.isArcrole:
            return None
        if "tableCode" not in self.attrs:
            from arelle import TableStructure
            TableStructure.evaluateRoleTypesTableCodes(self.modelDocument.modelXbrl)
        return self.get("tableCode")
    
    @property
    def propertyView(self):
        if self.isArcrole:
            return (("arcrole Uri", self.arcroleURI),
                    ("definition", self.definition),
                    ("used on", self.usedOns),
                    ("defined in", self.modelDocument.url))
        else:
            return (("role Uri", self.roleURI),
                    ("definition", self.definition),
                    ("used on", self.usedOns),
                    ("defined in", self.modelDocument.url))
        
    def __repr__(self):
        return ("{}[{}, uri: {}, definition: {}, usedOn: {}, file: {} line {}])"
                .format('modelArcroleType' if self.isArcrole else 'modelRoleType', 
                        self.objectIndex, 
                        self.arcroleURI if self.isArcrole else self.roleURI,
                        self.definition,
                        self.usedOns, 
                        self.modelDocument.basename, self.sourceline))

    @property
    def viewConcept(self):  # concept trees view roles as themselves
        return self 

cdef class ModelRoleRef(ModelXlinkSimple):
    cpdef readonly bool isArcrole  # true for roleType, false for arcroleType
    cpdef readonly AnyURI roleURI
    cpdef readonly AnyURI arcroleURI

    def __init__(self, ModelDocument modelDocument, bool isArcrole):
        super().__init__(modelDocument)
        self.isArcrole = isArcrole
        self.roleURI = self.arcroleURI = None
        
    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        #if traceToStdout: print("mdlRlTy setV ln {} isAttr {} val {}".format(transcode(localName), isAttribute, psviValue))
        if isAttribute:
            if equals(localName, lnRoleURI):
                self.roleURI = pyValue
                return
            elif equals(localName, lnArcroleURI):
                self.arcroleURI = pyValue
                if not isAbsoluteUrl(pyValue):
                    if isStandardArcInExtLinkElement(self):
                        self.modelXbrl.error("xbrl.3.5.2.5:arcroleNotAbsolute",
                            _("Arcrole %(arcrole)s is not absolute"),
                            modelObject=self, element=self.qname, arcrole=pyValue)
                    elif self.isOrSubstitutesForQName(qnGenArc):
                        self.modelXbrl.error("xbrlgene:nonAbsoluteArcRoleURI",
                            _("Generic arc arcrole %(arcrole)s is not absolute"),
                            modelObject=self, element=self.qname, arcrole=pyValue)
                return
        ModelXlinkSimple.setValue(self, namespace, localName, pyValue, isAttribute)
        
    cdef setup(self): # element has been set up
        if self.modelDocument.linkbaseRoleRefs is not None:
            if self.isArcrole:
                if self.arcroleURI not in self.modelDocument.linkbaseRoleRefs:
                    self.modelDocument.linkbaseRoleRefs[self.arcroleURI] = self
                else:
                    self.modelXbrl.error("xbrl.3.5.2.5.5:arcroleRefDuplicate",
                        _("arcroleRef is duplicated for %(refURI)s"),
                        modelObject=self, refURI=self.arcroleURI)
            else:
                if self.roleURI not in self.modelDocument.linkbaseRoleRefs:
                    self.modelDocument.linkbaseRoleRefs[self.roleURI] = self
                else:
                    self.modelXbrl.error("xbrl.3.5.2.4.5:roleRefDuplicate",
                        _("roleRef is duplicated for %(refURI)s"),
                        modelObject=self, refURI=self.roleURI)
        ModelXlinkSimple.setup(self)
           
    def iterAttrs(self):
        if self.roleURI is not None:
            yield (uRoleURI, self.roleURI)
        if self.arcroleURI is not None:
            yield (uArcroleURI, self.arcroleURI)
        ModelXlinkSimple.iterAttrs()

cdef class ModelXlinkObject(ModelObject): # extended link element
    cdef readonly unicode xlinkType
    cdef readonly AnyURI role
    cdef readonly unicode title
    cdef readonly unicode show
    cdef readonly unicode actuate

    def __init__(self, ModelDocument modelDocument):
        super().__init__(modelDocument)
        self.role = None
        self.xlinkType = self.title = self.show = self.actuate = None

    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        if isAttribute:
            if equals(namespace, nsXlink):
                if equals(localName, lnType):
                    self.xlinkType = pyValue
                    return
                elif equals(localName, lnRole):
                    self.role = pyValue
                    return
                elif equals(localName, lnTitle):
                    self.title = pyValue
                    return
                elif equals(localName, lnShow):
                    self.show = pyValue
                    return
                elif equals(localName, lnActuate):
                    self.actuate = pyValue
                    return
        ModelObject.setValue(self, namespace, localName, pyValue, isAttribute)

    def iterAttrs(self):
        if self.xlinkType is not None:
            yield (uClarkXlinkType, self.xlinkType)
        if self.role is not None:
            yield (uClarkXlinkRole, self.role)
        if self.title is not None:
            yield (uClarkXlinkTitle, self.title)
        if self.show is not None:
            yield (uClarkXlinkShow, self.show)
        if self.actuate is not None:
            yield (uClarkXlinkActuate, self.actuate)
        ModelObject.iterAttrs()

# xlink simple element
# includes link:schemaRef, linkbaseRef
cdef class ModelXlinkSimple(ModelXlinkObject): # simple link element
    cdef readonly AnyURI href
    cdef readonly ModelHref modelHref
    cdef readonly AnyURI arcrole

    def __init__(self, ModelDocument modelDocument):
        super().__init__(modelDocument)
        self.arcrole = self.href = None
        self.modelHref = None

    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        #if traceToStdout: print("mdlRlTy setV ln {} isAttr {} val {}".format(transcode(localName), isAttribute, psviValue))
        if isAttribute:
            if equals(namespace, nsXlink): 
                if equals(localName, lnHref):
                    self.href = pyValue
                    return
                elif equals(localName, lnArcrole):
                    self.arcrole = pyValue
                    return
        ModelXlinkObject.setValue(self, namespace, localName, pyValue, isAttribute)

    cdef setup(self): # element has been set up
        ModelXlinkObject.setup(self)
        if self.href is not None:
            # xlink simple elements (linkbaseRef, schemaRef) are discovered (in-DTS)
            if traceToStdout: print("setup ModelXlinkSimple {} base {}".format(self.href.urlWithoutFragment, self.baseForElement()))
            self.modelHref = self.modelDocument.modelHref(str(self.href.urlWithoutFragment), self.baseForElement(), True)

    def iterAttrs(self):
        if self.href is not None:
            yield (uClarkXlinkHref, self.href)
        if self.arcrole is not None:
            yield (uClarkXlinkArcrole, self.arcrole)
        ModelXlinkObject.iterAttrs()

    def dereference(self):
        """(ModelObject) -- Resolve linkbaseRef, schemaRef href if resource is a loc with href document and id modelHref """
        if self.modelHref is None or self.modelHref.modelDocument is None:
            return None
        return self.modelHref.modelDocument.fragmentObject(self.href.fragment)
                
cdef class ModelXlinkExtended(ModelXlinkObject): # extended link element
    cdef readonly AnyURI baseSetArcrole
    cdef readonly QName baseSetArcQName
    cdef readonly object labeledResources
    cdef readonly set arcroleQNames
    
    def __init__(self, ModelDocument modelDocument):
        super().__init__(modelDocument)
        self.baseSetArcrole = None
        self.baseSetArcQName = None
        self.labeledResources = defaultdict(list)
        self.arcroleQNames = set()
        
    @property
    def baseSet(self):
        # parameters of base set needed for relationship set construction
        return (self.baseSetArcrole, self.role, self.qname, self.baseSetArcQName)
        
    cdef setup(self): # element has been set up
        #if traceToStdout: print("setup baseset {}".format(self.qname))
        cdef list baseSetKeys = list()
        cdef AnyURI _arcrole
        cdef QName _arcQName
        cdef bool dimensionArcFound = False
        cdef bool formulaArcFound = False
        cdef bool tableRenderingArcFound = False
        cdef tuple arcroleQNameHash
        if self.modelDocument.type == Type.INLINEXBRL:
            return # setup performed when inline is compiled by ModelDocument
        if self.modelDocument.type == Type.INSTANCE:
            baseSetKeys.append( (uXbrlFootnotes,None,None,None) )
            baseSetKeys.append( (uXbrlFootnotes,self.role,None,None) )
        for _arcrole, _arcQName in self.arcroleQNames:
            baseSetKeys.append( (_arcrole, self.role, self.qname, _arcQName) )
            baseSetKeys.append( (_arcrole, self.role, None, None) )
            baseSetKeys.append( (_arcrole, None, None, None) )
            if not dimensionArcFound and _arcrole in dimensionArcroles:       
                baseSetKeys.append( (uXbrlDimensions, None, None, None) ) 
                baseSetKeys.append( (uXbrlDimensions, self.role, None, None) )
                dimensionArcFound = True
            if not formulaArcFound:
                baseSetKeys.append( (uXbrlFormulae, None, None, None) ) 
                baseSetKeys.append( (uXbrlFormulae, self.role, None, None) )
                formulaArcFound = True
            if not tableRenderingArcFound and _arcrole in tableRenderingArcroles:
                baseSetKeys.append( (uXbrlTableRendering, None, None, None) ) 
                baseSetKeys.append( (uXbrlTableRendering, self.role, None, None) ) 
                tableRenderingArcFound = True
                self.modelDocument.modelXbrl.hasTableRendering = True
        if traceToStdout: print("baseset baseSetKeys len {}".format(len(baseSetKeys)))
        for baseSetKey in baseSetKeys:
            self.modelDocument.modelXbrl.baseSets[baseSetKey].append(self)
        baseSetKeys.clear()
        self.arcroleQNames.clear()
        if traceToStdout: print("finish baseset {}".format(self.qname))

cdef class ModelXlinkResource(ModelXlinkObject):
    cdef readonly unicode xlinkLabel
    
    def __init__(self, ModelDocument modelDocument):
        super().__init__(modelDocument)
        self.xlinkLabel = None
        
    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        #if traceToStdout: print("mdlRlTy setV ln {} isAttr {} val {}".format(transcode(localName), isAttribute, psviValue))
        if isAttribute:
            if equals(namespace, nsXlink):
                if equals(localName, lnLabel):
                    self.xlinkLabel = pyValue
                    return
            elif equals(namespace, nsXml) and equals(localName, lnLang):
                self.modelDocument.modelXbrl.langs.add(pyValue)
        ModelXlinkObject.setValue(self, namespace, localName, pyValue, isAttribute)
        
    cdef setup(self): # element has been set up
        if (self.modelDocument.type != Type.INLINEXBRL and  # inline setup performed by ModelDocument compilation
            self._parent is not None): # must be an extended link
            self._parent.labeledResources[self.xlinkLabel].append(self)

    def iterAttrs(self):
        if self.xlinkLabel is not None:
            yield (uClarkXlinkLabel, self.xlinkLabel)
        ModelXlinkObject.iterAttrs()      
        
    def viewText(self, labelrole=None, lang=None):
        """(str) -- Text of contained (inner) text nodes except for any whose localName 
        starts with URI, for label and reference parts displaying purposes.
        (Footnotes, which return serialized html content of footnote.)"""
        if self.qname == XbrlConst.qnLinkFootnote:
            return XmlUtil.innerText(self, ixEscape="html", strip=True) # include HTML construct
        return " ".join([XmlUtil.text(resourceElt)
                           for resourceElt in self.iter()
                              if isinstance(resourceElt,ModelObject) and 
                                  not resourceElt.localName.startswith("URI")])
        
    def roleRefPartSortKey(self):
        return "{} {}".format(self.role,
                              " ".join("{} {}".format(_refPart.localName, _refPart.stringValue.strip())
                                       for _refPart in self.iterchildren()))[:200] # limit length of sort
        
    def dereference(self):
        return self
        
cdef class ModelXlinkLocator(ModelXlinkResource):
    cdef readonly AnyURI href
    cdef readonly ModelHref modelHref
    
    def __init__(self, ModelDocument modelDocument):
        super().__init__(modelDocument)
        self.href = None
        self.modelHref = None
        
    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        #if traceToStdout: print("mdlRlTy setV ln {} isAttr {} val {}".format(transcode(localName), isAttribute, psviValue))
        if isAttribute:
            if equals(namespace, nsXlink):
                if equals(localName, lnHref):
                    self.href = pyValue
                    return
        ModelXlinkResource.setValue(self, namespace, localName, pyValue, isAttribute)
            
    cdef setup(self): # element has been set up
        ModelXlinkResource.setup(self)
        if self.href is not None:
            # only link:loc elements are discovered (in-DTS) but not custom locators
            if traceToStdout: print("setup locator {} base {}".format(self.href.urlWithoutFragment, self.baseForElement()))
            self.modelHref = self.modelDocument.modelHref(str(self.href.urlWithoutFragment), self.baseForElement(), self.qname == qnLinkLoc)

    def iterAttrs(self):
        if self.href is not None:
            yield (uClarkXlinkHref, self.href)
        ModelXlinkResource.iterAttrs()      
        
    def dereference(self):
        """(ModelObject) -- Resolve loc's href if resource is a loc with href document and id modelHref"""
        if self.modelHref is None or self.modelHref.modelDocument is None:
            return None
        return self.modelHref.modelDocument.fragmentObject(self.href.fragment)
        
cdef class ModelXlinkArc(ModelXlinkObject):
    cdef readonly AnyURI arcrole, preferredLabel
    cdef readonly unicode fromLabel, toLabel
    cdef readonly object order, weight # Decimal
    cdef readonly int priority
    cdef readonly unicode use
    
    def __init__(self, ModelDocument modelDocument):
        super().__init__(modelDocument)
        self.arcrole = self.preferredLabel = None
        self.fromLabel = self.toLabel = self.use = None
        
    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        if isAttribute:
            if equals(namespace, nsXlink): 
                if equals(localName, lnArcrole):
                    self.arcrole = pyValue
                    return
                elif equals(localName, lnFrom):
                    self.fromLabel = pyValue
                    return
                elif equals(localName, lnTo):
                    self.toLabel = pyValue
                    return
            elif namespace[0] == chNull:
                if equals(localName, lnOrder):
                    self.order = pyValue
                    return
                elif equals(localName, lnPriority):
                    self.priority = pyValue
                    return
                elif equals(localName, lnWeight):
                    self.weight = pyValue
                    return
                elif equals(localName, lnPreferredLabel):
                    self.preferredLabel = pyValue
                    return
                elif equals(localName, lnUse):
                    self.use = pyValue
                    return
        ModelXlinkObject.setValue(self, namespace, localName, pyValue, isAttribute)

    cdef setup(self): # element attributes have been set up
        try:
            self._parent.arcroleQNames.add( (self.arcrole, self.qname) )
        except AttributeError: 
            pass # invalid xml structure had wrong parent for arc
        if self.order is None: # must default to 1
            self.order = dONE

    def iterAttrs(self):
        if self.arcrole is not None:
            yield (uClarkXlinkArcrole, self.arcrole)
        if self.fromLabel is not None:
            yield (uClarkXlinkFrom, self.fromLabel)
        if self.toLabel is not None:
            yield (uClarkXlinkTo, self.toLabel)
        if self.order is not None:
            yield (uOrder, self.order)
        if self.priority is not None:
            yield (uPriority, self.priority)
        if self.weight is not None:
            yield (uWeight, self.weight)
        if self.preferredLabel is not None:
            yield (uPreferredLabel, self.preferredLabel)
        if self.use is not None:
            yield (uUse, self.use)
        ModelXlinkObject.iterAttrs() 
    
    @property
    def contextElement(self): # Value of xbrldt:contextElement attribute (on applicable XDT arcs)
        return self.get("{http://xbrl.org/2005/xbrldt}contextElement")
    
    @property
    def targetRole(self): # Value of xbrldt:targetRole attribute (on applicable XDT arcs)
        return self.get("{http://xbrl.org/2005/xbrldt}targetRole")
        
cdef class ModelRelationship(ModelObject):
    cdef readonly ModelXlinkArc modelArc
    cdef readonly ModelObject fromModelObject
    cdef readonly ModelObject toModelObject
   
    def __init__(self, ModelDocument modelDocument, ModelXlinkArc modelArc, ModelObject fromModelObject, ModelObject toModelObject):
        super().__init__(modelDocument)
        self.modelArc = modelArc
        self.fromModelObject = fromModelObject
        self.toModelObject = toModelObject
        
    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        ModelObject.setValue(self, namespace, localName, pyValue, isAttribute)
        
    @property
    def qname(self):
        return self.modelArc.qname
    
    def get(self, unicode clarkName, object defaultValue=None): # get an arc attribute by clark name
        return self.modelArc.get(clarkName, defaultValue)

    @property
    def xlinkType(self):
        return self.modelArc.xlinkType
        
    @property
    def xlinkTitle(self):
        return self.modelArc.xlinkTitle
        
    @property
    def getparent(self):
        return self.modelArc.getparent

    @property
    def fromLabel(self):
        return self.modelArc.fromLabel
        
    @property
    def toLabel(self):
        return self.modelArc.toLabel
        
    @property
    def preferredLabel(self):
        return self.modelArc.preferredLabel
        
    @property
    def arcrole(self):
        return self.modelArc.arcrole
        
    @property
    def linkrole(self):
        return self.modelArc._parent.role

    @property
    def order(self):
        return self.modelArc.order
        
    @property
    def priority(self):
        return self.modelArc.priority
        
    @property
    def weight(self):
        return self.modelArc.weight
        
    @property
    def use(self):
        return self.modelArc.use
        
    @property
    def fromLocator(self):
        """(ModelLocator) -- Value of locator surrogate of relationship source, if any"""
        try:
            for fromResource in self.modelArc._parent.labeledResources[self.fromLabel]:
                if isinstance(fromResource, ModelXlinkLocator) and self.fromModelObject is fromResource.dereference():
                    return fromResource
        except AttributeError: 
            pass # invalid xml structure had wrong parent for relationshi; (arc)
        return None
        
    @property
    def toLocator(self):
        """(ModelLocator) -- Value of locator surrogate of relationship target, if any"""
        try:
            for toResource in self.modelArc._parent.labeledResources[self.toLabel]:
                if isinstance(toResource, ModelXlinkLocator) and self.toModelObject is toResource.dereference():
                    return toResource
        except AttributeError: 
            pass # invalid xml structure had wrong parent for relationshi; (arc)
        return None
    
    def locatorOf(self, dereferencedObject):
        """(ModelLocator) -- Value of locator surrogate of relationship target, if any"""
        fromLocator = self.fromLocator
        if fromLocator is not None and fromLocator.dereference() == dereferencedObject:
            return fromLocator
        toLocator = self.toLocator
        if toLocator is not None and toLocator.dereference() == dereferencedObject:
            return toLocator
        return None
        
    @property
    def isProhibited(self):
        return self.use == "prohibited"
    
    @property
    def prohibitedUseSortKey(self): # 2 if use is prohibited, else 1, for use in sorting effective arcs before prohibited arcs
        return 2 if self.isProhibited else 1

    @property
    def preferredLabel(self): # presentation and gpl preferredLabel
        return self.modelArc.preferredLabel

    @property
    def variablename(self): 
        return self.get("name")

    @property
    def variableQname(self):
        return self.get("name")
    
    @property
    def linkQname(self):
        """(QName) -- qname of the parent extended link element"""
        return self.modelArc._parent.qname
    
    @property
    def contextElement(self): # Value of xbrldt:contextElement attribute (on applicable XDT arcs)
        return self.modelArc.contextElement
    
    @property
    def targetRole(self): # Value of xbrldt:targetRole attribute (on applicable XDT arcs)
        return self.modelArc.targetRole
    
    @property
    def consecutiveLinkrole(self): #Value of xbrldt:targetRole attribute, if provided, else parent linkRole (on applicable XDT arcs)
        return self.targetRole or self.linkrole
    
    @property
    def isUsable(self): # True if xbrldt:usable is true (on applicable XDT arcs, defaults to True if absent)
        return self.get("{http://xbrl.org/2005/xbrldt}usable") in ("true","1", None)
    
    @property
    def closed(self): # Value of xbrldt:closed (on applicable XDT arcs, defaults to 'false' if absent)
        return self.get("{http://xbrl.org/2005/xbrldt}closed") or "false"
    
    @property
    def isClosed(self): # (bool) -- True if xbrldt:closed is true (on applicable XDT arcs, defaults to False if absent)
        return self.get("{http://xbrl.org/2005/xbrldt}closed", False)

    @property
    def usable(self): # Value of xbrldt:usable (on applicable XDT arcs, defaults to 'true' if absent)
        return self.get("{http://xbrl.org/2005/xbrldt}usable", True)
    
    @property
    def isComplemented(self): # True if complemented is true (on applicable formula/rendering arcs, defaults to False if absent)
        return self.get("complement", False)
    
    @property
    def isCovered(self): # True if cover is true (on applicable formula/rendering arcs, defaults to False if absent)
        return self.get("cover", False)
        
    @property
    def axisDisposition(self): # Value of axisDisposition (on applicable table linkbase arcs
        try:
            return self.get("=axisDisposition")
        except AttributeError:
            aType = (self.get("axis") or # XII 2013
                     self.get("axisDisposition") or # XII 2011
                     self.get("axisType"))  # Eurofiling
            self.set("=axisDisposition", ("x" if aType in ("xAxis","x")
                                          else "y" if aType in ("yAxis","y")
                                          else "z" if aType in ("zAxis","z")
                                          else None))
            return self.get("=axisDisposition")
        
    cdef tuple equivalenceAttrs(self):
        return (self.qname, 
                self.linkQname,
                self.linkrole,  # needed when linkrole=None merges multiple links
                self.fromModelObject.objectIndex if isinstance(self.fromModelObject, ModelObject) else -1, 
                self.toModelObject.objectIndex if isinstance(self.toModelObject, ModelObject) else -1, 
                self.order, 
                self.weight, 
                self.preferredLabel)
        
    @property
    def equivalenceHash(self): # not exact, use equivalenceKey if hashes are the same
        return PyObject_Hash(self.equivalenceAttrs())
        
    @property
    def equivalenceKey(self): # Key to determine relationship equivalence per 2.1 spec
        if self.modelArc.attrs is None or len(self.modelArc.attrs) == 0:
            return self.equivalenceAttrs()
        else:
            return self.equivalenceAttrs() + self.modelArc.keySortedAttrValues()
                
    def isIdenticalTo(self, otherModelRelationship):
        """(bool) -- Determines if relationship is identical to another, based on arc and identical from and to objects"""
        return (otherModelRelationship is not None and
                self.modelArc == otherModelRelationship.modelArc and
                self.fromModelObject is not None and otherModelRelationship.fromModelObject is not None and
                self.toModelObject is not None and otherModelRelationship.toModelObject is not None and
                self.fromModelObject == otherModelRelationship.fromModelObject and
                self.toModelObject == otherModelRelationship.toModelObject)

    def priorityOver(self, otherModelRelationship):
        """(bool) -- True if this relationship has priority over other relationship"""
        if otherModelRelationship is None:
            return True
        priority = self.priority
        otherPriority = otherModelRelationship.priority
        if priority > otherPriority:
            return True
        elif priority < otherPriority:
            return False
        if otherModelRelationship.isProhibited:
            return False
        return True
    
    @property
    def propertyView(self):
        return self.toModelObject.propertyView + \
               (("arcrole", self.arcrole),
                ("weight", self.weight) if self.arcrole == XbrlConst.summationItem else (),
                ("preferredLabel", self.preferredLabel)  if self.arcrole == XbrlConst.parentChild and self.preferredLabel else (),
                ("contextElement", self.contextElement)  if self.arcrole in (XbrlConst.all, XbrlConst.notAll)  else (),
                ("typedDomain", self.toModelObject.typedDomainElement.qname)  
                  if self.arcrole == XbrlConst.hypercubeDimension and
                     isinstance(self.toModelObject,ModelConcept) and
                     self.toModelObject.isTypedDimension and 
                     self.toModelObject.typedDomainElement is not None  else (),
                ("closed", self.closed) if self.arcrole in (XbrlConst.all, XbrlConst.notAll)  else (),
                ("usable", self.usable) if self.arcrole == XbrlConst.domainMember  else (),
                ("targetRole", self.targetRole) if self.arcrole.startswith(XbrlConst.dimStartsWith) else (),
                ("order", self.order),
                ("priority", self.priority)) + \
               (("from", self.fromModelObject.qname),) if isinstance(self.fromModelObject,ModelObject) else ()
        
    def __repr__(self):
        return ("modelRelationship[{0}, linkrole: {1}, arcrole: {2}, from: {3}, to: {4}, {5}, line {6}]"
                .format(self.objectIndex, os.path.basename(self.linkrole), os.path.basename(self.arcrole),
                        self.fromModelObject.qname if isinstance(self.fromModelObject, ModelObject) else "??",
                        self.toModelObject.qname if isinstance(self.toModelObject, ModelObject) else "??",
                        self.modelDocument.basename, self.sourceline))

    @property
    def viewConcept(self):
        if isinstance(self.toModelObject, ModelConcept):
            return self.toModelObject
        elif isinstance(self.fromModelObject, ModelConcept):
            return self.fromModelObject
        return None
                       
cdef XSTypeDefinition *elementSubstitutionComplexHeadType(XSElementDeclaration* eltDcl):
    cdef XSTypeDefinition *eltTypeDef
    cdef XSElementDeclaration* subsEltDcl
    cdef XSTypeDefinition *subsTypeDef
    cdef XSTypeDefinition *headComplexTypeDef
    cdef TYPE_CATEGORY eltTypeCategory, subsTypeCategory
    eltTypeDef = eltDcl.getTypeDefinition()
    eltTypeCategory = eltTypeDef.getTypeCategory()
    if eltTypeCategory == COMPLEX_TYPE: # declares an item type
        return eltTypeDef
    # proceding knowing element (simple type) doesn't declare an (item) type
    subsEltDcl = eltDcl.getSubstitutionGroupAffiliation()
    if subsEltDcl is not NULL:
        subsTypeDef = subsEltDcl.getTypeDefinition()
        subsTypeCategory = subsTypeDef.getTypeCategory()
        if subsTypeCategory == COMPLEX_TYPE:
            headComplexTypeDef = subsTypeDef # use complex type definition
        else:
            headComplexTypeDef = elementSubstitutionComplexHeadType(subsEltDcl)
    else:
        headComplexTypeDef = NULL
    if headComplexTypeDef is not NULL: # found a complex head type
        return headComplexTypeDef
    return eltTypeDef # must be a simple type, use outermost type
         
cdef class ModelConcept(ModelObject): # wrapped by python ModelConcept
    # cdef XSElementDeclaration* xsElementDeclaration # xerces element definition
    cdef ModelType _modelType
    cdef ModelConcept _substitutionGroupModelConcept
    cdef bool _modelTypeIsSet, _subsGroupIsSet, \
            _isAbstract, _isDimensionIsSet, _isDimension,  _isNoDecIsSet, _isNoDec,  _isEnumIsSet, _isEnum,\
            _isFractionIsSet, _isFraction, _isMonetaryIsSet, _isMonetary, _isNumericIsSet, _isNumeric, _isSharesIsSet, _isShares
    cdef readonly unicode balance
    cdef readonly unicode periodType
    
    def __init__(self, ModelDocument modelDocument, pyEltDeclArg, QName qname):
        super().__init__(modelDocument, qname)
        self._modelTypeIsSet = self._subsGroupIsSet = self._isFractionIsSet = self._isNumericIsSet = self._isMonetaryIsSet = \
            self._isNumericIsSet = self._isSharesIsSet = False
        self.balance = self.periodType = None
        
    def __cinit__(self, ModelDocument modelDocument, pyEltDeclArg, QName qname):
        cdef uint64_t vEltDeclArg = <uint64_t>pyEltDeclArg
        cdef XSElementDeclaration* xsElementDeclaration = <XSElementDeclaration*>vEltDeclArg
        #if traceToStdout: print("mdlConcept cinit args {} {}".format(modelDocument.basename, qname))
        #self.xsElementDeclaration = xsElementDeclaration
        self._isAbstract = xsElementDeclaration.getAbstract()
               
    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        if isAttribute:
            if equals(namespace, nsXbrli):
                if equals(localName, lnBalance):
                    self.balance = pyValue
                    return
                elif equals(localName, lnPeriodType):
                    self.periodType = pyValue
                    return
        ModelObject.setValue(self, namespace, localName, pyValue, isAttribute)
        
    cdef XSElementDeclaration* xsElementDeclaration(self):
        return self.modelDocument.modelXbrl.qnameXsElementDeclaration(self.qname)
    
    @property
    def abstract(self):
        """(str) -- u"true" if concept is abstract else u"false" """
        return u"true" if self._isAbstract else u"false"
    
    @property
    def baseXsdType(self):
        """(str) -- Value of localname of type (e.g., monetary for monetaryItemType)"""
        cdef ModelType modelType = self.modelType()
        return modelType.baseXsdType if modelType is not None else "anyType"

    @property
    def baseXbrliType(self):
        """(str) -- Attempts to return the base xsd type localName that this concept's type 
        is derived from.  If not determinable anyType is returned.  E.g., for monetaryItemType, 
        decimal is returned."""
        cdef QName qn = self.baseXbrliTypeQName
        if qn is not None:
            return qn.localName
        return None
        
    @property
    def baseXbrliTypeQName(self):
        """(qname) -- Attempts to return the base xsd type QName that this concept's type 
        is derived from.  If not determinable anyType is returned.  E.g., for monetaryItemType, 
        decimal is returned."""
        cdef ModelType modelType = self.modelType()
        if modelType is None:
            return None
        cdef QName qn = modelType.baseXbrliQName
        if qn.namespaceURI == uNsXbrli: # type may be xsd type if substitution is to an XBRL Concept as head
            return qn # type is an xbrli type
        return None
        
    @property
    def default(self):
        cdef XSElementDeclaration* xsElementDeclaration = self.xsElementDeclaration()
        if xsElementDeclaration.getConstraintType() != VALUE_CONSTRAINT.VALUE_CONSTRAINT_DEFAULT:
            return None
        cdef const XMLCh* xmlChDefault = xsElementDeclaration.getConstraintValue()
        cdef char* chDefault = transcode(xmlChDefault)
        cdef unicode pyDefault = chDefault
        release(&chDefault)
        return pyDefault
        
    @property
    def enumDomainQName(self):
        return self.get(uClarkEnumerationDomain2014) or self.get(uClarkEnumerationDomain2016) or self.get(uClarkEnumerationDomain2YMD) or self.get(uClarkEnumerationDomain1YMD) 

    @property
    def enumDomain(self):
        return self.modelXbrl.qnameConcepts.get(self.enumDomainQname)
        
    @property
    def enumLinkrole(self):
        return self.get(uClarkEnumerationLinkrole2014) or self.get(uClarkEnumerationLinkrole2016) or self.get(uClarkEnumerationLinkrole2YMD) or self.get(uClarkEnumerationLinkrole1YMD)
    
    @property
    def enumDomainUsable(self):
        return self.get(uClarkEnumerationUsable2014) or self.get(uClarkEnumerationUsable2014) or self.get(uClarkEnumerationUsable2YMD) or self.get(uClarkEnumerationUsable1YMD)


    @property
    def facets(self):
        cdef ModelType modelType = self.modelType()
        return modelType.facets if modelType is not None else None

    @property
    def fixed(self):
        cdef XSElementDeclaration* xsElementDeclaration = self.xsElementDeclaration()
        if xsElementDeclaration.getConstraintType() != VALUE_CONSTRAINT.VALUE_CONSTRAINT_FIXED:
            return None
        cdef const XMLCh* xmlChFixed = xsElementDeclaration.getConstraintValue()
        cdef char* chFixed = transcode(xmlChFixed)
        cdef unicode pyFixed = chFixed
        release(&chFixed)
        return pyFixed

    def instanceOfType(self, typeqname):
        """(bool) -- True if element is declared by, or derived from type of given qname or qnames"""
        cdef bool isListOfTypeQNames = isinstance(typeqname, (tuple,list,set))
        cdef ModelType modelType = self.modelType()
        cdef XSTypeDefinition *qnTypeDef
        if modelType is None:
            return False
        if isListOfTypeQNames: # union
            if modelType.qname in typeqname:
                return True
        else: # not union, single type
            if modelType.qname == typeqname:
                return True
        if isListOfTypeQNames:
            if any(modelType.xsTypeDefinition.derivedFromType(self.modelDocument.modelXbrl.qnameXsTypeDefinition(qn))
                   for qn in typeqname):
                return True
        else:
            qnTypeDef = self.modelDocument.modelXbrl.qnameXsTypeDefinition(typeqname)
            if modelType.xsTypeDefinition.derivedFromType(qnTypeDef):
                return True
        return False
    
    @property
    def isAbstract(self):
        """(bool) -- True if concept is abstract """
        return self._isAbstract
        
    @property
    def isDimensionItem(self):
        if not self._isDimensionIsSet:
            self._isDimension = self.substitutesForNsName(nsXbrldt, lnDimensionItem)
            self._isDimensionIsSet = True
        return self._isDimension

    @property
    def isDomainMember(self):
        """(bool) -- Same as isPrimaryItem (same definition in XDT)"""
        return self.isPrimaryItem   # same definition in XDT

    @property
    def isDtrNoDecimalsItemType(self):
        cdef XSTypeDefinition *xsTypeDefinition
        if not self._isNoDecIsSet:
            xsTypeDefinition = self.xsElementDeclaration().getTypeDefinition()
            self._isNoDec = (xsTypeDefinition.derivedFrom(nsDtrYMD, lnNoDecimalsMonetaryItemType) or 
                             xsTypeDefinition.derivedFrom(nsDtrYMD, lnNonNegativeNoDecimalsMonetaryItemType))
            self._isNoDecIsSet = True
        return self._isNoDec
    
    @property
    def isEnumeration(self):
        cdef XSTypeDefinition *xsTypeDefinition
        if not self._isEnumIsSet:
            xsTypeDefinition = self.xsElementDeclaration().getTypeDefinition()
            self._isEnum = (xsTypeDefinition.derivedFrom(nsEnum2014, lnEnumerationItemType) or 
                            xsTypeDefinition.derivedFrom(nsEnum2016, lnEnumerationItemType) or
                            xsTypeDefinition.derivedFrom(nsEnum2016, lnEnumerationsItemType) or 
                            xsTypeDefinition.derivedFrom(nsEnum2YMD, lnEnumerationItemType) or
                            xsTypeDefinition.derivedFrom(nsEnum2YMD, lnEnumerationSetItemType) or 
                            xsTypeDefinition.derivedFrom(nsEnum1YMD, lnEnumerationItemType) or
                            xsTypeDefinition.derivedFrom(nsEnum1YMD, lnEnumerationListItemType) or 
                            xsTypeDefinition.derivedFrom(nsEnum1YMD, lnEnumerationSetItemType))
            self._isEnumIsSet = True
        return self._isEnum

    @property
    def isEnumDomainUsable(self):
        return self.enumDomainUsable # boolean True
        
    @property
    def isExplicitDimension(self):
        return self.isDimensionItem and self.get(uClarkXbrldtTypedDomainRef) is None
        
    @property
    def isFraction(self):
        """(bool) -- True if the baseXbrliType is fractionItemType"""
        if not self._isFractionIsSet:
            self._isFraction = self.baseXbrliType == "fractionItemType"
            self._isFractionIsSet = True
        return self._isFraction

    @property
    def isGlobalDeclaration(self):
        """(bool) -- True for global scope definition """
        return self.xsElementDeclaration().getScope() == SCOPE.SCOPE_GLOBAL

    @property
    def isHypercubeItem(self):
        return self.substitutesForNsName(nsXbrldt, lnHypercubeItem)

    @property
    def isItem(self):
        return self.substitutesForNsName(nsXbrli, lnItem)
    
    @property
    def isLinkPart(self):
        return self.substitutesForNsName(nsLink,lnPart)

    @property
    def isMonetary(self):
        """(bool) -- True if the baseXbrliType is monetaryItemType"""
        if not self._isMonetaryIsSet:
            self._isMonetary = self.baseXbrliType == "monetaryItemType"
        return self._isMonetary
   
    @property
    def isNillable(self):
        """(bool) -- True if nillable"""
        return self.xsElementDeclaration().getNillable()
       
    @property
    def isNumeric(self):
        """(bool) -- True for elements of, or derived from, numeric base type (not including fractionItemType)"""
        if not self._isNumericIsSet:
            self._isNumeric = XbrlConst.isNumericXsdType(self.baseXsdType)
        return self._isNumeric
 
    @property
    def isPrimaryItem(self):
        return self.isItem and not self.isHypercubeItem and not self.isDimensionItem
        
    @property
    def isRoot(self):
        """(bool) -- True if parent of element definition is xsd schema element"""
        return self.isGlobalDeclaration
    
    @property
    def isShares(self):
        """(bool) -- True if the baseXbrliType is sharesItemType"""
        if not self._isSharesIsSet:
            self._isShares = self.baseXbrliType == "sharesItemType"
        return self._isShares
        
    @property
    def isSQNameType(self):
        cdef XSTypeDefinition *xsTypeDefinition = self.xsElementDeclaration().getTypeDefinition()
        return xsTypeDefinition.derivedFrom(nsDtrYMD, lnSQNameType)
        
    @property
    def isSQNameItemType(self):
        cdef XSTypeDefinition *xsTypeDefinition = self.xsElementDeclaration().getTypeDefinition()
        return xsTypeDefinition.derivedFrom(nsDtrYMD, lnSQNameItemType)
        
    @property
    def isTuple(self):
        return self.substitutesForNsName(nsXbrli, lnTuple)
        
    @property
    def isTypedDimension(self):
        return self.isDimensionItem and self.get(uClarkXbrldtTypedDomainRef) is not None
    
    @property
    def isTextBlock(self):
        """(bool) -- Element's type.isTextBlock."""
        return self.type is not None and self.type.isTextBlock
    
    @property
    def isMultiLanguage(self):
        """(bool) -- True if type is, or is derived from, stringItemType or normalizedStringItemType."""
        return self.baseXbrliType in {"stringItemType", "normalizedStringItemType", "string", "normalizedString"}
    
    cdef ModelType modelType(self):
        cdef XSTypeDefinition *xsTypeDefinition
        if not self._modelTypeIsSet:
            xsTypeDefinition = elementSubstitutionComplexHeadType(self.xsElementDeclaration())
            if xsTypeDefinition is not NULL:
                self._modelType = self.modelDocument.modelXbrl.xsTypeDefinitionType(xsTypeDefinition)
                if self._modelType is not None: # may be discovered later in loading process
                    # self._modelTypeIsSet = True
                    pass
        return self._modelType

    @property
    def name(self):
        """(str) --LocalName of concept """
        return self.qname.localName
        
    @property
    def niceType(self):
        """Provides a type name suited for user interfaces: hypercubes as Table, dimensions as Axis, 
        types ending in ItemType have ItemType removed and first letter capitalized (e.g., 
        stringItemType as String).  Otherwise returns the type's localName portion.
        """
        cdef QName typeQName
        if self.isHypercubeItem: return "Table"
        if self.isDimensionItem: return "Axis"
        typeQName = self.typeQName
        if typeQName:
            if typeQName.localName.endswith("ItemType"):
                return typeQName.localName[0].upper() + typeQName.localName[1:-8]
            return typeQName.localName
        return None
        
    @property
    def nillable(self):
        """(str) --Value of the nillable attribute or its default"""
        return u"true" if self.isNillable else u"false"
        
    @property
    def type(self):
        """Element's modelType object (if any)"""
        return self.modelType()

    @property
    def typeQName(self):
        """(QName) -- Value of type attribute, if any, or if type contains an anonymously-named
        type definition (as sub-elements), then QName formed of element QName with anonymousTypeSuffix
        appended to localName.  If neither type attribute or nested type definition, then attempts
        to get type definition in turn from substitution group element."""
        cdef ModelType modelType = self.modelType()
        return modelType.qname if modelType is not None else None
    
    @property
    def typedDomainRef(self):
        return self.get(uClarkXbrldtTypedDomainRef)

    @property
    def typedDomainElement(self):
        """(ModelConcept) -- the element definition for a typedDomainRef attribute (of a typed dimension element)"""
        return self.resolveUri(hrefObject=None, uri=self.typedDomainRef)

    cdef ModelConcept substitutionGroupModelConcept(self):
        cdef ModelXbrl modelXbrl
        if not self._subsGroupIsSet:
            modelXbrl = self.modelDocument.modelXbrl
            self._substitutionGroupModelConcept = modelXbrl.xsElementDeclarationConcept(self.xsElementDeclaration().getSubstitutionGroupAffiliation())
            self._subsGroupIsSet = True
        return self._substitutionGroupModelConcept

    @property
    def substitutionGroup(self):
        """modelConcept object for substitution group (or None)"""
        return self.substitutionGroupModelConcept()

    @property
    def substitutionGroupQName(self):
        """(QName) -- substitution group"""
        return self.modelDocument.modelXbrl.xsElementDeclarationQName(self.xsElementDeclaration().getSubstitutionGroupAffiliation())

    @property
    def substitutionGroupQNames(self):
        """([QName]) -- Ordered list of QNames of substitution groups (recursively)"""
        cdef list qnames = list()
        cdef QName qn
        cdef ModelXbrl modelXbrl = self.modelDocument.modelXbrl
        cdef XSElementDeclaration* eltDcl = self.xsElementDeclaration().getSubstitutionGroupAffiliation()
        while eltDcl is not NULL:
            qn = modelXbrl.xsElementDeclarationQName(eltDcl)
            if qn is not None:
                qnames.append(qn)
            eltDcl = eltDcl.getSubstitutionGroupAffiliation()
        return qnames
  
    def substitutesForQName(self, subsQName):
        """(bool) -- True if element substitutes for specified qname"""
        cdef ModelXbrl modelXbrl = self.modelDocument.modelXbrl
        cdef XSElementDeclaration* eltDcl = self.xsElementDeclaration().getSubstitutionGroupAffiliation()
        cdef QName qn
        while eltDcl is not NULL and subsQName is not None:
            qn = modelXbrl.xsElementDeclarationQName(eltDcl)
            if qn is not None and qn == subsQName:
                return True
            eltDcl = eltDcl.getSubstitutionGroupAffiliation()
        return False

    @property
    def subGroupHeadQName(self):
        """(QName) -- Head of substitution lineage of element (e.g., xbrli:item)"""
        cdef XSElementDeclaration* eltDcl = self.xsElementDeclaration().getSubstitutionGroupAffiliation()
        cdef XSElementDeclaration* nextEltDcl
        while eltDcl is not NULL:
            nextEltDcl = eltDcl.getSubstitutionGroupAffiliation()
            if nextEltDcl is NULL:
                return self.modelDocument.modelXbrl.xsElementDeclarationQName(eltDcl)
            eltDcl = nextEltDcl
        return None
    
    cdef bool substitutesForNsName(self, XMLCh *ns, XMLCh *name):
        cdef XSElementDeclaration* eltDcl = self.xsElementDeclaration().getSubstitutionGroupAffiliation()
        cdef XSElementDeclaration* nextEltDcl
        while eltDcl is not NULL:
            if equals(ns, eltDcl.getNamespace()) and equals(name, eltDcl.getName()):
                return True
            nextEltDcl = eltDcl.getSubstitutionGroupAffiliation()
            if nextEltDcl is NULL:
                return False
            eltDcl = nextEltDcl
        return False
        
cdef newModelConcept(ModelDocument modelDocument, XSElementDeclaration * xsElementDeclaration, QName qname):
    cdef uint64_t vEltDeclArg = <uint64_t>xsElementDeclaration
    cdef object pyEltDeclArg = vEltDeclArg
    cdef object modelConcept
    modelConcept = ModelDtsObject.ModelConcept(modelDocument, pyEltDeclArg, qname) # python ModelConcept wraps cython ModelConcept
    return modelConcept

cdef modelTypeBaseXbrliTypeQName(XSTypeDefinition *xsTypeDefinition, ModelXbrl modelXbrl):
    cdef QName qnType = modelXbrl.xsTypeDefinitionQName(xsTypeDefinition)
    cdef XSSimpleTypeDefinition *xsSimpleTypeDefinition
    cdef XSSimpleTypeDefinitionList *unionTypesList
    cdef XSTypeDefinition *xsBaseTypeDefinition
    if qnType is None or qnType.namespaceURI == uNsXbrli or qnType.namespaceURI == uNsXsd:
        return qnType
    else:
        if xsTypeDefinition.getTypeCategory() == SIMPLE_TYPE:
            xsSimpleTypeDefinition = <XSSimpleTypeDefinition*>xsTypeDefinition
            if xsSimpleTypeDefinition.getVariety() == VARIETY_UNION:
                unionTypesList = xsSimpleTypeDefinition.getMemberTypes()
                for i in range(unionTypesList.size()):
                    qnType = modelTypeBaseXbrliTypeQName(unionTypesList.elementAt(i), modelXbrl)
                    if qnType is not None:
                        return qnType
    xsBaseTypeDefinition = xsTypeDefinition.getBaseType() # try for base type first
    if xsBaseTypeDefinition is not NULL:
        return modelTypeBaseXbrliTypeQName(xsBaseTypeDefinition, modelXbrl)
    return None

cdef modelTypeBaseXsdTypes(XSTypeDefinition *xsTypeDefinition, ModelXbrl modelXbrl, list baseTypesList):
    cdef QName qnType = modelXbrl.xsTypeDefinitionQName(xsTypeDefinition)
    cdef XSSimpleTypeDefinition *xsSimpleTypeDefinition
    cdef XSSimpleTypeDefinitionList *unionTypesList
    if qnType.namespaceURI == uNsXsd:
        if qnType.localName not in baseTypesList:
            baseTypesList.append(qnType.localName) # deduplicate base type names
    else:
        if xsTypeDefinition.getTypeCategory() == SIMPLE_TYPE:
            xsSimpleTypeDefinition = <XSSimpleTypeDefinition*>xsTypeDefinition
            if xsSimpleTypeDefinition.getVariety() == VARIETY_UNION:
                unionTypesList = xsSimpleTypeDefinition.getMemberTypes()
                for i in range(unionTypesList.size()):
                    modelTypeBaseXsdTypes(unionTypesList.elementAt(i), modelXbrl, baseTypesList)
            else:
                modelTypeBaseXsdTypes((<XSTypeDefinition *>xsSimpleTypeDefinition).getBaseType(), modelXbrl, baseTypesList)
        else:
            modelTypeBaseXsdTypes((<XSComplexTypeDefinition *>xsTypeDefinition).getBaseType(), modelXbrl, baseTypesList)

cdef XSSimpleTypeDefinition *xsSimpleTypeDefinition(XSTypeDefinition *xsTypeDefinition):
    cdef XSSimpleTypeDefinition *xsSTD = NULL
    cdef XSTypeDefinition *xsTD
    cdef TYPE_CATEGORY typeCategory
    if xsTypeDefinition is not NULL:
        typeCategory = xsTypeDefinition.getTypeCategory()
        if typeCategory == COMPLEX_TYPE:
            xsSTD = (<XSComplexTypeDefinition*>xsTypeDefinition).getSimpleType()
            if xsSTD is NULL:
                xsTD = xsTypeDefinition.getBaseType()
                if xsTD is NULL:
                    return NULL
                elif xsTD != xsTypeDefinition:
                    return xsSimpleTypeDefinition(xsTD)
                return NULL # no simple type
        elif typeCategory == SIMPLE_TYPE: # it's simple type
            xsSTD = <XSSimpleTypeDefinition*>xsTypeDefinition
    return xsSTD

cdef class ModelType(ModelObject): # not wrapped by a Python ModelType
    # xsTypeDefinition is not persistent between checking type of different concepts
    # it seems to be a shared buffer in Xerces so should be accessed only from concept
    cdef XSTypeDefinition *xsTypeDefinition
    cdef dict _facets
    cdef bool _baseXbrliTypeIsSet, _baseXsdTypeIsSet, _facetsIsSet
    cdef QName _baseXbrliQName
    cdef object _baseXsdType # may be a type localName or list of type localNames
    cdef bool _isAnonymous
    
    def __init__(self, ModelDocument modelDocument, QName qname):
        super().__init__(modelDocument, qname)
        self._baseXbrliTypeIsSet = self._baseXsdTypeIsSet = self._facetsIsSet = False
        
    @property
    def attributes(self): # dict by qname of attributes
        cdef ModelXbrl modelXbrl = self.modelDocument.modelXbrl
        cdef XSSimpleTypeDefinition *attrTypeDef
        cdef XSAttributeUseList *attributeUseList
        cdef XSAttributeUse *attributeUse
        cdef XSAttributeDeclaration *attrDecl
        cdef QName attrQName
        cdef dict attrModelTypes = dict() # indexed by QName
        cdef ModelType attrModelType
        if self.xsTypeDefinition.getTypeCategory() == COMPLEX_TYPE:
            attributeUseList = (<XSComplexTypeDefinition *>self.xsTypeDefinition).getAttributeUses()
            if attributeUseList is not NULL:
                for i in range(attributeUseList.size()):
                    attributeUse = attributeUseList.elementAt(i)
                    attrDecl = attributeUse.getAttrDeclaration()
                    attrQName = modelXbrl.xmlchQName(attrDecl.getNamespace(), NULL, attrDecl.getName())
                    attrTypeDef = attrDecl.getTypeDefinition()
                    attrModelType = modelXbrl.xsTypeDefinitionType(attrTypeDef)
                    attrModelTypes[attrQName] = attrModelType
        return attrModelTypes
    
    @property
    def baseXbrliQName(self):
        """(qname) -- The qname of the parent type in the xbrli namespace, if any, otherwise the localName of the parent in the xsd namespace."""
        if self._baseXbrliTypeIsSet:
            return self._baseXbrliQName
        self._baseXbrliQName = modelTypeBaseXbrliTypeQName(self.xsTypeDefinition, self.modelDocument.modelXbrl)
        return self._baseXbrliQName
         
    @property
    def baseXbrliType(self):
        """(qname) -- The qname of the parent type in the xbrli namespace, if any, otherwise the localName of the parent in the xsd namespace."""
        cdef QName qn = self.baseXbrliQName
        if qn is not None:
            return qn.localName
        return None
         
    @property
    def baseXsdType(self):
        """(str) -- The xsd type localName that this type is derived from or: 
        list if union derived from multiple base types (in order appearing in union).
        """
        if self._baseXsdTypeIsSet:
            return self._baseXsdType
        cdef list baseTypesList = list() # set of base types underneath any unions
        modelTypeBaseXsdTypes(self.xsTypeDefinition, self.modelDocument.modelXbrl, baseTypesList)
        if len(baseTypesList) == 1:
            self._baseXsdType = baseTypesList.pop()
        else:
            self._baseXsdType = baseTypesList
        return self._baseXsdType
         

    cdef void elementParticleQNames(self, XSParticle *particle, list elementQNames):
        cdef TERM_TYPE particleTermType
        cdef XSElementDeclaration *eltDecl
        cdef XSModelGroup *modelGroupTerm
        cdef XSParticleList *groupParticlesList
        cdef XMLSize_t i
        cdef QName qname
        if particle is NULL:
            return 
        particleTermType = particle.getTermType()
        if particleTermType == TERM_ELEMENT:
            eltDecl = particle.getElementTerm()
            qname = self.modelDocument.modelXbrl.xmlchQName(eltDecl.getNamespace(), NULL, eltDecl.getName())
            if qname not in elementQNames:
                elementQNames.append(qname)
        if particleTermType == TERM_MODELGROUP:
            modelGroupTerm = particle.getModelGroupTerm()
            if modelGroupTerm is not NULL:
                groupParticlesList = modelGroupTerm.getParticles()
                for i in range(groupParticlesList.size()):
                    self.elementParticleQNames(groupParticlesList.elementAt(i), elementQNames)

    @property
    def elements(self): 
        """([QName]) -- List of element QNames that are descendants (content elements)"""
        cdef list elementQNames = list()
        
        if self.xsTypeDefinition.getTypeCategory() == COMPLEX_TYPE:
            self.elementParticleQNames((<XSComplexTypeDefinition *>self.xsTypeDefinition).getParticle(), elementQNames)
        
        return elementQNames
        
    @property
    def facets(self):
        cdef int facetIndex
        cdef XMLSize_t valueListIndex
        cdef XMLSize_t length
        cdef int definedFacets # bitwise OR of defined facets
        cdef FACET facetXercesName
        cdef XSSimpleTypeDefinition *simpleTypeDef
        cdef XMLCh* xmlChFacetValue
        cdef const XMLCh* n
        cdef const XMLCh* N
        cdef char* chFacetValue
        cdef dict chDictValue # enumeration is dict of value: enum id if any (for generic label href)
        cdef StringList* chFacetListValue
        cdef bool freeXmlChFacetValue = False
        cdef XSAnnotation* annotation
        if not self._facetsIsSet:
            self._facets = dict()
            simpleTypeDef = xsSimpleTypeDefinition(self.xsTypeDefinition)
            if simpleTypeDef is not NULL and simpleTypeDef.getTypeCategory() == SIMPLE_TYPE:
                definedFacets = simpleTypeDef.getDefinedFacets()
                for facetIndex in range(NUM_FACETS):
                    facetXercesName = facetXercesNames[facetIndex]
                    if facetXercesName & definedFacets: # bitwise and of facet "name" (a bit)
                        if facetXercesName == FACET_ENUMERATION:
                            chFacetListValue = simpleTypeDef.getLexicalEnumeration()
                            chDictValue = dict()
                            self._facets[facetPyNames[facetIndex]] = chDictValue
                            for valueListIndex in range(chFacetListValue.size()):
                                chFacetValue = transcode(chFacetListValue.elementAt(valueListIndex))
                                # to get ID for generic label, get ID via ModelXbrlIdentificationSAX2Handler
                                chDictValue[self.modelDocument.modelXbrl.internString(chFacetValue)] = "" # TBD should be ID of enum element
                                release(&chFacetValue)
                        else:
                            if facetXercesName == FACET_PATTERN:
                                chFacetListValue = simpleTypeDef.getLexicalPattern()
                                if chFacetListValue is NULL: # may be null if it really doesn't have a pattern
                                    continue
                                if chFacetListValue.size() == 1:
                                    xmlChFacetValue = chFacetListValue.elementAt(0)
                                else: # concatenate multiple patterns with | character
                                    length = 0 # compute sum of all pattern strings incl trailing | or null
                                    for valueListIndex in range(chFacetListValue.size()):
                                        length += stringLen(chFacetListValue.elementAt(valueListIndex)) + 1
                                    xmlChFacetValue = <XMLCh*>PyMem_Malloc((length+1) * sizeof(XMLCh))
                                    freeXmlChFacetValue = True
                                    xmlChFacetValue[0] = 0 #initialize string
                                    for valueListIndex in range(chFacetListValue.size()):
                                        if valueListIndex > 0:
                                            catString(xmlChFacetValue,  xmlchPipe)
                                        catString(xmlChFacetValue, chFacetListValue.elementAt(valueListIndex))
                            else:
                                xmlChFacetValue = <XMLCh*>simpleTypeDef.getLexicalFacetValue(facetXercesName)
                                if xmlChFacetValue is not NULL:
                                    continue
                            chFacetValue = transcode(xmlChFacetValue)
                            self._facets[facetPyNames[facetIndex]] = self.modelDocument.modelXbrl.internString(chFacetValue)
                            release(&chFacetValue)
                            if freeXmlChFacetValue:
                                PyMem_Free(xmlChFacetValue)
                                freeXmlChFacetValue = False
            self._facetsIsSet = True
        return self._facets

    @property
    def isAnonymous(self):
        """(bool) -- the type is defined anonymously """
        return self._isAnonymous
    
    @property
    def isMultiLanguage(self):
        """(bool) -- True if type is, or is derived from, stringItemType or normalizedStringItemType."""
        return self.baseXbrliType in {"stringItemType", "normalizedStringItemType", "string", "normalizedString"}

    @property
    def isComplexContent(self):
        """(str) -- the type is a complex type """
        return self.xsTypeDefinition.getTypeCategory() == COMPLEX_TYPE

    @property
    def isDomainItemType(self):
        """(bool) -- True if type is, or is derived from, domainItemType in either a us-types or a dtr-types namespace."""
        cdef ModelType typeDerivedFrom
        if self.name == "domainItemType" and \
           ("/us-types/" in self.qname.namespaceURI or
            self.qname.namespaceURI.startswith(XbrlConst.dtrTypesStartsWith)):
            return True
        typeDerivedFrom = self.typeDerivedFrom
        if not isinstance(typeDerivedFrom, ModelType): # textblock not a union type
            return False
        return typeDerivedFrom.isDomainItemType
    
    @property
    def isMixedContent(self):
        """(str) -- the type is a complex type with mixed content """
        return (self.xsTypeDefinition.getTypeCategory() == COMPLEX_TYPE and 
                (<XSComplexTypeDefinition *>self.xsTypeDefinition).getContentType() == CONTENTTYPE_MIXED)

    @property
    def isSimpleContent(self):
        """(str) -- the type is a complex type """
        return self.xsTypeDefinition.getTypeCategory() == SIMPLE_TYPE

    @property
    def isTextBlock(self):
        """(str) -- True if type is, or is derived from, us-types:textBlockItemType or dtr-types:escapedItemType"""
        cdef ModelType typeDerivedFrom
        if self.name == "textBlockItemType" and "/us-types/" in self.qname.namespaceURI:
            return True
        if self.name == "escapedItemType" and self.qname.namespaceURI.startswith(XbrlConst.dtrTypesStartsWith):
            return True
        typeDerivedFrom = self.typeDerivedFrom
        if not isinstance(typeDerivedFrom, ModelType): # textblock not a union type
            return False
        return typeDerivedFrom.isTextBlock    

    @property
    def name(self):
        """(str) --LocalName of type """
        if self.qname is not None:
            return self.qname.localName
        return uAnonymousType
    @property
    def qnameDerivedFrom(self):
        """(QName) -- the type(s) that this type is derived from (returns QNames list if type is a union)"""
        cdef XSSimpleTypeDefinition *xsSimpleTypeDefinition
        cdef XSSimpleTypeDefinitionList *unionXsTypesList
        cdef XSTypeDefinition *xsBaseTypeDefinition
        cdef XMLSize_t i
        cdef QName qnType
        cdef list unionQNamesList
        # if traceToStdout: print("qndf tr 1")
        if self.xsTypeDefinition.getTypeCategory() == SIMPLE_TYPE:
            xsSimpleTypeDefinition = <XSSimpleTypeDefinition*>self.xsTypeDefinition
            if xsSimpleTypeDefinition.getVariety() == VARIETY_UNION:
                unionXsTypesList = xsSimpleTypeDefinition.getMemberTypes()
                unionQNamesList = list()
                for i in range(unionXsTypesList.size()):
                    xsSimpleTypeDefinition = unionXsTypesList.elementAt(i)
                    qnType = self.modelDocument.modelXbrl.xsTypeDefinitionQName(xsSimpleTypeDefinition)
                    if qnType not in unionQNamesList:
                        unionQNamesList.append(qnType) # deduplicate type qnames
                # if traceToStdout: print("qndf tr 5")
                return unionQNamesList
            xsBaseTypeDefinition = xsSimpleTypeDefinition.getPrimitiveType()
        else:
            xsBaseTypeDefinition = self.xsTypeDefinition.getBaseType()
        # if traceToStdout: print("qndf tr 2")
        if xsBaseTypeDefinition is not NULL and xsBaseTypeDefinition != self.xsTypeDefinition: # prevent recursion on anyType (derived from itself)
            # if traceToStdout: print("qndf tr 3")
            return self.modelDocument.modelXbrl.xsTypeDefinitionQName(xsBaseTypeDefinition)
        # if traceToStdout: print("qndf tr 4")
        return None

    @property
    def typeDerivedFrom(self):
        """(ModelType) -- the type(s) that this type is derived from (returns ModelTypes tuple if type is a union)"""
        cdef XSSimpleTypeDefinition *xsSimpleTypeDefinition
        cdef XSSimpleTypeDefinitionList *unionXsTypesList
        cdef XSTypeDefinition *xsBaseTypeDefinition
        cdef XMLSize_t i
        cdef ModelType derivedFromType
        cdef list unionModelTypesList
        if self.xsTypeDefinition.getTypeCategory() == SIMPLE_TYPE:
            xsSimpleTypeDefinition = <XSSimpleTypeDefinition*>self.xsTypeDefinition
            if xsSimpleTypeDefinition.getVariety() == VARIETY_UNION:
                unionXsTypesList = xsSimpleTypeDefinition.getMemberTypes()
                unionModelTypesList = list()
                for i in range(unionXsTypesList.size()):
                    xsSimpleTypeDefinition = unionXsTypesList.elementAt(i)
                    derivedFromType = self.modelDocument.modelXbrl.xsTypeDefinitionType(xsSimpleTypeDefinition)
                    if derivedFromType is not None and derivedFromType not in unionModelTypesList:
                        unionModelTypesList.append(derivedFromType) # deduplicate derivedFromTypes
                return unionModelTypesList
            xsBaseTypeDefinition = xsSimpleTypeDefinition.getPrimitiveType()
        else:
            xsBaseTypeDefinition = self.xsTypeDefinition.getBaseType()
        if xsBaseTypeDefinition is not NULL and xsBaseTypeDefinition != self.xsTypeDefinition: # prevent recursion on anyType (derived from itself)
            return self.modelDocument.modelXbrl.xsTypeDefinitionType(xsBaseTypeDefinition)
        return None

    def __repr__(self):
        return ("modelType[{0}, qname: {1}, derivedFrom: {2}, {3}, line {4}]"
                .format(self.objectIndex, self.qname, self.qnameDerivedFrom,
                        self.modelDocument.basename, self.sourceline))
        
cdef newModelType(ModelDocument modelDocument, XSTypeDefinition *xsTypeDefinition, QName qname):
    cdef ModelType modelType
    modelType = ModelType(modelDocument, qname) # modelType is not a python wrap of cython object, just cython
    modelType.xsTypeDefinition = xsTypeDefinition
    modelType._isAnonymous = xsTypeDefinition.getAnonymous() # need to be cached for when xsModel is in flux
    return modelType

