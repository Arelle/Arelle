'''
Created on Nov 9, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import XmlUtil, XbrlConst
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname


def relateConceptMdlObjs(modelDocument, fromConceptMdlObjs, toConceptMdlObjs):
    for fromConceptMdlObj in fromConceptMdlObjs:
        fromConcept = fromConceptMdlObj
        if fromConcept is not None:
            fromConceptQname = fromConcept.qname
            for toConceptMdlObj in toConceptMdlObjs:
                toConcept = toConceptMdlObj.toConcept
                if toConcept is not None:
                    toConceptQname = toConcept.qname
                    modelDocument.relatedConcepts[fromConceptQname].add(toConceptQname)

class ModelVersObject(ModelObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        
    @property
    def name(self):
        return self.localName

    def viewText(self, labelrole=None, lang=None):
        return ''

class ModelAssignment(ModelVersObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        self.modelDocument.assignments[self.id] = self
        
    @property
    def categoryqname(self):
        for child in self.iterchildren():
            if isinstance(child, ModelObject):
                return "{" + child.namespaceURI + "}" + child.localName

    @property
    def categoryQName(self):
        for child in self.iterchildren():
            if isinstance(child, ModelObject):
                return child.prefixedName
        return None

    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.genLabel()),
                ("category", self.categoryQName))

class ModelAction(ModelVersObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        actionKey = self.id if self.id else "action{0:05}".format(len(self.modelDocument.actions) + 1)
        self.modelDocument.actions[actionKey] = self
        self.events = []
        
    @property
    def assignmentRefs(self):
        return XmlUtil.childrenAttrs(self, XbrlConst.ver, "assignmentRef", "ref")
        
    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.genLabel()),
                ("assgnmts", self.assignmentRefs))

class ModelUriMapped(ModelVersObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        
    @property
    def fromURI(self):
        return XmlUtil.childAttr(self, XbrlConst.ver, "fromURI", "value")
        
    @property
    def toURI(self):
        return XmlUtil.childAttr(self, XbrlConst.ver, "toURI", "value")

    @property
    def propertyView(self):
        return (("fromURI", self.fromURI),
                ("toURI", self.toURI))
        
    def viewText(self, labelrole=None, lang=None):
        return "{0} -> {1}".format(self.fromURI, self.toURI)
    
class ModelNamespaceRename(ModelUriMapped):
    def init(self, modelDocument):
        super().init(modelDocument)
        self.modelDocument.namespaceRenameFrom[self.fromURI] = self
        self.modelDocument.namespaceRenameFromURI[self.fromURI] = self.toURI
        self.modelDocument.namespaceRenameTo[self.toURI] = self
        self.modelDocument.namespaceRenameToURI[self.toURI] = self.fromURI
        
class ModelRoleChange(ModelUriMapped):
    def init(self, modelDocument):
        super().init(modelDocument)
        self.modelDocument.roleChanges[self.fromURI] = self

class ModelConceptChange(ModelVersObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        
    @property
    def actionId(self):
        return XmlUtil.parentId(self, XbrlConst.ver, "action")
    
    @property
    def fromConceptQname(self):
        fromConcept = XmlUtil.child(self, XbrlConst.vercb, "fromConcept")
        if fromConcept is not None and fromConcept.get("name"):
            return qname(fromConcept, fromConcept.get("name"))
        else:
            return None
        
    @property
    def toConceptQname(self):
        toConcept = XmlUtil.child(self, XbrlConst.vercb, "toConcept")
        if toConcept is not None and toConcept.get("name"):
            return qname(toConcept, toConcept.get("name"))
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
        if self.fromConcept is not None and self.toConcept is not None:
            self.modelDocument.equivalentConcepts[self.fromConcept.qname] = self.toConcept.qname

    @property
    def propertyView(self):
        fromConcept = self.fromConcept
        toConcept = self.toConcept
        return (("event", self.localName),
                 ("fromConcept", fromConcept.qname) if fromConcept is not None else (),
                 ("toConcept", toConcept.qname) if toConcept is not None else (),
                )

    def viewText(self, labelrole=XbrlConst.conceptNameLabelRole, lang=None):
        fromConceptQname = self.fromConceptQname
        fromConcept = self.fromConcept
        toConceptQname = self.toConceptQname
        toConcept = self.toConcept
        if (labelrole != XbrlConst.conceptNameLabelRole and
            (fromConceptQname is None or (fromConceptQname is not None and fromConcept is not None)) and
            (toConceptQname is None or (toConceptQname is not None and toConcept is not None))):
            if fromConceptQname is not None:
                if toConceptQname is not None:
                    return self.fromConcept.label(labelrole,True,lang) + " -> " + self.toConcept.label(labelrole,True,lang)
                else:
                    return self.fromConcept.label(labelrole,True,lang)
            elif toConceptQname is not None:
                return self.toConcept.label(labelrole,True,lang)
            else:
                return "(invalidConceptReference)"
        else:
            if fromConceptQname is not None:
                if toConceptQname is not None:
                    if toConceptQname.localName != fromConceptQname.localName:
                        return str(fromConceptQname) + " -> " + str(toConceptQname)
                    else:
                        return "( " + fromConceptQname.prefix + ": -> " + toConceptQname.prefix + ": ) " + toConceptQname.localName
                else:
                    return str(fromConceptQname)
            elif toConceptQname is not None:
                return str(toConceptQname)
            else:
                return "(invalidConceptReference)"
            

class ModelConceptBasicChange(ModelConceptChange):
    def init(self, modelDocument):
        super().init(modelDocument)
        self.modelDocument.conceptBasicChanges.append(self)
            
        
class ModelConceptExtendedChange(ModelConceptChange):
    def init(self, modelDocument):
        super().init(modelDocument)
        self.modelDocument.conceptExtendedChanges.append(self)
        
    def customAttributeQname(self, eventName):
        custAttrElt = XmlUtil.child(self, XbrlConst.verce, eventName)
        if custAttrElt is not None and custAttrElt.get("name"):
            return qname(custAttrElt, custAttrElt.get("name"))
        return None
        
    @property
    def fromCustomAttributeQname(self):
        return self.customAttributeQname("fromCustomAttribute")
        
    @property
    def toCustomAttributeQname(self):
        return self.customAttributeQname("toCustomAttribute")
        
    @property
    def fromResourceValue(self):
        return XmlUtil.childAttr(self, XbrlConst.verce, "fromResource", "value")
        
    @property
    def toResourceValue(self):
        return XmlUtil.childAttr(self, XbrlConst.verce, "toResource", "value")
        
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
                 ("fromConcept", fromConcept.qname) if fromConcept is not None else (),
                 ("fromCustomAttribute", fromCustomAttributeQname) if fromCustomAttributeQname is not None else (),
                 ("fromResource", self.fromResource.viewText() if self.fromResource is not None else "(invalidContentResourceIdentifier)") if self.fromResourceValue else (),
                 ("toConcept", toConcept.qname) if toConcept is not None else (),
                 ("toCustomAttribute", toCustomAttributeQname) if toCustomAttributeQname is not None else (),
                 ("toResource", self.toResource.viewText() if self.toResource is not None else "(invalidContentResourceIdentifier)") if self.toResourceValue else (),
                )

class ModelRelationshipSetChange(ModelVersObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        self.modelDocument.relationshipSetChanges.append(self)
        self.fromRelationshipSet = None
        self.toRelationshipSet = None
        
    @property
    def propertyView(self):
        return (("event", self.localName),
                )

class ModelRelationshipSet(ModelVersObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        self.relationships = []
        
    @property
    def isFromDTS(self):
        return self.localName == "fromRelationshipSet"
        
    @property
    def dts(self):
        return self.modelDocument.fromDTS if self.isFromDTS else self.modelDocument.toDTS
        
    @property
    def relationshipSetElement(self):
        return XmlUtil.child(self, XbrlConst.verrels, "relationshipSet")

    @property
    def link(self):
        if self.relationshipSetElement.get("link"):
            return self.prefixedNameQname(self.relationshipSetElement.get("link"))
        else:
            return None
        
    @property
    def linkrole(self):
        if self.relationshipSetElement.get("linkrole"):
            return self.relationshipSetElement.get("linkrole")
        else:
            return None
        
    @property
    def arc(self):
        if self.relationshipSetElement.get("arc"):
            return self.prefixedNameQname(self.relationshipSetElement.get("arc"))
        else:
            return None
        
    @property
    def arcrole(self):
        if self.relationshipSetElement.get("arcrole"):
            return self.relationshipSetElement.get("arcrole")
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
    def init(self, modelDocument):
        super().init(modelDocument)
        
    @property
    def fromName(self):
        if self.get("fromName"):
            return self.prefixedNameQname(self.get("fromName"))
        else:
            return None
        
    @property
    def toName(self):
        return self.prefixedNameQname(self.get("toName")) if self.get("toName") else None
        
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
        if self.get("axis"):
            return self.get("axis")
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
    def init(self, modelDocument):
        super().init(modelDocument)
        self.modelDocument.instanceAspectChanges.append(self)
        self.fromAspects = None
        self.toAspects = None
        
    @property
    def propertyView(self):
        return (("event", self.localName),
                )

class ModelInstanceAspects(ModelVersObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        self.aspects = []
        
    @property
    def isFromDTS(self):
        return self.localName == "fromAspects"
        
    @property
    def dts(self):
        return self.modelDocument.fromDTS if self.isFromDTS else self.modelDocument.toDTS
        
    @property
    def excluded(self):
        return self.get("excluded") if self.get("excluded") else None
        
    @property
    def propertyView(self):
        return self.aspectModelEvent.propertyView + \
               (("excluded", self.excluded) if self.excluded else (),
                )

class ModelInstanceAspect(ModelVersObject):
    def init(self, modelDocument):
        super().init(modelDocument)
        self.members = []

    @property
    def conceptName(self):
        return self.prefixedNameQname(self.get("name")) if self.get("name") else None
        
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
    def init(self, modelDocument):
        super().init(modelDocument)
        
    @property
    def conceptName(self):
        return self.prefixedNameQname(self.get("name")) if self.get("name") else None
        
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

from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
    (qname(XbrlConst.ver, "assignment"), ModelAssignment),
    (qname(XbrlConst.ver, "action"), ModelAction),
    (qname(XbrlConst.ver, "namespaceRename"), ModelNamespaceRename),
    (qname(XbrlConst.ver, "roleChange"), ModelRoleChange),
    (qname(XbrlConst.vercb, "conceptAdd"), ModelConceptBasicChange),
    (qname(XbrlConst.vercb, "conceptDelete"), ModelConceptBasicChange),
    (qname(XbrlConst.vercb, "conceptRename"), ModelConceptBasicChange),
    (qname(XbrlConst.verce, "conceptIDChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptTypeChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptSubstitutionGroupChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptDefaultChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptNillableChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptAbstractChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptBlockChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptFixedChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptFinalChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptPeriodTypeChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptBalanceChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptAttributeAdd"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptAttributeDelete"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptAttributeChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "tupleContentModelChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptLabelAdd"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptLabelDelete"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptLabelChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptReferenceAdd"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptReferenceDelete"), ModelConceptExtendedChange),
    (qname(XbrlConst.verce, "conceptReferenceChange"), ModelConceptExtendedChange),
    (qname(XbrlConst.verrels, "relationshipSetModelChange"), ModelRelationshipSetChange),
    (qname(XbrlConst.verrels, "relationshipSetModelAdd"), ModelRelationshipSetChange),
    (qname(XbrlConst.verrels, "relationshipSetModelDelete"), ModelRelationshipSetChange),
    (qname(XbrlConst.verrels, "fromRelationshipSet"), ModelRelationshipSet),
    (qname(XbrlConst.verrels, "toRelationshipSet"), ModelRelationshipSet),
    (qname(XbrlConst.verrels, "relationships"), ModelRelationships),
    (qname(XbrlConst.veria, "aspectModelChange"), ModelInstanceAspectsChange),
    (qname(XbrlConst.veria, "aspectModelAdd"), ModelInstanceAspectsChange),
    (qname(XbrlConst.veria, "aspectModelDelete"), ModelInstanceAspectsChange),
    (qname(XbrlConst.veria, "fromAspects"), ModelInstanceAspects),
    (qname(XbrlConst.veria, "toAspects"), ModelInstanceAspects),
    (qname(XbrlConst.veria, "concept"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "explicitDimension"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "typedDimension"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "segment"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "scenario"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "entityIdentifier"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "period"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "location"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "unit"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "member"), ModelInstanceMemberAspect),
    (qname(XbrlConst.veria, "startDate"), ModelInstanceMemberAspect),
    (qname(XbrlConst.veria, "endDate"), ModelInstanceMemberAspect),
    (qname(XbrlConst.veria, "instant"), ModelInstanceMemberAspect),
    (qname(XbrlConst.veria, "forever"), ModelInstanceMemberAspect),
    (qname(XbrlConst.veria, "multiplyBy"), ModelInstanceMemberAspect),
    (qname(XbrlConst.veria, "divideBy"), ModelInstanceMemberAspect),
    (qname(XbrlConst.veria, "measure"), ModelInstanceMemberAspect),
     ))
