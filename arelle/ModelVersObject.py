'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from arelle import XmlUtil, XbrlConst
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname

if TYPE_CHECKING:
    from arelle.ModelDocument import ModelDocument
    from arelle.ModelDtsObject import ModelConcept, ModelRelationship
    from arelle.ModelRelationshipSet import ModelRelationshipSet as DtsRelationshipSet
    from arelle.ModelValue import QName
    from arelle.ModelVersReport import ModelVersReport
    from arelle.ModelXbrl import ModelXbrl


def relateConceptMdlObjs(
    modelDocument: ModelVersReport,
    fromConceptMdlObjs: list[ModelConceptChange],
    toConceptMdlObjs: list[ModelConceptChange],
) -> None:
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
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelVersObject, self).init(modelDocument)

    @property
    def name(self) -> str:
        return self.localName

    def viewText(self, labelrole: str | None = None, lang: str | None = None) -> str:
        return ""


class ModelAssignment(ModelVersObject):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelAssignment, self).init(modelDocument)
        self.modelDocument.assignments[self.id] = self  # type: ignore[attr-defined]

    @property
    def categoryqname(self) -> str | None:
        for child in self.iterchildren():
            if isinstance(child, ModelObject):
                return "{" + child.namespaceURI + "}" + child.localName  # type: ignore[operator]
        return None

    @property
    def categoryQName(self) -> str | None:
        for child in self.iterchildren():
            if isinstance(child, ModelObject):
                return child.prefixedName
        return None

    @property
    def propertyView(self) -> tuple[tuple[str, str | None], ...]:
        return (("id", self.id),
                ("label", self.genLabel()),
                ("category", self.categoryQName))


class ModelAction(ModelVersObject):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelAction, self).init(modelDocument)
        actionKey = self.id if self.id else "action{0:05}".format(len(self.modelDocument.actions) + 1)  # type: ignore[attr-defined]
        self.modelDocument.actions[actionKey] = self  # type: ignore[attr-defined]
        self.events: list[ModelVersObject] = []

    @property
    def assignmentRefs(self) -> list[str]:
        return XmlUtil.childrenAttrs(self, XbrlConst.ver, "assignmentRef", "ref")

    @property
    def propertyView(self) -> tuple[tuple[str, str | list[str] | None], ...]:
        return (("id", self.id),
                ("label", self.genLabel()),
                ("assgnmts", self.assignmentRefs))


class ModelUriMapped(ModelVersObject):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelUriMapped, self).init(modelDocument)

    @property
    def fromURI(self) -> str | None:
        return XmlUtil.childAttr(self, XbrlConst.ver, "fromURI", "value")

    @property
    def toURI(self) -> str | None:
        return XmlUtil.childAttr(self, XbrlConst.ver, "toURI", "value")

    @property
    def propertyView(self) -> tuple[tuple[str, str | None], ...]:
        return (("fromURI", self.fromURI),
                ("toURI", self.toURI))

    def viewText(self, labelrole: str | None = None, lang: str | None = None) -> str:
        return "{0} -> {1}".format(self.fromURI, self.toURI)


class ModelNamespaceRename(ModelUriMapped):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelNamespaceRename, self).init(modelDocument)
        self.modelDocument.namespaceRenameFrom[self.fromURI] = self  # type: ignore[attr-defined]
        self.modelDocument.namespaceRenameFromURI[self.fromURI] = self.toURI  # type: ignore[attr-defined]
        self.modelDocument.namespaceRenameTo[self.toURI] = self  # type: ignore[attr-defined]
        self.modelDocument.namespaceRenameToURI[self.toURI] = self.fromURI  # type: ignore[attr-defined]


class ModelRoleChange(ModelUriMapped):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelRoleChange, self).init(modelDocument)
        self.modelDocument.roleChanges[self.fromURI] = self  # type: ignore[attr-defined]


class ModelConceptChange(ModelVersObject):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelConceptChange, self).init(modelDocument)

    @property
    def actionId(self) -> str | None:
        return XmlUtil.parentId(self, XbrlConst.ver, "action")

    @property
    def physical(self) -> str:
        return self.get("physical") or "true"  # default="true"

    @property
    def isPhysical(self) -> bool:
        return self.physical == "true"

    @property
    def fromConceptQname(self) -> QName | None:
        fromConcept = XmlUtil.child(self, None, "fromConcept")  # can be vercu or vercb, schema validation will assure right elements
        if fromConcept is not None and fromConcept.get("name"):
            return qname(fromConcept, fromConcept.get("name"))
        else:
            return None

    @property
    def toConceptQname(self) -> QName | None:
        toConcept = XmlUtil.child(self, None, "toConcept")
        if toConcept is not None and toConcept.get("name"):
            return qname(toConcept, toConcept.get("name"))
        else:
            return None

    @property
    def fromConcept(self) -> ModelConcept | None:
        # for href: return self.resolveUri(uri=self.fromConceptValue, dtsModelXbrl=self.modelDocument.fromDTS)
        return self.modelDocument.fromDTS.qnameConcepts.get(self.fromConceptQname)  # type: ignore[arg-type]

    @property
    def toConcept(self) -> ModelConcept | None:
        # return self.resolveUri(uri=self.toConceptValue, dtsModelXbrl=self.modelDocument.toDTS)
        return self.modelDocument.toDTS.qnameConcepts.get(self.toConceptQname)  # type: ignore[arg-type]

    def setConceptEquivalence(self) -> None:
        if self.fromConcept is not None and self.toConcept is not None:
            self.modelDocument.equivalentConcepts[self.fromConcept.qname] = self.toConcept.qname  # type: ignore[attr-defined]

    @property
    def propertyView(self) -> tuple[tuple[str, str | QName | None] | tuple[()], ...]:  # type: ignore[override]
        fromConcept = self.fromConcept
        toConcept = self.toConcept
        return (("event", self.localName),
                ("fromConcept", fromConcept.qname) if fromConcept is not None else (),
                ("toConcept", toConcept.qname) if toConcept is not None else (),)

    def viewText(self, labelrole: str | None = XbrlConst.conceptNameLabelRole, lang: str | None = None) -> str | None:  # type: ignore[override]
        fromConceptQname = self.fromConceptQname
        fromConcept = self.fromConcept
        toConceptQname = self.toConceptQname
        toConcept = self.toConcept
        if (labelrole != XbrlConst.conceptNameLabelRole and
            (fromConceptQname is None or (fromConceptQname is not None and fromConcept is not None)) and
            (toConceptQname is None or (toConceptQname is not None and toConcept is not None))):
            if fromConceptQname is not None:
                if toConceptQname is not None:
                    return fromConcept.label(labelrole, True, lang) + " -> " + toConcept.label(labelrole, True, lang)  # type: ignore[operator,union-attr]
                else:
                    return fromConcept.label(labelrole, True, lang)  # type: ignore[union-attr]
            elif toConceptQname is not None:
                return toConcept.label(labelrole, True, lang)  # type: ignore[union-attr]
            else:
                return "(invalidConceptReference)"
        else:
            if fromConceptQname is not None:
                if toConceptQname is not None:
                    if toConceptQname.localName != fromConceptQname.localName:
                        return str(fromConceptQname) + " -> " + str(toConceptQname)
                    else:
                        return "( " + fromConceptQname.prefix + ": -> " + toConceptQname.prefix + ": ) " + toConceptQname.localName  # type: ignore[operator]
                else:
                    return str(fromConceptQname)
            elif toConceptQname is not None:
                return str(toConceptQname)
            else:
                return "(invalidConceptReference)"


class ModelConceptUseChange(ModelConceptChange):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelConceptUseChange, self).init(modelDocument)
        self.modelDocument.conceptUseChanges.append(self)  # type: ignore[attr-defined]


class ModelConceptDetailsChange(ModelConceptChange):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelConceptDetailsChange, self).init(modelDocument)
        self.modelDocument.conceptDetailsChanges.append(self)  # type: ignore[attr-defined]

    def customAttributeQname(self, eventName: str) -> QName | None:
        custAttrElt = XmlUtil.child(self, None, eventName)  # will be vercd or verce
        if custAttrElt is not None and custAttrElt.get("name"):
            return qname(custAttrElt, custAttrElt.get("name"))
        return None

    @property
    def fromCustomAttributeQname(self) -> QName | None:
        return self.customAttributeQname("fromCustomAttribute")

    @property
    def toCustomAttributeQname(self) -> QName | None:
        return self.customAttributeQname("toCustomAttribute")

    @property
    def fromResourceValue(self) -> str | None:
        return XmlUtil.childAttr(self, None, "fromResource", "value")

    @property
    def toResourceValue(self) -> str | None:
        return XmlUtil.childAttr(self, None, "toResource", "value")

    @property
    def fromResource(self) -> ModelObject | None:
        return self.resolveUri(uri=self.fromResourceValue, dtsModelXbrl=self.modelDocument.fromDTS)

    @property
    def toResource(self) -> ModelObject | None:
        return self.resolveUri(uri=self.toResourceValue, dtsModelXbrl=self.modelDocument.toDTS)

    @property
    def propertyView(self) -> tuple[tuple[str, str | QName | None] | tuple[()], ...]:  # type: ignore[override]
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
                ("toResource", self.toResource.viewText() if self.toResource is not None else "(invalidContentResourceIdentifier)") if self.toResourceValue else (),)


class ModelRelationshipSetChange(ModelVersObject):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelRelationshipSetChange, self).init(modelDocument)
        self.modelDocument.relationshipSetChanges.append(self)  # type: ignore[attr-defined]
        self.fromRelationshipSet: ModelRelationshipSet | None = None
        self.toRelationshipSet: ModelRelationshipSet | None = None

    @property
    def propertyView(self) -> tuple[tuple[str, str]]:
        return (("event", self.localName),)


class ModelRelationshipSet(ModelVersObject):
    modelRelationshipSetEvent: ModelRelationshipSetChange

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelRelationshipSet, self).init(modelDocument)
        self.relationships: list[ModelRelationships] = []

    @property
    def isFromDTS(self) -> bool:
        return self.localName == "fromRelationshipSet"

    @property
    def dts(self) -> ModelXbrl:
        return self.modelDocument.fromDTS if self.isFromDTS else self.modelDocument.toDTS

    @property
    def relationshipSetElement(self) -> ModelObject | None:
        return XmlUtil.child(self, XbrlConst.verrels, "relationshipSet")

    @property
    def link(self) -> QName | None:
        if self.relationshipSetElement and self.relationshipSetElement.get("link"):
            return self.prefixedNameQname(self.relationshipSetElement.get("link"))
        else:
            return None

    @property
    def linkrole(self) -> str | None:
        if self.relationshipSetElement and self.relationshipSetElement.get("linkrole"):
            return self.relationshipSetElement.get("linkrole")
        else:
            return None

    @property
    def arc(self) -> QName | None:
        if self.relationshipSetElement and self.relationshipSetElement.get("arc"):
            return self.prefixedNameQname(self.relationshipSetElement.get("arc"))
        else:
            return None

    @property
    def arcrole(self) -> str | None:
        if self.relationshipSetElement and self.relationshipSetElement.get("arcrole"):
            return self.relationshipSetElement.get("arcrole")
        else:
            return None

    @property
    def propertyView(self) -> tuple[tuple[str, str | None] | tuple[()], ...]:  # type: ignore[override]
        return self.modelRelationshipSetEvent.propertyView + \
               (("model", self.localName),
                ("link", str(self.link)) if self.link else (),
                ("linkrole", self.linkrole) if self.linkrole else (),
                ("arc", str(self.arc)) if self.arc else (),
                ("arcrole", self.arcrole) if self.arcrole else (),)


class ModelRelationships(ModelVersObject):
    modelRelationshipSet: ModelRelationshipSet

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelRelationships, self).init(modelDocument)

    @property
    def fromName(self) -> QName | None:
        if self.get("fromName"):
            return self.prefixedNameQname(self.get("fromName"))
        else:
            return None

    @property
    def toName(self) -> QName | None:
        return self.prefixedNameQname(self.get("toName")) if self.get("toName") else None

    @property
    def fromConcept(self) -> ModelConcept | None:
        # for href: return self.resolveUri(uri=self.fromConceptValue, dtsModelXbrl=self.modelDocument.fromDTS)
        return self.modelRelationshipSet.dts.qnameConcepts.get(self.fromName) if self.fromName else None

    @property
    def toConcept(self) -> ModelConcept | None:
        # return self.resolveUri(uri=self.toConceptValue, dtsModelXbrl=self.modelDocument.toDTS)
        return self.modelRelationshipSet.dts.qnameConcepts.get(self.toName) if self.toName else None

    @property
    def axis(self) -> str | None:
        if self.get("axis"):
            return self.get("axis")
        else:
            return None

    @property
    def isFromDTS(self) -> bool:
        return self.modelRelationshipSet.isFromDTS

    @property
    def fromRelationships(self) -> list[ModelRelationship] | None:
        mdlRel = self.modelRelationshipSet
        relSet: DtsRelationshipSet | None = mdlRel.dts.relationshipSet(
            mdlRel.arcrole, mdlRel.linkrole, mdlRel.link, mdlRel.arc  # type: ignore[arg-type]
        )
        if relSet:
            return relSet.fromModelObject(self.fromConcept)  # type: ignore[arg-type]
        return None

    @property
    def fromRelationship(self) -> ModelRelationship | None:
        fromRelationships = self.fromRelationships
        if not fromRelationships:
            return None
        toName = self.toName
        if self.toName:
            for rel in fromRelationships:
                if rel.toModelObject.qname == toName:  # type: ignore[union-attr]
                    return rel
            return None
        else:   # return first (any) relationship
            return fromRelationships[0]

    @property
    def propertyView(self) -> tuple[tuple[str, str | QName | None] | tuple[()], ...]:  # type: ignore[override]
        return self.modelRelationshipSet.propertyView + \
                (("fromName", self.fromName) if self.fromName else (),
                 ("toName", self.toName) if self.toName else (),
                 ("axis", self.axis) if self.axis else (),)


class ModelInstanceAspectsChange(ModelVersObject):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelInstanceAspectsChange, self).init(modelDocument)
        self.modelDocument.instanceAspectChanges.append(self)  # type: ignore[attr-defined]
        self.fromAspects: ModelInstanceAspects | None = None
        self.toAspects: ModelInstanceAspects | None = None

    @property
    def propertyView(self) -> tuple[tuple[str, str]]:
        return (("event", self.localName),)


class ModelInstanceAspects(ModelVersObject):
    aspectModelEvent: ModelInstanceAspectsChange

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelInstanceAspects, self).init(modelDocument)
        self.aspects: list[ModelInstanceAspect] = []

    @property
    def isFromDTS(self) -> bool:
        return self.localName == "fromAspects"

    @property
    def dts(self) -> ModelXbrl:
        return self.modelDocument.fromDTS if self.isFromDTS else self.modelDocument.toDTS

    @property
    def excluded(self) -> str | None:
        return self.get("excluded") if self.get("excluded") else None

    @property
    def propertyView(self) -> tuple[tuple[str, str | None] | tuple[()], ...]:  # type: ignore[override]
        return self.aspectModelEvent.propertyView + \
               (("excluded", self.excluded) if self.excluded else (),)


class ModelInstanceAspect(ModelVersObject):
    modelAspects: ModelInstanceAspects

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelInstanceAspect, self).init(modelDocument)
        self.aspectProperties: list[ModelAspectProperty] = []

    @property
    def isFromDTS(self) -> bool:
        return self.modelAspects.isFromDTS

    @property
    def propertyView(self) -> tuple[tuple[str, str | None] | tuple[()], ...]:  # type: ignore[override]
        return self.modelAspects.propertyView + \
               (("aspect", self.localName),
                ) + self.elementAttributesTuple


class ModelConceptsDimsAspect(ModelInstanceAspect):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelConceptsDimsAspect, self).init(modelDocument)
        self.relatedConcepts: list[ModelRelatedConcept] = []

    @property
    def conceptName(self) -> QName | None:
        return self.prefixedNameQname(self.get("name")) if self.get("name") else None

    @property
    def concept(self) -> ModelConcept | None:
        # for href: return self.resolveUri(uri=self.fromConceptValue, dtsModelXbrl=self.modelDocument.fromDTS)
        return self.modelAspects.dts.qnameConcepts.get(self.conceptName) if self.conceptName else None

    @property
    def sourceDtsObject(self) -> ModelConcept | None:
        if self.localName == "explicitDimension":
            return self.concept
        return None


class ModelPeriodAspect(ModelInstanceAspect):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelPeriodAspect, self).init(modelDocument)
        self.relatedPeriods: list[Any] = []


class ModelMeasureAspect(ModelInstanceAspect):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelMeasureAspect, self).init(modelDocument)
        self.relatedMeasures: list[Any] = []


# this class is both for explicitDimension member and concepts concept elements
class ModelRelatedConcept(ModelVersObject):
    modelAspect: ModelInstanceAspect

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelRelatedConcept, self).init(modelDocument)

    @property
    def conceptName(self) -> QName | None:
        return self.prefixedNameQname(self.get("name")) if self.get("name") else None

    @property
    def concept(self) -> ModelConcept | None:
        # for href: return self.resolveUri(uri=self.fromConceptValue, dtsModelXbrl=self.modelDocument.fromDTS)
        return self.modelAspect.modelAspects.dts.qnameConcepts.get(self.conceptName) if self.conceptName else None

    @property
    def sourceDtsObject(self) -> ModelConcept | None:
        return self.concept

    @property
    def isFromDTS(self) -> bool:
        return self.modelAspect.modelAspects.isFromDTS

    @property
    def hasNetwork(self) -> bool:
        return XmlUtil.hasChild(self, XbrlConst.verdim, "network")

    @property
    def hasDrsNetwork(self) -> bool:
        return XmlUtil.hasChild(self, XbrlConst.verdim, "drsNetwork")

    @property
    def arcrole(self) -> str | None:
        return XmlUtil.childAttr(self, XbrlConst.verdim, ("network", "drsNetwork"), "arcrole")

    @property
    def linkrole(self) -> str | None:
        return XmlUtil.childAttr(self, XbrlConst.verdim, ("network", "drsNetwork"), "linkrole")

    @property
    def arc(self) -> QName | None:
        arc = XmlUtil.childAttr(self, XbrlConst.verdim, ("network", "drsNetwork"), "arc")
        return self.prefixedNameQname(arc) if arc else None

    @property
    def link(self) -> QName | None:
        link = XmlUtil.childAttr(self, XbrlConst.verdim, ("network", "drsNetwork"), "link")
        return self.prefixedNameQname(link) if link else None

    @property
    def propertyView(self) -> tuple[tuple[str, str | None] | tuple[()], ...]:  # type: ignore[override]
        return self.modelAspect.propertyView + \
               ((self.localName, ""),
                ) + self.elementAttributesTuple


# this class is both for properties of aspects period and measure
class ModelAspectProperty(ModelVersObject):
    modelAspect: ModelInstanceAspect

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelAspectProperty, self).init(modelDocument)

    @property
    def propertyView(self) -> tuple[tuple[str, str | None] | tuple[()], ...]:  # type: ignore[override]
        return self.modelAspect.propertyView + \
               ((self.localName, ""),
                ) + self.elementAttributesTuple


from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
    # 2010 names
    (qname(XbrlConst.ver10, "assignment"), ModelAssignment),
    (qname(XbrlConst.ver10, "action"), ModelAction),
    (qname(XbrlConst.ver10, "namespaceRename"), ModelNamespaceRename),
    (qname(XbrlConst.ver10, "roleChange"), ModelRoleChange),
    (qname(XbrlConst.vercb, "conceptAdd"), ModelConceptUseChange),
    (qname(XbrlConst.vercb, "conceptDelete"), ModelConceptUseChange),
    (qname(XbrlConst.vercb, "conceptRename"), ModelConceptUseChange),
    (qname(XbrlConst.verce, "conceptIDChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptTypeChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptSubstitutionGroupChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptDefaultChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptNillableChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptAbstractChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptBlockChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptFixedChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptFinalChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptPeriodTypeChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptBalanceChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptAttributeAdd"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptAttributeDelete"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptAttributeChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "tupleContentModelChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptLabelAdd"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptLabelDelete"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptLabelChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptReferenceAdd"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptReferenceDelete"), ModelConceptDetailsChange),
    (qname(XbrlConst.verce, "conceptReferenceChange"), ModelConceptDetailsChange),
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
    (qname(XbrlConst.veria, "explicitDimension"), ModelConceptsDimsAspect),
    (qname(XbrlConst.veria, "typedDimension"), ModelConceptsDimsAspect),
    (qname(XbrlConst.veria, "segment"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "scenario"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "entityIdentifier"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "period"), ModelPeriodAspect),
    (qname(XbrlConst.veria, "location"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "unit"), ModelInstanceAspect),
    (qname(XbrlConst.veria, "member"), ModelRelatedConcept),
    (qname(XbrlConst.veria, "startDate"), ModelRelatedConcept),
    (qname(XbrlConst.veria, "endDate"), ModelAspectProperty),
    (qname(XbrlConst.veria, "instant"), ModelAspectProperty),
    (qname(XbrlConst.veria, "forever"), ModelAspectProperty),
    (qname(XbrlConst.veria, "multiplyBy"), ModelMeasureAspect),
    (qname(XbrlConst.veria, "divideBy"), ModelMeasureAspect),
    (qname(XbrlConst.veria, "measure"), ModelAspectProperty),
    # 2013 names
    (qname(XbrlConst.ver, "assignment"), ModelAssignment),
    (qname(XbrlConst.ver, "action"), ModelAction),
    (qname(XbrlConst.ver, "namespaceRename"), ModelNamespaceRename),
    (qname(XbrlConst.ver, "roleChange"), ModelRoleChange),
    (qname(XbrlConst.vercu, "conceptAdd"), ModelConceptUseChange),
    (qname(XbrlConst.vercu, "conceptDelete"), ModelConceptUseChange),
    (qname(XbrlConst.vercu, "conceptRename"), ModelConceptUseChange),
    (qname(XbrlConst.vercd, "conceptIDChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptTypeChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptSubstitutionGroupChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptDefaultChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptNillableChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptAbstractChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptBlockChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptFixedChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptFinalChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptPeriodTypeChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptBalanceChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptAttributeAdd"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptAttributeDelete"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptAttributeChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "attributeDefinitionChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "tupleContentModelChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptLabelAdd"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptLabelDelete"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptLabelChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptReferenceAdd"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptReferenceDelete"), ModelConceptDetailsChange),
    (qname(XbrlConst.vercd, "conceptReferenceChange"), ModelConceptDetailsChange),
    (qname(XbrlConst.verdim, "aspectModelChange"), ModelInstanceAspectsChange),
    (qname(XbrlConst.verdim, "aspectModelAdd"), ModelInstanceAspectsChange),
    (qname(XbrlConst.verdim, "aspectModelDelete"), ModelInstanceAspectsChange),
    (qname(XbrlConst.verdim, "fromAspects"), ModelInstanceAspects),
    (qname(XbrlConst.verdim, "toAspects"), ModelInstanceAspects),
    (qname(XbrlConst.verdim, "concepts"), ModelConceptsDimsAspect),
    (qname(XbrlConst.verdim, "explicitDimension"), ModelConceptsDimsAspect),
    (qname(XbrlConst.verdim, "typedDimension"), ModelConceptsDimsAspect),
    (qname(XbrlConst.verdim, "concept"), ModelRelatedConcept),
    (qname(XbrlConst.verdim, "member"), ModelRelatedConcept),
     ))
