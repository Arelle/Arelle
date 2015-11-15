'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.

Deprecated Nov 15, 2015.  Use plugin/validate/EFM/Dimensions.py
'''
from collections import defaultdict
from arelle import XbrlConst
from arelle.ModelDtsObject import ModelConcept
import os
emptySet = set()

def checkDimensions(val, drsELRs):
    
    fromConceptELRs = defaultdict(set)
    hypercubes = set()
    hypercubesInLinkrole = defaultdict(set)
    domainsInLinkrole = defaultdict(set)
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
                                modelObject=hasHcRel, hypercube=hc.qname, linkrole=ELR, primaryItem=sourceConcept.qname)
                        if hc in positiveHypercubes:
                            val.modelXbrl.error(("EFM.6.16.08", "GFM.1.08.08"),
                                _("Not all hypercube %(hypercube)s in DRS role %(linkrole)s, is also the target of a positive hypercube"),
                                modelObject=hasHcRel, hypercube=hc.qname, linkrole=ELR, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR), primaryItem=sourceConcept.qname)
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
                            modelObject=hasHcRel, hypercube=hc.qname, fromConcept=sourceConcept.qname, toConcept=hc.qname, 
                            linkrole=ELR, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR),
                            arcroleURI=hasHcRel.arcrole, arcrole=os.path.basename(hasHcRel.arcrole))
                    for hcDimRel in hcDimRels:
                        dim = hcDimRel.toModelObject
                        if isinstance(dim, ModelConcept):
                            domELR = hcDimRel.targetRole
                            domTargetRequired = (domELR is not None)
                            if not domELR:
                                if dim.isExplicitDimension:
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
                            elif hasHypercubeArcrole == XbrlConst.notAll and \
                                 (dim not in positiveAxisTableSources or \
                                  not commonAncestor(domainMemberRelationshipSet,
                                                  sourceConcept, positiveAxisTableSources[dim])):
                                val.modelXbrl.error(("EFM.6.16.07", "GFM.1.08.08"),
                                    _("Negative table axis %(dimension)s in DRS role %(linkrole)s, not in any positive table in same role"),
                                     modelObject=hcDimRel, dimension=dim.qname, linkrole=ELR, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR), primaryItem=sourceConcept.qname)
                            dimDomRels = val.modelXbrl.relationshipSet(
                                 XbrlConst.dimensionDomain, domELR).fromModelObject(dim)   
                            if domTargetRequired and len(dimDomRels) == 0:
                                val.modelXbrl.error(("EFM.6.16.09", "GFM.1.08.09"),
                                    _("Axis %(dimension)s in DRS role %(linkrole)s, missing targetrole consecutive relationship"),
                                    modelObject=hcDimRel, dimension=dim.qname, fromConcept=hc.qname, toConcept=dim.qname, linkrole=ELR, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR), arcroleURI=hasHcRel.arcrole, arcrole=os.path.basename(hcDimRel.arcrole))
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
                                        modelObject=[hc, dim] + [rel for rel in cycleCausingConcept if not isinstance(rel, bool)], 
                                        linkrole=ELR, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR), 
                                        hypercube=hc.qname, dimension=dim.qname, conceptFrom=dim.qname,
                                        path=cyclePath(hc,cycleCausingConcept))
                                fromConceptELRs.clear()
                            elif val.validateSBRNL:
                                checkSBRNLMembers(val, hc, dim, domELR, dimDomRels, ELR, True)
                                for dimDomRel in dimDomRels:
                                    dom = dimDomRel.toModelObject
                                    if isinstance(dom, ModelConcept):
                                        domainsInLinkrole[domELR].add(dom) # this is the elr containing the HC-dim relations
                if hasHypercubeArcrole == XbrlConst.all and len(hasHcRels) > 1:
                    val.modelXbrl.error(("EFM.6.16.05", "GFM.1.08.05"),
                        _("Multiple tables (%(hypercubeCount)s) DRS role %(linkrole)s, source %(concept)s, only 1 allowed"),
                        modelObject=[sourceConcept] + hasHcRels, 
                        hypercubeCount=len(hasHcRels), linkrole=ELR, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR),
                        concept=sourceConcept.qname,
                        hypercubes=', '.join(str(r.toModelObject.qname) for r in hasHcRels if isinstance(r.toModelObject, ModelConcept)))
                    
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
                        modelObject=[relFrom] + [rel for rel in cycleCausingConcept if not isinstance(rel, bool)], 
                        linkrole=ELR, conceptFrom=relFrom.qname, path=cyclePath(relFrom, cycleCausingConcept))
                fromConceptELRs.clear()
            for rel in rels:
                fromMbr = rel.fromModelObject
                toMbr = rel.toModelObject
                toELR = rel.targetRole
                if isinstance(toMbr, ModelConcept) and toELR and len(
                    val.modelXbrl.relationshipSet(
                         XbrlConst.domainMember, toELR).fromModelObject(toMbr)) == 0:
                    val.modelXbrl.error(("EFM.6.16.09", "GFM.1.08.09"),
                        _("Domain member %(concept)s in DRS role %(linkrole)s, missing targetrole consecutive relationship"),
                        modelObject=rel, concept=fromMbr.qname, fromConcept=toMbr.qname, toConcept=fromMbr.qname, linkrole=ELR, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR), arcroleURI=hasHcRel.arcrole, arcrole=os.path.basename(rel.arcrole))
                    
    if val.validateSBRNL:
        # check hypercubes for unique set of members
        for hc in hypercubes:
            for priHcRel in val.modelXbrl.relationshipSet(XbrlConst.all).toModelObject(hc):
                priItem = priHcRel.fromModelObject
                ELR = priHcRel.linkrole
                checkSBRNLMembers(val, hc, priItem, ELR, 
                                  val.modelXbrl.relationshipSet(XbrlConst.domainMember, ELR).fromModelObject(priItem), 
                                  ELR, False)
                if priHcRel.contextElement == 'segment':  
                    val.modelXbrl.error("SBR.NL.2.3.5.06",
                        _("hypercube %(hypercube)s in segment not allowed, ELR role %(linkrole)s"),
                        modelObject=priHcRel, linkrole=ELR, hypercube=hc.qname)
        for notAllRel in val.modelXbrl.relationshipSet(XbrlConst.notAll).modelRelationships:
            val.modelXbrl.error("SBR.NL.2.3.5.05",
                _("Notall from primary item %(primaryItem)s in ELR role %(linkrole)s to %(hypercube)s"),
                modelObject=val.modelXbrl, primaryItem=notAllRel.fromModelObject.qname, linkrole=notAllRel.linkrole, hypercube=notAllRel.toModelObject.qname)
        for ELR, hypercubes in hypercubesInLinkrole.items():
            '''removed RH 2011-12-06
            for modelRel in val.modelXbrl.relationshipSet("XBRL-dimensions", ELR).modelRelationships:
                if modelRel.fromModelObject != hc:
                    val.modelXbrl.error("SBR.NL.2.3.5.03",
                        _("ELR role %(linkrole)s, is not dedicated to %(hypercube)s, but also has %(otherQname)s"),
                        modelObject=val.modelXbrl, linkrole=ELR, hypercube=hc.qname, otherQname=modelRel.fromModelObject.qname)
            '''
            domains = domainsInLinkrole.get(ELR, emptySet)
            for hc in hypercubes:  # only one member
                for arcrole in (XbrlConst.parentChild, "XBRL-dimensions"):
                    for modelRel in val.modelXbrl.relationshipSet(arcrole, ELR).modelRelationships:
                        if (modelRel.fromModelObject != hc and modelRel.toModelObject != hc and
                            modelRel.fromModelObject not in domains and modelRel.toModelObject not in domains):
                            val.modelXbrl.error("SBR.NL.2.2.3.05",
                                _("ELR role %(linkrole)s, has hypercube %(hypercube)s and a %(arcrole)s relationship not involving the hypercube or primary domain, from %(fromConcept)s to %(toConcept)s"),
                                modelObject=modelRel, linkrole=ELR, hypercube=hc.qname, arcrole=os.path.basename(modelRel.arcrole), 
                                fromConcept=modelRel.fromModelObject.qname, 
                                toConcept=(modelRel.toModelObject.qname if isinstance(modelRel.toModelObject, ModelConcept) else "unknown"))
        domainsInLinkrole = defaultdict(set)
        dimDomMemsByLinkrole = defaultdict(set)
        for rel in val.modelXbrl.relationshipSet(XbrlConst.dimensionDomain).modelRelationships:
            relFrom = rel.fromModelObject
            relTo = rel.toModelObject
            if isinstance(relFrom, ModelConcept) and isinstance(relTo, ModelConcept):
                domainsInLinkrole[rel.targetRole].add(relFrom)
                domMems = set() # determine usable dom and mems of dimension in this linkrole
                if rel.isUsable:
                    domMems.add(relTo)
                for relMem in val.modelXbrl.relationshipSet(XbrlConst.domainMember, (rel.targetRole or rel.linkrole)).fromModelObject(relTo):
                    if relMem.isUsable:
                        domMems.add(relMem.toModelObject)
                dimDomMemsByLinkrole[(rel.linkrole,relFrom)].update(domMems)
                if rel.isUsable and val.modelXbrl.relationshipSet(XbrlConst.domainMember, rel.targetRole).fromModelObject(relTo):
                    val.modelXbrl.error("SBR.NL.2.3.7.05",
                        _("Dimension %(dimension)s in DRS role %(linkrole)s, has usable domain with members %(domain)s"),
                        modelObject=rel, dimension=relFrom.qname, linkrole=rel.linkrole, domain=relTo.qname)
                if not relTo.isAbstract:
                    val.modelXbrl.error("SBR.NL.2.3.7.02",
                        _("Dimension %(dimension)s in DRS role %(linkrole)s, has nonAbsract domain %(domain)s"),
                        modelObject=rel, dimension=relFrom.qname, linkrole=rel.linkrole, domain=relTo.qname)
                if relTo.substitutionGroupQname.localName not in ("domainItem","domainMemberItem"):
                    val.modelXbrl.error("SBR.NL.2.2.2.19",
                        _("Domain item %(domain)s in DRS role %(linkrole)s, in dimension %(dimension)s is not a domainItem"),
                        modelObject=rel, domain=relTo.qname, linkrole=rel.linkrole, dimension=relFrom.qname)
                if not rel.targetRole and relTo.substitutionGroupQname.localName == "domainItem":
                    val.modelXbrl.error("SBR.NL.2.3.6.03",
                        _("Dimension %(dimension)s in DRS role %(linkrole)s, missing targetrole to consecutive domain relationship"),
                        modelObject=rel, dimension=relFrom.qname, linkrole=rel.linkrole)
        for linkrole, domains in domainsInLinkrole.items():
            if linkrole and len(domains) > 1:
                val.modelXbrl.error("SBR.NL.2.3.7.04",
                    _("Linkrole %(linkrole)s, has multiple domains %(domains)s"),
                    modelObject=val.modelXbrl, linkrole=linkrole, domains=", ".join([str(dom.qname) for dom in domains]))
        del domainsInLinkrole   # dereference
        linkrolesByDimDomMems = defaultdict(set)
        for linkroleDim, domMems in dimDomMemsByLinkrole.items():
            linkrole, dim = linkroleDim
            linkrolesByDimDomMems[(dim,tuple(domMems))].add(linkrole)
        for dimDomMems, linkroles in linkrolesByDimDomMems.items():
            if len(linkroles) > 1:
                val.modelXbrl.error("SBR.NL.2.3.6.02",
                    _("Dimension %(dimension)s  usable members same in linkroles %(linkroles)s"),
                    modelObject=val.modelXbrl, dimension=dimDomMems[0].qname, linkroles=', '.join(l for l in linkroles))
        del dimDomMemsByLinkrole, linkrolesByDimDomMems
        for rel in val.modelXbrl.relationshipSet(XbrlConst.domainMember).modelRelationships:
            if val.modelXbrl.relationshipSet(XbrlConst.domainMember, rel.targetRole).fromModelObject(rel.toModelObject):
                val.modelXbrl.error("SBR.NL.2.3.7.03",
                    _("Domain member %(member)s in DRS role %(linkrole)s, has nested members"),
                    modelObject=rel, member=(rel.toModelObject.qname if isinstance(rel.toModelObject, ModelConcept) else None), linkrole=rel.linkrole)
        for rel in val.modelXbrl.relationshipSet(XbrlConst.domainMember).modelRelationships:
            relFrom = rel.fromModelObject
            relTo = rel.toModelObject
            if isinstance(relTo, ModelConcept):
                # avoid primary item relationships in these tests
                if relFrom.substitutionGroupQname.localName == "domainItem":
                    if relTo.substitutionGroupQname.localName != "domainMemberItem":
                        val.modelXbrl.error("SBR.NL.2.2.2.19",
                            _("Domain member item %(member)s in DRS role %(linkrole)s is not a domainMemberItem"),
                            modelObject=rel, member=relTo.qname, linkrole=rel.linkrole)
                else:
                    if relTo.substitutionGroupQname.localName == "domainMemberItem":
                        val.modelXbrl.error("SBR.NL.2.2.2.19",
                            _("Domain item %(domain)s in DRS role %(linkrole)s is not a domainItem"),
                            modelObject=rel, domain=relFrom.qname, linkrole=rel.linkrole)
                        break # don't repeat parent's error on rest of child members
                    elif relFrom.isAbstract and relFrom.substitutionGroupQname.localName != "primaryDomainItem":
                        val.modelXbrl.error("SBR.NL.2.2.2.19",
                            _("Abstract domain item %(domain)s in DRS role %(linkrole)s is not a primaryDomainItem"),
                            modelObject=rel, domain=relFrom.qname, linkrole=rel.linkrole)
                        break # don't repeat parent's error on rest of child members
        hypercubeDRSDimensions = defaultdict(dict)
        for hcDimRel in val.modelXbrl.relationshipSet(XbrlConst.hypercubeDimension).modelRelationships:
            hc = hcDimRel.fromModelObject
            if isinstance(hc, ModelConcept):
                ELR = hcDimRel.linkrole
                try:
                    hcDRSdims = hypercubeDRSDimensions[hc][ELR]
                except KeyError:
                    hcDRSdims = set()
                    hypercubeDRSDimensions[hc][ELR] = hcDRSdims
                hcDRSdims.add(hcDimRel.toModelObject)
        for hc, DRSdims in hypercubeDRSDimensions.items():
            hcELRdimSets = {}
            for ELR, mutableDims in DRSdims.items():
                dims = frozenset(mutableDims)
                if dims not in hcELRdimSets:
                    hcELRdimSets[dims] = ELR
                else: 
                    val.modelXbrl.error("SBR.NL.2.3.5.02",
                        _("Hypercube %(hypercube)s has same dimensions in ELR roles %(linkrole)s and %(linkrole2)s: %(dimensions)s"),
                        modelObject=hc, hypercube=hc.qname, linkrole=ELR, linkrole2=hcELRdimSets[dims],
                        dimensions=", ".join([str(dim.qname) for dim in dims]))
        del hypercubeDRSDimensions # dereference
                        
def getDrsRels(val, fromELR, rels, drsELR, drsRelsFrom, drsRelsTo, fromConcepts=None):
    if not fromConcepts: fromConcepts = set()
    for rel in rels:
        relTo = rel.toModelObject
        if isinstance(relTo, ModelConcept):
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
            if isinstance(relTo, ModelConcept):
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
        if isinstance(relFrom, ModelConcept) and isinstance(relTo, ModelConcept):
            toELR = (rel.targetRole or rel.linkrole)
            
            if isDomMbr or not relTo.isAbstract:
                if relTo in members:
                    val.modelXbrl.relationshipSet(XbrlConst.all).toModelObject(hc)
                    if isDomMbr:
                        pass # removed by RH, now checking dom/mem usable set in entirety for 2.3.6.02 above
                        #val.modelXbrl.error("SBR.NL.2.3.6.02",
                        #    _("Dimension %(dimension)s in DRS role %(linkrole)s for hypercube %(hypercube)s, non-unique member %(concept)s"),
                        #    modelObject=relTo, dimension=dim.qname, linkrole=ELR, hypercube=hc.qname, concept=relTo.qname) 
                    else:
                        val.modelXbrl.error("SBR.NL.2.3.5.01",
                            _("Primary items for hypercube %(hypercube)s ELR %(ELR)s, have non-unique (inheritance) member %(concept)s in DRS role %(linkrole)s"),
                            modelObject=relTo, hypercube=hc.qname, ELR=domELR, concept=relTo.qname, linkrole=ELR)
                members.add(relTo)
            if not isDomMbr: # pri item relationships
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
    
