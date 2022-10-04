'''
See COPYRIGHT.md for copyright information.
'''
import os, datetime, re
from arelle import (ModelDocument, XmlUtil, XbrlConst, UrlUtil)
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelConcept
from .Consts import standardNamespacesPattern

targetNamespaceDatePattern = None
efmFilenamePattern = None
htmlFileNamePattern = None
roleTypePattern = None
arcroleTypePattern = None
arcroleDefinitionPattern = None
namePattern = None
linkroleDefinitionBalanceIncomeSheet = None
extLinkEltFileNameEnding = {
    "calculationLink": "_cal",
    "definitionLink": "_def",
    "labelLink": "_lab",
    "presentationLink": "_pre",
    "referenceLink": "_ref"}

def checkFilingDTS(val, modelDocument, isEFM, isGFM, visited):
    global targetNamespaceDatePattern, efmFilenamePattern, htmlFileNamePattern, roleTypePattern, arcroleTypePattern, \
            arcroleDefinitionPattern, namePattern, linkroleDefinitionBalanceIncomeSheet
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
    nonDomainItemNameProblemPattern = re.compile(
        r"({0})|(FirstQuarter|SecondQuarter|ThirdQuarter|FourthQuarter|[1-4]Qtr|Qtr[1-4]|ytd|YTD|HalfYear)(?:$|[A-Z\W])"
        .format(re.sub(r"\W", "", (val.entityRegistrantName or "").title())))


    visited.append(modelDocument)
    # check if an extension-filed standard taxonomy
    extensionFiledStandardTaxonomy = isEFM and modelDocument.targetNamespace in val.otherStandardTaxonomies
    for referencedDocument, modelDocumentReference in modelDocument.referencesDocument.items():
        #6.07.01 no includes
        if "include" in modelDocumentReference.referenceTypes:
            val.modelXbrl.error(("EFM.6.07.01", "GFM.1.03.01"),
                _("Taxonomy schema %(schema)s includes %(include)s, only import is allowed"),
                modelObject=modelDocumentReference.referringModelObject,
                    schema=modelDocument.basename,
                    include=referencedDocument.basename)
        if referencedDocument not in visited and (
            referencedDocument.inDTS or referencedDocument.type == ModelDocument.Type.INLINEXBRLDOCUMENTSET) and ( # ignore EdgarRenderer added non-DTS documents
            not extensionFiledStandardTaxonomy):
            checkFilingDTS(val, referencedDocument, isEFM, isGFM, visited)

    if modelDocument.type == ModelDocument.Type.INLINEXBRLDOCUMENTSET:
        return # nothing to check in inline document set surrogate parent

    if val.disclosureSystem.standardTaxonomiesDict is None:
        pass

    if isEFM:
        if modelDocument.uri not in val.disclosureSystem.standardTaxonomiesDict:
            if len(modelDocument.basename) > 32:
                val.modelXbrl.error("EFM.5.01.01.tooManyCharacters",
                    _("Document file name %(filename)s must not exceed 32 characters."),
                    edgarCode="cp-0501-File-Name-Length",
                    modelObject=modelDocument, filename=modelDocument.basename)
            if modelDocument.type != ModelDocument.Type.INLINEXBRLDOCUMENTSET:
                if modelDocument.type == ModelDocument.Type.INLINEXBRL:
                    _pattern = htmlFileNamePattern
                    _suffix = ".htm"
                else:
                    _pattern = efmFilenamePattern
                    _suffix = ".xsd or .xml"
                if not _pattern.match(modelDocument.basename) and not extensionFiledStandardTaxonomy:
                    val.modelXbrl.error("EFM.5.01.01",
                        _("Document file name %(filename)s must start with a-z or 0-9, contain upper or lower case letters, ., -, _, and end with %(suffix)s."),
                        edgarCode="cp-0501-File-Name",
                        modelObject=modelDocument, filename=modelDocument.basename, suffix=_suffix)

    if (modelDocument.type == ModelDocument.Type.SCHEMA and
        modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces and
        modelDocument.uri.startswith(val.modelXbrl.uriDir)
        and not extensionFiledStandardTaxonomy
        ):

        val.hasExtensionSchema = True
        disclosureSystemVersion = val.disclosureSystem.version
        # check schema contents types
        # 6.7.3 check namespace for standard authority
        targetNamespaceAuthority = UrlUtil.authority(modelDocument.targetNamespace)
        if targetNamespaceAuthority in val.disclosureSystem.standardAuthorities:
            val.modelXbrl.error(("EFM.6.07.03", "GFM.1.03.03"),
                _("The target namespace, %(targetNamespace)s cannot have the same authority (%(targetNamespaceAuthority)s) as a standard "
                  "taxonomy, in %(schema)s.  Please change your target namespace."),
                edgarCode="fs-0703-Extension-Has-Standard-Namespace-Authority",
                modelObject=modelDocument, schema=modelDocument.basename, targetNamespace=modelDocument.targetNamespace,
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
                _("You did not adhere to the requirements for target namespace, for %(targetNamespace)s in %(schema)s.  "
                  "Please recheck your submission and adhere to the target namespace requirements."),
                edgarCode="cp-0704-Taxonomy-Valid-Target-Namespace",
                modelObject=modelDocument, schema=modelDocument.basename, targetNamespace=modelDocument.targetNamespace)
        elif val.fileNameDate and date > val.fileNameDate:
            val.modelXbrl.info(("EFM.6.07.06", "GFM.1.03.06"),
                _("Warning: Taxonomy schema %(schema)s namespace %(targetNamespace)s has date later than document name date %(docNameDate)s"),
                modelObject=modelDocument, schema=modelDocument.basename, targetNamespace=modelDocument.targetNamespace,
                docNameDate=val.fileNameDate)

        if modelDocument.targetNamespace is not None:
            # 6.7.5 check prefix for _
            authority = UrlUtil.authority(modelDocument.targetNamespace)
            if not re.match(r"(http://|https://|ftp://|urn:)\w+",authority):
                val.modelXbrl.error(("EFM.6.07.05", "GFM.1.03.05"),
                    _("Taxonomy schema %(schema)s namespace %(targetNamespace)s must be a valid URI with a valid authority for the namespace."),
                    edgarCode="du-0705-Namespace-Authority",
                    modelObject=modelDocument, schema=modelDocument.basename, targetNamespace=modelDocument.targetNamespace)
            # may be multiple prefixes for namespace
            prefixes = [(prefix if prefix is not None else "")
                        for prefix, NS in modelDocument.xmlRootElement.nsmap.items()
                        if NS == modelDocument.targetNamespace]
            if not prefixes:
                prefix = None
                val.modelXbrl.error(("EFM.6.07.07", "GFM.1.03.07"),
                    _("The schema does not supply a prefix for %(targetNamespace)s without an underscore character, in file %(schema)s. "
                      "Please provide or change a prefix"),
                    edgarCode="du-0707-Recommended-Prefix-Disallowed",
                    modelObject=modelDocument, schema=modelDocument.basename, targetNamespace=modelDocument.targetNamespace)
            else:
                prefix = prefixes[0]
                if len(prefixes) > 1:
                    val.modelXbrl.error(("EFM.6.07.07", "GFM.1.03.07"),
                        _("The schema does not supply a prefix for %(targetNamespace)s without an underscore character, in file %(schema)s. "
                          "Please provide or change a prefix"),
                        edgarCode="du-0707-Recommended-Prefix-Disallowed",
                        modelObject=modelDocument, schema=modelDocument.basename, targetNamespace=modelDocument.targetNamespace, prefix=", ".join(prefixes))
                elif "_" in prefix:
                    val.modelXbrl.error(("EFM.6.07.07", "GFM.1.03.07"),
                        _("The schema does not supply a prefix for %(targetNamespace)s without an underscore character, in file %(schema)s. "
                          "Please provide or change a prefix"),
                        edgarCode="du-0707-Recommended-Prefix-Disallowed",
                        modelObject=modelDocument, schema=modelDocument.basename, targetNamespace=modelDocument.targetNamespace, prefix=prefix)

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
                                    _("Your extension taxonomy contains an element, %(concept)s, which has the same name as an element in the base taxonomy, "
                                      "%(standardConcept)s.  Please ensure that this extension is appropriate and if so, please change the extension concept name."),
                                    edgarCode="cp-0716-Element-Name-Same-As-Base",
                                    modelObject=(modelConcept,c), concept=modelConcept.qname, standardSchema=c.modelDocument.basename, standardConcept=c.qname)

                    # 6.7.17 id properly formed
                    _id = modelConcept.id
                    requiredId = (prefix if prefix is not None else "") + "_" + name
                    if _id != requiredId:
                        val.modelXbrl.error(("EFM.6.07.17", "GFM.1.03.19"),
                            _("You did not adhere to the declarations for concepts by containing an 'id' attribute whose value begins with the recommended "
                              "namespace prefix of the taxonomy, followed by an underscore, followed by an element name, for the concept %(concept)s.  "
                              "Please recheck your submission."),
                            edgarCode="cp-0717-Element-Id",
                            modelObject=modelConcept, concept=modelConcept.qname, id=_id, requiredId=requiredId)

                    # 6.7.18 nillable is true
                    nillable = modelConcept.get("nillable")
                    if nillable != "true" and modelConcept.isItem:
                        val.modelXbrl.error(("EFM.6.07.18", "GFM.1.03.20"),
                            _("Element %(concept)s is declared without a 'true' value for the nillable attribute.  Please set the value to 'true'."),
                            edgarCode="du-0718-Nillable-Not-True",
                            modelObject=modelConcept, schema=modelDocument.basename,
                            concept=name, nillable=nillable)

                    # 6.7.19 not tuple
                    if modelConcept.isTuple:
                        val.modelXbrl.error(("EFM.6.07.19", "GFM.1.03.21"),
                            _("You provided an extension concept which is a tuple, %(concept)s.  Please remove tuples and check your submission."),
                            edgarCode="cp-0719-No-Tuple-Element",
                            modelObject=modelConcept, concept=modelConcept.qname)

                    # 6.7.20 no typed domain ref
                    if modelConcept.isTypedDimension:
                        val.modelXbrl.error(("EFM.6.07.20", "GFM.1.03.22"),
                            _("There is an xbrldt:typedDomainRef attribute on %(concept)s (%(typedDomainRef)s). Please remove it."),
                            edgarCode="du-0720-Typed-Domain-Ref-Disallowed",
                            modelObject=modelConcept, concept=modelConcept.qname,
                            typedDomainRef=modelConcept.typedDomainElement.qname if modelConcept.typedDomainElement is not None else modelConcept.typedDomainRef)

                    # 6.7.21 abstract must be duration
                    isDuration = modelConcept.periodType == "duration"
                    if modelConcept.isAbstract and not isDuration:
                        val.modelXbrl.error(("EFM.6.07.21", "GFM.1.03.23"),
                            _("Element %(concept)s is declared as an abstract item with period type 'instant'.  Please change it to 'duration' or "
                              "make the element not abstract."),
                            edgarCode="du-0721-Abstract-Is-Instant",
                            modelObject=modelConcept, schema=modelDocument.basename, concept=modelConcept.qname)

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
                            _("The substitution group 'xbrldt:dimensionItem' is only consistent with an element name that ends with 'Axis'.  "
                              "Please change %(conceptLocalName)s or change the substitutionGroup."),
                            edgarCode="du-0723-Axis-Dimension-Name-Mismatch",
                            modelObject=modelConcept, concept=modelConcept.qname, conceptLocalName=modelConcept.qname.localName)

                    # 6.7.24 Table must be subs group hypercube
                    if name.endswith("Table") ^ (substitutionGroupQname == XbrlConst.qnXbrldtHypercubeItem):
                        val.modelXbrl.error(("EFM.6.07.24", "GFM.1.03.26"),
                            _("The substitution group 'xbrldt:hypercubeItem' is only allowed with an element name that ends with 'Table'.  "
                              "Please change %(conceptLocalName)s or change the substitutionGroup."),
                            edgarCode="du-0724-Table-Hypercube-Name-Mismatch",
                            modelObject=modelConcept, schema=modelDocument.basename, concept=modelConcept.qname, conceptLocalName=modelConcept.qname.localName)

                    # 6.7.25 if neither hypercube or dimension, substitution group must be item
                    if substitutionGroupQname not in (None,
                                                        XbrlConst.qnXbrldtDimensionItem,
                                                        XbrlConst.qnXbrldtHypercubeItem,
                                                        XbrlConst.qnXbrliItem):
                        val.modelXbrl.error(("EFM.6.07.25", "GFM.1.03.27"),
                            _("The substitution group attribute value %(substitutionGroup)s of element %(conceptLocalName)s is not allowed.  "
                              "Please change it to one of 'xbrli:item', 'xbrldt:dimensionItem' or 'xbrldt:hypercubeItem'."),
                            edgarCode="du-0725-Substitution-Group-Custom",
                            modelObject=modelConcept, concept=modelConcept.qname, conceptLocalName=modelConcept.qname.localName,
                            substitutionGroup=modelConcept.substitutionGroupQname)

                    # 6.7.26 Table must be subs group hypercube
                    if name.endswith("LineItems") and modelConcept.abstract != "true":
                        val.modelXbrl.error(("EFM.6.07.26", "GFM.1.03.28"),
                            _("The element %(conceptLocalName)s ends with 'LineItems' but is not abstract. Please change %(conceptLocalName)s or "
                              "the value of the 'abstract' attribute."),
                            edgarCode="du-0726-LineItems-Abstract-Name-Mismatch",
                            modelObject=modelConcept, concept=modelConcept.qname, conceptLocalName=modelConcept.qname.localName)

                    # 6.7.27 type domainMember must end with Domain or Member
                    conceptType = modelConcept.type
                    isDomainItemType = conceptType is not None and conceptType.isDomainItemType
                    endsWithDomainOrMember = name.endswith("Domain") or name.endswith("Member")
                    if isDomainItemType != endsWithDomainOrMember:
                        val.modelXbrl.error(("EFM.6.07.27", "GFM.1.03.29"),
                            _("The type 'us-types:domainItemType' is only allowed with an element name that ends with 'Domain' or 'Member'.  "
                              "Please change %(conceptLocalName)s or change the type."),
                            edgarCode="du-0727-Domain-Type-Name-Mismatch",
                            modelObject=modelConcept, concept=modelConcept.qname, conceptLocalName=modelConcept.qname.localName)

                    # 6.7.28 domainItemType must be duration
                    if isDomainItemType and not isDuration:
                        val.modelXbrl.error(("EFM.6.07.28", "GFM.1.03.30"),
                            _("Element %(conceptLocalName)s is declared as a us-types:domainItemType with period type 'instant'.  "
                              "Please change it to 'duration' or change the item type."),
                            edgarCode="du-0728-Domain-Member-Is-Instant",
                            modelObject=modelConcept, concept=modelConcept.qname, conceptLocalName=modelConcept.qname.localName)

                    #6.7.31 (version 27) fractions
                    if modelConcept.isFraction:
                        val.modelXbrl.error("EFM.6.07.31",
                            _("Element %(concept)s is declared as a fraction item type.  Change or remove the declaration."),
                            edgarCode="du-0731-Fraction-Item-Type",
                            modelObject=modelConcept, concept=modelConcept.qname)

                    #6.7.32 (version 27) instant non numeric
                    if modelConcept.isItem and not isDuration:
                        if val.disclosureSystemVersion[0] >= 58:
                            #6.7.32 text block must be duration
                            if modelConcept.isTextBlock:
                                val.modelXbrl.error("EFM.6.07.32",
                                    _("Declaration of element %(concept)s in %(schema)s must have xbrli:periodType of 'duration' because its base type is a text block."),
                                    edgarCode="rq-0732-TextBlock-Must-Be-Duration",
                                    modelObject=modelConcept, schema=modelDocument.basename, concept=modelConcept.qname)
                        else:
                            if not modelConcept.isNumeric and not modelConcept.isAbstract and not isDomainItemType:
                                val.modelXbrl.error("EFM.6.07.32",
                                    _("Declaration of element %(concept)s in %(schema)s must have xbrli:periodType of 'duration' because its base type is not numeric."),
                                    edgarCode="rq-0732-Nonnnumeric-Must-Be-Duration",
                                    modelObject=modelConcept, schema=modelDocument.basename, concept=modelConcept.qname)

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
                        _("Role %(roleType)s does not begin with %(targetNamespace)s's scheme and authority. "
                          "Please change the role URI or target namespace URI."),
                        edgarCode="du-0709-Role-Namespace-Mismatch",
                        modelObject=e, roleType=roleURI, targetNamespaceAuthority=targetNamespaceAuthority, targetNamespace=modelDocument.targetNamespace)
                # 6.7.9 end with .../role/lc3 name
                if not roleTypePattern.match(roleURI):
                    val.modelXbrl.warning(("EFM.6.07.09.roleEnding", "GFM.1.03.09"),
                        "RoleType %(roleType)s should end with /role/{mnemonic name}",
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
                                _("The role %(roleType)s did not provide a usedOn element for all three link types (presentation, "
                                  "calculation and definition), missing %(usedOn)s. Change the declaration to be for all three types of link, and resubmit."),
                                edgarCode="du-0711-Role-Type-Declaration-Incomplete",
                                modelObject=e, roleType=roleURI, usedOn=requiredUsedOns - usedOns)

                        # 6.7.12 definition match pattern
                        if (val.disclosureSystem.roleDefinitionPattern is not None and
                            (definition is None or not val.disclosureSystem.roleDefinitionPattern.match(definition))):
                            val.modelXbrl.error(("EFM.6.07.12", "GFM.1.03.12-14"),
                                _("The definition '%(definition)s' of role %(roleType)s does not match the expected format. "
                                  "Please check that the definition matches {number} - {type} - {text}."),
                                edgarCode="rq-0712-Role-Definition-Mismatch",
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
                        _("Relationship role %(arcroleType)s does not begin with %(targetNamespace)s's scheme and authority.  "
                          "Please change the relationship role URI or target namespace URI."),
                        edgarCode="du-0713-Arcrole-Namespace-Mismatch",
                        modelObject=e, arcroleType=arcroleURI, targetNamespaceAuthority=targetNamespaceAuthority, targetNamespace=modelDocument.targetNamespace)
                # 6.7.13 end with .../arcrole/lc3 name
                if not arcroleTypePattern.match(arcroleURI):
                    val.modelXbrl.warning(("EFM.6.07.13.arcroleEnding", "GFM.1.03.15"),
                        _("ArcroleType %(arcroleType)s should end with /arcrole/{mnemonic name}"),
                        modelObject=e, arcroleType=arcroleURI)

                # 6.7.15 definition match pattern
                modelRoleTypes = val.modelXbrl.arcroleTypes[arcroleURI]
                definition = modelRoleTypes[0].definition
                if definition is None or not arcroleDefinitionPattern.match(definition):
                    val.modelXbrl.error(("EFM.6.07.15", "GFM.1.03.17"),
                        _("Relationship role declaration %(arcroleType)s is missing a definition.  Please provide a definition."),
                        edgarCode="du-0715-Arcrole-Definition-Missing",
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
                                        _("Non-numeric element %(concept)s has a label role for numeric elements: %(role)s. "
                                          "Please change the role attribute."),
                                        edgarCode="du-1009-Numeric-Label-Role",
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
