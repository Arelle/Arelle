'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from collections import defaultdict
from arelle import (UrlUtil, XbrlConst)
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelConcept

def loadDimensionDefaults(val):
    # load dimension defaults when required without performing validations
    val.modelXbrl.qnameDimensionDefaults = {}
    for baseSetKey in val.modelXbrl.baseSets.keys():
        arcrole, ELR, linkqname, arcqname = baseSetKey
        if ELR and linkqname and arcqname and arcrole == XbrlConst.dimensionDefault:
            checkBaseSet(val, arcrole, ELR, val.modelXbrl.relationshipSet(arcrole,ELR,linkqname,arcqname))

def checkBaseSet(val, arcrole, ELR, relsSet):
    # check hypercube-dimension relationships
    if arcrole == XbrlConst.hypercubeDimension:
        for modelRel in relsSet.modelRelationships:
            fromConcept = modelRel.fromModelObject
            toConcept = modelRel.toModelObject
            if fromConcept is not None and toConcept is not None:
                if not fromConcept.isHypercubeItem:
                    val.modelXbrl.error("xbrldte:HypercubeDimensionSourceError",
                        "Hypercube-dimension relationship from %(source)s to %(target)s in link role %(linkrole)s must have a hypercube declaration source",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                if not toConcept.isDimensionItem:
                    val.modelXbrl.error("xbrldte:HypercubeDimensionTargetError",
                        "Hypercube-dimension relationship from %(source)s to %(target)s in link role %(linkrole)s must have a dimension declaration target",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
    # check all, notAll relationships
    elif arcrole in (XbrlConst.all, XbrlConst.notAll):
        fromRelationships = relsSet.fromModelObjects()
        for priItemConcept, hcRels in fromRelationships.items():
            for hasHcRel in hcRels:
                hcConcept = hasHcRel.toModelObject
                if priItemConcept is not None and hcConcept is not None:
                    if not priItemConcept.isPrimaryItem:
                        val.modelXbrl.error("xbrldte:HasHypercubeSourceError",
                            "HasHypercube %(arcroleType)s relationship from %(source)s to %(target)s in link role %(linkrole)s must have a primary item source",
                            modelObject=hasHcRel, arcroleType=os.path.basename(arcrole), 
                            source=priItemConcept.qname, target=hcConcept.qname, linkrole=ELR)
                    if not hcConcept.isHypercubeItem:
                        val.modelXbrl.error("xbrldte:HasHypercubeTargetError",
                            "HasHypercube %(arcroleType)s relationship from %(source)s to %(target)s in link role %(linkrole)s must have a hypercube declaration target",
                            modelObject=hasHcRel, arcroleType=os.path.basename(arcrole), 
                            source=priItemConcept.qname, target=hcConcept.qname, linkrole=ELR)
                    hcContextElement = hasHcRel.contextElement
                    if hcContextElement not in ("segment","scenario"):
                        val.modelXbrl.error("xbrldte:HasHypercubeMissingContextElementAttributeError",
                            "HasHypercube %(arcroleType)s relationship from %(source)s to %(target)s in link role %(linkrole)s must have a context element",
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
                                val.modelXbrl.qnameDimensionContextElement[dimConcept.qname] = hcContextElement
                            domELR = hcDimRel.targetRole
                            if not domELR:
                                domELR = dimELR
                            dimDomRels = val.modelXbrl.relationshipSet(
                                 XbrlConst.dimensionDomain, domELR).fromModelObject(dimConcept)
                            if xdtCycle(val, domainTargetRoles(val, domELR,dimDomRels), dimDomRels, {hcConcept,dimConcept}):
                                val.modelXbrl.error("xbrldte:DRSDirectedCycleError",
                                    "Dimension relationships have a directed cycle in DRS role %(linkrole)s starting from hypercube %(hypercube)s, dimension %(dimension)s",
                                    modelObject=hcConcept, hypercube=hcConcept.qname, dimension=dimConcept.qname, linkrole=ELR)
                            if drsPolymorphism(val, domELR, dimDomRels, drsPriItems(val, ELR, priItemConcept)):
                                val.modelXbrl.error("xbrldte:PrimaryItemPolymorphismError",
                                    "Dimension relationships have a polymorphism cycle in DRS role %(linkrole)s starting from hypercube %(hypercube)s, dimension %(dimension)s",
                                    modelObject=hcConcept, hypercube=hcConcept.qname, dimension=dimConcept.qname, linkrole=ELR)
    # check dimension-domain relationships
    elif arcrole == XbrlConst.dimensionDomain:
        for modelRel in relsSet.modelRelationships:
            fromConcept = modelRel.fromModelObject
            toConcept = modelRel.toModelObject
            if fromConcept is not None and toConcept is not None:   # none if failed to load
                if not fromConcept.isDimensionItem:
                    val.modelXbrl.error("xbrldte:DimensionDomainSourceError",
                        "Dimension-domain relationship from %(source)s to %(target)s in link role %(linkrole)s must have a dimension declaration source",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                elif fromConcept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef") is not None:
                    val.modelXbrl.error("xbrldte:DimensionDomainSourceError",
                        "Dimension-domain relationship from %(source)s to %(target)s in link role %(linkrole)s has a typed dimension source",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                if not toConcept.isDomainMember:
                    val.modelXbrl.error("xbrldte:DimensionDomainTargetError",
                        "Dimension-domain relationship from %(source)s to %(target)s in link role %(linkrole)s must have a domain member target",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
    # check dimension-default relationships
    elif arcrole == XbrlConst.dimensionDefault:
        for modelRel in relsSet.modelRelationships:
            fromConcept = modelRel.fromModelObject
            toConcept = modelRel.toModelObject
            if fromConcept is not None and toConcept is not None:
                if not fromConcept.isDimensionItem:
                    val.modelXbrl.error("xbrldte:DimensionDefaultSourceError",
                        "Dimension-default relationship from %(source)s to %(target)s in link role %(linkrole)s must have a dimension declaration source",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                elif fromConcept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef"):
                    val.modelXbrl.error("xbrldte:DimensionDefaultSourceError",
                        "Dimension-default relationship from %(source)s to %(target)s in link role %(linkrole)s has a typed dimension source",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                if not toConcept.isDomainMember:
                    val.modelXbrl.error("xbrldte:DimensionDefaultTargetError",
                        "Dimension-default relationship from %(source)s to %(target)s in link role %(linkrole)s must have a domain member target",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                if fromConcept in val.dimensionDefaults and toConcept != val.dimensionDefaults[fromConcept]:
                    val.modelXbrl.error("xbrldte:TooManyDefaultMembersError",
                        "Dimension %(source)s has multiple defaults %(target)s and %(target2)s",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, 
                        target2=val.dimensionDefaults[fromConcept].qname)
                else:
                    val.dimensionDefaults[fromConcept] = toConcept
                    val.modelXbrl.qnameDimensionDefaults[fromConcept.qname] = toConcept.qname

    # check for primary item cycles
    elif arcrole == XbrlConst.domainMember:
        fromRelationships = relsSet.fromModelObjects()
        for priItemConcept, rels in fromRelationships.items():
                for domMbrRel in rels:
                    toConcept = domMbrRel.toModelObject
                    if toConcept is not None:
                        if not priItemConcept.isDomainMember:
                            val.modelXbrl.error("xbrldte:DomainMemberSourceError",
                                "Domain-Member relationship from %(source)s to %(target)s in link role %(linkrole)s must have a domain primary item or domain member source",
                                modelObject=domMbrRel, source=priItemConcept.qname, target=toConcept.qname, linkrole=ELR)
                        if not toConcept.isDomainMember:
                            val.modelXbrl.error("xbrldte:DomainMemberTargetError",
                                "Domain-Member relationship from %(source)s to %(target)s in link role %(linkrole)s must have a domain primary item or domain member target",
                                modelObject=domMbrRel, source=priItemConcept.qname, target=toConcept.qname, linkrole=ELR)

def domainTargetRoles(val, fromELR, rels, fromConcepts=None, ELRs=None):
    if fromConcepts is None:
        fromConcepts = set()
    if not ELRs:
        ELRs = {fromELR}
    for rel in rels:
        relTo = rel.toModelObject
        if relTo not in fromConcepts:
            fromConcepts.add(relTo)
            toELR = rel.targetRole
            if toELR:
                ELRs.add(toELR)
            else:
                toELR = fromELR
            domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(relTo)
            domainTargetRoles(val, toELR, domMbrRels, fromConcepts, ELRs)
            fromConcepts.discard(relTo)
    return ELRs

def xdtCycle(val, ELRs, rels, fromConcepts):
    for rel in rels:
        relTo = rel.toModelObject
        if rel.isUsable and relTo in fromConcepts: # don't think we want this?? and toELR == drsELR: #forms a directed cycle
            return True
        fromConcepts.add(relTo)
        for ELR in ELRs: 
            domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, ELR).fromModelObject(relTo)
            if xdtCycle(val, ELRs, domMbrRels, fromConcepts):
                return True
        fromConcepts.discard(relTo)
    return False

def drsPriItems(val, fromELR, fromPriItem, priItems=None):
    if priItems is None:
        priItems = {fromPriItem}
    for rel in  val.modelXbrl.relationshipSet(XbrlConst.domainMember, fromELR).fromModelObject(fromPriItem):
        toPriItem = rel.toModelObject
        if toPriItem not in priItems:
            if rel.isUsable:
                priItems.add(toPriItem)
            toELR = rel.targetRole
            drsPriItems(val, toELR if toELR else fromELR, toPriItem, priItems)
    return priItems

def drsPolymorphism(val, fromELR, rels, priItems, visitedMbrs=None):
    if visitedMbrs is None:
        visitedMbrs = set()
    for rel in rels:
        relTo = rel.toModelObject
        toELR = rel.targetRole
        if not toELR:
            toELR = fromELR
        if rel.isUsable and relTo in priItems: # don't think we want this?? and toELR == drsELR: #forms a directed cycle
            return True
        if relTo not in visitedMbrs:
            visitedMbrs.add(relTo)
            domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(relTo)
            if drsPolymorphism(val, toELR, domMbrRels, priItems, visitedMbrs):
                return True
            visitedMbrs.discard(relTo)
    return False

def checkConcept(val, concept):
    if concept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef"):
        if concept.isDimensionItem:
            typedDomainElement = concept.typedDomainElement
            if typedDomainElement is None:
                url, id = UrlUtil.splitDecodeFragment(concept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef"))
                if len(id) == 0:
                    val.modelXbrl.error("xbrldte:TypedDimensionURIError",
                        "Concept %(concept)s typedDomainRef has no fragment identifier",
                        modelObject=concept, concept=concept.qname)
                else:
                    val.modelXbrl.error("xbrldte:OutOfDTSSchemaError",
                        "Concept %(concept)s typedDomainRef is not resolved",
                        modelObject=concept, concept=concept.qname)
            elif not isinstance(typedDomainElement, ModelConcept) or \
                        not typedDomainElement.isGlobalDeclaration or \
                        typedDomainElement.abstract == "true":
                val.modelXbrl.error("xbrldte:TypedDimensionError",
                    "Concept %(concept)s typedDomainRef must identify a non-abstract element",
                        modelObject=concept, concept=concept.qname)
        else:
            val.modelXbrl.error("xbrldte:TypedDomainRefError",
                "Concept %(concept)s is not a dimension item but has a typedDomainRef",
                modelObject=concept, concept=concept.qname)

def checkContext(val, cntx):
    # check errorDimensions of context
    for modelDimValues in (cntx.segDimValues.values(), cntx.scenDimValues.values(), cntx.errorDimValues):
        for modelDimValue in modelDimValues:
            dimensionConcept = modelDimValue.dimension
            if dimensionConcept is None or \
                not dimensionConcept.isDimensionItem or \
                modelDimValue.isTyped != (dimensionConcept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef") is not None):
                val.modelXbrl.error("xbrldie:TypedMemberNotTypedDimensionError" if modelDimValue.isTyped else "xbrldie:ExplicitMemberNotExplicitDimensionError",
                    "Context %(contextID)s %(dimension)s %(value)s is not an appropriate dimension item",
                    modelObject=modelDimValue, contextID=cntx.id, 
                    dimension=modelDimValue.prefixedName, value=modelDimValue.dimensionQname)
            elif modelDimValue.isExplicit:
                memberConcept = modelDimValue.member
                if memberConcept is None or not memberConcept.isGlobalDeclaration:
                    val.modelXbrl.error("xbrldie:ExplicitMemberUndefinedQNameError",
                        "Context %(contextID)s explicit dimension %(dimension)s member %(value)s is not a global member item",
                        modelObject=modelDimValue, contextID=cntx.id, 
                        dimension=modelDimValue.dimensionQname, value=modelDimValue.memberQname)
                if val.dimensionDefaults.get(dimensionConcept) == memberConcept:
                    val.modelXbrl.error("xbrldie:DefaultValueUsedInInstanceError",
                        "Context %(contextID)s explicit dimension %(dimension)s member {2} is a default member item",
                        modelObject=modelDimValue, contextID=cntx.id, 
                        dimension=modelDimValue.dimensionQname, value=modelDimValue.memberQname)
            elif modelDimValue.isTyped:
                typedDomainConcept = dimensionConcept.typedDomainElement
                problem = _("missing content")                
                for element in modelDimValue.getchildren():
                    if isinstance(element,ModelObject):
                        if problem is None:
                            problem = _("multiple contents")
                        elif element.localName != typedDomainConcept.name or \
                            element.namespaceURI != typedDomainConcept.namespaceURI:
                            problem = _("wrong content {0}").format(element.prefixedName)
                        else:
                            problem = None
                if problem:
                    val.modelXbrl.error("xbrldie:IllegalTypedDimensionContentError",
                        "Context %(contextID)s typed dimension %(dimension)s has %(error)s",
                        modelObject=modelDimValue, contextID=cntx.id, 
                        dimension=modelDimValue.dimensionQname, error=problem)

    for modelDimValue in cntx.errorDimValues:
        dimensionConcept = modelDimValue.dimension
        if dimensionConcept is not None \
           and (dimensionConcept in cntx.segDimValues or dimensionConcept in cntx.scenDimValues):
            val.modelXbrl.error("xbrldie:RepeatedDimensionInInstanceError",
                "Context %(contextID)s dimension %(dimension)s is a repeated dimension value",
                modelObject=modelDimValue, contextID=cntx.id, dimension=modelDimValue.dimensionQname)
    # decision by WG that dimensions in both seg & scen is also a duplication
    for modelDimValue in cntx.segDimValues.values():
        dimensionConcept = modelDimValue.dimension
        if dimensionConcept is not None and dimensionConcept in cntx.scenDimValues:
            val.modelXbrl.error("xbrldie:RepeatedDimensionInInstanceError",
                "Context %(contextID)s dimension %(dimension)s is a repeated dimension value",
                modelObject=modelDimValue, contextID=cntx.id, dimension=modelDimValue.dimensionQname)
            
def checkFact(val, f):
    if not isFactDimensionallyValid(val, f):
        val.modelXbrl.error("xbrldie:PrimaryItemDimensionallyInvalidError",
            "Fact %(fact)s context %(contextID)s dimensionally not valid",
            modelObject=f, fact=f.concept.qname, contextID=f.context.id)

def isFactDimensionallyValid(val, f):
    hasElrHc = False
    for ELR, hcRels in priItemElrHcRels(val, f.concept).items():
        hasElrHc = True
        if checkFactElrHcs(val, f, ELR, hcRels):
            return True # meets hypercubes in this ELR
        
    if hasElrHc:
        # no ELR hypercubes fully met
        return False
    return True
    
def priItemElrHcRels(val, priItem, ELR=None, elrHcRels=None):
    if elrHcRels is None:
        elrHcRels = defaultdict(list)
    # add has hypercube relationships for ELR
    for arcrole in (XbrlConst.all, XbrlConst.notAll):
        for hasHcRel in val.modelXbrl.relationshipSet(arcrole,ELR).fromModelObject(priItem):
            elrHcRels[hasHcRel.linkrole].append(hasHcRel)
    # check inherited ELRs
    for domMbrRel in val.modelXbrl.relationshipSet(XbrlConst.domainMember).toModelObject(priItem):
        toELR = domMbrRel.targetRole
        relLinkrole = domMbrRel.linkrole
        if toELR is None:
            toELR = relLinkrole
        if ELR is None or ELR == toELR:
            priItemElrHcRels(val, domMbrRel.fromModelObject, relLinkrole, elrHcRels)
    return elrHcRels

NOT_FOUND = 0
MEMBER_USABLE = 1
MEMBER_NOT_USABLE = 2

def checkFactElrHcs(val, f, ELR, hcRels):
    context = f.context
    elrValid = True # start assuming ELR is valid
    
    for hasHcRel in hcRels:
        hcConcept = hasHcRel.toModelObject
        hcIsClosed = hasHcRel.isClosed
        hcContextElement = hasHcRel.contextElement
        hcNegating = hasHcRel.arcrole == XbrlConst.notAll
        modelDimValues = context.dimValues(hcContextElement)
        contextElementDimSet = set(modelDimValues.keys())
        modelNonDimValues = context.nonDimValues(hcContextElement)
        hcValid = True
        
        # if closed and any nonDim values, hc invalid
        if hcIsClosed and len(modelNonDimValues) > 0:
            hcValid = False
        else:
            dimELR = hasHcRel.targetRole
            if dimELR is None:
                dimELR = ELR
            for hcDimRel in val.modelXbrl.relationshipSet(
                                XbrlConst.hypercubeDimension, dimELR).fromModelObject(hcConcept):
                dimConcept = hcDimRel.toModelObject
                domELR = hcDimRel.targetRole
                if domELR is None:
                    domELR = dimELR
                dimDomRels = val.modelXbrl.relationshipSet(
                                XbrlConst.dimensionDomain, domELR).fromModelObject(dimConcept)
                if dimConcept in modelDimValues:
                    memModelDimension = modelDimValues[dimConcept]
                    contextElementDimSet.discard(dimConcept)
                    memConcept = memModelDimension.member
                elif dimConcept in val.dimensionDefaults:
                    memConcept = val.dimensionDefaults[dimConcept]
                else:
                    hcValid = False
                    continue
                if not dimConcept.isTypedDimension:
                    if memberStateInDomain(val, memConcept, dimDomRels, domELR) != MEMBER_USABLE:
                        hcValid = False 
        if hcIsClosed and len(contextElementDimSet) > 0:
            hcValid = False # has extra stuff in the context element
        if hcNegating:
            hcValid = not hcValid
        if not hcValid:
            elrValid = False
    return elrValid
                            
def memberStateInDomain(val, memConcept, rels, ELR, fromConcepts=None):
    foundState = NOT_FOUND
    if fromConcepts is None:
        fromConcepts = set()
    for rel in rels:
        toConcept = rel.toModelObject
        if toConcept == memConcept:
            foundState = max(foundState, 
                             MEMBER_USABLE if rel.isUsable else MEMBER_NOT_USABLE)
        if toConcept not in fromConcepts:
            fromConcepts.add(toConcept)
        toELR = rel.targetRole
        if toELR is None:
            toELR = ELR
        domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(toConcept)
        foundState = max(foundState,
                         memberStateInDomain(val, memConcept, domMbrRels, toELR, fromConcepts))
        fromConcepts.discard(toConcept)
    return foundState

# check a single dimension value for primary item (not the complete set of dimension values)
def checkPriItemDimValueValidity(val, priItemConcept, dimConcept, memConcept):
    if priItemConcept and dimConcept and memConcept:
        for ELR, hcRels in priItemElrHcRels(val, priItemConcept).items():
            if checkPriItemDimValueElrHcs(val, priItemConcept, dimConcept, memConcept, ELR, hcRels):
                return True
    return False

def checkPriItemDimValueElrHcs(val, priItemConcept, matchDim, matchMem, ELR, hcRels):
    for hasHcRel in hcRels:
        hcConcept = hasHcRel.toModelObject
        hcIsClosed = hasHcRel.isClosed
        hcNegating = hasHcRel.arcrole == XbrlConst.notAll
        
        dimELR = hasHcRel.targetRole
        if dimELR is None:
            dimELR = ELR
        for hcDimRel in val.modelXbrl.relationshipSet(
                            XbrlConst.hypercubeDimension, dimELR).fromModelObject(hcConcept):
            dimConcept = hcDimRel.toModelObject
            if dimConcept != matchDim:
                continue
            domELR = hcDimRel.targetRole
            if domELR is None:
                domELR = dimELR
            dimDomRels = val.modelXbrl.relationshipSet(
                            XbrlConst.dimensionDomain, domELR).fromModelObject(dimConcept)
            if memberStateInDomain(val, matchMem, dimDomRels, domELR) != MEMBER_USABLE:
                return hcNegating # true if all, false if not all
        if hcIsClosed:
            return False # has extra stuff in the context element
        if hcNegating:
            return True
    return True
