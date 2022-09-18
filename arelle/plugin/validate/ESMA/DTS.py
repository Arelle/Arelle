'''
Created on June 6, 2018

Filer Guidelines: esma32-60-254_esef_reporting_manual.pdf

Taxonomy Architecture: 

Taxonomy package expected to be installed: 

@author: Mark V Systems Limited
(c) Copyright 2018 Mark V Systems Limited, All rights reserved.
'''

import re
from arelle import ModelDocument, XbrlConst
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelObject import ModelObject
from .Const import qnDomainItemType, standardTaxonomyURIs

def checkFilingDTS(val, modelDocument, visited):
    visited.append(modelDocument)
    for referencedDocument, modelDocumentReference in modelDocument.referencesDocument.items():
        if referencedDocument not in visited and referencedDocument.inDTS: # ignore non-DTS documents
            checkFilingDTS(val, referencedDocument, visited)
            
    if (modelDocument.type == ModelDocument.Type.SCHEMA and 
        (modelDocument.uri.startswith(val.modelXbrl.uriDir) or
         not any(modelDocument.uri.startswith(standardTaxonomyURI) for standardTaxonomyURI in standardTaxonomyURIs))):
        
        val.hasExtensionSchema = True
        
        tuplesInExtTxmy = []
        typedDimsInExtTxmy = []
        domainMembersWrongType = []
        extLineItemsWithoutHypercube = []
        extAbstractConcepts = []
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
                    if modelConcept.isTypedDimension:
                        typedDimsInExtTxmy.append(modelConcept)
                    if modelConcept.isDomainMember and modelConcept in val.domainMembers and modelConcept.typeQname != qnDomainItemType:
                        domainMembersWrongType.append(modelConcept)
                    if modelConcept.isPrimaryItem and not modelConcept.isAbstract and modelConcept not in val.primaryItems:
                        extLineItemsWithoutHypercube.append(modelConcept)
                    if modelConcept.isAbstract and modelConcept not in val.domainMembers:
                        extAbstractConcepts.append(modelConcept)
                    # what is language of standard label?
                    label = modelConcept.label(lang="en", fallbackToQname=False)
                    if label:
                        # allow Joe's Bar, N.A.  to be JoesBarNA -- remove ', allow A. as not article "a"
                        lc3name = ''.join(re.sub(r"['.-]", "", (w[0] or w[2] or w[3] or w[4])).title()
                                          for w in re.findall(r"((\w+')+\w+)|(A[.-])|([.-]A(?=\W|$))|(\w+)", label)
                                          # if w[4].lower() not in ("the", "a", "an")
                                          )
                        if not(name == lc3name or 
                               (name and lc3name and lc3name[0].isdigit() and name[1:] == lc3name and (name[0].isalpha() or name[0] == '_'))):
                            val.modelXbrl.warning("esma.3.2.1.extensionTaxonomyElementNameDoesNotFollowLc3Convention",
                                _("Extension taxonomy element name SHOULD follow the LC3 convention: %(concept)s should match expected LC3 composition %(lc3name)s"),
                                modelObject=modelConcept, concept=modelConcept.qname, lc3name=lc3name)
                            
        if tuplesInExtTxmy:
            val.modelXbrl.error("esma.2.1.3.tupleDefinedInExtensionTaxonomy",
                _("Tuples MUST NOT be defined in extension taxonomy: %(concepts)s"),
                modelObject=tuplesInExtTxmy, concepts=", ".join(str(c.qname) for c in tuplesInExtTxmy))
        if typedDimsInExtTxmy:
            val.modelXbrl.warning("esma.3.2.3.typedDimensionDefinitionInExtensionTaxonomy",
                _("Extension taxonomy SHOULD NOT define typed dimensions: %(concepts)s."),
                modelObject=typedDimsInExtTxmy, concepts=", ".join(str(c.qname) for c in typedDimsInExtTxmy))
        if domainMembersWrongType:
            val.modelXbrl.error("esma.3.2.2.domainMemberWrongDataType",
                _("Domain members MUST have domainItemType data type as defined in \"http://www.xbrl.org/dtr/type/nonNumeric-2009-12-16.xsd\": concept %(concepts)s."),
                modelObject=domainMembersWrongType, concepts=", ".join(str(c.qname) for c in domainMembersWrongType))
        if extLineItemsWithoutHypercube:
            val.modelXbrl.error("esma.3.4.1.extensionTaxonomyLineItemNotLinkedToAnyHypercube",
                _("Line items that do not require any dimensional information to tag data MUST be linked to \"Line items not dimensionally qualified\" hypercube in http://www.esma.europa.eu/xbrl/esef/role/esef_role-999999 declared in esef_cor.xsd: concept %(concepts)s."),
                modelObject=extLineItemsWithoutHypercube, concepts=", ".join(str(c.qname) for c in extLineItemsWithoutHypercube))
        if extAbstractConcepts:
            val.modelXbrl.warning("esma.3.2.5.abstractConceptDefinitionInExtensionTaxonomy",
                _("Extension taxonomy SHOULD NOT define abstract concepts: concept %(concepts)s."),
                modelObject=extAbstractConcepts, concepts=", ".join(str(c.qname) for c in extAbstractConcepts))
            

        embeddedLinkbaseElements = [e
                                    for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}linkbase")
                                    if isinstance(e,ModelObject)]
        if embeddedLinkbaseElements:
                val.modelXbrl.error("esma.3.1.1.linkbasesNotSeparateFiles",
                    _("Each linkbase type SHOULD be provided in a separate linkbase file, but a linkbase was found in %(schema)s."),
                    modelObject=embeddedLinkbaseElements, schema=modelDocument.basename)
                            
    if (modelDocument.type == ModelDocument.Type.LINKBASE and 
        (modelDocument.uri.startswith(val.modelXbrl.uriDir) or
         not any(modelDocument.uri.startswith(standardTaxonomyURI) for standardTaxonomyURI in standardTaxonomyURIs))):
        
        linkbasesFound = set()
        
        for linkEltName in ("labelLink", "presentationLink", "calculationLink", "definitionLink"):
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
        if len(linkbasesFound) > 1:
            val.modelXbrl.error("esma.3.1.1.extensionTaxonomyWrongFilesStructure",
                _("Each linkbase type SHOULD be provided in a separate linkbase file, found: %(linkbasesFound)s."),
                modelObject=modelDocument.xmlRootElement, linkbasesFound=", ".join(sorted(linkbasesFound)))
            
        # check for any prohibiting dimensionArc's
        for prohibitingArcElt in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}definitionArc"):
            if (prohibitingArcElt.get("use") == "prohibited" and 
                prohibitingArcElt.get("{http://www.w3.org/1999/xlink}arcrole")  == XbrlConst.dimensionDefault):
                val.modelXbrl.error("esma.3.4.3.extensionTaxonomyOverridesDefaultMembers",
                    _("The extension taxonomy MUST not modify (prohibit and/or override) default members assigned to dimensions by the ESEF taxonomy."),
                    modelObject=modelDocument.xmlRootElement, linkbasesFound=", ".join(sorted(linkbasesFound)))
                
        
