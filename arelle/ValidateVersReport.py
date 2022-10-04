'''
See COPYRIGHT.md for copyright information.
'''
from arelle import ModelVersObject, XbrlConst, ValidateXbrl, ModelDocument
from arelle.ModelValue import qname

conceptAttributeEventAttributes = {
        "conceptAttributeDelete": ("fromCustomAttribute",),
        "conceptAttributeAdd": ("toCustomAttribute",),
        "conceptAttributeChange": ("fromCustomAttribute","toCustomAttribute"),
        "conceptAttributeChange": ("fromCustomAttribute","toCustomAttribute"),
        "attributeDefinitionChange": ("fromCustomAttribute","toCustomAttribute"),
        }

schemaAttributeEventAttributes = {
        "conceptIDChange": "id",
        "conceptTypeChange": "type",
        "conceptSubstitutionGroupChange": "substitutionGroup",
        "conceptNillableChange": "nillable",
        "conceptAbstractChange": "abstract",
        "conceptBlockChange": "block",
        "conceptDefaultChange": "default",
        "conceptFixedChange": "fixed",
        "conceptFinalChange": "final"
        }

class ValidateVersReport():
    def __init__(self, testModelXbrl):
        self.testModelXbrl = testModelXbrl  # testcase or controlling validation object

    def close(self):
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
                    _("%(dts)s is missing or not loaded"),
                    modelObject=self, dts=DTSname)
            else:
                # validate DTS
                ValidateXbrl.ValidateXbrl(DTSmodelXbrl).validate(DTSmodelXbrl)
                if len(DTSmodelXbrl.errors) > 0:
                    self.modelVersReport.error("vere:invalidDTSIdentifier",
                        _("%(dts) has errors: %(error)s"),
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
                        _("AssignmentRef %(assignmentRef)s does not reference an assignment"),
                        modelObject=assignmentRef, assignmentRef=ref)

        # check namespace renames
        for NSrename in versReport.namespaceRenameFrom.values():
            if NSrename.fromURI not in versReport.fromDTS.namespaceDocs:
                self.modelVersReport.error("vere:invalidNamespaceMapping",
                    _("NamespaceRename fromURI %(uri)s does not reference a schema in fromDTS"),
                    modelObject=self, uri=NSrename.fromURI)
            if NSrename.toURI not in versReport.toDTS.namespaceDocs:
                self.modelVersReport.error("vere:invalidNamespaceMapping",
                    _("NamespaceRename toURI %(uri)s does not reference a schema in toDTS"),
                    modelObject=self, uri=NSrename.toURI)

        # check role changes
        for roleChange in versReport.roleChanges.values():
            if roleChange.fromURI not in versReport.fromDTS.roleTypes:
                self.modelVersReport.error("vere:invalidRoleChange",
                    _("RoleChange fromURI %(uri)s does not reference a roleType in fromDTS"),
                    modelObject=self, uri=roleChange.fromURI)
            if roleChange.toURI not in versReport.toDTS.roleTypes:
                self.modelVersReport.error("vere:invalidRoleChange",
                    _("RoleChange toURI %(uri)s does not reference a roleType in toDTS"),
                    modelObject=self, uri=roleChange.toURI)

        # check reportRefs
        # check actions
        for reportRef in versReportElt.iterdescendants(tag="{http://xbrl.org/2010/versioning-base}reportRef"):
            # if existing it must be valid
            href = reportRef.get("{http://www.w3.org/1999/xlink}href")
            # TBD

        if versReport.fromDTS and versReport.toDTS:
            # check concept changes of concept basic
            for conceptChange in versReport.conceptUseChanges:
                fromConceptQn = conceptChange.fromConceptQname
                toConceptQn = conceptChange.toConceptQname
                if (conceptChange.name != "conceptAdd" and
                    (fromConceptQn is None or fromConceptQn not in versReport.fromDTS.qnameConcepts)):
                    self.modelVersReport.error("vercue:invalidConceptReference",
                        _("%(event)s fromConcept %(concept)s does not reference a concept in fromDTS"),
                        modelObject=conceptChange, event=conceptChange.name, concept=conceptChange.fromConceptQname)
                if (conceptChange.name != "conceptDelete" and
                    (toConceptQn is None or toConceptQn not in versReport.toDTS.qnameConcepts)):
                    self.modelVersReport.error("vercue:invalidConceptReference",
                        _("%(event)s toConcept %(concept)s does not reference a concept in toDTS"),
                        modelObject=conceptChange, event=conceptChange.name, concept=conceptChange.toConceptQname)
                if (conceptChange.name == "conceptAdd" and toConceptQn is not None and
                    conceptChange.isPhysical ^
                    (qname(versReport.namespaceRenameTo.get(toConceptQn.namespaceURI, toConceptQn.namespaceURI),
                           toConceptQn.localName) not in versReport.fromDTS.qnameConcepts)):
                    self.modelVersReport.error("vercue:inconsistentPhysicalAttribute",
                        _("%(event)s toConcept %(concept)s physical attribute conflicts with presence in fromDTS"),
                        modelObject=conceptChange, event=conceptChange.name, concept=conceptChange.toConceptQname)
                if (conceptChange.name == "conceptDelete" and toConceptQn is not None and
                    conceptChange.isPhysical ^
                    (qname(versReport.namespaceRenameFrom.get(fromConceptQn.namespaceURI, fromConceptQn.namespaceURI),
                           fromConceptQn.localName) in versReport.toDTS.qnameConcepts)):
                    self.modelVersReport.error("vercue:inconsistentPhysicalAttribute",
                        _("%(event)s toConcept %(concept)s physical attribute conflicts with presence in toDTS"),
                        modelObject=conceptChange, event=conceptChange.name, concept=conceptChange.toConceptQname)

            # check concept changes of concept extended
            equivalentAttributes = {}
            for conceptChange in versReport.conceptDetailsChanges:
                fromConcept = conceptChange.fromConcept
                toConcept = conceptChange.toConcept
                fromResource = conceptChange.fromResource
                toResource = conceptChange.toResource
                # fromConcept checks
                if not conceptChange.name.endswith("Add"):
                    if not fromConcept is not None:
                        self.modelVersReport.error("vercue:invalidConceptReference",
                            _("%(action)s %(event)s fromConcept %(concept)s does not reference a concept in fromDTS"),
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, concept=conceptChange.fromConceptQname)
                    # tuple check
                    elif _("Child") in conceptChange.name and \
                        not versReport.fromDTS.qnameConcepts[fromConcept.qname] \
                            .isTuple:
                        self.modelVersReport.error("vercue:invalidConceptReference",
                            _("%(action)s %(event)s fromConcept %(concept)s must be defined as a tuple"),
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, concept=conceptChange.fromConceptQname)
                    # resource check
                    elif "Label" in conceptChange.name:
                        if fromResource is None:
                            self.modelVersReport.error("vercde:invalidResourceIdentifier",
                                _("%(action)s %(event)s fromResource %(resource)s does not reference a resource in fromDTS"),
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.fromResourceValue)
                        else:
                            relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.conceptLabel)
                            if relationship is not None:
                                if (relationship.qname != XbrlConst.qnLinkLabelArc or
                                    relationship.parentQname != XbrlConst.qnLinkLabelLink or
                                    fromResource.qname != XbrlConst.qnLinkLabel):
                                    self.modelVersReport.error("vercde:invalidConceptLabelIdentifier",
                                        _("%(action)s %(event)s fromResource %(resource)s for %(concept)s in fromDTS does not have expected link, arc, or label elements"),
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                            else:
                                relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.elementLabel)
                                if relationship is not None:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       fromResource.qname != XbrlConst.qnGenLabel:
                                        self.modelVersReport.error("vercde:invalidConceptLabelIdentifier",
                                            _("%(action)s %(event)s fromResource %(resource)s for %(concept)s in fromDTS does not have expected link, arc, or label elements"),
                                            modelObject=conceptChange, action=conceptChange.actionId,
                                            event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                                else:
                                    self.modelVersReport.error("vercde:invalidResourceIdentifier",
                                        _("%(action)s %(event)s fromResource %(resource)s does not have a label relationship to {3} in fromDTS"),
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.fromResourceValue)
                    elif "Reference" in conceptChange.name:
                        if fromResource is None:
                            self.modelVersReport.error("vercde:invalidResourceIdentifier",
                                _("%(action)s %(event)s fromResource %(resource)s does not reference a resource in fromDTS"),
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.fromResourceValue)
                        else:
                            relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.conceptReference)
                            if relationship is not None:
                                if relationship.qname != XbrlConst.qnLinkReferenceArc or \
                                   relationship.parentQname != XbrlConst.qnLinkReferenceLink or \
                                   fromResource.qname != XbrlConst.qnLinkReference:
                                    self.modelVersReport.error("vercde:invalidConceptReferenceIdentifier",
                                        _("%(action)s %(event)s fromResource %(resource)s for %(concept)s in fromDTS does not have expected link, arc, or label elements"),
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                            else:
                                relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.elementReference)
                                if relationship is not None:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       fromResource.qname != XbrlConst.qnGenReference:
                                        self.modelVersReport.error("vercde:invalidConceptReferenceIdentifier",
                                            _("%(action)s %(event)s fromResource %(resource)s for %(concept)s  in fromDTS does not have expected link, arc, or label elements"),
                                            modelObject=conceptChange, action=conceptChange.actionId,
                                            event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                                else:
                                    self.modelVersReport.error("vercde:invalidResourceIdentifier",
                                        _("%(action)s %(event)s fromResource %(resource)s does not have a reference relationship to %(concept)s in fromDTS"),
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)

                # toConcept checks
                if not conceptChange.name.endswith("Delete"):
                    if not toConcept is not None:
                        self.modelVersReport.error("vercue:invalidConceptReference",
                            _("%(action)s %(event)s toConcept %(concept)s does not reference a concept in toDTS"),
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, concept=conceptChange.toConceptQname)
                    # tuple check
                    elif "Child" in conceptChange.name and \
                        not versReport.toDTS.qnameConcepts[toConcept.qname] \
                            .isTuple:
                        self.modelVersReport.error("vercue:invalidConceptReference",
                            _("%(action)s %(event)s toConcept %(concept)s must be defined as a tuple"),
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, concept=conceptChange.toConceptQname)
                    # resource check
                    elif "Label" in conceptChange.name:
                        if toResource is None:
                            self.modelVersReport.error("vercde:invalidResourceIdentifier",
                                _("%(action)s %(event)s toResource %(resource)s for %(concept)s does not reference a resource in toDTS"),
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                        elif toResource.qname not in (XbrlConst.qnLinkLabel, XbrlConst.qnGenLabel):
                            self.modelVersReport.error("vercde:invalidConceptLabelIdentifier",
                                _("%(action)s %(event)s toResource %(resource)s is not a label in toDTS"),
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                        else:
                            relationship = toConcept.relationshipToResource(toResource, XbrlConst.conceptLabel)
                            if relationship is not None:
                                if relationship.qname != XbrlConst.qnLinkLabelArc or \
                                   relationship.parentQname != XbrlConst.qnLinkLabelLink or \
                                   toResource.qname != XbrlConst.qnLinkLabel:
                                    self.modelVersReport.error("vercde:invalidConceptLabelIdentifier",
                                        _("%(action)s %(event)s toResource %(resource)s for %(concept)s in toDTS does not have expected link, arc, or label elements"),
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                            else:
                                relationship = toConcept.relationshipToResource(toResource, XbrlConst.elementLabel)
                                if relationship is not None:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       toResource.qname != XbrlConst.qnGenLabel:
                                        self.modelVersReport.error("vercde:invalidConceptLabelIdentifier",
                                            _("%(action)s %(event)s toResource %(resource)s for %(concept)s in toDTS does not have expected link, arc, or label elements"),
                                            modelObject=conceptChange, action=conceptChange.actionId,
                                            event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                                else:
                                    self.modelVersReport.error("vercde:invalidConceptResourceIdentifier",
                                        _("%(action)s %(event)s toResource %(resource)s does not have a label relationship to %(concept)s in toDTS"),
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                    elif "Reference" in conceptChange.name:
                        if toResource is None:
                            self.modelVersReport.error("vercde:invalidResourceIdentifier",
                                _("%(action)s %(event)s toResource %(resource)s does not reference a resource in toDTS"),
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.toResourceValue)
                        elif toResource.qname not in (XbrlConst.qnLinkReference, XbrlConst.qnGenReference):
                            self.modelVersReport.error("vercde:invalidConceptReferenceIdentifier",
                                _("%(action)s %(event)s toResource %(resource)s is not a reference in toDTS"),
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                        else:
                            relationship = toConcept.relationshipToResource(toResource, XbrlConst.conceptReference)
                            if relationship is not None:
                                if relationship.qname != XbrlConst.qnLinkReferenceArc or \
                                   relationship.parentQname != XbrlConst.qnLinkReferenceLink or \
                                   toResource.qname != XbrlConst.qnLinkReference:
                                    self.modelVersReport.error("vercde:invalidConceptReferenceIdentifier",
                                        _("%(action)s %(event)s toResource %(resource)s for %(concept)s in toDTS does not have expected link, arc, or label elements"),
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                            else:
                                relationship = toConcept.relationshipToResource(toResource, XbrlConst.elementReference)
                                if relationship is not None:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       toResource.qname != XbrlConst.qnGenReference:
                                        self.modelVersReport.error("vercde:invalidConceptReferenceIdentifier",
                                            _("%(action)s %(event)s toResource %(resource)s for %(concept)s in toDTS does not have expected link, arc, or label elements"),
                                            modelObject=conceptChange, action=conceptChange.actionId,
                                            event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                                else:
                                    self.modelVersReport.error("vercde:invalidConceptResourceIdentifier",
                                        _("%(action)s %(event)s toResource %(resource)s does not have a reference relationship to %(concept)s in toDTS"),
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)

                # check concept correspondence
                if fromConcept is not None and toConcept is not None:
                    if (versReport.toDTSqname(fromConcept.qname) != toConcept.qname and
                        versReport.equivalentConcepts.get(fromConcept.qname) != toConcept.qname and
                        toConcept.qname not in versReport.relatedConcepts.get(fromConcept.qname,[])):
                        self.modelVersReport.error("vercde:invalidConceptCorrespondence",
                            _("%(action)s %(event)s fromConcept %(conceptFrom)s and toConcept %(conceptTo)s must be equivalent or related"),
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, conceptFrom=conceptChange.fromConceptQname, conceptTo=conceptChange.toConceptQname)

                # custom attribute events
                if conceptChange.name.startswith("conceptAttribute") or conceptChange.name == "attributeDefinitionChange":
                    try:
                        for attr in conceptAttributeEventAttributes[conceptChange.name]:
                            customAttributeQname = conceptChange.customAttributeQname(attr)
                            if not customAttributeQname:
                                self.modelVersReport.info("arelle:invalidAttributeChange",
                                    _("%(action)s %(event)s %(attr)s %(attrName)s does not have a name"),
                                    modelObject=conceptChange, action=conceptChange.actionId,
                                    attr=attr, attrName=customAttributeQname)
                            elif customAttributeQname.namespaceURI in (None, XbrlConst.xbrli, XbrlConst.xsd):
                                self.modelVersReport.error("vercde:illegalCustomAttributeEvent",
                                    _("%(action)s %(event)s %(attr)s %(attrName)s has an invalid namespace"),
                                    modelObject=conceptChange, action=conceptChange.actionId, event=conceptChange.name,
                                    attr=attr, attrName=customAttributeQname)
                    except KeyError:
                        self.modelVersReport.info("arelle:eventNotRecognized",
                            _("%(action)s %(event)s event is not recognized"),
                            modelObject=conceptChange, action=conceptChange.actionId, event=conceptChange.name)

                if conceptChange.name == "attributeDefinitionChange":
                    fromAttr = conceptChange.customAttributeQname("fromCustomAttribute")
                    toAttr = conceptChange.customAttributeQname("toCustomAttribute")
                    equivalentAttributes[fromAttr] = toAttr
                    equivalentAttributes[toAttr] = fromAttr

                # check item concept identifiers
                if conceptChange.name in ("conceptPeriodTypeChange", "conceptPeriodTypeChange"):
                    for concept in (fromConcept, toConcept):
                        if concept is not None and not concept.isItem:
                            self.modelVersReport.error("vercde:invalidItemConceptIdentifier",
                                _("%(action)s %(event)s concept %(concept)s does not reference an item concept."),
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, concept=concept.qname)

                # check tuple concept identifiers
                if conceptChange.name in ("tupleContentModelChange", ):
                    for concept in (fromConcept, toConcept):
                        if concept is not None and not concept.isItem:
                            self.modelVersReport.error("vercde:invalidTupleConceptIdentifier",
                                _("%(action)s %(event)s concept %(concept)s does not reference a tuple concept."),
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, concept=concept.qname)

                if conceptChange.name in schemaAttributeEventAttributes:
                    attr = schemaAttributeEventAttributes[conceptChange.name]
                    if (fromConcept is not None and not fromConcept.get(attr) and
                        toConcept is not None and not toConcept.get(attr)):
                            self.modelVersReport.error("vercde:illegalSchemaAttributeChangeEvent",
                                _("%(action)s %(event)s neither concepts have a %(attribute)s attribute: %(fromConcept)s, %(toConcept)s."),
                                modelObject=conceptChange, action=conceptChange.actionId, attribute=attr,
                                event=conceptChange.name, fromConcept=fromConcept.qname, toConcept=toConcept.qname)

            # check concept changes for equivalent attributes
            for conceptChange in versReport.conceptDetailsChanges:
                if conceptChange.name == "conceptAttributeChange":
                    fromAttr = conceptChange.customAttributeQname("fromCustomAttribute")
                    toAttr = conceptChange.customAttributeQname("toCustomAttribute")
                    if (equivalentAttributes.get(fromAttr) != toAttr and
                        (fromAttr.localName != toAttr.localName or
                         (fromAttr.namespaceURI != toAttr.namespaceURI and
                          versReport.namespaceRenameFrom.get(fromAttr.namespaceURI, fromAttr.namespaceURI) != toAttr.namespaceURI))):
                        self.modelVersReport.error("vercde:invalidAttributeCorrespondence",
                            _("%(action)s %(event)s has non-equivalent attributes %(fromQname)s and %(toQname)s"),
                            modelObject=conceptChange, action=conceptChange.actionId, event=conceptChange.name,
                            fromQname=fromAttr, toQname=toAttr)
            del equivalentAttributes # dereference

            # check relationship set changes
            for relSetChange in versReport.relationshipSetChanges:
                for relationshipSet, name in ((relSetChange.fromRelationshipSet, "fromRelationshipSet"),
                                              (relSetChange.toRelationshipSet, "toRelationshipSet")):
                    if relationshipSet is not None:
                        dts = relationshipSet.dts
                        relationshipSetValid = True
                        if relationshipSet.link:
                            if (relationshipSet.link not in dts.qnameConcepts or
                                (dts.qnameConcepts[relationshipSet.link].type is not None and
                                 not dts.qnameConcepts[relationshipSet.link].type.isDerivedFrom(XbrlConst.qnXlExtendedType))):
                                self.modelVersReport.error("verrelse:invalidLinkElementReferenceEvent",
                                    _("%(event)s %(relSet)s link %(link)s does not reference an element in its DTS"),
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    link=relationshipSet.link)
                                relationshipSetValid = False
                        if relationshipSet.arc:
                            if (relationshipSet.arc not in dts.qnameConcepts or
                                (dts.qnameConcepts[relationshipSet.arc].type is not None and
                                 not dts.qnameConcepts[relationshipSet.arc].type.isDerivedFrom(XbrlConst.qnXlArcType))):
                                self.modelVersReport.error("verrelse:invalidArcElementReferenceEvent",
                                    _("%(event)s %(relSet)s arc %(arc) does not reference an element in its DTS"),
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    arc=relationshipSet.arc)
                                relationshipSetValid = False
                        if relationshipSet.linkrole:
                            if not (XbrlConst.isStandardRole(relationshipSet.linkrole) or
                                    relationshipSet.linkrole in relationshipSet.dts.roleTypes):
                                self.modelVersReport.error("verrelse:invalidLinkrole",
                                    _("%(event)s %(relSet)s linkrole %(linkrole)s does not reference an linkrole in its DTS"),
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    linkrole=relationshipSet.linkrole)
                                relationshipSetValid = False
                            elif not any(linkrole == relationshipSet.linkrole
                                         for arcrole, linkrole, linkqname, arcqname in dts.baseSets.keys()):
                                self.modelVersReport.error("verrelse:invalidLinkrole",
                                    _("%(event)s %(relSet)s linkrole %(linkrole)s is not used in its DTS"),
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    linkrole=relationshipSet.linkrole)
                                relationshipSetValid = False
                        if relationshipSet.arcrole:
                            if not (XbrlConst.isStandardArcrole(relationshipSet.arcrole) or
                                    relationshipSet.arcrole in relationshipSet.dts.arcroleTypes):
                                self.modelVersReport.error("verrelse:invalidArcrole",
                                    _("%(event)s %(relSet)s arcrole %(arcrole)s does not reference an arcrole in its DTS"),
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    arcrole=relationshipSet.arcrole)
                                relationshipSetValid = False
                            elif not any(arcrole == relationshipSet.arcrole
                                         for arcrole, linkrole, linkqname, arcqname in dts.baseSets.keys()):
                                self.modelVersReport.error("verrelse:invalidArcrole",
                                    _("%(event)s %(relSet)s arcrole %(arcrole)s is not used in its DTS"),
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    arcrole=relationshipSet.arcrole)
                                relationshipSetValid = False
                        for relationship in relationshipSet.relationships:
                            # fromConcept checks
                            if relationship.fromConcept is None:
                                self.modelVersReport.error("vercue:invalidConceptReference",
                                    _("%(event)s %(relSet)s relationship fromConcept %(conceptFrom)s does not reference a concept in its DTS"),
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    conceptFrom=relationship.fromName)
                                relationshipSetValid = False
                            if relationship.toName and relationship.toConcept is None:
                                self.modelVersReport.error("vercue:invalidConceptReference",
                                    _("%(event)s %(relSet)s relationship toConcept %(conceptTo)s does not reference a concept in its DTS"),
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    conceptTo=relationship.toName)
                                relationshipSetValid = False
                            if relationshipSetValid: # test that relations exist
                                if relationship.fromRelationship is None:
                                    if relationship.toName:
                                        self.modelVersReport.error("verrelse:invalidRelationshipReference",
                                            _("%(event)s %(relSet)s no relationship found from fromConcept %(conceptFrom)s to toConcept %(conceptTo)s in its DTS"),
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    conceptFrom=relationship.fromName, conceptTo=relationship.toName)
                                    else:
                                        self.modelVersReport.error("verrelse:invalidRelationshipReference",
                                            _("%(event)s %(relSet)s no relationship found fromConcept %(conceptFrom)s in its DTS"),
                                            modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                            conceptFrom=relationship.fromName)




            # check instance aspect changes
            for iaChange in versReport.instanceAspectChanges:
                for instAspects in (iaChange.fromAspects, iaChange.toAspects):
                    if instAspects is not None and instAspects.aspects:
                        dimAspectElts = {}
                        for aspect in instAspects.aspects:
                            dts = aspect.modelAspects.dts
                            if (aspect.localName in ("explicitDimension", "typedDimension") and aspect.concept is None):
                                self.modelVersReport.error("vercue:invalidConceptReference",
                                    _("%(event)s dimension %(dimension)s is not a concept in its DTS"),
                                    modelObject=aspect, event=iaChange.name, dimension=aspect.conceptName)
                            elif aspect.localName == "explicitDimension":
                                dimConcept = aspect.concept
                                if not dimConcept.isExplicitDimension:
                                    self.modelVersReport.error("verdime:invalidExplicitDimensionIdentifier",
                                        _("%(event)s dimension %(dimension)s is not an explicit dimension in its DTS"),
                                        modelObject=aspect, event=iaChange.name, dimension=aspect.conceptName)
                                if dimConcept in dimAspectElts:
                                    self.modelVersReport.error("verdime:duplicateExplicitDimensionAspect",
                                        _("%(event)s dimension %(dimension)s is duplicated in a single explicitDimension element"),
                                        modelObject=(aspect, dimAspectElts[dimConcept]), event=iaChange.name, dimension=aspect.conceptName)
                                else:
                                    dimAspectElts[dimConcept] = aspect
                            elif aspect.localName == "typedDimension":
                                dimConcept = aspect.concept
                                if not dimConcept.isTypedDimension:
                                    self.modelVersReport.error("verdime:invalidTypedDimensionIdentifier",
                                        _("%(event)s dimension %(dimension)s is not a typed dimension in its DTS"),
                                        modelObject=aspect, event=iaChange.name, dimension=aspect.conceptName)
                                if dimConcept in dimAspectElts:
                                    self.modelVersReport.error("verdime:duplicateTypedDimensionAspect",
                                        _("%(event)s dimension %(dimension)s is duplicated in a single explicitDimension element"),
                                        modelObject=(aspect, dimAspectElts[dimConcept]), event=iaChange.name, dimension=aspect.conceptName)
                                else:
                                    dimAspectElts[dimConcept] = aspect
                            if aspect.localName in ("explicitDimension", "concepts"):
                                for relatedConcept in aspect.relatedConcepts:
                                    conceptMdlObj = relatedConcept.concept
                                    if conceptMdlObj is None or not conceptMdlObj.isItem:
                                        self.modelVersReport.error("vercue:invalidConceptReference",
                                            _("%(event)s concept %(concept)s is not an item in its DTS"),
                                            modelObject=aspect, event=iaChange.name, concept=relatedConcept.conceptName)
                                    if relatedConcept.arcrole is not None:
                                        if (not XbrlConst.isStandardArcrole(relatedConcept.arcrole) and
                                            relatedConcept.arcrole not in dts.arcroleTypes):
                                            self.modelVersReport.error("verdime:invalidURI",
                                                _("%(event)s arcrole %(arcrole)s is not defined in its DTS"),
                                                modelObject=aspect, event=iaChange.name, arcrole=relatedConcept.arcrole)
                                        elif not any(arcrole == relatedConcept.arcrole
                                                     for arcrole, linkrole, linkqname, arcqname in dts.baseSets.keys()):
                                            self.modelVersReport.error("verdime:invalidURI",
                                                _("%(event)s arcrole %(arcrole)s is not used in its DTS"),
                                                modelObject=aspect, event=iaChange.name, linkrole=relatedConcept.arcrole)
                                    if relatedConcept.linkrole is not None:
                                        if (relatedConcept.linkrole != "http://www.xbrl.org/2003/role/link" and
                                            relatedConcept.linkrole not in dts.roleTypes):
                                            self.modelVersReport.error("verdime:invalidURI",
                                                _("%(event)s linkrole %(linkrole)s is not defined in its DTS"),
                                                modelObject=aspect, event=iaChange.name, linkrole=relatedConcept.linkrole)
                                        elif not any(linkrole == relatedConcept.linkrole
                                                     for arcrole, linkrole, linkqname, arcqname in dts.baseSets.keys()):
                                            self.modelVersReport.error("verdime:invalidURI",
                                                _("%(event)s linkrole %(linkrole)s is not used in its DTS"),
                                                modelObject=aspect, event=iaChange.name, linkrole=relatedConcept.linkrole)
                                    if (relatedConcept.arc is not None and
                                        (relatedConcept.arc not in dts.qnameConcepts or
                                         (dts.qnameConcepts[relatedConcept.arc].type is not None and
                                          not dts.qnameConcepts[relatedConcept.arc].type.isDerivedFrom(XbrlConst.qnXlArcType)))):
                                        self.modelVersReport.error("verdime:invalidArcElement",
                                            _("%(event)s arc %(arc)s is not defined as an arc in its DTS"),
                                            modelObject=aspect, event=iaChange.name, arc=relatedConcept.arc)
                                    if (relatedConcept.link is not None and
                                        (relatedConcept.link not in dts.qnameConcepts or
                                         (dts.qnameConcepts[relatedConcept.link].type is not None and
                                          not dts.qnameConcepts[relatedConcept.link].type.isDerivedFrom(XbrlConst.qnXlExtendedType)))):
                                        self.modelVersReport.error("verdime:invalidLinkElement",
                                            _("%(event)s link %(link)s is not defined in its DTS"),
                                            modelObject=aspect, event=iaChange.name, link=relatedConcept.link)

        self.close()
