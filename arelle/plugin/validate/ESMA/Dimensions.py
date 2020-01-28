'''
Created on June 6, 2018

Filer Guidelines: esma32-60-254_esef_reporting_manual.pdf


@author: Mark V Systems Limited
(c) Copyright 2018 Mark V Systems Limited, All rights reserved.
'''

from collections import defaultdict
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelObject import ModelObject
from arelle.PrototypeDtsObject import PrototypeObject
from arelle import XbrlConst
from .Const import WiderNarrower, DefaultDimensionLinkrole
from .Util import isExtension

def checkFilingDimensions(val):

    val.primaryItems = set() # concepts which are line items (should not also be dimension members)
    val.domainMembers = set() # concepts which are dimension domain members
    
    def addDomMbrs(sourceDomMbr, ELR, membersSet):
        if isinstance(sourceDomMbr, ModelConcept) and sourceDomMbr not in membersSet:
            membersSet.add(sourceDomMbr)
            for domMbrRel in val.modelXbrl.relationshipSet(XbrlConst.domainMember, ELR).fromModelObject(sourceDomMbr):
                addDomMbrs(domMbrRel.toModelObject, domMbrRel.targetRole, membersSet)
            
    
    for hasHypercubeArcrole in (XbrlConst.all, XbrlConst.notAll):
        hasHypercubeRelationships = val.modelXbrl.relationshipSet(hasHypercubeArcrole).fromModelObjects()
        for hasHcRels in hasHypercubeRelationships.values():
            for hasHcRel in hasHcRels:
                sourceConcept = hasHcRel.fromModelObject
                val.primaryItems.add(sourceConcept)
                # find associated primary items to source concept
                for domMbrRel in val.modelXbrl.relationshipSet(XbrlConst.domainMember).fromModelObject(sourceConcept):
                    if domMbrRel.targetRole == hasHcRel.linkrole: # only those related to this hc
                        addDomMbrs(domMbrRelfromModelObject, domMbrRel.linkrole, val.primaryItems)
                hc = hasHcRel.toModelObject
                if hasHypercubeArcrole == XbrlConst.all:
                    if not hasHcRel.isClosed and isExtension(val, hasHcRel):
                        val.modelXbrl.error("esma.3.4.2.openPositiveHypercubeInDefinitionLinkbase",
                            _("Hypercubes appearing as target of definition arc with http://xbrl.org/int/dim/arcrole/all arcrole MUST have xbrldt:closed attribute set to \"true\""
                              ": hypercube %(hypercube)s, linkrole %(linkrole)s, primary item %(primaryItem)s"),
                            modelObject=hasHcRel, hypercube=hc.qname, linkrole=hasHcRel.linkrole, primaryItem=sourceConcept.qname)
                elif hasHypercubeArcrole == XbrlConst.notAll:
                    if hasHcRel.isClosed and isExtension(val, hasHcRel):
                        val.modelXbrl.error("esma.3.4.2.closedNegativeHypercubeInDefinitionLinkbase",
                            _("Hypercubes appearing as target of definition arc with http://xbrl.org/int/dim/arcrole/notAll arcrole MUST have xbrldt:closed attribute set to \"false\""
                              ": hypercube %(hypercube)s, linkrole %(linkrole)s, primary item %(primaryItem)s"),
                            modelObject=hasHcRel, hypercube=hc.qname, linkrole=hasHcRel.linkrole, primaryItem=sourceConcept.qname)
                    if isExtension(val, hasHcRel):
                        val.modelXbrl.warning("esma.3.4.2.notAllArcroleUsedInDefinitionLinkbase",
                            _("Extension taxonomies SHOULD NOT define definition arcs with http://xbrl.org/int/dim/arcrole/notAll arcrole"
                              ": hypercube %(hypercube)s, linkrole %(linkrole)s, primary item %(primaryItem)s"),
                            modelObject=hasHcRel, hypercube=hc.qname, linkrole=hasHcRel.linkrole, primaryItem=sourceConcept.qname)
                for hcDimRel in val.modelXbrl.relationshipSet(XbrlConst.hypercubeDimension, hasHcRel.targetRole).fromModelObject(hc):
                    dim = hcDimRel.toModelObject
                    if isinstance(dim, ModelConcept):
                        for dimDomRel in val.modelXbrl.relationshipSet(XbrlConst.dimensionDomain, hcDimRel.targetRole).fromModelObject(dim):
                            dom = hcDimRel.toModelObject
                            if isinstance(dom, ModelConcept):
                                 addDomMbrs(dom, dimDomRel.targetRole, val.domainMembers)

    # check ELRs with WiderNarrower relationships
    elrsContainingDimensionalRelationships = set(
        ELR
        for arcrole, ELR, linkqname, arcqname in val.modelXbrl.baseSets.keys()
        if arcrole == "XBRL-dimensions" and ELR is not None)
    anchorsInDimensionalELRs = defaultdict(list)
    for ELR in elrsContainingDimensionalRelationships:
        for anchoringRel in val.modelXbrl.relationshipSet(WiderNarrower,ELR).modelRelationships:
            anchorsInDimensionalELRs[ELR].append(anchoringRel)
    if anchorsInDimensionalELRs:
        for ELR, rels in anchorsInDimensionalELRs.items():
            val.modelXbrl.error("esma.3.3.2.anchoringRelationshipsDefinedInElrContainingDimensionalRelationships",
                _("Anchoring relationships MUST NOT be defined in an extended link role applying XBRL Dimensions relationship. %(anchoringDimensionalELR)s"),
                modelObject=rels, anchoringDimensionalELR=ELR)
        
    # check dimension-defaults
    invalidDefaultELRs = defaultdict(list)
    for defaultMemberRel in val.modelXbrl.relationshipSet(XbrlConst.dimensionDefault).modelRelationships:
        if defaultMemberRel.linkrole != DefaultDimensionLinkrole and isExtension(val, defaultMemberRel):
            invalidDefaultELRs[defaultMemberRel.linkrole].append(defaultMemberRel)
    if invalidDefaultELRs:
        for invalidDefaultELR, rels in invalidDefaultELRs.items():
            val.modelXbrl.error("esma.3.4.3.extensionTaxonomyDimensionNotAssigedDefaultMemberInDedicatedPlaceholder",
                _("Each dimension in an issuer specific extension taxonomy MUST be assigned to a default member in the ELR with role URI http://www.esma.europa.eu/xbrl/role/ifrs-dim_role-990000 defined in esef_cor.xsd schema file. %(invalidDefaultELR)s"),
                modelObject=rels, invalidDefaultELR=invalidDefaultELR)
        
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
                            val.modelXbrl.error("esma.3.4.3.extensionTaxonomyOverridesDefaultMembers",
                                _("The extension taxonomy MUST not modify (prohibit and/or override) default members assigned to dimensions by the ESEF taxonomy."),
                                modelObject=linkChild)
