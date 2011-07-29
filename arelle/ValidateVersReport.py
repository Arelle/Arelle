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

    def __del__(self):
        self.__dict__.clear()   # dereference everything
        
    def validate(self, modelVersReport):
        self.modelVersReport = modelVersReport
        versReport = modelVersReport.modelDocument
        if not hasattr(versReport, "xmlDocument"): # not parsed
            return
        for DTSname in ("fromDTS", "toDTS"):
            DTSmodelXbrl = getattr(versReport, DTSname)
            if DTSmodelXbrl is None or DTSmodelXbrl.modelDocument is None:
                self.modelVersReport.error("vere:invalidDTSIdentifier",
                    "%(dts)s is missing or not loaded",
                    modelObject=self, dts=DTSname)
            else:
                # validate DTS
                ValidateXbrl.ValidateXbrl(DTSmodelXbrl).validate(DTSmodelXbrl)
                if len(DTSmodelXbrl.errors) > 0:
                    self.modelVersReport.error("vere:invalidDTSIdentifier",
                        "%(dts) has errors: %(error)s",DTSname,
                        modelObject=DTSmodelXbrl.modelDocument, dts=DTSname, error=DTSmodelXbrl.errors)
        # validate linkbases
        ValidateXbrl.ValidateXbrl(self.modelVersReport).validate(modelVersReport)

        versReportElt = versReport.xmlRootElement
        # check actions
        for assignmentRef in versReportElt.iterdescendants(tag="{http://xbrl.org/2010/versioning-base}assignmentRef"):
            ref = assignmentRef.get("ref")
            if ref not in versReport.idObjects or \
               not isinstance(versReport.idObjects[ref], ModelVersObject.ModelAssignment):
                    self.modelVersReport.error("vere:invalidAssignmentRef",
                        "AssignmentRef %(assignmentRef)s does not reference an assignment",
                        modelObject=assignmentRef, assignmentRef=ref)
                    
        # check namespace renames
        for NSrename in versReport.namespaceRenameFrom.values():
            if NSrename.fromURI not in versReport.fromDTS.namespaceDocs:
                self.modelVersReport.error("vere:invalidNamespaceMapping",
                    "NamespaceRename fromURI %(uri)s does not reference a schema in fromDTS",
                    modelObject=self, uri=NSrename.fromURI)
            if NSrename.toURI not in versReport.toDTS.namespaceDocs:
                self.modelVersReport.error("vere:invalidNamespaceMapping",
                    "NamespaceRename toURI %(uri)s does not reference a schema in toDTS",
                    modelObject=self, uri=NSrename.toURI)
                
        # check role changes
        for roleChange in versReport.roleChanges.values():
            if roleChange.fromURI not in versReport.fromDTS.roleTypes:
                self.modelVersReport.error("vere:invalidRoleChange",
                    "RoleChange fromURI %(uri)s does not reference a roleType in fromDTS",
                    modelObject=self, uri=roleChange.fromURI)
            if roleChange.toURI not in versReport.toDTS.roleTypes:
                self.modelVersReport.error("vere:invalidRoleChange",
                    "RoleChange toURI %(uri)s does not reference a roleType in toDTS",
                    modelObject=self, uri=roleChange.toURI)
                
        # check reportRefs
        # check actions
        for reportRef in versReportElt.iterdescendants(tag="{http://xbrl.org/2010/versioning-base}reportRef"):
            xlinkType = reportRef.get("{http://www.w3.org/1999/xlink}type")
            if xlinkType != "simple":
                self.modelVersReport.error("vere:invalidXlinkType",
                    "ReportRef xlink:type %(xlinkType)s must be \"simple\"",
                    modelObject=reportRef, xlinkType=xlinkType)
            # if existing it must be valid
            href = reportRef.get("{http://www.w3.org/1999/xlink}href")
            # TBD
            
            arcrole = reportRef.get("{http://www.w3.org/1999/xlink}arcrole")
            if arcrole is None:
                self.modelVersReport.error("vere:missingXlinkArcrole"
                    "ReportRef xlink:arcrole is missing",
                    modelObject=reportRef)
            else:
                if arcrole != "http://xbrl.org/arcrole/2010/versioning/related-report":
                    self.modelVersReport.error("vere:invalidXlinkArcrole",
                        "ReportRef xlink:arcrole %(arcrole)s is invalid",
                        modelObject=reportRef, arcrole=arcrole)
            
        if versReport.fromDTS and versReport.toDTS:
            # check concept changes of concept basic
            for conceptChange in versReport.conceptBasicChanges:
                if conceptChange.name != "conceptAdd" and \
                   (conceptChange.fromConcept is None or \
                    conceptChange.fromConcept.qname not in versReport.fromDTS.qnameConcepts):
                    self.modelVersReport.error("vercbe:invalidConceptReference",
                        "%(event)s fromConcept %(concept)s does not reference a concept in fromDTS",
                        modelObject=conceptChange, event=conceptChange.name, concept=conceptChange.fromConceptQname) 
                if conceptChange.name != "conceptDelete" and \
                   (conceptChange.toConcept is None or \
                    conceptChange.toConcept.qname not in versReport.toDTS.qnameConcepts):
                    self.modelVersReport.error("vercbe:invalidConceptReference"
                        "%(event)s toConcept %(concept)s does not reference a concept in toDTS",
                        modelObject=conceptChange, event=conceptChange.name, concept=conceptChange.toConceptQname) 
                    
            # check concept changes of concept extended
            for conceptChange in versReport.conceptExtendedChanges:
                fromConcept = conceptChange.fromConcept
                toConcept = conceptChange.toConcept
                fromResource = conceptChange.fromResource
                toResource = conceptChange.toResource
                # fromConcept checks
                if not conceptChange.name.endswith("Add"):
                    if not fromConcept:
                        self.modelVersReport.error("vercbe:invalidConceptReference",
                            "%(action)s %(event)s fromConcept %(concept)s does not reference a concept in fromDTS",
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, concept=conceptChange.fromConceptQname) 
                    # tuple check
                    elif "Child" in conceptChange.name and \
                        not versReport.fromDTS.qnameConcepts[fromConcept.qname] \
                            .isTuple:
                        self.modelVersReport.error("vercbe:invalidConceptReference",
                            "%(action)s %(event)s fromConcept %(concept)s must be defined as a tuple",
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, concept=conceptChange.fromConceptQname) 
                    # resource check
                    elif "Label" in conceptChange.name:
                        if not fromResource:
                            self.modelVersReport.error("vercee:invalidContentResourceIdentifier",
                                "%(action)s %(event)s fromResource %(resource)s does not reference a resource in fromDTS",
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.fromResourceValue) 
                        else:
                            relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.conceptLabel)
                            if relationship:
                                if relationship.qname != XbrlConst.qnLinkLabelArc or \
                                   relationship.parentQname != XbrlConst.qnLinkLabelLink or \
                                   fromResource.qname != XbrlConst.qnLinkLabel:
                                    self.modelVersReport.error("vercee:invalidConceptLabelIdentifier",
                                        "%(action)s %(event)s fromResource %(resource)s for %(concept)s in fromDTS does not have expected link, arc, or label elements",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                            else:
                                relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.elementLabel)
                                if relationship:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       fromResource.qname != XbrlConst.qnGenLabel:
                                        self.modelVersReport.error("vercee:invalidConceptLabelIdentifier",
                                            "%(action)s %(event)s fromResource %(resource)s for %(concept)s in fromDTS does not have expected link, arc, or label elements",
                                            modelObject=conceptChange, action=conceptChange.actionId,
                                            event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                                else:
                                    self.modelVersReport.error("vercee:invalidContentResourceIdentifier",
                                        "%(action)s %(event)s fromResource %(resource)s does not have a label relationship to {3} in fromDTS",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.fromResourceValue)
                    elif "Reference" in conceptChange.name:
                        if not fromResource:
                            self.modelVersReport.error("vercee:invalidContentResourceIdentifier",
                                "%(action)s %(event)s fromResource %(resource)s does not reference a resource in fromDTS",
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.fromResourceValue)
                        else:
                            relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.conceptReference)
                            if relationship:
                                if relationship.qname != XbrlConst.qnLinkReferenceArc or \
                                   relationship.parentQname != XbrlConst.qnLinkReferenceLink or \
                                   fromResource.qname != XbrlConst.qnLinkReference:
                                    self.modelVersReport.error("vercee:invalidConceptReferenceIdentifier",
                                        "%(action)s %(event)s fromResource %(resource)s for %(concept)s in fromDTS does not have expected link, arc, or label elements",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                            else:
                                relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.elementReference)
                                if relationship:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       fromResource.qname != XbrlConst.qnGenReference:
                                        self.modelVersReport.error("vercee:invalidConceptReferenceIdentifier",
                                            "%(action)s %(event)s fromResource %(resource)s for %(concept)s  in fromDTS does not have expected link, arc, or label elements",
                                            modelObject=conceptChange, action=conceptChange.actionId,
                                            event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                                else:
                                    self.modelVersReport.error("vercee:invalidContentResourceIdentifier",
                                        "%(action)s %(event)s fromResource %(resource)s does not have a reference relationship to %(concept)s in fromDTS",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                             
                # toConcept checks
                if not conceptChange.name.endswith("Delete"):
                    if not toConcept:
                        self.modelVersReport.error("vercbe:invalidConceptReference",
                            "%(action)s %(event)s toConcept %(concept)s does not reference a concept in toDTS",
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, concept=conceptChange.toConceptQname)
                    # tuple check
                    elif "Child" in conceptChange.name and \
                        not versReport.toDTS.qnameConcepts[toConcept.qname] \
                            .isTuple:
                        self.modelVersReport.error("vercbe:invalidConceptReference",
                            "%(action)s %(event)s toConcept %(concept)s must be defined as a tuple",
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, concept=conceptChange.toConceptQname)
                    # resource check
                    elif "Label" in conceptChange.name:
                        if not toResource:
                            self.modelVersReport.error("vercee:invalidContentResourceIdentifier",
                                "%(action)s %(event)s toResource %(resource)s for %(concept)s does not reference a resource in toDTS",
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                        else:
                            relationship = toConcept.relationshipToResource(toResource, XbrlConst.conceptLabel)
                            if relationship:
                                if relationship.qname != XbrlConst.qnLinkLabelArc or \
                                   relationship.parentQname != XbrlConst.qnLinkLabelLink or \
                                   toResource.qname != XbrlConst.qnLinkLabel:
                                    self.modelVersReport.error("vercee:invalidConceptLabelIdentifier",
                                        "%(action)s %(event)s toResource %(resource)s for %(concept)s in toDTS does not have expected link, arc, or label elements",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                            else:
                                relationship = toConcept.relationshipToResource(toResource, XbrlConst.elementLabel)
                                if relationship:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       toResource.qname != XbrlConst.qnGenLabel:
                                        self.modelVersReport.error("vercee:invalidConceptLabelIdentifier",
                                            "%(action)s %(event)s toResource %(resource)s for %(concept)s in toDTS does not have expected link, arc, or label elements",
                                            modelObject=conceptChange, action=conceptChange.actionId,
                                            event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                                else:
                                    self.modelVersReport.error("vercee:invalidContentResourceIdentifier",
                                        "%(action)s %(event)s toResource %(resource)s does not have a label relationship to %(concept)s in toDTS",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                    elif "Reference" in conceptChange.name:
                        if not toResource:
                            self.modelVersReport.error("vercee:invalidContentResourceIdentifier",
                                "%(action)s %(event)s toResource %(resource)s does not reference a resource in toDTS",
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.toResourceValue)
                        else:
                            relationship = toConcept.relationshipToResource(toResource, XbrlConst.conceptReference)
                            if relationship:
                                if relationship.qname != XbrlConst.qnLinkReferenceArc or \
                                   relationship.parentQname != XbrlConst.qnLinkReferenceLink or \
                                   toResource.qname != XbrlConst.qnLinkReference:
                                    self.modelVersReport.error("vercee:invalidConceptReferenceIdentifier",
                                        "%(action)s %(event)s toResource %(resource)s for %(concept)s in toDTS does not have expected link, arc, or label elements",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                            else:
                                relationship = toConcept.relationshipToResource(toResource, XbrlConst.elementReference)
                                if relationship:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       toResource.qname != XbrlConst.qnGenReference:
                                        self.modelVersReport.error("vercee:invalidConceptReferenceIdentifier",
                                            "%(action)s %(event)s toResource %(resource)s for %(concept)s in toDTS does not have expected link, arc, or label elements",
                                            modelObject=conceptChange, action=conceptChange.actionId,
                                            event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                                else:
                                    self.modelVersReport.error(
                                        "%(action)s %(event)s toResource %(resource)s does not have a reference relationship to %(concept)s in toDTS",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                        
                # check concept correspondence
                if fromConcept and toConcept:
                    if versReport.toDTSqname(fromConcept.qname) != toConcept.qname and \
                       versReport.equivalentConcepts.get(fromConcept.qname) != toConcept.qname and \
                       toConcept.qname not in versReport.relatedConcepts.get(fromConcept.qname,[]):
                        self.modelVersReport.error("vercee:invalidConceptCorrespondence",
                            "%(action)s %(event)s fromConcept %(conceptFrom)s and toConcept %(conceptTo)s must be equivalent or related",
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, conceptFrom=conceptChange.fromConceptQname, conceptTo=conceptChange.toConceptQname)
    
                # custom attribute events
                if conceptChange.name.startswith("conceptAttribute"):
                    try:
                        for attr in conceptAttributeEventAttributes[conceptChange.name]:
                            customAttributeQname = conceptChange.customAttributeQname(attr)
                            if not customAttributeQname or customAttributeQname.namespaceURI is None:
                                self.modelVersReport.error("vercee:invalidAttributeChange",
                                    "%(action)s %(event)s %(attr)s $(attrName)s does not have a namespace",
                                    modelObject=conceptChange, action=conceptChange.actionId,
                                    attr=attr, attrName=customAttributeQname)
                            elif customAttributeQname.namespaceURI in (XbrlConst.xbrli, XbrlConst.xsd):
                                self.modelVersReport.error("vercee:illegalCustomAttributeEvent",
                                    "%(action)s %(event)s %(attr)s $(attrName)s has an invalid namespace",
                                    modelObject=conceptChange, action=conceptChange.actionId, event=conceptChange.name,
                                    attr=attr, attrName=customAttributeQname)
                    except KeyError:
                        self.modelVersReport.info("arelle:eventNotRecognized",
                            "%(action)s %(event)s event is not recognized",
                            modelObject=conceptChange, action=conceptChange.actionId, event=conceptChange.name)
    
            # check relationship set changes
            for relSetChange in versReport.relationshipSetChanges:
                for relationshipSet, name in ((relSetChange.fromRelationshipSet, "fromRelationshipSet"),
                                              (relSetChange.toRelationshipSet, "toRelationshipSet")):
                    if relationshipSet:
                        relationshipSetValid = True
                        if relationshipSet.link and relationshipSet.link not in relationshipSet.dts.qnameConcepts:
                            self.modelVersReport.error("verrelse:invalidLinkElementReference",
                                "%(event)s %(relSet)s link %(link)s does not reference an element in its DTS",
                                modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                link=relationshipSet.link)
                            relationshipSetValid = False
                        if relationshipSet.arc and relationshipSet.arc not in relationshipSet.dts.qnameConcepts:
                            self.modelVersReport.error("verrelse:invalidArcElementReference",
                                "%(event)s %(relSet)s arc %(arc) does not reference an element in its DTS",
                                modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                arc=relationshipSet.arc)
                            relationshipSetValid = False
                        if relationshipSet.linkrole and not (XbrlConst.isStandardRole(relationshipSet.linkrole) or
                                                             relationshipSet.linkrole in relationshipSet.dts.roleTypes):
                            self.modelVersReport.error("verrelse:invalidLinkrole",
                                "%(event)s %(relSet)s linkrole %(linkrole)s does not reference an linkrole in its DTS",
                                modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                linkrole=relationshipSet.linkrole)
                            relationshipSetValid = False
                        if relationshipSet.arcrole and not (XbrlConst.isStandardArcrole(relationshipSet.arcrole) or
                                                            relationshipSet.arcrole in relationshipSet.dts.arcroleTypes):
                            self.modelVersReport.error("verrelse:invalidArcrole",
                                "%(event)s %(relSet)s arcrole %(arcrole)s does not reference an arcrole in its DTS",
                                modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                arcrole=relationshipSet.arcrole)
                            relationshipSetValid = False
                        for relationship in relationshipSet.relationships:
                            # fromConcept checks
                            if not relationship.fromConcept:
                                self.modelVersReport.error("verrelse:invalidConceptReference",
                                    "%(event)s %(relSet)s relationship fromConcept %(conceptFrom)s does not reference a concept in its DTS",
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    conceptFrom=relationship.fromName)
                                relationshipSetValid = False
                            if relationship.toName and not relationship.toConcept:
                                self.modelVersReport.error("verrelse:invalidConceptReference",
                                    "%(event)s %(relSet)s relationship toConcept %(conceptTo)s does not reference a concept in its DTS",
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    conceptTo=relationship.toName)
                                relationshipSetValid = False
                            if relationshipSetValid: # test that relations exist
                                if relationship.fromRelationship is None:
                                    if relationship.toName:
                                        self.modelVersReport.error("verrelse:invalidRelationshipReference",
                                            "%(event)s %(relSet)s no relationship found from fromConcept %(conceptFrom)s to toConcept %(conceptTo)s in its DTS",
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    conceptFrom=relationship.fromName, conceptTo=relationship.toName)
                                    else:
                                        self.modelVersReport.error("verrelse:invalidRelationshipReference",
                                            "%(event)s %(relSet)s no relationship found fromConcept %(conceptFrom)s in its DTS",
                                            modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                            conceptFrom=relationship.fromName)
                                    

                        
            
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