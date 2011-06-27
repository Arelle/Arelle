'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, datetime
from arelle import (ModelDocument, ModelValue, XmlUtil, XbrlConst, UrlUtil)
from arelle.ModelObject import ModelObject

def checkDTS(val, modelDocument, visited):
    visited.append(modelDocument)
    definesLabelLinkbase = False
    for referencedDocument in modelDocument.referencesDocument.items():
        #6.07.01 no includes
        if referencedDocument[1] == "include":
            val.modelXbrl.error(
                _("Taxonomy schema {0} includes {1}, only import is allowed").format(
                    os.path.basename(modelDocument.uri), 
                    os.path.basename(referencedDocument[0].uri)), 
                "err", "EFM.6.07.01", "GFM.1.03.01", "SBR.NL.2.2.0.18")
        if referencedDocument[0] not in visited:
            checkDTS(val, referencedDocument[0], visited)
            
    if val.disclosureSystem.standardTaxonomiesDict is None:
        pass
    if (modelDocument.type == ModelDocument.Type.SCHEMA and 
        modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces and
        modelDocument.uri.startswith(val.modelXbrl.uriDir)):
        
        # check schema contents types
        if val.validateSBRNL:
            definesConcepts = False
            definesLinkroles = False
            definesArcroles = False
            definesLinkParts = False
            definesAbstractItems = False
            definesNonabstractItems = False
            definesTuples = False
            definesEnumerations = False
            definesDimensions = False
            definesDomains = False
            definesHypercubes = False
                
        # 6.7.3 check namespace for standard authority
        targetNamespaceAuthority = UrlUtil.authority(modelDocument.targetNamespace) 
        if targetNamespaceAuthority in val.disclosureSystem.standardAuthorities:
            val.modelXbrl.error(
                _("Taxonomy schema {0} namespace {1} is a disallowed authority").format(
                    os.path.basename(modelDocument.uri), 
                    modelDocument.targetNamespace), 
                "err", "EFM.6.07.03", "GFM.1.03.03")
            
        # 6.7.4 check namespace format
        if modelDocument.targetNamespace is None:
            match = None
        elif val.validateEFMorGFM:
            targetNamespaceDate = modelDocument.targetNamespace[len(targetNamespaceAuthority):]
            match = val.targetNamespaceDatePattern.match(targetNamespaceDate)
        else:
            match = None
        if match is not None:
            try:
                if match.lastindex == 3:
                    datetime.date(int(match.group(1)),int(match.group(2)),int(match.group(3)))
                elif match.lastindex == 6:
                    datetime.date(int(match.group(4)),int(match.group(5)),int(match.group(6)))
                else:
                    match = None
            except ValueError:
                match = None
        if match is None:
            val.modelXbrl.error(
                _("Taxonomy schema {0} namespace {1} must have format http://{2}authority{3}/{2}versionDate{3}").format(
                    os.path.basename(modelDocument.uri), 
                    modelDocument.targetNamespace, "{", "}"), 
                "err", "EFM.6.07.04", "GFM.1.03.04")

        if modelDocument.targetNamespace is not None:
            # 6.7.5 check prefix for _
            prefix = XmlUtil.xmlnsprefix(modelDocument.xmlRootElement,modelDocument.targetNamespace)
            if prefix and "_" in prefix:
                val.modelXbrl.error(
                    _("Taxonomy schema {0} namespace {1} prefix {2} must not have an '_'").format(
                        os.path.basename(modelDocument.uri), 
                        modelDocument.targetNamespace, 
                        prefix), 
                    "err", "EFM.6.07.07", "GFM.1.03.07")

            for eltName in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/2001/XMLSchema}element"):
                if isinstance(eltName,ModelObject):
                    # 6.7.16 name not duplicated in standard taxonomies
                    name = eltName.get("name")
                    if name is None: name = ""
                    concepts = val.modelXbrl.nameConcepts.get(name)
                    modelConcept = None
                    if concepts is not None:
                        for c in concepts:
                            if c.modelDocument == modelDocument:
                                modelConcept = c
                            elif (val.validateEFMorGFM and
                                  not c.modelDocument.uri.startswith(val.modelXbrl.uriDir)):
                                val.modelXbrl.error(
                                    _("Taxonomy schema {0} element {1} is also defined in standard taxonomy schema {2}").format(
                                        os.path.basename(modelDocument.uri),
                                        name,
                                        os.path.basename(c.modelDocument.uri)), 
                                    "err", "EFM.6.07.16", "GFM.1.03.18")
                        if val.validateSBRNL:
                            for c in concepts:
                                if c.modelDocument != modelDocument:
                                    relSet = val.modelXbrl.relationshipSet(XbrlConst.generalSpecial)
                                    if not (relSet.isRelated(modelConcept, "child", c) or relSet.isRelated(modelConcept, "child", c)):
                                        val.modelXbrl.error(
                                            _("Taxonomy schema {0} element {1} is also defined in standard taxonomy schema {2} without a general-special relationship").format(
                                                os.path.basename(modelDocument.uri),
                                                name,
                                                os.path.basename(c.modelDocument.uri)), 
                                            "err", "SBR.NL.2.2.2.02")
                    # 6.7.17 id properly formed
                    id = eltName.id
                    requiredId = (prefix if prefix is not None else "") + "_" + name
                    if val.validateEFMorGFM and id != requiredId:
                        val.modelXbrl.error(
                            _("Taxonomy schema {0} element {1} id {2} should be {3}").format(
                                os.path.basename(modelDocument.uri),
                                name, id, requiredId),
                            "err", "EFM.6.07.17", "GFM.1.03.19")
                        
                    # 6.7.18 nillable is true
                    nillable = eltName.get("nillable")
                    if nillable != "true":
                        val.modelXbrl.error(
                            _("Taxonomy schema {0} element {1} nillable {2} should be 'true'").format(
                                os.path.basename(modelDocument.uri),
                                name, nillable),
                            "err", "EFM.6.07.18", "GFM.1.03.20")
        
                    if modelConcept is not None:
                        # 6.7.19 not tuple
                        if modelConcept.isTuple:
                            if val.validateEFMorGFM:
                                val.modelXbrl.error(
                                    _("Taxonomy schema {0} element {1} is a tuple").format(
                                        os.path.basename(modelDocument.uri),
                                        name),
                                    "err", "EFM.6.07.19", "GFM.1.03.21")
                            
                        # 6.7.20 no typed domain ref
                        if modelConcept.typedDomainRefQname is not None:
                            val.modelXbrl.error(
                                _("Taxonomy schema {0} element {1} has typedDomainRef {2}").format(
                                    os.path.basename(modelDocument.uri),
                                    name,
                                    modelConcept.typedDomainRefQname),
                                "err", "EFM.6.07.20", "GFM.1.03.22")
                            
                        # 6.7.21 abstract must be duration
                        isDuration = modelConcept.periodType == "duration"
                        if modelConcept.abstract == "true" and not isDuration:
                            val.modelXbrl.error(
                                _("Taxonomy schema {0} element {1} is abstract but period type is not duration").format(
                                    os.path.basename(modelDocument.uri),
                                    name),
                                "err", "EFM.6.07.21", "GFM.1.03.23")
                            
                        # 6.7.22 abstract must be stringItemType
                        ''' removed SEC EFM v.17, Edgar release 10.4, and GFM 2011-04-08
                        if modelConcept.abstract == "true" and modelConcept.typeQname != XbrlConst. qnXbrliStringItemType:
                            val.modelXbrl.error(
                                _("Taxonomy schema {0} element {1} is abstract but type is not xbrli:stringItemType").format(
                                    os.path.basename(modelDocument.uri),
                                    name),
                                "err", "EFM.6.07.22", "GFM.1.03.24")
    					'''
                        substititutionGroupQname = modelConcept.substitutionGroupQname
                        # 6.7.23 Axis must be subs group dimension
                        if name.endswith("Axis") ^ (substititutionGroupQname == XbrlConst.qnXbrldtDimensionItem):
                            val.modelXbrl.error(
                                _("Taxonomy schema {0} element {1} must end in Axis to be in dimensionItem substitution group").format(
                                    os.path.basename(modelDocument.uri),
                                    name),
                                "err", "EFM.6.07.23", "GFM.1.03.25")
    
                        # 6.7.24 Table must be subs group hypercube
                        if name.endswith("Table") ^ (substititutionGroupQname == XbrlConst.qnXbrldtHypercubeItem):
                            val.modelXbrl.error(
                                _("Taxonomy schema {0} element {1} is an Axis but not in hypercubeItem substitution group").format(
                                    os.path.basename(modelDocument.uri),
                                    name),
                                "err", "EFM.6.07.24", "GFM.1.03.26")
    
                        # 6.7.25 if neither hypercube or dimension, substitution group must be item
                        if substititutionGroupQname not in (None,
                                                            XbrlConst.qnXbrldtDimensionItem, 
                                                            XbrlConst.qnXbrldtHypercubeItem,
                                                            XbrlConst.qnXbrliItem):                           
                            val.modelXbrl.error(
                                _("Taxonomy schema {0} element {1} has disallowed substitution group {2}").format(
                                    os.path.basename(modelDocument.uri),
                                    name, modelConcept.substitutionGroupQname),
                                "err", "EFM.6.07.25", "GFM.1.03.27")
                            
                        # 6.7.26 Table must be subs group hypercube
                        if name.endswith("LineItems") and modelConcept.abstract != "true":
                            val.modelXbrl.error(
                                _("Taxonomy schema {0} element {1} is a LineItems but not abstract").format(
                                    os.path.basename(modelDocument.uri),
                                    name),
                                "err", "EFM.6.07.26", "GFM.1.03.28")
    
                        # 6.7.27 type domainMember must end with Domain or Member
                        conceptType = modelConcept.type
                        isDomainItemType = conceptType is not None and conceptType.isDomainItemType
                        endsWithDomainOrMember = name.endswith("Domain") or name.endswith("Member")
                        if isDomainItemType != endsWithDomainOrMember:
                            val.modelXbrl.error(
                                _("Taxonomy schema {0} element {1} must end with Domain or Member for type of domainItemType").format(
                                    os.path.basename(modelDocument.uri),
                                    name),
                                "err", "EFM.6.07.27", "GFM.1.03.29")
    
                        # 6.7.28 domainItemType must be duration
                        if isDomainItemType and not isDuration:
                            val.modelXbrl.error(
                                _("Taxonomy schema {0} element {1} is a domainItemType and must be periodType duration").format(
                                    os.path.basename(modelDocument.uri),
                                    name),
                                "err", "EFM.6.07.28", "GFM.1.03.30")
                        
                        if val.validateSBRNL:
                            definesConcepts = True
                            if modelConcept.isTuple:
                                definesTuples = True
                                if modelConcept.abstract == "true":
                                    val.modelXbrl.error(
                                        _("Taxonomy schema {0} element {1} is an abstract tuple").format(
                                            os.path.basename(modelDocument.uri), modelConcept.qname), 
                                        "err", "SBR.NL.2.2.2.03")
                                if tupleCycle(val,modelConcept):
                                    val.modelXbrl.error(
                                        _("Taxonomy schema {0} tuple {1} has a tuple cycle").format(
                                            os.path.basename(modelDocument.uri), modelConcept.qname), 
                                        "err", "SBR.NL.2.2.2.07")
                                if modelConcept.nillable != "false" and modelConcept.isRoot:
                                    val.modelXbrl.error(
                                        _("Taxonomy schema {0} tuple {1} must have nillable='false'").format(
                                            os.path.basename(modelDocument.uri), modelConcept.qname), 
                                        "err", "SBR.NL.2.2.2.17")
                            if modelConcept.abstract == "true":
                                if modelConcept.isRoot:
                                    if modelConcept.nillable != "false":
                                        val.modelXbrl.error(
                                            _("Taxonomy schema {0} abstract root concept {1} must have nillable='false'").format(
                                                os.path.basename(modelDocument.uri), modelConcept.qname), 
                                            "err", "SBR.NL.2.2.2.16")
                                    if modelConcept.typeQname != XbrlConst.qnXbrliStringItemType:
                                        val.modelXbrl.error(
                                            _("Taxonomy schema {0} abstract root concept {1} must have type='xbrli:stringItemType'").format(
                                                os.path.basename(modelDocument.uri), modelConcept.qname), 
                                            "err", "SBR.NL.2.2.2.21")
                                else: # not root
                                    if modelConcept.isItem:
                                        val.modelXbrl.error(
                                            _("Taxonomy schema {0} abstract item {1} must not be a child of a tuple").format(
                                                os.path.basename(modelDocument.uri), modelConcept.qname), 
                                            "err", "SBR.NL.2.2.2.31")
                                if modelConcept.balance:
                                    val.modelXbrl.error(
                                        _("Taxonomy schema {0} abstract concept {1} must not have a balance attribute").format(
                                            os.path.basename(modelDocument.uri), modelConcept.qname), 
                                        "err", "SBR.NL.2.2.2.22")
                                if modelConcept.isTuple:
                                    val.modelXbrl.error(
                                        _("Taxonomy schema {0} tuple {1} must not be abstract").format(
                                            os.path.basename(modelDocument.uri), modelConcept.qname), 
                                        "err", "SBR.NL.2.2.2.31")
                                if modelConcept.isHypercubeItem:
                                    definesHypercubes = True
                                elif modelConcept.isDimensionItem:
                                    definesDimensions = True
                                elif substititutionGroupQname.localName == "domainItem":
                                    definesDomains = True
                                elif modelConcept.isItem:
                                    definesAbstractItems = True
                            else:   # not abstract
                                if not (modelConcept.label(preferredLabel=XbrlConst.documentationLabel,fallbackToQname=False,lang="nl") or
                                        val.modelXbrl.relationshipSet(XbrlConst.conceptReference).fromModelObject(c)):
                                    val.modelXbrl.error(
                                        _("Taxonomy schema {0} {1} must have a documentation label or reference").format(
                                            os.path.basename(modelDocument.uri), modelConcept.qname), 
                                        "err", "SBR.NL.2.2.2.28")
                            if modelConcept.balance and not modelConcept.instanceOfType(XbrlConst.qnXbrliMonetaryItemType):
                                val.modelXbrl.error(
                                    _("Taxonomy schema {0} non-monetary concept {1} must not have a balance attribute").format(
                                        os.path.basename(modelDocument.uri), modelConcept.qname), 
                                    "err", "SBR.NL.2.2.2.24")
                            if not modelConcept.label(fallbackToQname=False,lang="nl"):
                                val.modelXbrl.error(
                                    _("Taxonomy schema {0} {1} must have a standard label in language 'nl'").format(
                                        os.path.basename(modelDocument.uri), modelConcept.qname), 
                                    "err", "SBR.NL.2.2.2.26")
                            if not modelConcept.isRoot:    # tuple child
                                if modelConcept.element.get("maxOccurs") is not None and modelConcept.element.get("maxOccurs") != "1":
                                    val.modelXbrl.error(
                                        _("Taxonomy schema {0} tuple concept {1} must have maxOccurs='1'").format(
                                            os.path.basename(modelDocument.uri), modelConcept.qname), 
                                        "err", "SBR.NL.2.2.2.30")
                            if modelConcept.isLinkPart:
                                definesLinkParts = True
                                val.modelXbrl.error(
                                    _("Taxonomy schema {0} link:part concept {1} is not allowed").format(
                                        os.path.basename(modelDocument.uri), modelConcept.qname), 
                                    "err", "SBR.NL.2.2.5.01")
                            if modelConcept.isTypedDimension:
                                domainElt = modelConcept.typedDomainElement
                                if domainElt is not None and domainElt.localName == "complexType":
                                    val.modelXbrl.error(
                                        _("Taxonomy schema {0} typed dimension {1} domain element {2} has disallowed complex content").format(
                                            os.path.basename(modelDocument.uri), modelConcept.qname, domainElt.qname), 
                                        "err", "SBR.NL.2.2.8.02")

        # 6.7.8 check for embedded linkbase
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}linkbase"):
            if isinstance(e,ModelObject):
                val.modelXbrl.error(
                    _("Taxonomy schema {0} contains an embedded linkbase").format(
                        os.path.basename(modelDocument.uri)), 
                    "err", "EFM.6.07.08", "GFM.1.03.08")
                break

        requiredUsedOns = {XbrlConst.qnLinkPresentationLink,
                           XbrlConst.qnLinkCalculationLink,
                           XbrlConst.qnLinkDefinitionLink}

        # 6.7.9 role types authority
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}roleType"):
            if isinstance(e,ModelObject):
                roleURI = e.get("roleURI")
                if targetNamespaceAuthority != UrlUtil.authority(roleURI):
                    val.modelXbrl.error(
                        _("Taxonomy schema {0} roleType {1} does not match authority {2}").format(
                            os.path.basename(modelDocument.uri),
                            roleURI,
                            targetNamespaceAuthority), 
                        "err", "EFM.6.07.09", "GFM.1.03.09")
                # 6.7.9 end with .../role/lc3 name
                if not val.roleTypePattern.match(roleURI):
                    val.modelXbrl.error(
                        _("Taxonomy schema {0} roleType {1} should end with /role/{2}LC3name{3}").format(
                            os.path.basename(modelDocument.uri),
                            roleURI, '{', '}'), 
                        "wrn", "EFM.6.07.09", "GFM.1.03.09")
                    
                # 6.7.10 only one role type declaration in DTS
                modelRoleTypes = val.modelXbrl.roleTypes.get(roleURI)
                if modelRoleTypes is not None:
                    if len(modelRoleTypes) > 1:
                        val.modelXbrl.error(
                            _("Taxonomy schema {0} roleType {1} is defined in multiple taxonomies").format(
                                os.path.basename(modelDocument.uri),
                                roleURI), 
                            "err", "EFM.6.07.10", "GFM.1.03.10")
                    elif len(modelRoleTypes) == 1:
                        # 6.7.11 used on's for pre, cal, def if any has a used on
                        usedOns = modelRoleTypes[0].usedOns
                        if not usedOns.isdisjoint(requiredUsedOns) and len(requiredUsedOns - usedOns) > 0:
                            val.modelXbrl.error(
                                _("Taxonomy schema {0} roleType {1} missing used on {2}").format(
                                    os.path.basename(modelDocument.uri),
                                    roleURI,
                                    requiredUsedOns - usedOns), 
                                "err", "EFM.6.07.11", "GFM.1.03.11")
                            
                        # 6.7.12 definition match pattern
                        definition = modelRoleTypes[0].definitionNotStripped
                        if (val.disclosureSystem.roleDefinitionPattern is not None and
                            (definition is None or not val.disclosureSystem.roleDefinitionPattern.match(definition))):
                            val.modelXbrl.error(
                                _("Taxonomy schema {0} roleType {1} definition \"{2}\" must match {3}Sortcode{4} - {3}Type{4} - {3}Title{4}").format(
                                    os.path.basename(modelDocument.uri),
                                    roleURI, definition, '{', '}'), 
                                "err", "EFM.6.07.12", "GFM.1.03.12-14")
                        
                    if val.validateSBRNL and (usedOns & XbrlConst.standardExtLinkQnames):
                        definesLinkroles = True

        # 6.7.13 arcrole types authority
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/1999/xlink}arcroleType"):
            if isinstance(e,ModelObject):
                arcroleURI = e.get("arcroleURI")
                if targetNamespaceAuthority != UrlUtil.authority(arcroleURI):
                    val.modelXbrl.error(
                        _("Taxonomy schema {0} arcroleType {1} does not match authority {2}").format(
                            os.path.basename(modelDocument.uri),
                            arcroleURI,
                            targetNamespaceAuthority), 
                        "err", "EFM.6.07.13", "GFM.1.03.15")
                # 6.7.13 end with .../arcrole/lc3 name
                if not val.arcroleTypePattern.match(arcroleURI):
                    val.modelXbrl.error(
                        _("Taxonomy schema {0} arcroleType {1} should end with /arcrole/{2}LC3name{3}").format(
                            os.path.basename(modelDocument.uri),
                            arcroleURI, '{', '}'), 
                        "wrn", "EFM.6.07.13", "GFM.1.03.15")
                    
                # 6.7.14 only one arcrole type declaration in DTS
                modelRoleTypes = val.modelXbrl.arcroleTypes[arcroleURI]
                if len(modelRoleTypes) > 1:
                    val.modelXbrl.error(
                        _("Taxonomy schema {0} arcroleType {1} is defined in multiple taxonomies").format(
                            os.path.basename(modelDocument.uri),
                            arcroleURI), 
                        "err", "EFM.6.07.14", "GFM.1.03.16")
                    
                # 6.7.15 definition match pattern
                definition = modelRoleTypes[0].definition
                if definition is None or not val.arcroleDefinitionPattern.match(definition):
                    val.modelXbrl.error(
                        _("Taxonomy schema {0} arcroleType {1} definition must be non-empty").format(
                            os.path.basename(modelDocument.uri),
                            arcroleURI, '{', '}'), 
                        "err", "EFM.6.07.15", "GFM.1.03.17")
    
                if val.validateSBRNL:
                    definesArcroles = True
        if val.validateSBRNL and (definesLinkroles + definesArcroles + definesLinkParts +
                                  definesAbstractItems + definesNonabstractItems + definesTuples +
                                  definesEnumerations + definesDimensions + definesDomains + 
                                  definesHypercubes) > 1:
            schemaContents = []
            if definesLinkroles: schemaContents.append(_("linkroles"))
            if definesArcroles: schemaContents.append(_("arcroles"))
            if definesLinkParts: schemaContents.append(_("link parts"))
            if definesAbstractItems: schemaContents.append(_("abstract items"))
            if definesNonabstractItems: schemaContents.append(_("nonabstract items"))
            if definesTuples: schemaContents.append(_("tuples"))
            if definesEnumerations: schemaContents.append(_("enumerations"))
            if definesDimensions: schemaContents.append(_("dimensions"))
            if definesDomains: schemaContents.append(_("domains"))
            if definesHypercubes: schemaContents.append(_("hypercubes"))
            val.modelXbrl.error(
                _("Taxonomy schema {0} may only define one of these: {1}").format(
                    os.path.basename(modelDocument.uri), ', '.join(schemaContents)), 
                "err", "SBR.NL.2.2.1.01")

    visited.remove(modelDocument)
    
def tupleCycle(val, concept, ancestorTuples=None):
    if ancestorTuples is None: ancestorTuples = set()
    if concept in ancestorTuples:
        return True
    ancestorTuples.add(concept)
    for elementQname in concept.type.elements:
        childConcept = val.modelXbrl.qnameConcepts.get(elementQname)
        if childConcept is not None and tupleCycle(val, childConcept, ancestorTuples):
            return True
    ancestorTuples.discard(concept)
    return False
