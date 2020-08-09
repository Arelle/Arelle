'''
Created on June 6, 2018

Filer Guidelines: ESMA_ESEF Manula 2019.pdf


@author: Mark V Systems Limited
(c) Copyright 2018 Mark V Systems Limited, All rights reserved.
'''

from collections import defaultdict
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelObject import ModelObject
from arelle.PrototypeDtsObject import PrototypeObject
from arelle import XbrlConst
from .Const import DefaultDimensionLinkrole, LineItemsNotQualifiedLinkrole
from .Util import isExtension, isInEsefTaxonomy

def checkFilingDimensions(val):

    val.primaryItems = set() # concepts which are line items (should not also be dimension members
    val.domainMembers = set() # concepts which are dimension domain members
    elrPrimaryItems = defaultdict(set)
    hcPrimaryItems = set()
    hcMembers = set()
    
    def addDomMbrs(sourceDomMbr, ELR, membersSet):
        if isinstance(sourceDomMbr, ModelConcept) and sourceDomMbr not in membersSet:
            membersSet.add(sourceDomMbr)
            for domMbrRel in val.modelXbrl.relationshipSet(XbrlConst.domainMember, ELR).fromModelObject(sourceDomMbr):
                #if domMbrRel.isUsable:
                addDomMbrs(domMbrRel.toModelObject, domMbrRel.consecutiveLinkrole, membersSet)
            
    
    for hasHypercubeArcrole in (XbrlConst.all, XbrlConst.notAll):
        hasHypercubeRelationships = val.modelXbrl.relationshipSet(hasHypercubeArcrole).fromModelObjects()
        for hasHcRels in hasHypercubeRelationships.values():
            for hasHcRel in hasHcRels:
                sourceConcept = hasHcRel.fromModelObject
                hcPrimaryItems.add(sourceConcept)
                # find associated primary items to source concept
                for domMbrRel in val.modelXbrl.relationshipSet(XbrlConst.domainMember).fromModelObject(sourceConcept):
                    if domMbrRel.consecutiveLinkrole == hasHcRel.linkrole: # only those related to this hc
                        addDomMbrs(domMbrRel.toModelObject, domMbrRel.consecutiveLinkrole, hcPrimaryItems)
                val.primaryItems.update(hcPrimaryItems)
                hc = hasHcRel.toModelObject
                if hasHypercubeArcrole == XbrlConst.all:
                    if not hasHcRel.isClosed and isExtension(val, hasHcRel):
                        val.modelXbrl.error("ESEF.3.4.2.openPositiveHypercubeInDefinitionLinkbase",
                            _("Hypercubes appearing as target of definition arc with http://xbrl.org/int/dim/arcrole/all arcrole MUST have xbrldt:closed attribute set to \"true\""
                              ": hypercube %(hypercube)s, linkrole %(linkrole)s, primary item %(primaryItem)s"),
                            modelObject=hasHcRel, hypercube=hc.qname, linkrole=hasHcRel.linkrole, primaryItem=sourceConcept.qname)
                elif hasHypercubeArcrole == XbrlConst.notAll:
                    if hasHcRel.isClosed and isExtension(val, hasHcRel):
                        val.modelXbrl.error("ESEF.3.4.2.closedNegativeHypercubeInDefinitionLinkbase",
                            _("Hypercubes appearing as target of definition arc with http://xbrl.org/int/dim/arcrole/notAll arcrole MUST have xbrldt:closed attribute set to \"false\""
                              ": hypercube %(hypercube)s, linkrole %(linkrole)s, primary item %(primaryItem)s"),
                            modelObject=hasHcRel, hypercube=hc.qname, linkrole=hasHcRel.linkrole, primaryItem=sourceConcept.qname)
                    if isExtension(val, hasHcRel):
                        val.modelXbrl.warning("ESEF.3.4.2.notAllArcroleUsedInDefinitionLinkbase",
                            _("Extension taxonomies SHOULD NOT define definition arcs with http://xbrl.org/int/dim/arcrole/notAll arcrole"
                              ": hypercube %(hypercube)s, linkrole %(linkrole)s, primary item %(primaryItem)s"),
                            modelObject=hasHcRel, hypercube=hc.qname, linkrole=hasHcRel.linkrole, primaryItem=sourceConcept.qname)
                for hcDimRel in val.modelXbrl.relationshipSet(XbrlConst.hypercubeDimension, hasHcRel.consecutiveLinkrole).fromModelObject(hc):
                    dim = hcDimRel.toModelObject
                    if isinstance(dim, ModelConcept):
                        for dimDomRel in val.modelXbrl.relationshipSet(XbrlConst.dimensionDomain, hcDimRel.consecutiveLinkrole).fromModelObject(dim):
                            dom = dimDomRel.toModelObject
                            if isinstance(dom, ModelConcept):
                                 addDomMbrs(dom, dimDomRel.consecutiveLinkrole, hcMembers)
                val.domainMembers.update(hcMembers)
                if hasHcRel.linkrole == LineItemsNotQualifiedLinkrole or hcMembers:
                    for hcPrimaryItem in hcPrimaryItems:
                        if not hcPrimaryItem.isAbstract:
                            elrPrimaryItems[hasHcRel.linkrole].add(hcPrimaryItem)
                hcPrimaryItems.clear()
                hcMembers.clear()
                                 
    # find primary items with other dimensions in 
    #for ELR, priItems in elrPrimaryItems.items():
    #    if ELR != LineItemsNotQualifiedLinkrole:
    #        # consider any pri item in not reported non-dimensionally
    #        i = set(hcPrimaryItem
    #                for hcPrimaryItem in (priItems & elrPrimaryItems.get(LineItemsNotQualifiedLinkrole, set()))
    #                if not any(not f.context.qnameDims for f in val.modelXbrl.factsByQname.get(hcPrimaryItem.qname,())))
    #        if i:
    #            val.modelXbrl.warning("ESEF.3.4.2.extensionTaxonomyLineItemIncorrectlyLinkedToNonDimensionallyQualifiedHypercube",
    #                _("Dimensional line item SHOULD NOT also be linked to \"not dimensionally qualified\" hypercube from %(linkrole)s, primary item %(qnames)s"),
    #                modelObject=i, linkrole=ELR, qnames=", ".join(sorted(str(c.qname) for c in i)))

    # reported pri items not in LineItemsNotQualifiedLinkrole
    i = set(concept
            for qn, facts in val.modelXbrl.factsByQname.items()
            if any(not f.context.qnameDims for f in facts if f.context is not None)
            for concept in (val.modelXbrl.qnameConcepts.get(qn),)
            if concept is not None and concept not in elrPrimaryItems.get(LineItemsNotQualifiedLinkrole, set()))
    if i:
        val.modelXbrl.warning("ESEF.3.4.2.lineItemNotLinkedToNonDimensionallyQualifiedHypercube",
            _("Dimensional line item reported non-dimensionally SHOULD be linked to \"not dimensionally qualified\" hypercube %(linkrole)s, primary item %(qnames)s"),
            modelObject=i, linkrole=LineItemsNotQualifiedLinkrole, qnames=", ".join(sorted(str(c.qname) for c in i)))
    # pri items in LineItemsNotQualifiedLinkrole which are not used in report non-dimensionally
    i = set(hcPrimaryItem
            for hcPrimaryItem in elrPrimaryItems.get(LineItemsNotQualifiedLinkrole, set())
            if not any(not f.context.qnameDims 
                       for f in val.modelXbrl.factsByQname.get(hcPrimaryItem.qname,())
                       if f.context is not None))
    if i:
        val.modelXbrl.warning("ESEF.3.4.2.lineItemUnnecessarilyLinkedToNonDimensionallyQualifiedHypercube",
            _("Dimensional line item not reported non-dimensionally has no need to be linked to \"not dimensionally qualified\" hypercube %(linkrole)s, primary item %(qnames)s"),
            modelObject=i, linkrole=LineItemsNotQualifiedLinkrole, qnames=", ".join(sorted(str(c.qname) for c in i)))

    # check ELRs with WiderNarrower relationships
    elrsContainingDimensionalRelationships = set(
        ELR
        for arcrole, ELR, linkqname, arcqname in val.modelXbrl.baseSets.keys()
        if arcrole == "XBRL-dimensions" and ELR is not None)
    anchorsInDimensionalELRs = defaultdict(list)
    for anchoringRel in val.modelXbrl.relationshipSet(XbrlConst.widerNarrower).modelRelationships:
        ELR = anchoringRel.linkrole
        fromObj = anchoringRel.fromModelObject
        toObj = anchoringRel.toModelObject
        if fromObj is not None and toObj is not None and fromObj.type is not None and toObj.type is not None:
            if not (isInEsefTaxonomy(val, fromObj) ^ isInEsefTaxonomy(val, toObj)):
                val.modelXbrl.error("ESEF.3.3.1.anchoringRelationshipBase",
                    _("Anchoring relationships MUST be from or to an ESEF element, from %(qname1)s to %(qname2)s"),
                    modelObject=(anchoringRel, fromObj, toObj), qname1=fromObj.qname, qname2=toObj.qname)
            if fromObj.type.isDomainItemType or toObj.type.isDomainItemType:
                val.modelXbrl.error("ESEF.3.3.1.anchoringRelationshipsForDomainMembersDefinedUsingWiderNarrowerArcrole",
                    _("Anchoring relationships MUST be from and to concepts, from %(qname1)s to %(qname2)s"),
                    modelObject=(anchoringRel, fromObj, toObj), qname1=fromObj.qname, qname2=toObj.qname)
            elif fromObj.isDimensionItem or toObj.isDimensionItem:
                val.modelXbrl.error("ESEF.3.3.1.anchoringRelationshipsForDimensionsDefinedUsingWiderNarrowerArcrole",
                    _("Anchoring relationships MUST be from and to concepts, from %(qname1)s to %(qname2)s"),
                    modelObject=(anchoringRel, fromObj, toObj), qname1=fromObj.qname, qname2=toObj.qname)
            else: # neither from nor to are dimensions or domain members
                if ELR in elrsContainingDimensionalRelationships:
                    anchorsInDimensionalELRs[ELR].append(anchoringRel)
    if anchorsInDimensionalELRs:
        for ELR, rels in anchorsInDimensionalELRs.items():
            val.modelXbrl.error("ESEF.3.3.2.anchoringRelationshipsForConceptsDefinedInElrContainingDimensionalRelationships",
                _("Anchoring relationships for concepts MUST be defined in a dedicated extended link role (or roles if needed to properly represent the relationships), e.g. http://{issuer default pattern for roles}/Anchoring. %(anchoringDimensionalELR)s"),
                modelObject=rels, anchoringDimensionalELR=ELR)
        
    # check base set dimension default overrides in extension taxonomies
    for modelLink in val.modelXbrl.baseSets[XbrlConst.dimensionDefault, None, None, None]:
        if isExtension(val, modelLink): 
            for linkChild in modelLink:
                if (isinstance(linkChild,(ModelObject,PrototypeObject)) and 
                    linkChild.get("{http://www.w3.org/1999/xlink}type") == "arc" and 
                    linkChild.get("{http://www.w3.org/1999/xlink}arcrole") == XbrlConst.dimensionDefault):
                    fromLabel = linkChild.get("{http://www.w3.org/1999/xlink}from")
                    for fromResource in modelLink.labeledResources[fromLabel]:
                        if not isExtension(val, fromResource):
                            val.modelXbrl.error("ESEF.3.4.3.extensionTaxonomyOverridesDefaultMembers",
                                _("The extension taxonomy MUST not modify (prohibit and/or override) default members assigned to dimensions by the ESEF taxonomy."),
                                modelObject=linkChild)
