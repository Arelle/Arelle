'''
This module provides database interfaces to postgres SQL

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).
'''
from arelle import XbrlConst

def EFMlinkRoleURIstructure(dts, roleURI):
    relSet = dts.relationshipSet(XbrlConst.parentChild, roleURI)
    dimMems = {} # by dimension qname, set of member qnames
    priItems = set()
    for rootConcept in relSet.rootConcepts:
        EFMlinkRoleDescendants(relSet, rootConcept, dimMems, priItems)
    return dimMems, priItems
        
def EFMlinkRoleDescendants(relSet, concept, dimMems, priItems):
    if concept is not None:
        if concept.isDimensionItem:
            dimMems[concept.qname] = EFMdimMems(relSet, concept, set())
        else:
            if not concept.isAbstract:
                priItems.add(concept.qname)
            for rel in relSet.fromModelObject(concept):
                EFMlinkRoleDescendants(relSet, rel.toModelObject, dimMems, priItems)

def EFMdimMems(relSet, concept, memQNames):
    for rel in relSet.fromModelObject(concept):
        dimConcept = rel.toModelObject
        if dimConcept is not None and dimConcept.isDomainMember:
            memQNames.add(dimConcept.qname)
            EFMdimMems(relSet, dimConcept, memQNames)
    return memQNames

def tableFacts(dts):
    # identify tables
    disclosureSystem = dts.modelManager.disclosureSystem
    if disclosureSystem.validationType in ("EFM", "HMRC"):
        roleURIcodeFacts = []  # list of (roleURI, code, fact)
        
        # resolve structural model
        roleTypes = [roleType
                     for roleURI in dts.relationshipSet(XbrlConst.parentChild).linkRoleUris
                     for roleType in dts.roleTypes.get(roleURI,())]
        roleTypes.sort(key=lambda roleType: roleType.definition)
        # find defined non-default axes in pre hierarchy for table
        factsByQname = dts.factsByQname
        for roleType in roleTypes:
            roleURI = roleType.roleURI
            code = roleType.tableCode
            roleURIdims, priItemQNames = EFMlinkRoleURIstructure(dts, roleURI)
            for priItemQName in priItemQNames:
                for fact in factsByQname[priItemQName]:
                    cntx = fact.context
                    # non-explicit dims must be default
                    if (cntx is not None and
                        all(dimQn in dts.qnameDimensionDefaults
                            for dimQn in (roleURIdims.keys() - cntx.qnameDims.keys())) and
                        all(mdlDim.memberQname in roleURIdims[dimQn]
                            for dimQn, mdlDim in cntx.qnameDims.items()
                            if dimQn in roleURIdims)):
                        roleURIcodeFacts.append((roleType, code, fact))
                     
        return roleURIcodeFacts
    return None
    