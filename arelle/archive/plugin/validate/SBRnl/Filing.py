'''
See COPYRIGHT.md for copyright information.
'''
import regex as re
from collections import defaultdict
from arelle import (ModelDocument, ModelRelationshipSet, XmlUtil, XbrlConst)
from arelle.ModelDtsObject import ModelConcept, ModelResource
from arelle.ModelObject import ModelObject
from arelle.UrlUtil import isHttpUrl
from .Dimensions import checkFilingDimensions
from .DTS import checkFilingDTS


def validateFiling(val, modelXbrl):

    linkroleDefinitionStatementSheet = re.compile(r"[^-]+-\s+Statement\s+-\s+.*", # no restriction to type of statement
                                                  re.IGNORECASE)
    if not hasattr(modelXbrl.modelDocument, "xmlDocument"): # not parsed
        return

    val._isStandardUri = {}
    modelXbrl.modelManager.disclosureSystem.loadStandardTaxonomiesDict()

    # find typedDomainRefs before validateXBRL pass
    val.typedDomainQnames = set()
    val.typedDomainElements = set()
    for modelConcept in modelXbrl.qnameConcepts.values():
        if modelConcept.isTypedDimension:
            typedDomainElement = modelConcept.typedDomainElement
            if isinstance(typedDomainElement, ModelConcept):
                val.typedDomainQnames.add(typedDomainElement.qname)
                val.typedDomainElements.add(typedDomainElement)

    # note that some XFM tests are done by ValidateXbrl to prevent multiple node walks
    xbrlInstDoc = modelXbrl.modelDocument.xmlDocument.getroot()
    disclosureSystem = val.disclosureSystem
    disclosureSystemVersion = disclosureSystem.version

    modelXbrl.modelManager.showStatus(_("validating {0}").format(disclosureSystem.name))

    val.modelXbrl.profileActivity()
    conceptsUsed = {} # key=concept object value=True if has presentation label
    labelsRelationshipSet = modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    genLabelsRelationshipSet = modelXbrl.relationshipSet(XbrlConst.elementLabel)
    presentationRelationshipSet = modelXbrl.relationshipSet(XbrlConst.parentChild)
    referencesRelationshipSetWithProhibits = modelXbrl.relationshipSet(XbrlConst.conceptReference, includeProhibits=True)
    val.modelXbrl.profileActivity("... cache lbl, pre, ref relationships", minTimeToShow=1.0)

    val.validateLoggingSemantic = validateLoggingSemantic = (
          modelXbrl.isLoggingEffectiveFor(level="WARNING-SEMANTIC") or
          modelXbrl.isLoggingEffectiveFor(level="ERROR-SEMANTIC"))

    # instance checks
    val.fileNameBasePart = None # prevent testing on fileNameParts if not instance or invalid
    val.fileNameDate = None
    val.entityRegistrantName = None
    val.requiredContext = None
    val.standardNamespaceConflicts = defaultdict(set)
    val.exhibitType = None # e.g., EX-101, EX-201


    # entry point schema checks
    if modelXbrl.modelDocument.type == ModelDocument.Type.SCHEMA:
        # entry must have a P-link
        if not any(hrefElt.localName == "linkbaseRef" and hrefElt.get("{http://www.w3.org/1999/xlink}role") == "http://www.xbrl.org/2003/role/presentationLinkbaseRef"
                   for hrefElt, hrefDoc, hrefId in modelXbrl.modelDocument.hrefObjects):
            modelXbrl.error("SBR.NL.2.2.10.01",
                'Entrypoint schema must have a presentation linkbase', modelObject=modelXbrl.modelDocument)
    # all-labels and references checks
    for concept in modelXbrl.qnameConcepts.values():
        conceptHasDefaultLangStandardLabel = False
        for modelLabelRel in labelsRelationshipSet.fromModelObject(concept):
            modelLabel = modelLabelRel.toModelObject
            role = modelLabel.role
            text = modelLabel.text
            lang = modelLabel.xmlLang
            if role == XbrlConst.documentationLabel:
                if concept.modelDocument.targetNamespace in disclosureSystem.standardTaxonomiesDict:
                    modelXbrl.error("SBR.NL.2.1.0.08",
                        _("Concept %(concept)s of a standard taxonomy cannot have a documentation label: %(text)s"),
                        modelObject=modelLabel, concept=concept.qname, text=text)
            elif text and lang and disclosureSystem.defaultXmlLang and lang.startswith(disclosureSystem.defaultXmlLang):
                if role == XbrlConst.standardLabel:  # merge of pre-plugin code per LOGIUS
                    conceptHasDefaultLangStandardLabel = True
                match = modelXbrl.modelManager.disclosureSystem.labelCheckPattern.search(text)
                if match:
                    modelXbrl.error("SBR.NL.2.3.8.07",
                        'Label for concept %(concept)s role %(role)s has disallowed characters: "%(text)s"',
                        modelObject=modelLabel, concept=concept.qname, role=role, text=match.group())
        for modelRefRel in referencesRelationshipSetWithProhibits.fromModelObject(concept):
            modelReference = modelRefRel.toModelObject
            text = XmlUtil.innerText(modelReference)
            #6.18.1 no reference to company extension concepts
            if (concept.modelDocument.targetNamespace in disclosureSystem.standardTaxonomiesDict and
                not isStandardUri(val, modelRefRel.modelDocument.uri)): # merge of pre-plugin code per LOGIUS
                #6.18.2 no extension to add or remove references to standard concepts
                modelXbrl.error("SBR.NL.2.1.0.08",
                    _("References for standard taxonomy concept %(concept)s are not allowed in an extension linkbase: %(text)s"),
                    modelObject=modelReference, concept=concept.qname, text=text, xml=XmlUtil.xmlstring(modelReference, stripXmlns=True, contentsOnly=True))
        if concept.isItem or concept.isTuple:
            if concept.modelDocument.targetNamespace not in disclosureSystem.standardTaxonomiesDict:
                if not conceptHasDefaultLangStandardLabel:
                    modelXbrl.error("SBR.NL.2.2.2.26",
                        _("Concept %(concept)s missing standard label in local language."),
                        modelObject=concept, concept=concept.qname)
                subsGroup = concept.get("substitutionGroup")
                if ((not concept.isAbstract or subsGroup == "sbr:presentationItem") and
                    not (presentationRelationshipSet.toModelObject(concept) or
                         presentationRelationshipSet.fromModelObject(concept))):
                    modelXbrl.error("SBR.NL.2.2.2.04",
                        _("Concept %(concept)s not referred to by presentation relationship."),
                        modelObject=concept, concept=concept.qname)
                elif ((concept.isDimensionItem or
                      (subsGroup and (subsGroup.endswith(":domainItem") or subsGroup.endswith(":domainMemberItem")))) and
                    not (presentationRelationshipSet.toModelObject(concept) or
                         presentationRelationshipSet.fromModelObject(concept))):
                    modelXbrl.error("SBR.NL.2.2.10.03",
                        _("DTS concept %(concept)s not referred to by presentation relationship."),
                        modelObject=concept, concept=concept.qname)
                if (concept.substitutionGroupQname and
                    concept.substitutionGroupQname.namespaceURI not in disclosureSystem.baseTaxonomyNamespaces):
                    modelXbrl.error("SBR.NL.2.2.2.05",
                        _("Concept %(concept)s has a substitutionGroup of a non-standard concept."),
                        modelObject=concept, concept=concept.qname)

                if concept.isTuple: # verify same presentation linkbase nesting
                    for missingQname in set(concept.type.elements) ^ pLinkedNonAbstractDescendantQnames(modelXbrl, concept):
                        modelXbrl.error("SBR.NL.2.3.4.01",
                            _("Tuple %(concept)s has mismatch between content and presentation children: %(missingQname)s."),
                            modelObject=concept, concept=concept.qname, missingQname=missingQname)
            checkConceptLabels(val, modelXbrl, labelsRelationshipSet, disclosureSystem, concept)
            checkConceptLabels(val, modelXbrl, genLabelsRelationshipSet, disclosureSystem, concept)

    val.modelXbrl.profileActivity("... filer concepts checks", minTimeToShow=1.0)

    # checks on all documents: instance, schema, instance
    checkFilingDTS(val, modelXbrl.modelDocument, [])
    ''' removed RH 2011-12-23, corresponding use of nameWordsTable in ValidateFilingDTS
    if val.validateSBRNL:
        del val.nameWordsTable
    '''
    val.modelXbrl.profileActivity("... filer DTS checks", minTimeToShow=1.0)

    conceptRelsUsedWithPreferredLabels = defaultdict(list)
    usedCalcsPresented = defaultdict(set) # pairs of concepts objectIds used in calc
    usedCalcFromTosELR = {}
    localPreferredLabels = defaultdict(set)
    drsELRs = set()

    # do calculation, then presentation, then other arcroles
    val.summationItemRelsSetAllELRs = modelXbrl.relationshipSet(XbrlConst.summationItem)
    for arcroleFilter in (XbrlConst.summationItem, XbrlConst.parentChild, "*"):
        for baseSetKey, baseSetModelLinks  in modelXbrl.baseSets.items():
            arcrole, ELR, linkqname, arcqname = baseSetKey
            if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-"):
                # assure summationItem, then parentChild, then others
                if not (arcroleFilter == arcrole or
                        arcroleFilter == "*" and arcrole not in (XbrlConst.summationItem, XbrlConst.parentChild)):
                    continue
                if arcrole == XbrlConst.parentChild:
                    ineffectiveArcs = ModelRelationshipSet.ineffectiveArcs(baseSetModelLinks, arcrole)
                    #validate ineffective arcs
                    for modelRel in ineffectiveArcs:
                        if isinstance(modelRel.fromModelObject, ModelObject) and isinstance(modelRel.toModelObject, ModelObject):
                            modelXbrl.error("SBR.NL.2.3.4.06",
                                _("Ineffective arc %(arc)s in \nlink role %(linkrole)s \narcrole %(arcrole)s \nfrom %(conceptFrom)s \nto %(conceptTo)s \n%(ineffectivity)s"),
                                modelObject=modelRel, arc=modelRel.qname, arcrole=modelRel.arcrole,
                                linkrole=modelRel.linkrole, linkroleDefinition=modelXbrl.roleTypeDefinition(modelRel.linkrole),
                                conceptFrom=modelRel.fromModelObject.qname, conceptTo=modelRel.toModelObject.qname,
                                ineffectivity=modelRel.ineffectivity)
                if arcrole == XbrlConst.parentChild:
                    isStatementSheet = any(linkroleDefinitionStatementSheet.match(roleType.definition or '')
                                           for roleType in val.modelXbrl.roleTypes.get(ELR,()))
                    conceptsPresented = set()
                    # 6.12.2 check for distinct order attributes
                    parentChildRels = modelXbrl.relationshipSet(arcrole, ELR)
                    for relFrom, siblingRels in parentChildRels.fromModelObjects().items():
                        targetConceptPreferredLabels = defaultdict(dict)
                        orderRels = {}
                        firstRel = True
                        relFromUsed = True
                        for rel in siblingRels:
                            if firstRel:
                                firstRel = False
                                if relFrom in conceptsUsed:
                                    conceptsUsed[relFrom] = True # 6.12.3, has a pres relationship
                                    relFromUsed = True
                            relTo = rel.toModelObject
                            preferredLabel = rel.preferredLabel
                            if relTo in conceptsUsed:
                                conceptsUsed[relTo] = True # 6.12.3, has a pres relationship
                                if preferredLabel and preferredLabel != "":
                                    conceptRelsUsedWithPreferredLabels[relTo].append(rel)
                                    if preferredLabel in ("periodStart","periodEnd"):
                                        modelXbrl.error("SBR.NL.2.3.4.03",
                                            _("Preferred label on presentation relationships not allowed"), modelObject=modelRel)
                                # 6.12.5 distinct preferred labels in base set
                                preferredLabels = targetConceptPreferredLabels[relTo]
                                if (preferredLabel in preferredLabels or
                                    (not relFrom.isTuple and
                                     (not preferredLabel or None in preferredLabels))):
                                    if preferredLabel in preferredLabels:
                                        rel2, relTo2 = preferredLabels[preferredLabel]
                                    else:
                                        rel2 = relTo2 = None
                                    modelXbrl.error("SBR.NL.2.3.4.06",
                                        _("Concept %(concept)s has duplicate preferred label %(preferredLabel)s in link role %(linkrole)s"),
                                        modelObject=(rel, relTo, rel2, relTo2),
                                        concept=relTo.qname, fromConcept=rel.fromModelObject.qname,
                                        preferredLabel=preferredLabel, linkrole=rel.linkrole, linkroleDefinition=modelXbrl.roleTypeDefinition(rel.linkrole))
                                else:
                                    preferredLabels[preferredLabel] = (rel, relTo)
                                if relFromUsed:
                                    # 6.14.5
                                    conceptsPresented.add(relFrom.objectIndex)
                                    conceptsPresented.add(relTo.objectIndex)
                            order = rel.order
                            if order in orderRels:
                                modelXbrl.error("SBR.NL.2.3.4.05",
                                    _("Duplicate presentation relations from concept %(conceptFrom)s for order %(order)s in base set role %(linkrole)s to concept %(conceptTo)s and to concept %(conceptTo2)s"),
                                    modelObject=(rel, orderRels[order]), conceptFrom=relFrom.qname, order=rel.arcElement.get("order"), linkrole=rel.linkrole, linkroleDefinition=modelXbrl.roleTypeDefinition(rel.linkrole),
                                    conceptTo=rel.toModelObject.qname, conceptTo2=orderRels[order].toModelObject.qname)
                            else:
                                orderRels[order] = rel
                            if not relFrom.isTuple:
                                if relTo in localPreferredLabels:
                                    if {None, preferredLabel} & localPreferredLabels[relTo]:
                                        val.modelXbrl.error("SBR.NL.2.3.4.06",
                                            _("Non-distinguished preferredLabel presentation relations from concept %(conceptFrom)s in base set role %(linkrole)s"),
                                            modelObject=rel, conceptFrom=relFrom.qname, linkrole=rel.linkrole, conceptTo=relTo.qname)
                                localPreferredLabels[relTo].add(preferredLabel)
                        targetConceptPreferredLabels.clear()
                        orderRels.clear()
                    localPreferredLabels.clear() # clear for next relationship
                    for conceptPresented in conceptsPresented:
                        if conceptPresented in usedCalcsPresented:
                            usedCalcPairingsOfConcept = usedCalcsPresented[conceptPresented]
                            if len(usedCalcPairingsOfConcept & conceptsPresented) > 0:
                                usedCalcPairingsOfConcept -= conceptsPresented
                elif arcrole == XbrlConst.summationItem:
                    # find a calc relationship to get the containing document name
                    for modelRel in val.modelXbrl.relationshipSet(arcrole, ELR).modelRelationships:
                        val.modelXbrl.error("SBR.NL.2.3.9.01",
                            _("Calculation linkbase linkrole %(linkrole)s"),
                            modelObject=modelRel, linkrole=ELR)
                        break

                elif arcrole == XbrlConst.all or arcrole == XbrlConst.notAll:
                    drsELRs.add(ELR)

                else:
                    if arcrole == XbrlConst.dimensionDefault:
                        for modelRel in val.modelXbrl.relationshipSet(arcrole).modelRelationships:
                            val.modelXbrl.error("SBR.NL.2.3.6.05",
                                _("Dimension-default in from %(conceptFrom)s to %(conceptTo)s in role %(linkrole)s is not allowed"),
                                modelObject=modelRel, conceptFrom=modelRel.fromModelObject.qname, conceptTo=modelRel.toModelObject.qname,
                                linkrole=modelRel.linkrole)
                    ''' removed per RH 2013-01-11
                    if not (XbrlConst.isStandardArcrole(arcrole) or XbrlConst.isDefinitionOrXdtArcrole(arcrole)):
                        for modelRel in val.modelXbrl.relationshipSet(arcrole).modelRelationships:
                            relTo = modelRel.toModelObject
                            relFrom = modelRel.fromModelObject
                            if not ((isinstance(relFrom,ModelConcept) and isinstance(relTo,ModelConcept)) or
                                    (relFrom.modelDocument.inDTS and
                                     (relTo.qname == XbrlConst.qnGenLabel and modelRel.arcrole == XbrlConst.elementLabel) or
                                     (relTo.qname == XbrlConst.qnGenReference and modelRel.arcrole == XbrlConst.elementReference) or
                                     (relTo.qname == val.qnSbrLinkroleorder))):
                                val.modelXbrl.error("SBR.NL.2.3.2.07",
                                    _("The source and target of an arc must be in the DTS from %(elementFrom)s to %(elementTo)s, in linkrole %(linkrole)s, arcrole %(arcrole)s"),
                                    modelObject=modelRel, elementFrom=relFrom.qname, elementTo=relTo.qname,
                                    linkrole=modelRel.linkrole, arcrole=arcrole)
                        '''

    del localPreferredLabels # dereference
    del usedCalcFromTosELR
    del val.summationItemRelsSetAllELRs

    val.modelXbrl.profileActivity("... filer relationships checks", minTimeToShow=1.0)


    # checks on dimensions
    checkFilingDimensions(val, drsELRs)
    val.modelXbrl.profileActivity("... filer dimensions checks", minTimeToShow=1.0)

    del conceptRelsUsedWithPreferredLabels

    # 6 16 4, 1.16.5 Base sets of Domain Relationship Sets testing
    val.modelXbrl.profileActivity("... filer preferred label checks", minTimeToShow=1.0)

    # moved from original validateSBRnl finally

    for qname, modelType in modelXbrl.qnameTypes.items():
        if qname.namespaceURI not in val.disclosureSystem.baseTaxonomyNamespaces:
            facets = modelType.facets
            if facets:
                lengthFacets = facets.keys() & {"minLength", "maxLength", "length"}
                if lengthFacets:
                    modelXbrl.error("SBR.NL.2.2.7.02",
                        _("Type %(typename)s has length restriction facets %(facets)s"),
                        modelObject=modelType, typename=modelType.qname, facets=", ".join(lengthFacets))
                if "enumeration" in facets and not modelType.isDerivedFrom(XbrlConst.qnXbrliStringItemType):
                    modelXbrl.error("SBR.NL.2.2.7.04",
                        _("Concept %(concept)s has enumeration and is not based on stringItemType"),
                        modelObject=modelType, concept=modelType.qname)

    ''' removed RH 2011-12-23, corresponding use of nameWordsTable in ValidateFilingDTS
    # build camelCasedNamesTable
    self.nameWordsTable = {}
    for name in modelXbrl.nameConcepts.keys():
        words = []
        wordChars = []
        lastchar = ""
        for c in name:
            if c.isupper() and lastchar.islower(): # it's another word
                partialName = ''.join(wordChars)
                if partialName in modelXbrl.nameConcepts:
                    words.append(partialName)
            wordChars.append(c)
            lastchar = c
        if words:
            self.nameWordsTable[name] = words
    self.modelXbrl.profileActivity("... build name words table", minTimeToShow=1.0)
    '''



    # check presentation link roles for generic linkbase order number
    ordersRelationshipSet = modelXbrl.relationshipSet("http://www.nltaxonomie.nl/2011/arcrole/linkrole-order")
    presLinkroleNumberURI = {}
    presLinkrolesCount = 0
    for countLinkroles in (True, False):
        for _roleURI, modelRoleTypes in modelXbrl.roleTypes.items():
            for modelRoleType in modelRoleTypes:
                if XbrlConst.qnLinkPresentationLink in modelRoleType.usedOns:
                    if countLinkroles:
                        presLinkrolesCount += 1
                    else:
                        if not ordersRelationshipSet:
                            modelXbrl.error("SBR.NL.2.2.3.06",
                                _("Presentation linkrole %(linkrole)s missing order number relationship set"),
                                modelObject=modelRoleType, linkrole=modelRoleType.roleURI)
                        else:
                            order = None
                            for orderNumRel in ordersRelationshipSet.fromModelObject(modelRoleType):
                                order = getattr(orderNumRel.toModelObject, "xValue", "(noPSVIvalue)")
                                if order in presLinkroleNumberURI:
                                    modelXbrl.error("SBR.NL.2.2.3.06",
                                        _("Presentation linkrole order number %(order)s of %(linkrole)s also used in %(otherLinkrole)s"),
                                        modelObject=modelRoleType, order=order, linkrole=modelRoleType.roleURI, otherLinkrole=presLinkroleNumberURI[order])
                                else:
                                    presLinkroleNumberURI[order] = modelRoleType.roleURI
                            if not order:
                                modelXbrl.error("SBR.NL.2.2.3.06",
                                    _("Presentation linkrole %(linkrole)s missing order number"),
                                    modelObject=modelRoleType, linkrole=modelRoleType.roleURI)
        if countLinkroles and presLinkrolesCount < 2:
            break   # don't check order numbers if only one presentation linkrole
    # check arc role definitions for labels
    for arcroleURI, modelRoleTypes in modelXbrl.arcroleTypes.items():
        for modelRoleType in modelRoleTypes:
            if (not arcroleURI.startswith("http://xbrl.org/") and
                modelRoleType.modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces and
                (not modelRoleType.genLabel(lang="nl") or not modelRoleType.genLabel(lang="en"))):
                modelXbrl.error("SBR.NL.2.2.4.02",
                    _("ArcroleType missing nl or en generic label: %(arcrole)s"),
                    modelObject=modelRoleType, arcrole=arcroleURI)

    for domainElt in val.typedDomainElements:
        if domainElt.modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces:
            if not domainElt.genLabel(fallbackToQname=False, lang="nl"):
                modelXbrl.error("SBR.NL.2.2.8.01",
                    _("Typed dimension domain element %(concept)s must have a generic label"),
                    modelObject=domainElt, concept=domainElt.qname)
            if domainElt.type is not None and domainElt.type.localName == "complexType":
                modelXbrl.error("SBR.NL.2.2.8.02",
                    _("Typed dimension domain element %(concept)s has disallowed complex content"),
                    modelObject=domainElt, concept=domainElt.qname)

    modelXbrl.profileActivity("... SBR role types and type facits checks", minTimeToShow=1.0)
    # end moved from ValidateFiling

    # 3.2.4.4 check each using prefix against taxonomy declaring the prefix
    for docs in modelXbrl.namespaceDocs.values():
        for doc in docs:
            for prefix, NS in doc.xmlRootElement.nsmap.items():
                if NS in val.namespacePrefix and prefix != val.namespacePrefix[NS]:
                    modelXbrl.error("SBR.NL.3.2.4.04",
                        _("The assigned namespace prefix %(assignedPrefix)s for the schema that declares the targetnamespace %(namespace)s, MUST be adhired by all other NT schemas, referencedPrefix: %(referencedPrefix)s"),
                        modelObject=doc.xmlRootElement, namespace=NS, assignedPrefix=val.namespacePrefix.get(NS, ''), referencedPrefix=prefix)

    # check non-concept elements that can appear in elements for labels (concepts checked by
    labelsRelationshipSet = modelXbrl.relationshipSet((XbrlConst.conceptLabel, XbrlConst.elementLabel))
    baseTaxonomyNamespaces = val.disclosureSystem.baseTaxonomyNamespaces
    for eltDef in modelXbrl.qnameConcepts.values():
        if (not (eltDef.isItem or eltDef.isTuple or eltDef.isLinkPart) and
            eltDef.qname.namespaceURI not in baseTaxonomyNamespaces):
            eltDefHasDefaultLangStandardLabel = False
            for modelLabelRel in labelsRelationshipSet.fromModelObject(eltDef):
                modelLabel = modelLabelRel.toModelObject
                role = modelLabel.role
                text = modelLabel.text
                lang = modelLabel.xmlLang
                if text and lang and val.disclosureSystem.defaultXmlLang and lang.startswith(val.disclosureSystem.defaultXmlLang):
                    if role in (XbrlConst.standardLabel, XbrlConst.genStandardLabel):
                        eltDefHasDefaultLangStandardLabel = True
            if not eltDefHasDefaultLangStandardLabel:
                modelXbrl.error("SBR.NL.3.2.15.01",
                    _("XML nodes that can appear in instances MUST have standard labels in the local language: %(element)s"),
                    modelObject=eltDef, element=eltDef.qname)

    val.modelXbrl.profileStat(_("validate{0}").format(modelXbrl.modelManager.disclosureSystem.validationType))

    modelXbrl.modelManager.showStatus(_("ready"), 2000)

def isStandardUri(val, uri):
    try:
        return val._isStandardUri[uri]
    except KeyError:
        isStd = (uri in val.disclosureSystem.standardTaxonomiesDict or
                 (not isHttpUrl(uri) and
                  # try 2011-12-23 RH: if works, remove the localHrefs
                  # any(u.endswith(e) for u in (uri.replace("\\","/"),) for e in disclosureSystem.standardLocalHrefs)
                  "/basis/sbr/" in uri.replace("\\","/")
                  ))
        val._isStandardUri[uri] = isStd
        return isStd

def checkConceptLabels(val, modelXbrl, labelsRelationshipSet, disclosureSystem, concept):
    hasDefaultLangStandardLabel = False
    dupLabels = {}
    for modelLabelRel in labelsRelationshipSet.fromModelObject(concept):
        modelLabel = modelLabelRel.toModelObject
        if isinstance(modelLabel, ModelResource) and modelLabel.xmlLang:
            if modelLabel.xmlLang.startswith(disclosureSystem.defaultXmlLang) and \
               modelLabel.role == XbrlConst.standardLabel:
                hasDefaultLangStandardLabel = True
            dupDetectKey = ( (modelLabel.role or ''), modelLabel.xmlLang)
            if dupDetectKey in dupLabels:
                modelXbrl.error("SBR.NL.2.2.1.05",
                    _("Concept %(concept)s has duplicated labels for role %(role)s lang %(lang)s."),
                    modelObject=(modelLabel, dupLabels[dupDetectKey]), # removed concept from modelObjects
                    concept=concept.qname, role=dupDetectKey[0], lang=dupDetectKey[1])
            else:
                dupLabels[dupDetectKey] = modelLabel
            if modelLabel.role in (XbrlConst.periodStartLabel, XbrlConst.periodEndLabel):
                modelXbrl.error("SBR.NL.2.3.8.03",
                    _("Concept %(concept)s has label for semantical role %(role)s."),
                    modelObject=modelLabel, concept=concept.qname, role=modelLabel.role)
    for role, lang in dupLabels.keys():
        if role and lang != disclosureSystem.defaultXmlLang and (role,disclosureSystem.defaultXmlLang) not in dupLabels:
            modelXbrl.error("SBR.NL.2.3.8.05",
                _("Concept %(concept)s has en but no nl label in role %(role)s."),
                modelObject=(concept,dupLabels[(role,lang)]), concept=concept.qname, role=role)



# for SBR 2.3.4.01
def pLinkedNonAbstractDescendantQnames(modelXbrl, concept, descendants=None):
    if descendants is None: descendants = set()
    for rel in modelXbrl.relationshipSet(XbrlConst.parentChild).fromModelObject(concept):
        child = rel.toModelObject
        if child is not None:
            if child.isAbstract:
                pLinkedNonAbstractDescendantQnames(modelXbrl, child, descendants)
            else:
                descendants.add(child.qname)
    return descendants
