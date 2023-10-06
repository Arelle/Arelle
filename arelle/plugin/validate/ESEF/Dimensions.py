"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, List, cast

import regex as re

from arelle import XbrlConst
from arelle.ModelDtsObject import ModelConcept, ModelLink
from arelle.ModelObject import ModelObject
from arelle.PrototypeDtsObject import PrototypeObject
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from .Util import isExtension, isInEsefTaxonomy

_: TypeGetText  # Handle gettext


def checkFilingDimensions(
    val: ValidateXbrl,
    defaultDimensionLinkroles: tuple[str, ...],
    lineItemsNotQualifiedLinkroles: tuple[str, ...],
) -> None:

    val.primaryItems = set() # concepts which are line items (should not also be dimension members
    val.domainMembers = set()  # concepts which are dimension domain members

    elrPrimaryItems = defaultdict(set)
    hcPrimaryItems: set[ModelConcept] = set()
    hcMembers: set[Any] = set()

    def addDomMbrs(sourceDomMbr: ModelConcept, ELR: str, membersSet: set[ModelConcept]) -> None:
        if isinstance(sourceDomMbr, ModelConcept) and sourceDomMbr not in membersSet:
            membersSet.add(sourceDomMbr)
            for domMbrRel in val.modelXbrl.relationshipSet(XbrlConst.domainMember, ELR).fromModelObject(sourceDomMbr):
                addDomMbrs(domMbrRel.toModelObject, domMbrRel.consecutiveLinkrole, membersSet)

    for hasHypercubeArcrole in (XbrlConst.all, XbrlConst.notAll):
        hasHypercubeRelationships = val.modelXbrl.relationshipSet(hasHypercubeArcrole).fromModelObjects()

        for hasHcRels in hasHypercubeRelationships.values():
            for hasHcRel in hasHcRels:
                sourceConcept: ModelConcept = hasHcRel.fromModelObject
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
                        val.modelXbrl.error("ESEF.3.4.2.notAllArcroleUsedInDefinitionLinkbase",
                            _("Extension taxonomies MUST NOT define definition arcs with http://xbrl.org/int/dim/arcrole/notAll arcrole"
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
                if hasHcRel.linkrole in lineItemsNotQualifiedLinkroles or hcMembers:
                    for hcPrimaryItem in hcPrimaryItems:
                        if not hcPrimaryItem.isAbstract:
                            elrPrimaryItems[hasHcRel.linkrole].add(hcPrimaryItem)
                            elrPrimaryItems["*"].add(hcPrimaryItem) # members of any ELR
                hcPrimaryItems.clear()
                hcMembers.clear()

    # reported pri items not in LineItemsNotQualifiedLinkrole
    nsExcl = val.authParam.get("lineItemsNotDimQualExclusionNsPattern")
    if nsExcl:
        nsExclPat = re.compile(nsExcl)
    i = set(concept
            for qn, facts in val.modelXbrl.factsByQname.items()
            if any(not f.context.qnameDims for f in facts if f.context is not None)
            for concept in (val.modelXbrl.qnameConcepts.get(qn),)
            if concept is not None and
               not any(concept in elrPrimaryItems.get(lr, set()) for lr in lineItemsNotQualifiedLinkroles) and
               concept not in elrPrimaryItems.get("*", set()) and
               (not nsExcl or not nsExclPat.match(cast(str, qn.namespaceURI))))
    if i:
        val.modelXbrl.error("ESEF.3.4.2.extensionTaxonomyLineItemNotLinkedToAnyHypercube",
            _("Line items that do not require any dimensional information to tag data MUST be linked to the dedicated \"Line items not dimensionally qualified\" hypercube in %(linkrole)s declared in esef_cor.xsd, primary item %(qnames)s"),
            modelObject=i, linkrole=lineItemsNotQualifiedLinkroles[0], qnames=", ".join(sorted(str(c.qname) for c in i)))

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
    for modelLink in cast(List[ModelLink], val.modelXbrl.baseSets[XbrlConst.dimensionDefault, None, None, None]):
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
                    if modelLink.role not in defaultDimensionLinkroles:
                        val.modelXbrl.error("ESEF.3.4.3.dimensionDefaultLinkrole",
                            _("Each dimension in an issuer specific extension taxonomy MUST be assigned to a default member in the ELR with role URI http://www.esma.europa.eu/xbrl/role/cor/ifrs-dim_role-990000, but linkrole used is %(linkrole)s."),
                            modelObject=linkChild, linkrole=modelLink.role)
