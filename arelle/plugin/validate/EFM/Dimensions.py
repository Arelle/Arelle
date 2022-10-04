'''
See COPYRIGHT.md for copyright information.
'''
from collections import defaultdict
from arelle import XbrlConst
from arelle.ModelDtsObject import ModelConcept
import os
emptySet = set()

def checkFilingDimensions(val, drsELRs):

    fromConceptELRs = defaultdict(set)
    hypercubes = set()
    hypercubesInLinkrole = defaultdict(set)
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
                    elif hasHypercubeArcrole == XbrlConst.notAll:
                        if hasHcRel.isClosed:
                            val.modelXbrl.error(("EFM.6.16.06", "GFM.1.08.06"),
                                _("The notAll relationship for table %(hypercube)s must have the closed attribute set to 'false' "
                                  "so that it can achieve its intended purpose of excluding combinations of domain values, on "
                                  "relationship from %(primaryItem)s, in role %(linkrole)s. Please recheck submission."),
                                edgarCode="fs-1606-Not-All-Relationship-Is-Closed",
                                modelObject=hasHcRel, hypercube=hc.qname, linkrole=ELR, primaryItem=sourceConcept.qname)
                        if hc in positiveHypercubes:
                            val.modelXbrl.error(("EFM.6.16.08", "GFM.1.08.08"),
                                _("Element %(hypercube)s is a table that negates itself in %(linkroleDefinition)s for primary item "
                                  "%(primaryItem)s.  Modify the 'all' and 'notAll' relationships that have the element as a target.  "
                                  "Please recheck submission."),
                                edgarCode="fs-1608-Table-Excludes-Itself",
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
                            _("A table is malformed because the %(arcroleURI)s from %(fromConcept)s to %(toConcept)s in link role "
                              "%(linkroleDefinition)s has no consecutive relationships.  "
                              "Remove the targetRole attribute, or provide a consecutive relationship."),
                            edgarCode="fs-1609-Target-Role-With-No-Consecutive-Relationships",
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
                            if hasHypercubeArcrole == XbrlConst.all:
                                positiveAxisTableSources[dim].add(sourceConcept)
                            elif hasHypercubeArcrole == XbrlConst.notAll and \
                                 (dim not in positiveAxisTableSources or \
                                  not commonAncestor(domainMemberRelationshipSet,
                                                  sourceConcept, positiveAxisTableSources[dim])):
                                val.modelXbrl.error(("EFM.6.16.07", "GFM.1.08.08"),
                                    _("Members of axis %(dimension)s are excluded, in role %(linkroleDefinition)s, "
                                      "from primary item %(primaryItem)s but not included in any table.  "
                                      "Please modify the relationships to make it consistent."),
                                    edgarCode="fs-1607-Axis-Excluded-Not-In-Table",
                                    modelObject=hcDimRel, dimension=dim.qname, linkrole=ELR, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR), primaryItem=sourceConcept.qname)
                            dimDomRels = val.modelXbrl.relationshipSet(
                                 XbrlConst.dimensionDomain, domELR).fromModelObject(dim)
                            if domTargetRequired and len(dimDomRels) == 0:
                                val.modelXbrl.error(("EFM.6.16.09", "GFM.1.08.09"),
                                    _("A table is malformed because the %(arcroleURI)s from %(fromConcept)s to %(toConcept)s "
                                      "in link role %(linkroleDefinition)s has no consecutive relationships.  "
                                      "Remove the targetRole attribute, or provide a consecutive relationship."),
                                    edgarCode="fs-1609-Target-Role-With-No-Consecutive-Relationships",
                                    modelObject=hcDimRel, dimension=dim.qname, fromConcept=hc.qname, toConcept=dim.qname, linkrole=ELR, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR), arcroleURI=hasHcRel.arcrole, arcrole=os.path.basename(hcDimRel.arcrole))
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
                                    _("Element %(conceptFrom)s appears in overlapping sets of members in a Directed Relationship "
                                      "Set in role %(linkroleDefinition)s, axis %(dimension)s, path %(path)s.  "
                                      "Remove it as a target of one of its domain-member relationships. Please recheck submission."),
                                    edgarCode="fs-1604-Domain-Is-Tangled",
                                    modelObject=[hc, dim] + [rel for rel in cycleCausingConcept if not isinstance(rel, bool)],
                                    linkrole=ELR, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR),
                                    hypercube=hc.qname, dimension=dim.qname, conceptFrom=dim.qname,
                                    path=cyclePath(hc,cycleCausingConcept))
                            fromConceptELRs.clear()
                if hasHypercubeArcrole == XbrlConst.all and len(hasHcRels) > 1:
                    val.modelXbrl.error(("EFM.6.16.05", "GFM.1.08.05"),
                        _("Element %(concept)s is a primary element of more than one Table in relationship group %(linkroleDefinition)s, "
                          "to tables %(hypercubes)s. Please modify the 'all' relationships that have the element as a source so that "
                          "it has only one primary axis."),
                        edgarCode="fs-1605-Primary-Element-Has-Redundant-Tables",
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
                        _("Element %(conceptFrom)s appears in overlapping sets of members in a Directed Relationship Set in "
                          "role %(linkroleDefinition)s, from %(conceptFrom)s, path %(path)s.  "
                          "Remove it as a target of one of its domain-member relationships. Please recheck submission."),
                        edgarCode="fs-1604-Domain-Is-Tangled",
                        modelObject=[relFrom] + [rel for rel in cycleCausingConcept if not isinstance(rel, bool)],
                        linkrole=ELR, conceptFrom=relFrom.qname, path=cyclePath(relFrom, cycleCausingConcept),
                        linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR))
                fromConceptELRs.clear()
            for rel in rels:
                fromMbr = rel.fromModelObject
                toMbr = rel.toModelObject
                toELR = rel.targetRole
                if isinstance(toMbr, ModelConcept) and toELR and len(
                    val.modelXbrl.relationshipSet(
                         XbrlConst.domainMember, toELR).fromModelObject(toMbr)) == 0:
                    val.modelXbrl.error(("EFM.6.16.09", "GFM.1.08.09"),
                        _("A table is malformed because the %(arcroleURI)s from %(fromConcept)s to %(toConcept)s in link role "
                          "%(linkroleDefinition)s has no consecutive relationships.  "
                          "Remove the targetRole attribute, or provide a consecutive relationship."),
                        edgarCode="fs-1609-Target-Role-With-No-Consecutive-Relationships",
                        modelObject=rel, concept=fromMbr.qname, fromConcept=toMbr.qname, toConcept=fromMbr.qname, linkrole=ELR, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR), arcroleURI=hasHcRel.arcrole, arcrole=os.path.basename(rel.arcrole))


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
