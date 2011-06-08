'''
Created on Nov 9, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import (ModelObject, XbrlUtil, XmlUtil, XbrlConst)
from arelle.ModelValue import qname

# initialize object from an element
def create(modelDocument, element=None, localName=None, namespaceURI=None):
    if element:
        ln = element.localName
        ns = element.namespaceURI
    else:
        ln = localName
        ns = namespaceURI
    modelObject = None
    if ns == XbrlConst.ver:
        if ln == "assignment":
            modelObject = ModelAssignment(modelDocument, element)
        elif ln == "action":
            modelObject = ModelAction(modelDocument, element)
        elif ln == "namespaceRename":
            modelObject = ModelNamespaceRename(modelDocument, element)
        elif ln == "roleChange":
            modelObject = ModelRoleChange(modelDocument, element)
        else:
            modelObject = ModelVersObject(modelDocument, element)
    elif ns == XbrlConst.vercb:
        modelObject = ModelConceptBasicChange(modelDocument, element)
    elif ns == XbrlConst.verce:
        modelObject = ModelConceptExtendedChange(modelDocument, element)
    elif ns == XbrlConst.verrels:
        modelObject = ModelRelationshipSetChange(modelDocument, element)
    return modelObject

def relateConceptMdlObjs(modelDocument, fromConceptMdlObjs, toConceptMdlObjs):
    for fromConceptMdlObj in fromConceptMdlObjs:
        fromConcept = fromConceptMdlObj
        if fromConcept:
            fromConceptQname = fromConcept.qname
            for toConceptMdlObj in toConceptMdlObjs:
                toConcept = toConceptMdlObj.toConcept
                if toConcept:
                    toConceptQname = toConcept.qname
                    modelDocument.relatedConcepts[fromConceptQname].add(toConceptQname)

class ModelVersObject(ModelObject.ModelObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        
    @property
    def name(self):
        return self.element.localName

    def viewText(self, labelrole=None, lang=None):
        return ''

class ModelAssignment(ModelVersObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        modelDocument.assignments[self.id] = self
        
    @property
    def categoryqname(self):
        for child in self.element.childNodes:
            if child.nodeType == 1:
                return "{" + child.namespaceURI + "}" + child.localName

    @property
    def categoryQName(self):
        for child in self.element.childNodes:
            if child.nodeType == 1:
                return child.tagName
        return None

    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.genLabel()),
                ("category", self.categoryQName))

class ModelAction(ModelVersObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        actionKey = self.id if self.id else "action{0:05}".format(len(modelDocument.actions) + 1)
        modelDocument.actions[actionKey] = self
        self.events = []
        
    @property
    def assignmentRefs(self):
        return XmlUtil.childrenAttrs(self.element, XbrlConst.ver, "assignmentRef", "ref")
        
    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.genLabel()),
                ("assgnmts", self.assignmentRefs))

class ModelUriMapped(ModelVersObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        
    @property
    def fromURI(self):
        return XmlUtil.childAttr(self.element, XbrlConst.ver, "fromURI", "value")
        
    @property
    def toURI(self):
        return XmlUtil.childAttr(self.element, XbrlConst.ver, "toURI", "value")

    @property
    def propertyView(self):
        return (("fromURI", self.fromURI),
                ("toURI", self.toURI))
        
    def viewText(self, labelrole=None, lang=None):
        return "{0} -> {1}".format(self.fromURI, self.toURI)
    
class ModelNamespaceRename(ModelUriMapped):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        modelDocument.namespaceRenameFrom[self.fromURI] = self
        modelDocument.namespaceRenameTo[self.toURI] = self
        
class ModelRoleChange(ModelUriMapped):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        modelDocument.roleChanges[self.fromURI] = self

class ModelConceptChange(ModelVersObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        
    @property
    def actionId(self):
        return XmlUtil.parentId(self.element, XbrlConst.ver, "action")
    
    @property
    def fromConceptQname(self):
        fromConcept = XmlUtil.child(self.element, XbrlConst.vercb, "fromConcept")
        if fromConcept and fromConcept.hasAttribute("name"):
            return qname(fromConcept, fromConcept.getAttribute("name"))
        else:
            return None
        
    @property
    def toConceptQname(self):
        toConcept = XmlUtil.child(self.element, XbrlConst.vercb, "toConcept")
        if toConcept and toConcept.hasAttribute("name"):
            return qname(toConcept, toConcept.getAttribute("name"))
        else:
            return None
        
    @property
    def fromConcept(self):
        # for href: return self.resolveUri(uri=self.fromConceptValue, dtsModelXbrl=self.modelDocument.fromDTS)
        return self.modelDocument.fromDTS.qnameConcepts.get(self.fromConceptQname)
    
    @property
    def toConcept(self):
        # return self.resolveUri(uri=self.toConceptValue, dtsModelXbrl=self.modelDocument.toDTS)
        return self.modelDocument.toDTS.qnameConcepts.get(self.toConceptQname)
        
    def setConceptEquivalence(self):
        if self.fromConcept and self.toConcept:
            self.modelDocument.equivalentConcepts[self.fromConcept.qname] = self.toConcept.qname

    @property
    def propertyView(self):
        fromConcept = self.fromConcept
        toConcept = self.toConcept
        return (("event", self.localName),
                 ("fromConcept", fromConcept.qname) if fromConcept else (),
                 ("toConcept", toConcept.qname) if toConcept else (),
                )

    def viewText(self, labelrole=XbrlConst.conceptNameLabelRole, lang=None):
        fromConceptQname = self.fromConceptQname
        fromConcept = self.fromConcept
        toConceptQname = self.toConceptQname
        toConcept = self.toConcept
        if (labelrole != XbrlConst.conceptNameLabelRole and
            (fromConceptQname is None or (fromConceptQname and fromConcept)) and
            (toConceptQname is None or (toConceptQname and toConcept))):
            if fromConceptQname:
                if toConceptQname:
                    return self.fromConcept.label(labelrole,True,lang) + " -> " + self.toConcept.label(labelrole,True,lang)
                else:
                    return self.fromConcept.label(labelrole,True,lang)
            elif toConceptQname:
                return self.toConcept.label(labelrole,True,lang)
            else:
                return "(invalidConceptReference)"
        else:
            if fromConceptQname:
                if toConceptQname:
                    if toConceptQname.localName != fromConceptQname.localName:
                        return str(fromConceptQname) + " -> " + str(toConceptQname)
                    else:
                        return "( " + fromConceptQname.prefix + ": -> " + toConceptQname.prefix + ": ) " + toConceptQname.localName
                else:
                    return str(fromConceptQname)
            elif toConceptQname:
                return str(toConceptQname)
            else:
                return "(invalidConceptReference)"
            

class ModelConceptBasicChange(ModelConceptChange):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        modelDocument.conceptBasicChanges.append(self)
        ln = self.element.localName
            
        
class ModelConceptExtendedChange(ModelConceptChange):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        modelDocument.conceptExtendedChanges.append(self)
        
    def customAttributeQname(self, eventName):
        custAttrElt = XmlUtil.child(self.element, XbrlConst.verce, eventName)
        if custAttrElt and custAttrElt.hasAttribute("name"):
            return qname(custAttrElt, custAttrElt.getAttribute("name"))
        return None
        
    @property
    def fromCustomAttributeQname(self):
        return self.customAttributeQname("fromCustomAttribute")
        
    @property
    def toCustomAttributeQname(self):
        return self.customAttributeQname("toCustomAttribute")
        
    @property
    def fromResourceValue(self):
        return XmlUtil.childAttr(self.element, XbrlConst.verce, "fromResource", "value")
        
    @property
    def toResourceValue(self):
        return XmlUtil.childAttr(self.element, XbrlConst.verce, "toResource", "value")
        
    @property
    def fromResource(self):
        return self.resolveUri(uri=self.fromResourceValue, dtsModelXbrl=self.modelDocument.fromDTS)
        
    @property
    def toResource(self):
        return self.resolveUri(uri=self.toResourceValue, dtsModelXbrl=self.modelDocument.toDTS)
        
    @property
    def propertyView(self):
        fromConcept = self.fromConcept
        toConcept = self.toConcept
        fromCustomAttributeQname = self.fromCustomAttributeQname
        toCustomAttributeQname = self.toCustomAttributeQname
        return (("event", self.localName),
                 ("fromConcept", fromConcept.qname) if fromConcept else (),
                 ("fromCustomAttribute", fromCustomAttributeQname) if fromCustomAttributeQname else (),
                 ("fromResource", self.fromResource.viewText() if self.fromResource else "(invalidContentResourceIdentifier)") if self.fromResourceValue else (),
                 ("toConcept", toConcept.qname) if toConcept else (),
                 ("toCustomAttribute", toCustomAttributeQname) if toCustomAttributeQname else (),
                 ("toResource", self.toResource.viewText() if self.toResource else "(invalidContentResourceIdentifier)") if self.toResourceValue else (),
                )

class ModelRelationshipSetChange(ModelVersObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        modelDocument.relationshipSetChanges.append(self)
        self.fromRelationshipSet = None
        self.toRelationshipSet = None
        
    @property
    def propertyView(self):
        return (("event", self.localName),
                )

class ModelRelationshipSet(ModelVersObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        self.relationships = []
        
    @property
    def isFromDTS(self):
        return self.element.localName == "fromRelationshipSet"
        
    @property
    def dts(self):
        return self.modelDocument.fromDTS if self.isFromDTS else self.modelDocument.toDTS
        
    @property
    def relationshipSetElement(self):
        return XmlUtil.child(self.element, XbrlConst.verrels, "relationshipSet")

    @property
    def link(self):
        if self.relationshipSetElement.hasAttribute("link"):
            return self.prefixedNameQname(self.relationshipSetElement.getAttribute("link"))
        else:
            return None
        
    @property
    def linkrole(self):
        if self.relationshipSetElement.hasAttribute("linkrole"):
            return self.relationshipSetElement.getAttribute("linkrole")
        else:
            return None
        
    @property
    def arc(self):
        if self.relationshipSetElement.hasAttribute("arc"):
            return self.prefixedNameQname(self.relationshipSetElement.getAttribute("arc"))
        else:
            return None
        
    @property
    def arcrole(self):
        if self.relationshipSetElement.hasAttribute("arcrole"):
            return self.relationshipSetElement.getAttribute("arcrole")
        else:
            return None
        
    @property
    def propertyView(self):
        return self.modelRelationshipSetEvent.propertyView + \
               (("model", self.localName),
                ("link", str(self.link)) if self.link else (),
                ("linkrole", self.linkrole) if self.linkrole else (),
                ("arc", str(self.arc)) if self.arc else (),
                ("arcrole", self.arcrole) if self.arcrole else (),
                )

class ModelRelationships(ModelVersObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        
    @property
    def fromName(self):
        if self.element.hasAttribute("fromName"):
            return self.prefixedNameQname(self.element.getAttribute("fromName"))
        else:
            return None
        
    @property
    def toName(self):
        return self.prefixedNameQname(self.element.getAttribute("toName")) if self.element.hasAttribute("toName") else None
        
    @property
    def fromConcept(self):
        # for href: return self.resolveUri(uri=self.fromConceptValue, dtsModelXbrl=self.modelDocument.fromDTS)
        return self.modelRelationshipSet.dts.qnameConcepts.get(self.fromName) if self.fromName else None
    
    @property
    def toConcept(self):
        # return self.resolveUri(uri=self.toConceptValue, dtsModelXbrl=self.modelDocument.toDTS)
        return self.modelRelationshipSet.dts.qnameConcepts.get(self.toName) if self.toName else None
        
    @property
    def axis(self):
        if self.element.hasAttribute("axis"):
            return self.element.getAttribute("axis")
        else:
            return None
        
    @property
    def isFromDTS(self):
        return self.modelRelationshipSet.isFromDTS
        
    @property
    def fromRelationships(self):
        mdlRel = self.modelRelationshipSet
        relSet = mdlRel.dts.relationshipSet(mdlRel.arcrole, mdlRel.linkrole, mdlRel.link, mdlRel.arc)
        if relSet:
            return relSet.fromModelObject(self.fromConcept)
        return None
        
    @property
    def fromRelationship(self):
        fromRelationships = self.fromRelationships
        if not fromRelationships:
            return None
        toName = self.toName
        if self.toName:
            for rel in fromRelationships:
                if rel.toModelObject.qname == toName:
                    return rel
            return None
        else:   # return first (any) relationship
            return fromRelationships[0]
        
    @property
    def propertyView(self):
        return self.modelRelationshipSet.propertyView + \
                (("fromName", self.fromName) if self.fromName else (),
                 ("toName", self.toName) if self.toName else (),
                 ("axis", self.axis) if self.axis else (),
                )

class ModelInstanceAspectsChange(ModelVersObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        modelDocument.instanceAspectChanges.append(self)
        self.fromAspects = None
        self.toAspects = None
        
    @property
    def propertyView(self):
        return (("event", self.localName),
                )

class ModelInstanceAspects(ModelVersObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        self.aspects = []
        
    @property
    def isFromDTS(self):
        return self.element.localName == "fromAspects"
        
    @property
    def dts(self):
        return self.modelDocument.fromDTS if self.isFromDTS else self.modelDocument.toDTS
        
    @property
    def excluded(self):
        return self.element.getAttribute("excluded") if self.element.hasAttribute("excluded") else None
        
    @property
    def propertyView(self):
        return self.aspectModelEvent.propertyView + \
               (("excluded", self.excluded) if self.excluded else (),
                )

class ModelInstanceAspect(ModelVersObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        self.members = []

    @property
    def conceptName(self):
        return self.prefixedNameQname(self.element.getAttribute("name")) if self.element.hasAttribute("name") else None
        
    @property
    def concept(self):
        # for href: return self.resolveUri(uri=self.fromConceptValue, dtsModelXbrl=self.modelDocument.fromDTS)
        return self.modelAspects.dts.qnameConcepts.get(self.conceptName) if self.conceptName else None
    
    @property
    def sourceDtsObject(self):
        if self.localName == "concept":
            return self.concept
        elif self.localName == "explicitDimension":
            return self.concept
        return None

    @property
    def isFromDTS(self):
        return self.modelAspects.isFromDTS
    
    @property
    def propertyView(self):
        return self.modelAspects.propertyView + \
               (("aspect", self.localName),
                ) + self.elementAttributesTuple

class ModelInstanceMemberAspect(ModelVersObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        
    @property
    def conceptName(self):
        return self.prefixedNameQname(self.element.getAttribute("name")) if self.element.hasAttribute("name") else None
        
    @property
    def concept(self):
        # for href: return self.resolveUri(uri=self.fromConceptValue, dtsModelXbrl=self.modelDocument.fromDTS)
        return self.modelAspect.modelAspects.dts.qnameConcepts.get(self.conceptName) if self.conceptName else None
    
    @property
    def sourceDtsObject(self):
        if self.localName == "member":
            return self.concept
        return None

    @property
    def isFromDTS(self):
        return self.modelAspect.modelAspects.isFromDTS
    
    @property
    def propertyView(self):
        return self.modelAspect.propertyView + \
               ((self.localName, ''),
                ) + self.elementAttributesTuple

        
