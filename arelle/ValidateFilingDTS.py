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
extLinkEltFileNameEnding = {
    "calculationLink": "cal",
    "definitionLink": "def",
    "labelLink": "lab",
    "presentationLink": "pre",
    "referenceLink": "ref"}

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
            definesLinkroles = False
            definesArcroles = False
            definesLinkParts = False
            definesAbstractItems = False
            definesNonabstractItems = False
            definesConcepts = False
            definesTuples = False
            definesPresentationTuples = False
            definesSpecificationTuples = False
            definesTypes = False
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

            if val.validateSBRNL:
                genrlSpeclRelSet = val.modelXbrl.relationshipSet(XbrlConst.generalSpecial)
            for modelConcept in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/2001/XMLSchema}element"):
                if isinstance(modelConcept,ModelConcept):
                    # 6.7.16 name not duplicated in standard taxonomies
                    name = modelConcept.get("name")
                    if name is None: 
                        name = ""
                        if modelConcept.get("ref") is not None:
                            continue    # don't validate ref's here
                    for c in val.modelXbrl.nameConcepts.get(name, []):
                        if c.modelDocument != modelDocument:
                            if (val.validateEFMorGFM and
                                  not c.modelDocument.uri.startswith(val.modelXbrl.uriDir)):
                                val.modelXbrl.error(("EFM.6.07.16", "GFM.1.03.18"),
                                    _("Concept %(concept)s is also defined in standard taxonomy schema schema %(standardSchema)s"),
                                    modelObject=c, concept=modelConcept.qname, standardSchema=os.path.basename(c.modelDocument.uri))
                            elif val.validateSBRNL:
                                if not (genrlSpeclRelSet.isRelated(modelConcept, "child", c) or genrlSpeclRelSet.isRelated(c, "child", modelConcept)):
                                    val.modelXbrl.error("SBR.NL.2.2.2.02",
                                        _("Concept %(concept)s is also defined in standard taxonomy schema %(standardSchema)s without a general-special relationship"),
                                        modelObject=c, concept=modelConcept.qname, standardSchema=os.path.basename(c.modelDocument.uri))
                    ''' removed RH 2011-12-23 corresponding set up of table in ValidateFiling
                    if val.validateSBRNL and name in val.nameWordsTable:
                        if not any( any( genrlSpeclRelSet.isRelated(c, "child", modelConcept)
                                         for c in val.modelXbrl.nameConcepts.get(partialWordName, []))
                                    for partialWordName in val.nameWordsTable[name]):
                            val.modelXbrl.error("SBR.NL.2.3.2.01",
                                _("Concept %(specialName)s is appears to be missing a general-special relationship to %(generalNames)s"),
                                modelObject=c, specialName=modelConcept.qname, generalNames=', or to '.join(val.nameWordsTable[name]))
                    '''

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
                            _("Concept %(concept)s must end in Axis to be in xbrldt:dimensionItem substitution group"),
                            modelObject=modelConcept, concept=modelConcept.qname)

                    # 6.7.24 Table must be subs group hypercube
                    if name.endswith("Table") ^ (substititutionGroupQname == XbrlConst.qnXbrldtHypercubeItem):
                        val.modelXbrl.error(("EFM.6.07.24", "GFM.1.03.26"),
                            _("Concept %(concept)s must end in Table to be in xbrldt:hypercubeItem substitution group"),
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
                        if modelConcept.isTuple:
                            if modelConcept.substitutionGroupQname.localName == "presentationTuple" and modelConcept.substitutionGroupQname.namespaceURI.endswith("/basis/sbr/xbrl/xbrl-syntax-extension"): # namespace may change each year
                                definesPresentationTuples = True
                            elif modelConcept.substitutionGroupQname.localName == "specificationTuple" and modelConcept.substitutionGroupQname.namespaceURI.endswith("/basis/sbr/xbrl/xbrl-syntax-extension"): # namespace may change each year
                                definesSpecificationTuples = True
                            else:
                                definesTuples = True
                            definesConcepts = True
                            if modelConcept.isAbstract:
                                val.modelXbrl.error("SBR.NL.2.2.2.03",
                                    _("Concept %(concept)s is an abstract tuple"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if tupleCycle(val,modelConcept):
                                val.modelXbrl.error("SBR.NL.2.2.2.07",
                                    _("Tuple %(concept)s has a tuple cycle"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if modelConcept.get("nillable") != "false" and modelConcept.isRoot:
                                val.modelXbrl.error("SBR.NL.2.2.2.17", #don't want default, just what was really there
                                    _("Tuple %(concept)s must have nillable='false'"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                        elif modelConcept.isItem:
                            definesConcepts = True
                        if modelConcept.abstract == "true":
                            if modelConcept.isRoot:
                                if modelConcept.get("nillable") != "false": #don't want default, just what was really there
                                    val.modelXbrl.error("SBR.NL.2.2.2.16",
                                        _("Abstract root concept %(concept)s must have nillable='false'"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                                if modelConcept.typeQname != XbrlConst.qnXbrliStringItemType:
                                    val.modelXbrl.error("SBR.NL.2.2.2.21",
                                        _("Abstract root concept %(concept)s must have type='xbrli:stringItemType'"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if modelConcept.balance:
                                val.modelXbrl.error("SBR.NL.2.2.2.22",
                                    _("Abstract concept %(concept)s must not have a balance attribute"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if modelConcept.isHypercubeItem:
                                definesHypercubes = True
                            elif modelConcept.isDimensionItem:
                                definesDimensions = True
                            elif substititutionGroupQname and substititutionGroupQname.localName in ("domainItem","domainMemberItem"):
                                definesDomains = True
                            elif modelConcept.isItem:
                                definesAbstractItems = True
                        else:   # not abstract
                            if modelConcept.isItem:
                                definesNonabstractItems = True
                                if not (modelConcept.label(preferredLabel=XbrlConst.documentationLabel,fallbackToQname=False,lang="nl") or
                                        val.modelXbrl.relationshipSet(XbrlConst.conceptReference).fromModelObject(c) or
                                        modelConcept.genLabel(role=XbrlConst.genDocumentationLabel,lang="nl") or
                                        val.modelXbrl.relationshipSet(XbrlConst.elementReference).fromModelObject(c)):
                                    val.modelXbrl.error("SBR.NL.2.2.2.28",
                                        _("Concept %(concept)s must have a documentation label or reference"),
                                        modelObject=modelConcept, concept=modelConcept.qname)
                        if modelConcept.balance and not modelConcept.instanceOfType(XbrlConst.qnXbrliMonetaryItemType):
                            val.modelXbrl.error("SBR.NL.2.2.2.24",
                                _("Non-monetary concept %(concept)s must not have a balance attribute"),
                                modelObject=modelConcept, concept=modelConcept.qname)
                        if modelConcept.isLinkPart:
                            definesLinkParts = True
                            val.modelXbrl.error("SBR.NL.2.2.5.01",
                                _("Link:part concept %(concept)s is not allowed"),
                                modelObject=modelConcept, concept=modelConcept.qname)
                            if not modelConcept.genLabel(fallbackToQname=False,lang="nl"):
                                val.modelXbrl.error("SBR.NL.2.2.5.02",
                                    _("Link part definition %(concept)s must have a generic label in language 'nl'"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
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
                    modelRoleType = modelRoleTypes[0]
                    definition = modelRoleType.definitionNotStripped
                    usedOns = modelRoleType.usedOns
                    if len(modelRoleTypes) > 1:
                        val.modelXbrl.error(("EFM.6.07.10", "GFM.1.03.10"),
                            _("RoleType %(roleType)s is defined in multiple taxonomies"),
                            modelObject=e, roleType=roleURI)
                    elif len(modelRoleTypes) == 1:
                        # 6.7.11 used on's for pre, cal, def if any has a used on
                        if not usedOns.isdisjoint(requiredUsedOns) and len(requiredUsedOns - usedOns) > 0:
                            val.modelXbrl.error(("EFM.6.07.11", "GFM.1.03.11"),
                                _("RoleType %(roleType)s missing used on %(usedOn)s"),
                                modelObject=e, roleType=roleURI, usedOn=requiredUsedOns - usedOns)
                            
                        # 6.7.12 definition match pattern
                        if (val.disclosureSystem.roleDefinitionPattern is not None and
                            (definition is None or not val.disclosureSystem.roleDefinitionPattern.match(definition))):
                            val.modelXbrl.error(("EFM.6.07.12", "GFM.1.03.12-14"),
                                _("RoleType %(roleType)s definition \"%(definition)s\" must match {Sortcode} - {Type} - {Title}"),
                                modelObject=e, roleType=roleURI, definition=definition)
                        
                    if val.validateSBRNL:
                        if usedOns & XbrlConst.standardExtLinkQnames or XbrlConst.qnGenLink in usedOns:
                            definesLinkroles = True
                            if not e.genLabel():
                                val.modelXbrl.error("SBR.NL.2.2.3.03",
                                    _("Link RoleType %(roleType)s missing a generic standard label"),
                                    modelObject=e, roleType=roleURI)
                            nlLabel = e.genLabel(lang="nl")
                            if definition != nlLabel:
                                val.modelXbrl.error("SBR.NL.2.2.3.04",
                                    _("Link RoleType %(roleType)s definition does not match NL standard generic label, \ndefinition: %(definition)s \nNL label: %(label)s"),
                                    modelObject=e, roleType=roleURI, definition=definition, label=nlLabel)
                        if definition and (definition[0].isspace() or definition[-1].isspace()):
                            val.modelXbrl.error("SBR.NL.2.2.3.07",
                                _('Link RoleType %(roleType)s definition has leading or trailing spaces: "%(definition)s"'),
                                modelObject=e, roleType=roleURI, definition=definition)

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
                    val.modelXbrl.error("SBR.NL.2.2.4.01",
                        _("Arcrole type definition is not allowed: %(arcroleURI)s"),
                        modelObject=e, arcroleURI=arcroleURI)
                    
        if val.validateSBRNL:
            for appinfoElt in modelDocument.xmlRootElement.iter(tag="{http://www.w3.org/2001/XMLSchema}appinfo"):
                for nonLinkElt in appinfoElt.iterdescendants():
                    if isinstance(nonLinkElt, ModelObject) and nonLinkElt.namespaceURI != XbrlConst.link:
                        val.modelXbrl.error("SBR.NL.2.2.11.05",
                            _("Appinfo contains disallowed non-link element %(element)s"),
                            modelObject=nonLinkElt, element=nonLinkElt.qname)

            for cplxTypeElt in modelDocument.xmlRootElement.iter(tag="{http://www.w3.org/2001/XMLSchema}complexType"):
                choiceElt = cplxTypeElt.find("{http://www.w3.org/2001/XMLSchema}choice")
                if choiceElt is not None:
                    val.modelXbrl.error("SBR.NL.2.2.11.09",
                        _("ComplexType contains disallowed xs:choice element"),
                        modelObject=choiceElt)
                    
            for cplxContentElt in modelDocument.xmlRootElement.iter(tag="{http://www.w3.org/2001/XMLSchema}complexContent"):
                if XmlUtil.descendantAttr(cplxContentElt, "http://www.w3.org/2001/XMLSchema", ("extension","restriction"), "base") != "sbr:placeholder":
                    val.modelXbrl.error("SBR.NL.2.2.11.10",
                        _("ComplexContent is disallowed"),
                        modelObject=cplxContentElt)

            definesTypes = (modelDocument.xmlRootElement.find("{http://www.w3.org/2001/XMLSchema}complexType") is not None or
                            modelDocument.xmlRootElement.find("{http://www.w3.org/2001/XMLSchema}simpleType") is not None)
            if (definesLinkroles + definesArcroles + definesLinkParts +
                definesAbstractItems + definesNonabstractItems + 
                definesTuples + definesPresentationTuples + definesSpecificationTuples + definesTypes +
                definesEnumerations + definesDimensions + definesDomains + 
                definesHypercubes) != 1:
                schemaContents = []
                if definesLinkroles: schemaContents.append(_("linkroles"))
                if definesArcroles: schemaContents.append(_("arcroles"))
                if definesLinkParts: schemaContents.append(_("link parts"))
                if definesAbstractItems: schemaContents.append(_("abstract items"))
                if definesNonabstractItems: schemaContents.append(_("nonabstract items"))
                if definesTuples: schemaContents.append(_("tuples"))
                if definesPresentationTuples: schemaContents.append(_("sbrPresentationTuples"))
                if definesSpecificationTuples: schemaContents.append(_("sbrSpecificationTuples"))
                if definesTypes: schemaContents.append(_("types"))
                if definesEnumerations: schemaContents.append(_("enumerations"))
                if definesDimensions: schemaContents.append(_("dimensions"))
                if definesDomains: schemaContents.append(_("domains"))
                if definesHypercubes: schemaContents.append(_("hypercubes"))
                if schemaContents:
                    val.modelXbrl.error("SBR.NL.2.2.1.01",
                        _("Taxonomy schema may only define one of these: %(contents)s"),
                        modelObject=modelDocument, contents=', '.join(schemaContents))
                elif not any(refDoc.inDTS and refDoc.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces
                             for refDoc in modelDocument.referencesDocument.keys()): # no linkbase ref or includes
                    val.modelXbrl.error("SBR.NL.2.2.1.01",
                        _("Taxonomy schema must be a DTS entrypoint OR define linkroles OR arcroles OR link:parts OR context fragments OR abstract items OR tuples OR non-abstract elements OR types OR enumerations OR dimensions OR domains OR hypercubes"),
                        modelObject=modelDocument)
            if definesConcepts ^ any(  # xor so either concepts and no label LB or no concepts and has label LB
                       (refDoc.type == ModelDocument.Type.LINKBASE and
                        XmlUtil.descendant(refDoc.xmlRootElement, XbrlConst.link, "labelLink") is not None)
                       for refDoc in modelDocument.referencesDocument.keys()): # no label linkbase
                val.modelXbrl.error("SBR.NL.2.2.1.02",
                    _("A schema that defines concepts MUST have a linked 2.1 label linkbase"),
                    modelObject=modelDocument)
            if (definesNonabstractItems or definesTuples) and not any(  # was xor but changed to and not per RH 1/11/12
                       (refDoc.type == ModelDocument.Type.LINKBASE and
                       (XmlUtil.descendant(refDoc.xmlRootElement, XbrlConst.link, "referenceLink") is not None or
                        XmlUtil.descendant(refDoc.xmlRootElement, XbrlConst.link, "label", "{http://www.w3.org/1999/xlink}role", "http://www.xbrl.org/2003/role/documentation" ) is not None))
                        for refDoc in modelDocument.referencesDocument.keys()):
                val.modelXbrl.error("SBR.NL.2.2.1.03",
                    _("A schema that defines non-abstract items MUST have a linked (2.1) reference linkbase AND/OR a label linkbase with @xlink:role=documentation"),
                    modelObject=modelDocument)

        if val.fileNameBasePart:
            #6.3.3 filename check
            expectedFilename = "{0}-{1}.xsd".format(val.fileNameBasePart, val.fileNameDatePart)
            if modelDocument.basename != expectedFilename and not ( # skip if an edgar testcase
               re.match("e[0-9]{8}(gd|ng)", val.fileNameBasePart) and re.match("e.*-[0-9]{8}.*", modelDocument.basename)):
                val.modelXbrl.error(("EFM.6.03.03", "GFM.1.01.01"),
                    _('Invalid schema file name: %(filename)s, expected %(expectedFilename)s'),
                    modelObject=modelDocument, filename=modelDocument.basename, expectedFilename=expectedFilename)

    elif modelDocument.type == ModelDocument.Type.LINKBASE:
        # if it is part of the submission (in same directory) check name
        if modelDocument.filepath.startswith(val.modelXbrl.modelDocument.filepathdir):
            #6.3.3 filename check
            extLinkElt = XmlUtil.descendant(modelDocument.xmlRootElement, XbrlConst.link, "*", "{http://www.w3.org/1999/xlink}type", "extended")
            if val.fileNameBasePart and extLinkElt is not None and extLinkElt.localName in extLinkEltFileNameEnding: 
                expectedFilename = "{0}-{1}_{2}.xml".format(val.fileNameBasePart, val.fileNameDatePart, 
                                                            extLinkEltFileNameEnding[extLinkElt.localName])
                if modelDocument.basename != expectedFilename and not ( # skip if an edgar testcase
                    re.match("e[0-9]{8}(gd|ng)", val.fileNameBasePart) and re.match("e.*-[0-9]{8}.*", modelDocument.basename)):
                    val.modelXbrl.error(("EFM.6.03.03", "GFM.1.01.01"),
                        _('Invalid linkbase file name: %(filename)s, expected %(expectedFilename)s'),
                        modelObject=modelDocument, filename=modelDocument.basename, expectedFilename=expectedFilename)
            
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
