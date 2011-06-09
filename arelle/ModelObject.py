'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
from arelle import (XmlUtil, XbrlConst, XbrlUtil, UrlUtil, Locale, ModelValue)

# initialize object from an element
def create(modelDocument, element=None, localName=None, namespaceURI=None):
    if element:
        ln = element.localName
        ns = element.namespaceURI
    else:
        ln = localName
        ns = namespaceURI
    modelObject = None
    if ns == XbrlConst.xsd:
        if ln == "element":
            modelObject = ModelConcept(modelDocument, element)
        elif ln == "attribute":
            modelObject = ModelAttribute(modelDocument, element)
        elif ln == "complexType" or ln == "simpleType":
            modelObject = ModelType(modelDocument, element)
        elif ln == "enumeration":
            modelObject = ModelEnumeration(modelDocument, element)
    elif ns == XbrlConst.link and \
         ln == "roleType" or ln == "arcroleType":
        modelObject = ModelRoleType(modelDocument, element)
    return modelObject

def createLink(modelDocument, element):
    return ModelLink(modelDocument, element)

def createLocator(modelDocument, element, modelHref):
    return ModelLocator(modelDocument, element, modelHref)


def createResource(modelDocument, element):
    from arelle import ModelRenderingObject
    return modelDocument.modelXbrl.matchSubstitutionGroup(
        ModelValue.qname(element),
        resourceConstructors)(modelDocument, element)
         
def createRelationship(modelDocument, arcElement, fromModelObject, toModelObject):
    return ModelRelationship(modelDocument, arcElement, fromModelObject, toModelObject)

def createFact(modelDocument, element):
    return ModelFact(modelDocument, element)

def createInlineFact(modelDocument, element):
    return ModelInlineFact(modelDocument, element)

def createContext(modelDocument, element):
    return ModelContext(modelDocument, element)

def createUnit(modelDocument, element):
    return ModelUnit(modelDocument, element)

def createDimensionValue(modelDocument, element):
    return ModelDimensionValue(modelDocument, element)

def createTestcaseVariation(modelDocument, element):
    return ModelTestcaseVariation(modelDocument, element)

class ModelObject:
    def __init__(self, modelDocument, element):
        self.isChanged = False
        self.modelDocument = modelDocument
        self.objectIndex = len(modelDocument.modelXbrl.modelObjects)
        modelDocument.modelXbrl.modelObjects.append(self)
        modelDocument.modelObjects.append(self)
        self.element = element
        
    def __del__(self):
        if self.modelDocument is not None and self.modelDocument.modelXbrl is not None:
            self.modelXbrl.modelObjects[self.objectIndex] = None
        self.modelDocument = None
        self.objectIndex = None
        self.element = None

    def objectId(self,refId=""):
        return "_{0}_{1}".format(refId, self.objectIndex)
    
    @property
    def modelXbrl(self):
        return self.modelDocument.modelXbrl
        
    def attr(self, attrname):
        return self.element.getAttribute(attrname)
    
    # qname of concept of fact or element for all but concept element, type, attr, param, override to the name parameter
    @property
    def qname(self):
        try:
            return self._elementQname
        except AttributeError:
            self._elementQname = ModelValue.qname(self.element)
            return self._elementQname
        
    # qname is overridden for concept, type, attribute, and formula parameter, elementQname is unambiguous
    @property
    def elementQname(self):
        try:
            return self._elementQname
        except AttributeError:
            self._elementQname = ModelValue.qname(self.element)
            return self._elementQname
    
    @property
    def localName(self):
        return self.element.localName
    
    @property
    def parentQname(self):
        try:
            return self._parentQname
        except AttributeError:
            self._parentQname = ModelValue.qname( self.element.parentNode )
            return self._parentQname

    
    @property
    def id(self):
        if self.element.hasAttribute("id"):
            return self.element.getAttribute("id")
        return None
    
    @property
    def document(self):
        return self.modelDocument
    
    def prefixedNameQname(self, prefixedName):
        return ModelValue.qname(self.element, prefixedName)
    
    @property
    def innerText(self):
        return XmlUtil.innerText(self.element)
    
    @property
    def text(self):
        return XmlUtil.text(self.element)
    
    @property
    def elementAttributesTuple(self):
        return tuple((name,value) for name,value in XbrlUtil.attributes(self.modelXbrl, None, self.element))
    
    @property
    def elementAttributesStr(self):
        return ', '.join(["{0}='{1}'".format(name,value) for name,value in XbrlUtil.attributes(self.modelXbrl, None, self.element)])

    def resolveUri(self, hrefObject=None, uri=None, dtsModelXbrl=None):
        if dtsModelXbrl is None:
            dtsModelXbrl = self.modelXbrl
        doc = None
        if hrefObject:
            hrefElt,doc,id = hrefObject
        elif uri:
            url, id = UrlUtil.splitDecodeFragment(uri)
            if url == "":
                doc = self.modelDocument
            else:
                normalizedUrl = self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(
                                   url, 
                                   self.modelDocument.baseForElement(self.element))
                doc = dtsModelXbrl.urlDocs.get(normalizedUrl)
        from arelle import ModelDocument
        if isinstance(doc, ModelDocument.ModelDocument):
            if id is None:
                return doc
            elif id in doc.idObjects:
                return doc.idObjects[id]
            else:
                xpointedElement = XmlUtil.xpointerElement(doc,id)
                # find element
                for docModelObject in doc.modelObjects:
                    if docModelObject.element == xpointedElement:
                        doc.idObjects[id] = docModelObject # cache for reuse
                        return docModelObject
        return None

    def genLabel(self,role=None,fallbackToQname=False,fallbackToXlinkLabel=False,lang=None):
        if role is None: role = XbrlConst.genStandardLabel
        if role == XbrlConst.conceptNameLabelRole: return str(self.qname)
        labelsRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.elementLabel)
        if labelsRelationshipSet:
            label = labelsRelationshipSet.label(self, role, lang)
            if label is not None:
                return label
        if fallbackToQname:
            return str(self.qname)
        elif fallbackToXlinkLabel and hasattr(self,"xlinkLabel"):
            return self.xlinkLabel
        else:
            return None

    
    @property
    def propertyView(self):
        return (("QName", self.qname),
                ("id", self.id))
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))
    
class ModelRoleType(ModelObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        
    @property
    def isArcrole(self):
        return self.element.localName == "arcroleType"
    
    @property
    def roleURI(self):
        return self.element.getAttribute("roleURI")
    
    @property
    def arcroleURI(self):
        return self.element.getAttribute("arcroleURI")
    
    @property
    def cyclesAllowed(self):
        return self.element.getAttribute("cyclesAllowed") if self.element.hasAttribute("cyclesAllowed") else None

    @property
    def definition(self):
        try:
            return self._definition
        except AttributeError:
            definitionElement = XmlUtil.child(self.element, XbrlConst.link,"definition")
            self._definition = XmlUtil.text(definitionElement) if definitionElement else None
            return self._definition

    @property
    def definitionNotStripped(self):
        definitionElement = XmlUtil.child(self.element, XbrlConst.link,"definition")
        return XmlUtil.textNotStripped(definitionElement) if definitionElement else None
    
    @property
    def usedOns(self): 
        try:
            return self._usedOns
        except AttributeError:
            self._usedOns = set(ModelValue.qname(element, XmlUtil.text(element))
                                for element in self.element.getElementsByTagNameNS(XbrlConst.link, "usedOn"))
            return self._usedOns
    
    @property
    def propertyView(self):
        if self.isArcrole:
            return (("arcrole Uri", self.arcroleURI),
                    ("definition", self.definition),
                    ("used on", self.usedOns))
        else:
            return (("role Uri", self.roleURI),
                    ("definition", self.definition),
                    ("used on", self.usedOns))
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format('modelArcroleType' if self.isArcrole else 'modelRoleType', self.objectId(),self.propertyView))

    @property
    def viewConcept(self):  # concept trees view roles as themselves
        return self

class ModelSchemaObject(ModelObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        
    @property
    def name(self):
        return self.element.getAttribute("name") if self.element.hasAttribute("name") else None
    
    @property
    def namespaceURI(self):
        return self.modelDocument.targetNamespace
        
    @property
    def qname(self):
        try:
            return self._qname
        except AttributeError:
            name = self.name
            if self.name:
                prefix = XmlUtil.xmlnsprefix(self.modelDocument.xmlRootElement,self.modelDocument.targetNamespace)
                self._qname =  ModelValue.qname(self.modelDocument.targetNamespace, 
                                                prefix + ":" + name if prefix else name)
            else:
                self._qname = None
            return self._qname
    
    @property
    def isGlobalDeclaration(self):
        parentNode = self.element.parentNode
        return parentNode.namespaceURI == XbrlConst.xsd and parentNode.localName == "schema"

anonymousTypeSuffix = "@anonymousType"

class ModelConcept(ModelSchemaObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        if self.name:  # don't index elements with ref and no name
            self.modelXbrl.qnameConcepts[self.qname] = self
            self.modelXbrl.nameConcepts[self.name].append(self)
            self._baseXsdAttrType = {}
        
    @property
    def abstract(self):
        return self.element.getAttribute("abstract") if self.element.hasAttribute("abstract") else 'false'
    
    @property
    def isAbstract(self):
        return self.abstract == "true"
    
    @property
    def periodType(self):
        return self.element.getAttributeNS(XbrlConst.xbrli, "periodType") if self.element.hasAttributeNS(XbrlConst.xbrli, "periodType") else None
    
    @property
    def balance(self):
        return self.element.getAttributeNS(XbrlConst.xbrli, "balance") if self.element.hasAttributeNS(XbrlConst.xbrli, "balance") else None
    
    @property
    def typeQname(self):
        try:
            return self._typeQname
        except AttributeError:
            if self.element.hasAttribute("type"):
                self._typeQname = self.prefixedNameQname(self.element.getAttribute("type"))
            else:
                # check if anonymous type exists
                typeQname = ModelValue.qname(self.qname.nsname() +  anonymousTypeSuffix)
                if typeQname in self.modelXbrl.qnameTypes:
                    self._typeQname = typeQname
                else:
                    # try substitution group for type
                    subs = self.substitutionGroup
                    if subs:
                        self._typeQname = subs.typeQname
                    else:
                        self._typeQname =  None
            return self._typeQname
        
    @property
    def niceType(self):
        if self.isHypercubeItem: return "Table"
        if self.isDimensionItem: return "Axis"
        if self.typeQname.localName.endswith("ItemType"):
            return self.typeQname.localName[0].upper() + self.typeQname.localName[1:-8]
        niceName = self.typeQname.localName
        return niceName
        
    @property
    def baseXsdType(self):
        try:
            return self._baseXsdType
        except AttributeError:
            typeqname = self.typeQname
            if typeqname.namespaceURI == XbrlConst.xsd:
                return typeqname.localName
            type = self.type
            self._baseXsdType = type.baseXsdType if type else None
            return self._baseXsdType
    
    def baseXsdAttrType(self,attrName):
        try:
            return self._baseXsdAttrType[attrName]
        except KeyError:
            attrType = self.type.baseXsdAttrType(attrName)
            self._baseXsdAttrType[attrName] = attrType
            return attrType
    
    @property
    def baseXbrliType(self):
        try:
            return self._baseXbrliType
        except AttributeError:
            typeqname = self.typeQname
            if typeqname.namespaceURI == XbrlConst.xbrli:
                return typeqname.localName
            self._baseXbrliType = self.type.baseXbrliType if self.type else None
            return self._baseXbrliType
        
    def instanceOfType(self, typeqname):
        if typeqname == self.typeQname:
            return True
        type = self.type
        if type and self.type.isDerivedFrom(typeqname):
            return True
        subs = self.substitutionGroup
        if subs: 
            return subs.instanceOfType(typeqname)
        return False
    
    @property
    def isNumeric(self):
        try:
            return self._isNumeric
        except AttributeError:
            self._isNumeric = XbrlConst.isNumericXsdType(self.baseXsdType)
            return self._isNumeric
    
    @property
    def isFraction(self):
        try:
            return self._isFraction
        except AttributeError:
            self._isFraction = self.baseXbrliType == "fractionItemType"
            return self._isFraction
    
    @property
    def isMonetary(self):
        try:
            return self._isMonetary
        except AttributeError:
            self._isMonetary = self.baseXbrliType == "monetaryItemType"
            return self._isMonetary
    
    @property
    def isShares(self):
        try:
            return self._isShares
        except AttributeError:
            self._isShares = self.baseXbrliType == "sharesItemType"
            return self._isShares
    
    @property
    def isTextBlock(self):
        return self.type.isTextBlock
    
    @property
    def type(self):
        try:
            return self._type
        except AttributeError:
            self._type = self.modelXbrl.qnameTypes.get(self.typeQname)
            return self._type
    
    @property
    def substitutionGroup(self):
        subsgroupqname = self.substitutionGroupQname
        if subsgroupqname is not None:
            return self.modelXbrl.qnameConcepts.get(subsgroupqname)
        return None
        
    @property
    def substitutionGroupQname(self):
        try:
            return self._substitutionGroupQname
        except AttributeError:
            self._substitutionGroupQname = None
            if self.element.hasAttribute("substitutionGroup"):
                self._substitutionGroupQname = self.prefixedNameQname(self.element.getAttribute("substitutionGroup"))
            return self._substitutionGroupQname
        
    @property
    def substitutionGroupQnames(self):   # ordered list of all substitution group qnames
        qnames = []
        subs = self
        subNext = subs.substitutionGroup
        while subNext is not None:
            qnames.append(subNext.qname)
            subs = subNext
            subNext = subs.substitutionGroup
        return qnames
    
    @property
    def nillable(self):
        return self.element.getAttribute("nillable") if self.element.hasAttribute("nillable") else 'false'
        
    @property
    def block(self):
        return self.element.getAttribute("block") if self.element.hasAttribute("block") else None
    
    @property
    def default(self):
        return self.element.getAttribute("default") if self.element.hasAttribute("default") else None
    
    @property
    def fixed(self):
        return self.element.getAttribute("fixed") if self.element.hasAttribute("fixed") else None
    
    @property
    def final(self):
        return self.element.getAttribute("final") if self.element.hasAttribute("final") else None
    
    @property
    def isRoot(self):
        return self.element.parentNode.localName == "schema"
    
    def label(self,preferredLabel=None,fallbackToQname=True,lang=None):
        if preferredLabel is None: preferredLabel = XbrlConst.standardLabel
        if preferredLabel == XbrlConst.conceptNameLabelRole: return str(self.qname)
        labelsRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
        if labelsRelationshipSet:
            label = labelsRelationshipSet.label(self, preferredLabel, lang)
            if label is not None:
                return label
        return str(self.qname) if fallbackToQname else None
    
    def relationshipToResource(self, resourceObject, arcrole):    
        relationshipSet = self.modelXbrl.relationshipSet(arcrole)
        if relationshipSet:
            for modelRel in relationshipSet.fromModelObject(self):
                if modelRel.toModelObject == resourceObject:
                    return modelRel
        return None
    
    @property
    def isItem(self): # true for a substitution for item but not xbrli:item itself
        try:
            return self._isItem
        except AttributeError:
            self._isItem = self.subGroupHeadQname == XbrlConst.qnXbrliItem and self.namespaceURI != XbrlConst.xbrli
            return self._isItem

    @property
    def isTuple(self): # true for a substitution for item but not xbrli:item itself
        try:
            return self._isTuple
        except AttributeError:
            self._isTuple = self.subGroupHeadQname == XbrlConst.qnXbrliTuple and self.namespaceURI != XbrlConst.xbrli
            return self._isTuple
        
    @property
    def isLinkPart(self): # true for a substitution for item but not link:part itself
        try:
            return self._isLinkPart
        except AttributeError:
            self._isLinkPart = self.subGroupHeadQname == XbrlConst.qnLinkPart and self.namespaceURI != XbrlConst.link
            return self._isLinkPart
        
    @property
    def isPrimaryItem(self):
        try:
            return self._isPrimaryItem
        except AttributeError:
            self._isPrimaryItem = self.isItem and not \
            (self.substitutesForQname(XbrlConst.qnXbrldtHypercubeItem) or self.substitutesForQname(XbrlConst.qnXbrldtDimensionItem))
            return self._isPrimaryItem

    @property
    def isDomainMember(self):
        return self.isPrimaryItem   # same definition in XDT
        
    @property
    def isHypercubeItem(self):
        try:
            return self._isHypercubeItem
        except AttributeError:
            self._isHypercubeItem = self.substitutesForQname(XbrlConst.qnXbrldtHypercubeItem)
            return self._isHypercubeItem
        
    @property
    def isDimensionItem(self):
        try:
            return self._isDimensionItem
        except AttributeError:
            self._isDimensionItem = self.substitutesForQname(XbrlConst.qnXbrldtDimensionItem)
            return self._isDimensionItem
        
    @property
    def isTypedDimension(self):
        try:
            return self._isTypedDimension
        except AttributeError:
            self._isTypedDimension = self.isDimensionItem and self.element.hasAttributeNS(XbrlConst.xbrldt,"typedDomainRef")
            return self._isTypedDimension
        
    @property
    def isExplicitDimension(self):
        return self.isDimensionItem and not self.isTypedDimension
    
    @property
    def typedDomainElement(self):
        try:
            return self._typedDomainElement
        except AttributeError:
            self._typedDomainElement = self.resolveUri(uri=self.element.getAttributeNS(XbrlConst.xbrldt,"typedDomainRef"))
            return self._typedDomainElement
        
    def substitutesForQname(self, subsQname):
        subs = self
        subNext = subs.substitutionGroup
        while subNext is not None:
            if subsQname == subs.substitutionGroupQname:
                return True
            subs = subNext
            subNext = subs.substitutionGroup
        return False
        
    @property
    def subGroupHeadQname(self): # true for a substitution but not item itself (differs from w3c definition)
        subs = self
        subNext = subs.substitutionGroup
        while subNext is not None:
            subs = subNext
            subNext = subs.substitutionGroup
        return subs.qname
    
    @property
    def typedDomainRefQname(self):
        if self.element.hasAttributeNS(XbrlConst.xbrldt, "typedDomainRef"):
            return self.prefixedNameQname(self.element.getAttributeNS(XbrlConst.xbrldt, "typedDomainRef"))
        return None

    @property
    def propertyView(self):
        return (("label", self.label(lang=self.modelXbrl.modelManager.defaultLang)),
                ("name", self.name),
                ("id", self.id),
                ("abstract", self.abstract),
                ("type", self.typeQname),
                ("subst grp", self.substitutionGroupQname),
                ("period type", self.periodType) if self.periodType else (),
                ("balance", self.balance) if self.balance else ())
        
    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))

    @property
    def viewConcept(self):
        return self
            
class ModelAttribute(ModelSchemaObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        self.modelXbrl.qnameAttributes[self.qname] = self
        self._baseXsdAttrType = {}
        
    @property
    def typeQname(self):
        if self.element.hasAttribute("type"):
            return self.prefixedNameQname(self.element.getAttribute("type"))
        else:
            # check if anonymous type exists
            typeqname = ModelValue.qname(self.qname.nsname() +  "@anonymousType")
            if typeqname in self.modelXbrl.qnameTypes:
                return typeqname
            # try substitution group for type
            subs = self.substitutionGroup
            if subs:
                return subs.typeQname
            return None
    
    @property
    def type(self):
        try:
            return self._type
        except AttributeError:
            self._type = self.modelXbrl.qnameTypes.get(self.typeQname)
            return self._type
    
    @property
    def baseXsdType(self):
        try:
            return self._baseXsdType
        except AttributeError:
            typeqname = self.typeQname
            if typeqname.namespaceURI == XbrlConst.xsd:
                return typeqname.localName
            type = self.type
            self._baseXsdType = type.baseXsdType if type else None
            return self._baseXsdType
    
    @property
    def isNumeric(self):
        try:
            return self._isNumeric
        except AttributeError:
            self._isNumeric = XbrlConst.isNumericXsdType(self.baseXsdType)
            return self._isNumeric
    
    @property
    def default(self):
        return self.element.getAttribute("default") if self.element.hasAttribute("default") else None
    
    @property
    def fixed(self):
        return self.element.getAttribute("fixed") if self.element.hasAttribute("fixed") else None
    
            
class ModelType(ModelSchemaObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        self.modelXbrl.qnameTypes[self.qname] = self
        
    @property
    def name(self):
        if self.element.hasAttribute("name"):
            return self.element.getAttribute("name")
        # may be anonymous type of parent self.element.tagName
        element = self.element
        while element.nodeType == 1:
            if element.hasAttribute("name"):
                return element.getAttribute("name") + "@anonymousType"
            element = element.parentNode
        return None
    
    @property
    def qnameDerivedFrom(self):
        return self.prefixedNameQname(XmlUtil.descendantAttr(self.element, XbrlConst.xsd, ("extension","restriction"), "base"))
    
    @property
    def baseXsdType(self):
        try:
            return self._baseXsdType
        except AttributeError:
            if self.qname == XbrlConst.qnXbrliDateUnion:
                return "XBRLI_DATEUNION"
            qnameDerivedFrom = self.qnameDerivedFrom
            if qnameDerivedFrom and qnameDerivedFrom.namespaceURI == XbrlConst.xsd:
                self._baseXsdType = qnameDerivedFrom.localName
            else:
                typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
                #assert typeDerivedFrom is not None, _("Unable to determine derivation of {0}").format(qnameDerivedFrom)
                self._baseXsdType = typeDerivedFrom.baseXsdType if typeDerivedFrom else None
            return self._baseXsdType
    
    @property
    def baseXbrliType(self):
        try:
            return self._baseXbrliType
        except AttributeError:
            self._baseXbrliType = None
            if self.qname == XbrlConst.qnXbrliDateUnion:
                return "XBRLI_DATEUNION"
            qnameDerivedFrom = self.qnameDerivedFrom
            if qnameDerivedFrom:
                if qnameDerivedFrom.namespaceURI == XbrlConst.xbrli:  # xbrli type
                    self._baseXbrliType = qnameDerivedFrom.localName
                elif qnameDerivedFrom.namespaceURI == XbrlConst.xsd:    # xsd type
                    self._baseXbrliType = qnameDerivedFrom.localName
                else:
                    typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
                    self._baseXbrliType = typeDerivedFrom.baseXbrliType if typeDerivedFrom else None
            return self._baseXbrliType
    
    @property
    def isTextBlock(self):
        if self.name == "textBlockItemType" and self.modelDocument.targetNamespace.startswith(XbrlConst.usTypesStartsWith):
            return True
        if self.name == "escapedItemType" and self.modelDocument.targetNamespace.startswith(XbrlConst.dtrTypesStartsWith):
            return True
        qnameDerivedFrom = self.qnameDerivedFrom
        if qnameDerivedFrom and (qnameDerivedFrom.namespaceURI in(XbrlConst.xsd,XbrlConst.xbrli)):
            return False
        typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
        return typeDerivedFrom.isTextBlock if typeDerivedFrom else False

    @property
    def isDomainItemType(self):
        if self.name == "domainItemType" and \
           (self.modelDocument.targetNamespace.startswith(XbrlConst.usTypesStartsWith) or
            self.modelDocument.targetNamespace.startswith(XbrlConst.dtrTypesStartsWith)):
            return True
        qnameDerivedFrom = self.qnameDerivedFrom
        if qnameDerivedFrom and (qnameDerivedFrom.namespaceURI in (XbrlConst.xsd,XbrlConst.xbrli)):
            return False
        typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
        return typeDerivedFrom.isDomainItemType if typeDerivedFrom else False
    
    def isDerivedFrom(self, typeqname):
        qnameDerivedFrom = self.qnameDerivedFrom
        if qnameDerivedFrom == typeqname:
            return True
        typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
        return typeDerivedFrom.isDerivedFrom(typeqname) if typeDerivedFrom else False
        
    
    @property
    def attributes(self):
        return XmlUtil.schemaDescendantsNames(self.element, XbrlConst.xsd, "attribute")

    @property
    def elements(self):
        return XmlUtil.schemaDescendantsNames(self.element, XbrlConst.xsd, "element")
    
    @property
    def facets(self):
        try:
            return self._facets
        except AttributeError:
            self._facets = self.constrainingFacets()
            return self._facets
    
    def constrainingFacets(self, facetValues=None):
        facetValues = facetValues if facetValues else {}
        for facetElt in XmlUtil.descendants(self.element, XbrlConst.xsd, (
                    "length", "minLength", "maxLength", "pattern", "whiteSpace",  
                    "maxInclusive", "maxExclusive", "minExclusive", "totalDigits", "fractionDigits")):
            facetName = facetElt.localName
            if facetName not in facetValues:
                facetValues[facetName] = facetElt.getAttribute("value")
        if "enumeration" not in facetValues:
            for facetElt in XmlUtil.descendants(self.element, XbrlConst.xsd, "enumeration"):
                facetValues.setdefault("enumeration",set()).add(facetElt.getAttribute("value"))
        typeDerivedFrom = self.modelXbrl.qnameTypes.get(self.qnameDerivedFrom)
        if typeDerivedFrom:
            typeDerivedFrom.constrainingFacets(facetValues)
        return facetValues
                
        
    
    def baseXsdAttrType(self, attrName):
        attr = XmlUtil.schemaDescendant(self.element, XbrlConst.xsd, "attribute", attrName)
        if attr and attr.hasAttribute("type"):
            qnameAttrType = ModelValue.qname(attr, attr.getAttribute("type"))
            if qnameAttrType and qnameAttrType.namespaceURI == XbrlConst.xsd:
                return qnameAttrType.localName
            typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameAttrType)
            if typeDerivedFrom:
                return typeDerivedFrom.baseXsdType
        return None

    def fixedOrDefaultAttrValue(self, attrName):
        attr = XmlUtil.schemaDescendant(self.element, XbrlConst.xsd, "attribute", attrName)
        if attr:
            if attr.hasAttribute("fixed"):
                return attr.getAttribute("fixed")
            elif attr.hasAttribute("default"):
                return attr.getAttribute("default")
        return None
    
    @property
    def propertyView(self):
        return (("name", self.name),
                ("xsd type", self.baseXsdType),
                ("derived from", self.qnameDerivedFrom),
                ("facits", self.facets))
        
    def __repr__(self):
        return ("modelType[{0}]{1})".format(self.objectId(),self.propertyView))
    
class ModelEnumeration(ModelSchemaObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        
    @property
    def value(self):
        return self.element.getAttribute("value") if self.element.hasAttribute("value") else None
    
class ModelLink(ModelObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        self.labeledResources = defaultdict(list)
        
    @property
    def role(self):
        return self.element.getAttributeNS(XbrlConst.xlink, "role")
        
    def modelResourceOfResourceElement(self,resourceElement):
        label = resourceElement.getAttributeNS(XbrlConst.xlink, "label")
        for modelResource in self.labeledResources[label]:
            if modelResource.element == resourceElement:
                return modelResource
        return None

class ModelResource(ModelObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        if self.xmlLang:
            self.modelXbrl.langs.add(self.xmlLang)
        if self.localName == "label":
            self.modelXbrl.labelroles.add(self.role)
        
    @property
    def role(self):
        return self.element.getAttributeNS(XbrlConst.xlink, "role")
        
    @property
    def xlinkLabel(self):
        return self.element.getAttributeNS(XbrlConst.xlink, "label")

    @property
    def xmlLang(self):
        lang = self.element.getAttribute("xml:lang")
        return lang

    @property
    def text(self):
        return XmlUtil.text(self.element)

    @property
    def textNotStripped(self):
        return XmlUtil.textNotStripped(self.element)

    def viewText(self, labelrole=None, lang=None): # text of label or reference parts
        return " ".join([XmlUtil.text(resourceElt)
                           for resourceElt in [self.element] + XmlUtil.children(self.element,'*','*')
                              if not resourceElt.localName.startswith("URI") and XmlUtil.text(resourceElt)])
    def dereference(self):
        return self
        
class ModelLocator(ModelResource):
    def __init__(self, modelDocument, element, modelHref):
        super().__init__(modelDocument, element)
        self.modelHref = modelHref
    
    def dereference(self):
        # resource is a loc with href document and id modelHref a tuple with href's element, modelDocument, id
        return self.resolveUri(self.modelHref)
    
class RelationStatus:
    Unknown = 0
    EFFECTIVE = 1
    OVERRIDDEN = 2
    PROHIBITED = 3
    INEFFECTIVE = 4
    
class ModelRelationship(ModelObject):
    def __init__(self, modelDocument, arcElement, fromModelObject, toModelObject):
        super().__init__(modelDocument, arcElement)
        self.fromModelObject = fromModelObject
        self.toModelObject = toModelObject
        
    @property
    def fromLabel(self):
        return self.element.getAttributeNS(XbrlConst.xlink, "from")
        
    @property
    def toLabel(self):
        return self.element.getAttributeNS(XbrlConst.xlink, "to")
        
    @property
    def arcrole(self):
        return self.element.getAttributeNS(XbrlConst.xlink, "arcrole")

    @property
    def order(self):
        if not self.element.hasAttribute("order"):
            return 1.0
        try:
            return float(self.element.getAttribute("order"))
        except (ValueError) :
            return float("nan")

    @property
    def priority(self):
        if not self.element.hasAttribute("priority"):
            return 0
        try:
            return int(self.element.getAttribute("priority"))
        except (ValueError) :
            # XBRL validation error needed
            return 0

    @property
    def weight(self):
        if not self.element.hasAttribute("weight"):
            return None
        try:
            return float(self.element.getAttribute("weight"))
        except (ValueError) :
            # XBRL validation error needed
            return float("nan")

    @property
    def use(self):
        return self.element.getAttribute("use") if self.element.hasAttribute("use") else None
    
    @property
    def isProhibited(self):
        return self.use == "prohibited"
    
    @property
    def prohibitedUseSortKey(self):
        return 2 if self.isProhibited else 1
    
    @property
    def preferredLabel(self):
        return self.element.getAttribute("preferredLabel") if self.element.hasAttribute("preferredLabel") else None

    @property
    def variablename(self):
        return self.element.getAttribute("name")

    @property
    def variableQname(self):
        return ModelValue.qname(self.element, self.element.getAttribute("name"), noPrefixIsNoNamespace=True) if self.element.hasAttribute("name") else None

    @property
    def linkrole(self):
        return self.element.parentNode.getAttributeNS(XbrlConst.xlink, "role")
    
    @property
    def linkQname(self):
        return ModelValue.qname(self.element.parentNode)
    
    @property
    def contextElement(self):
        return self.element.getAttributeNS(XbrlConst.xbrldt,"contextElement") if self.element.hasAttributeNS(XbrlConst.xbrldt,"contextElement") else None
    
    @property
    def targetRole(self):
        return self.element.getAttributeNS(XbrlConst.xbrldt,"targetRole") if self.element.hasAttributeNS(XbrlConst.xbrldt,"targetRole") else None
    
    @property
    def consecutiveLinkrole(self):
        return self.targetRole if self.targetRole else self.linkrole
    
    @property
    def isUsable(self):
        return self.element.getAttributeNS(XbrlConst.xbrldt,"usable") == "true" if self.element.hasAttributeNS(XbrlConst.xbrldt,"usable") else True
    
    @property
    def closed(self):
        return self.element.getAttributeNS(XbrlConst.xbrldt,"closed") if self.element.hasAttributeNS(XbrlConst.xbrldt,"closed") else "false"

    @property
    def isComplemented(self):
        try:
            return self._isComplemented
        except AttributeError:
            self._isComplemented = self.element.getAttribute("complement") == "true" if self.element.hasAttribute("complement") else False
            return self._isComplemented
    
    @property
    def isCovered(self):
        try:
            return self._isCovered
        except AttributeError:
            self._isCovered = self.element.getAttribute("cover") == "true" if self.element.hasAttribute("cover") else False
            return self._isCovered
    
    @property
    def isClosed(self):
        try:
            return self._isClosed
        except AttributeError:
            self._isClosed = self.element.getAttributeNS(XbrlConst.xbrldt,"closed") == "true" if self.element.hasAttributeNS(XbrlConst.xbrldt,"closed") else False
            return self._isClosed

    @property
    def usable(self):
        if self.arcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember):
            return self.element.getAttributeNS(XbrlConst.xbrldt,"usable") if self.element.hasAttributeNS(XbrlConst.xbrldt,"usable") else "true"
        return None
        
    @property
    def equivalenceKey(self):

        return (self.qname, 
                self.linkQname,
                self.linkrole,  # needed when linkrole=None merges multiple links
                self.fromModelObject.objectIndex if self.fromModelObject else -1, 
                self.toModelObject.objectIndex if self.toModelObject else -1,
                self.order, 
                self.weight, 
                self.preferredLabel) + \
                XbrlUtil.attributes(self.modelXbrl, None, self.element,
                    exclusions=(XbrlConst.xlink, "use","priority","order","weight","preferredLabel"))
                
    def isIdenticalTo(self, otherModelRelationship):
        return (otherModelRelationship and
                self.element == otherModelRelationship.element and
                self.fromModelObject and otherModelRelationship.fromModelObject and
                self.toModelObject and otherModelRelationship.toModelObject and
                self.fromModelObject.element == otherModelRelationship.fromModelObject.element and
                self.toModelObject.element == otherModelRelationship.toModelObject.element)

    def priorityOver(self, otherModelRelationship):
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
                ("contextElement", self.contextElement)  if self.arcrole in (self.arcrole == XbrlConst.all, XbrlConst.notAll)  else (),
                ("closed", self.closed) if self.arcrole in (XbrlConst.all, XbrlConst.notAll)  else (),
                ("usable", self.usable) if self.arcrole == XbrlConst.domainMember  else (),
                ("targetRole", self.targetRole) if self.arcrole.startswith(XbrlConst.dimStartsWith) else (),
                ("order", self.order),
                ("priority", self.priority))
        
    def __repr__(self):
        return ("modelRelationship[{0}]{1})".format(self.objectId(),self.propertyView))

    @property
    def viewConcept(self):
        if isinstance(self.toModelObject, ModelConcept):
            return self.toModelObject
        elif isinstance(self.fromModelObject, ModelConcept):
            return self.fromModelObject
        return None
           
class ModelFact(ModelObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        self.modelTupleFacts = []
        
    def __del__(self):
        super().__del__()
        self.modelTupleFacts = []
        
    @property
    def concept(self):
        concept = self.modelXbrl.qnameConcepts.get(self.qname)
        return concept
        
    @property
    def contextID(self):
        return self.element.getAttribute("contextRef") if self.element.hasAttribute("contextRef") else None

    @property
    def context(self):
        context = self.modelXbrl.contexts.get(self.contextID)
        return context
    
    @property
    def unit(self):
        return self.modelXbrl.units.get(self.unitID)
    
    @property
    def unitID(self):
        return self.element.getAttribute("unitRef") if self.element.hasAttribute("unitRef") else None

    @property
    def isItem(self):
        try:
            return self._isItem
        except AttributeError:
            concept = self.concept
            self._isItem = concept and concept.isItem
            return self._isItem

    @property
    def isTuple(self):
        try:
            return self._isTuple
        except AttributeError:
            concept = self.concept
            self._isTuple = concept and concept.isTuple
            return self._isTuple

    @property
    def isNumeric(self):
        try:
            return self._isNumeric
        except AttributeError:
            concept = self.concept
            self._isNumeric = concept and concept.isNumeric
            return self._isNumeric

    @property
    def isFraction(self):
        try:
            return self._isFraction
        except AttributeError:
            concept = self.concept
            self._isFraction = concept and concept.isFraction
            return self._isFraction
        
    @property
    def parentElement(self):
        return XmlUtil.parent(self.element)

    @property
    def ancestorQnames(self):
        try:
            return self._ancestorQnames
        except AttributeError:
            self._ancestorQnames = set( ModelValue.qname(ancestor) for ancestor in XmlUtil.ancestors(self.element) )
            return self._ancestorQnames

    @property
    def decimals(self):
        try:
            return self._decimals
        except AttributeError:
            if self.element.hasAttribute("decimals"):
                self._decimals = self.element.getAttribute("decimals")
            else:   #check for fixed decimals on type
                type = self.concept.type
                self._decimals = type.fixedOrDefaultAttrValue("decimals") if type else None
            return  self._decimals

    @property
    def precision(self):
        try:
            return self._precision
        except AttributeError:
            if self.element.hasAttribute("precision"):
                self._precision = self.element.getAttribute("precision")
            else:   #check for fixed decimals on type
                type = self.concept.type
                self._precision = type.fixedOrDefaultAttrValue("precision") if type else None
            return  self._precision

    @property
    def xmlLang(self):
        lang = self.element.getAttribute("xml:lang")
        if lang == "" and self.modelXbrl.modelManager.validateDisclosureSystem:
            concept = self.concept
            if concept is not None and not concept.isNumeric:
                lang = self.modelXbrl.modelManager.disclosureSystem.defaultXmlLang
        return lang
    
    @property
    def xsiNil(self):
        return self.element.getAttributeNS(XbrlConst.xsi,"nil") if self.element.hasAttributeNS(XbrlConst.xsi,"nil") else "false"
    
    @property
    def isNil(self):
        return self.xsiNil == "true"
    
    @property
    def value(self):
        v = self.text
        if len(v) == 0:
            if self.concept.default is not None:
                v = self.concept.default
            elif self.concept.fixed is not None:
                v = self.concept.fixed
        return v
    
    @property
    def fractionValue(self):
        return (XmlUtil.text(XmlUtil.child(self.element, None, "numerator")),
                XmlUtil.text(XmlUtil.child(self.element, None, "denominator")))
    
    @property
    def effectiveValue(self):
        concept = self.concept
        if not concept or concept.isTuple:
            return None
        if self.isNil:
            return "(nil)"
        if concept.isNumeric:
            val = self.value
            try:
                num = float(val)
                dec = self.decimals
                if dec is None or dec == "INF":
                    dec = len(val.partition(".")[2])
                else:
                    dec = int(dec)
                return Locale.format(self.modelXbrl.locale, "%.*f", (dec, num), True)
            except ValueError: 
                return "(error)"
        return self.value

    @property
    def vEqValue(self): #v-equals value (numeric or string)
        if self.concept.isNumeric:
            return float(self.value)
        return self.value
    
    def isVEqualTo(self, other):
        if self.isTuple or other.isTuple:
            return False
        if self.isNil:
            return other.isNil
        if other.isNil:
            return False
        if not self.context.isEqualTo(other.context):
            return False
        if self.concept.isNumeric:
            if other.concept.isNumeric:
                if not self.unit.isEqualTo(other.unit):
                    return False
                return float(self.value) == float(other.value)
            else:
                return False
        return self.value.strip() == other.value.strip()

    @property
    def propertyView(self):
        try:
            concept = self.modelXbrl.qnameConcepts[self.qname]
            lbl = (("label", concept.label(lang=self.modelXbrl.modelManager.defaultLang)),)
        except KeyError:
            lbl = (("name", self.qname),)
        return lbl + (
               (("contextRef", self.contextID, self.context.propertyView),
                ("unitRef", self.unitID, self.unit.propertyView if self.isNumeric else ()),
                ("decimals", self.decimals),
                ("precision", self.precision),
                ("xsi:nil", self.xsiNil),
                ("value", self.effectiveValue.strip()))
                if self.isItem else () )
        
    def __repr__(self):
        return ("fact({0}{1}{2}, '{3}')".format(
                self.qname, 
                ', ' + self.contextID if self.element.hasAttribute("contextRef") else '', 
                ', ' + self.unitID if self.element.hasAttribute("unitRef") else '', 
                self.effectiveValue.strip() if self.isItem else '(tuple)'))
    
    @property
    def viewConcept(self):
        return self.concept

class ModelInlineFact(ModelFact):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        
    @property
    def qname(self):
        return self.prefixedNameQname(self.element.getAttribute("name")) if self.element.hasAttribute("name") else None

    @property
    def contextID(self):
        return self.element.getAttribute("contextRef") if self.element.hasAttribute("contextRef") else None

    @property
    def unitID(self):
        return self.element.getAttribute("unitRef") if self.element.hasAttribute("unitRef") else None

    @property
    def sign(self):
        return self.element.getAttribute("sign")
    
    @property
    def tupleID(self):
        try:
            return self._tupleId
        except AttributeError:
            self._tupleId = self.element.getAttribute("tupleID") if self.element.hasAttribute("tupleID") else None
            return self._tupleId
    
    @property
    def tupleRef(self):
        try:
            return self._tupleRef
        except AttributeError:
            self._tupleRef = self.element.getAttribute("tupleRef") if self.element.hasAttribute("tupleRef") else None
            return self._tupleRef

    @property
    def order(self):
        try:
            return self._order
        except AttributeError:
            try:
                orderAttr = self.element.getAttribute("order") if self.element.hasAttribute("order") else None
                self._order = float(orderAttr)
            except ValueError:
                self._order = None
            return self._order

    @property
    def footnoteRefs(self):
        return self.element.getAttribute("footnoteRefs").split()

    @property
    def format(self):
        return self.element.getAttribute("format")

    @property
    def scale(self):
        return self.element.getAttribute("scale")
    
    def transformedValue(self):
        num = 0
        negate = -1 if self.sign else 1
        mult = 1
        decSep = "," if self.format.endswith("comma") else "."
        for c in self.text:
            if c == decSep:
                mult = 0.1
            elif c.isnumeric():
                if mult >= 1:
                    num = num * 10 + int(c)
                else:
                    num += int(c) * mult
                    mult *= .1
        try:
            num *= 10 ** int(self.scale)
        except ValueError:
            pass
        return "{0}".format(num * negate)
    
    @property
    def value(self):
        if self.element.localName == "nonNumeric" or self.element.localName == "tuple":
            return XmlUtil.innerText(self.element, ixExclude=True)
        else:
            return self.transformedValue()

    @property
    def propertyView(self):
        if self.element.localName == "nonFraction" or self.element.localName == "fraction":
            numProperties = (("format", self.format),
                ("scale", self.scale),
                ("html value", self.innerText))
        else:
            numProperties = ()
        return super(ModelInlineFact,self).propertyView + \
               numProperties
        
    def __repr__(self):
        return ("modelInlineFact[{0}]{1})".format(self.objectId(),self.propertyView))
               
class ModelContext(ModelObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        self.segDimValues = {}
        self.scenDimValues = {}
        self.qnameDims = {}
        self.errorDimValues = []
        self.segNonDimValues = []
        self.scenNonDimValues = []
        self._isEqualTo = {}
        
    def __del__(self):
        super().__del__()
        self.segDimValues = None
        self.scenDimValues = None
        self.qnameDims = None
        self.errorDimValues = None
        self.segNonDimValues = None
        self.scenNonDimValues = None
        self._isEqualTo = None

    @property
    def isStartEndPeriod(self):
        try:
            return self._isStartEndPeriod
        except AttributeError:
            self._isStartEndPeriod = XmlUtil.hasChild(self.period, XbrlConst.xbrli, ("startDate","endDate"))
            return self._isStartEndPeriod
                                
    @property
    def isInstantPeriod(self):
        try:
            return self._isInstantPeriod
        except AttributeError:
            self._isInstantPeriod = XmlUtil.hasChild(self.period, XbrlConst.xbrli, "instant")
            return self._isInstantPeriod

    @property
    def isForeverPeriod(self):
        try:
            return self._isForeverPeriod
        except AttributeError:
            self._isForeverPeriod = XmlUtil.hasChild(self.period, XbrlConst.xbrli, "forever")
            return self._isForeverPeriod

    @property
    def startDatetime(self):
        try:
            return self._startDatetime
        except AttributeError:
            self._startDatetime = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, "startDate"))
            return self._startDatetime

    @property
    def endDatetime(self):
        try:
            return self._endDatetime
        except AttributeError:
            self._endDatetime = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, ("endDate","instant")), addOneDay=True)
            return self._endDatetime
        
    @property
    def instantDatetime(self):
        try:
            return self._instantDatetime
        except AttributeError:
            self._instantDatetime = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, "instant"), addOneDay=True)
            return self._instantDatetime
    
    @property
    def period(self):
        try:
            return self._period
        except AttributeError:
            self._period = XmlUtil.child(self.element, XbrlConst.xbrli, "period")
            return self._period

    @property
    def entity(self):
        try:
            return self._entity
        except AttributeError:
            self._entity = XmlUtil.child(self.element, XbrlConst.xbrli, "entity")
            return self._entity

    @property
    def entityIdentifierElement(self):
        try:
            return self._entityIdentifierElement
        except AttributeError:
            self._entityIdentifierElement = XmlUtil.child(self.entity, XbrlConst.xbrli, "identifier")
            return self._entityIdentifierElement

    @property
    def entityIdentifier(self):
        return (self.entityIdentifierElement.getAttribute("scheme"),
                XmlUtil.text(self.entityIdentifierElement))
    @property
    def hasSegment(self):
        return XmlUtil.hasChild(self.entity, XbrlConst.xbrli, "segment")

    @property
    def segment(self):
        return XmlUtil.child(self.entity, XbrlConst.xbrli, "segment")

    @property
    def hasScenario(self):
        return XmlUtil.hasChild(self.element, XbrlConst.xbrli, "scenario")
    
    @property
    def scenario(self):
        return XmlUtil.child(self.element, XbrlConst.xbrli, "scenario")
    
    def dimValues(self, contextElement):
        if contextElement == "segment":
            return self.segDimValues
        elif contextElement == "scenario":
            return self.scenDimValues
        return {}
    
    def hasDimension(self, dimQname):
        return dimQname in self.qnameDims
    
    # returns ModelDimensionValue for instance dimensions, else QName for defaults
    def dimValue(self, dimQname):
        if dimQname in self.qnameDims:
            return self.qnameDims[dimQname]
        elif dimQname in self.modelXbrl.qnameDimensionDefaults:
            return self.modelXbrl.qnameDimensionDefaults[dimQname]
        return None
    
    def dimMemberQname(self, dimQname, includeDefaults=False):
        dimValue = self.dimValue(dimQname)
        if isinstance(dimValue, ModelDimensionValue) and dimValue.isExplicit:
            return dimValue.memberQname
        elif isinstance(dimValue, ModelValue.QName):
            return dimValue
        if not dimValue and includeDefaults and dimQname in self.modelXbrl.qnameDimensionDefaults:
            return self.modelXbrl.qnameDimensionDefaults[dimQname]
        return None
    
    @property
    def dimAspects(self):
        return set(self.qnameDims.keys() | self.modelXbrl.qnameDimensionDefaults.keys())
    
    def nonDimValues(self, contextElement):
        from arelle.ModelFormulaObject import Aspect
        if contextElement in ("segment", Aspect.NON_XDT_SEGMENT):
            return self.segNonDimValues
        elif contextElement in ("scenario", Aspect.NON_XDT_SCENARIO):
            return self.scenNonDimValues
        elif contextElement == Aspect.COMPLETE_SEGMENT and self.hasSegment:
            return XmlUtil.children(self.segment, None, "*")
        elif contextElement == Aspect.COMPLETE_SCENARIO and self.hasScenario:
            return XmlUtil.children(self.scenario, None, "*")
        return []
    
    def isPeriodEqualTo(self, cntx2):
        if self.isForeverPeriod:
            return cntx2.isForeverPeriod
        elif self.isStartEndPeriod:
            if not cntx2.isStartEndPeriod:
                return False
            return self.startDatetime == cntx2.startDatetime and self.endDatetime == cntx2.endDatetime
        elif self.isInstantPeriod:
            if not cntx2.isInstantPeriod:
                return False
            return self.instantDatetime == cntx2.instantDatetime
        else:
            return False
        
    def isEntityIdentifierEqualTo(self, cntx2):
        return self.entityIdentifier == cntx2.entityIdentifier
    
    def isEqualTo(self, cntx2, dimensionalAspectModel=None):
        if dimensionalAspectModel is None: dimensionalAspectModel = self.modelXbrl.hasXDT
        try:
            return self._isEqualTo[(cntx2,dimensionalAspectModel)]
        except KeyError:
            result = self.isEqualTo_(cntx2, dimensionalAspectModel)
            self._isEqualTo[(cntx2,dimensionalAspectModel)] = result
            return result
        
    def isEqualTo_(self, cntx2, dimensionalAspectModel):
        if not self.isPeriodEqualTo(cntx2) or not self.isEntityIdentifierEqualTo(cntx2):
            return False
        if dimensionalAspectModel:
            if self.qnameDims.keys() != cntx2.qnameDims.keys():
                return False
            for dimQname, ctx1Dim in self.qnameDims.items():
                if not ctx1Dim.isEqualTo(cntx2.qnameDims[dimQname]):
                    return False
            for nonDimVals1, nonDimVals2 in ((self.segNonDimValues,cntx2.segNonDimValues),
                                             (self.scenNonDimValues,cntx2.scenNonDimValues)):
                if len(nonDimVals1) !=  len(nonDimVals2):
                    return False
                for i, nonDimVal1 in enumerate(nonDimVals1):
                    if not XbrlUtil.sEqual(self.modelXbrl, nonDimVal1, nonDimVals2[i]):
                        return False                    
        else:
            if self.hasSegment:
                if not cntx2.hasSegment:
                    return False
                if not XbrlUtil.sEqual(self.modelXbrl, self.segment, cntx2.segment):
                    return False
            elif cntx2.hasSegment:
                return False
    
            if self.hasScenario:
                if not cntx2.hasScenario:
                    return False
                if not XbrlUtil.sEqual(self.modelXbrl, self.scenario, cntx2.scenario):
                    return False
            elif cntx2.hasScenario:
                return False
        
        return True

    @property
    def propertyView(self):
        scheme, entityId = self.entityIdentifier
        return (("entity", entityId, entityId, (("scheme", scheme),)),
                (("forever", "") if self.isForeverPeriod else
                  (("instant", str(self.instantDatetime)) if self.isInstantPeriod else
                   (("startDate", str(self.startDatetime)),("endDate",str(self.endDatetime))))),
                ("dimensions", "({0})".format(len(self.qnameDims)),
                  tuple(mem.propertyView for dim,mem in sorted(self.qnameDims.items())))
                  if self.qnameDims else (),
                )

def measuresOf(parent):
    return sorted([ModelValue.qname(m, XmlUtil.text(m)) 
                   for m in parent.getElementsByTagNameNS(XbrlConst.xbrli,"measure")])

def measuresStr(m):
    return m.localName if m.namespaceURI in (XbrlConst.xbrli, XbrlConst.iso4217) else str(m)


class ModelDimensionValue(ModelObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        
       
    @property
    def dimensionQname(self):
        return self.prefixedNameQname(self.element.getAttribute("dimension"))
        
    @property
    def dimension(self):
        try:
            return self._dimension
        except AttributeError:
            self._dimension = self.modelXbrl.qnameConcepts.get(self.dimensionQname)
            return  self._dimension
        
    @property
    def isExplicit(self):
        return self.element.localName == "explicitMember"
    
    @property
    def typedMember(self):
        return self.element

    @property
    def isTyped(self):
        return self.element.localName == "typedMember"

    @property
    def memberQname(self):
        return self.prefixedNameQname(self.text)
        
    @property
    def member(self):
        try:
            return self._member
        except AttributeError:
            self._member = self.modelXbrl.qnameConcepts.get(self.memberQname)
            return  self._member
        
    def isEqualTo(self, other):
        if isinstance(other, ModelValue.QName):
            return self.isExplicit and self.memberQname == other
        elif other is None:
            return False
        elif self.isExplicit:
            return self.memberQname == other.memberQname
        else:
            return XbrlUtil.nodesCorrespond(self.modelXbrl, self.typedMember, other.typedMember)
        
    @property
    def contextElement(self):
        return self.element.parentNode.localName
    
    @property
    def propertyView(self):
        if self.isExplicit:
            return (str(self.dimensionQname),str(self.memberQname))
        else:
            return (str(self.dimensionQname),XmlUtil.child(self.element).toxml())
        
class ModelUnit(ModelObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        
    @property
    def measures(self):
        try:
            return self._measures
        except AttributeError:
            if self.isDivide:
                self._measures = (measuresOf(XmlUtil.descendant(self.element, XbrlConst.xbrli, "unitNumerator")),
                                  measuresOf(XmlUtil.descendant(self.element, XbrlConst.xbrli, "unitDenominator")))
            else:
                self._measures = (measuresOf(self.element),[])
            return self._measures

    @property
    def isDivide(self):
        return XmlUtil.hasChild(self.element, XbrlConst.xbrli, "divide")
    
    @property
    def isSingleMeasure(self):
        measures = self.measures
        return len(measures[0]) == 1 and len(measures[1]) == 0
    
    def isEqualTo(self, unit2):
        '''
        meas1 = self.measures
        meas2 = unit2.measures
        num1 = list(meas1[0])
        denom1 = list(meas1[1])
        num2 = list(meas2[0])
        denom2 = list(meas2[1])
        num1.sort()
        num2.sort()
        denom1.sort()
        denom2.sort()
        return num1 == num2 and denom1 == denom2
        '''
        return self.measures == unit2.measures
    
    @property
    def value(self):
        mul, div = self.measures
        return ' '.join([measuresStr(m) for m in mul] + (['/'] + [measuresStr(d) for d in div] if div else []))

    @property
    def propertyView(self):
        if self.isDivide:
            return tuple(('mul',m) for m in self.measures[0]) + \
                   tuple(('div',d) for d in self.measures[1]) 
        else:
            return tuple(('',m) for m in self.measures[0])

class ModelTestcaseVariation(ModelObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        self.status = ""
        self.actual = []
        self.assertions = None

    @property
    def name(self):
        if self.element.hasAttribute("name"):
            return self.element.getAttribute("name")
        for nameElement in self.element.getElementsByTagName(
             "name" if self.element.localName != "testcase" else "number"):
            return XmlUtil.innerText(nameElement)
        return None

    @property
    def description(self):
        for nameElement in self.element.getElementsByTagName("description"):
            return XmlUtil.innerText(nameElement)
        return None

    @property
    def readMeFirstUris(self):
        try:
            return self._readMeFirstUris
        except AttributeError:
            self._readMeFirstUris = []
            for anElement in self.element.getElementsByTagName("*"):
                if anElement.getAttribute("readMeFirst") == "true":
                    if anElement.hasAttributeNS(XbrlConst.xlink,"href"):
                        uri = anElement.getAttributeNS(XbrlConst.xlink,"href")
                    else:
                        uri = XmlUtil.innerText(anElement)
                    if anElement.hasAttribute("name"):
                        self._readMeFirstUris.append( (ModelValue.qname(anElement, anElement.getAttribute("name")), uri) )
                    elif anElement.hasAttribute("dts"):
                        self._readMeFirstUris.append( (anElement.getAttribute("dts"), uri) )
                    else:
                        self._readMeFirstUris.append(uri)
            return self._readMeFirstUris
    
    @property
    def parameters(self):
        try:
            return self._parameters
        except AttributeError:
            self._parameters = dict([
                (ModelValue.qname(paramElt, paramElt.getAttribute("name")),
                 (ModelValue.qname(paramElt, paramElt.getAttribute("datatype")),paramElt.getAttribute("value"))) 
                for paramElt in XmlUtil.descendants(self.element, self.element.namespaceURI, "parameter")])
            return self._parameters
    
    @property
    def resultIsVersioningReport(self):
        for resultElt in self.element.getElementsByTagName("result"):
            for versReportElt in resultElt.getElementsByTagName("versioningReport"):
                return True
        return False
        
    @property
    def versioningReportUri(self):
        for versReportElt in self.element.getElementsByTagName("versioningReport"):
            return XmlUtil.text(versReportElt)
        return None
    @property
    def resultIsXbrlInstance(self):
        for resultElt in self.element.getElementsByTagName("result"):
            for resultInstanceElt in resultElt.getElementsByTagName("instance"):
                return True
        return False
        
    @property
    def resultXbrlInstanceUri(self):
        for resultElt in self.element.getElementsByTagName("result"):
            for resultInstanceElt in resultElt.getElementsByTagName("instance"):
                return XmlUtil.text(resultInstanceElt)
        return None
    
    
    @property
    def cfcnCall(self):
        # tuple of (expression, element holding the expression)
        try:
            return self._cfcnCall
        except AttributeError:
            self._cfcnCall = None
            for callElement in self.element.getElementsByTagNameNS(XbrlConst.cfcn, "call"):
                self._cfcnCall = (XmlUtil.innerText(callElement), callElement)
                break
            return self._cfcnCall
    
    @property
    def cfcnTest(self):
        # tuple of (expression, element holding the expression)
        try:
            return self._cfcnTest
        except AttributeError:
            self._cfcnTest = None
            for testElement in self.element.getElementsByTagNameNS(XbrlConst.cfcn, "test"):
                self._cfcnTest = (XmlUtil.innerText(testElement), testElement)
                break
            return self._cfcnTest
    
    @property
    def expected(self):
        if self.element.localName == "testcase":
            return self.document.basename[:4]   #starts with PASS or FAIL
        for errorElement in self.element.getElementsByTagName("error"):
            return ModelValue.qname(errorElement, XmlUtil.innerText(errorElement))
        for versioningReport in self.element.getElementsByTagName("versioningReport"):
            return XmlUtil.innerText(versioningReport)
        for resultElement in self.element.getElementsByTagName("result"):
            expected = resultElement.getAttribute("expected")
            if expected != "":
                return expected
            for assertElement in resultElement.getElementsByTagName("assert"):
                num = assertElement.getAttribute("num")
                if len(num) == 5:
                    return "EFM.{0}.{1}.{2}".format(num[0],num[1:3],num[3:6])
            asserTests = {}
            for atElt in resultElement.getElementsByTagName("assertionTests"):
                try:
                    asserTests[atElt.getAttribute("assertionID")] = (int(atElt.getAttribute("countSatisfied")),int(atElt.getAttribute("countNotSatisfied")))
                except ValueError:
                    pass
            if asserTests:
                return asserTests
                
        return None

    @property
    def propertyView(self):
        assertions = []
        for assertionElement in self.element.getElementsByTagName("assertionTests"):
            assertions.append(("assertion",assertionElement.getAttribute("assertionID")))
            assertions.append(("   satisfied", assertionElement.getAttribute("countSatisfied")))
            assertions.append(("   not sat.", assertionElement.getAttribute("countNotSatisfied")))
        '''
        for assertionElement in self.element.getElementsByTagName("assert"):
            efmNum = assertionElement.getAttribute("num")
            assertions.append(("assertion",
                               "EFM.{0}.{1}.{2}".format(efmNum[0], efmNum[1:2], efmNum[3:4])))
            assertions.append(("   not sat.", "1"))
        '''
        readMeFirsts = [("readFirst", readMeFirstUri) for readMeFirstUri in self.readMeFirstUris]
        parameters = []
        if len(self.parameters) > 0: parameters.append(("parameters", None))
        for pName, pTypeValue in self.parameters.items():
            parameters.append((pName,pTypeValue[1]))
        return [("id", self.id),
                ("name", self.name),
                ("description", self.description)] + \
                readMeFirsts + \
                parameters + \
               [("status", self.status),
                ("call", self.cfcnCall[0]) if self.cfcnCall else (),
                ("test", self.cfcnTest[0]) if self.cfcnTest else (),
                ("expected", self.expected) if self.expected else (),
                ("actual", " ".join(str(i) for i in self.actual) if len(self.actual) > 0 else ())] + \
                assertions
        
    def __repr__(self):
        return ("modelTestcaseVariation[{0}]{1})".format(self.objectId(),self.propertyView))

resourceConstructors = {
     None: ModelResource
    }
