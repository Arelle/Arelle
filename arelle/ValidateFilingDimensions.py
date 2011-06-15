'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
from arelle import XbrlConst

def checkDimensions(val, drsELRs):
    
    fromConceptELRs = defaultdict(set)
    hypercubes = set()
    hypercubesInLinkrole = defaultdict(set)
    hypercubeDRSDimensions = defaultdict(dict)
    val.domainsInLinkrole = defaultdict(set)
    for ELR in drsELRs:
        domainMemberRelationshipSet = val.modelXbrl.relationshipSet( XbrlConst.domainMember, ELR)
                            
        # check Hypercubes in ELR, accumulate list of primary items
        positiveAxisTableSources = defaultdict(set)
        positiveHypercubes = set()
        primaryItems = set()
        for hasHypercubeArcrole in (XbrlConst.all, XbrlConst.notAll):
            hasHypercubeRelationships = val.modelXbrl.relationshipSet(
                             hasHypercubeArcrole, ELR).fromModelObjects()
            for hasHcRels in hasHypercubeRelationships.values():
                numberOfHCsPerSourceConcept = 0
                for hasHcRel in hasHcRels:
                    sourceConcept = hasHcRel.fromModelObject
                    primaryItems.add(sourceConcept)
                    hc = hasHcRel.toModelObject
                    hypercubes.add(hc)
                    if hasHypercubeArcrole == XbrlConst.all:
                        positiveHypercubes.add(hc)
                        if not hasHcRel.isClosed:
                            val.modelXbrl.error(
                                _("All hypercube {0} in DRS role {1}, does not have closed='true'").format(
                                      hc.qname, ELR), 
                                "err", "SBR.NL.2.3.6.04")
                    elif hasHypercubeArcrole == XbrlConst.notAll:
                        if hasHcRel.isClosed:
                            val.modelXbrl.error(
                                _("Not all hypercube {0} in DRS role {1}, does not have closed='false'").format(
                                      hc.qname, ELR), 
                                "err", "EFM.6.16.06", "GFM.1.08.06")
                        if hc in positiveHypercubes:
                            val.modelXbrl.error(
                                _("Not all hypercube {0} in DRS role {1}, is also the target of a positive hypercube").format(
                                      hc.qname, ELR), 
                                "err", "EFM.6.16.08", "GFM.1.08.08")
                    numberOfHCsPerSourceConcept += 1
                    dimELR = hasHcRel.targetRole
                    dimTargetRequired = (dimELR is not None)
                    if not dimELR:
                        dimELR = ELR
                    hypercubesInLinkrole[dimELR].add(hc) # this is the elr containing the HC-dim relations
                    hcDimRels = val.modelXbrl.relationshipSet(
                             XbrlConst.hypercubeDimension, dimELR).fromModelObject(hc)
                    if dimTargetRequired and len(hcDimRels) == 0:
                        val.modelXbrl.error(
                            _("Table {0} in DRS role {1}, missing targetrole consecutive relationship").format(
                                  hc.qname, ELR), 
                            "err", "EFM.6.16.09", "GFM.1.08.09")
                    for hcDimRel in hcDimRels:
                        dim = hcDimRel.toModelObject
                        domELR = hcDimRel.targetRole
                        domTargetRequired = (domELR is not None)
                        if not domELR:
                            domELR = dimELR
                            if val.validateSBRNL:
                                val.modelXbrl.error(
                                    _("Hypercube {0} in DRS role {1}, missing targetrole to dimension {2} consecutive relationship").format(
                                          hc.qname, ELR, dim.qname), 
                                    "err", "SBR.NL.2.3.5.04")
                        else:
                            if dim.isTypedDimension and val.validateSBRNL:
                                val.modelXbrl.error(
                                    _("Typed dimension {0} in DRS role {1}, has targetrole consecutive relationship").format(
                                          dim.qname, ELR), 
                                    "err", "SBR.NL.2.3.5.07")
                        if hasHypercubeArcrole == XbrlConst.all:
                            positiveAxisTableSources[dim].add(sourceConcept)
                            try:
                                hcDRSdims = hypercubeDRSDimensions[hc][domELR]
                            except KeyError:
                                hcDRSdims = set()
                                hypercubeDRSDimensions[hc][domELR] = hcDRSdims
                            hcDRSdims.add(dim)
                        elif hasHypercubeArcrole == XbrlConst.notAll and \
                             (dim not in positiveAxisTableSources or \
                              not commonAncestor(domainMemberRelationshipSet,
                                              sourceConcept, positiveAxisTableSources[dim])):
                            val.modelXbrl.error(
                                _("Negative table axis {0} in DRS role {1}, not in any positive table in same role").format(
                                      dim.qname, ELR), 
                                "err", "EFM.6.16.07", "GFM.1.08.08")
                        dimDomRels = val.modelXbrl.relationshipSet(
                             XbrlConst.dimensionDomain, domELR).fromModelObject(dim)   
                        if domTargetRequired and len(dimDomRels) == 0:
                            val.modelXbrl.error(
                                _("Axis {0} in DRS role {1}, missing targetrole consecutive relationship").format(
                                      dim.qname, ELR), 
                                "err", "EFM.6.16.09", "GFM.1.08.09")
                        if val.validateEFMorGFM:
                            # flatten DRS member relationsihps in ELR for undirected cycle detection
                            drsRelsFrom = defaultdict(list)
                            drsRelsTo = defaultdict(list)
                            getDrsRels(val, domELR, dimDomRels, ELR, drsRelsFrom, drsRelsTo)
                            # check for cycles
                            fromConceptELRs[hc].add(dimELR)
                            fromConceptELRs[dim].add(domELR)
                            cycleCausingConcept = undirectedFwdCycle(val, domELR, dimDomRels, ELR, drsRelsFrom, drsRelsTo, fromConceptELRs)
                            if cycleCausingConcept is not None:
                                val.modelXbrl.error(
                                    _("Dimension relationships have an undirected cycle in DRS role {0} starting from table {1}, axis {2}, at {3}").format(
                                          ELR, hc.qname, dim.qname, cycleCausingConcept.qname), 
                                    "err", "EFM.6.16.04", "GFM.1.08.04")
                            fromConceptELRs.clear()
                        elif val.validateSBRNL:
                            checkSBRNLMembers(val, hc, dim, domELR, dimDomRels, ELR, True)
                if hasHypercubeArcrole == XbrlConst.all and numberOfHCsPerSourceConcept > 1:
                    val.modelXbrl.error(
                        _("Multiple tables ({0}) DRS role {1}, source {2}, only 1 allowed").format(
                              numberOfHCsPerSourceConcept, ELR, sourceConcept.qname), 
                        "err", "EFM.6.16.05", "GFM.1.08.05")
                    
        # check for primary item dimension-member graph undirected cycles
        fromRelationships = domainMemberRelationshipSet.fromModelObjects()
        for relFrom, rels in fromRelationships.items():
            if relFrom in primaryItems:
                drsRelsFrom = defaultdict(list)
                drsRelsTo = defaultdict(list)
                getDrsRels(val, ELR, rels, ELR, drsRelsFrom, drsRelsTo)
                fromConceptELRs[relFrom].add(ELR)
                cycleCausingConcept = undirectedFwdCycle(val, ELR, rels, ELR, drsRelsFrom, drsRelsTo, fromConceptELRs)
                if cycleCausingConcept is not None:
                    val.modelXbrl.error(
                        _("Domain-member primary-item relationships have an undirected cycle in DRS role {0} starting from {1} at {2}").format(
                              ELR, relFrom.qname, cycleCausingConcept.qname), 
                        "err", "EFM.6.16.04", "GFM.1.08.04")
                fromConceptELRs.clear()
            for rel in rels:
                fromMbr = rel.fromModelObject
                toMbr = rel.toModelObject
                toELR = rel.targetRole
                if toELR and len(
                    val.modelXbrl.relationshipSet(
                         XbrlConst.domainMember, toELR).fromModelObject(toMbr)) == 0:
                    val.modelXbrl.error(
                        _("Domain member {0} in DRS role {1}, missing targetrole consecutive relationship").format(
                              fromMbr.qname, ELR), 
                        "err", "EFM.6.16.09", "GFM.1.08.09")
                    
    if val.validateSBRNL:
        # check hypercubes for unique set of members
        for hc in hypercubes:
            for priHcRel in val.modelXbrl.relationshipSet(XbrlConst.all).toModelObject(hc):
                priItem = priHcRel.fromModelObject
                ELR = priHcRel.linkrole
                checkSBRNLMembers(val, hc, priItem, ELR, 
                                  val.modelXbrl.relationshipSet(XbrlConst.domainMember, ELR).fromModelObject(priItem), 
                                  ELR, False)
        for ELR, hypercubes in hypercubesInLinkrole.items():
            if len(hypercubes) > 1:
                val.modelXbrl.error(
                    _("ELR role {0}, has multiple hypercubes {1}").format(
                          ELR, ", ".join([str(hc.qname) for hc in hypercubes])), 
                    "err", "SBR.NL.2.3.5.03")
            for hc in hypercubes:  # only one member
                for arcrole in (XbrlConst.parentChild, "XBRL-dimensions"):
                    for modelRel in val.modelXbrl.relationshipSet(arcrole, ELR).modelRelationships:
                        if modelRel.fromModelObject != hc:
                            val.modelXbrl.error(
                                _("ELR role {0}, for hypercube {1} has another parent {2}").format(
                                      ELR, hc.qname, modelRel.fromModelObject.qname), 
                                "err", "SBR.NL.2.2.3.05")
        for ELR, domains in val.domainsInLinkrole.items():
            if len(domains) > 1:
                val.modelXbrl.error(
                    _("ELR role {0}, has multiple domains {1}").format(
                          ELR, ", ".join([str(dom.qname) for dom in domains])), 
                    "err", "SBR.NL.2.3.7.04")
        #check unique set of dimensions per hypercube
        for hc, DRSdims in hypercubeDRSDimensions.items():
            priorELR = None
            priorDRSdims = None
            for ELR, dims in DRSdims.items():
                if priorDRSdims is not None and priorDRSdims != dims:
                    val.modelXbrl.error(
                        _("Hypercube {0} has different dimensions in DRS roles {1} and {2}: {3} and {4}").format(
                              hc.qname, ELR, priorELR,
                              ", ".join([str(dim.qname) for dim in dims]),
                              ", ".join([str(dim.qname) for dim in priorDRSdims])), 
                        "err", "SBR.NL.2.3.5.02")
                priorELR = ELR
                priorDRSdims = dims
    del val.domainsInLinkrole   # dereference

                        
def getDrsRels(val, fromELR, rels, drsELR, drsRelsFrom, drsRelsTo, fromConcepts=None):
    if not fromConcepts: fromConcepts = set()
    for rel in rels:
        relTo = rel.toModelObject
        drsRelsFrom[rel.fromModelObject].append(rel)
        drsRelsTo[relTo].append(rel)
        toELR = rel.targetRole
        if not toELR: toELR = fromELR
        if relTo not in fromConcepts: 
            fromConcepts.add(relTo)
            domMbrRels = val.modelXbrl.relationshipSet(
                     XbrlConst.domainMember, toELR).fromModelObject(relTo)
            getDrsRels(val, toELR, domMbrRels, drsELR, drsRelsFrom, drsRelsTo, fromConcepts)
            fromConcepts.discard(relTo)
    return False        
    
def undirectedFwdCycle(val, fromELR, rels, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited=None):
    if not ELRsVisited: ELRsVisited = set()
    ELRsVisited.add(fromELR)
    for rel in rels:
        if rel.linkrole == fromELR:
            relTo = rel.toModelObject
            toELR = rel.targetRole
            if not toELR:
                toELR = fromELR
            if relTo in fromConceptELRs and toELR in fromConceptELRs[relTo]: #forms a directed cycle
                return relTo
            fromConceptELRs[relTo].add(toELR)
            if drsRelsFrom:
                domMbrRels = drsRelsFrom[relTo]
            else:
                domMbrRels = val.modelXbrl.relationshipSet(
                         XbrlConst.domainMember, toELR).fromModelObject(relTo)
            cycleCausingConcept = undirectedFwdCycle(val, toELR, domMbrRels, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited)
            if cycleCausingConcept is not None:
                return cycleCausingConcept
            fromConceptELRs[relTo].discard(toELR)
            # look for back path in any of the ELRs visited (pass None as ELR)
            cycleCausingConcept = undirectedRevCycle(val, None, relTo, rel, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited)
            if cycleCausingConcept is not None:
                return cycleCausingConcept
    return None

def undirectedRevCycle(val, fromELR, mbrConcept, turnbackRel, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited):
    for arcrole in (XbrlConst.domainMember, XbrlConst.dimensionDomain):
        '''
        for ELR in ELRsVisited if (not fromELR) else (fromELR,):
            for rel in val.modelXbrl.relationshipSet(arcrole, ELR).toModelObject(mbrConcept):
                if not rel.isIdenticalTo(turnbackRel):
                    relFrom = rel.fromModelObject
                    relELR = rel.linkrole
                    if relFrom in fromConcepts and relELR == drsELR:
                        return True
                    if undirectedRevCycle(val, relELR, relFrom, turnbackRel, drsELR, fromConcepts, ELRsVisited):
                        return True
        '''
        if drsRelsTo:
            mbrDomRels = drsRelsTo[mbrConcept]
        else:
            mbrDomRels = val.modelXbrl.relationshipSet(arcrole, None).toModelObject(mbrConcept)
        for rel in mbrDomRels:
            if not rel.isIdenticalTo(turnbackRel):
                relFrom = rel.fromModelObject
                relELR = rel.linkrole
                if relFrom in fromConceptELRs and relELR in fromConceptELRs[relFrom]:
                    return turnbackRel.toModelObject
                cycleCausingConcept = undirectedRevCycle(val, relELR, relFrom, turnbackRel, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited)
                if cycleCausingConcept is not None:
                    return cycleCausingConcept
    return None
                
def commonAncestor(domainMemberRelationshipSet, 
                   negSourceConcept, posSourceConcepts):
    negAncestors = ancestorOrSelf(domainMemberRelationshipSet,negSourceConcept)
    for posSourceConcept in posSourceConcepts:
        if len(negAncestors & ancestorOrSelf(domainMemberRelationshipSet,posSourceConcept)):
            return True
    return False

def ancestorOrSelf(domainMemberRelationshipSet,sourceConcept,result=None):
    if not result:
        result = set()
    if not sourceConcept in result:
        result.add(sourceConcept)
        for rels in domainMemberRelationshipSet.toModelObject(sourceConcept):
            ancestorOrSelf(domainMemberRelationshipSet, rels.fromModelObject, result)
    return result
        
def checkSBRNLMembers(val, hc, dim, domELR, rels, ELR, isDomMbr, members=None, ancestors=None):
    if members is None: members = set()
    if ancestors is None: ancestors = set()
    for rel in rels:
        relFrom = rel.fromModelObject
        relTo = rel.toModelObject
        toELR = rel.targetRole
        if not toELR: 
            toELR = rel.linkrole
        
        if isDomMbr or not relTo.isAbstract:
            if relTo in members:
                val.modelXbrl.relationshipSet(XbrlConst.all).toModelObject(hc)
                if isDomMbr:
                    val.modelXbrl.error(
                        _("Dimension {1} in DRS role {2} for hypercube {3}, non-unique member {4}").format(
                              dim.qname, ELR, hc.qname, relTo.qname), 
                        "err", "SBR.NL.2.3.6.02")
                else:
                    val.modelXbrl.error(
                        _("Primary items for hypercube {0} ELR{1}, have non-unique (inheritance) member {2} in DRS role {3}").format(
                              hc.qname, domELR, relTo.qname, ELR), 
                        "err", "SBR.NL.2.3.5.01")
            members.add(relTo)
        if isDomMbr:
            if rel.arcrole == XbrlConst.dimensionDomain:
                val.domainsInLinkrole[toELR].add(relTo)
                if not rel.isUsable:
                    val.modelXbrl.error(
                        _("Dimension {0} in DRS role {1} for hypercube {2}, has usable domain {3}").format(
                              dim.qname, ELR, hc.qname, relTo.qname), 
                        "err", "SBR.NL.2.3.7.05")
                if not relTo.isAbstract:
                    val.modelXbrl.error(
                        _("Dimension {0} in DRS role {1} for hypercube {2}, has nonAbsract domain {3}").format(
                              dim.qname, ELR, hc.qname, relTo.qname), 
                        "err", "SBR.NL.2.3.7.02")
                if relTo.substitutionGroupQname.localName != "domainItem":
                    val.modelXbrl.error(
                        _("Domain item {0} in DRS role {1} for hypercube {2}, in dimension {3} is not a domainItem").format(
                              relTo.qname, ELR, hc.qname, relFrom.qname), 
                        "err", "SBR.NL.2.2.2.19")
                if not rel.targetRole:
                    val.modelXbrl.error(
                        _("Dimension {0} in DRS role {1} in hypercube {2}, missing targetrole to consecutive domain relationship").format(
                              dim.qname, ELR, hc.qname), 
                        "err", "SBR.NL.2.3.6.03")
            else: # domain-member arcrole
                val.modelXbrl.error(
                    _("Dimension {0} in DRS role {1} for hypercube {2}, has nested members {3} and {4}").format(
                          dim.qname, ELR, hc.qname, relFrom.qname, relTo.qname), 
                    "err", "SBR.NL.2.3.7.03")
                if relTo.substitutionGroupQname.localName != "domainMemberItem":
                    val.modelXbrl.error(
                        _("Member item {0} in DRS role {1} for hypercube {2}, in dimension {3} is not a domainItem").format(
                              relTo.qname, ELR, hc.qname, dim.qname), 
                        "err", "SBR.NL.2.2.2.19")
        else: # pri item relationships
            if (relTo.isAbstract and not relFrom.isAbstract or 
                relFrom.substitutionGroupQname.localName != "primaryDomainItem"):
                val.modelXbrl.error(
                    _("Primary item {0} in DRS role {1} for hypercube {2}, has parent {3} which is not a primaryDomainItem").format(
                          relTo.qname, ELR, hc.qname, relFrom.qname), 
                    "err", "SBR.NL.2.3.7.01")
        if relTo not in ancestors: 
            ancestors.add(relTo)
            domMbrRels = val.modelXbrl.relationshipSet(
                     XbrlConst.domainMember, toELR).fromModelObject(relTo)
            checkSBRNLMembers(val, hc, dim, domELR, domMbrRels, ELR, isDomMbr, members, ancestors)
            ancestors.discard(relTo)
    return False        
    
