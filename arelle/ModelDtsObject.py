'''
Created on Oct 5, 2010
Refactored from ModelObject on Jun 11, 2011

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
from lxml import etree
import decimal
from arelle import (XmlUtil, XbrlConst, XbrlUtil, UrlUtil, Locale, ModelValue, XmlValidate)
from arelle.ModelObject import ModelObject

class ModelRoleType(ModelObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        
    @property
    def isArcrole(self):
        return self.localName == "arcroleType"
    
    @property
    def roleURI(self):
        return self.get("roleURI")
    
    @property
    def arcroleURI(self):
        return self.get("arcroleURI")
    
    @property
    def cyclesAllowed(self):
        return self.get("cyclesAllowed")

    @property
    def definition(self):
        try:
            return self._definition
        except AttributeError:
            definition = XmlUtil.child(self, XbrlConst.link, "definition")
            self._definition = definition.elementText.strip() if definition is not None else None
            return self._definition

    @property
    def definitionNotStripped(self):
        definition = XmlUtil.child(self, XbrlConst.link, "definition")
        return definition.elementText if definition is not None else None
    
    @property
    def usedOns(self): 
        try:
            return self._usedOns
        except AttributeError:
            XmlValidate.validate(self.modelXbrl, self)
            self._usedOns = set(usedOn.xValue
                                for usedOn in self.iterdescendants("{http://www.xbrl.org/2003/linkbase}usedOn")
                                if isinstance(usedOn,ModelObject))
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
    def init(self, modelDocument):
        super().init(modelDocument)
        
    @property
    def name(self):
        return self.getStripped("name")
    
    @property
    def qname(self):
        try:
            return self._xsdQname
        except AttributeError:
            name = self.name
            if self.name:
                if self.parentQname == XbrlConst.qnXsdSchema or self.isQualifiedForm:
                    prefix = XmlUtil.xmlnsprefix(self.modelDocument.xmlRootElement,self.modelDocument.targetNamespace)
                    self._xsdQname = ModelValue.QName(prefix, self.modelDocument.targetNamespace, name)
                else:
                    self._xsdQname = ModelValue.QName(None, None, name)
            else:
                self._xsdQname = None
            return self._xsdQname
    
    @property
    def isGlobalDeclaration(self):
        parent = self.getparent()
        return parent.namespaceURI == XbrlConst.xsd and parent.localName == "schema"

anonymousTypeSuffix = "@anonymousType"

class ModelConcept(ModelSchemaObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        if self.name:  # don't index elements with ref and no name
            self.modelXbrl.qnameConcepts[self.qname] = self
            self.modelXbrl.nameConcepts[self.name].append(self)
        self._baseXsdAttrType = {}
        
    @property
    def abstract(self):
        return self.get("abstract") if self.get("abstract") else 'false'
    
    @property
    def isAbstract(self):
        return self.abstract == "true"
    
    @property
    def periodType(self):
        return self.get("{http://www.xbrl.org/2003/instance}periodType")
    
    @property
    def balance(self):
        return self.get("{http://www.xbrl.org/2003/instance}balance")
    
    @property
    def typeQname(self):
        try:
            return self._typeQname
        except AttributeError:
            if self.get("type"):
                self._typeQname = self.prefixedNameQname(self.get("type"))
            else:
                # check if anonymous type exists (clark qname tag + suffix)
                qn = self.qname
                if qn is not None:
                    typeQname = ModelValue.QName(qn.prefix, qn.namespaceURI, qn.localName + anonymousTypeSuffix)
                else:
                    typeQname = None
                if typeQname in self.modelXbrl.qnameTypes:
                    self._typeQname = typeQname
                else:
                    # try substitution group for type
                    subs = self.substitutionGroup
                    if subs is not None:
                        self._typeQname = subs.typeQname
                    else:
                        self._typeQname =  XbrlConst.qnXsdDefaultType
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
            if typeqname is not None and typeqname.namespaceURI == XbrlConst.xsd:
                self._baseXsdType = typeqname.localName
            else:
                type = self.type
                self._baseXsdType = type.baseXsdType if type is not None else "anyType"
            return self._baseXsdType
        
    @property
    def facets(self):
        return self.type.facets if self.type is not None else None
    
    ''' unused, remove???
    def baseXsdAttrType(self,attrName):
        try:
            return self._baseXsdAttrType[attrName]
        except KeyError:
            if self.type is not None:
                attrType = self.type.baseXsdAttrType(attrName)
            else:
                attrType = "anyType"
            self._baseXsdAttrType[attrName] = attrType
            return attrType
    '''
    
    @property
    def baseXbrliType(self):
        try:
            return self._baseXbrliType
        except AttributeError:
            typeqname = self.typeQname
            if typeqname is not None and typeqname.namespaceURI == XbrlConst.xbrli:
                return typeqname.localName
            self._baseXbrliType = self.type.baseXbrliType if self.type is not None else None
            return self._baseXbrliType
        
    def instanceOfType(self, typeqname):
        if typeqname == self.typeQname:
            return True
        type = self.type
        if type is not None and self.type.isDerivedFrom(typeqname):
            return True
        subs = self.substitutionGroup
        if subs is not None: 
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
            if self.get("substitutionGroup"):
                self._substitutionGroupQname = self.prefixedNameQname(self.get("substitutionGroup"))
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
    def isQualifiedForm(self): # used only in determining qname, which itself is cached
        if self.get("form") is not None: # form is almost never used
            return self.get("form") == "qualified"
        return self.modelDocument.isQualifiedElementFormDefault
        
    @property
    def nillable(self):
        return self.get("nillable") if self.get("nillable") else 'false'
    
    @property
    def isNillable(self):
        return self.get("nillable") == 'true'
        
    @property
    def block(self):
        return self.get("block")
    
    @property
    def default(self):
        return self.get("default")
    
    @property
    def fixed(self):
        return self.get("fixed") if self.get("fixed") else None
    
    @property
    def final(self):
        return self.get("final") if self.get("final") else None
    
    @property
    def isRoot(self):
        return self.getparent().localName == "schema"
    
    def label(self,preferredLabel=None,fallbackToQname=True,lang=None,strip=False):
        if preferredLabel is None: preferredLabel = XbrlConst.standardLabel
        if preferredLabel == XbrlConst.conceptNameLabelRole: return str(self.qname)
        labelsRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
        if labelsRelationshipSet:
            label = labelsRelationshipSet.label(self, preferredLabel, lang)
            if label is not None:
                if strip: return label.strip()
                return Locale.rtlString(label, lang=lang)
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
            self._isTypedDimension = self.isDimensionItem and self.get("{http://xbrl.org/2005/xbrldt}typedDomainRef") is not None
            return self._isTypedDimension
        
    @property
    def isExplicitDimension(self):
        return self.isDimensionItem and not self.isTypedDimension
    
    @property
    def typedDomainRef(self):
        return self.get("{http://xbrl.org/2005/xbrldt}typedDomainRef")

    @property
    def typedDomainElement(self):
        try:
            return self._typedDomainElement
        except AttributeError:
            self._typedDomainElement = self.resolveUri(uri=self.typedDomainRef)
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

    def dereference(self):
        ref = self.get("ref")
        if ref:
            return self.modelXbrl.qnameConcepts.get(ModelValue.qname(self, ref))
        return self

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
    def init(self, modelDocument):
        super().init(modelDocument)
        if self.isGlobalDeclaration:
            self.modelXbrl.qnameAttributes[self.qname] = self
        
    @property
    def typeQname(self):
        if self.get("type"):
            return self.prefixedNameQname(self.get("type"))
        else:
            # check if anonymous type exists
            typeqname = ModelValue.qname(self.qname.clarkNotation +  "@anonymousType")
            if typeqname in self.modelXbrl.qnameTypes:
                return typeqname
            # try substitution group for type
            ''' HF: I don't think attributes can have a substitution group ??
            subs = self.substitutionGroup
            if subs:
                return subs.typeQname
            '''
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
            if typeqname is None:   # anyType is default type
                return "anyType"
            if typeqname.namespaceURI == XbrlConst.xsd:
                return typeqname.localName
            type = self.type
            self._baseXsdType = type.baseXsdType if type is not None else None
            return self._baseXsdType
    
    @property
    def facets(self):
        try:
            return self._facets
        except AttributeError:
            type = self.type
            self._facets = type.facets if type is not None else None
            return self._facets
    
    @property
    def isNumeric(self):
        try:
            return self._isNumeric
        except AttributeError:
            self._isNumeric = XbrlConst.isNumericXsdType(self.baseXsdType)
            return self._isNumeric
    
    @property
    def isQualifiedForm(self): # used only in determining qname, which itself is cached
        if self.get("form") is not None: # form is almost never used
            return self.get("form") == "qualified"
        return self.modelDocument.isQualifiedAttributeFormDefault
        
    @property
    def isRequired(self):
        return self.get("use") == "required"
    
    @property
    def default(self):
        return self.get("default")
    
    @property
    def fixed(self):
        return self.get("fixed")
    
    def dereference(self):
        ref = self.get("ref")
        if ref:
            return self.modelXbrl.qnameAttributes.get(ModelValue.qname(self, ref))
        return self

class ModelAttributeGroup(ModelSchemaObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        if self.isGlobalDeclaration:
            self.modelXbrl.qnameAttributeGroups[self.qname] = self
        
    @property
    def isQualifiedForm(self): # always qualified
        return True
    
    @property
    def attributes(self):
        try:
            return self._attributes
        except AttributeError:
            self._attributes = {}
            attrs, attrGroups = XmlUtil.schemaAttributesGroups(self)
            for attrGroupRef in attrGroups:
                attrGroupDecl = attrGroupRef.dereference()
                if attrGroupDecl is not None:
                    for attrRef in attrGroupDecl.attributes.values():
                        attrDecl = attrRef.dereference()
                        if attrDecl is not None:
                            self._attributes[attrDecl.qname] = attrDecl
            for attrRef in attrs:
                attrDecl = attrRef.dereference()
                if attrDecl is not None:
                    self._attributes[attrDecl.qname] = attrDecl
            return self._attributes
        
    def dereference(self):
        ref = self.get("ref")
        if ref:
            return self.modelXbrl.qnameAttributeGroups.get(ModelValue.qname(self, ref))
        return self
        
class ModelType(ModelSchemaObject):
    def init(self, modelDocument):
        super().init(modelDocument)     
        self.modelXbrl.qnameTypes[self.qname] = self
        
    @property
    def name(self):
        nameAttr = self.getStripped("name")
        if nameAttr:
            return nameAttr
        # may be anonymous type of parent
        element = self.getparent()
        while element is not None:
            nameAttr = element.getStripped("name")
            if nameAttr:
                return nameAttr + "@anonymousType"
            element = element.getparent()
        return None
    
    @property
    def isQualifiedForm(self): # always qualified
        return True
    
    @property
    def qnameDerivedFrom(self):
        return self.prefixedNameQname(XmlUtil.schemaBaseTypeDerivedFrom(self))
    
    @property
    def typeDerivedFrom(self):
        qnameDerivedFrom = self.qnameDerivedFrom
        if qnameDerivedFrom is not None:
            self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
        return None
    
    @property
    def baseXsdType(self):
        try:
            return self._baseXsdType
        except AttributeError:
            if self.qname == XbrlConst.qnXbrliDateUnion:
                return "XBRLI_DATEUNION"
            elif self.qname == XbrlConst.qnXbrliDecimalsUnion:
                return "XBRLI_DECIMALSUNION"
            elif self.qname == XbrlConst.qnXbrliPrecisionUnion:
                return "XBRLI_PRECISIONUNION"
            elif self.qname == XbrlConst.qnXbrliNonZeroDecimalUnion:
                return "XBRLI_NONZERODECIMAL"
            qnameDerivedFrom = self.qnameDerivedFrom
            if qnameDerivedFrom is None:
                # want None if base type has no content (not mixed content, TBD)
                #self._baseXsdType =  "anyType"
                self._baseXsdType =  "noContent"
            elif qnameDerivedFrom.namespaceURI == XbrlConst.xsd:
                self._baseXsdType = qnameDerivedFrom.localName
            else:
                typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
                #assert typeDerivedFrom is not None, _("Unable to determine derivation of {0}").format(qnameDerivedFrom)
                self._baseXsdType = typeDerivedFrom.baseXsdType if typeDerivedFrom is not None else "anyType"
            if self._baseXsdType == "anyType" and XmlUtil.emptyContentModel(self):
                self._baseXsdType = "noContent"
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
            if qnameDerivedFrom is not None:
                if qnameDerivedFrom.namespaceURI == XbrlConst.xbrli:  # xbrli type
                    self._baseXbrliType = qnameDerivedFrom.localName
                elif qnameDerivedFrom.namespaceURI == XbrlConst.xsd:    # xsd type
                    self._baseXbrliType = qnameDerivedFrom.localName
                else:
                    typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
                    self._baseXbrliType = typeDerivedFrom.baseXbrliType if typeDerivedFrom is not None else None
            else:
                self._baseXbrliType = None
            return self._baseXbrliType
    
    @property
    def isTextBlock(self):
        if self.name == "textBlockItemType" and "/us-types/" in self.modelDocument.targetNamespace:
            return True
        if self.name == "escapedItemType" and self.modelDocument.targetNamespace.startswith(XbrlConst.dtrTypesStartsWith):
            return True
        qnameDerivedFrom = self.qnameDerivedFrom
        if qnameDerivedFrom is None or (qnameDerivedFrom.namespaceURI in(XbrlConst.xsd,XbrlConst.xbrli)):
            return False
        typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
        return typeDerivedFrom.isTextBlock if typeDerivedFrom is not None else False

    @property
    def isDomainItemType(self):
        if self.name == "domainItemType" and \
           ("/us-types/" in self.modelDocument.targetNamespace or
            self.modelDocument.targetNamespace.startswith(XbrlConst.dtrTypesStartsWith)):
            return True
        qnameDerivedFrom = self.qnameDerivedFrom
        if qnameDerivedFrom is None or (qnameDerivedFrom.namespaceURI in (XbrlConst.xsd,XbrlConst.xbrli)):
            return False
        typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
        return typeDerivedFrom.isDomainItemType if typeDerivedFrom is not None else False
    
    def isDerivedFrom(self, typeqname):
        qnameDerivedFrom = self.qnameDerivedFrom
        if qnameDerivedFrom is None:    # not derived from anything
            return typeqname is None
        if qnameDerivedFrom == typeqname:
            return True
        typeDerivedFrom = self.modelXbrl.qnameTypes.get(qnameDerivedFrom)
        return typeDerivedFrom.isDerivedFrom(typeqname) if typeDerivedFrom is not None else False
        
    
    @property
    def attributes(self):
        try:
            return self._attributes
        except AttributeError:
            self._attributes = {}
            attrs, attrGroups = XmlUtil.schemaAttributesGroups(self)
            for attrRef in attrs:
                attrDecl = attrRef.dereference()
                if attrDecl is not None:
                    self._attributes[attrDecl.qname] = attrDecl
            for attrGroupRef in attrGroups:
                attrGroupDecl = attrGroupRef.dereference()
                if attrGroupDecl is not None:
                    for attrRef in attrGroupDecl.attributes.values():
                        attrDecl = attrRef.dereference()
                        if attrDecl is not None:
                            self._attributes[attrDecl.qname] = attrDecl
            return self._attributes

    @property
    def requiredAttributeQnames(self):
        try:
            return self._requiredAttributeQnames
        except AttributeError:
            self._requiredAttributeQnames = set(a.qname for a in self.attributes.values() if a.isRequired)
            return self._requiredAttributeQnames
            
    @property
    def defaultAttributeQnames(self):
        try:
            return self._defaultAttributeQnames
        except AttributeError:
            self._defaultAttributeQnames = set(a.qname for a in self.attributes.values() if a.default is not None)
            return self._defaultAttributeQnames
            
    @property
    def elements(self):
        return XmlUtil.schemaDescendantsNames(self, XbrlConst.xsd, "element")
    
    @property
    def facets(self):
        try:
            return self._facets
        except AttributeError:
            facets = self.constrainingFacets()
            self._facets = facets if facets else None
            return self._facets
    
    def constrainingFacets(self, facetValues=None):
        facetValues = facetValues if facetValues else {}
        for facetElt in XmlUtil.schemaFacets(self, (
                    "{http://www.w3.org/2001/XMLSchema}length", "{http://www.w3.org/2001/XMLSchema}minLength", 
                    "{http://www.w3.org/2001/XMLSchema}maxLength", 
                    "{http://www.w3.org/2001/XMLSchema}pattern", "{http://www.w3.org/2001/XMLSchema}whiteSpace",  
                    "{http://www.w3.org/2001/XMLSchema}maxInclusive", "{http://www.w3.org/2001/XMLSchema}maxExclusive", "{http://www.w3.org/2001/XMLSchema}minExclusive", 
                    "{http://www.w3.org/2001/XMLSchema}totalDigits", "{http://www.w3.org/2001/XMLSchema}fractionDigits")):
            XmlValidate.validateFacet(self, facetElt)
            facetName = facetElt.localName
            if facetName not in facetValues:
                facetValue = XmlValidate.validateFacet(self, facetElt)
                if facetValue:
                    facetValues[facetName] = facetValue
        if "enumeration" not in facetValues:
            for facetElt in XmlUtil.schemaFacets(self, ("{http://www.w3.org/2001/XMLSchema}enumeration",)):
                facetValues.setdefault("enumeration",set()).add(facetElt.get("value"))
        typeDerivedFrom = self.typeDerivedFrom
        if typeDerivedFrom is not None:
            typeDerivedFrom.constrainingFacets(facetValues)
        return facetValues
                
    def fixedOrDefaultAttrValue(self, attrName):
        attr = XmlUtil.schemaDescendant(self, XbrlConst.xsd, "attribute", attrName)
        if attr is not None:
            if attr.get("fixed"):
                return attr.get("fixed")
            elif attr.get("default"):
                return attr.get("default")
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
    def init(self, modelDocument):
        super().init(modelDocument)
        
    @property
    def value(self):
        return self.get("value")
    
class ModelLink(ModelObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        self.labeledResources = defaultdict(list)
        
    @property
    def role(self):
        return self.get("{http://www.w3.org/1999/xlink}role")
        
class ModelResource(ModelObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        if self.xmlLang:
            self.modelXbrl.langs.add(self.xmlLang)
        if self.localName == "label":
            self.modelXbrl.labelroles.add(self.role)
        
    @property
    def role(self):
        return self.get("{http://www.w3.org/1999/xlink}role")
        
    @property
    def xlinkLabel(self):
        return self.get("{http://www.w3.org/1999/xlink}label")

    @property
    def xmlLang(self):
        lang = self.get("{http://www.w3.org/XML/1998/namespace}lang")
        return lang

    def viewText(self, labelrole=None, lang=None): # text of label or reference parts
        return " ".join([XmlUtil.text(resourceElt)
                           for resourceElt in self.iter()
                              if isinstance(resourceElt,ModelObject) and 
                                  not resourceElt.localName.startswith("URI")])
    def dereference(self):
        return self
        
class ModelLocator(ModelResource):
    def init(self, modelDocument):
        super().init(modelDocument)
    
    def dereference(self):
        # resource is a loc with href document and id modelHref a tuple with href's element, modelDocument, id
        return self.resolveUri(self.modelHref)
    
class RelationStatus:
    Unknown = 0
    EFFECTIVE = 1
    OVERRIDDEN = 2
    PROHIBITED = 3
    INEFFECTIVE = 4
    
arcCustAttrsExclusions = {XbrlConst.xlink, "use","priority","order","weight","preferredLabel"}
    
class ModelRelationship(ModelObject):
    def __init__(self, modelDocument, arcElement, fromModelObject, toModelObject):
        # copy model object properties from arcElement
        self.arcElement = arcElement
        self.init(modelDocument)
        self.fromModelObject = fromModelObject
        self.toModelObject = toModelObject
        
    # simulate etree operations
    def get(self, attrname):
        return self.arcElement.get(attrname)
    
    @property
    def localName(self):
        return self.arcElement.localName
        
    @property
    def namespaceURI(self):
        return self.arcElement.namespaceURI
        
    @property
    def prefixedName(self):
        return self.arcElement.prefixedName
        
    @property
    def sourceline(self):
        return self.arcElement.sourceline
        
    @property
    def tag(self):
        return self.arcElement.tag
    
    @property
    def elementQname(self):
        return self.arcElement.elementQname
        
    @property
    def qname(self):
        return self.arcElement.qname
    
    def itersiblings(self, **kwargs):
        return self.arcElement.itersiblings(**kwargs)
        
    @property
    def fromLabel(self):
        return self.arcElement.get("{http://www.w3.org/1999/xlink}from")
        
    @property
    def toLabel(self):
        return self.arcElement.get("{http://www.w3.org/1999/xlink}to")
        
    @property
    def arcrole(self):
        return self.arcElement.get("{http://www.w3.org/1999/xlink}arcrole")

    @property
    def order(self):
        try:
            return self.arcElement._order
        except AttributeError:
            o = self.arcElement.get("order")
            if o is None:
                order = 1.0
            else:
                try:
                    order = float(o)
                except (TypeError,ValueError) :
                    order = float("nan")
            self.arcElement._order = order
            return order

    @property
    def priority(self):
        try:
            return self.arcElement._priority
        except AttributeError:
            p = self.arcElement.get("priority")
            if p is None:
                priority = 0
            else:
                try:
                    priority = int(p)
                except (TypeError,ValueError) :
                    # XBRL validation error needed
                    priority = 0
            self.arcElement._priority = priority
            return priority

    @property
    def weight(self):
        try:
            return self.arcElement._weight
        except AttributeError:
            w = self.arcElement.get("weight")
            if w is None:
                weight = None
            else:
                try:
                    weight = float(w)
                except (TypeError,ValueError) :
                    # XBRL validation error needed
                    weight = float("nan")
            self.arcElement._weight = weight
            return weight

    @property
    def weightDecimal(self):
        try:
            return self.arcElement._weightDecimal
        except AttributeError:
            w = self.arcElement.get("weight")
            if w is None:
                weight = None
            else:
                try:
                    weight = decimal.Decimal(w)
                except (TypeError,ValueError) :
                    # XBRL validation error needed
                    weight = decimal.Decimal("nan")
            self.arcElement._weightDecimal = weight
            return weight

    @property
    def use(self):
        return self.get("use")
    
    @property
    def isProhibited(self):
        return self.use == "prohibited"
    
    @property
    def prohibitedUseSortKey(self):
        return 2 if self.isProhibited else 1
    
    @property
    def preferredLabel(self):
        return self.get("preferredLabel")

    @property
    def variablename(self):
        return self.getStripped("name")

    @property
    def variableQname(self):
        varName = self.variablename
        return ModelValue.qname(self.arcElement, varName, noPrefixIsNoNamespace=True) if varName else None

    @property
    def linkrole(self):
        return self.arcElement.getparent().get("{http://www.w3.org/1999/xlink}role")
    
    @property
    def linkQname(self):
        return self.arcElement.getparent().elementQname
    
    @property
    def contextElement(self):
        return self.get("{http://xbrl.org/2005/xbrldt}contextElement")
    
    @property
    def targetRole(self):
        return self.get("{http://xbrl.org/2005/xbrldt}targetRole")
    
    @property
    def consecutiveLinkrole(self):
        return self.targetRole if self.targetRole else self.linkrole
    
    @property
    def isUsable(self):
        return self.get("{http://xbrl.org/2005/xbrldt}usable") == "true" if self.get("{http://xbrl.org/2005/xbrldt}usable") else True
    
    @property
    def closed(self):
        return self.get("{http://xbrl.org/2005/xbrldt}closed") if self.get("{http://xbrl.org/2005/xbrldt}closed") else "false"

    @property
    def isComplemented(self):
        try:
            return self._isComplemented
        except AttributeError:
            self._isComplemented = self.get("complement") == "true" if self.get("complement") else False
            return self._isComplemented
    
    @property
    def isCovered(self):
        try:
            return self._isCovered
        except AttributeError:
            self._isCovered = self.get("cover") == "true" if self.get("cover") else False
            return self._isCovered
    
    @property
    def isClosed(self):
        try:
            return self._isClosed
        except AttributeError:
            self._isClosed = self.get("{http://xbrl.org/2005/xbrldt}closed") == "true" if self.get("{http://xbrl.org/2005/xbrldt}closed") else False
            return self._isClosed

    @property
    def usable(self):
        try:
            return self._usable
        except AttributeError:
            if self.arcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember):
                self._usable = self.get("{http://xbrl.org/2005/xbrldt}usable") if self.get("{http://xbrl.org/2005/xbrldt}usable") else "true"
            else:
                self._usable = None
            return self._usable
        
    @property
    def axisType(self):
        try:
            return self._tableAxis
        except AttributeError:
            aType = self.get("axisType")
            if aType in ("xAxis","x-axis"): self._axisType = "xAxis"
            elif aType in ("yAxis","y-axis"): self._axisType = "yAxis"
            elif aType in ("zAxis","z-axis"): self._axisType = "zAxis"
            else: self._axisType = None
            return self._axisType
        
    @property
    def equivalenceKey(self):
        # cannot be cached because this is unique per relationship
        return (self.qname, 
                self.linkQname,
                self.linkrole,  # needed when linkrole=None merges multiple links
                self.fromModelObject.objectIndex if self.fromModelObject is not None else -1, 
                self.toModelObject.objectIndex if self.toModelObject is not None else -1, 
                self.order, 
                self.weight, 
                self.preferredLabel) + \
                XbrlUtil.attributes(self.modelXbrl, self.arcElement, 
                    exclusions=arcCustAttrsExclusions, keyByTag=True) # use clark tag for key instead of qname
                
    def isIdenticalTo(self, otherModelRelationship):
        return (otherModelRelationship is not None and
                self.arcElement == otherModelRelationship.arcElement and
                self.fromModelObject is not None and otherModelRelationship.fromModelObject is not None and
                self.toModelObject is not None and otherModelRelationship.toModelObject is not None and
                self.fromModelObject == otherModelRelationship.fromModelObject and
                self.toModelObject == otherModelRelationship.toModelObject)

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
           
from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
     (XbrlConst.qnXlExtended, ModelLink),
     (XbrlConst.qnXlLocator, ModelLocator),
     (XbrlConst.qnXlResource, ModelResource),
    ))
