'''
See COPYRIGHT.md for copyright information.

Deprecated Nov 15, 2015.  Use plugin/validate/SBRnl
'''

from arelle import ModelDocument, XbrlConst, XmlUtil
from arelle.ModelDtsObject import ModelConcept, ModelType, ModelLocator, ModelResource
from arelle.ModelObject import ModelObject
import regex as re
from lxml import etree


def setup(val, modelXbrl, *args, **kwargs):
    cntlr = modelXbrl.modelManager.cntlr
    val.prefixNamespace = {}
    val.namespacePrefix = {}
    val.idObjects = {}

'''
def factCheck(val, fact):
    concept = fact.concept
    context = fact.context
    if concept is None or context is None:
        return # not checkable

    try:
    except Exception as err:
'''

def final(val, conceptsUsed, *args, **kwargs):
    modelXbrl = val.modelXbrl
    # moved from ValidateFiling
    for qname, modelType in modelXbrl.qnameTypes.items():
        if qname.namespaceURI not in val.disclosureSystem.baseTaxonomyNamespaces:
            facets = modelType.facets
            if facets:
                lengthFacets = tfacets.keys() & {"minLength", "maxLength", "length"}
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
        for roleURI, modelRoleTypes in modelXbrl.roleTypes.items():
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
    standardXbrlSchmas = XbrlConst.standardNamespaceSchemaLocations.values()
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

    del val.prefixNamespace, val.namespacePrefix, val.idObjects

def checkDTSdocument(val, modelDocument, *args, **kwargs):
    modelXbrl = val.modelXbrl
    if modelDocument.type in (ModelDocument.Type.SCHEMA, ModelDocument.Type.LINKBASE):
        isSchema = modelDocument.type == ModelDocument.Type.SCHEMA
        docinfo = modelDocument.xmlDocument.docinfo
        if docinfo and docinfo.xml_version != "1.0":
            modelXbrl.error("SBR.NL.2.2.0.02" if isSchema else "SBR.NL.2.3.0.02",
                    _('%(docType)s xml version must be "1.0" but is "%(xmlVersion)s"'),
                    modelObject=modelDocument, docType=modelDocument.gettype().title(),
                    xmlVersion=docinfo.xml_version)
        if modelDocument.documentEncoding.lower() != "utf-8":
            modelXbrl.error("SBR.NL.2.2.0.03" if isSchema else "SBR.NL.2.3.0.03",
                    _('%(docType)s encoding must be "utf-8" but is "%(xmlEncoding)s"'),
                    modelObject=modelDocument, docType=modelDocument.gettype().title(),
                    xmlEncoding=modelDocument.documentEncoding)
        lookingForPrecedingComment = True
        for commentNode in modelDocument.xmlRootElement.itersiblings(preceding=True):
            if isinstance(commentNode, etree._Comment):
                if lookingForPrecedingComment:
                    lookingForPrecedingComment = False
                else:
                    modelXbrl.error("SBR.NL.2.2.0.05" if isSchema else "SBR.NL.2.3.0.05",
                            _('%(docType)s must have only one comment node before schema element'),
                            modelObject=modelDocument, docType=modelDocument.gettype().title())
        if lookingForPrecedingComment:
            modelXbrl.error("SBR.NL.2.2.0.04" if isSchema else "SBR.NL.2.3.0.04",
                _('%(docType)s must have comment node only on line 2'),
                modelObject=modelDocument, docType=modelDocument.gettype().title())

        # check namespaces are used
        for prefix, ns in modelDocument.xmlRootElement.nsmap.items():
            if ((prefix not in val.valUsedPrefixes) and
                (modelDocument.type != ModelDocument.Type.SCHEMA or ns != modelDocument.targetNamespace)):
                modelXbrl.error("SBR.NL.2.2.0.11" if modelDocument.type == ModelDocument.Type.SCHEMA else "SBR.NL.2.3.0.08",
                    _('%(docType)s namespace declaration "%(declaration)s" is not used'),
                    modelObject=modelDocument, docType=modelDocument.gettype().title(),
                    declaration=("xmlns" + (":" + prefix if prefix else "") + "=" + ns))

        if isSchema and val.annotationsCount > 1:
            modelXbrl.error("SBR.NL.2.2.0.22",
                _('Schema has %(annotationsCount)s xs:annotation elements, only 1 allowed'),
                modelObject=modelDocument, annotationsCount=val.annotationsCount)
    if modelDocument.type == ModelDocument.Type.LINKBASE:
        if not val.containsRelationship:
            modelXbrl.error("SBR.NL.2.3.0.12",
                "Linkbase has no relationships",
                modelObject=modelDocument)
        # check file name suffixes
        extLinkElt = XmlUtil.descendant(modelDocument.xmlRootElement, XbrlConst.link, "*", "{http://www.w3.org/1999/xlink}type", "extended")
        if extLinkElt is not None:
            expectedSuffix = None
            if extLinkElt.localName == "labelLink":
                anyLabel = XmlUtil.descendant(modelDocument.xmlRootElement, XbrlConst.link, "label", "{http://www.w3.org/XML/1998/namespace}lang", "*")
                if anyLabel is not None:
                    xmlLang = anyLabel.get("{http://www.w3.org/XML/1998/namespace}lang")
                    expectedSuffix = "-lab-{0}.xml".format(xmlLang)
            else:
                expectedSuffix = {"referenceLink": "-ref.xml",
                                  "presentationLink": "-pre.xml",
                                  "definitionLink": "-def.xml"}.get(extLinkElt.localName, None)
            if expectedSuffix:
                if not modelDocument.uri.endswith(expectedSuffix):
                    modelXbrl.error("SBR.NL.3.2.1.09",
                        "Linkbase filename expected to end with %(expectedSuffix)s: %(filename)s",
                        modelObject=modelDocument, expectedSuffix=expectedSuffix, filename=modelDocument.uri)
            elif extLinkElt.qname == XbrlConst.qnGenLink:
                anyLabel = XmlUtil.descendant(modelDocument.xmlRootElement, XbrlConst.link, "label", "{http://www.w3.org/XML/1998/namespace}lang", "*")
                if anyLabel is not None:
                    xmlLang = anyLabel.get("{http://www.w3.org/XML/1998/namespace}lang")
                    expectedSuffix = "-generic-lab-{0}.xml".format(xmlLang)
                elif XmlUtil.descendant(modelDocument.xmlRootElement, XbrlConst.link, "reference") is not None:
                    expectedSuffix = "-generic-ref.xml"
                if expectedSuffix and not modelDocument.uri.endswith(expectedSuffix):
                    modelXbrl.error("SBR.NL.3.2.1.10",
                        "Generic linkbase filename expected to end with %(expectedSuffix)s: %(filename)s",
                        modelObject=modelDocument, expectedSuffix=expectedSuffix, filename=modelDocument.uri)
        # label checks
        for qnLabel in (XbrlConst.qnLinkLabel, XbrlConst.qnGenLabel):
            for modelLabel in modelDocument.xmlRootElement.iterdescendants(tag=qnLabel.clarkNotation):
                if isinstance(modelLabel, ModelResource):
                    if not modelLabel.text or not modelLabel.text[:1].isupper():
                        modelXbrl.error("SBR.NL.3.2.7.05",
                            _("Labels MUST have a capital first letter, label %(label)s: %(text)s"),
                            modelObject=modelLabel, label=modelLabel.xlinkLabel, text=modelLabel.text[:64])
                    if modelLabel.role in (XbrlConst.standardLabel, XbrlConst.genStandardLabel):
                        if len(modelLabel.text) > 255:
                            modelXbrl.error("SBR.NL.3.2.7.06",
                                _("Labels with the 'standard' role MUST NOT exceed 255 characters, label %(label)s: %(text)s"),
                                modelObject=modelLabel, label=modelLabel.xlinkLabel, text=modelLabel.text[:64])
                if modelLabel.role in (XbrlConst.standardLabel, XbrlConst.genStandardLabel):
                    if len(modelLabel.text) > 255:
                        modelXbrl.error("SBR.NL.3.2.7.06",
                            _("Labels with the 'standard' role MUST NOT exceed 255 characters, label %(label)s: %(text)s"),
                            modelObject=modelLabel, label=modelLabel.xlinkLabel, text=modelLabel.text[:64])
        for modelResource in modelDocument.xmlRootElement.iter():
            # locator checks
            if isinstance(modelResource, ModelLocator):
                hrefModelObject = modelResource.dereference()
                if isinstance(hrefModelObject, ModelObject):
                    expectedLocLabel = hrefModelObject.id + "_loc"
                    if modelResource.xlinkLabel != expectedLocLabel:
                        modelXbrl.error("SBR.NL.3.2.11.01",
                            _("Locator @xlink:label names MUST be concatenated from: @id from the XML node, underscore, 'loc', expected %(expectedLocLabel)s, found %(foundLocLabel)s"),
                            modelObject=modelResource, expectedLocLabel=expectedLocLabel, foundLocLabel=modelResource.xlinkLabel)
            # xlinkLabel checks
            if isinstance(modelResource, ModelResource):
                if re.match(r"[^a-zA-Z0-9_-]", modelResource.xlinkLabel):
                    modelXbrl.error("SBR.NL.3.2.11.03",
                        _("@xlink:label names MUST use a-zA-Z0-9_- characters only: %(xlinkLabel)s"),
                        modelObject=modelResource, xlinkLabel=modelResource.xlinkLabel)
    elif modelDocument.targetNamespace: # SCHEMA with targetNamespace
        # check for unused imports
        for referencedDocument in modelDocument.referencesDocument.keys():
            if (referencedDocument.type == ModelDocument.Type.SCHEMA and
                referencedDocument.targetNamespace not in {XbrlConst.xbrli, XbrlConst.link} and
                referencedDocument.targetNamespace not in val.referencedNamespaces):
                modelXbrl.error("SBR.NL.2.2.0.15",
                    _("A schema import schemas of which no content is being addressed: %(importedFile)s"),
                    modelObject=modelDocument, importedFile=referencedDocument.basename)
        if modelDocument.targetNamespace != modelDocument.targetNamespace.lower():
            modelXbrl.error("SBR.NL.3.2.3.02",
                _("Namespace URI's MUST be lower case: %(namespaceURI)s"),
                modelObject=modelDocument, namespaceURI=modelDocument.targetNamespace)
        if len(modelDocument.targetNamespace) > 255:
            modelXbrl.error("SBR.NL.3.2.3.03",
                _("Namespace URI's MUST NOT be longer than 255 characters: %(namespaceURI)s"),
                modelObject=modelDocument, namespaceURI=modelDocument.targetNamespace)
        if re.match(r"[^a-z0-9_/-]", modelDocument.targetNamespace):
            modelXbrl.error("SBR.NL.3.2.3.04",
                _("Namespace URI's MUST use only signs from a-z0-9_-/: %(namespaceURI)s"),
                modelObject=modelDocument, namespaceURI=modelDocument.targetNamespace)
        if not modelDocument.targetNamespace.startswith('http://www.nltaxonomie.nl'):
            modelXbrl.error("SBR.NL.3.2.3.05",
                _("Namespace URI's MUST start with 'http://www.nltaxonomie.nl': %(namespaceURI)s"),
                modelObject=modelDocument, namespaceURI=modelDocument.targetNamespace)
        namespacePrefix = XmlUtil.xmlnsprefix(modelDocument.xmlRootElement, modelDocument.targetNamespace)
        if not namespacePrefix:
            modelXbrl.error("SBR.NL.3.2.4.01",
                _("TargetNamespaces MUST have a prefix: %(namespaceURI)s"),
                modelObject=modelDocument, namespaceURI=modelDocument.targetNamespace)
        elif namespacePrefix in val.prefixNamespace:
            modelXbrl.error("SBR.NL.3.2.4.02",
                _("Namespace prefix MUST be unique within the NT but prefix '%(prefix)s' is used by both %(namespaceURI)s and %(namespaceURI2)s."),
                modelObject=modelDocument, prefix=namespacePrefix,
                namespaceURI=modelDocument.targetNamespace, namespaceURI2=val.prefixNamespace[namespacePrefix])
        else:
            val.prefixNamespace[namespacePrefix] = modelDocument.targetNamespace
            val.namespacePrefix[modelDocument.targetNamespace] = namespacePrefix
        if namespacePrefix in {"xsi", "xsd", "xs", "xbrli", "link", "xlink", "xbrldt", "xbrldi", "gen", "xl"}:
            modelXbrl.error("SBR.NL.3.2.4.03",
                _("Namespace prefix '%(prefix)s' reserved by organizations for international specifications is used %(namespaceURI)s."),
                modelObject=modelDocument, prefix=namespacePrefix, namespaceURI=modelDocument.targetNamespace)
        if len(namespacePrefix) > 20:
            modelXbrl.warning("SBR.NL.3.2.4.06",
                _("Namespace prefix '%(prefix)s' SHOULD not exceed 20 characters %(namespaceURI)s."),
                modelObject=modelDocument, prefix=namespacePrefix, namespaceURI=modelDocument.targetNamespace)
        # check every non-targetnamespace prefix against its schema
    requiredLinkrole = None # only set for extension taxonomies
    # check folder names
    if modelDocument.filepathdir.startswith(modelXbrl.uriDir):
        partnerPrefix = None
        pathDir = modelDocument.filepathdir[len(modelXbrl.uriDir) + 1:].replace("\\", "/")
        lastPathSegment = None
        for pathSegment in pathDir.split("/"):
            if pathSegment.lower() != pathSegment:
                modelXbrl.error("SBR.NL.3.2.1.02",
                    _("Folder names must be in lower case: %(folder)s"),
                    modelObject=modelDocument, folder=pathSegment)
            if len(pathSegment) >= 15 :
                modelXbrl.error("SBR.NL.3.2.1.03",
                    _("Folder names must be less than 15 characters: %(folder)s"),
                    modelObject=modelDocument, folder=pathSegment)
            if pathSegment in ("bd", "kvk", "cbs"):
                partnerPrefix = pathSegment + '-'
            lastPathSegment = pathSegment
        if modelDocument.basename.lower() != modelDocument.basename:
            modelXbrl.error("SBR.NL.3.2.1.05",
                _("File names must be in lower case: %(file)s"),
                modelObject=modelDocument, file=modelDocument.basename)
        if partnerPrefix and not modelDocument.basename.startswith(partnerPrefix):
            modelXbrl.error("SBR.NL.3.2.1.14",
                "NT Partner DTS files MUST start with %(partnerPrefix)s consistently: %(filename)s",
                modelObject=modelDocument, partnerPrefix=partnerPrefix, filename=modelDocument.uri)
        if modelDocument.type == ModelDocument.Type.SCHEMA:
            if modelDocument.targetNamespace:
                nsParts = modelDocument.targetNamespace.split("/")
                # [0] = https, [1] = // [2] = nl.taxonomie  [3] = year or version
                nsYrOrVer = nsParts[3]
                requiredNamespace = "http://www.nltaxonomie.nl/" + nsYrOrVer + "/" + pathDir + "/" + modelDocument.basename[:-4]
                requiredLinkrole = "http://www.nltaxonomie.nl/" + nsYrOrVer + "/" + pathDir + "/"
                if modelDocument == modelXbrl.modelDocument:  # entry point
                    nsYr = "{year}"
                    if '2009' <= nsParts[3] < '2020':  # must be a year, use as year
                        nsYr = nsParts[3]
                    else: # look for year in parts of basename of required namespace
                        for nsPart in nsParts:
                            for baseNamePart in nsPart.split('-'):
                                if '2009' <= baseNamePart < '2020':
                                    nsYr = baseNamePart
                                    break
                    if not requiredNamespace.endswith('-' + nsYr):
                        requiredNamespace += '-' + nsYr
                if not modelDocument.targetNamespace.startswith(requiredNamespace):
                    modelXbrl.error("SBR.NL.3.2.3.06",
                        _("Namespace URI's MUST be constructed like %(requiredNamespace)s: %(namespaceURI)s"),
                        modelObject=modelDocument, requiredNamespace=requiredNamespace, namespaceURI=modelDocument.targetNamespace)
            else:
                requiredLinkrole = ''
            # concept checks
            for modelConcept in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/2001/XMLSchema}element"):
                if isinstance(modelConcept, ModelConcept):
                    # 6.7.16 name not duplicated in standard taxonomies
                    name = modelConcept.get("name")
                    if name:
                        ''' removed per RH 2013-03-25
                        substititutionGroupQname = modelConcept.substitutionGroupQname
                        if substititutionGroupQname:
                            if name.endswith("Member") ^ (substititutionGroupQname.localName == "domainMemberItem" and
                                                          substititutionGroupQname.namespaceURI.endswith("/xbrl/xbrl-syntax-extension")):
                                modelXbrl.error("SBR.NL.3.2.5.11",
                                    _("Concept %(concept)s must end in Member to be in sbr:domainMemberItem substitution group"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if name.endswith("Domain") ^ (substititutionGroupQname.localName == "domainItem" and
                                                          substititutionGroupQname.namespaceURI.endswith("/xbrl/xbrl-syntax-extension")):
                                modelXbrl.error("SBR.NL.3.2.5.12",
                                    _("Concept %(concept)s must end in Domain to be in sbr:domainItem substitution group"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if name.endswith("TypedAxis") ^ (substititutionGroupQname == XbrlConst.qnXbrldtDimensionItem and
                                                             modelConcept.isTypedDimension):
                                modelXbrl.error("SBR.NL.3.2.5.14",
                                    _("Concept %(concept)s must end in TypedAxis to be in xbrldt:dimensionItem substitution group if they represent a typed dimension"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if (name.endswith("Axis") and
                                not name.endswith("TypedAxis")) ^ (substititutionGroupQname == XbrlConst.qnXbrldtDimensionItem and
                                                                   modelConcept.isExplicitDimension):
                                modelXbrl.error("SBR.NL.3.2.5.13",
                                    _("Concept %(concept)s must end in Axis to be in xbrldt:dimensionItem substitution group if they represent an explicit dimension"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if name.endswith("Table") ^ (substititutionGroupQname == XbrlConst.qnXbrldtHypercubeItem):
                                modelXbrl.error("SBR.NL.3.2.5.15",
                                    _("Concept %(concept)s must end in Table to be in xbrldt:hypercubeItem substitution group"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if name.endswith("Title") ^ (substititutionGroupQname.localName == "presentationItem" and
                                                         substititutionGroupQname.namespaceURI.endswith("/xbrl/xbrl-syntax-extension")):
                                modelXbrl.error("SBR.NL.3.2.5.16",
                                    _("Concept %(concept)s must end in Title to be in sbr:presentationItem substitution group"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                        '''
                        if len(name) > 200:
                            modelXbrl.error("SBR.NL.3.2.12.02" if modelConcept.isLinkPart
                                                else "SBR.NL.3.2.5.21" if (modelConcept.isItem or modelConcept.isTuple)
                                                else "SBR.NL.3.2.14.01",
                                _("Concept %(concept)s name length %(namelength)s exceeds 200 characters"),
                                modelObject=modelConcept, concept=modelConcept.qname, namelength=len(name))
            # type checks
            for typeType in ("simpleType", "complexType"):
                for modelType in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/2001/XMLSchema}" + typeType):
                    if isinstance(modelType, ModelType):
                        name = modelType.get("name")
                        if name is None:
                            name = ""
                            if modelType.get("ref") is not None:
                                continue    # don't validate ref's here
                        if len(name) > 200:
                            modelXbrl.error("SBR.NL.3.2.5.21",
                                _("Type %(type)s name length %(namelength)s exceeds 200 characters"),
                                modelObject=modelType, type=modelType.qname, namelength=len(name))
                        if modelType.qnameDerivedFrom and modelType.qnameDerivedFrom.namespaceURI != XbrlConst.xbrli:
                            modelXbrl.error("SBR.NL.3.2.8.01",
                                _("Custom datatypes MUST be a restriction from XII defined datatypes: %(type)s"),
                                modelObject=modelType, type=modelType.qname)
                        if re.match(r"[^a-zA-Z0-9_-]", name):
                            modelXbrl.error("SBR.NL.3.2.8.02",
                                _("Datatype names MUST use characters a-zA-Z0-9_- only: %(type)s"),
                                modelObject=modelDocument, type=modelType.qname)
                        if modelType.facets and "enumeration" in modelType.facets:
                            if not modelType.qnameDerivedFrom == XbrlConst.qnXbrliStringItemType:
                                modelXbrl.error("SBR.NL.3.2.13.01",
                                    _("Enumerations MUST use a restriction on xbrli:stringItemType: %(type)s"),
                                    modelObject=modelDocument, type=modelType.qname)
            if lastPathSegment == "entrypoints":
                if not modelDocument.xmlRootElement.id:
                    modelXbrl.error("SBR.NL.2.2.0.23",
                        _("xs:schema/@id MUST be present in schema files in the reports/{NT partner}/entrypoints/ folder"),
                        modelObject=modelDocument)


    # check for idObject conflicts
    for id, modelObject in modelDocument.idObjects.items():
        if id in val.idObjects:
            modelXbrl.error("SBR.NL.3.2.6.01",
                _("ID %(id)s must be unique in the DTS but is present on two elements."),
                modelObject=(modelObject, val.idObjects[id]), id=id)
        else:
            val.idObjects[id] = modelObject


    for roleURI, modelRoleTypes in modelXbrl.roleTypes.items():
        if not roleURI.startswith("http://www.xbrl.org"):
            usedOns = set.union(*[modelRoleType.usedOns for modelRoleType in modelRoleTypes])
            # check roletypes for linkroles (only)
            if usedOns & {XbrlConst.qnLinkPresentationLink, XbrlConst.qnLinkCalculationLink, XbrlConst.qnLinkDefinitionLink,
                          XbrlConst.qnLinkLabel, XbrlConst.qnLinkReference, XbrlConst.qnLinkFootnote}:
                if len(modelRoleTypes) > 1:
                    modelXbrl.error("SBR.NL.3.2.9.01",
                        _("Linkrole URI's MUST be unique in the NT: %(linkrole)s"),
                        modelObject=modelRoleTypes, linkrole=roleURI)
                if roleURI.lower() != roleURI:
                    modelXbrl.error("SBR.NL.3.2.9.02",
                        _("Linkrole URI's MUST be in lowercase: %(linkrole)s"),
                        modelObject=modelRoleTypes, linkrole=roleURI)
                if re.match(r"[^a-z0-9_/-]", roleURI):
                    modelXbrl.error("SBR.NL.3.2.9.03",
                        _("Linkrole URI's MUST use characters a-z0-9_-/ only: %(linkrole)s"),
                        modelObject=modelRoleTypes, linkrole=roleURI)
                if len(roleURI) > 255:
                    modelXbrl.error("SBR.NL.3.2.9.04",
                        _("Linkrole URI's MUST NOT be longer than 255 characters, length is %(len)s: %(linkrole)s"),
                        modelObject=modelRoleTypes, len=len(roleURI), linkrole=roleURI)
                ''' removed per RH 2013-03-13 e-mail
                if not roleURI.startswith('http://www.nltaxonomie.nl'):
                    modelXbrl.error("SBR.NL.3.2.9.05",
                        _("Linkrole URI's MUST start with 'http://www.nltaxonomie.nl': %(linkrole)s"),
                        modelObject=modelRoleTypes, linkrole=roleURI)
                if (requiredLinkrole and
                    not roleURI.startswith(requiredLinkrole) and
                    re.match(r".*(domain$|axis$|table$|lineitem$)", roleURI)):
                        modelXbrl.error("SBR.NL.3.2.9.06",
                            _("Linkrole URI's MUST have the following construct: http://www.nltaxonomie.nl / {folder path} / {functional name} - {domain or axis or table or lineitem}: %(linkrole)s"),
                            modelObject=modelRoleTypes, linkrole=roleURI)
                '''
                for modelRoleType in modelRoleTypes:
                    if len(modelRoleType.id) > 255:
                        modelXbrl.error("SBR.NL.3.2.10.02",
                            _("Linkrole @id MUST NOT exceed 255 characters, length is %(length)s: %(linkroleID)s"),
                            modelObject=modelRoleType, length=len(modelRoleType.id), linkroleID=modelRoleType.id)
                partnerPrefix = modelRoleTypes[0].modelDocument.basename.split('-')
                if partnerPrefix:  # first element before dash is prefix
                    urnPartnerLinkroleStart = "urn:{0}:linkrole:".format(partnerPrefix[0])
                    if not roleURI.startswith(urnPartnerLinkroleStart):
                        modelXbrl.error("SBR.NL.3.2.9.10",
                            _("Linkrole MUST start with urn:{NT partner code}:linkrole:, \nexpecting: %(expectedStart)s..., \nfound: %(linkrole)s"),
                            modelObject=modelRoleType, expectedStart=urnPartnerLinkroleStart, linkrole=roleURI)

def checkForBOMs(modelXbrl, file, mappedUri, filepath, *args, **kwargs):
    # callback is for all opened docs, must only process when SBRNL validation active
    if (modelXbrl.modelManager.validateDisclosureSystem and
        modelXbrl.modelManager.disclosureSystem.SBRNL):
        #must read file in binary and return nothing to not replace standard loading
        with open(filepath, 'rb') as fb:
            startingBytes = fb.read(8)
            if re.match(b"\\x00\\x00\\xFE\\xFF|\\xFF\\xFE\\x00\\x00|\\x2B\\x2F\\x76\\x38|\\x2B\\x2F\\x76\\x39|\\x2B\\x2F\\x76\\x2B|\\x2B\\x2F\\x76\\x2F|\\xDD\\x73\\x66\\x73|\\xEF\\xBB\\xBF|\\x0E\\xFE\\xFF|\\xFB\\xEE\\x28|\\xFE\\xFF|\\xFF\\xFE",
                        startingBytes):
                modelXbrl.error("SBR.NL.2.1.0.09",
                    _("File MUST not start with a Byte Order Mark (BOM): %(filename)s"),
                    modelObject=modelXbrl, filename=mappedUri)
    return None # must return None for regular document loading to continue

''' Deprecated and thus commented out so not recognized as a plugin
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate SBR-NL',
    'version': '0.9',
    'description': "SBR-NL Validation.",
    'license': 'Apache-2',
    'author': 'S. Bee Are',
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'Validate.SBRNL.Start': setup,
    # 'Validate.SBRNL.Fact': factCheck  (no instances being checked by SBRNL,
    'Validate.SBRNL.Finally': final,
    'Validate.SBRNL.DTS.document': checkDTSdocument,
    'ModelDocument.CustomLoader': checkForBOMs
}
'''
