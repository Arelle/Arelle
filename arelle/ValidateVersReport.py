'''
Created on Nov 9, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import (ModelVersObject, XbrlConst, ValidateXbrl, ModelDocument)

conceptAttributeEventAttributes = {
        "conceptAttributeDelete": ("fromCustomAttribute",),
        "conceptAttributeAdd": ("toCustomAttribute",),
        "conceptAttributeChange": ("fromCustomAttribute","toCustomAttribute"),
        }

class ValidateVersReport():
    def __init__(self, testModelXbrl):
        self.testModelXbrl = testModelXbrl  # testcase or controlling validation object

        
    def validate(self, modelVersReport):
        self.modelVersReport = modelVersReport
        versReport = modelVersReport.modelDocument
        if not hasattr(versReport, "xmlDocument"): # not parsed
            return
        for DTSname in ("fromDTS", "toDTS"):
            DTSmodelXbrl = getattr(versReport, DTSname)
            if DTSmodelXbrl is None or DTSmodelXbrl.modelDocument is None:
                self.modelVersReport.error(
                    _("{0} is missing or not loaded").format(DTSname),
                    "err", "vere:invalidDTSIdentifier")
            else:
                # validate DTS
                ValidateXbrl.ValidateXbrl(DTSmodelXbrl).validate(DTSmodelXbrl)
                if len(DTSmodelXbrl.errors) > 0:
                    self.modelVersReport.error(
                        _("{0} {1} has errors: {2}").format(DTSname,
                            DTSmodelXbrl.modelDocument.basename, 
                            DTSmodelXbrl.errors), 
                        "err", "vere:invalidDTSIdentifier")
        # validate linkbases
        ValidateXbrl.ValidateXbrl(self.modelVersReport).validate(modelVersReport)

        versReportElt = versReport.xmlRootElement
        # check actions
        for assignmentRef in versReportElt.iterdescendants(tag="{http://xbrl.org/2010/versioning-base}assignmentRef"):
            ref = assignmentRef.get("ref")
            if ref not in versReport.idObjects or \
               not isinstance(versReport.idObjects[ref], ModelVersObject.ModelAssignment):
                    self.modelVersReport.error(
                        _("AssignmentRef {0} does not reference an assignment").format(ref), 
                        "err", "vere:invalidAssignmentRef")
                    
        # check namespace renames
        for NSrename in versReport.namespaceRenameFrom.values():
            if NSrename.fromURI not in versReport.fromDTS.namespaceDocs:
                self.modelVersReport.error(
                    _("NamespaceRename fromURI {0} does not reference a schema in fromDTS").format(
                    NSrename.fromURI), 
                    "err", "vere:invalidNamespaceMapping")
            if NSrename.toURI not in versReport.toDTS.namespaceDocs:
                self.modelVersReport.error(
                    _("NamespaceRename toURI {0} does not reference a schema in toDTS").format(
                    NSrename.toURI), 
                    "err", "vere:invalidNamespaceMapping")
                
        # check role changes
        for roleChange in versReport.roleChanges.values():
            if roleChange.fromURI not in versReport.fromDTS.roleTypes:
                self.modelVersReport.error(
                    _("RoleChange fromURI {0} does not reference a roleType in fromDTS").format(
                    roleChange.fromURI), 
                    "err", "vere:invalidRoleChange")
            if roleChange.toURI not in versReport.toDTS.roleTypes:
                self.modelVersReport.error(
                    _("RoleChange toURI {0} does not reference a roleType in toDTS").format(
                    roleChange.toURI), 
                    "err", "vere:invalidRoleChange")
                
        # check reportRefs
        # check actions
        for reportRef in versReportElt.iterdescendants(tag="{http://xbrl.org/2010/versioning-base}reportRef"):
            xlinkType = reportRef.get("{http://www.w3.org/1999/xlink}type")
            if xlinkType != "simple":
                self.modelVersReport.error(
                    _("ReportRef xlink:type {0} must be \"simple\"").format(xlinkType), 
                    "err", "vere:invalidXlinkType")
            # if existing it must be valid
            href = reportRef.get("{http://www.w3.org/1999/xlink}href")
            # TBD
            
            arcrole = reportRef.get("{http://www.w3.org/1999/xlink}arcrole")
            if arcrole is None:
                self.modelVersReport.error(
                    _("ReportRef xlink:arcrole is missing"), 
                    "err", "vere:missingXlinkArcrole")
            else:
                if arcrole != "http://xbrl.org/arcrole/2010/versioning/related-report":
                    self.modelVersReport.error(
                        _("ReportRef xlink:arcrole {0} is invalid").format(arcrole), 
                        "err", "vere:invalidXlinkArcrole")
            
        if versReport.fromDTS and versReport.toDTS:
            # check concept changes of concept basic
            for conceptChange in versReport.conceptBasicChanges:
                if conceptChange.name != "conceptAdd" and \
                   (conceptChange.fromConcept is None or \
                    conceptChange.fromConcept.qname not in versReport.fromDTS.qnameConcepts):
                    self.modelVersReport.error(
                        _("{0} fromConcept {1} does not reference a concept in fromDTS").format(
                        conceptChange.name, conceptChange.fromConceptQname), 
                        "err", "vercbe:invalidConceptReference")
                if conceptChange.name != "conceptDelete" and \
                   (conceptChange.toConcept is None or \
                    conceptChange.toConcept.qname not in versReport.toDTS.qnameConcepts):
                    self.modelVersReport.error(
                        _("{0} toConcept {1} does not reference a concept in toDTS").format(
                        conceptChange.name, conceptChange.toConceptQname), 
                        "err", "vercbe:invalidConceptReference")
                    
            # check concept changes of concept extended
            for conceptChange in versReport.conceptExtendedChanges:
                fromConcept = conceptChange.fromConcept
                toConcept = conceptChange.toConcept
                fromResource = conceptChange.fromResource
                toResource = conceptChange.toResource
                # fromConcept checks
                if not conceptChange.name.endswith("Add"):
                    if not fromConcept:
                        self.modelVersReport.error(
                            _("{0} {1} fromConcept {2} does not reference a concept in fromDTS").format(
                            conceptChange.actionId, conceptChange.name, conceptChange.fromConceptQname), 
                            "err", "vercbe:invalidConceptReference")
                    # tuple check
                    elif "Child" in conceptChange.name and \
                        not versReport.fromDTS.qnameConcepts[fromConcept.qname] \
                            .isTuple:
                        self.modelVersReport.error(
                            _("{0} {1} fromConcept {2} must be defined as a tuple").format(
                            conceptChange.actionId, conceptChange.name, conceptChange.fromConceptQname), 
                            "err", "vercbe:invalidConceptReference")
                    # resource check
                    elif "Label" in conceptChange.name:
                        if not fromResource:
                            self.modelVersReport.error(
                                _("{0} {1} fromResource {2} does not reference a resource in fromDTS").format(
                                conceptChange.actionId, conceptChange.name, conceptChange.fromResourceValue), 
                                "err", "vercee:invalidContentResourceIdentifier")
                        else:
                            relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.conceptLabel)
                            if relationship:
                                if relationship.qname != XbrlConst.qnLinkLabelArc or \
                                   relationship.parentQname != XbrlConst.qnLinkLabelLink or \
                                   fromResource.qname != XbrlConst.qnLinkLabel:
                                    self.modelVersReport.error(
                                        _("{0} {1} fromResource {2} for {3} in fromDTS does not have expected link, arc, or label elements").format(
                                        conceptChange.actionId, conceptChange.name, conceptChange.fromResourceValue, conceptChange.fromConceptQname), 
                                        "err", "vercee:invalidConceptLabelIdentifier")
                            else:
                                relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.elementLabel)
                                if relationship:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       fromResource.qname != XbrlConst.qnGenLabel:
                                        self.modelVersReport.error(
                                            _("{0} {1} fromResource {2} for {3} in fromDTS does not have expected link, arc, or label elements").format(
                                            conceptChange.actionId, conceptChange.name, conceptChange.fromResourceValue, conceptChange.fromConceptQname), 
                                            "err", "vercee:invalidConceptLabelIdentifier")
                                else:
                                    self.modelVersReport.error(
                                        _("{0} {1} fromResource {2} does not have a label relationship to {3} in fromDTS").format(
                                        conceptChange.actionId, conceptChange.name, conceptChange.fromResourceValue, conceptChange.fromConceptQname), 
                                        "err", "vercee:invalidContentResourceIdentifier")
                    elif "Reference" in conceptChange.name:
                        if not fromResource:
                            self.modelVersReport.error(
                                _("{0} {1} fromResource {2} does not reference a resource in fromDTS").format(
                                conceptChange.actionId, conceptChange.name, conceptChange.fromResourceValue), 
                                "err", "vercee:invalidContentResourceIdentifier")
                        else:
                            relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.conceptReference)
                            if relationship:
                                if relationship.qname != XbrlConst.qnLinkReferenceArc or \
                                   relationship.parentQname != XbrlConst.qnLinkReferenceLink or \
                                   fromResource.qname != XbrlConst.qnLinkReference:
                                    self.modelVersReport.error(
                                        _("{0} {1} fromResource {2} for {3} in fromDTS does not have expected link, arc, or label elements").format(
                                        conceptChange.actionId, conceptChange.name, conceptChange.fromResourceValue, conceptChange.fromConceptQname), 
                                        "err", "vercee:invalidConceptReferenceIdentifier")
                            else:
                                relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.elementReference)
                                if relationship:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       fromResource.qname != XbrlConst.qnGenReference:
                                        self.modelVersReport.error(
                                            _("{0} {1} fromResource {2} for {3} in fromDTS does not have expected link, arc, or label elements").format(
                                            conceptChange.actionId, conceptChange.name, conceptChange.fromResourceValue, conceptChange.fromConceptQname), 
                                            "err", "vercee:invalidConceptReferenceIdentifier")
                                else:
                                    self.modelVersReport.error(
                                        _("{0} {1} fromResource {2} does not have a reference relationship to {3} in fromDTS").format(
                                        conceptChange.actionId, conceptChange.name, conceptChange.fromResourceValue, conceptChange.fromConceptQname), 
                                        "err", "vercee:invalidContentResourceIdentifier")
                             
                # toConcept checks
                if not conceptChange.name.endswith("Delete"):
                    if not toConcept:
                        self.modelVersReport.error(
                            _("{0} {1} toConcept {2} does not reference a concept in toDTS").format(
                            conceptChange.actionId, conceptChange.name, conceptChange.toConceptQname), 
                            "err", "vercbe:invalidConceptReference")
                    # tuple check
                    elif "Child" in conceptChange.name and \
                        not versReport.toDTS.qnameConcepts[toConcept.qname] \
                            .isTuple:
                        self.modelVersReport.error(
                            _("{0} {1} toConcept {2} must be defined as a tuple").format(
                            conceptChange.actionId, conceptChange.name, conceptChange.toConceptQname), 
                            "err", "vercbe:invalidConceptReference")
                    # resource check
                    elif "Label" in conceptChange.name:
                        if not toResource:
                            self.modelVersReport.error(
                                _("{0} {1} toResource {2} does not reference a resource in toDTS").format(
                                conceptChange.actionId, conceptChange.name, conceptChange.toResourceValue), 
                                "err", "vercee:invalidContentResourceIdentifier")
                        else:
                            relationship = toConcept.relationshipToResource(toResource, XbrlConst.conceptLabel)
                            if relationship:
                                if relationship.qname != XbrlConst.qnLinkLabelArc or \
                                   relationship.parentQname != XbrlConst.qnLinkLabelLink or \
                                   toResource.qname != XbrlConst.qnLinkLabel:
                                    self.modelVersReport.error(
                                        _("{0} {1} toResource {2} for {3} in toDTS does not have expected link, arc, or label elements").format(
                                        conceptChange.actionId, conceptChange.name, conceptChange.toResourceValue, conceptChange.toConceptQname), 
                                        "err", "vercee:invalidConceptLabelIdentifier")
                            else:
                                relationship = toConcept.relationshipToResource(toResource, XbrlConst.elementLabel)
                                if relationship:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       toResource.qname != XbrlConst.qnGenLabel:
                                        self.modelVersReport.error(
                                            _("{0} {1} toResource {2} for {3} in toDTS does not have expected link, arc, or label elements").format(
                                            conceptChange.actionId, conceptChange.name, conceptChange.toResourceValue, conceptChange.toConceptQname), 
                                            "err", "vercee:invalidConceptLabelIdentifier")
                                else:
                                    self.modelVersReport.error(
                                        _("{0} {1} toResource {2} does not have a label relationship to {3} in toDTS").format(
                                        conceptChange.actionId, conceptChange.name, conceptChange.toResourceValue, conceptChange.toConceptQname), 
                                        "err", "vercee:invalidContentResourceIdentifier")
                    elif "Reference" in conceptChange.name:
                        if not toResource:
                            self.modelVersReport.error(
                                _("{0} {1} toResource {2} does not reference a resource in toDTS").format(
                                conceptChange.actionId, conceptChange.name, conceptChange.toResourceValue), 
                                "err", "vercee:invalidContentResourceIdentifier")
                        else:
                            relationship = toConcept.relationshipToResource(toResource, XbrlConst.conceptReference)
                            if relationship:
                                if relationship.qname != XbrlConst.qnLinkReferenceArc or \
                                   relationship.parentQname != XbrlConst.qnLinkReferenceLink or \
                                   toResource.qname != XbrlConst.qnLinkReference:
                                    self.modelVersReport.error(
                                        _("{0} {1} toResource {2} for {3} in toDTS does not have expected link, arc, or label elements").format(
                                        conceptChange.actionId, conceptChange.name, conceptChange.toResourceValue, conceptChange.toConceptQname), 
                                        "err", "vercee:invalidConceptReferenceIdentifier")
                            else:
                                relationship = toConcept.relationshipToResource(toResource, XbrlConst.elementReference)
                                if relationship:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       toResource.qname != XbrlConst.qnGenReference:
                                        self.modelVersReport.error(
                                            _("{0} {1} toResource {2} for {3} in toDTS does not have expected link, arc, or label elements").format(
                                            conceptChange.actionId, conceptChange.name, conceptChange.toResourceValue, conceptChange.toConceptQname), 
                                            "err", "vercee:invalidConceptReferenceIdentifier")
                                else:
                                    self.modelVersReport.error(
                                        _("{0} {1} toResource {2} does not have a reference relationship to {3} in toDTS").format(
                                        conceptChange.actionId, conceptChange.name, conceptChange.toResourceValue, conceptChange.toConceptQname), 
                                        "err", "vercee:invalidContentResourceIdentifier")
                        
                # check concept correspondence
                if fromConcept and toConcept:
                    if versReport.toDTSqname(fromConcept.qname) != toConcept.qname and \
                       versReport.equivalentConcepts.get(fromConcept.qname) != toConcept.qname and \
                       toConcept.qname not in versReport.relatedConcepts.get(fromConcept.qname,[]):
                        self.modelVersReport.error(
                            _("{0} {1} fromConcept {2} and toConcept {3} must be equivalent or related").format(
                            conceptChange.actionId, conceptChange.name, conceptChange.fromConceptQname, conceptChange.toConceptQname), 
                            "err", "vercee:invalidConceptCorrespondence")
    
                # custom attribute events
                if conceptChange.name.startswith("conceptAttribute"):
                    try:
                        for attr in conceptAttributeEventAttributes[conceptChange.name]:
                            customAttributeQname = conceptChange.customAttributeQname(attr)
                            if not customAttributeQname or customAttributeQname.namespaceURI is None:
                                self.modelVersReport.error(
                                    _("{0} {1} {2} {3} does not have a namespace").format(
                                    conceptChange.actionId, conceptChange.name, attr, customAttributeQname), 
                                    "err", "vercee:invalidAttributeChange")
                            elif customAttributeQname.namespaceURI in (XbrlConst.xbrli, XbrlConst.xsd):
                                self.modelVersReport.error(
                                    _("{0} {1} {2} {3} has an invalid namespace").format(
                                    conceptChange.actionId, conceptChange.name, attr, customAttributeQname), 
                                    "err", "vercee:illegalCustomAttributeEvent")
                    except KeyError:
                        self.modelVersReport.error(
                            _("{0} {1} event is not recognized").format(conceptChange.actionId, conceptChange.name), 
                            "info", "arelle:eventNotRecognized")
    
            # check relationship set changes
            for relSetChange in versReport.relationshipSetChanges:
                for relationshipSet, name in ((relSetChange.fromRelationshipSet, "fromRelationshipSet"),
                                              (relSetChange.toRelationshipSet, "toRelationshipSet")):
                    if relationshipSet:
                        relationshipSetValid = True
                        if relationshipSet.link and relationshipSet.link not in relationshipSet.dts.qnameConcepts:
                            self.modelVersReport.error(
                                _("{0} link {1} does not reference an element in its DTS").format(
                                relSetChange.name, name, relationshipSet.link), 
                                "err", "verrelse:invalidLinkElementReference")
                            relationshipSetValid = False
                        if relationshipSet.arc and relationshipSet.arc not in relationshipSet.dts.qnameConcepts:
                            self.modelVersReport.error(
                                _("{0} arc {1} does not reference an element in its DTS").format(
                                relSetChange.name, name, relationshipSet.link), 
                                "err", "verrelse:invalidArcElementReference")
                            relationshipSetValid = False
                        if relationshipSet.linkrole and not (XbrlConst.isStandardRole(relationshipSet.linkrole) or
                                                             relationshipSet.linkrole in relationshipSet.dts.roleTypes):
                            self.modelVersReport.error(
                                _("{0} linkrole {1} does not reference an linkrole in its DTS").format(
                                relSetChange.name, name, relationshipSet.linkrole), 
                                "err", "verrelse:invalidLinkrole")
                            relationshipSetValid = False
                        if relationshipSet.arcrole and not (XbrlConst.isStandardArcrole(relationshipSet.arcrole) or
                                                            relationshipSet.arcrole in relationshipSet.dts.arcroleTypes):
                            self.modelVersReport.error(
                                _("{0} arcrole {1} does not reference an arcrole in its DTS").format(
                                relSetChange.name, name, relationshipSet.linkrole), 
                                "err", "verrelse:invalidArcrole")
                            relationshipSetValid = False
                        for relationship in relationshipSet.relationships:
                            # fromConcept checks
                            if not relationship.fromConcept:
                                self.modelVersReport.error(
                                    _("{0} {1} relationship fromConcept {2} does not reference a concept in its DTS").format(
                                    relSetChange.name, name, relationship.fromName), 
                                    "err", "verrelse:invalidConceptReference")
                                relationshipSetValid = False
                            if relationship.toName and not relationship.toConcept:
                                self.modelVersReport.error(
                                    _("{0} {1} relationship toConcept {2} does not reference a concept in its DTS").format(
                                    relSetChange.name, name, relationship.toName), 
                                    "err", "verrelse:invalidConceptReference")
                                relationshipSetValid = False
                            if relationshipSetValid: # test that relations exist
                                if relationship.fromRelationship is None:
                                    if relationship.toName:
                                        self.modelVersReport.error(
                                            _("{0} {1} no relationship found from toConcept {2} to {3} in its DTS").format(
                                            relSetChange.name, name, relationship.fromName, relationship.toName), 
                                            "err", "verrelse:invalidRelationshipReference")
                                    else:
                                        self.modelVersReport.error(
                                            _("{0} {1} no relationship found from toConcept {2} in its DTS").format(
                                            relSetChange.name, name, relationship.fromName), 
                                            "err", "verrelse:invalidRelationshipReference")
                                    

                        
            
            '''
            # check instance aspect changes
            for iaChange in versReport.instanceAspectChanges:
                # validate related concepts
                for aspectName in ("{http://xbrl.org/2010/versioning-instance-aspects}concept", "{http://xbrl.org/2010/versioning-instance-aspects}member"):
                    for aspectElt in iaChange.iterdescendants(aspectName):
                        # check link attribute
                        link = aspectElement.get("link")
                        if link is not None:
                            iaChange.hrefToModelObject(link, dts)
            '''