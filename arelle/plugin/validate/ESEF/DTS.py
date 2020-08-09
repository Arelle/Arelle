'''
Created on June 6, 2018

Filer Guidelines: ESMA_ESEF Manula 2019.pdf

Taxonomy Architecture: 

Taxonomy package expected to be installed: 

@author: Mark V Systems Limited
(c) Copyright 2018 Mark V Systems Limited, All rights reserved.
'''

import unicodedata
try:
    import regex as re
except ImportError:
    import re
from collections import defaultdict
from arelle import ModelDocument, XbrlConst
from arelle.ModelDtsObject import ModelConcept, ModelType
from arelle.ModelObject import ModelObject
from arelle.XbrlConst import xbrli, standardLabelRoles, dimensionDefault, standardLinkbaseRefRoles
from .Const import qnDomainItemType, esefDefinitionArcroles, disallowedURIsPattern, DefaultDimensionLinkrole
from .Util import isExtension

def checkFilingDTS(val, modelDocument, visited, hrefXlinkRole=None):
    visited.append(modelDocument)
    for referencedDocument, modelDocumentReference in modelDocument.referencesDocument.items():
        if referencedDocument not in visited and referencedDocument.inDTS: # ignore non-DTS documents
            checkFilingDTS(val, referencedDocument, visited, modelDocumentReference.referringXlinkRole)
            
    isExtensionDoc = isExtension(val, modelDocument)
    filenamePattern = None
    
    if modelDocument.type == ModelDocument.Type.SCHEMA and isExtensionDoc:
        
        val.hasExtensionSchema = True
        
        filenamePattern = re.compile(r"(.{1,})-[0-9]{4}-[0-9]{2}-[0-9]{2}[.]xsd$")

        for doc, docRef in modelDocument.referencesDocument.items():
            if docRef.referenceType in ("import","include") and disallowedURIsPattern.match(doc.uri):
                val.modelXbrl.warning("ESEF.3.1.1.extensionImportNotAllowed",
                                    _("Taxonomy reference not allowed for extension schema: %(taxonomy)s"),
                                    modelObject=modelDocument, taxonomy=doc.uri)
        
        tuplesInExtTxmy = []
        fractionsInExtTxmy = []
        typedDimsInExtTxmy = []
        domainMembersWrongType = []
        extLineItemsWithoutHypercube = []
        extLineItemsNotAnchored = []
        extAbstractConcepts = []
        extMonetaryConceptsWithoutBalance = []
        langRoleLabels = defaultdict(list)
        conceptsWithoutStandardLabel = []
        conceptsWithNoLabel = []
        widerNarrowerRelSet = val.modelXbrl.relationshipSet(XbrlConst.widerNarrower)
        calcRelSet = val.modelXbrl.relationshipSet(XbrlConst.summationItem)
        dimensionDefaults = val.modelXbrl.relationshipSet(dimensionDefault, DefaultDimensionLinkrole)
        labelsRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
        if modelDocument.targetNamespace is not None:
            for modelConcept in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/2001/XMLSchema}element"):
                if isinstance(modelConcept,ModelConcept):
                    name = modelConcept.get("name")
                    if name is None: 
                        name = ""
                        if modelConcept.get("ref") is not None:
                            continue    # don't validate ref's here
                    if modelConcept.isTuple:
                        tuplesInExtTxmy.append(modelConcept)
                    if modelConcept.isFraction:
                        fractionsInExtTxmy.append(modelConcept)
                    if modelConcept.isTypedDimension:
                        typedDimsInExtTxmy.append(modelConcept)
                    if modelConcept.isExplicitDimension and not dimensionDefaults.fromModelObject(modelConcept):
                        val.modelXbrl.error("ESEF.3.4.3.extensionTaxonomyDimensionNotAssigedDefaultMemberInDedicatedPlaceholder",
                            _("Each dimension in an issuer specific extension taxonomy MUST be assigned to a default member in the ELR with role URI http://www.esma.europa.eu/xbrl/role/core/ifrs-dim_role-990000 defined in esef_cor.xsd schema file. %(qname)s"),
                            modelObject=modelConcept, qname=modelConcept.qname)
                    if modelConcept.isDomainMember and modelConcept in val.domainMembers and modelConcept.typeQname != qnDomainItemType:
                        domainMembersWrongType.append(modelConcept)
                    if modelConcept.isPrimaryItem and not modelConcept.isAbstract:
                        if modelConcept not in val.primaryItems:
                            extLineItemsWithoutHypercube.append(modelConcept)
                        elif not widerNarrowerRelSet.fromModelObject(modelConcept) and not widerNarrowerRelSet.toModelObject(modelConcept):
                            if not calcRelSet.fromModelObject(modelConcept) or not calcRelSet.toModelObject(modelConcept): # exclude subtotals
                                extLineItemsNotAnchored.append(modelConcept)
                    if (modelConcept.isAbstract and modelConcept not in val.domainMembers and 
                        modelConcept.type is not None and not modelConcept.type.isDomainItemType and
                        not modelConcept.isHypercubeItem and not modelConcept.isDimensionItem):
                        extAbstractConcepts.append(modelConcept)
                    if modelConcept.isMonetary and not modelConcept.balance:
                        extMonetaryConceptsWithoutBalance.append(modelConcept)
                    # check all lang's of standard label
                    hasLc3Match = False
                    lc3names = []
                    hasStandardLabel = False
                    hasNonStandardLabel = False
                    if labelsRelationshipSet:
                        for labelRel in labelsRelationshipSet.fromModelObject(modelConcept):
                            concept = labelRel.fromModelObject
                            label = labelRel.toModelObject
                            if concept is not None and label is not None:
                                if label.role == XbrlConst.standardLabel:
                                    hasStandardLabel = True
                                    # allow Joe's Bar, N.A.  to be JoesBarNA -- remove ', allow A. as not article "a"
                                    lc3name = ''.join(re.sub(r"['.-]", "", (w[0] or w[2] or w[3] or w[4])).title()
                                                      for w in re.findall(r"((\w+')+\w+)|(A[.-])|([.-]A(?=\W|$))|(\w+)", 
                                                                          unicodedata.normalize('NFKD', label.textValue)
                                                                          .encode('ASCII', 'ignore').decode()  # remove diacritics 
                                                                          )
                                                      # if w[4].lower() not in ("the", "a", "an")
                                                      )
                                    lc3names.append(lc3name)
                                    if (name == lc3name or 
                                        (name and lc3name and lc3name[0].isdigit() and name[1:] == lc3name and (name[0].isalpha() or name[0] == '_'))):
                                        hasLc3Match = True
                                else:
                                    hasNonStandardLabel = True
                            langRoleLabels[(label.xmlLang,label.role)].append(label)
                            if label.role not in standardLabelRoles:
                                val.modelXbrl.warning("ESEF.3.4.5.extensionTaxonomyElementLabelCustomRole",
                                    _("Extension taxonomy element label SHOULD not be custom: %(concept)s role %(labelrole)s"),
                                    modelObject=(modelConcept,label), concept=modelConcept.qname, labelrole=label.role)
                    if modelConcept.isItem or modelConcept.isTuple or modelConcept.isHypercubeItem or modelConcept.isDimensionItem:
                        if not hasStandardLabel:
                            if hasNonStandardLabel:
                                conceptsWithoutStandardLabel.append(modelConcept)
                            else:
                                conceptsWithNoLabel.append(modelConcept)
                        elif not hasLc3Match:
                            val.modelXbrl.warning("ESEF.3.2.1.extensionTaxonomyElementNameDoesNotFollowLc3Convention",
                                _("Extension taxonomy element name SHOULD follow the LC3 convention: %(concept)s should match an expected LC3 composition %(lc3names)s"),
                                modelObject=modelConcept, concept=modelConcept.qname, lc3names=", ".join(lc3names))
                        for (lang,labelrole),labels in langRoleLabels.items():
                            if len(labels) > 1:
                                val.modelXbrl.warning("ESEF.3.4.5.extensionTaxonomyElementDuplicateLabels",
                                    _("Extension taxonomy element name SHOULD not have multiple labels for lang %(lang)s and role %(labelrole)s: %(concept)s"),
                                    modelObject=[modelConcept]+labels, concept=modelConcept.qname, lang=lang, labelrole=labelrole)
                    langRoleLabels.clear()
            for modelType in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/2001/XMLSchema}complexType"):
                if (isinstance(modelType,ModelType) and isExtension(val, modelType) and 
                    modelType.typeDerivedFrom is not None and modelType.typeDerivedFrom.qname.namespaceURI == xbrli and
                    not modelType.particlesList):
                    val.modelXbrl.error("ESEF.RTS.Annex.IV.Par.11.customDataTypeDuplicatingXbrlOrDtrEntry",
                        _("Extension taxonomy element must not define a type where one is already defined by the XBRL specifications or in the XBRL Data Types Registry: %(qname)s"),
                        modelObject=modelType, qname=modelType.qname)
        if tuplesInExtTxmy:
            val.modelXbrl.error("ESEF.2.4.1.tupleDefinedInExtensionTaxonomy",
                _("Tuples MUST NOT be defined in extension taxonomy: %(concepts)s"),
                modelObject=tuplesInExtTxmy, concepts=", ".join(str(c.qname) for c in tuplesInExtTxmy))
        if fractionsInExtTxmy:
            val.modelXbrl.error("ESEF.2.4.1.fractionDefinedInExtensionTaxonomy",
                _("Fractions MUST NOT be defined in extension taxonomy: %(concepts)s"),
                modelObject=fractionsInExtTxmy, concepts=", ".join(str(c.qname) for c in fractionsInExtTxmy))
        if typedDimsInExtTxmy:
            val.modelXbrl.warning("ESEF.3.2.3.typedDimensionDefinitionInExtensionTaxonomy",
                _("Extension taxonomy SHOULD NOT define typed dimensions: %(concepts)s."),
                modelObject=typedDimsInExtTxmy, concepts=", ".join(str(c.qname) for c in typedDimsInExtTxmy))
        if domainMembersWrongType:
            val.modelXbrl.error("ESEF.3.2.2.domainMemberWrongDataType",
                _("Domain members MUST have domainItemType data type as defined in \"http://www.xbrl.org/dtr/type/nonNumeric-2009-12-16.xsd\": concept %(concepts)s."),
                modelObject=domainMembersWrongType, concepts=", ".join(str(c.qname) for c in domainMembersWrongType))
        # HF - think this is only about reported line items, not ext line items (?)
        #if extLineItemsWithoutHypercube:
        #    val.modelXbrl.error("ESEF.3.4.2.extensionTaxonomyLineItemNotLinkedToAnyHypercube",
        #        _("Line items that do not require any dimensional information to tag data MUST be linked to \"Line items not dimensionally qualified\" hypercube in http://www.esma.europa.eu/xbrl/esef/role/esef_role-999999 declared in esef_cor.xsd: concept %(concepts)s."),
        #        modelObject=extLineItemsWithoutHypercube, concepts=", ".join(str(c.qname) for c in extLineItemsWithoutHypercube))
        if extLineItemsNotAnchored:
            val.modelXbrl.error("ESEF.3.3.1.extensionConceptsNotAnchored",
                _("Extension concepts SHALL be anchored to concepts in the ESEF taxonomy:  %(concepts)s."),
                modelObject=extLineItemsNotAnchored, concepts=", ".join(str(c.qname) for c in extLineItemsNotAnchored))
        if extAbstractConcepts:
            val.modelXbrl.warning("ESEF.3.2.5.abstractConceptDefinitionInExtensionTaxonomy",
                _("Extension taxonomy SHOULD NOT define abstract concepts: concept %(concepts)s."),
                modelObject=extAbstractConcepts, concepts=", ".join(str(c.qname) for c in extAbstractConcepts))
        if extMonetaryConceptsWithoutBalance:  
            val.modelXbrl.error("ESEF.RTS.Annex.IV.Par.4.2.monetaryConceptWithoutBalance",
                _("Extension monetary concepts MUST provide balance attribute: concept %(concepts)s."),
                modelObject=extMonetaryConceptsWithoutBalance, concepts=", ".join(str(c.qname) for c in extMonetaryConceptsWithoutBalance))
        if conceptsWithNoLabel:
            val.modelXbrl.error("ESEF.RTS.Annex.IV.Par.4_G3.4.5.extensionConceptNoLabel",
                _("Extension concepts MUST provide labels: %(concepts)s."),
                modelObject=conceptsWithNoLabel, concepts=", ".join(str(c.qname) for c in conceptsWithNoLabel))
        if conceptsWithoutStandardLabel:
            val.modelXbrl.error("ESEF.RTS.Annex.IV.Par.4_G3.4.5.extensionConceptStandardLabel",
                _("Extension concepts MUST provide a standard label: %(concepts)s."),
                modelObject=conceptsWithoutStandardLabel, concepts=", ".join(str(c.qname) for c in conceptsWithoutStandardLabel))

        embeddedLinkbaseElements = [e
                                    for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}linkbase")
                                    if isinstance(e,ModelObject)]
        if embeddedLinkbaseElements:
                val.modelXbrl.warning("ESEF.3.1.1.linkbasesNotSeparateFiles",
                    _("Each linkbase type SHOULD be provided in a separate linkbase file, but a linkbase was found in %(schema)s."),
                    modelObject=embeddedLinkbaseElements, schema=modelDocument.basename)

        del (tuplesInExtTxmy, fractionsInExtTxmy, typedDimsInExtTxmy, domainMembersWrongType, 
             extLineItemsWithoutHypercube, extLineItemsNotAnchored, extAbstractConcepts, 
             extMonetaryConceptsWithoutBalance, langRoleLabels, conceptsWithNoLabel, conceptsWithoutStandardLabel)
                            
    if modelDocument.type == ModelDocument.Type.LINKBASE and isExtensionDoc:
        
        linkbasesFound = set()
        disallowedArcroles = defaultdict(list)
        prohibitedBaseConcepts = []
        prohibitingLbElts = []
        
        if hrefXlinkRole in standardLinkbaseRefRoles:
            # account for empty linkbaseRefs (populated are identified by extended links below)
            if hrefXlinkRole == "http://www.xbrl.org/2003/role/calculationLinkbaseRef":
                val.hasExtensionCal = True
                filenamePattern = re.compile(r"(.{1,})-[0-9]{4}-[0-9]{2}-[0-9]{2}_cal[.]xml$")
            elif hrefXlinkRole == "http://www.xbrl.org/2003/role/definitionLinkbaseRef":
                filenamePattern = re.compile(r"(.{1,})-[0-9]{4}-[0-9]{2}-[0-9]{2}_def[.]xml$")
                val.hasExtensionDef = True
            elif hrefXlinkRole == "http://www.xbrl.org/2003/role/labelLinkbaseRef":
                filenamePattern = re.compile(r"(.{1,})-[0-9]{4}-[0-9]{2}-[0-9]{2}_lbl-[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*[.]xml$")
                val.hasExtensionLbl = True
            elif hrefXlinkRole == "http://www.xbrl.org/2003/role/presentationLinkbaseRef":
                filenamePattern = re.compile(r"(.{1,})-[0-9]{4}-[0-9]{2}-[0-9]{2}_pre[.]xml$")
                val.hasExtensionPre = True
            elif hrefXlinkRole == "http://www.xbrl.org/2003/role/referenceLinkbaseRef":
                filenamePattern = re.compile(r"(.{1,})-[0-9]{4}-[0-9]{2}-[0-9]{2}_ref[.]xml$")


        for linkEltName in ("labelLink", "presentationLink", "calculationLink", "definitionLink", "referenceLink"):
            for linkElt in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}" + linkEltName):
                if linkEltName == "labelLink":
                    val.hasExtensionLbl = True
                    linkbasesFound.add(linkEltName)
                if linkEltName == "presentationLink":
                    val.hasExtensionPre = True
                    linkbasesFound.add(linkEltName)
                if linkEltName == "calculationLink":
                    val.hasExtensionCal = True
                    linkbasesFound.add(linkEltName)
                if linkEltName == "definitionLink":
                    val.hasExtensionDef = True
                    linkbasesFound.add(linkEltName)
                    # check for any unexpected definition arcrole which might be a custom wider-narrower arcrole
                    for arcElt in linkElt.iterchildren(tag="{http://www.xbrl.org/2003/linkbase}definitionArc"):
                        arcrole = arcElt.get("{http://www.w3.org/1999/xlink}arcrole") 
                        if arcrole not in esefDefinitionArcroles:
                            disallowedArcroles[arcrole].append(arcElt)
                if linkEltName in ("labelLink", "referenceLink"):
                    # check for prohibited esef taxnonomy target elements
                    prohibitedArcFroms = defaultdict(list)
                    prohibitedArcTos = defaultdict(list)
                    for arcElt in linkElt.iterchildren("{http://www.xbrl.org/2003/linkbase}labelArc", "{http://www.xbrl.org/2003/linkbase}referenceArc"):
                        if arcElt.get("use") == "prohibited":
                             prohibitedArcFroms[arcElt.get("{http://www.w3.org/1999/xlink}from")].append(arcElt)
                             prohibitedArcTos[arcElt.get("{http://www.w3.org/1999/xlink}to")].append(arcElt)
                    for locElt in linkElt.iterchildren("{http://www.xbrl.org/2003/linkbase}loc"):
                        prohibitingArcs = prohibitedArcTos.get(locElt.get("{http://www.w3.org/1999/xlink}label"))
                        if prohibitingArcs and not isExtension(val, locElt.get("{http://www.w3.org/1999/xlink}href")):
                            prohibitingLbElts.extend(prohibitingArcs)
                        prohibitingArcs = prohibitedArcFroms.get(locElt.get("{http://www.w3.org/1999/xlink}label"))
                        if prohibitingArcs and not isExtension(val, locElt.get("{http://www.w3.org/1999/xlink}href")):
                            prohibitingLbElts.extend(prohibitingArcs)
                            prohibitedBaseConcepts.append(locElt.dereference())
                    del prohibitedArcFroms, prohibitedArcTos # dereference                   
            for disallowedArcrole, arcs in disallowedArcroles.items():
                val.modelXbrl.error("ESEF.RTS.Annex.IV.disallowedDefinitionArcrole",
                    _("Disallowed arcrole in definition linkbase %(arcrole)s."),
                    modelObject=arcs, arcrole=arcrole)
            disallowedArcroles.clear()
            if prohibitingLbElts and prohibitedBaseConcepts:
                val.modelXbrl.error("ESEF.RTS.Annex.IV.Par.8.coreTaxonomy{}Modification".format(linkEltName[:-4].title()),
                    _("Disallowed modification of core taxonomy %(resource)s for %(qnames)s."),
                    modelObject=prohibitingLbElts+prohibitedBaseConcepts, 
                    resource=linkEltName[:-4],
                    qnames=", ".join(str(c.qname) for c in prohibitedBaseConcepts),
                    messageCodes=("ESEF.RTS.Annex.IV.Par.8.coreTaxonomyReferenceModification",
                                  "ESEF.RTS.Annex.IV.Par.8.coreTaxonomyLabelModification"))
            del prohibitingLbElts[:]
            del prohibitedBaseConcepts[:]
        if len(linkbasesFound) > 1:
            val.modelXbrl.error("ESEF.3.1.1.extensionTaxonomyWrongFilesStructure",
                _("Each linkbase type SHOULD be provided in a separate linkbase file, found: %(linkbasesFound)s."),
                modelObject=modelDocument.xmlRootElement, linkbasesFound=", ".join(sorted(linkbasesFound)))
            
        # check for any prohibiting dimensionArc's
        for prohibitingArcElt in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}definitionArc"):
            if (prohibitingArcElt.get("use") == "prohibited" and 
                prohibitingArcElt.get("{http://www.w3.org/1999/xlink}arcrole")  == XbrlConst.dimensionDefault):
                val.modelXbrl.error("ESEF.3.4.3.extensionTaxonomyOverridesDefaultMembers",
                    _("The extension taxonomy MUST not prohibit default members assigned to dimensions by the ESEF taxonomy."),
                    modelObject=modelDocument.xmlRootElement, linkbasesFound=", ".join(sorted(linkbasesFound)))
    
    if isExtensionDoc and filenamePattern is not None:
        m = filenamePattern.match(modelDocument.basename)
        if not m:
            val.modelXbrl.warning("ESEF.3.1.5.extensionTaxonomyDocumentNameDoesNotFollowNamingConvention",
                _("Extension taxonomy document file name SHOULD match the {base}-{date}_{suffix}.{extension} pattern."),
                modelObject=modelDocument.xmlRootElement)
        elif len(m.group(1)) > 20:
            val.modelXbrl.warning("ESEF.3.1.5.baseComponentInNameOfTaxonomyFileExceedsTwentyCharacters",
                _("Extension taxonomy document file name {base} component SHOULD be no longer than 20 characters, length is %(length)s."),
                modelObject=modelDocument.xmlRootElement, length=len(m.group(1)))
        
        
