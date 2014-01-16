'''
This module provides database interfaces to postgres SQL

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).
'''
import re
from arelle import XbrlConst

EFMtableCodes = [
    # ELRs are parsed for these patterns in sort order until there is one match per code
    # sheet(s) may be plural
    ("DEI", re.compile(r".* - document - .*document\W+.*entity\W+.*information.*", re.IGNORECASE)),
    ("BS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*balance\W+sheet.*", re.IGNORECASE)),
    ("BSP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                       r".*balance\W+sheet.*", re.IGNORECASE)),
    ("CF", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*cash\W*flow.*", re.IGNORECASE)),
    ("IS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*comprehensive(.*\Wincome|.*\Wloss)", re.IGNORECASE)),
    ("SE", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*(equity|capital|deficit).*", re.IGNORECASE)),
    ("IS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*(income|operations)", re.IGNORECASE)),
    ("ISP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                      r".*(income|operations)", re.IGNORECASE)),
    ("CFP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                      r".*cash\W*flow.*", re.IGNORECASE)),
    ("IS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*loss", re.IGNORECASE)),
    ("ISP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                      r".*loss", re.IGNORECASE)),
    ("BS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".(position|condition)", re.IGNORECASE)),
    ("BSP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                       r".*(position|condition)", re.IGNORECASE)),
    ("SE", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*equity\W(\w+\W+)*comprehensive.*", re.IGNORECASE)),
    ]

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
    if disclosureSystem.EFM:
        tableCodes = list( EFMtableCodes ) # separate copy of list so entries can be deleted
        codeRoleURIs = {}  # lookup by code for roleURI
        roleURIcodeFacts = []  # list of (roleURI, code, fact)
        
        # resolve structural model
        roleTypes = [roleType
                     for roleURI in dts.relationshipSet(XbrlConst.parentChild).linkRoleUris
                     for roleType in dts.roleTypes.get(roleURI,())]
        roleTypes.sort(key=lambda roleType: roleType.definition)
        # assign code to table
        for roleType in roleTypes:
            definition = roleType.definition
            for i, tableCode in enumerate(tableCodes):
                code, pattern = tableCode
                if code not in codeRoleURIs and pattern.match(definition):
                    codeRoleURIs[roleType.roleURI] = code
                    del tableCodes[i] # done with looking at this code
                    break
        # find defined non-default axes in pre hierarchy for table
        factsByQname = dts.factsByQname
        for roleType in roleTypes:
            roleURI = roleType.roleURI
            code = codeRoleURIs.get(roleURI)
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
    