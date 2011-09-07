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
                            val.modelXbrl.error("SBR.NL.2.3.6.04",
                                _("All hypercube %(hypercube)s in DRS role %(linkrole)s, does not have closed='true'"),
                                modelObject=hasHcRel, hypercube=hc.qname, linkrole=ELR)
                    elif hasHypercubeArcrole == XbrlConst.notAll:
                        if hasHcRel.isClosed:
                            val.modelXbrl.error(("EFM.6.16.06", "GFM.1.08.06"),
                                _("Not all hypercube %(hypercube)s in DRS role %(linkrole)s, does not have closed='false'"),
                                modelObject=hasHcRel, hypercube=hc.qname, linkrole=ELR)
                        if hc in positiveHypercubes:
                            val.modelXbrl.error(("EFM.6.16.08", "GFM.1.08.08"),
                                _("Not all hypercube %(hypercube)s in DRS role %(linkrole)s, is also the target of a positive hypercube"),
                                modelObject=hasHcRel, hypercube=hc.qname, linkrole=ELR)
                    numberOfHCsPerSourceConcept += 1
                    dimELR = hasHcRel.targetRole
                    dimTargetRequired = (dimELR is not None)
                    if not dimELR:
                        dimELR = ELR
                    hypercubesInLinkrole[dimELR].add(hc) # this is the elr containing the HC-dim relations
                    hcDimRels = val.modelXbrl.relationshipSet(
                             XbrlConst.hypercubeDimension, dimELR).fromModelObject(hc)
                    if dimTargetRequired and len(hcDimRels) == 0:
                        val.modelXbrl.error(("EFM.6.16.09", "GFM.1.08.09"),
                            _("Table %(hypercube)s in DRS role %(linkrole)s, missing targetrole consecutive relationship"),
                            modelObject=hasHcRel, hypercube=hc.qname, linkrole=ELR)
                    for hcDimRel in hcDimRels:
                        dim = hcDimRel.toModelObject
                        domELR = hcDimRel.targetRole
                        domTargetRequired = (domELR is not None)
                        if not domELR:
                            domELR = dimELR
                            if val.validateSBRNL:
                                val.modelXbrl.error("SBR.NL.2.3.5.04",
                                    _("Hypercube %(hypercube)s in DRS role %(linkrole)s, missing targetrole to dimension %(dimension)s consecutive relationship"),
                                    modelObject=hcDimRel, hypercube=hc.qname, linkrole=ELR, dimension=dim.qname)
                        else:
                            if dim.isTypedDimension and val.validateSBRNL:
                                val.modelXbrl.error("SBR.NL.2.3.5.07",
                                    _("Typed dimension %(dimension)s in DRS role %(linkrole)s, has targetrole consecutive relationship"),
                                    modelObject=hcDimRel, dimension=dim.qname, linkrole=ELR)
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
                            val.modelXbrl.error(("EFM.6.16.07", "GFM.1.08.08"),
                                _("Negative table axis %(dimension)s in DRS role %(linkrole)s, not in any positive table in same role"),
                                 modelObject=hcDimRel, dimension=dim.qname, linkrole=ELR)
                        dimDomRels = val.modelXbrl.relationshipSet(
                             XbrlConst.dimensionDomain, domELR).fromModelObject(dim)   
                        if domTargetRequired and len(dimDomRels) == 0:
                            val.modelXbrl.error(("EFM.6.16.09", "GFM.1.08.09"),
                                _("Axis %(dimension)s in DRS role %(linkrole)s, missing targetrole consecutive relationship"),
                                modelObject=hcDimRel, dimension=dim.qname, linkrole=ELR)
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
                                cycleCausingConcept.append(hcDimRel)
                                val.modelXbrl.error(("EFM.6.16.04", "GFM.1.08.04"),
                                    _("Dimension relationships have an undirected cycle in DRS role %(linkrole)s \nstarting from table %(hypercube)s, \naxis %(dimension)s, \npath %(path)s"),
                                    modelObject=hcDimRel, linkrole=ELR, hypercube=hc.qname, dimension=dim.qname, path=cyclePath(hc,cycleCausingConcept))
                            fromConceptELRs.clear()
                        elif val.validateSBRNL:
                            checkSBRNLMembers(val, hc, dim, domELR, dimDomRels, ELR, True)
                if hasHypercubeArcrole == XbrlConst.all and numberOfHCsPerSourceConcept > 1:
                    val.modelXbrl.error(("EFM.6.16.05", "GFM.1.08.05"),
                        _("Multiple tables (%(hypercubeCount)s) DRS role %(linkrole)s, source %(concept)s, only 1 allowed"),
                        modelObject=sourceConcept, 
                        hypercubeCount=numberOfHCsPerSourceConcept, linkrole=ELR, concept=sourceConcept.qname)
                    
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
                    val.modelXbrl.error(("EFM.6.16.04", "GFM.1.08.04"),
                        _("Domain-member primary-item relationships have an undirected cycle in DRS role %(linkrole)s \nstarting from %(conceptFrom)s, \npath %(path)s"),
                        modelObject=relFrom, linkrole=ELR, conceptFrom=relFrom.qname, path=cyclePath(relFrom, cycleCausingConcept))
                fromConceptELRs.clear()
            for rel in rels:
                fromMbr = rel.fromModelObject
                toMbr = rel.toModelObject
                toELR = rel.targetRole
                if toELR and len(
                    val.modelXbrl.relationshipSet(
                         XbrlConst.domainMember, toELR).fromModelObject(toMbr)) == 0:
                    val.modelXbrl.error(("EFM.6.16.09", "GFM.1.08.09"),
                        _("Domain member %(concept)s in DRS role %(linkrole)s, missing targetrole consecutive relationship"),
                        modelObject=rel, concept=fromMbr.qname, linkrole=ELR)
                    
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
                val.modelXbrl.error("SBR.NL.2.3.5.03",
                    _("ELR role %(linkrole)s, has multiple hypercubes %(hypercubes)s"),
                    modelObject=val.modelXbrl, linkrole=ELR, hypercubes=", ".join([str(hc.qname) for hc in hypercubes]))
            for hc in hypercubes:  # only one member
                for arcrole in (XbrlConst.parentChild, "XBRL-dimensions"):
                    for modelRel in val.modelXbrl.relationshipSet(arcrole, ELR).modelRelationships:
                        if modelRel.fromModelObject != hc:
                            val.modelXbrl.error("SBR.NL.2.2.3.05",
                                _("ELR role %(linkrole)s, for hypercube %(hypercube)s has another parent %(concept)s"),
                                modelObject=modelRel, linkrole=ELR, hypercube=hc.qname, concept=modelRel.fromModelObject.qname)
        for ELR, domains in val.domainsInLinkrole.items():
            if len(domains) > 1:
                val.modelXbrl.error("SBR.NL.2.3.7.04",
                    _("ELR role %(linkrole)s, has multiple domains %(domains)s"),
                    modelObject=val.modelXbrl, linkrole=ELR, domains=", ".join([str(dom.qname) for dom in domains]))
        #check unique set of dimensions per hypercube
        for hc, DRSdims in hypercubeDRSDimensions.items():
            priorELR = None
            priorDRSdims = None
            for ELR, dims in DRSdims.items():
                if priorDRSdims is not None and priorDRSdims != dims:
                    val.modelXbrl.error("SBR.NL.2.3.5.02",
                        _("Hypercube %(hypercube)s has different dimensions in DRS roles %(linkrole)s and %(linkrole2)s: %(dimensions)s and %(dimensoins2)s"),
                        modelObject=val.modelXbrl, hypercube=hc.qname, linkrole=ELR, linkrole2=priorELR,
                        dimensions=", ".join([str(dim.qname) for dim in dims]),
                        dimensions2=", ".join([str(dim.qname) for dim in priorDRSdims]))
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
                return [rel,True]
            fromConceptELRs[relTo].add(toELR)
            if drsRelsFrom:
                domMbrRels = drsRelsFrom[relTo]
            else:
                domMbrRels = val.modelXbrl.relationshipSet(
                         XbrlConst.domainMember, toELR).fromModelObject(relTo)
            cycleCausingConcept = undirectedFwdCycle(val, toELR, domMbrRels, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited)
            if cycleCausingConcept is not None:
                cycleCausingConcept.append(rel)
                cycleCausingConcept.append(True)
                return cycleCausingConcept
            fromConceptELRs[relTo].discard(toELR)
            # look for back path in any of the ELRs visited (pass None as ELR)
            cycleCausingConcept = undirectedRevCycle(val, None, relTo, rel, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited)
            if cycleCausingConcept is not None:
                cycleCausingConcept.append(rel)
                cycleCausingConcept.append(True)
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
                    return [rel, False] # turnbackRel.toModelObject
                cycleCausingConcept = undirectedRevCycle(val, relELR, relFrom, turnbackRel, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited)
                if cycleCausingConcept is not None:
                    cycleCausingConcept.append(rel)
                    cycleCausingConcept.append(False)
                    return cycleCausingConcept
    return None

def cyclePath(source, cycles):
    isForward = True
    path = []
    for rel in reversed(cycles):
        if isinstance(rel,bool):
            isForward = rel
        else:
            path.append("{0}:{1} {2}".format(rel.modelDocument.basename, 
                                             rel.sourceline, 
                                             rel.toModelObject.qname if isForward else rel.fromModelObject.qname))
    return str(source.qname) + " " + " - ".join(path)            
                
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
                    val.modelXbrl.error("SBR.NL.2.3.6.02",
                        _("Dimension %(dimension)s in DRS role %(linkrole)s for hypercube %(hypercube)s, non-unique member %(concept)s"),
                        modelObject=relTo, dimension=dim.qname, linkrole=ELR, hypercube=hc.qname, concept=relTo.qname) 
                else:
                    val.modelXbrl.error("SBR.NL.2.3.5.01",
                        _("Primary items for hypercube %(hypercube)s ELR %(ELR)s, have non-unique (inheritance) member %(concept)s in DRS role %(linkrole)s"),
                        modelObject=relTo, hypercube=hc.qname, ELR=domELR, concept=relTo.qname, linkrole=ELR)
            members.add(relTo)
        if isDomMbr:
            if rel.arcrole == XbrlConst.dimensionDomain:
                val.domainsInLinkrole[toELR].add(relTo)
                if not rel.isUsable:
                    val.modelXbrl.error("SBR.NL.2.3.7.05",
                        _("Dimension %(dimension)s in DRS role %(linkrole)s for hypercube %(hypercube)s, has usable domain %(domain)s"),
                        modelObject=rel, dimension=dim.qname, linkrole=ELR, hypercube=hc.qname, domain=relTo.qname)
                if not relTo.isAbstract:
                    val.modelXbrl.error("SBR.NL.2.3.7.02",
                        _("Dimension %(dimension)s in DRS role %(linkrole)s for hypercube %(hypercube)s, has nonAbsract domain %(domain)s"),
                        modelObject=rel, dimension=dim.qname, linkrole=ELR, hypercube=hc.qname, domain=relTo.qname)
                if relTo.substitutionGroupQname.localName != "domainItem":
                    val.modelXbrl.error("SBR.NL.2.2.2.19",
                        _("Domain item %(domain)s in DRS role %(linkrole)s for hypercube %(hypercube)s, in dimension %(dimension)s is not a domainItem"),
                        modelObject=rel, domain=relTo.qname, linkrole=ELR, hypercube=hc.qname, dimension=relFrom.qname)
                if not rel.targetRole:
                    val.modelXbrl.error("SBR.NL.2.3.6.03",
                        _("Dimension %(dimension)s in DRS role %(linkrole)s in hypercube %(hypercube)s, missing targetrole to consecutive domain relationship"),
                        modelObject=rel, dimension=dim.qname, linkrole=ELR)
            else: # domain-member arcrole
                val.modelXbrl.error("SBR.NL.2.3.7.03",
                    _("Dimension %(dimension)s in DRS role %(linkrole)s for hypercube %(hypercube)s, has nested members %(member)s and %(member2)s"),
                    modelObject=rel, dimension=dim.qname, linkrole=ELR, hypercube=hc.qname, member=relFrom.qname, member2=relTo.qname)
                if relTo.substitutionGroupQname.localName != "domainMemberItem":
                    val.modelXbrl.error("SBR.NL.2.2.2.19",
                        _("Member item %(member)s in DRS role %(linkrole)s for hypercube %(hypercube)s, in dimension %(dimension)s is not a domainItem"),
                        modelObject=rel, member=relTo.qname, linkrole=ELR, hypercube=hc.qname, dimension=dim.qname)
        else: # pri item relationships
            if (relTo.isAbstract and not relFrom.isAbstract or 
                relFrom.substitutionGroupQname.localName != "primaryDomainItem"):
                val.modelXbrl.error("SBR.NL.2.3.7.01",
                    _("Primary item %(concept)s in DRS role %(linkrole)s for hypercube %(hypercube)s, has parent %(concept2)s which is not a primaryDomainItem"),
                    modelObject=rel, concept=relTo.qname, linkrole=ELR, hypercube=hc.qname, concept2=relFrom.qname)
        if relTo not in ancestors: 
            ancestors.add(relTo)
            domMbrRels = val.modelXbrl.relationshipSet(
                     XbrlConst.domainMember, toELR).fromModelObject(relTo)
            checkSBRNLMembers(val, hc, dim, domELR, domMbrRels, ELR, isDomMbr, members, ancestors)
            ancestors.discard(relTo)
    return False        
    
