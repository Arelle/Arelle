'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import TYPE_CHECKING

from arelle import UrlUtil, XbrlConst
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelObject import ModelObject
from arelle.PrototypeInstanceObject import ContextPrototype, DimValuePrototype
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelDtsObject import ModelRelationship
    from arelle.ModelInstanceObject import ModelContext, ModelFact
    from arelle.ModelRelationshipSet import ModelRelationshipSet
    from arelle.ValidateXbrl import ValidateXbrl
    from arelle.ModelManager import ModelManager
    from arelle.ModelXbrl import ModelXbrl
    from arelle.PrototypeInstanceObject import FactPrototype
    from arelle.formula.XPathContext import XPathContext

_: TypeGetText

NONDEFAULT = sys.intern(str("non-default"))


def loadDimensionDefaults(val: ModelManager | ModelXbrl) -> None:
    # load dimension defaults when required without performing validations
    assert val.modelXbrl is not None, "modelXbrl not loaded"
    val.modelXbrl.dimensionDefaultConcepts = {}
    val.modelXbrl.qnameDimensionDefaults = {}
    val.modelXbrl.qnameDimensionContextElement = {}
    for baseSetKey in val.modelXbrl.baseSets.keys():
        arcrole, ELR, linkqname, arcqname = baseSetKey
        if ELR and linkqname and arcqname and arcrole in (XbrlConst.all, XbrlConst.dimensionDefault):
            checkBaseSet(val, arcrole, ELR, val.modelXbrl.relationshipSet(arcrole,ELR,linkqname,arcqname))  # type: ignore[arg-type]
    val.modelXbrl.isDimensionsValidated = True


def checkBaseSet(val: ValidateXbrl | ModelXbrl, arcrole: str, ELR: str, relsSet: ModelRelationshipSet) -> None:
    # check hypercube-dimension relationships
    if arcrole == XbrlConst.hypercubeDimension:
        for modelRel in relsSet.modelRelationships:
            fromConcept = modelRel.fromModelObject
            toConcept = modelRel.toModelObject
            if fromConcept is not None and toConcept is not None:
                if not isinstance(fromConcept, ModelConcept) or not fromConcept.isHypercubeItem:
                    val.modelXbrl.error("xbrldte:HypercubeDimensionSourceError",
                        _("Hypercube-dimension relationship from %(source)s to %(target)s in link role %(linkrole)s must have a hypercube declaration source"),
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                if not isinstance(toConcept, ModelConcept) or not toConcept.isDimensionItem:
                    val.modelXbrl.error("xbrldte:HypercubeDimensionTargetError",
                        _("Hypercube-dimension relationship from %(source)s to %(target)s in link role %(linkrole)s must have a dimension declaration target"),
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
    # check all, notAll relationships
    elif arcrole in (XbrlConst.all, XbrlConst.notAll):
        fromRelationships = relsSet.fromModelObjects()
        for priItemConcept, hcRels in fromRelationships.items():
            for hasHcRel in hcRels:
                hcConcept = hasHcRel.toModelObject
                if priItemConcept is not None and hcConcept is not None:
                    if not isinstance(priItemConcept, ModelConcept) or not priItemConcept.isPrimaryItem:
                        val.modelXbrl.error("xbrldte:HasHypercubeSourceError",
                            _("HasHypercube %(arcroleType)s relationship from %(source)s to %(target)s in link role %(linkrole)s must have a primary item source"),
                            modelObject=hasHcRel, arcroleType=os.path.basename(arcrole),
                            source=priItemConcept.qname, target=hcConcept.qname, linkrole=ELR)
                    if not isinstance(hcConcept, ModelConcept) or not hcConcept.isHypercubeItem:
                        val.modelXbrl.error("xbrldte:HasHypercubeTargetError",
                            _("HasHypercube %(arcroleType)s relationship from %(source)s to %(target)s in link role %(linkrole)s must have a hypercube declaration target"),
                            modelObject=hasHcRel, arcroleType=os.path.basename(arcrole),
                            source=priItemConcept.qname, target=hcConcept.qname, linkrole=ELR)
                    hcContextElement = hasHcRel.contextElement
                    if hcContextElement not in ("segment","scenario"):
                        val.modelXbrl.error("xbrldte:HasHypercubeMissingContextElementAttributeError",
                            _("HasHypercube %(arcroleType)s relationship from %(source)s to %(target)s in link role %(linkrole)s must have a context element"),
                            modelObject=hasHcRel, arcroleType=os.path.basename(arcrole),
                            source=priItemConcept.qname, target=hcConcept.qname, linkrole=ELR)

                    # must check the cycles starting from hypercube ELR (primary item consec relationship
                    dimELR = hasHcRel.targetRole
                    if not dimELR:
                        dimELR = ELR
                    hcDimRels = val.modelXbrl.relationshipSet(
                         XbrlConst.hypercubeDimension, dimELR).fromModelObject(hcConcept)
                    for hcDimRel in hcDimRels:
                        dimConcept = hcDimRel.toModelObject
                        if dimConcept is not None:
                            if arcrole == XbrlConst.all:
                                cntxElt = val.modelXbrl.qnameDimensionContextElement.setdefault(dimConcept.qname, hcContextElement)  # type: ignore[arg-type]
                                if cntxElt != hcContextElement:
                                    val.modelXbrl.qnameDimensionContextElement[dimConcept.qname] = "ambiguous"
                            domELR = hcDimRel.targetRole
                            if not domELR:
                                domELR = dimELR
                            dimDomRels = val.modelXbrl.relationshipSet(
                                 XbrlConst.dimensionDomain, domELR).fromModelObject(dimConcept)
                            cycle = xdtCycle(val, domainTargetRoles(val, domELR,dimDomRels), dimDomRels, {hcConcept, dimConcept})  # type: ignore[arg-type]
                            if cycle is not None:
                                if cycle is not None:
                                    cycle.append(hcDimRel)
                                    path = str(hcConcept.qname) + " " + " - ".join(
                                        "{0}:{1} {2}".format(rel.modelDocument.basename, rel.sourceline, (rel.toModelObject.qname if isinstance(rel.toModelObject, ModelObject) else None))
                                        for rel in reversed(cycle))
                                val.modelXbrl.error("xbrldte:DRSDirectedCycleError",
                                    _("Dimension relationships have a directed cycle in DRS role %(linkrole)s \nstarting from hypercube %(hypercube)s, \ndimension %(dimension)s, \npath %(path)s"),
                                    modelObject=[hcConcept] + cycle, hypercube=hcConcept.qname, dimension=dimConcept.qname, linkrole=ELR, path=path)
                            cycle = drsPolymorphism(val, domELR, dimDomRels, drsPriItems(val, ELR, priItemConcept))  # type: ignore[arg-type]
                            if cycle is not None:
                                if cycle is not None:
                                    cycle.append(hcDimRel)
                                    path = str(priItemConcept.qname) + " " + " - ".join(
                                        "{0}:{1} {2}".format(rel.modelDocument.basename, rel.sourceline, (rel.toModelObject.qname if isinstance(rel.toModelObject, ModelObject) else None))
                                        for rel in reversed(cycle))
                                val.modelXbrl.error("xbrldte:PrimaryItemPolymorphismError",
                                    _("Dimension relationships have a polymorphism cycle in DRS role %(linkrole)s \nstarting from hypercube %(hypercube)s, \ndimension %(dimension)s, \npath %(path)s"),
                                    modelObject=[hcConcept] + cycle, hypercube=hcConcept.qname, dimension=dimConcept.qname, linkrole=ELR, path=path)
    # check dimension-domain relationships
    elif arcrole == XbrlConst.dimensionDomain:
        for modelRel in relsSet.modelRelationships:
            fromConcept = modelRel.fromModelObject
            toConcept = modelRel.toModelObject
            if fromConcept is not None and toConcept is not None:   # none if failed to load
                if not isinstance(fromConcept, ModelConcept) or not fromConcept.isDimensionItem:
                    val.modelXbrl.error("xbrldte:DimensionDomainSourceError",
                        _("Dimension-domain relationship from %(source)s to %(target)s in link role %(linkrole)s must have a dimension declaration source"),
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                elif fromConcept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef") is not None:
                    val.modelXbrl.error("xbrldte:DimensionDomainSourceError",
                        _("Dimension-domain relationship from %(source)s to %(target)s in link role %(linkrole)s has a typed dimension source"),
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                if not isinstance(toConcept, ModelConcept) or not toConcept.isDomainMember:
                    val.modelXbrl.error("xbrldte:DimensionDomainTargetError",
                        _("Dimension-domain relationship from %(source)s to %(target)s in link role %(linkrole)s must have a domain member target"),
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
    # check dimension-default relationships
    elif arcrole == XbrlConst.dimensionDefault:
        for modelRel in relsSet.modelRelationships:
            fromConcept = modelRel.fromModelObject
            toConcept = modelRel.toModelObject
            if fromConcept is not None and toConcept is not None:
                if not isinstance(fromConcept, ModelConcept) or not fromConcept.isDimensionItem:
                    val.modelXbrl.error("xbrldte:DimensionDefaultSourceError",
                        _("Dimension-default relationship from %(source)s to %(target)s in link role %(linkrole)s must have a dimension declaration source"),
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                elif fromConcept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef"):
                    val.modelXbrl.error("xbrldte:DimensionDefaultSourceError",
                        _("Dimension-default relationship from %(source)s to %(target)s in link role %(linkrole)s has a typed dimension source"),
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                if not isinstance(toConcept, ModelConcept) or not toConcept.isDomainMember:
                    val.modelXbrl.error("xbrldte:DimensionDefaultTargetError",
                        _("Dimension-default relationship from %(source)s to %(target)s in link role %(linkrole)s must have a domain member target"),
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                if fromConcept in val.modelXbrl.dimensionDefaultConcepts and toConcept != val.modelXbrl.dimensionDefaultConcepts[fromConcept]:
                    val.modelXbrl.error("xbrldte:TooManyDefaultMembersError",
                        _("Dimension %(source)s has multiple defaults %(target)s and %(target2)s"),
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname,
                        target2=val.modelXbrl.dimensionDefaultConcepts[fromConcept].qname)
                else:
                    val.modelXbrl.dimensionDefaultConcepts[fromConcept] = toConcept  # type: ignore[index,assignment]
                    val.modelXbrl.qnameDimensionDefaults[fromConcept.qname] = toConcept.qname

    # check for primary item cycles
    elif arcrole == XbrlConst.domainMember:
        fromRelationships = relsSet.fromModelObjects()
        for priItemConcept, rels in fromRelationships.items():
                for domMbrRel in rels:
                    toConcept = domMbrRel.toModelObject
                    if toConcept is not None:
                        if not isinstance(priItemConcept, ModelConcept) or not priItemConcept.isDomainMember:
                            val.modelXbrl.error("xbrldte:DomainMemberSourceError",
                                _("Domain-Member relationship from %(source)s to %(target)s in link role %(linkrole)s must have a domain primary item or domain member source"),
                                modelObject=domMbrRel, source=priItemConcept.qname, target=toConcept.qname, linkrole=ELR)
                        if not isinstance(toConcept, ModelConcept) or not toConcept.isDomainMember:
                            val.modelXbrl.error("xbrldte:DomainMemberTargetError",
                                _("Domain-Member relationship from %(source)s to %(target)s in link role %(linkrole)s must have a domain primary item or domain member target"),
                                modelObject=domMbrRel, source=priItemConcept.qname, target=toConcept.qname, linkrole=ELR)


def domainTargetRoles(
    val: ModelXbrl,
    fromELR: str,
    rels: list[ModelRelationship],
    fromConcepts: set[ModelObject] | None = None,
    ELRs: set[str] | None = None,
) -> set[str]:
    if fromConcepts is None:
        fromConcepts = set()
    if not ELRs:
        ELRs = {fromELR}
    for rel in rels:
        relTo = rel.toModelObject
        if relTo not in fromConcepts:
            fromConcepts.add(relTo)  # type: ignore[arg-type]
            toELR = rel.targetRole
            if toELR:
                ELRs.add(toELR)
            else:
                toELR = fromELR
            domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(relTo)  # type: ignore[arg-type]
            domainTargetRoles(val, toELR, domMbrRels, fromConcepts, ELRs)
            fromConcepts.discard(relTo)
    return ELRs


def xdtCycle(
    val: ModelXbrl,
    ELRs: set[str],
    rels: list[ModelRelationship],
    fromConcepts: set[ModelObject],
) -> list[ModelRelationship] | None:
    for rel in rels:
        relTo = rel.toModelObject
        if rel.isUsable and relTo in fromConcepts: # don't think we want this?? and toELR == drsELR: #forms a directed cycle
            return [rel,]
        fromConcepts.add(relTo)  # type: ignore[arg-type]
        for ELR in ELRs:
            domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, ELR).fromModelObject(relTo)  # type: ignore[arg-type]
            foundCycle = xdtCycle(val, ELRs, domMbrRels, fromConcepts)
            if foundCycle is not None:
                foundCycle.append(rel)
                return foundCycle
        fromConcepts.discard(relTo)
    return None


def drsPriItems(
    val: ModelXbrl,
    fromELR: str,
    fromPriItem: ModelObject,
    priItems: set[ModelObject] | None = None,
) -> set[ModelObject]:
    if priItems is None:
        priItems = {fromPriItem}
    for rel in  val.modelXbrl.relationshipSet(XbrlConst.domainMember, fromELR).fromModelObject(fromPriItem):
        toPriItem = rel.toModelObject
        if toPriItem not in priItems:
            if rel.isUsable:
                priItems.add(toPriItem)  # type: ignore[arg-type]
            toELR = rel.targetRole
            drsPriItems(val, toELR if toELR else fromELR, toPriItem, priItems)  # type: ignore[arg-type]
    return priItems


def drsPolymorphism(
    val: ModelXbrl,
    fromELR: str,
    rels: list[ModelRelationship],
    priItems: set[ModelObject],
    visitedMbrs: set[ModelObject] | None = None,
) -> list[ModelRelationship] | None:
    if visitedMbrs is None:
        visitedMbrs = set()
    for rel in rels:
        relTo = rel.toModelObject
        toELR = rel.targetRole
        if not toELR:
            toELR = fromELR
        if rel.isUsable and relTo in priItems: # don't think we want this?? and toELR == drsELR: #forms a directed cycle
            return [rel,]
        if relTo not in visitedMbrs:
            visitedMbrs.add(relTo)  # type: ignore[arg-type]
            domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(relTo)  # type: ignore[arg-type]
            foundCycle = drsPolymorphism(val, toELR, domMbrRels, priItems, visitedMbrs)
            if foundCycle is not None:
                foundCycle.append(rel)
                return foundCycle
            visitedMbrs.discard(relTo)
    return None


def checkConcept(val: ValidateXbrl, concept: ModelConcept) -> None:
    if concept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef"):
        if concept.isDimensionItem:
            typedDomainElement = concept.typedDomainElement
            if typedDomainElement is None:
                url, id = UrlUtil.splitDecodeFragment(concept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef"))  # type: ignore[arg-type]
                if len(id) == 0:
                    val.modelXbrl.error("xbrldte:TypedDimensionURIError",
                        _("Concept %(concept)s typedDomainRef has no fragment identifier"),
                        modelObject=concept, concept=concept.qname)
                else:
                    val.modelXbrl.error("xbrldte:OutOfDTSSchemaError",
                        _("Concept %(concept)s typedDomainRef is not resolved"),
                        modelObject=concept, concept=concept.qname)
            elif not isinstance(typedDomainElement, ModelConcept) or \
                        not typedDomainElement.isGlobalDeclaration or \
                        typedDomainElement.abstract == "true":
                val.modelXbrl.error("xbrldte:TypedDimensionError",
                    _("Concept %(concept)s typedDomainRef must identify a non-abstract element"),
                        modelObject=concept, concept=concept.qname)
        else:
            val.modelXbrl.error("xbrldte:TypedDomainRefError",
                _("Concept %(concept)s is not a dimension item but has a typedDomainRef"),
                modelObject=concept, concept=concept.qname)


def checkContext(val: ValidateXbrl, cntx: ModelContext) -> None:
    def logDimAndFacts(modelDimValue: ModelObject) -> list[ModelObject]:
        dimAndFacts: list[ModelObject] = [modelDimValue]
        for f in val.modelXbrl.facts:
            if f.context == cntx:
                dimAndFacts.append(f)
                if len(dimAndFacts) > 10:   # log up to 10 facts using this context
                    break
        return dimAndFacts

    # check errorDimensions of context
    for modelDimValues in (cntx.segDimValues.values(), cntx.scenDimValues.values(), cntx.errorDimValues):
        for modelDimValue in modelDimValues:
            dimensionConcept = modelDimValue.dimension
            if dimensionConcept is None or \
                not dimensionConcept.isDimensionItem or \
                modelDimValue.isTyped != (dimensionConcept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef") is not None):
                val.modelXbrl.error("xbrldie:TypedMemberNotTypedDimensionError" if modelDimValue.isTyped else "xbrldie:ExplicitMemberNotExplicitDimensionError",
                    _("Context %(contextID)s %(dimension)s %(value)s is not an appropriate dimension item"),
                    modelObject=logDimAndFacts(modelDimValue), contextID=cntx.id,
                    dimension=modelDimValue.prefixedName, value=modelDimValue.dimensionQname,
                    messageCodes=("xbrldie:TypedMemberNotTypedDimensionError", "xbrldie:ExplicitMemberNotExplicitDimensionError"))
            elif modelDimValue.isTyped:
                typedDomainConcept = dimensionConcept.typedDomainElement
                problem = _("missing content")
                for element in modelDimValue:
                    if isinstance(element,ModelObject):
                        if problem is None:
                            problem = _("multiple contents")
                        elif typedDomainConcept is None:
                            problem = _("Missing domain element schema definition for {0}").format(dimensionConcept.typedDomainRef)
                        elif (element.localName != typedDomainConcept.name or  # type: ignore[attr-defined]
                            element.namespaceURI != typedDomainConcept.modelDocument.targetNamespace):
                            problem = _("wrong content {0}").format(element.prefixedName)
                        else:
                            problem = None  # type: ignore[assignment]
                            # validate enumeration set typed dimension value here
                            if (val.validateEnum and typedDomainConcept.isEnumeration and getattr(element,"xValid", 0) == 4 and  # type: ignore[attr-defined]
                                element.get("{http://www.w3.org/2001/XMLSchema-instance}nil") not in ("true","1")):
                                qnEnums = element.xValue
                                if not isinstance(qnEnums, list): qnEnums = (qnEnums,)  # type: ignore[assignment]
                                if not all(enumerationMemberUsable(val, typedDomainConcept, val.modelXbrl.qnameConcepts.get(qnEnum))  # type: ignore[arg-type]
                                           for qnEnum in qnEnums):  # type: ignore[union-attr]
                                    val.modelXbrl.error("enum2ie:InvalidDimensionSetValue",
                                        _("Dimension value %(dimensionMember)s context %(contextID)s enumeration %(value)s is not in the domain of %(concept)s"),
                                        modelObject=element, dimensionMember=element.qname, contextID=cntx.id, value=element.xValue, concept=element.qname)
                                if len(qnEnums) > len(set(qnEnums)):  # type: ignore[arg-type]
                                    val.modelXbrl.error("enum2ie:RepeatedDimensionSetValue",
                                        _("Dimension value %(dimensionMember)s context %(contextID)s enumeration has non-unique values %(value)s"),
                                        modelObject=element, dimensionMember=element.qname, contextID=cntx.id, value=element.xValue, concept=element.qname)
                                if any(qnEnum < qnEnums[i] for i, qnEnum in enumerate(qnEnums[1:])):  # type: ignore[index,arg-type]
                                    val.modelXbrl.error("enum2ie:InvalidDimensionSetOrder",
                                        _("Dimension value %(dimensionMember) context %(contextID)s enumeration is not in lexicographical order %(value)s"),
                                        modelObject=element, dimensionMember=element.qname, contextID=cntx.id, value=element.xValue, concept=element.qname)
                if problem:
                    val.modelXbrl.error("xbrldie:IllegalTypedDimensionContentError",
                        _("Context %(contextID)s typed dimension %(dimension)s has %(error)s"),
                        modelObject=logDimAndFacts(modelDimValue), contextID=cntx.id,
                        dimension=modelDimValue.dimensionQname, error=problem)
            if modelDimValue.isExplicit: # this test is required even when ExplicitMemberNotExplicitDimensionError is raised
                memberConcept = modelDimValue.member
                if memberConcept is None or not memberConcept.isGlobalDeclaration:
                    val.modelXbrl.error("xbrldie:ExplicitMemberUndefinedQNameError",
                        _("Context %(contextID)s explicit dimension %(dimension)s member %(value)s is not a global member item"),
                        modelObject=logDimAndFacts(modelDimValue), contextID=cntx.id,
                        dimension=modelDimValue.dimensionQname, value=modelDimValue.memberQname)
                elif val.modelXbrl.dimensionDefaultConcepts.get(dimensionConcept) == memberConcept:  # type: ignore[arg-type]
                    val.modelXbrl.error("xbrldie:DefaultValueUsedInInstanceError",
                        _("Context %(contextID)s explicit dimension %(dimension)s member %(value)s is a default member item"),
                        modelObject=logDimAndFacts(modelDimValue), contextID=cntx.id,
                        dimension=modelDimValue.dimensionQname, value=modelDimValue.memberQname)

    for modelDimValue in cntx.errorDimValues:
        dimensionConcept = modelDimValue.dimension
        if dimensionConcept is not None \
           and (dimensionConcept in cntx.segDimValues or dimensionConcept in cntx.scenDimValues):
            val.modelXbrl.error("xbrldie:RepeatedDimensionInInstanceError",
                _("Context %(contextID)s dimension %(dimension)s is a repeated dimension value"),
                modelObject=logDimAndFacts(modelDimValue), contextID=cntx.id, dimension=modelDimValue.dimensionQname)
    # decision by WG that dimensions in both seg & scen is also a duplication
    for modelDimValue in cntx.segDimValues.values():
        dimensionConcept = modelDimValue.dimension
        if dimensionConcept is not None and dimensionConcept in cntx.scenDimValues:
            val.modelXbrl.error("xbrldie:RepeatedDimensionInInstanceError",
                _("Context %(contextID)s dimension %(dimension)s is a repeated dimension value"),
                modelObject=logDimAndFacts(modelDimValue), contextID=cntx.id, dimension=modelDimValue.dimensionQname)


def checkFact(val: ValidateXbrl, f: ModelFact, otherFacts: set[ModelFact] | None = None) -> None:
    if not isFactDimensionallyValid(val, f, otherFacts=otherFacts):
        val.modelXbrl.error("xbrldie:PrimaryItemDimensionallyInvalidError",
            _("Fact %(fact)s context %(contextID)s dimensionally not valid"),
            modelObject=f, fact=f.qname, contextID=f.context.id)  # type: ignore[union-attr]


def isFactDimensionallyValid(
        val: ValidateXbrl | ModelXbrl,
        f: ModelFact | FactPrototype,
        setPrototypeContextElements: bool = False,
        otherFacts: set[ModelFact] | None = None
    ) -> bool:
    hasElrHc = False
    for ELR, hcRels in priItemElrHcRels(val, f.concept).items():  # type: ignore[arg-type]
        hasElrHc = True
        '''
        if otherFacts: # find relevant facts with compatible primary items and same dims
            relevantPriItems = set.intersection(*[priItemsOfElrHc(val, rel.fromModelObject, ELR, ELR)
                                                  for rel in hcRels])
            relevantFactsByPriItems = set.union(*[val.factsByQname(priItem.qname)
                                                for priItem in relevantPriItems]) & otherFacts
            relevantFactsByDims = set.instersection(relevantFactsByPriItems,
                                                    *[val.factsByDimMemQname(dimQname, NONDEFAULT)
                                                      for dimQname in f.context.dimAspects(val.modelXbrl.qnameDimensionDefaults.keys())])
        else:
            relevantFactsByDims = None
        '''
        if checkFactElrHcs(val, f, ELR, hcRels, setPrototypeContextElements):  # type: ignore[arg-type]
            return True # meets hypercubes in this ELR

    if hasElrHc:
        # no ELR hypercubes fully met
        return False
    return True


def priItemElrHcRels(val: ModelXbrl | XPathContext, priItem: ModelConcept, ELR: str | None = None) -> dict[str, list[ModelRelationship]]:
    key = (priItem, ELR)
    try:
        priItemElrHcRels = val.priItemElrHcRels  # type: ignore[union-attr]
    except AttributeError:
        priItemElrHcRels = val.priItemElrHcRels = {}  # type: ignore[union-attr]
    try:
        return priItemElrHcRels[key]  # type: ignore[no-any-return]
    except KeyError:
        rels = priItemElrHcRels[key] = findPriItemElrHcRels(val, priItem, ELR)  # type: ignore[arg-type]
        return rels


def findPriItemElrHcRels(
    val: ModelXbrl,
    priItem: ModelObject,
    ELR: str | None = None,
    elrHcRels: defaultdict[str, list[ModelRelationship]] | None = None,
    seenPrimaryItems: set[tuple[str | None, ModelObject]] | None = None,
) -> dict[str, list[ModelRelationship]]:
    if elrHcRels is None:
        elrHcRels = defaultdict(list)
    if seenPrimaryItems is None:
        seenPrimaryItems = set()
    seenConceptsKey = (ELR, priItem)
    if seenConceptsKey in seenPrimaryItems:
        return elrHcRels
    seenPrimaryItems.add(seenConceptsKey)
    # add has hypercube relationships for ELR
    for arcrole in (XbrlConst.all, XbrlConst.notAll):
        for hasHcRel in val.modelXbrl.relationshipSet(arcrole,ELR).fromModelObject(priItem):
            elrHcRels[hasHcRel.linkrole].append(hasHcRel)  # type: ignore[index]
    # check inherited ELRs
    for domMbrRel in val.modelXbrl.relationshipSet(XbrlConst.domainMember).toModelObject(priItem):
        relLinkrole = domMbrRel.linkrole
        toELR = (domMbrRel.targetRole or relLinkrole)
        if ELR is None or ELR == toELR:
            findPriItemElrHcRels(val, domMbrRel.fromModelObject, relLinkrole, elrHcRels, seenPrimaryItems)  # type: ignore[arg-type]
    return elrHcRels


def priItemsOfElrHc(
    val: ModelXbrl,
    priItem: ModelObject,
    hcELR: str,
    relELR: str,
    priItems: set[ModelObject] | None = None,
) -> set[ModelObject]:
    if priItems is None:
        priItems = {priItem}
    for domMbrRel in val.modelXbrl.relationshipSet(XbrlConst.domainMember, relELR).fromModelObject(priItem):
        toPriItem = domMbrRel.toModelObject
        linkrole = domMbrRel.consecutiveLinkrole
        if linkrole == hcELR:
            priItems.add(toPriItem)  # type: ignore[arg-type]
        priItemsOfElrHc(val, toPriItem, hcELR, linkrole, priItems)  # type: ignore[arg-type]
    return priItems


NOT_FOUND = 0
MEMBER_USABLE = 1
MEMBER_NOT_USABLE = 2


def checkFactElrHcs(
    val: ModelXbrl,
    f: ModelFact,
    ELR: str,
    hcRels: list[ModelRelationship],
    setPrototypeContextElements: bool = False,
) -> bool:
    context = f.context
    elrValid = True # start assuming ELR is valid

    for hasHcRel in hcRels:
        hcConcept = hasHcRel.toModelObject
        hcIsClosed = hasHcRel.isClosed
        hcContextElement = hasHcRel.contextElement
        hcNegating = hasHcRel.arcrole == XbrlConst.notAll
        modelDimValues = context.dimValues(hcContextElement)  # type: ignore[arg-type,union-attr]
        if setPrototypeContextElements and isinstance(context,ContextPrototype):
            oppositeContextDimValues = context.dimValues(hcContextElement, oppositeContextElement=True)
        contextElementDimSet = set(modelDimValues.keys())
        modelNonDimValues = context.nonDimValues(hcContextElement)  # type: ignore[arg-type,union-attr]
        hcValid = True

        # if closed and any nonDim values, hc invalid
        if hcIsClosed and len(modelNonDimValues) > 0:
            hcValid = False
        else:
            dimELR = (hasHcRel.targetRole or ELR)
            for hcDimRel in val.modelXbrl.relationshipSet(
                                XbrlConst.hypercubeDimension, dimELR).fromModelObject(hcConcept):  # type: ignore[arg-type]
                dimConcept = hcDimRel.toModelObject
                if isinstance(dimConcept, ModelConcept):
                    domELR = (hcDimRel.targetRole or dimELR)
                    if dimConcept in modelDimValues:
                        memModelDimension = modelDimValues[dimConcept]
                        contextElementDimSet.discard(dimConcept)
                        memConcept = memModelDimension.member
                    elif dimConcept in val.modelXbrl.dimensionDefaultConcepts:
                        memConcept = val.modelXbrl.dimensionDefaultConcepts[dimConcept]
                        memModelDimension = None
                    elif setPrototypeContextElements and isinstance(context,ContextPrototype) and dimConcept in oppositeContextDimValues:
                        memModelDimension = oppositeContextDimValues[dimConcept]
                        memConcept = memModelDimension.member
                    else:
                        hcValid = False
                        continue
                    if not dimConcept.isTypedDimension:
                        # change to cache all member concepts usability per domain: if dimensionMemberState(val, dimConcept, memConcept, domELR) != MEMBER_USABLE:
                        if not dimensionMemberUsable(val, dimConcept, memConcept, domELR):  # type: ignore[arg-type]
                            hcValid = False
                    if hcValid and setPrototypeContextElements and isinstance(memModelDimension,DimValuePrototype) and not hcNegating:
                        memModelDimension.contextElement = hcContextElement
        if hcIsClosed:
            if len(contextElementDimSet) > 0:
                hcValid = False # has extra stuff in the context element
        elif setPrototypeContextElements and isinstance(context,ContextPrototype) and hcValid and not hcNegating:
            for memModelDimension in modelDimValues.values(): # be sure no ambiguous items are left, this cube is open
                if memModelDimension.contextElement != hcContextElement: # if not moved by being explicit cube member
                    memModelDimension.contextElement = hcContextElement # move it
            if len(oppositeContextDimValues) > 0: # move any opposite dim values into open hypercube
                for memModelDimension in oppositeContextDimValues.values():
                    if memModelDimension.contextElement != hcContextElement: # if not moved by being explicit cube member
                        memModelDimension.contextElement = hcContextElement # move it
        if hcNegating:
            hcValid = not hcValid
        if not hcValid:
            elrValid = False
    return elrValid


def dimensionMemberUsable(val: ValidateXbrl, dimConcept: ModelConcept, memConcept: ModelObject, domELR: str) -> bool:
    try:
        dimensionMembersUsable = val.dimensionMembersUsable  # type: ignore[attr-defined]
    except AttributeError:
        dimensionMembersUsable = val.dimensionMembersUsable = {}  # type: ignore[attr-defined]
    key = (dimConcept, domELR)
    try:
        return memConcept in dimensionMembersUsable[key]
    except KeyError:
        usableMembers: set[ModelConcept] = set()
        unusableMembers: set[ModelConcept] = set()
        dimensionMembersUsable[key] = usableMembers
        # build set of usable members in dimension/domain/ELR
        findUsableMembersInDomainELR(val, val.modelXbrl.relationshipSet(XbrlConst.dimensionDomain, domELR).fromModelObject(dimConcept),
                                     domELR, usableMembers, unusableMembers, defaultdict(set))
        usableMembers -= unusableMembers
        return memConcept in usableMembers


def findUsableMembersInDomainELR(
    val: ValidateXbrl,
    rels: list[ModelRelationship],
    ELR: str,
    usableMembers: set[ModelConcept],
    unusableMembers: set[ModelConcept],
    toConceptELRs: defaultdict[ModelConcept, set[str]],
) -> None:
    for rel in rels:
        toConcept = rel.toModelObject
        if rel.isUsable:
            usableMembers.add(toConcept)  # type: ignore[arg-type]
        else:
            unusableMembers.add(toConcept)  # type: ignore[arg-type]
        toELR = (rel.targetRole or ELR)
        toELRs = toConceptELRs[toConcept]  # type: ignore[index]
        if toELR not in toELRs:  # looping if it's already there in a visited ELR
            toELRs.add(toELR)
            domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(toConcept)  # type: ignore[arg-type]
            findUsableMembersInDomainELR(val, domMbrRels, toELR, usableMembers, unusableMembers, toConceptELRs)
            toELRs.discard(toELR)


def usableEnumerationMembers(val: ValidateXbrl, enumConcept: ModelConcept | None) -> set[ModelConcept]:
    if enumConcept is None:
        return set()
    try:
        enumerationMembersUsable = val.enumerationMembersUsable  # type: ignore[attr-defined]
    except AttributeError:
        enumerationMembersUsable = val.enumerationMembersUsable = {}  # type: ignore[attr-defined]
    try:
        return enumerationMembersUsable[enumConcept]  # type: ignore[no-any-return]
    except KeyError:
        domConcept = enumConcept.enumDomain
        usableMembers: set[ModelConcept] = set()
        unusableMembers: set[ModelConcept] = set()
        enumerationMembersUsable[enumConcept] = usableMembers
        if domConcept is None:
            usableMembers = set()
            return usableMembers
        if enumConcept.isEnumDomainUsable:
            usableMembers.add(domConcept)
        # build set of usable members in dimension/domain/ELR
        domELR = enumConcept.enumLinkrole
        findUsableMembersInDomainELR(val, val.modelXbrl.relationshipSet(XbrlConst.domainMember, domELR).fromModelObject(domConcept),
                                     domELR, usableMembers, unusableMembers, defaultdict(set))  # type: ignore[arg-type]
        usableMembers -= unusableMembers
        return usableMembers


def enumerationMemberUsable(val: ValidateXbrl, enumConcept: ModelConcept | None, memConcept: ModelConcept | None) -> bool:
    if enumConcept is None or memConcept is None:
        return False
    else:
        return memConcept in usableEnumerationMembers(val, enumConcept)
''' removed to cache all members usability for domain
def dimensionMemberState(val, dimConcept, memConcept, domELR):
    try:
        dimensionMemberStates = val.dimensionMemberStates
    except AttributeError:
        dimensionMemberStates = val.dimensionMemberStates = {}
    key = (dimConcept, memConcept, domELR)
    try:
        return dimensionMemberStates[key]
    except KeyError:
        dimDomRels = val.modelXbrl.relationshipSet(
                        XbrlConst.dimensionDomain, domELR).fromModelObject(dimConcept)
        state = memberStateInDomain(val, memConcept, dimDomRels, domELR)
        dimensionMemberStates[key] = state
        return state

def memberStateInDomain(val, memConcept, rels, ELR, toConceptELRs=None):
    foundState = NOT_FOUND
    if toConceptELRs is None:
        toConceptELRs = defaultdict(set)
    for rel in rels:
        toConcept = rel.toModelObject
        if toConcept == memConcept:
            foundState = max(foundState,
                             MEMBER_USABLE if rel.isUsable else MEMBER_NOT_USABLE)
        toELR = (rel.targetRole or ELR)
        toELRs = toConceptELRs[toConcept]
        if toELR not in toELRs:  # looping if it's already there in a visited ELR
            toELRs.add(toELR)
            domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(toConcept)
            foundState = max(foundState,
                             memberStateInDomain(val, memConcept, domMbrRels, toELR, toConceptELRs))
            toELRs.discard(toELR)
    return foundState
'''

''' removed because no valid way to check one isolated dimension for validity without full set of others
# check a single dimension value for primary item (not the complete set of dimension values)
# returnn the contextElement of the hypercube where valid
def checkPriItemDimValueValidity(val, priItemConcept, dimConcept, memConcept, srcCntxEltName=None):
    if priItemConcept is not None and dimConcept is not None:
        _priItemElrHcRels = priItemElrHcRels(val, priItemConcept)
        for ELR, hcRels in _priItemElrHcRels.items():
            hcCntxElt = checkPriItemDimValueElrHcs(val, priItemConcept, dimConcept, memConcept, srcCntxEltName, hcRels)
            if hcCntxElt:
                return hcCntxElt
        # look for open hypercubes in other ELRs
    for hasHcRel in val.modelXbrl.relationshipSet(XbrlConst.all).modelRelationships:
        if hasHcRel.linkrole not in _priItemElrHcRels:
            hcCntxElt = checkPriItemDimValueElrHcs(val, priItemConcept, dimConcept, memConcept, srcCntxEltName, hcRels, openOnly=True)
            if hcCntxElt:
                return hcCntxElt
    return None

def checkPriItemDimValueElrHcs(val, priItemConcept, matchDim, matchMem, srcCntxEltName, hcRels, openOnly=False):
    hcCntxElt = None
    for hasHcRel in hcRels:
        if hasHcRel.arcrole == XbrlConst.all:
            hcConcept = hasHcRel.toModelObject
            hcIsClosed = hasHcRel.isClosed
            cntxElt = hasHcRel.contextElement

            dimELR = (hasHcRel.targetRole or hasHcRel.linkrole)
            for hcDimRel in val.modelXbrl.relationshipSet(
                                XbrlConst.hypercubeDimension, dimELR).fromModelObject(hcConcept):
                dimConcept = hcDimRel.toModelObject
                if dimConcept != matchDim:
                    continue
                if matchMem is None and not openOnly:
                    if cntxElt == srcCntxEltName:
                        return cntxElt
                    else:
                        hcCntxElt = cntxElt
                        continue
                domELR = (hcDimRel.targetRole or dimELR)
                state = dimensionMemberState(val, dimConcept, matchMem, domELR)
                if state == MEMBER_USABLE and not openOnly:
                    if cntxElt == srcCntxEltName:
                        return cntxElt
                    else:
                        hcCntxElt = cntxElt
                        continue
            if not hcIsClosed:
                hcCntxElt = cntxElt
    return hcCntxElt
'''
