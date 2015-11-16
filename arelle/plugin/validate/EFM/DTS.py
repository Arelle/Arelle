'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, datetime, re
from arelle import (ModelDocument, XmlUtil, XbrlConst, UrlUtil)
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelConcept

targetNamespaceDatePattern = None
efmFilenamePattern = None
htmlFileNamePattern = None
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

def checkFilingDTS(val, modelDocument, isEFM, isGFM, visited):
    global targetNamespaceDatePattern, efmFilenamePattern, htmlFileNamePattern, roleTypePattern, arcroleTypePattern, \
            arcroleDefinitionPattern, namePattern, linkroleDefinitionBalanceIncomeSheet, \
            namespacesConflictPattern
    if targetNamespaceDatePattern is None:
        targetNamespaceDatePattern = re.compile(r"/([12][0-9]{3})-([01][0-9])-([0-3][0-9])|"
                                            r"/([12][0-9]{3})([01][0-9])([0-3][0-9])|")
        efmFilenamePattern = re.compile(r"^[a-z0-9][a-zA-Z0-9_\.\-]*(\.xsd|\.xml|\.htm)$")
        htmlFileNamePattern = re.compile(r"^[a-zA-Z0-9][._a-zA-Z0-9-]*(\.htm)$")
        roleTypePattern = re.compile(r"^.*/role/[^/\s]+$")
        arcroleTypePattern = re.compile(r"^.*/arcrole/[^/\s]+$")
        arcroleDefinitionPattern = re.compile(r"^.*[^\\s]+.*$")  # at least one non-whitespace character
        namePattern = re.compile("[][()*+?\\\\/^{}|@#%^=~`\"';:,<>&$\u00a3\u20ac]") # u20ac=Euro, u00a3=pound sterling 
        linkroleDefinitionBalanceIncomeSheet = re.compile(r"[^-]+-\s+Statement\s+-\s+.*(income|balance|financial\W+position)",
                                                          re.IGNORECASE)
        namespacesConflictPattern = re.compile(r"http://(xbrl\.us|fasb\.org|xbrl\.sec\.gov)/(dei|us-types|us-roles|rr)/([0-9]{4}-[0-9]{2}-[0-9]{2})$")
    nonDomainItemNameProblemPattern = re.compile(
        r"({0})|(FirstQuarter|SecondQuarter|ThirdQuarter|FourthQuarter|[1-4]Qtr|Qtr[1-4]|ytd|YTD|HalfYear)(?:$|[A-Z\W])"
        .format(re.sub(r"\W", "", (val.entityRegistrantName or "").title())))
    
        
    visited.append(modelDocument)
    for referencedDocument, modelDocumentReference in modelDocument.referencesDocument.items():
        #6.07.01 no includes
        if modelDocumentReference.referenceType == "include":
            val.modelXbrl.error(("EFM.6.07.01", "GFM.1.03.01"),
                _("Taxonomy schema %(schema)s includes %(include)s, only import is allowed"),
                modelObject=modelDocumentReference.referringModelObject,
                    schema=os.path.basename(modelDocument.uri), 
                    include=os.path.basename(referencedDocument.uri))
        if referencedDocument not in visited and referencedDocument.inDTS: # ignore EdgarRenderer added non-DTS documents
            checkFilingDTS(val, referencedDocument, isEFM, isGFM, visited)
            
    if val.disclosureSystem.standardTaxonomiesDict is None:
        pass

    if isEFM: 
        if modelDocument.uri in val.disclosureSystem.standardTaxonomiesDict:
            if modelDocument.targetNamespace:
                # check for duplicates of us-types, dei, and rr taxonomies
                match = namespacesConflictPattern.match(modelDocument.targetNamespace)
                if match is not None:
                    val.standardNamespaceConflicts[match.group(2)].add(modelDocument)
        else:
            if len(modelDocument.basename) > 32:
                val.modelXbrl.error("EFM.5.01.01.tooManyCharacters",
                    _("Document file name %(filename)s must not exceed 32 characters."),
                    modelObject=modelDocument, filename=modelDocument.basename)
            if modelDocument.type == ModelDocument.Type.INLINEXBRL:
                if not htmlFileNamePattern.match(modelDocument.basename):
                    val.modelXbrl.error("EFM.5.01.01",
                        _("Document file name %(filename)s must start with a-z or 0-9, contain upper or lower case letters, ., -, _, and end with .htm."),
                        modelObject=modelDocument, filename=modelDocument.basename)
            elif not efmFilenamePattern.match(modelDocument.basename):
                val.modelXbrl.error("EFM.5.01.01",
                    _("Document file name %(filename)s must start with a-z or 0-9, contain upper or lower case letters, ., -, _, and end with .xsd or .xml."),
                    modelObject=modelDocument, filename=modelDocument.basename)
    
    if (modelDocument.type == ModelDocument.Type.SCHEMA and 
        modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces and
        modelDocument.uri.startswith(val.modelXbrl.uriDir)):
        
        val.hasExtensionSchema = True
        # check schema contents types
        # 6.7.3 check namespace for standard authority
        targetNamespaceAuthority = UrlUtil.authority(modelDocument.targetNamespace) 
        if targetNamespaceAuthority in val.disclosureSystem.standardAuthorities:
            val.modelXbrl.error(("EFM.6.07.03", "GFM.1.03.03"),
                _("Taxonomy schema %(schema)s namespace %(targetNamespace)s is a disallowed authority"),
                modelObject=modelDocument, schema=os.path.basename(modelDocument.uri), targetNamespace=modelDocument.targetNamespace, 
                targetNamespaceAuthority=UrlUtil.authority(modelDocument.targetNamespace, includeScheme=False))
            
        # 6.7.4 check namespace format
        if modelDocument.targetNamespace is None or not modelDocument.targetNamespace.startswith("http://"):
            match = None
        else:
            targetNamespaceDate = modelDocument.targetNamespace[len(targetNamespaceAuthority):]
            match = targetNamespaceDatePattern.match(targetNamespaceDate)
        if match is not None:
            try:
                if match.lastindex == 3:
                    date = datetime.date(int(match.group(1)),int(match.group(2)),int(match.group(3)))
                elif match.lastindex == 6:
                    date = datetime.date(int(match.group(4)),int(match.group(5)),int(match.group(6)))
                else:
                    match = None
            except ValueError:
                match = None
        if match is None:
            val.modelXbrl.error(("EFM.6.07.04", "GFM.1.03.04"),
                _("Taxonomy schema %(schema)s namespace %(targetNamespace)s must have format http://{authority}/{versionDate}"),
                modelObject=modelDocument, schema=os.path.basename(modelDocument.uri), targetNamespace=modelDocument.targetNamespace)
        elif val.fileNameDate and date > val.fileNameDate:
            val.modelXbrl.info(("EFM.6.07.06", "GFM.1.03.06"),
                _("Warning: Taxonomy schema %(schema)s namespace %(targetNamespace)s has date later than document name date %(docNameDate)s"),
                modelObject=modelDocument, schema=os.path.basename(modelDocument.uri), targetNamespace=modelDocument.targetNamespace,
                docNameDate=val.fileNameDate)

        if modelDocument.targetNamespace is not None:
            # 6.7.5 check prefix for _
            authority = UrlUtil.authority(modelDocument.targetNamespace)
            if not re.match(r"(http://|https://|ftp://|urn:)\w+",authority):
                val.modelXbrl.error(("EFM.6.07.05", "GFM.1.03.05"),
                    _("Taxonomy schema %(schema)s namespace %(targetNamespace)s must be a valid URL with a valid authority for the namespace."),
                    modelObject=modelDocument, schema=os.path.basename(modelDocument.uri), targetNamespace=modelDocument.targetNamespace)
            prefix = XmlUtil.xmlnsprefix(modelDocument.xmlRootElement,modelDocument.targetNamespace)
            if not prefix:
                val.modelXbrl.error(("EFM.6.07.07", "GFM.1.03.07"),
                    _("Taxonomy schema %(schema)s namespace %(targetNamespace)s missing prefix for the namespace."),
                    modelObject=modelDocument, schema=os.path.basename(modelDocument.uri), targetNamespace=modelDocument.targetNamespace)
            elif "_" in prefix:
                val.modelXbrl.error(("EFM.6.07.07", "GFM.1.03.07"),
                    _("Taxonomy schema %(schema)s namespace %(targetNamespace)s prefix %(prefix)s must not have an '_'"),
                    modelObject=modelDocument, schema=os.path.basename(modelDocument.uri), targetNamespace=modelDocument.targetNamespace, prefix=prefix)

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
                            if not c.modelDocument.uri.startswith(val.modelXbrl.uriDir):
                                val.modelXbrl.error(("EFM.6.07.16", "GFM.1.03.18"),
                                    _("Concept %(concept)s is also defined in standard taxonomy schema schema %(standardSchema)s"),
                                    modelObject=(modelConcept,c), concept=modelConcept.qname, standardSchema=os.path.basename(c.modelDocument.uri), standardConcept=c.qname)

                    # 6.7.17 id properly formed
                    _id = modelConcept.id
                    requiredId = (prefix if prefix is not None else "") + "_" + name
                    if _id != requiredId:
                        val.modelXbrl.error(("EFM.6.07.17", "GFM.1.03.19"),
                            _("Concept %(concept)s id %(id)s should be %(requiredId)s"),
                            modelObject=modelConcept, concept=modelConcept.qname, id=_id, requiredId=requiredId)
                        
                    # 6.7.18 nillable is true
                    nillable = modelConcept.get("nillable")
                    if nillable != "true" and modelConcept.isItem:
                        val.modelXbrl.error(("EFM.6.07.18", "GFM.1.03.20"),
                            _("Taxonomy schema %(schema)s element %(concept)s nillable %(nillable)s should be 'true'"),
                            modelObject=modelConcept, schema=os.path.basename(modelDocument.uri),
                            concept=name, nillable=nillable)
        
                    # 6.7.19 not tuple
                    if modelConcept.isTuple:
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
                    if modelConcept.isAbstract and not isDuration:
                        val.modelXbrl.error(("EFM.6.07.21", "GFM.1.03.23"),
                            _("Taxonomy schema %(schema)s element %(concept)s is abstract but period type is not duration"),
                            modelObject=modelConcept, schema=os.path.basename(modelDocument.uri), concept=modelConcept.qname)
                        
                    # 6.7.22 abstract must be stringItemType
                    ''' removed SEC EFM v.17, Edgar release 10.4, and GFM 2011-04-08
                    if modelConcept.abstract == "true" and modelConcept.typeQname != XbrlConst. qnXbrliStringItemType:
                        val.modelXbrl.error(("EFM.6.07.22", "GFM.1.03.24"),
                            _("Concept %(concept)s  is abstract but type is not xbrli:stringItemType"),
                            modelObject=modelConcept, concept=modelConcept.qname)
					'''
                    substitutionGroupQname = modelConcept.substitutionGroupQname
                    # 6.7.23 Axis must be subs group dimension
                    if name.endswith("Axis") ^ (substitutionGroupQname == XbrlConst.qnXbrldtDimensionItem):
                        val.modelXbrl.error(("EFM.6.07.23", "GFM.1.03.25"),
                            _("Concept %(concept)s must end in Axis to be in xbrldt:dimensionItem substitution group"),
                            modelObject=modelConcept, concept=modelConcept.qname)

                    # 6.7.24 Table must be subs group hypercube
                    if name.endswith("Table") ^ (substitutionGroupQname == XbrlConst.qnXbrldtHypercubeItem):
                        val.modelXbrl.error(("EFM.6.07.24", "GFM.1.03.26"),
                            _("Concept %(concept)s must end in Table to be in xbrldt:hypercubeItem substitution group"),
                            modelObject=modelConcept, schema=os.path.basename(modelDocument.uri), concept=modelConcept.qname)

                    # 6.7.25 if neither hypercube or dimension, substitution group must be item
                    if substitutionGroupQname not in (None,
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
                                                
                    #6.7.31 (version 27) fractions
                    if modelConcept.isFraction:
                        val.modelXbrl.error("EFM.6.07.31",
                            _("Concept %(concept)s is a fraction"),
                            modelObject=modelConcept, concept=modelConcept.qname)
    
                    #6.7.32 (version 27) instant non numeric
                    if modelConcept.isItem and (not modelConcept.isNumeric and not isDuration and not modelConcept.isAbstract and not isDomainItemType):
                        val.modelXbrl.error("EFM.6.07.32",
                            _("Taxonomy schema %(schema)s element %(concept)s is non-numeric but period type is not duration"),
                            modelObject=modelConcept, schema=os.path.basename(modelDocument.uri), concept=modelConcept.qname)
                        
                    # 6.8.5 semantic check, check LC3 name
                    if name:
                        if not name[0].isupper():
                            val.modelXbrl.log("ERROR-SEMANTIC", ("EFM.6.08.05.firstLetter", "GFM.2.03.05.firstLetter"),
                                _("Concept %(concept)s name must start with a capital letter"),
                                modelObject=modelConcept, concept=modelConcept.qname)
                        if namePattern.search(name):
                            val.modelXbrl.log("ERROR-SEMANTIC", ("EFM.6.08.05.disallowedCharacter", "GFM.2.03.05.disallowedCharacter"),
                                _("Concept %(concept)s has disallowed name character"),
                                modelObject=modelConcept, concept=modelConcept.qname)
                        if len(name) > 200:
                            val.modelXbrl.log("ERROR-SEMANTIC", "EFM.6.08.05.nameLength",
                                _("Concept %(concept)s name length %(namelength)s exceeds 200 characters"),
                                modelObject=modelConcept, concept=modelConcept.qname, namelength=len(name))
                        
                    if isEFM:
                        label = modelConcept.label(lang="en-US", fallbackToQname=False)
                        if label:
                            # allow Joe's Bar, N.A.  to be JoesBarNA -- remove ', allow A. as not article "a"
                            lc3name = ''.join(re.sub(r"['.-]", "", (w[0] or w[2] or w[3] or w[4])).title()
                                              for w in re.findall(r"((\w+')+\w+)|(A[.-])|([.-]A(?=\W|$))|(\w+)", label) # EFM implies this should allow - and . re.findall(r"[\w\-\.]+", label)
                                              if w[4].lower() not in ("the", "a", "an"))
                            if not(name == lc3name or 
                                   (name and lc3name and lc3name[0].isdigit() and name[1:] == lc3name and (name[0].isalpha() or name[0] == '_'))):
                                val.modelXbrl.log("WARNING-SEMANTIC", "EFM.6.08.05.LC3",
                                    _("Concept %(concept)s should match expected LC3 composition %(lc3name)s"),
                                    modelObject=modelConcept, concept=modelConcept.qname, lc3name=lc3name)
                                
                    if conceptType is not None:
                        # 6.8.6 semantic check
                        if not isDomainItemType and conceptType.qname != XbrlConst.qnXbrliDurationItemType:
                            nameProblems = nonDomainItemNameProblemPattern.findall(name)
                            if any(any(t) for t in nameProblems):  # list of tuples with possibly nonempty strings
                                val.modelXbrl.log("WARNING-SEMANTIC", ("EFM.6.08.06", "GFM.2.03.06"),
                                    _("Concept %(concept)s should not contain company or period information, found: %(matches)s"),
                                    modelObject=modelConcept, concept=modelConcept.qname, 
                                    matches=", ".join(''.join(t) for t in nameProblems))
                        
                        if conceptType.qname == XbrlConst.qnXbrliMonetaryItemType:
                            if not modelConcept.balance:
                                # 6.8.11 may not appear on a income or balance statement
                                if any(linkroleDefinitionBalanceIncomeSheet.match(roleType.definition)
                                       for rel in val.modelXbrl.relationshipSet(XbrlConst.parentChild).toModelObject(modelConcept)
                                       for roleType in val.modelXbrl.roleTypes.get(rel.linkrole,())):
                                    val.modelXbrl.log("ERROR-SEMANTIC", ("EFM.6.08.11", "GFM.2.03.11"),
                                        _("Concept %(concept)s must have a balance because it appears in a statement of income or balance sheet"),
                                        modelObject=modelConcept, concept=modelConcept.qname)
                                # 6.11.5 semantic check, must have a documentation label
                                stdLabel = modelConcept.label(lang="en-US", fallbackToQname=False)
                                defLabel = modelConcept.label(preferredLabel=XbrlConst.documentationLabel, lang="en-US", fallbackToQname=False)
                                if not defLabel or ( # want different words than std label
                                    stdLabel and re.findall(r"\w+", stdLabel) == re.findall(r"\w+", defLabel)):
                                    val.modelXbrl.log("ERROR-SEMANTIC", ("EFM.6.11.05", "GFM.2.04.04"),
                                        _("Concept %(concept)s is monetary without a balance and must have a documentation label that disambiguates its sign"),
                                        modelObject=modelConcept, concept=modelConcept.qname)
                        
                        # 6.8.16 semantic check
                        if conceptType.qname == XbrlConst.qnXbrliDateItemType and modelConcept.periodType != "duration":
                            val.modelXbrl.log("ERROR-SEMANTIC", ("EFM.6.08.16", "GFM.2.03.16"),
                                _("Concept %(concept)s of type xbrli:dateItemType must have periodType duration"),
                                modelObject=modelConcept, concept=modelConcept.qname)
                        
                        # 6.8.17 semantic check
                        if conceptType.qname == XbrlConst.qnXbrliStringItemType and modelConcept.periodType != "duration":
                            val.modelXbrl.log("ERROR-SEMANTIC", ("EFM.6.08.17", "GFM.2.03.17"),
                                _("Concept %(concept)s of type xbrli:stringItemType must have periodType duration"),
                                modelObject=modelConcept, concept=modelConcept.qname)
                        

        # 6.7.8 check for embedded linkbase
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}linkbase"):
            if isinstance(e,ModelObject):
                val.modelXbrl.error(("EFM.6.07.08", "GFM.1.03.08"),
                    _("Taxonomy schema %(schema)s contains an embedded linkbase"),
                    modelObject=e, schema=modelDocument.basename)
                break

        requiredUsedOns = {XbrlConst.qnLinkPresentationLink,
                           XbrlConst.qnLinkCalculationLink,
                           XbrlConst.qnLinkDefinitionLink}
        
        standardUsedOns = {XbrlConst.qnLinkLabel, XbrlConst.qnLinkReference, 
                           XbrlConst.qnLinkDefinitionArc, XbrlConst.qnLinkCalculationArc, XbrlConst.qnLinkPresentationArc, 
                           XbrlConst.qnLinkLabelArc, XbrlConst.qnLinkReferenceArc, 
                           # per WH, private footnote arc and footnore resource roles are not allowed
                           XbrlConst.qnLinkFootnoteArc, XbrlConst.qnLinkFootnote,
                           }

        # 6.7.9 role types authority
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}roleType"):
            if isinstance(e,ModelObject):
                roleURI = e.get("roleURI")
                if targetNamespaceAuthority != UrlUtil.authority(roleURI):
                    val.modelXbrl.error(("EFM.6.07.09", "GFM.1.03.09"),
                        _("RoleType %(roleType)s does not match authority %(targetNamespaceAuthority)s"),
                        modelObject=e, roleType=roleURI, targetNamespaceAuthority=targetNamespaceAuthority, targetNamespace=modelDocument.targetNamespace)
                # 6.7.9 end with .../role/lc3 name
                if not roleTypePattern.match(roleURI):
                    val.modelXbrl.warning(("EFM.6.07.09.roleEnding", "GFM.1.03.09"),
                        "RoleType %(roleType)s should end with /role/{LC3name}",
                        modelObject=e, roleType=roleURI)
                    
                # 6.7.10 only one role type declaration in DTS
                modelRoleTypes = val.modelXbrl.roleTypes.get(roleURI)
                if modelRoleTypes is not None:
                    modelRoleType = modelRoleTypes[0]
                    definition = modelRoleType.definitionNotStripped
                    usedOns = modelRoleType.usedOns
                    if len(modelRoleTypes) == 1:
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
                                modelObject=e, roleType=roleURI, definition=(definition or ""))

                    if usedOns & standardUsedOns: # semantics check
                        val.modelXbrl.log("ERROR-SEMANTIC", ("EFM.6.08.03", "GFM.2.03.03"),
                            _("RoleType %(roleuri)s is defined using role types already defined by standard roles for: %(qnames)s"),
                            modelObject=e, roleuri=roleURI, qnames=', '.join(str(qn) for qn in usedOns & standardUsedOns))


        # 6.7.13 arcrole types authority
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}arcroleType"):
            if isinstance(e,ModelObject):
                arcroleURI = e.get("arcroleURI")
                if targetNamespaceAuthority != UrlUtil.authority(arcroleURI):
                    val.modelXbrl.error(("EFM.6.07.13", "GFM.1.03.15"),
                        _("ArcroleType %(arcroleType)s does not match authority %(targetNamespaceAuthority)s"),
                        modelObject=e, arcroleType=arcroleURI, targetNamespaceAuthority=targetNamespaceAuthority, targetNamespace=modelDocument.targetNamespace)
                # 6.7.13 end with .../arcrole/lc3 name
                if not arcroleTypePattern.match(arcroleURI):
                    val.modelXbrl.warning(("EFM.6.07.13.arcroleEnding", "GFM.1.03.15"),
                        _("ArcroleType %(arcroleType)s should end with /arcrole/{LC3name}"),
                        modelObject=e, arcroleType=arcroleURI)
                    
                # 6.7.15 definition match pattern
                modelRoleTypes = val.modelXbrl.arcroleTypes[arcroleURI]
                definition = modelRoleTypes[0].definition
                if definition is None or not arcroleDefinitionPattern.match(definition):
                    val.modelXbrl.error(("EFM.6.07.15", "GFM.1.03.17"),
                        _("ArcroleType %(arcroleType)s definition must be non-empty"),
                        modelObject=e, arcroleType=arcroleURI)
    
                # semantic checks
                usedOns = modelRoleTypes[0].usedOns
                if usedOns & standardUsedOns: # semantics check
                    val.modelXbrl.log("ERROR-SEMANTIC", ("EFM.6.08.03", "GFM.2.03.03"),
                        _("ArcroleType %(arcroleuri)s is defined using role types already defined by standard arcroles for: %(qnames)s"),
                        modelObject=e, arcroleuri=arcroleURI, qnames=', '.join(str(qn) for qn in usedOns & standardUsedOns))



        #6.3.3 filename check
        m = re.match(r"^\w+-([12][0-9]{3}[01][0-9][0-3][0-9]).xsd$", modelDocument.basename)
        if m:
            try: # check date value
                datetime.datetime.strptime(m.group(1),"%Y%m%d").date()
                # date and format are ok, check "should" part of 6.3.3
                if val.fileNameBasePart:
                    expectedFilename = "{0}-{1}.xsd".format(val.fileNameBasePart, val.fileNameDatePart)
                    if modelDocument.basename != expectedFilename:
                        val.modelXbrl.log("WARNING-SEMANTIC", ("EFM.6.03.03.matchInstance", "GFM.1.01.01.matchInstance"),
                            _('Schema file name warning: %(filename)s, should match %(expectedFilename)s'),
                            modelObject=modelDocument, filename=modelDocument.basename, expectedFilename=expectedFilename)
            except ValueError:
                val.modelXbrl.error((val.EFM60303, "GFM.1.01.01"),
                    _('Invalid schema file base name part (date) in "{base}-{yyyymmdd}.xsd": %(filename)s'),
                    modelObject=modelDocument, filename=modelDocument.basename,
                    messageCodes=("EFM.6.03.03", "EFM.6.23.01", "GFM.1.01.01"))
        else:
            val.modelXbrl.error((val.EFM60303, "GFM.1.01.01"),
                _('Invalid schema file name, must match "{base}-{yyyymmdd}.xsd": %(filename)s'),
                modelObject=modelDocument, filename=modelDocument.basename,
                messageCodes=("EFM.6.03.03", "EFM.6.23.01", "GFM.1.01.01"))

    elif modelDocument.type == ModelDocument.Type.LINKBASE:
        # if it is part of the submission (in same directory) check name
        labelRels = None
        if modelDocument.filepath.startswith(val.modelXbrl.modelDocument.filepathdir):
            #6.3.3 filename check
            extLinkElt = XmlUtil.descendant(modelDocument.xmlRootElement, XbrlConst.link, "*", "{http://www.w3.org/1999/xlink}type", "extended")
            if extLinkElt is None:# no ext link element
                val.modelXbrl.error((val.EFM60303 + ".noLinkElement", "GFM.1.01.01.noLinkElement"),
                    _('Invalid linkbase file name: %(filename)s, has no extended link element, cannot determine link type.'),
                    modelObject=modelDocument, filename=modelDocument.basename,
                    messageCodes=("EFM.6.03.03.noLinkElement", "EFM.6.23.01.noLinkElement",  "GFM.1.01.01.noLinkElement"))
            elif extLinkElt.localName not in extLinkEltFileNameEnding:
                val.modelXbrl.error("EFM.6.03.02",
                    _('Invalid linkbase link element %(linkElement)s in %(filename)s'),
                    modelObject=modelDocument, linkElement=extLinkElt.localName, filename=modelDocument.basename)
            else:
                m = re.match(r"^\w+-([12][0-9]{3}[01][0-9][0-3][0-9])(_[a-z]{3}).xml$", modelDocument.basename)
                expectedSuffix = extLinkEltFileNameEnding[extLinkElt.localName]
                if m and m.group(2) == expectedSuffix:
                    try: # check date value
                        datetime.datetime.strptime(m.group(1),"%Y%m%d").date()
                        # date and format are ok, check "should" part of 6.3.3
                        if val.fileNameBasePart:
                            expectedFilename = "{0}-{1}{2}.xml".format(val.fileNameBasePart, val.fileNameDatePart, expectedSuffix)
                            if modelDocument.basename != expectedFilename:
                                val.modelXbrl.log("WARNING-SEMANTIC", ("EFM.6.03.03.matchInstance", "GFM.1.01.01.matchInstance"),
                                    _('Linkbase name warning: %(filename)s should match %(expectedFilename)s'),
                                    modelObject=modelDocument, filename=modelDocument.basename, expectedFilename=expectedFilename)
                    except ValueError:
                        val.modelXbrl.error((val.EFM60303, "GFM.1.01.01"),
                            _('Invalid linkbase base file name part (date) in "{base}-{yyyymmdd}_{suffix}.xml": %(filename)s'),
                            modelObject=modelDocument, filename=modelDocument.basename,
                            messageCodes=("EFM.6.03.03", "EFM.6.23.01", "GFM.1.01.01"))
                else:
                    val.modelXbrl.error((val.EFM60303, "GFM.1.01.01"),
                        _('Invalid linkbase name, must match "{base}-{yyyymmdd}%(expectedSuffix)s.xml": %(filename)s'),
                        modelObject=modelDocument, filename=modelDocument.basename, expectedSuffix=expectedSuffix,
                        messageCodes=("EFM.6.03.03", "EFM.6.23.01", "GFM.1.01.01"))
                if extLinkElt.localName == "labelLink":
                    if labelRels is None:
                        labelRels = val.modelXbrl.relationshipSet(XbrlConst.conceptLabel)
                    for labelElt in XmlUtil.children(extLinkElt, XbrlConst.link, "label"):
                        # 6.10.9
                        if XbrlConst.isNumericRole(labelElt.role):
                            for rel in labelRels.toModelObject(labelElt):
                                if rel.fromModelObject is not None and not rel.fromModelObject.isNumeric:
                                    val.modelXbrl.error("EFM.6.10.09",
                                        _("Label of non-numeric concept %(concept)s has a numeric role: %(role)s"), 
                                          modelObject=(labelElt, rel.fromModelObject), concept=rel.fromModelObject.qname, role=labelElt.role)
    
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
