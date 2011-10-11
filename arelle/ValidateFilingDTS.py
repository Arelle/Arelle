'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, datetime, re
from arelle import (ModelDocument, ModelValue, XmlUtil, XbrlConst, UrlUtil)
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelConcept

targetNamespaceDatePattern = None
roleTypePattern = None
arcroleTypePattern = None
arcroleDefinitionPattern = None

def checkDTS(val, modelDocument, visited):
    global targetNamespaceDatePattern, roleTypePattern, arcroleTypePattern, arcroleDefinitionPattern
    if targetNamespaceDatePattern is None:
        targetNamespaceDatePattern = re.compile(r"/([12][0-9]{3})-([01][0-9])-([0-3][0-9])|"
                                            r"/([12][0-9]{3})([01][0-9])([0-3][0-9])|")
        roleTypePattern = re.compile(r".*/role/[^/]+")
        arcroleTypePattern = re.compile(r".*/arcrole/[^/]+")
        arcroleDefinitionPattern = re.compile(r"^.*[^\\s]+.*$")  # at least one non-whitespace character
        
    visited.append(modelDocument)
    definesLabelLinkbase = False
    for referencedDocument in modelDocument.referencesDocument.items():
        #6.07.01 no includes
        if referencedDocument[1] == "include":
            val.modelXbrl.error(("EFM.6.07.01", "GFM.1.03.01", "SBR.NL.2.2.0.18"),
                _("Taxonomy schema %(schema)s includes %(include)s, only import is allowed"),
                modelObject=modelDocument,
                    schema=os.path.basename(modelDocument.uri), 
                    include=os.path.basename(referencedDocument[0].uri))
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
            val.modelXbrl.error(("EFM.6.07.03", "GFM.1.03.03"),
                _("Taxonomy schema %(schema)s namespace %(targetNamespace)s is a disallowed authority"),
                modelObject=modelDocument, schema=os.path.basename(modelDocument.uri), targetNamespace=modelDocument.targetNamespace)
            
        # 6.7.4 check namespace format
        if modelDocument.targetNamespace is None:
            match = None
        elif val.validateEFMorGFM:
            targetNamespaceDate = modelDocument.targetNamespace[len(targetNamespaceAuthority):]
            match = targetNamespaceDatePattern.match(targetNamespaceDate)
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
            val.modelXbrl.error(("EFM.6.07.04", "GFM.1.03.04"),
                _("Taxonomy schema %(schema)s namespace %(targetNamespace)s must have format http://{authority}/{versionDate}"),
                modelObject=modelDocument, schema=os.path.basename(modelDocument.uri), targetNamespace=modelDocument.targetNamespace)

        if modelDocument.targetNamespace is not None:
            # 6.7.5 check prefix for _
            prefix = XmlUtil.xmlnsprefix(modelDocument.xmlRootElement,modelDocument.targetNamespace)
            if prefix and "_" in prefix:
                val.modelXbrl.error(("EFM.6.07.07", "GFM.1.03.07"),
                    _("Taxonomy schema %(schema)s namespace %(targetNamespace)s prefix %(prefix)s must not have an '_'"),
                    modelObject=modelDocument, schema=os.path.basename(modelDocument.uri), targetNamespace=modelDocument.targetNamespace, prefix=prefix)

            for modelConcept in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/2001/XMLSchema}element"):
                if isinstance(modelConcept,ModelConcept):
                    # 6.7.16 name not duplicated in standard taxonomies
                    name = modelConcept.get("name")
                    if name is None: 
                        name = ""
                    concepts = val.modelXbrl.nameConcepts.get(name)
                    if concepts is not None:
                        for c in concepts:
                            if c.modelDocument != modelDocument:
                                if (val.validateEFMorGFM and
                                      not c.modelDocument.uri.startswith(val.modelXbrl.uriDir)):
                                    val.modelXbrl.error(("EFM.6.07.16", "GFM.1.03.18"),
                                        _("Concept %(concept)s is also defined in standard taxonomy schema schema %(standardSchema)s"),
                                        modelObject=c, concept=modelConcept.qname, standardSchema=os.path.basename(c.modelDocument.uri))
                                elif val.validateSBRNL and c.modelDocument != modelDocument:
                                        relSet = val.modelXbrl.relationshipSet(XbrlConst.generalSpecial)
                                        if not (relSet.isRelated(modelConcept, "child", c) or relSet.isRelated(modelConcept, "child", c)):
                                            val.modelXbrl.error("SBR.NL.2.2.2.02",
                                                _("Concept %(concept)s is also defined in standard taxonomy schema %(standardSchema)s without a general-special relationship"),
                                                modelObject=c, concept=modelConcept.qname, standardSchema=os.path.basename(c.modelDocument.uri))
                    # 6.7.17 id properly formed
                    id = modelConcept.id
                    requiredId = (prefix if prefix is not None else "") + "_" + name
                    if val.validateEFMorGFM and id != requiredId:
                        val.modelXbrl.error(("EFM.6.07.17", "GFM.1.03.19"),
                            _("Concept %(concept)s id %(id)s should be $(requiredId)s"),
                            modelObject=modelConcept, concept=modelConcept.qname, id=id, requiredId=requiredId)
                        
                    # 6.7.18 nillable is true
                    nillable = modelConcept.get("nillable")
                    if nillable != "true":
                        val.modelXbrl.error(("EFM.6.07.18", "GFM.1.03.20"),
                            _("Taxonomy schema %(schema)s element %(concept)s nillable %(nillable)s should be 'true'"),
                            modelObject=modelConcept, schema=os.path.basename(modelDocument.uri),
                            concept=name, nillable=nillable)
        
                    if modelConcept is not None:
                        # 6.7.19 not tuple
                        if modelConcept.isTuple:
                            if val.validateEFMorGFM:
                                val.modelXbrl.error(("EFM.6.07.19", "GFM.1.03.21"),
                                    _("Concept %(concept)s is a tuple"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            
                        # 6.7.20 no typed domain ref
                        if modelConcept.isTypedDimension:
                            val.modelXbrl.error(("EFM.6.07.20", "GFM.1.03.22"),
                                _("Concept %(concept)s has typedDomainRef %(typedDomainRef)s"),
                                modelObject=modelConcept, concept=modelConcept.qname,
                                typedDomainRef=modelConcept.typedDomainElement.qname if modelConcept.typedDomainElement is not None else modelConcept.typedDomainRef)
                            
                        # 6.7.21 abstract must be duration
                        isDuration = modelConcept.periodType == "duration"
                        if modelConcept.abstract == "true" and not isDuration:
                            val.modelXbrl.error(("EFM.6.07.21", "GFM.1.03.23"),
                                _("Taxonomy schema %(schema)s element %(concept)s is abstract but period type is not duration"),
                                modelObject=modelConcept, schema=os.path.basename(modelDocument.uri), concept=name)
                            
                        # 6.7.22 abstract must be stringItemType
                        ''' removed SEC EFM v.17, Edgar release 10.4, and GFM 2011-04-08
                        if modelConcept.abstract == "true" and modelConcept.typeQname != XbrlConst. qnXbrliStringItemType:
                            val.modelXbrl.error(("EFM.6.07.22", "GFM.1.03.24"),
                                _("Concept %(concept)s  is abstract but type is not xbrli:stringItemType"),
                                modelObject=modelConcept, concept=modelConcept.qname)
    					'''
                        substititutionGroupQname = modelConcept.substitutionGroupQname
                        # 6.7.23 Axis must be subs group dimension
                        if name.endswith("Axis") ^ (substititutionGroupQname == XbrlConst.qnXbrldtDimensionItem):
                            val.modelXbrl.error(("EFM.6.07.23", "GFM.1.03.25"),
                                _("Concept %(concept)s must end in Axis to be in dimensionItem substitution group"),
                                modelObject=modelConcept, concept=modelConcept.qname)
    
                        # 6.7.24 Table must be subs group hypercube
                        if name.endswith("Table") ^ (substititutionGroupQname == XbrlConst.qnXbrldtHypercubeItem):
                            val.modelXbrl.error(("EFM.6.07.24", "GFM.1.03.26"),
                                _("Concept %(concept)s is an Axis but not in hypercubeItem substitution group"),
                                modelObject=modelConcept, schema=os.path.basename(modelDocument.uri), concept=modelConcept.qname)
    
                        # 6.7.25 if neither hypercube or dimension, substitution group must be item
                        if substititutionGroupQname not in (None,
                                                            XbrlConst.qnXbrldtDimensionItem, 
                                                            XbrlConst.qnXbrldtHypercubeItem,
                                                            XbrlConst.qnXbrliItem):                           
                            val.modelXbrl.error(("EFM.6.07.25", "GFM.1.03.27"),
                                _("Concept %(concept)s has disallowed substitution group %(substitutionGroup)s"),
                                modelObject=modelConcept, concept=modelConcept.qname,
                                substitutionGroup=modelConcept.substitutionGroupQname)
                            
                        # 6.7.26 Table must be subs group hypercube
                        if name.endswith("LineItems") and modelConcept.abstract != "true":
                            val.modelXbrl.error(("EFM.6.07.26", "GFM.1.03.28"),
                                _("Concept %(concept)s is a LineItems but not abstract"),
                                modelObject=modelConcept, concept=modelConcept.qname)
    
                        # 6.7.27 type domainMember must end with Domain or Member
                        conceptType = modelConcept.type
                        isDomainItemType = conceptType is not None and conceptType.isDomainItemType
                        endsWithDomainOrMember = name.endswith("Domain") or name.endswith("Member")
                        if isDomainItemType != endsWithDomainOrMember:
                            val.modelXbrl.error(("EFM.6.07.27", "GFM.1.03.29"),
                                _("Concept %(concept)s must end with Domain or Member for type of domainItemType"),
                                modelObject=modelConcept, concept=modelConcept.qname)
    
                        # 6.7.28 domainItemType must be duration
                        if isDomainItemType and not isDuration:
                            val.modelXbrl.error(("EFM.6.07.28", "GFM.1.03.30"),
                                _("Concept %(concept)s is a domainItemType and must be periodType duration"),
                                modelObject=modelConcept, concept=modelConcept.qname)
                        
                        if val.validateSBRNL:
                            definesConcepts = True
                            if modelConcept.isTuple:
                                definesTuples = True
                                if modelConcept.abstract == "true":
                                    val.modelXbrl.error("SBR.NL.2.2.2.03",
                                        _("Concept %(concept)s is an abstract tuple"),
                                        modelObject=modelConcept, concept=modelConcept.qname)
                                if tupleCycle(val,modelConcept):
                                    val.modelXbrl.error("SBR.NL.2.2.2.07",
                                        _("Tuple %(concept)s has a tuple cycle"),
                                        modelObject=modelConcept, concept=modelConcept.qname)
                                if modelConcept.nillable != "false" and modelConcept.isRoot:
                                    val.modelXbrl.error("SBR.NL.2.2.2.17",
                                        _("Tuple %(concept)s must have nillable='false'"),
                                        modelObject=modelConcept, concept=modelConcept.qname)
                            if modelConcept.abstract == "true":
                                if modelConcept.isRoot:
                                    if modelConcept.nillable != "false":
                                        val.modelXbrl.error("SBR.NL.2.2.2.16",
                                            _("Abstract root concept %(concept)s must have nillable='false'"),
                                        modelObject=modelConcept, concept=modelConcept.qname)
                                    if modelConcept.typeQname != XbrlConst.qnXbrliStringItemType:
                                        val.modelXbrl.error("SBR.NL.2.2.2.21",
                                            _("Abstract root concept %(concept)s must have type='xbrli:stringItemType'"),
                                        modelObject=modelConcept, concept=modelConcept.qname)
                                else: # not root
                                    if modelConcept.isItem:
                                        val.modelXbrl.error("SBR.NL.2.2.2.31",
                                            _("Taxonomy schema {0} abstract item %(concept)s must not be a child of a tuple"),
                                            modelObject=modelConcept, concept=modelConcept.qname)
                                if modelConcept.balance:
                                    val.modelXbrl.error("SBR.NL.2.2.2.22",
                                        _("Abstract concept %(concept)s must not have a balance attribute"),
                                        modelObject=modelConcept, concept=modelConcept.qname)
                                if modelConcept.isTuple:
                                    val.modelXbrl.error("SBR.NL.2.2.2.31",
                                        _("Tuple %(concept)s must not be abstract"),
                                        modelObject=modelConcept, concept=modelConcept.qname)
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
                                    val.modelXbrl.error("SBR.NL.2.2.2.28",
                                        _("Concept %(concept)s must have a documentation label or reference"),
                                        modelObject=modelConcept, concept=modelConcept.qname)
                            if modelConcept.balance and not modelConcept.instanceOfType(XbrlConst.qnXbrliMonetaryItemType):
                                val.modelXbrl.error("SBR.NL.2.2.2.24",
                                    _("Non-monetary concept %(concept)s must not have a balance attribute"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if not modelConcept.label(fallbackToQname=False,lang="nl"):
                                val.modelXbrl.error("SBR.NL.2.2.2.26",
                                    _("Concept %(concept)s must have a standard label in language 'nl'"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if not modelConcept.isRoot:    # tuple child
                                if modelConcept.get("maxOccurs") is not None and modelConcept.get("maxOccurs") != "1":
                                    val.modelXbrl.error("SBR.NL.2.2.2.30",
                                        _("Tuple concept %(concept)s must have maxOccurs='1'"),
                                        modelObject=modelConcept, concept=modelConcept.qname)
                            if modelConcept.isLinkPart:
                                definesLinkParts = True
                                val.modelXbrl.error("SBR.NL.2.2.5.01",
                                    _("Link:part concept %(concept)s is not allowed"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if modelConcept.isTypedDimension:
                                domainElt = modelConcept.typedDomainElement
                                if domainElt is not None and domainElt.localName == "complexType":
                                    val.modelXbrl.error("SBR.NL.2.2.8.02",
                                        _("Typed dimension %(concept)s domain element %(typedDomainElement)s has disallowed complex content"),
                                        modelObject=modelConcept, concept=modelConcept.qname,
                                        typedDomainElement=domainElt.qname)

        # 6.7.8 check for embedded linkbase
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}linkbase"):
            if isinstance(e,ModelObject):
                val.modelXbrl.error(("EFM.6.07.08", "GFM.1.03.08"),
                    _("Taxonomy schema %(schema)s contains an embedded linkbase"),
                    modelObject=e, schema=os.path.basename(modelDocument.uri))
                break

        requiredUsedOns = {XbrlConst.qnLinkPresentationLink,
                           XbrlConst.qnLinkCalculationLink,
                           XbrlConst.qnLinkDefinitionLink}

        # 6.7.9 role types authority
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}roleType"):
            if isinstance(e,ModelObject):
                roleURI = e.get("roleURI")
                if targetNamespaceAuthority != UrlUtil.authority(roleURI):
                    val.modelXbrl.error(("EFM.6.07.09", "GFM.1.03.09"),
                        _("RoleType %(roleType)s does not match authority %(targetNamespaceAuthority)s"),
                        modelObject=e, roleType=roleURI, targetNamespaceAuthority=targetNamespaceAuthority)
                # 6.7.9 end with .../role/lc3 name
                if not roleTypePattern.match(roleURI):
                    val.modelXbrl.warning(("EFM.6.07.09", "GFM.1.03.09"),
                        "RoleType %(roleType)s should end with /role/{LC3name}",
                        modelObject=e, roleType=roleURI)
                    
                # 6.7.10 only one role type declaration in DTS
                modelRoleTypes = val.modelXbrl.roleTypes.get(roleURI)
                if modelRoleTypes is not None:
                    if len(modelRoleTypes) > 1:
                        val.modelXbrl.error(("EFM.6.07.10", "GFM.1.03.10"),
                            _("RoleType %(roleType)s is defined in multiple taxonomies"),
                            modelObject=e, roleType=roleURI)
                    elif len(modelRoleTypes) == 1:
                        # 6.7.11 used on's for pre, cal, def if any has a used on
                        usedOns = modelRoleTypes[0].usedOns
                        if not usedOns.isdisjoint(requiredUsedOns) and len(requiredUsedOns - usedOns) > 0:
                            val.modelXbrl.error(("EFM.6.07.11", "GFM.1.03.11"),
                                _("RoleType %(roleType)s missing used on %(usedOn)s"),
                                modelObject=e, roleType=roleURI, usedOn=requiredUsedOns - usedOns)
                            
                        # 6.7.12 definition match pattern
                        definition = modelRoleTypes[0].definitionNotStripped
                        if (val.disclosureSystem.roleDefinitionPattern is not None and
                            (definition is None or not val.disclosureSystem.roleDefinitionPattern.match(definition))):
                            val.modelXbrl.error(("EFM.6.07.12", "GFM.1.03.12-14"),
                                _("RoleType %(roleType)s definition \"%(definition)s\" must match {Sortcode} - {Type} - {Title}"),
                                modelObject=e, roleType=roleURI, definition=definition)
                        
                    if val.validateSBRNL and (usedOns & XbrlConst.standardExtLinkQnames):
                        definesLinkroles = True

        # 6.7.13 arcrole types authority
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}arcroleType"):
            if isinstance(e,ModelObject):
                arcroleURI = e.get("arcroleURI")
                if targetNamespaceAuthority != UrlUtil.authority(arcroleURI):
                    val.modelXbrl.error(("EFM.6.07.13", "GFM.1.03.15"),
                        _("ArcroleType %(arcroleType)s does not match authority %(targetNamespaceAuthority)s"),
                        modelObject=e, arcroleType=arcroleURI, targetNamespaceAuthority=targetNamespaceAuthority)
                # 6.7.13 end with .../arcrole/lc3 name
                if not arcroleTypePattern.match(arcroleURI):
                    val.modelXbrl.warning(("EFM.6.07.13", "GFM.1.03.15"),
                        _("ArcroleType %(arcroleType)s should end with /arcrole/{LC3name}"),
                        modelObject=e, arcroleType=arcroleURI)
                    
                # 6.7.14 only one arcrole type declaration in DTS
                modelRoleTypes = val.modelXbrl.arcroleTypes[arcroleURI]
                if len(modelRoleTypes) > 1:
                    val.modelXbrl.error(("EFM.6.07.14", "GFM.1.03.16"),
                        _("ArcroleType %(arcroleType)s is defined in multiple taxonomies"),
                        modelObject=e, arcroleType=arcroleURI)
                    
                # 6.7.15 definition match pattern
                definition = modelRoleTypes[0].definition
                if definition is None or not arcroleDefinitionPattern.match(definition):
                    val.modelXbrl.error(("EFM.6.07.15", "GFM.1.03.17"),
                        _("ArcroleType %(arcroleType)s definition must be non-empty"),
                        modelObject=e, arcroleType=arcroleURI)
    
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
            val.modelXbrl.error("SBR.NL.2.2.1.01",
                _("Taxonomy schema %(schema)s may only define one of these: %(contents)s"),
                modelObject=val.modelXbrl,
                schema=os.path.basename(modelDocument.uri), contents=', '.join(schemaContents))

    visited.remove(modelDocument)
    
def tupleCycle(val, concept, ancestorTuples=None):
    if ancestorTuples is None: ancestorTuples = set()
    if concept in ancestorTuples:
        return True
    ancestorTuples.add(concept)
    if concept.type is not None:
        for elementQname in concept.type.elements:
            childConcept = val.modelXbrl.qnameConcepts.get(elementQname)
            if childConcept is not None and tupleCycle(val, childConcept, ancestorTuples):
                return True
    ancestorTuples.discard(concept)
    return False
