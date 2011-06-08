'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from collections import defaultdict
from arelle import (ModelObject, UrlUtil, XbrlConst)

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
            if fromConcept and toConcept:
                if not fromConcept.isHypercubeItem:
                    val.modelXbrl.error(
                        _("Hypercube-dimension relationship from {0} to {1} in link role {2} must have a hypercube declaration source").format(
                              fromConcept.qname, toConcept.qname, ELR), 
                        "err", "xbrldte:HypercubeDimensionSourceError")
                if not toConcept.isDimensionItem:
                    val.modelXbrl.error(
                        _("Hypercube-dimension relationship from {0} to {1} in link role {2} must have a dimension declaration target").format(
                              fromConcept.qname, toConcept.qname, ELR), 
                        "err", "xbrldte:HypercubeDimensionTargetError")
    # check all, notAll relationships
    elif arcrole in (XbrlConst.all, XbrlConst.notAll):
        fromRelationships = relsSet.fromModelObjects()
        for priItemConcept, hcRels in fromRelationships.items():
            for hasHcRel in hcRels:
                hcConcept = hasHcRel.toModelObject
                if priItemConcept and hcConcept:
                    if not priItemConcept.isPrimaryItem:
                        val.modelXbrl.error(
                            _("HasHypercube {0} relationship from {1} to {2} in link role {3} must have a primary item source").format(
                                  os.path.basename(arcrole), priItemConcept.qname, hcConcept.qname, ELR), 
                            "err", "xbrldte:HasHypercubeSourceError")
                    if not hcConcept.isHypercubeItem:
                        val.modelXbrl.error(
                            _("HasHypercube {0} relationship from {1} to {2} in link role {3} must have a hypercube declaration target").format(
                                  os.path.basename(arcrole), priItemConcept.qname, hcConcept.qname, ELR), 
                            "err", "xbrldte:HasHypercubeTargetError")
                    hcContextElement = hasHcRel.contextElement
                    if hcContextElement not in ("segment","scenario"):
                        val.modelXbrl.error(
                            _("HasHypercube {0} relationship from {1} to {2} in link role {3} must have a context element").format(
                                  os.path.basename(arcrole), priItemConcept.qname, hcConcept.qname, ELR), 
                            "err", "xbrldte:HasHypercubeMissingContextElementAttributeError")
                        
                    # must check the cycles starting from hypercube ELR (primary item consec relationship
                    dimELR = hasHcRel.targetRole
                    if not dimELR:
                        dimELR = ELR
                    hcDimRels = val.modelXbrl.relationshipSet(
                         XbrlConst.hypercubeDimension, dimELR).fromModelObject(hcConcept)
                    for hcDimRel in hcDimRels:
                        dimConcept = hcDimRel.toModelObject
                        if dimConcept:
                            if arcrole == XbrlConst.all:
                                val.modelXbrl.qnameDimensionContextElement[dimConcept.qname] = hcContextElement
                            domELR = hcDimRel.targetRole
                            if not domELR:
                                domELR = dimELR
                            dimDomRels = val.modelXbrl.relationshipSet(
                                 XbrlConst.dimensionDomain, domELR).fromModelObject(dimConcept)
                            if xdtCycle(val, domainTargetRoles(val, domELR,dimDomRels), dimDomRels, {hcConcept,dimConcept}):
                                val.modelXbrl.error(
                                    _("Dimension relationships have a directed cycle in DRS role {0} starting from hypercube {1}, dimension {2}").format(
                                          ELR, hcConcept.qname, dimConcept.qname), 
                                    "err", "xbrldte:DRSDirectedCycleError")
                            if drsPolymorphism(val, domELR, dimDomRels, drsPriItems(val, ELR, priItemConcept)):
                                val.modelXbrl.error(
                                    _("Dimension relationships have a polymorphism cycle in DRS role {0} starting from hypercube {1}, dimension {2}").format(
                                          ELR, hcConcept.qname, dimConcept.qname), 
                                    "err", "xbrldte:PrimaryItemPolymorphismError")
    # check dimension-domain relationships
    elif arcrole == XbrlConst.dimensionDomain:
        for modelRel in relsSet.modelRelationships:
            fromConcept = modelRel.fromModelObject
            toConcept = modelRel.toModelObject
            if fromConcept and toConcept:   # none if failed to load
                if not fromConcept.isDimensionItem:
                    val.modelXbrl.error(
                        _("Dimension-domain relationship from {0} to {1} in link role {2} must have a dimension declaration source").format(
                              fromConcept.qname, toConcept.qname, ELR), 
                        "err", "xbrldte:DimensionDomainSourceError")
                elif fromConcept.element.hasAttributeNS(XbrlConst.xbrldt, "typedDomainRef"):
                    val.modelXbrl.error(
                        _("Dimension-domain relationship from {0} to {1} in link role {2} has a typed dimension source").format(
                              fromConcept.qname, toConcept.qname, ELR), 
                        "err", "xbrldte:DimensionDomainSourceError")
                if not toConcept.isDomainMember:
                    val.modelXbrl.error(
                        _("Dimension-domain relationship from {0} to {1} in link role {2} must have a domain member target").format(
                              fromConcept.qname, toConcept.qname, ELR), 
                        "err", "xbrldte:DimensionDomainTargetError")
    # check dimension-default relationships
    elif arcrole == XbrlConst.dimensionDefault:
        for modelRel in relsSet.modelRelationships:
            fromConcept = modelRel.fromModelObject
            toConcept = modelRel.toModelObject
            if fromConcept and toConcept:
                if not fromConcept.isDimensionItem:
                    val.modelXbrl.error(
                        _("Dimension-default relationship from {0} to {1} in link role {2} must have a dimension declaration source").format(
                              fromConcept.qname, toConcept.qname, ELR), 
                        "err", "xbrldte:DimensionDefaultSourceError")
                elif fromConcept.element.hasAttributeNS(XbrlConst.xbrldt, "typedDomainRef"):
                    val.modelXbrl.error(
                        _("Dimension-default relationship from {0} to {1} in link role {2} has a typed dimension source").format(
                              fromConcept.qname, toConcept.qname, ELR), 
                        "err", "xbrldte:DimensionDefaultSourceError")
                if not toConcept.isDomainMember:
                    val.modelXbrl.error(
                        _("Dimension-default relationship from {0} to {1} in link role {2} must have a domain member target").format(
                              fromConcept.qname, toConcept.qname, ELR), 
                        "err", "xbrldte:DimensionDefaultTargetError")
                if fromConcept in val.dimensionDefaults and toConcept != val.dimensionDefaults[fromConcept]:
                    val.modelXbrl.error(
                        _("Dimension {0} has multiple defaults {1} and {2}").format(
                              fromConcept.qname, toConcept.qname, val.dimensionDefaults[fromConcept].qname), 
                        "err", "xbrldte:TooManyDefaultMembersError")
                else:
                    val.dimensionDefaults[fromConcept] = toConcept
                    val.modelXbrl.qnameDimensionDefaults[fromConcept.qname] = toConcept.qname

    # check for primary item cycles
    elif arcrole == XbrlConst.domainMember:
        fromRelationships = relsSet.fromModelObjects()
        for priItemConcept, rels in fromRelationships.items():
                for domMbrRel in rels:
                    toConcept = domMbrRel.toModelObject
                    if toConcept:
                        if not priItemConcept.isDomainMember:
                            val.modelXbrl.error(
                                _("Domain-Member relationship from {0} to {1} in link role {2} must have a domain primary item or domain member source").format(
                                      priItemConcept.qname, toConcept.qname, ELR), 
                                "err", "xbrldte:DomainMemberSourceError")
                        if not toConcept.isDomainMember:
                            val.modelXbrl.error(
                                _("Domain-Member relationship from {0} to {1} in link role {2} must have a domain primary item or domain member target").format(
                                      priItemConcept.qname, toConcept.qname, ELR), 
                                "err", "xbrldte:DomainMemberTargetError")

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
    if concept.element.hasAttributeNS(XbrlConst.xbrldt, "typedDomainRef"):
        if concept.isDimensionItem:
            typedDomainElement = concept.typedDomainElement
            if typedDomainElement is None:
                url, id = UrlUtil.splitDecodeFragment(concept.element.getAttributeNS(XbrlConst.xbrldt, "typedDomainRef"))
                if len(id) == 0:
                    val.modelXbrl.error(
                        _("Concept {0} typedDomainRef has no fragment identifier").format(
                              concept.qname), 
                        "err", "xbrldte:TypedDimensionURIError")
                else:
                    val.modelXbrl.error(
                        _("Concept {0} typedDomainRef is not resolved").format(
                              concept.qname), 
                        "err", "xbrldte:OutOfDTSSchemaError")
            elif not isinstance(typedDomainElement, ModelObject.ModelConcept) or \
                        not typedDomainElement.isGlobalDeclaration or \
                        typedDomainElement.abstract == "true":
                val.modelXbrl.error(
                    _("Concept {0} typedDomainRef must identify a non-abstract element").format(
                          concept.qname), 
                    "err", "xbrldte:TypedDimensionError")
        else:
            val.modelXbrl.error(
                _("Concept {0} is not a dimension item but has a typedDomainRef").format(
                      concept.qname), 
                "err", "xbrldte:TypedDomainRefError")

def checkContext(val, cntx):
    # check errorDimensions of context
    for modelDimValues in (cntx.segDimValues.values(), cntx.scenDimValues.values(), cntx.errorDimValues):
        for modelDimValue in modelDimValues:
            dimensionConcept = modelDimValue.dimension
            if not dimensionConcept or \
                not dimensionConcept.isDimensionItem or \
                modelDimValue.isTyped != dimensionConcept.element.hasAttributeNS(XbrlConst.xbrldt, "typedDomainRef"):
                val.modelXbrl.error(
                    _("Context {0} {1} {2} is not an appropriate dimension item").format(
                          cntx.id, modelDimValue.element.tagName,
                          modelDimValue.dimensionQname), 
                    "err", "xbrldie:TypedMemberNotTypedDimensionError" if modelDimValue.isTyped else "xbrldie:ExplicitMemberNotExplicitDimensionError")
            elif modelDimValue.isExplicit:
                memberConcept = modelDimValue.member
                if not memberConcept or not memberConcept.isGlobalDeclaration:
                    val.modelXbrl.error(
                        _("Context {0} explicit dimension {1} member {2} is not a global member item").format(
                              cntx.id, modelDimValue.dimensionQname, modelDimValue.memberQname), 
                        "err", "xbrldie:ExplicitMemberUndefinedQNameError")
                if val.dimensionDefaults.get(dimensionConcept) == memberConcept:
                    val.modelXbrl.error(
                        _("Context {0} explicit dimension {1} member {2} is a default member item").format(
                              cntx.id, modelDimValue.dimensionQname, modelDimValue.memberQname), 
                        "err", "xbrldie:DefaultValueUsedInInstanceError")
            elif modelDimValue.isTyped:
                typedDomainConcept = dimensionConcept.typedDomainElement
                problem = _("missing content")                
                for element in modelDimValue.element.childNodes:
                    if element.nodeType == 1: #element
                        if problem is None:
                            problem = _("multiple contents")
                        elif element.localName != typedDomainConcept.name or \
                            element.namespaceURI != typedDomainConcept.namespaceURI:
                            problem = _("wrong content {0}").format(element.tagName)
                        else:
                            problem = None
                if problem:
                    val.modelXbrl.error(
                        _("Context {0} typed dimension {1} has {2}").format(
                              cntx.id, modelDimValue.dimensionQname, problem), 
                        "err", "xbrldie:IllegalTypedDimensionContentError")

    for modelDimValue in cntx.errorDimValues:
        dimensionConcept = modelDimValue.dimension
        if dimensionConcept and (dimensionConcept in cntx.segDimValues or dimensionConcept in cntx.scenDimValues):
            val.modelXbrl.error(
                _("Context {0} dimension {1} is a repeated dimension value").format(
                      cntx.id, modelDimValue.dimensionQname), 
                "err", "xbrldie:RepeatedDimensionInInstanceError")
    # decision by WG that dimensions in both seg & scen is also a duplication
    for modelDimValue in cntx.segDimValues.values():
        dimensionConcept = modelDimValue.dimension
        if dimensionConcept and dimensionConcept in cntx.scenDimValues:
            val.modelXbrl.error(
                _("Context {0} dimension {1} is a repeated dimension value").format(
                      cntx.id, modelDimValue.dimensionQname), 
                "err", "xbrldie:RepeatedDimensionInInstanceError")
            
def checkFact(val, f):
    if not isFactDimensionallyValid(val, f):
        val.modelXbrl.error(
            _("Fact {0} context {1} dimensions not valid").format(
                  f.concept.qname, f.context.id), 
            "err", "xbrldie:PrimaryItemDimensionallyInvalidError")

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
