'''
See COPYRIGHT.md for copyright information.
'''
import os, re
from arelle import (ModelDocument, XmlUtil, XbrlConst)
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelConcept

targetNamespaceDatePattern = None
efmFilenamePattern = None
roleTypePattern = None
arcroleTypePattern = None
arcroleDefinitionPattern = None
namePattern = None
namespacesConflictPattern = None
linkroleDefinitionBalanceIncomeSheet = None
extLinkEltFileNameEnding = {
    "calculationLink": "_cal",
    "definitionLink": "_def",
    "labelLink": "_lab",
    "presentationLink": "_pre",
    "referenceLink": "_ref"}

def checkFilingDTS(val, modelDocument, visited):
    global targetNamespaceDatePattern, efmFilenamePattern, roleTypePattern, arcroleTypePattern, \
            arcroleDefinitionPattern, namePattern, linkroleDefinitionBalanceIncomeSheet, \
            namespacesConflictPattern
    if targetNamespaceDatePattern is None:
        targetNamespaceDatePattern = re.compile(r"/([12][0-9]{3})-([01][0-9])-([0-3][0-9])|"
                                            r"/([12][0-9]{3})([01][0-9])([0-3][0-9])|")
        efmFilenamePattern = re.compile(r"^[a-z0-9][a-zA-Z0-9_\.\-]*(\.xsd|\.xml)$")
        roleTypePattern = re.compile(r"^.*/role/[^/\s]+$")
        arcroleTypePattern = re.compile(r"^.*/arcrole/[^/\s]+$")
        arcroleDefinitionPattern = re.compile(r"^.*[^\\s]+.*$")  # at least one non-whitespace character
        namePattern = re.compile("[][()*+?\\\\/^{}|@#%^=~`\"';:,<>&$\u00a3\u20ac]") # u20ac=Euro, u00a3=pound sterling
        linkroleDefinitionBalanceIncomeSheet = re.compile(r"[^-]+-\s+Statement\s+-\s+.*(income|balance|financial\W+position)",
                                                          re.IGNORECASE)
        namespacesConflictPattern = re.compile(r"http://(xbrl\.us|fasb\.org|xbrl\.sec\.gov)/(dei|us-types|us-roles|rr)/([0-9]{4}-[0-9]{2}-[0-9]{2})$")

    visited.append(modelDocument)
    for referencedDocument, modelDocumentReference in modelDocument.referencesDocument.items():
        #6.07.01 no includes
        if "include" in modelDocumentReference.referenceTypes:
            val.modelXbrl.error("SBR.NL.2.2.0.18",
                _("Taxonomy schema %(schema)s includes %(include)s, only import is allowed"),
                modelObject=modelDocumentReference.referringModelObject,
                    schema=os.path.basename(modelDocument.uri),
                    include=os.path.basename(referencedDocument.uri))
        if referencedDocument not in visited:
            checkFilingDTS(val, referencedDocument, visited)

    if val.disclosureSystem.standardTaxonomiesDict is None:
        pass

    if (modelDocument.type == ModelDocument.Type.SCHEMA and
        modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces and
        modelDocument.uri.startswith(val.modelXbrl.uriDir)):

        # check schema contents types
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
                    elif modelConcept.substitutionGroupQname and modelConcept.substitutionGroupQname.localName in ("domainItem","domainMemberItem"):
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

        # 6.7.9 role types authority
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}roleType"):
            if isinstance(e,ModelObject):
                roleURI = e.get("roleURI")
                # 6.7.10 only one role type declaration in DTS
                modelRoleTypes = val.modelXbrl.roleTypes.get(roleURI)
                if modelRoleTypes is not None:
                    modelRoleType = modelRoleTypes[0]
                    definition = modelRoleType.definitionNotStripped
                    usedOns = modelRoleType.usedOns
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
                definesArcroles = True
                val.modelXbrl.error("SBR.NL.2.2.4.01",
                    _("Arcrole type definition is not allowed: %(arcroleURI)s"),
                    modelObject=e, arcroleURI=arcroleURI)

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

        for typeEltTag in ("{http://www.w3.org/2001/XMLSchema}complexType",
                            "{http://www.w3.org/2001/XMLSchema}simpleType"):
            for typeElt in modelDocument.xmlRootElement.iter(tag=typeEltTag):
                definesTypes = True
                name = typeElt.get("name")
                if name:
                    if not name[0].islower() or not name.isalnum():
                        val.modelXbrl.error("SBR.NL.3.2.8.09",
                            _("Type name attribute must be lower camelcase: %(name)s."),
                            modelObject=typeElt, name=name)

        for enumElt in modelDocument.xmlRootElement.iter(tag="{http://www.w3.org/2001/XMLSchema}enumeration"):
            definesEnumerations = True
            if any(not valueElt.genLabel(lang="nl")
                   for valueElt in enumElt.iter(tag="{http://www.w3.org/2001/XMLSchema}value")):
                val.modelXbrl.error("SBR.NL.2.2.7.05",
                    _("Enumeration element has value(s) without generic label."),
                    modelObject=enumElt)

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
                if not ((definesTuples or definesPresentationTuples or definesSpecificationTuples) and
                        not (definesLinkroles or definesArcroles or definesLinkParts or definesAbstractItems or
                             definesTypes or definesDimensions or definesDomains or definesHypercubes)):
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

    elif modelDocument.type == ModelDocument.Type.LINKBASE:
        pass
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
