'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
from typing import TYPE_CHECKING
from arelle import (ModelDocument, ModelDtsObject, HtmlUtil, UrlUtil, XmlUtil, XbrlUtil, XbrlConst,
                    XmlValidate)
from arelle.ModelRelationshipSet import baseSetRelationship
from arelle.ModelObject import ModelObject, ModelComment
from arelle.ModelValue import qname
from arelle.PluginManager import pluginClassMethods
from arelle.XhtmlValidate import ixMsgCode
from lxml import etree
from collections import defaultdict
import regex as re

if TYPE_CHECKING:
    from arelle.ValidateXbrl import ValidateXbrl


instanceSequence = {"schemaRef":1, "linkbaseRef":2, "roleRef":3, "arcroleRef":4}
schemaTop = {"import", "include", "redefine"}
schemaBottom = {"element", "attribute", "notation", "simpleType", "complexType", "group", "attributeGroup"}
xsd1_1datatypes = {qname(XbrlConst.xsd,'anyAtomicType'), qname(XbrlConst.xsd,'yearMonthDuration'), qname(XbrlConst.xsd,'dayTimeDuration'), qname(XbrlConst.xsd,'dateTimeStamp'), qname(XbrlConst.xsd,'precisionDecimal')}
link_loc_spec_sections = {"labelLink":"5.2.2.1",
                          "referenceLink":"5.2.3.1",
                          "calculationLink":"5.2.5.1",
                          "definitionLink":"5.2.6.1",
                          "presentationLink":"5.2.4.1",
                          "footnoteLink":"4.11.1.1"}
standard_roles_for_ext_links = ("xbrl.3.5.3", (XbrlConst.defaultLinkRole,))
standard_roles_definitions = {
    XbrlConst.qnLinkDefinitionLink: standard_roles_for_ext_links,
    XbrlConst.qnLinkCalculationLink: standard_roles_for_ext_links,
    XbrlConst.qnLinkPresentationLink: standard_roles_for_ext_links,
    XbrlConst.qnLinkLabelLink: standard_roles_for_ext_links,
    XbrlConst.qnLinkReferenceLink: standard_roles_for_ext_links,
    XbrlConst.qnLinkFootnoteLink: standard_roles_for_ext_links,
    XbrlConst.qnIXbrl11Relationship: standard_roles_for_ext_links, # has xlinkRole of footnoteLinks
    XbrlConst.qnLinkLabel: ("xbrl.5.2.2.2.2", XbrlConst.standardLabelRoles),
    XbrlConst.qnLinkReference: ("xbrl.5.2.3.2.1", XbrlConst.standardReferenceRoles),
    XbrlConst.qnLinkFootnote: ("xbrl.4.11.1.2", (XbrlConst.footnote,)),
    XbrlConst.qnLinkLinkbaseRef: ("xbrl.4.3.4", XbrlConst.standardLinkbaseRefRoles),
    XbrlConst.qnLinkLoc: ("xbrl.3.5.3.7", ())
    }
standard_roles_other = ("xbrl.5.1.3", ())

inlineDisplayNonePattern = re.compile(r"display\s*:\s*none")

def arcFromConceptQname(arcElement):
    modelRelationship = baseSetRelationship(arcElement)
    if modelRelationship is None:
        return arcElement.get("{http://www.w3.org/1999/xlink}from")
    else:
        return modelRelationship.fromModelObject.qname

def arcToConceptQname(arcElement):
    modelRelationship = baseSetRelationship(arcElement)
    if modelRelationship is None:
        return arcElement.get("{http://www.w3.org/1999/xlink}to")
    else:
        return modelRelationship.toModelObject.qname

def checkDTS(val: ValidateXbrl, modelDocument: ModelDocument.ModelDocument, checkedModelDocuments: set[ModelDocument.ModelDocument]) -> None:
    checkedModelDocuments.add(modelDocument)
    for referencedDocument in modelDocument.referencesDocument.keys():
        if referencedDocument not in checkedModelDocuments:
            checkDTS(val, referencedDocument, checkedModelDocuments)

    # skip processing versioning report here
    if modelDocument.type == ModelDocument.Type.VERSIONINGREPORT:
        return

    # skip processing if skipDTS requested
    if modelDocument.skipDTS:
        return

    # skip system schemas
    if modelDocument.type == ModelDocument.Type.SCHEMA:
        if XbrlConst.isStandardNamespace(modelDocument.targetNamespace):
            return
        val.hasLinkRole = val.hasLinkPart = val.hasContextFragment = val.hasAbstractItem = \
            val.hasTuple = val.hasNonAbstractElement = val.hasType = val.hasEnumeration = \
            val.hasDimension = val.hasDomain = val.hasHypercube = False


    # check for linked up hrefs
    isInstance = (modelDocument.type == ModelDocument.Type.INSTANCE or
                  modelDocument.type == ModelDocument.Type.INLINEXBRL)
    if not hasattr(val, "ixdsRoleRefURIs"):
        val.ixdsRoleRefURIs = val.ixdsArcroleRefURIs = {} # in case no ixds
    if modelDocument.type == ModelDocument.Type.INLINEXBRL:
        if not val.validateIXDS: # set up IXDS validation
            val.validateIXDS = True
            val.ixdsDocs = []
            val.ixdsFootnotes = {}
            val.ixdsHeaderCount = 0
            val.ixdsTuples = {}
            val.ixdsReferences = defaultdict(list)
            val.ixdsRelationships = []
            val.ixdsRoleRefURIs = val.modelXbrl.targetRoleRefs  # roleRefs defined for current targets
            val.ixdsArcroleRefURIs = val.modelXbrl.targetArcroleRefs  # arcroleRefs defined for current targets
        # accumulate all role/arcrole refs across target document instance files
        val.roleRefURIs = val.ixdsRoleRefURIs
        val.arcroleRefURIs = val.ixdsArcroleRefURIs
        val.ixdsDocs.append(modelDocument)

    for hrefElt, hrefedDoc, hrefId in modelDocument.hrefObjects:
        hrefedElt = None
        if hrefedDoc is None:
            val.modelXbrl.error("xbrl:hrefFileNotFound",
                _("Href %(elementHref)s file not found"),
                modelObject=hrefElt,
                elementHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
        else:
            if hrefedDoc.type != ModelDocument.Type.UnknownNonXML:
                if hrefId:
                    if hrefId in hrefedDoc.idObjects:
                        hrefedElt = hrefedDoc.idObjects[hrefId]
                    else:
                        hrefedElt = XmlUtil.xpointerElement(hrefedDoc,hrefId)
                        if hrefedElt is None:
                            val.modelXbrl.error("xbrl.3.5.4:hrefIdNotFound",
                                _("Href %(elementHref)s not located"),
                                modelObject=hrefElt,
                                elementHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
                else:
                    hrefedElt = hrefedDoc.xmlRootElement

            if hrefId:  #check scheme regardless of whether document loaded
                # check all xpointer schemes
                for scheme, path in XmlUtil.xpointerSchemes(hrefId):
                    if scheme != "element":
                        val.modelXbrl.error("xbrl.3.5.4:hrefScheme",
                            _("Href %(elementHref)s unsupported scheme: %(scheme)s"),
                            modelObject=hrefElt,
                            elementHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"),
                            scheme=scheme)
                        break
                    elif val.validateEFMorGFM:
                        val.modelXbrl.error(("EFM.6.03.06", "GFM.1.01.03"),
                            _("Href %(elementHref)s may only have shorthand xpointers"),
                            modelObject=hrefElt,
                            elementHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
            # check href'ed target if a linkbaseRef
            if hrefElt.namespaceURI == XbrlConst.link:
                if hrefElt.localName == "linkbaseRef":
                    # check linkbaseRef target
                    if (hrefedDoc is None or
                        hrefedDoc.type < ModelDocument.Type.firstXBRLtype or  # range of doc types that can have linkbase
                        hrefedDoc.type > ModelDocument.Type.lastXBRLtype or
                        hrefedElt.namespaceURI != XbrlConst.link or hrefedElt.localName != "linkbase"):
                        val.modelXbrl.error("xbrl.4.3.2:linkbaseRefHref",
                            _("LinkbaseRef %(linkbaseHref)s does not identify an link:linkbase element"),
                            modelObject=(hrefElt, hrefedDoc),
                            linkbaseHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
                    elif hrefElt.get("{http://www.w3.org/1999/xlink}role") is not None:
                        role = hrefElt.get("{http://www.w3.org/1999/xlink}role")
                        for linkNode in hrefedElt.iterchildren():
                            if (isinstance(linkNode,ModelObject) and
                                linkNode.get("{http://www.w3.org/1999/xlink}type") == "extended"):
                                ln = linkNode.localName
                                ns = linkNode.namespaceURI
                                if (role == "http://www.xbrl.org/2003/role/calculationLinkbaseRef" and \
                                    (ns != XbrlConst.link or ln != "calculationLink")) or \
                                   (role == "http://www.xbrl.org/2003/role/definitionLinkbaseRef" and \
                                    (ns != XbrlConst.link or ln != "definitionLink")) or \
                                   (role == "http://www.xbrl.org/2003/role/presentationLinkbaseRef" and \
                                    (ns != XbrlConst.link or ln != "presentationLink")) or \
                                   (role == "http://www.xbrl.org/2003/role/labelLinkbaseRef" and \
                                    (ns != XbrlConst.link or ln != "labelLink")) or \
                                   (role == "http://www.xbrl.org/2003/role/referenceLinkbaseRef" and \
                                    (ns != XbrlConst.link or ln != "referenceLink")):
                                    val.modelXbrl.error("xbrl.4.3.4:linkbaseRefLinks",
                                        "LinkbaseRef %(linkbaseHref)s role %(role)s has wrong extended link %(link)s",
                                        modelObject=hrefElt,
                                        linkbaseHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"),
                                        role=role, link=linkNode.prefixedName)
                elif hrefElt.localName == "schemaRef":
                    # check schemaRef target
                    if (hrefedDoc.type != ModelDocument.Type.SCHEMA or
                        hrefedElt.namespaceURI != XbrlConst.xsd or hrefedElt.localName != "schema"):
                        val.modelXbrl.error("xbrl.4.2.2:schemaRefHref",
                            _("SchemaRef %(schemaRef)s does not identify an xsd:schema element"),
                            modelObject=hrefElt, schemaRef=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
                # check loc target
                elif hrefElt.localName == "loc":
                    linkElt = hrefElt.getparent()
                    if linkElt.namespaceURI ==  XbrlConst.link:
                        acceptableTarget = False
                        hrefEltKey = linkElt.localName
                        if hrefElt in val.remoteResourceLocElements:
                            hrefEltKey += "ToResource"
                        for tgtTag in {
                                   "labelLink":("{http://www.w3.org/2001/XMLSchema}element", "{http://www.xbrl.org/2003/linkbase}label"),
                                   "labelLinkToResource":("{http://www.xbrl.org/2003/linkbase}label",),
                                   "referenceLink":("{http://www.w3.org/2001/XMLSchema}element", "{http://www.xbrl.org/2003/linkbase}reference"),
                                   "referenceLinkToResource":("{http://www.xbrl.org/2003/linkbase}reference",),
                                   "calculationLink":("{http://www.w3.org/2001/XMLSchema}element",),
                                   "definitionLink":("{http://www.w3.org/2001/XMLSchema}element",),
                                   "presentationLink":("{http://www.w3.org/2001/XMLSchema}element",),
                                   "footnoteLink":("XBRL-item-or-tuple",) }[hrefEltKey]:
                            if tgtTag == "XBRL-item-or-tuple":
                                concept = val.modelXbrl.qnameConcepts.get(qname(hrefedElt))
                                acceptableTarget =  isinstance(concept, ModelDtsObject.ModelConcept) and \
                                                    (concept.isItem or concept.isTuple)
                            elif hrefedElt is not None and hrefedElt.tag == tgtTag:
                                acceptableTarget = True
                        if not acceptableTarget:
                            val.modelXbrl.error("xbrl.{0}:{1}LocTarget".format(
                                            {"labelLink":"5.2.2.1",
                                             "referenceLink":"5.2.3.1",
                                             "calculationLink":"5.2.5.1",
                                             "definitionLink":"5.2.6.1",
                                             "presentationLink":"5.2.4.1",
                                             "footnoteLink":"4.11.1.1"}[linkElt.localName],
                                             linkElt.localName),
                                 _("%(linkElement)s loc href %(locHref)s must identify a %(acceptableTarget)s"),
                                 modelObject=hrefElt, linkElement=linkElt.localName,
                                 locHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"),
                                 acceptableTarget= {"labelLink": "concept or label",
                                                    "labelLinkToResource": "label",
                                                    "referenceLink":"concept or reference",
                                                    "referenceLinkToResource":"reference",
                                                    "calculationLink": "concept",
                                                    "definitionLink": "concept",
                                                    "presentationLink": "concept",
                                                    "footnoteLink": "item or tuple" }[hrefEltKey],
                                 messageCodes=("xbrl.5.2.2.1:labelLinkLocTarget", "xbrl.5.2.3.1:referenceLinkLocTarget", "xbrl.5.2.5.1:calculationLinkLocTarget", "xbrl.5.2.6.1:definitionLinkLocTarget", "xbrl.5.2.4.1:presentationLinkLocTarget", "xbrl.4.11.1.1:footnoteLinkLocTarget"))
                        if isInstance and not XmlUtil.isDescendantOf(hrefedElt, modelDocument.xmlRootElement):
                            val.modelXbrl.error("xbrl.4.11.1.1:instanceLoc",
                                _("Instance loc's href %(locHref)s not an element in same instance"),
                                 modelObject=hrefElt, locHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
                    ''' is this ever needed???
                    else: # generic link or other non-2.1 link element
                        if (hrefElt.modelDocument.inDTS and
                            ModelDocument.Type.firstXBRLtype <= hrefElt.modelDocument.type <= ModelDocument.Type.lastXBRLtype and # is a discovered linkbase
                            not ModelDocument.Type.firstXBRLtype <= hrefedDoc.type <= ModelDocument.Type.lastXBRLtype): # must discover schema or linkbase
                            val.modelXbrl.error("xbrl.3.2.3:linkLocTarget",
                                _("Locator %(xlinkLabel)s on link:loc in a discovered linkbase does not target a schema or linkbase"),
                                modelObject=(hrefedElt, hrefedDoc),
                                xlinkLabel=hrefElt.get("{http://www.w3.org/1999/xlink}label"))
                    '''
                    # non-standard link holds standard loc, href must be discovered document
                    if (hrefedDoc.type < ModelDocument.Type.firstXBRLtype or  # range of doc types that can have linkbase
                        hrefedDoc.type > ModelDocument.Type.lastXBRLtype or
                        not hrefedDoc.inDTS):
                        val.modelXbrl.error("xbrl.3.5.3.7.2:instanceLocInDTS",
                            _("Loc's href %(locHref)s does not identify an element in an XBRL document discovered as part of the DTS"),
                            modelObject=hrefElt, locHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))

    # used in linkbase children navigation but may be errant linkbase elements
    val.roleRefURIs = {}
    val.arcroleRefURIs = {}
    val.elementIDs = {}
    val.conceptNames = {}
    val.annotationsCount = 0

    # XML validation checks (remove if using validating XML)
    val.extendedElementName = None
    isFilingDocument = False
    # validate contents of entry point document or its sibling/descendant documents or in report package of entry point
    if ((modelDocument.uri.startswith(val.modelXbrl.uriDir) or # document uri in same subtree as entry doocument
         (val.modelXbrl.fileSource.isOpen and modelDocument.filepath.startswith(val.modelXbrl.fileSource.baseurl))) and # document in entry submission's package
        modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces and
        modelDocument.xmlDocument):
        isFilingDocument = True
        val.valUsedPrefixes = set()
        val.schemaRoleTypes = {}
        val.schemaArcroleTypes = {}
        val.referencedNamespaces = set()

        val.containsRelationship = False

        checkElements(val, modelDocument, modelDocument.xmlDocument)

        if (modelDocument.type == ModelDocument.Type.INLINEXBRL and
            val.validateGFM and
            (val.documentTypeEncoding.lower() != 'utf-8' or val.metaContentTypeEncoding.lower() != 'utf-8')):
            val.modelXbrl.error("GFM.1.10.4",
                    _("XML declaration encoding %(encoding)s and meta content type encoding %(metaContentTypeEncoding)s must both be utf-8"),
                    modelXbrl=modelDocument, encoding=val.documentTypeEncoding,
                    metaContentTypeEncoding=val.metaContentTypeEncoding)
        if val.validateSBRNL:
            for pluginXbrlMethod in pluginClassMethods("Validate.SBRNL.DTS.document"):
                pluginXbrlMethod(val, modelDocument)
        del val.valUsedPrefixes
        del val.schemaRoleTypes
        del val.schemaArcroleTypes
    for pluginXbrlMethod in pluginClassMethods("Validate.XBRL.DTS.document"):
        pluginXbrlMethod(val, modelDocument, isFilingDocument)

    val.roleRefURIs = None
    val.arcroleRefURIs = None
    val.elementIDs = None
    val.conceptNames = None

def checkElements(val, modelDocument, parent):
    isSchema = modelDocument.type == ModelDocument.Type.SCHEMA
    if isinstance(parent, ModelObject):
        parentXlinkType = parent.get("{http://www.w3.org/1999/xlink}type")
        isInstance = parent.namespaceURI == XbrlConst.xbrli and parent.localName == "xbrl"
        parentIsLinkbase = parent.namespaceURI == XbrlConst.link and parent.localName == "linkbase"
        parentIsSchema = parent.namespaceURI == XbrlConst.xsd and parent.localName == "schema"
        if isInstance or parentIsLinkbase: # only for non-inline instance
            val.roleRefURIs = {} # uses ixdsRoleRefURIs when inline instance (across current target documents)
            val.arcroleRefURIs = {}
            def linkbaseTopElts():
                for refPass in (True, False): # do roleType and arcroleType before extended links and any other children
                    for child in parent.iterchildren():
                        if refPass == (isinstance(child,ModelObject)
                                       and child.localName in ("roleRef","arcroleRef")
                                       and child.namespaceURI == XbrlConst.link):
                            yield child
            childrenIter = linkbaseTopElts()
        else:
            childrenIter = parent.iterchildren()
    else: # parent is document node, not an element
        parentXlinkType = None
        isInstance = False
        parentIsLinkbase = False
        rootElement = parent.getroot()
        if isinstance(rootElement, etree._Element) and rootElement.tag == 'nsmap':
            childrenIter = rootElement # causes first for loop to iterate nsmap children
        else:
            childrenIter = (rootElement,) # causes first for loop to process the root element itself
        if isSchema:
            val.inSchemaTop = True

    parentIsAppinfo = False
    if modelDocument.type == ModelDocument.Type.INLINEXBRL:
        if isinstance(parent,ModelObject): # element
            if (parent.localName == "meta" and parent.namespaceURI == XbrlConst.xhtml and
                (parent.get("http-equiv") or "").lower() == "content-type"):
                val.metaContentTypeEncoding = HtmlUtil.attrValue(parent.get("content"), "charset")
        elif isinstance(parent,etree._ElementTree): # documentNode
            val.documentTypeEncoding = modelDocument.documentEncoding # parent.docinfo.encoding
            val.metaContentTypeEncoding = ""

    instanceOrder = 0
    if modelDocument.type == ModelDocument.Type.SCHEMA:
        ncnameTests = (("id","xml.3.3.1:idMustBeUnique", val.elementIDs),
                       ("name","xbrl.5.1.1:conceptName", val.conceptNames))
    else:
        ncnameTests = (("id","xml.3.3.1:idMustBeUnique", val.elementIDs),)
    for elt in childrenIter:
        if isinstance(elt,ModelObject):
            for name, errCode, _valueItems in ncnameTests:
                if elt.get(name) is not None:
                    attrValue = elt.get(name)
                    ''' done in XmlValidate now
                    if not val.NCnamePattern.match(attrValue):
                        val.modelXbrl.error(errCode,
                            _("Element %(element)s attribute %(attribute)s '%(value)s' is not an NCname"),
                            modelObject=elt, element=elt.prefixedName, attribute=name, value=attrValue)
                    '''
                    if name == "id" or (isinstance(elt, ModelDtsObject.ModelConcept) and (elt.isItem or elt.isTuple)):
                        if attrValue in _valueItems:
                            # 2.1 spec @id validation refers to http://www.w3.org/TR/REC-xml#NT-TokenizedType
                            # TODO: this check should not test inline elements, those should be in ModelDocument inlineIxdsDiscover using ixdsEltById
                            val.modelXbrl.error(errCode,
                                _("Element %(element)s %(attribute)s %(value)s is duplicated"),
                                modelObject=(elt,_valueItems[attrValue]), element=elt.prefixedName, attribute=name, value=attrValue,
                                messageCodes=("xml.3.3.1:idMustBeUnique", "xbrl.5.1.1:conceptName"))
                        else:
                            _valueItems[attrValue] = elt

            # checks for elements in schemas only
            if isSchema:
                if elt.namespaceURI == XbrlConst.xsd:
                    localName = elt.localName
                    if localName == "schema":
                        XmlValidate.validate(val.modelXbrl, elt)
                        targetNamespace = elt.get("targetNamespace")
                        if targetNamespace is not None:
                            if targetNamespace == "":
                                val.modelXbrl.error("xbrl.5.1:emptyTargetNamespace",
                                    "Schema element has an empty targetNamespace",
                                    modelObject=elt)
                            if val.validateEFM and len(targetNamespace) > 85:
                                l = len(targetNamespace.encode("utf-8"))
                                if l > 255:
                                    val.modelXbrl.error("EFM.6.07.30",
                                        _("Schema targetNamespace length (%(length)s) is over 255 bytes long in utf-8 %(targetNamespace)s"),
                                        edgarCode="du-0730-Uri-Length-Limit",
                                        modelObject=elt, length=l, targetNamespace=targetNamespace, value=targetNamespace)
                        if val.validateSBRNL:
                            if elt.get("targetNamespace") is None:
                                val.modelXbrl.error("SBR.NL.2.2.0.08",
                                    _('Schema element must have a targetNamespace attribute'),
                                    modelObject=elt)
                            if (elt.get("attributeFormDefault") != "unqualified" or
                                elt.get("elementFormDefault") != "qualified"):
                                val.modelXbrl.error("SBR.NL.2.2.0.09",
                                        _('Schema element attributeFormDefault must be "unqualified" and elementFormDefault must be "qualified"'),
                                        modelObject=elt)
                            for attrName in ("blockDefault", "finalDefault", "version"):
                                if elt.get(attrName) is not None:
                                    val.modelXbrl.error("SBR.NL.2.2.0.10",
                                        _('Schema element must not have a %(attribute)s attribute'),
                                        modelObject=elt, attribute=attrName)
                    elif val.validateSBRNL:
                        if localName in ("assert", "openContent", "fallback"):
                            val.modelXbrl.error("SBR.NL.2.2.0.01",
                                _('Schema contains XSD 1.1 content "%(element)s"'),
                                modelObject=elt, element=elt.qname)

                        if localName == "element":
                            for attr, presence, errCode in (("block", False, "2.2.2.09"),
                                                            ("final", False, "2.2.2.10"),
                                                            ("fixed", False, "2.2.2.11"),
                                                            ("form", False, "2.2.2.12"),):
                                if (elt.get(attr) is not None) != presence:
                                    val.modelXbrl.error("SBR.NL.{0}".format(errCode),
                                        _('Schema element %(concept)s %(requirement)s contain attribute %(attribute)s'),
                                        modelObject=elt, concept=elt.get("name"),
                                        requirement=(_("MUST NOT"),_("MUST"))[presence], attribute=attr,
                                        messageCodes=("SBR.NL.2.2.2.09", "SBR.NL.2.2.2.10", "SBR.NL.2.2.2.11", "SBR.NL.2.2.2.12"))
                            eltName = elt.get("name")
                            if eltName is not None: # skip for concepts which are refs
                                type = qname(elt, elt.get("type"))
                                eltQname = elt.qname
                                if type in xsd1_1datatypes:
                                    val.modelXbrl.error("SBR.NL.2.2.0.01",
                                        _('Schema element %(concept)s contains XSD 1.1 datatype "%(xsdType)s"'),
                                        modelObject=elt, concept=elt.get("name"), xsdType=type)
                                if not parentIsSchema: # root element
                                    if elt.get("name") is not None and (elt.isItem or elt.isTuple):
                                        val.modelXbrl.error("SBR.NL.2.2.2.01",
                                            _('Schema concept definition is not at the root level: %(concept)s'),
                                            modelObject=elt, concept=elt.get("name"))
                                elif eltQname not in val.typedDomainQnames:
                                    for attr, presence, errCode in (("abstract", True, "2.2.2.08"),
                                                                    ("id", True, "2.2.2.13"),
                                                                    ("nillable", True, "2.2.2.15"),
                                                                    ("substitutionGroup", True, "2.2.2.18"),):
                                        if (elt.get(attr) is not None) != presence:
                                            val.modelXbrl.error("SBR.NL.{0}".format(errCode),
                                                _('Schema root element %(concept)s %(requirement)s contain attribute %(attribute)s'),
                                                modelObject=elt, concept=elt.get("name"),
                                                requirement=(_("MUST NOT"),_("MUST"))[presence], attribute=attr,
                                                messageCodes=("SBR.NL.2.2.2.08", "SBR.NL.2.2.2.13", "SBR.NL.2.2.2.15", "SBR.NL.2.2.2.18"))
                                # semantic checks
                                if elt.isTuple:
                                    val.hasTuple = True
                                elif elt.isLinkPart:
                                    val.hasLinkPart = True
                                elif elt.isItem:
                                    if elt.isDimensionItem:
                                        val.hasDimension = True
                                    #elif elt.substitutesFor()
                                    if elt.isAbstract:
                                        val.hasAbstractItem = True
                                    else:
                                        val.hasNonAbstraceElement = True
                                if elt.isAbstract and elt.isItem:
                                    val.hasAbstractItem = True
                                if elt.typeQname is not None:
                                    val.referencedNamespaces.add(elt.typeQname.namespaceURI)
                                if elt.substitutionGroupQname is not None:
                                    val.referencedNamespaces.add(elt.substitutionGroupQname.namespaceURI)
                                if elt.isTypedDimension and elt.typedDomainElement is not None:
                                    val.referencedNamespaces.add(elt.typedDomainElement.namespaceURI)
                            else:
                                referencedElt = elt.dereference()
                                if referencedElt is not None:
                                    val.referencedNamespaces.add(referencedElt.modelDocument.targetNamespace)
                            if not parentIsSchema:
                                eltDecl = elt.dereference()
                                if (elt.get("minOccurs") is None or elt.get("maxOccurs") is None):
                                    val.modelXbrl.error("SBR.NL.2.2.2.14",
                                        _('Schema %(element)s must have minOccurs and maxOccurs'),
                                        modelObject=elt, element=eltDecl.qname)
                                elif elt.get("maxOccurs") != "1" and eltDecl.isItem:
                                    val.modelXbrl.error("SBR.NL.2.2.2.30",
                                        _("Tuple concept %(concept)s must have maxOccurs='1'"),
                                        modelObject=elt, concept=eltDecl.qname)
                                if eltDecl.isItem and eltDecl.isAbstract:
                                    val.modelXbrl.error("SBR.NL.2.2.2.31",
                                        _("Abstract concept %(concept)s must not be a child of a tuple"),
                                        modelObject=elt, concept=eltDecl.qname)
                        elif localName in ("sequence","choice"):
                            for attrName in ("minOccurs", "maxOccurs"):
                                attrValue = elt.get(attrName)
                                if  attrValue is None:
                                    val.modelXbrl.error("SBR.NL.2.2.2.14",
                                        _('Schema %(element)s must have %(attrName)s'),
                                        modelObject=elt, element=elt.elementQname, attrName=attrName)
                                elif attrValue != "1":
                                    val.modelXbrl.error("SBR.NL.2.2.2.33",
                                        _('Schema %(element)s must have %(attrName)s = "1"'),
                                        modelObject=elt, element=elt.elementQname, attrName=attrName)
                        elif localName in {"complexType","simpleType"}:
                            qnameDerivedFrom = elt.qnameDerivedFrom
                            if qnameDerivedFrom is not None:
                                if isinstance(qnameDerivedFrom, list): # union
                                    for qn in qnameDerivedFrom:
                                        val.referencedNamespaces.add(qn.namespaceURI)
                                else: # not union type
                                    val.referencedNamespaces.add(qnameDerivedFrom.namespaceURI)
                        elif localName == "attribute":
                            if elt.typeQname is not None:
                                val.referencedNamespaces.add(elt.typeQname.namespaceURI)
                    if localName == "redefine":
                        val.modelXbrl.error("xbrl.5.6.1:Redefine",
                            "Redefine is not allowed",
                            modelObject=elt)
                    if localName in {"attribute", "element", "attributeGroup"}:
                        ref = elt.get("ref")
                        if ref is not None:
                            if qname(elt, ref) not in {"attribute":val.modelXbrl.qnameAttributes,
                                                       "element":val.modelXbrl.qnameConcepts,
                                                       "attributeGroup":val.modelXbrl.qnameAttributeGroups}[localName]:
                                val.modelXbrl.error("xmlSchema:refNotFound",
                                    _("%(element)s ref %(ref)s not found"),
                                    modelObject=elt, element=localName, ref=ref)
                        if val.validateSBRNL and localName == "attribute":
                            val.modelXbrl.error("SBR.NL.2.2.11.06",
                                _('xs:attribute must not be used'), modelObject=elt)

                    if localName == "appinfo":
                        if val.validateSBRNL:
                            if (parent.localName != "annotation" or parent.namespaceURI != XbrlConst.xsd or
                                parent.getparent().localName != "schema" or parent.getparent().namespaceURI != XbrlConst.xsd or
                                XmlUtil.previousSiblingElement(parent) != None):
                                val.modelXbrl.error("SBR.NL.2.2.0.12",
                                    _('Annotation/appinfo record must be be behind schema and before import'), modelObject=elt)
                            nextSiblingElement = XmlUtil.nextSiblingElement(parent)
                            if nextSiblingElement is not None and nextSiblingElement.localName != "import":
                                val.modelXbrl.error("SBR.NL.2.2.0.14",
                                    _('Annotation/appinfo record must be followed only by import'),
                                    modelObject=elt)
                    if localName == "annotation":
                        val.annotationsCount += 1
                        if val.validateSBRNL and not XmlUtil.hasChild(elt,XbrlConst.xsd,"appinfo"):
                            val.modelXbrl.error("SBR.NL.2.2.0.12",
                                _('Schema file annotation missing appinfo element must be be behind schema and before import'),
                                modelObject=elt)

                    if val.validateEFM and localName in {"element", "complexType", "simpleType"}:
                        name = elt.get("name")
                        if name and len(name) > 64:
                            l = len(name.encode("utf-8"))
                            if l > 200:
                                val.modelXbrl.error("EFM.6.07.29",
                                    _("Schema %(element)s has a name length (%(length)s) over 200 bytes long in utf-8, %(name)s."),
                                    edgarCode="du-0729-Name-Length-Limit",
                                    modelObject=elt, element=localName, name=name, length=l)

                    if val.validateSBRNL and localName in {"all", "documentation", "any", "anyAttribute", "attributeGroup",
                                                                # comment out per R.H. 2011-11-16 "complexContent", "complexType", "extension",
                                                                "field", "group", "key", "keyref",
                                                                "list", "notation", "redefine", "selector", "unique"}:
                        val.modelXbrl.error("SBR.NL.2.2.11.{0:02}".format({"all":1, "documentation":2, "any":3, "anyAttribute":4, "attributeGroup":7,
                                                                  "complexContent":10, "complexType":11, "extension":12, "field":13, "group":14, "key":15, "keyref":16,
                                                                  "list":17, "notation":18, "redefine":20, "selector":22, "unique":23}[localName]),
                            _('Schema file element must not be used "%(element)s"'),
                            modelObject=elt, element=elt.qname,
                            messageCodes=("SBR.NL.2.2.11.1", "SBR.NL.2.2.11.2", "SBR.NL.2.2.11.3", "SBR.NL.2.2.11.4", "SBR.NL.2.2.11.7", "SBR.NL.2.2.11.10", "SBR.NL.2.2.11.11", "SBR.NL.2.2.11.12",
                                          "SBR.NL.2.2.11.13", "SBR.NL.2.2.11.14", "SBR.NL.2.2.11.15", "SBR.NL.2.2.11.16", "SBR.NL.2.2.11.17", "SBR.NL.2.2.11.18", "SBR.NL.2.2.11.20", "SBR.NL.2.2.11.22", "SBR.NL.2.2.11.23"))
                    if val.inSchemaTop:
                        if localName in schemaBottom:
                            val.inSchemaTop = False
                    elif localName in schemaTop:
                        val.modelXbrl.error("xmlschema.3.4.2:contentModel",
                            _("Element %(element)s is mis-located in schema file"),
                            modelObject=elt, element=elt.prefixedName)

                # check schema roleTypes
                if elt.localName in ("roleType","arcroleType") and elt.namespaceURI == XbrlConst.link:
                    uriAttr, xbrlSection, roleTypes, localRoleTypes = {
                           "roleType":("roleURI","5.1.3",val.modelXbrl.roleTypes, val.schemaRoleTypes),
                           "arcroleType":("arcroleURI","5.1.4",val.modelXbrl.arcroleTypes, val.schemaArcroleTypes)
                           }[elt.localName]
                    if not parent.localName == "appinfo" and parent.namespaceURI == XbrlConst.xsd:
                        val.modelXbrl.error("xbrl.{0}:{1}Appinfo".format(xbrlSection,elt.localName),
                            _("%(element)s not child of xsd:appinfo"),
                            modelObject=elt, element=elt.qname,
                            messageCodes=("xbrl.5.1.3:roleTypeAppinfo", "xbrl.5.1.4:arcroleTypeAppinfo"))
                    else: # parent is appinfo, element IS in the right location
                        XmlValidate.validate(val.modelXbrl, elt) # validate [arc]roleType
                        roleURI = elt.get(uriAttr)
                        if roleURI is None or not UrlUtil.isValidUriReference(roleURI):
                            val.modelXbrl.error("xbrl.{0}:{1}Missing".format(xbrlSection,uriAttr),
                                _("%(element)s missing or invalid %(attribute)s"),
                                modelObject=elt, element=elt.qname, attribute=uriAttr,
                                messageCodes=("xbrl.5.1.3:roleTypeMissing", "xbrl.5.1.4:arcroleTypeMissing"))
                        if roleURI in localRoleTypes:
                            val.modelXbrl.error("xbrl.{0}:{1}Duplicate".format(xbrlSection,elt.localName),
                                _("Duplicate %(element)s %(attribute)s %(roleURI)s"),
                                modelObject=elt, element=elt.qname, attribute=uriAttr, roleURI=roleURI,
                                messageCodes=("xbrl.5.1.3:roleTypeDuplicate", "xbrl.5.1.4:arcroleTypeDuplicate"))
                        else:
                            localRoleTypes[roleURI] = elt
                        for otherRoleType in roleTypes[roleURI]:
                            if elt != otherRoleType and not XbrlUtil.sEqual(val.modelXbrl, elt, otherRoleType):
                                val.modelXbrl.error("xbrl.{0}:{1}s-inequality".format(xbrlSection,elt.localName),
                                    _("%(element)s %(roleURI)s not s-equal in %(otherSchema)s"),
                                    modelObject=elt, element=elt.qname, roleURI=roleURI,
                                    otherSchema=otherRoleType.modelDocument.basename,
                                    messageCodes=("xbrl.5.1.3:roleTypes-inequality", "xbrl.5.1.4:arcroleTypes-inequality"))
                        if elt.localName == "arcroleType":
                            cycles = elt.get("cyclesAllowed")
                            if cycles not in ("any", "undirected", "none"):
                                val.modelXbrl.error("xbrl.{0}:{1}CyclesAllowed".format(xbrlSection,elt.localName),
                                    _("%(element)s %(roleURI)s invalid cyclesAllowed %(value)s"),
                                    modelObject=elt, element=elt.qname, roleURI=roleURI, value=cycles,
                                    messageCodes=("xbrl.5.1.3:roleTypeCyclesAllowed", "xbrl.5.1.4:arcroleTypeCyclesAllowed"))
                            if val.validateSBRNL:
                                val.modelXbrl.error("SBR.NL.2.2.4.01",
                                        _('ArcroleType is not allowed %(roleURI)s'),
                                        modelObject=elt, roleURI=roleURI)
                        else: # roleType
                            if val.validateSBRNL:
                                roleTypeModelObject = modelDocument.idObjects.get(elt.get("id"))
                                if roleTypeModelObject is not None and not roleTypeModelObject.genLabel(lang="nl"):
                                    val.modelXbrl.error("SBR.NL.2.3.8.05",
                                        _('RoleType %(roleURI)s must have a label in lang "nl"'),
                                        modelObject=elt, roleURI=roleURI)
                        if val.validateEFM and len(roleURI) > 85:
                            l = len(roleURI.encode("utf-8"))
                            if l > 255:
                                val.modelXbrl.error("EFM.6.07.30",
                                    _("Schema %(element)s %(attribute)s length (%(length)s) is over 255 bytes long in utf-8 %(roleURI)s"),
                                    modelObject=elt, element=elt.qname, attribute=uriAttr, length=l, roleURI=roleURI, value=roleURI)
                    # check for used on duplications
                    usedOns = set()
                    for usedOn in elt.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}usedOn"):
                        if isinstance(usedOn,ModelObject):
                            qName = qname(usedOn, XmlUtil.text(usedOn))
                            if qName not in usedOns:
                                usedOns.add(qName)
                            else:
                                val.modelXbrl.error("xbrl.{0}:{1}s-inequality".format(xbrlSection,elt.localName),
                                    _("%(element)s %(roleURI)s usedOn %(value)s on has s-equal duplicate"),
                                    modelObject=elt, element=elt.qname, roleURI=roleURI, value=qName,
                                    messageCodes=("xbrl.5.1.3:roleTypes-inequality", "xbrl.5.1.4:arcroleTypes-inequality"))
                            if val.validateSBRNL:
                                val.valUsedPrefixes.add(qName.prefix)
                                if qName == XbrlConst.qnLinkCalculationLink:
                                    val.modelXbrl.error("SBR.NL.2.2.3.01",
                                        _("%(element)s usedOn must not be link:calculationLink"),
                                        modelObject=elt, element=parent.qname, value=qName)
                                if elt.localName == "roleType" and qName in XbrlConst.standardExtLinkQnames:
                                    if not any((key[1] == roleURI  and key[2] == qName)
                                               for key in val.modelXbrl.baseSets.keys()):
                                        val.modelXbrl.error("SBR.NL.2.2.3.02",
                                            _("%(element)s usedOn %(usedOn)s not addressed for role %(role)s"),
                                            modelObject=elt, element=parent.qname, usedOn=qName, role=roleURI)
                elif elt.localName == "linkbase"  and elt.namespaceURI == XbrlConst.link:
                    XmlValidate.validate(val.modelXbrl, elt) # check linkbases inside schema files
                if val.validateSBRNL and not elt.prefix:
                        val.modelXbrl.error("SBR.NL.2.2.0.06",
                                'Schema element is not prefixed: "%(element)s"',
                                modelObject=elt, element=elt.qname)
            elif modelDocument.type == ModelDocument.Type.LINKBASE:
                if elt.localName == "linkbase":
                    XmlValidate.validate(val.modelXbrl, elt)
                if val.validateSBRNL and not elt.prefix:
                        val.modelXbrl.error("SBR.NL.2.2.0.06",
                            _('Linkbase element is not prefixed: "%(element)s"'),
                            modelObject=elt, element=elt.qname)
            # check of roleRefs when parent is linkbase or instance element
            xlinkType = elt.get("{http://www.w3.org/1999/xlink}type")
            xlinkRole = elt.get("{http://www.w3.org/1999/xlink}role")
            if elt.namespaceURI == XbrlConst.link:
                if elt.localName == "linkbase":
                    if elt.parentQname is not None and elt.parentQname not in (XbrlConst.qnXsdAppinfo, XbrlConst.qnNsmap):
                        val.modelXbrl.error("xbrl.5.2:linkbaseRootElement",
                            "Linkbase must be a root element or child of appinfo, and may not be nested in %(parent)s",
                            parent=elt.parentQname,
                            modelObject=elt)
                elif elt.localName in ("roleRef","arcroleRef"):
                    uriAttr, xbrlSection, roleTypeDefs, refs, ixdsTgtRefs = {
                           "roleRef":("roleURI","3.5.2.4",val.modelXbrl.roleTypes,val.roleRefURIs, val.ixdsRoleRefURIs),
                           "arcroleRef":("arcroleURI","3.5.2.5",val.modelXbrl.arcroleTypes,val.arcroleRefURIs, val.ixdsArcroleRefURIs)
                           }[elt.localName]
                    if parentIsAppinfo:
                        pass    #ignore roleTypes in appinfo (test case 160 v05)
                    elif not (parentIsLinkbase or isInstance or elt.parentQname in (XbrlConst.qnIXbrlResources, XbrlConst.qnIXbrl11Resources)):
                        val.modelXbrl.info("info:{1}Location".format(xbrlSection,elt.localName),
                            _("Link:%(elementName)s not child of link:linkbase or xbrli:instance"),
                            modelObject=elt, elementName=elt.localName,
                            messageCodes=("info:roleRefLocation", "info:arcroleRefLocation"))
                    else: # parent is linkbase or instance, element IS in the right location

                        # check for duplicate roleRefs when parent is linkbase or instance element
                        refUri = elt.get(uriAttr)
                        hrefAttr = elt.get("{http://www.w3.org/1999/xlink}href")
                        hrefUri, hrefId = UrlUtil.splitDecodeFragment(hrefAttr)
                        if refUri == "":
                            val.modelXbrl.error("xbrl.{}.5:{}Missing".format(xbrlSection,elt.localName),
                                _("%(element)s %(refURI)s missing"),
                                modelObject=elt, element=elt.qname, refURI=refUri,
                                messageCodes=("xbrl.3.5.2.4.5:roleRefMissing", "xbrl.3.5.2.5.5:arcroleRefMissing"))
                        elif elt.parentQname == XbrlConst.qnIXbrl11Resources and refUri not in ixdsTgtRefs:
                            continue # elt not in this ixds target
                        elif refUri in refs:
                            val.modelXbrl.error("xbrl.{}.5:{}Duplicate".format(xbrlSection,elt.localName),
                                _("%(element)s is duplicated for %(refURI)s"),
                                modelObject=elt, element=elt.qname, refURI=refUri,
                                messageCodes=("xbrl.3.5.2.4.5:roleRefDuplicate", "xbrl.3.5.2.5.5:arcroleRefDuplicate"))
                        elif refUri not in roleTypeDefs:
                            val.modelXbrl.error("xbrl.{}.5:{}NotDefined".format(xbrlSection,elt.localName),
                                _("%(element)s %(refURI)s is not defined"),
                                modelObject=elt, element=elt.qname, refURI=refUri,
                                messageCodes=("xbrl.3.5.2.4.5:roleRefNotDefined", "xbrl.3.5.2.5.5:arcroleRefNotDefined"))
                        else:
                            refs[refUri] = hrefUri
                            roleTypeElt = elt.resolveUri(uri=hrefAttr)
                            if roleTypeElt not in roleTypeDefs[refUri]:
                                val.modelXbrl.error("xbrl.{}.5:{}Mismatch".format(xbrlSection,elt.localName),
                                    _("%(element)s %(refURI)s defined with different URI"),
                                    modelObject=(elt,roleTypeElt), element=elt.qname, refURI=refUri,
                                messageCodes=("xbrl.3.5.2.4.5:roleRefMismatch", "xbrl.3.5.2.5.5:arcroleRefMismatch"))


                        if val.validateEFMorGFMorSBRNL:
                            if elt.localName == "arcroleRef":
                                if hrefUri not in val.disclosureSystem.standardTaxonomiesDict:
                                    val.modelXbrl.error(("EFM.6.09.06", "GFM.1.04.06"),
                                        _("Arcrole %(refURI)s arcroleRef %(xlinkHref)s must be a standard taxonomy"),
                                        modelObject=elt, refURI=refUri, xlinkHref=hrefUri)
                                if val.validateSBRNL:
                                    for attrName, errCode in (("{http://www.w3.org/1999/xlink}arcrole","SBR.NL.2.3.2.05"),("{http://www.w3.org/1999/xlink}role","SBR.NL.2.3.2.06")):
                                        if elt.get(attrName):
                                            val.modelXbrl.error(errCode,
                                                _("Arcrole %(refURI)s arcroleRef %(xlinkHref)s must not have an %(attribute)s attribute"),
                                                modelObject=elt, refURI=refUri, xlinkHref=hrefUri, attribute=attrName,
                                                messageCodes=("SBR.NL.2.3.2.05", "SBR.NL.2.3.2.06"))
                            elif elt.localName == "roleRef":
                                if val.validateSBRNL:
                                    for attrName, errCode in (("{http://www.w3.org/1999/xlink}arcrole","SBR.NL.2.3.10.09"),("{http://www.w3.org/1999/xlink}role","SBR.NL.2.3.10.10")):
                                        if elt.get(attrName):
                                            val.modelXbrl.error(errCode,
                                                _("Role %(refURI)s roleRef %(xlinkHref)s must not have an %(attribute)s attribute"),
                                                modelObject=elt, refURI=refUri, xlinkHref=hrefUri, attribute=attrName,
                                                messageCodes=("SBR.NL.2.3.10.09", "SBR.NL.2.3.10.10"))
                    if val.validateSBRNL:
                        if not xlinkType:
                            val.modelXbrl.error("SBR.NL.2.3.0.01",
                                _("Xlink 1.1 simple type is not allowed (xlink:type is missing)"),
                                modelObject=elt)
            # checks for elements in linkbases
            if elt.namespaceURI == XbrlConst.link:
                if elt.localName in ("schemaRef", "linkbaseRef", "roleRef", "arcroleRef"):
                    if xlinkType != "simple":
                        val.modelXbrl.error("xbrl.3.5.1.1:simpleLinkType",
                            _("Element %(element)s missing xlink:type=\"simple\""),
                            modelObject=elt, element=elt.qname)
                    href = elt.get("{http://www.w3.org/1999/xlink}href")
                    if not href or "xpointer(" in href:
                        val.modelXbrl.error("xbrl.3.5.1.2:simpleLinkHref",
                            _("Element %(element)s missing or invalid href"),
                            modelObject=elt, element=elt.qname)
                    for name in ("{http://www.w3.org/1999/xlink}role", "{http://www.w3.org/1999/xlink}arcrole"):
                        if elt.get(name) == "":
                            val.modelXbrl.error("xbrl.3.5.1.2:simpleLink" + name,
                                _("Element %(element)s has empty %(attribute)s"),
                                modelObject=elt, attribute=name,
                                messageCodes=("xbrl.3.5.1.2:simpleLink{http://www.w3.org/1999/xlink}role", "xbrl.3.5.1.2:simpleLink{http://www.w3.org/1999/xlink}arcrole"))
                    if elt.localName == "linkbaseRef" and \
                        elt.get("{http://www.w3.org/1999/xlink}arcrole") != XbrlConst.xlinkLinkbase:
                            val.modelXbrl.error("xbrl.4.3.3:linkbaseRefArcrole",
                                _("LinkbaseRef missing arcrole"),
                                modelObject=elt)
                elif elt.localName == "loc":
                    if xlinkType != "locator":
                        val.modelXbrl.error("xbrl.3.5.3.7.1:linkLocType",
                            _("Element %(element)s missing xlink:type=\"locator\""),
                            modelObject=elt, element=elt.qname)
                    for name, errName in (("{http://www.w3.org/1999/xlink}href","xbrl.3.5.3.7.2:linkLocHref"),
                                          ("{http://www.w3.org/1999/xlink}label","xbrl.3.5.3.7.3:linkLocLabel")):
                        if elt.get(name) is None:
                            val.modelXbrl.error(errName,
                                _("Element %(element)s missing: %(attribute)s"),
                                modelObject=elt, element=elt.qname, attribute=name,
                                messageCodes=("xbrl.3.5.3.7.2:linkLocHref","xbrl.3.5.3.7.3:linkLocLabel"))
                elif xlinkType == "resource":
                    if val.disclosureSystem.xmlLangIsInheritable:
                        if elt.localName == "footnote" and elt.xmlLang is None:
                            val.modelXbrl.error("xbrl.4.11.1.2.1:footnoteLang",
                                _("Footnote %(xlinkLabel)s element missing an in-scope xml:lang attribute"),
                                modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"))
                        elif elt.localName == "label" and elt.xmlLang is None:
                            val.modelXbrl.error("xbrl.5.2.2.2.1:labelLang",
                                _("Label %(xlinkLabel)s element missing an in-scope xml:lang attribute"),
                                modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"))
                    else:
                        if elt.localName == "footnote" and elt.get("{http://www.w3.org/XML/1998/namespace}lang") is None:
                            val.modelXbrl.error("xbrl.4.11.1.2.1:footnoteLang",
                                _("Footnote %(xlinkLabel)s element missing xml:lang attribute"),
                                modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"))
                        elif elt.localName == "label" and elt.get("{http://www.w3.org/XML/1998/namespace}lang") is None:
                            val.modelXbrl.error("xbrl.5.2.2.2.1:labelLang",
                                _("Label %(xlinkLabel)s element missing xml:lang attribute"),
                                modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"))
                    if val.validateSBRNL:
                        if elt.localName in ("label", "reference"):
                            if not XbrlConst.isStandardRole(xlinkRole):
                                val.modelXbrl.error("SBR.NL.2.3.10.13",
                                    _("Extended link %(element)s must have a standard xlink:role attribute (%(xlinkRole)s)"),
                                    modelObject=elt, element=elt.elementQname, xlinkRole=xlinkRole)
                        if elt.localName == "reference": # look for custom reference parts
                            for linkPart in elt.iterchildren():
                                if linkPart.namespaceURI not in val.disclosureSystem.baseTaxonomyNamespaces:
                                    val.modelXbrl.error("SBR.NL.2.2.5.01",
                                        _("Link part %(element)s is not authorized"),
                                        modelObject=linkPart, element=linkPart.elementQname)
                    # TBD: add lang attributes content validation
            if xlinkRole is not None:
                checkLinkRole(val, elt, elt.qname, xlinkRole, xlinkType, val.roleRefURIs)
            elif xlinkType == "extended" and val.validateSBRNL: # no @role on extended link
                val.modelXbrl.error("SBR.NL.2.3.10.13",
                    _("Extended link %(element)s must have an xlink:role attribute"),
                    modelObject=elt, element=elt.elementQname)
            if elt.get("{http://www.w3.org/1999/xlink}arcrole") is not None:
                checkArcrole(val, elt, elt.qname, elt.get("{http://www.w3.org/1999/xlink}arcrole"), val.arcroleRefURIs)

            #check resources
            if parentXlinkType == "extended":
                if elt.localName not in ("documentation", "title") and \
                    xlinkType not in ("arc", "locator", "resource"):
                    val.modelXbrl.error("xbrl.3.5.3.8.1:resourceType",
                        _("Element %(element)s appears to be a resource missing xlink:type=\"resource\""),
                        modelObject=elt, element=elt.qname)
                elif (xlinkType == "locator" and elt.namespaceURI != XbrlConst.link and
                      parent.namespaceURI == XbrlConst.link and parent.localName in link_loc_spec_sections):
                    val.modelXbrl.error("xbrl.{0}:customLocator".format(link_loc_spec_sections[parent.localName]),
                        _("Element %(element)s is a custom locator in a standard %(link)s"),
                        modelObject=(elt,parent), element=elt.qname, link=parent.qname,
                        messageCodes=("xbrl.5.2.2.1:customLocator", "xbrl.5.2.3.1:customLocator", "xbrl.5.2.5.1:customLocator", "xbrl.5.2.6.1:customLocator", "xbrl.5.2.4.1:customLocator", "xbrl.4.11.1.1:customLocator"))

            if xlinkType == "resource":
                if not elt.get("{http://www.w3.org/1999/xlink}label"):
                    val.modelXbrl.error("xbrl.3.5.3.8.2:resourceLabel",
                        _("Element %(element)s missing xlink:label"),
                        modelObject=elt, element=elt.qname)
            elif xlinkType == "arc":
                for name, errName in (("{http://www.w3.org/1999/xlink}from", "xbrl.3.5.3.9.2:arcFrom"),
                                      ("{http://www.w3.org/1999/xlink}to", "xbrl.3.5.3.9.2:arcTo")):
                    if not elt.get(name):
                        val.modelXbrl.error(errName,
                            _("Element %(element)s missing xlink:%(attribute)s"),
                            modelObject=elt, element=elt.qname, attribute=name,
                            messageCodes=("xbrl.3.5.3.9.2:arcFrom", "xbrl.3.5.3.9.2:arcTo"))
                if val.modelXbrl.hasXDT and elt.get("{http://xbrl.org/2005/xbrldt}targetRole") is not None:
                    targetRole = elt.get("{http://xbrl.org/2005/xbrldt}targetRole")
                    if not XbrlConst.isStandardRole(targetRole) and \
                       elt.qname == XbrlConst.qnLinkDefinitionArc and \
                       targetRole not in val.roleRefURIs:
                        val.modelXbrl.error("xbrldte:TargetRoleNotResolvedError",
                            _("TargetRole %(targetRole)s is missing a roleRef"),
                            modelObject=elt, element=elt.qname, targetRole=targetRole)
                val.containsRelationship = True
            xmlLang = elt.get("{http://www.w3.org/XML/1998/namespace}lang")
            if val.validateXmlLang and xmlLang is not None:
                if not val.disclosureSystem.xmlLangPattern.match(xmlLang):
                    val.modelXbrl.error("SBR.NL.2.3.8.01" if (val.validateSBRNL and xmlLang.startswith('nl')) else "SBR.NL.2.3.8.02" if (val.validateSBRNL and xmlLang.startswith('en')) else "arelle:langError",
                        _("Element %(element)s %(xlinkLabel)s has unauthorized xml:lang='%(lang)s'"),
                        modelObject=elt, element=elt.qname,
                        xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"),
                        lang=elt.get("{http://www.w3.org/XML/1998/namespace}lang"),
                        messageCodes=("SBR.NL.2.3.8.01", "SBR.NL.2.3.8.02", "arelle:langError"))

            if isInstance:
                if elt.namespaceURI == XbrlConst.xbrli:
                    expectedSequence = instanceSequence.get(elt.localName,9)
                else:
                    expectedSequence = 9    #itdms last
                if instanceOrder > expectedSequence:
                    val.modelXbrl.error("xbrl.4.7:instanceElementOrder",
                        _("Element %(element)s is out of order"),
                        modelObject=elt, element=elt.qname)
                else:
                    instanceOrder = expectedSequence

            if modelDocument.type == ModelDocument.Type.UnknownXML:
                if elt.localName == "xbrl" and elt.namespaceURI == XbrlConst.xbrli:
                    if elt.getparent() is not None:
                        val.modelXbrl.error("xbrl.4:xbrlRootElement",
                            "Xbrl must be a root element, and may not be nested in %(parent)s",
                            parent=elt.parentQname,
                            modelObject=elt)
                elif elt.localName == "schema" and elt.namespaceURI == XbrlConst.xsd:
                    if elt.getparent() is not None:
                        val.modelXbrl.error("xbrl.5.1:schemaRootElement",
                            "Schema must be a root element, and may not be nested in %(parent)s",
                            parent=elt.parentQname,
                            modelObject=elt)

            if modelDocument.type == ModelDocument.Type.INLINEXBRL and elt.namespaceURI in XbrlConst.ixbrlAll:
                if elt.localName == "footnote":
                    if val.validateGFM:
                        if elt.get("{http://www.w3.org/1999/xlink}arcrole") != XbrlConst.factFootnote:
                            # must be in a nonDisplay div
                            if not any(inlineDisplayNonePattern.search(e.get("style") or "")
                                       for ns in (XbrlConst.xhtml, None)  # may be un-namespaced html
                                       for e in XmlUtil.ancestors(elt, ns, "div")):
                                val.modelXbrl.error(("EFM.N/A", "GFM:1.10.16"),
                                    _("Inline XBRL footnote %(footnoteID)s must be in non-displayable div due to arcrole %(arcrole)s"),
                                    modelObject=elt, footnoteID=elt.get("footnoteID"),
                                    arcrole=elt.get("{http://www.w3.org/1999/xlink}arcrole"))

                        if not elt.get("{http://www.w3.org/XML/1998/namespace}lang"):
                            val.modelXbrl.error(("EFM.N/A", "GFM:1.10.13"),
                                _("Inline XBRL footnote %(footnoteID)s is missing an xml:lang attribute"),
                                modelObject=elt, footnoteID=id)
                    if elt.namespaceURI == XbrlConst.ixbrl:
                        val.ixdsFootnotes[elt.footnoteID] = elt
                    else:
                        checkIxContinuationChain(val, elt)
                    if not elt.xmlLang:
                        val.modelXbrl.error(ixMsgCode("footnoteLang", elt, sect="validation"),
                            _("Inline XBRL footnotes require an in-scope xml:lang"),
                            modelObject=elt)
                elif elt.localName == "fraction":
                    ixDescendants = XmlUtil.descendants(elt, elt.namespaceURI, '*')
                    wrongDescendants = [d
                                        for d in ixDescendants
                                        if d.localName not in ('numerator','denominator','fraction')]
                    if wrongDescendants:
                        val.modelXbrl.error(ixMsgCode("fractionDescendants", elt, sect="validation"),
                            _("Inline XBRL fraction may only contain ix:numerator, ix:denominator, or ix:fraction, but contained %(wrongDescendants)s"),
                            modelObject=[elt] + wrongDescendants, wrongDescendants=", ".join(str(d.elementQname) for d in wrongDescendants))
                    ixDescendants = XmlUtil.descendants(elt, elt.namespaceURI, ('numerator','denominator'))
                    if not elt.isNil:
                        if set(d.localName for d in ixDescendants) != {'numerator','denominator'}:
                            val.modelXbrl.error(ixMsgCode("fractionTerms", elt, sect="validation"),
                                _("Inline XBRL fraction must have one ix:numerator and one ix:denominator when not nil"),
                                modelObject=[elt] + ixDescendants)
                    else:
                        if ixDescendants: # nil and has fraction term elements
                            val.modelXbrl.error(ixMsgCode("fractionNilTerms", elt, sect="validation"),
                                _("Inline XBRL fraction must not have ix:numerator or ix:denominator when nil"),
                                modelObject=[elt] + ixDescendants)
                        e2 = XmlUtil.ancestor(elt, elt.namespaceURI, "fraction")
                        if e2 is not None:
                            val.modelXbrl.error(ixMsgCode("nestedFractionIsNil", elt, sect="validation"),
                                _("Inline XBRL nil ix:fraction may not have an ancestor ix:fraction"),
                                modelObject=(elt,e2))
                elif elt.localName in ("denominator", "numerator"):
                    wrongDescendants = [d for d in XmlUtil.descendants(elt, '*', '*')]
                    if wrongDescendants:
                        val.modelXbrl.error(ixMsgCode("fractionTermDescendants", elt, sect="validation"),
                            _("Inline XBRL fraction term ix:%(name)s may only contain text nodes, but contained %(wrongDescendants)s"),
                            modelObject=[elt] + wrongDescendants, name=elt.localName, wrongDescendants=", ".join(str(d.elementQname) for d in wrongDescendants))
                    if elt.get("format") is None and '-' in XmlUtil.innerText(elt):
                        val.modelXbrl.error(ixMsgCode("fractionTermNegative", elt, sect="validation"),
                            _("Inline XBRL ix:numerator or ix:denominator without format attribute must be non-negative"),
                            modelObject=elt)
                elif elt.localName == "header":
                    if not any(inlineDisplayNonePattern.search(e.get("style") or "")
                               for ns in (XbrlConst.xhtml, None)  # may be un-namespaced html
                               for e in XmlUtil.ancestors(elt, ns, "div")):
                        val.modelXbrl.warning(ixMsgCode("headerDisplayNone", elt, sect="non-validatable"),
                            _("Warning, Inline XBRL ix:header is recommended to be nested in a <div> with style display:none"),
                            modelObject=elt)
                    val.ixdsHeaderCount += 1
                elif elt.localName == "nonFraction":
                    if elt.isNil:
                        e2 = XmlUtil.ancestor(elt, elt.namespaceURI, "nonFraction")
                        if e2 is not None:
                            val.modelXbrl.error(ixMsgCode("nestedNonFractionIsNil", elt, sect="validation"),
                                _("Inline XBRL nil ix:nonFraction may not have an ancestor ix:nonFraction"),
                                modelObject=(elt,e2))
                    else:
                        c = XmlUtil.children(elt, '*', '*')
                        if c and (len(c) != 1 or c[0].namespaceURI != elt.namespaceURI or c[0].localName != "nonFraction"):
                            val.modelXbrl.error(ixMsgCode("nonFractionChildren", elt, sect="validation"),
                                _("Inline XBRL nil ix:nonFraction may only have one child ix:nonFraction"),
                                modelObject=[elt] + c)
                        for e in c:
                            if (e.namespaceURI == elt.namespaceURI and e.localName == "nonFraction" and
                                (e.format != elt.format or e.scaleInt != elt.scaleInt or e.unitID != elt.unitID)):
                                val.modelXbrl.error(ixMsgCode("nestedNonFractionProperties", e, sect="validation"),
                                    _("Inline XBRL nested ix:nonFraction must have matching format, scale, and unitRef properties"),
                                    modelObject=(elt, e))
                    if elt.get("format") is None and '-' in XmlUtil.innerText(elt):
                        val.modelXbrl.error(ixMsgCode("nonFractionNegative", elt, sect="validation"),
                            _("Inline XBRL ix:nonFraction without format attribute must be non-negative"),
                            modelObject=elt)
                elif elt.localName == "nonNumeric":
                    checkIxContinuationChain(val, elt)
                elif elt.localName == "references":
                    val.ixdsReferences[elt.get("target")].append(elt)
                elif elt.localName == "relationship":
                    val.ixdsRelationships.append(elt)
                elif elt.localName == "tuple":
                    if not elt.tupleID:
                        if not elt.isNil:
                            if not XmlUtil.descendants(elt, elt.namespaceURI, ("fraction", "nonFraction", "nonNumeric",  "tuple")):
                                val.modelXbrl.error(ixMsgCode("tupleID", elt, sect="validation"),
                                    _("Inline XBRL non-nil tuples without ix:fraction, ix:nonFraction, ix:nonNumeric or ix:tuple descendants require a tupleID"),
                                    modelObject=elt)
                    else:
                        val.ixdsTuples[elt.tupleID] = elt
            if val.validateEFMorGFMorSBRNL:
                if xlinkType == "extended":
                    if not xlinkRole or xlinkRole == "":
                        val.modelXbrl.error(("EFM.6.09.04", "GFM.1.04.04"),
                            "%(element)s is missing an xlink:role",
                            modelObject=elt, element=elt.qname)
                    eltNsName = (elt.namespaceURI,elt.localName)
                    if not val.extendedElementName:
                        val.extendedElementName = elt.qname
                    elif val.extendedElementName != elt.qname:
                        val.modelXbrl.error(("EFM.6.09.07", "GFM:1.04.07", "SBR.NL.2.3.0.11"),
                            _("Extended element %(element)s must be the same as %(element2)s"),
                            modelObject=elt, element=elt.qname, element2=val.extendedElementName)
                if xlinkType == "locator":
                    if val.validateSBRNL and elt.qname != XbrlConst.qnLinkLoc:
                        val.modelXbrl.error("SBR.NL.2.3.0.11",
                            _("Loc element %(element)s may not be contained in a linkbase with %(element2)s"),
                            modelObject=elt, element=elt.qname, element2=val.extendedElementName)
                if xlinkType == "resource":
                    if not xlinkRole:
                        val.modelXbrl.error(("EFM.6.09.04", "GFM.1.04.04"),
                            _("%(element)s is missing an xlink:role"),
                            modelObject=elt, element=elt.qname)
                    elif not XbrlConst.isStandardRole(xlinkRole):
                        modelsRole = val.modelXbrl.roleTypes.get(xlinkRole)
                        if (modelsRole is None or len(modelsRole) == 0 or
                            modelsRole[0].modelDocument.targetNamespace not in val.disclosureSystem.standardTaxonomiesDict):
                            val.modelXbrl.error(("EFM.6.09.05", "GFM.1.04.05", "SBR.NL.2.3.10.14"),
                                _("Resource %(xlinkLabel)s role %(role)s is not a standard taxonomy role"),
                                modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"), role=xlinkRole, element=elt.qname,
                                roleDefinition=val.modelXbrl.roleTypeDefinition(xlinkRole))
                    if val.validateSBRNL:
                        if elt.localName == "reference":
                            for child in elt.iterdescendants():
                                if isinstance(child,ModelObject) and child.namespaceURI.startswith("http://www.xbrl.org") and child.namespaceURI != "http://www.xbrl.org/2006/ref":
                                    val.modelXbrl.error("SBR.NL.2.3.3.01",
                                        _("Reference %(xlinkLabel)s has unauthorized part element %(element)s"),
                                        modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"),
                                        element=qname(child))
                            id = elt.get("id")
                            if not id:
                                val.modelXbrl.error("SBR.NL.2.3.3.02",
                                    _("Reference %(xlinkLabel)s is missing an id attribute"),
                                    modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"))
                            elif id in val.DTSreferenceResourceIDs:
                                val.modelXbrl.error("SBR.NL.2.3.3.03",
                                    _("Reference %(xlinkLabel)s has duplicated id %(id)s also in linkbase %(otherLinkbase)s"),
                                    modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"),
                                    id=id, otherLinkbase=val.DTSreferenceResourceIDs[id])
                            else:
                                val.DTSreferenceResourceIDs[id] = modelDocument.basename
                        if elt.qname not in {
                            XbrlConst.qnLinkLabelLink: (XbrlConst.qnLinkLabel,),
                            XbrlConst.qnLinkReferenceLink: (XbrlConst.qnLinkReference,),
                            XbrlConst.qnLinkPresentationLink: tuple(),
                            XbrlConst.qnLinkCalculationLink: tuple(),
                            XbrlConst.qnLinkDefinitionLink: tuple(),
                            XbrlConst.qnLinkFootnoteLink: (XbrlConst.qnLinkFootnote,),
                            # XbrlConst.qnGenLink: (XbrlConst.qnGenLabel, XbrlConst.qnGenReference, val.qnSbrLinkroleorder),
                             }.get(val.extendedElementName,(elt.qname,)):  # allow non-2.1 to be ok regardless per RH 2013-03-13
                            val.modelXbrl.error("SBR.NL.2.3.0.11",
                                _("Resource element %(element)s may not be contained in a linkbase with %(element2)s"),
                                modelObject=elt, element=elt.qname, element2=val.extendedElementName)
                if xlinkType == "arc":
                    if elt.get("priority") is not None:
                        priority = elt.get("priority")
                        try:
                            if int(priority) >= 10:
                                val.modelXbrl.error(("EFM.6.09.09", "GFM.1.04.08"),
                                    _("Arc from %(xlinkFrom)s to %(xlinkTo)s priority %(priority)s must be less than 10"),
                                    modelObject=elt,
                                    arcElement=elt.qname,
                                    xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                    xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                                    priority=priority)
                        except (ValueError) :
                            val.modelXbrl.error(("EFM.6.09.09", "GFM.1.04.08"),
                                _("Arc from %(xlinkFrom)s to %(xlinkTo)s priority %(priority)s is not an integer"),
                                modelObject=elt,
                                arcElement=elt.qname,
                                xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                                priority=priority)
                    if elt.namespaceURI == XbrlConst.link:
                        if elt.localName == "presentationArc" and not elt.get("order"):
                            val.modelXbrl.error(("EFM.6.12.01", "GFM.1.06.01", "SBR.NL.2.3.4.04"),
                                _("PresentationArc from %(xlinkFrom)s to %(xlinkTo)s must have an order"),
                                modelObject=elt,
                                xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                                conceptFrom=arcFromConceptQname(elt),
                                conceptTo=arcToConceptQname(elt))
                        elif elt.localName == "calculationArc":
                            if not elt.get("order"):
                                val.modelXbrl.error(("EFM.6.14.01", "GFM.1.07.01"),
                                    _("CalculationArc from %(xlinkFrom)s to %(xlinkTo)s must have an order"),
                                    modelObject=elt,
                                    xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                    xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                                    conceptFrom=arcFromConceptQname(elt),
                                    conceptTo=arcToConceptQname(elt))
                            try:
                                weightAttr = elt.get("weight")
                                weight = float(weightAttr)
                                if not weight in (1, -1):
                                    val.modelXbrl.error(("EFM.6.14.02", "GFM.1.07.02"),
                                        _("CalculationArc from %(xlinkFrom)s to %(xlinkTo)s weight %(weight)s must be 1 or -1"),
                                        modelObject=elt,
                                        xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                        xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                                        conceptFrom=arcFromConceptQname(elt),
                                        conceptTo=arcToConceptQname(elt),
                                        weight=weightAttr)
                            except ValueError:
                                val.modelXbrl.error(("EFM.6.14.02", "GFM.1.07.02"),
                                    _("CalculationArc from %(xlinkFrom)s to %(xlinkTo)s must have an weight (value error in \"%(weight)s\")"),
                                    modelObject=elt,
                                    xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                    xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                                    conceptFrom=arcFromConceptQname(elt),
                                    conceptTo=arcToConceptQname(elt),
                                    weight=weightAttr)
                        elif elt.localName == "definitionArc":
                            if not elt.get("order"):
                                val.modelXbrl.error(("EFM.6.16.01", "GFM.1.08.01"),
                                    _("DefinitionArc from %(xlinkFrom)s to %(xlinkTo)s must have an order"),
                                    modelObject=elt,
                                    xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                    xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                                    conceptFrom=arcFromConceptQname(elt),
                                    conceptTo=arcToConceptQname(elt))
                            if val.validateSBRNL and arcrole in (XbrlConst.essenceAlias, XbrlConst.similarTuples, XbrlConst.requiresElement):
                                val.modelXbrl.error({XbrlConst.essenceAlias: "SBR.NL.2.3.2.02",
                                                  XbrlConst.similarTuples: "SBR.NL.2.3.2.03",
                                                  XbrlConst.requiresElement: "SBR.NL.2.3.2.04"}[arcrole],
                                    _("DefinitionArc from %(xlinkFrom)s to %(xlinkTo)s has unauthorized arcrole %(arcrole)s"),
                                    modelObject=elt,
                                    xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                    xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                                    arcrole=arcrole,
                                    messageCodes=("SBR.NL.2.3.2.02", "SBR.NL.2.3.2.03", "SBR.NL.2.3.2.04")),
                        elif elt.localName == "referenceArc" and val.validateSBRNL:
                            if elt.get("order"):
                                val.modelXbrl.error("SBR.NL.2.3.3.05",
                                    _("ReferenceArc from %(xlinkFrom)s to %(xlinkTo)s has an order"),
                                    modelObject=elt,
                                    xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                    xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"))
                        if val.validateSBRNL and elt.get("use") == "prohibited" and elt.getparent().tag in (
                                "{http://www.xbrl.org/2003/linkbase}presentationLink",
                                "{http://www.xbrl.org/2003/linkbase}labelLink",
                                "{http://xbrl.org/2008/generic}link",
                                "{http://www.xbrl.org/2003/linkbase}referenceLink"):
                            val.modelXbrl.error("SBR.NL.2.3.0.10",
                                _("%(arc)s must not contain use='prohibited'"),
                                modelObject=elt, arc=elt.getparent().qname)
                    if val.validateSBRNL and elt.qname not in {
                        XbrlConst.qnLinkLabelLink: (XbrlConst.qnLinkLabelArc,),
                        XbrlConst.qnLinkReferenceLink: (XbrlConst.qnLinkReferenceArc,),
                        XbrlConst.qnLinkPresentationLink: (XbrlConst.qnLinkPresentationArc,),
                        XbrlConst.qnLinkCalculationLink: (XbrlConst.qnLinkCalculationArc,),
                        XbrlConst.qnLinkDefinitionLink: (XbrlConst.qnLinkDefinitionArc,),
                        XbrlConst.qnLinkFootnoteLink: (XbrlConst.qnLinkFootnoteArc,),
                        # XbrlConst.qnGenLink: (XbrlConst.qnGenArc,),
                         }.get(val.extendedElementName, (elt.qname,)):  # allow non-2.1 to be ok regardless per RH 2013-03-13
                        val.modelXbrl.error("SBR.NL.2.3.0.11",
                            _("Arc element %(element)s may not be contained in a linkbase with %(element2)s"),
                            modelObject=elt, element=elt.qname, element2=val.extendedElementName)
                    if val.validateSBRNL and elt.qname == XbrlConst.qnLinkLabelArc and elt.get("order"):
                        val.modelXbrl.error("SBR.NL.2.3.8.08",
                            _("labelArc may not be contain order (%(order)s)"),
                            modelObject=elt, order=elt.get("order"))
                if val.validateSBRNL:
                    # check attributes for prefixes and xmlns
                    val.valUsedPrefixes.add(elt.prefix)
                    if elt.namespaceURI not in val.disclosureSystem.baseTaxonomyNamespaces:
                        val.modelXbrl.error("SBR.NL.2.2.0.20",
                            _("%(fileType)s element %(element)s must not have custom namespace %(namespace)s"),
                            modelObject=elt, element=elt.qname,
                            fileType="schema" if isSchema else "linkbase" ,
                            namespace=elt.namespaceURI)
                    for attrTag, attrValue in elt.items():
                        prefix, ns, localName = XmlUtil.clarkNotationToPrefixNsLocalname(elt, attrTag, isAttribute=True)
                        if prefix: # don't count unqualified prefixes for using default namespace
                            val.valUsedPrefixes.add(prefix)
                        if ns and ns not in val.disclosureSystem.baseTaxonomyNamespaces:
                            val.modelXbrl.error("SBR.NL.2.2.0.20",
                                _("%(fileType)s element %(element)s must not have %(prefix)s:%(localName)s"),
                                modelObject=elt, element=elt.qname,
                                fileType="schema" if isSchema else "linkbase" ,
                                prefix=prefix, localName=localName)
                        if isSchema and localName in ("base", "ref", "substitutionGroup", "type"):
                            valuePrefix, sep, valueName = attrValue.partition(":")
                            if sep:
                                val.valUsedPrefixes.add(valuePrefix)
                    # check for xmlns on a non-root element
                    parentElt = elt.getparent()
                    if parentElt is not None:
                        for prefix, ns in elt.nsmap.items():
                            if prefix not in parentElt.nsmap or parentElt.nsmap[prefix] != ns:
                                val.modelXbrl.error(("SBR.NL.2.2.0.19" if isSchema else "SBR.NL.2.3.1.01"),
                                    _("%(fileType)s element %(element)s must not have xmlns:%(prefix)s"),
                                    modelObject=elt, element=elt.qname,
                                    fileType="schema" if isSchema else "linkbase" ,
                                    prefix=prefix,
                                    messageCodes=("SBR.NL.2.2.0.19", "SBR.NL.2.3.1.01"))

                    if elt.localName == "roleType" and not elt.get("id"):
                        val.modelXbrl.error("SBR.NL.2.3.10.11",
                            _("RoleType %(roleURI)s missing id attribute"),
                            modelObject=elt, roleURI=elt.get("roleURI"))
                    elif elt.localName == "loc" and elt.get("{http://www.w3.org/1999/xlink}role"):
                        val.modelXbrl.error("SBR.NL.2.3.10.08",
                            _("Loc %(xlinkLabel)s has unauthorized role attribute"),
                            modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"))
                    elif elt.localName == "documentation":
                        val.modelXbrl.error("SBR.NL.2.3.10.12" if elt.namespaceURI == XbrlConst.link else "SBR.NL.2.2.11.02",
                            _("Documentation element must not be used: %(value)s"),
                            modelObject=elt, value=XmlUtil.text(elt),
                            messageCodes=("SBR.NL.2.3.10.12", "SBR.NL.2.2.11.02"))
                    if elt.localName == "linkbase":
                        schemaLocation = elt.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
                        if schemaLocation:
                            schemaLocations = schemaLocation.split()
                            for sl in (XbrlConst.link, XbrlConst.xlink):
                                if sl in schemaLocations:
                                    val.modelXbrl.error("SBR.NL.2.3.0.07",
                                        _("Linkbase element must not have schemaLocation entry for %(schemaLocation)s"),
                                        modelObject=elt, schemaLocation=sl)
                        for attrName, errCode in (("id", "SBR.NL.2.3.10.04"),
                                                  ("{http://www.w3.org/2001/XMLSchema-instance}nil", "SBR.NL.2.3.10.05"),
                                                  ("{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation", "SBR.NL.2.3.10.06"),
                                                  ("{http://www.w3.org/2001/XMLSchema-instance}type", "SBR.NL.2.3.10.07")):
                            if elt.get(attrName) is not None:
                                val.modelXbrl.error(errCode,
                                    _("Linkbase element %(element)s must not have attribute %(attribute)s"),
                                    modelObject=elt, element=elt.qname, attribute=attrName,
                                    messageCodes=("SBR.NL.2.3.10.04", "SBR.NL.2.3.10.05", "SBR.NL.2.3.10.06", "SBR.NL.2.3.10.07"))
                    for attrName, errCode in (("{http://www.w3.org/1999/xlink}actuate", "SBR.NL.2.3.10.01"),
                                              ("{http://www.w3.org/1999/xlink}show", "SBR.NL.2.3.10.02"),
                                              ("{http://www.w3.org/1999/xlink}title", "SBR.NL.2.3.10.03")):
                        if elt.get(attrName) is not None:
                            val.modelXbrl.error(errCode,
                                _("Linkbase element %(element)s must not have attribute xlink:%(attribute)s"),
                                modelObject=elt, element=elt.qname, attribute=attrName,
                                messageCodes=("SBR.NL.2.3.10.01", "SBR.NL.2.3.10.02", "SBR.NL.2.3.10.03"))

            checkElements(val, modelDocument, elt)
        elif isinstance(elt,ModelComment): # comment node
            if val.validateSBRNL:
                if elt.itersiblings(preceding=True):
                    val.modelXbrl.error("SBR.NL.2.2.0.05" if isSchema else "SBR.NL.2.3.0.05",
                            _('%(fileType)s must have only one comment node before schema element: "%(value)s"'),
                            modelObject=elt, fileType=modelDocument.gettype().title(), value=elt.text,
                            messageCodes=("SBR.NL.2.2.0.05", "SBR.NL.2.3.0.05"))

def checkLinkRole(val, elt, linkEltQname, xlinkRole, xlinkType, roleRefURIs) -> None:
    if xlinkRole == "" and xlinkType == "simple":
        val.modelXbrl.error("xbrl.3.5.1.3:emptySimpleLinkRole",
            _("Simple link role %(xlinkRole)s is empty"),
            modelObject=elt, xlinkRole=xlinkRole)
    elif xlinkRole == "" and xlinkType == "extended" and \
         XbrlConst.isStandardResourceOrExtLinkElement(elt):
        val.modelXbrl.error("xbrl.3.5.3.3:emptyStdExtLinkRole",
            _("Standard extended link role %(xlinkRole)s is empty"),
            modelObject=elt, xlinkRole=xlinkRole)
    elif not UrlUtil.isAbsolute(xlinkRole):
        if XbrlConst.isStandardResourceOrExtLinkElement(elt):
            val.modelXbrl.error("xbrl.3.5.2.4:roleNotAbsolute",
                _("Role %(xlinkRole)s is not absolute"),
                modelObject=elt, xlinkRole=xlinkRole)
        elif val.isGenericLink(elt):
            val.modelXbrl.error("xbrlgene:nonAbsoluteLinkRoleURI",
                _("Generic link role %(xlinkRole)s is not absolute"),
                modelObject=elt, xlinkRole=xlinkRole)
        elif val.isGenericResource(elt):
            val.modelXbrl.error("xbrlgene:nonAbsoluteResourceRoleURI",
                _("Generic resource role %(xlinkRole)s is not absolute"),
                modelObject=elt, xlinkRole=xlinkRole)
    elif XbrlConst.isStandardRole(xlinkRole):
        if linkEltQname.namespaceURI == XbrlConst.link:
            errCode, definedRoles = standard_roles_definitions.get(elt.qname, standard_roles_other)
            if xlinkRole not in definedRoles:
                val.modelXbrl.error(errCode,
                    _("Standard role %(xlinkRole)s is not defined for %(element)s"),
                    modelObject=elt, xlinkRole=xlinkRole, element=linkEltQname,
                    messageCodes=("xbrl.5.2.2.2.2", "xbrl.5.2.3.2.1", "xbrl.4.11.1.2", "xbrl.4.3.4", "xbrl.3.5.3.7"))
    else:  # custom role
        if xlinkRole not in roleRefURIs:
            if XbrlConst.isStandardResourceOrExtLinkElement(elt):
                val.modelXbrl.error("xbrl.3.5.2.4:missingRoleRef",
                    _("Role %(xlinkRole)s is missing a roleRef"),
                    modelObject=elt, xlinkRole=xlinkRole)
            elif val.isGenericLink(elt):
                val.modelXbrl.error("xbrlgene:missingRoleRefForLinkRole",
                    _("Generic link role %(xlinkRole)s is missing a roleRef"),
                    modelObject=elt, xlinkRole=xlinkRole)
            elif val.isGenericResource(elt):
                val.modelXbrl.error("xbrlgene:missingRoleRefForResourceRole",
                    _("Generic resource role %(xlinkRole)s is missing a roleRef"),
                    modelObject=elt, xlinkRole=xlinkRole)
        modelsRole = val.modelXbrl.roleTypes.get(xlinkRole)
        if modelsRole is None or len(modelsRole) == 0 or linkEltQname not in modelsRole[0].usedOns:
            if XbrlConst.isStandardResourceOrExtLinkElement(elt):
                val.modelXbrl.error("xbrl.5.1.3.4:custRoleUsedOn",
                    _("Role %(xlinkRole)s missing usedOn for %(element)s"),
                    modelObject=elt, xlinkRole=xlinkRole, element=linkEltQname)
            elif val.isGenericLink(elt):
                val.modelXbrl.error("xbrlgene:missingLinkRoleUsedOnValue",
                    _("Generic link role %(xlinkRole)s missing usedOn for {2}"),
                    modelObject=elt, xlinkRole=xlinkRole, element=linkEltQname)
            elif val.isGenericResource(elt):
                val.modelXbrl.error("xbrlgene:missingResourceRoleUsedOnValue",
                    _("Generic resource role %(xlinkRole)s missing usedOn for %(element)s"),
                    modelObject=elt, xlinkRole=xlinkRole, element=linkEltQname)
    if xlinkRole in XbrlConst.lrrUnapprovedRoles:
        val.modelXbrl.warning("lrr:unApprovedRole",
            _("LRR resource role %(xlinkRole)s on %(element)s has status %(status)s"),
            modelObject=elt, xlinkRole=xlinkRole, element=linkEltQname, status=XbrlConst.lrrUnapprovedRoles[xlinkRole])

def checkArcrole(val, elt, arcEltQname, arcrole, arcroleRefURIs) -> None:
    if arcrole == "" and \
        elt.get("{http://www.w3.org/1999/xlink}type") == "simple":
        val.modelXbrl.error("xbrl.3.5.1.4:emptyXlinkArcrole",
            _("Arcrole on %(element)s is empty"),
            modelObject=elt, element=arcEltQname)
    elif not UrlUtil.isAbsolute(arcrole):
        if XbrlConst.isStandardArcInExtLinkElement(elt):
            val.modelXbrl.error("xbrl.3.5.2.5:arcroleNotAbsolute",
                _("Arcrole %(arcrole)s is not absolute"),
                modelObject=elt, element=arcEltQname, arcrole=arcrole)
        elif val.isGenericArc(elt):
            val.modelXbrl.error("xbrlgene:nonAbsoluteArcRoleURI",
                _("Generic arc arcrole %(arcrole)s is not absolute"),
                modelObject=elt, element=arcEltQname, arcrole=arcrole)
    elif not XbrlConst.isStandardArcrole(arcrole):
        if arcrole not in arcroleRefURIs:
            if XbrlConst.isStandardArcInExtLinkElement(elt):
                val.modelXbrl.error("xbrl.3.5.2.5:missingArcroleRef",
                    _("Arcrole %(arcrole)s is missing an arcroleRef"),
                    modelObject=elt, element=arcEltQname, arcrole=arcrole)
            elif val.isGenericArc(elt):
                val.modelXbrl.error("xbrlgene:missingRoleRefForArcRole",
                    _("Generic arc arcrole %(arcrole)s is missing an arcroleRef"),
                    modelObject=elt, element=arcEltQname, arcrole=arcrole)
        modelsRole = val.modelXbrl.arcroleTypes.get(arcrole)
        if modelsRole is None or len(modelsRole) == 0 or arcEltQname not in modelsRole[0].usedOns:
            if XbrlConst.isStandardArcInExtLinkElement(elt):
                val.modelXbrl.error("xbrl.5.1.4.5:custArcroleUsedOn",
                    _("Arcrole %(arcrole)s missing usedOn for %(element)s"),
                    modelObject=elt, element=arcEltQname, arcrole=arcrole)
            elif val.isGenericArc(elt):
                val.modelXbrl.error("xbrlgene:missingArcRoleUsedOnValue",
                    _("Generic arc arcrole %(arcrole)s missing usedOn for %(element)s"),
                    modelObject=elt, element=arcEltQname, arcrole=arcrole)
    elif XbrlConst.isStandardArcElement(elt):
        if XbrlConst.standardArcroleArcElement(arcrole) != arcEltQname.localName:
            val.modelXbrl.error("xbrl.5.1.4.5:custArcroleUsedOn",
                _("Standard arcrole %(arcrole)s used on wrong arc %(element)s"),
                modelObject=elt, element=arcEltQname, arcrole=arcrole)
    if arcrole in XbrlConst.lrrUnapprovedArcroles:
        val.modelXbrl.warning("lrr:unApprovedArcrole",
            _("LRR arcrole %(arcrole)s on %(element)s has status %(status)s"),
            modelObject=elt, arcrole=arcrole, element=arcEltQname, status=XbrlConst.lrrUnapprovedArcroles[arcrole])


def checkIxContinuationChain(val, elt, chain=None):
    if chain is None:
        chain = [elt]
    else:
        for otherElt in chain:
            if XmlUtil.isDescendantOf(elt, otherElt) or XmlUtil.isDescendantOf(otherElt, elt):
                val.modelXbrl.error("ix:continuationDescendancy",
                                _("Inline XBRL continuation chain has elements which are descendants of each other."),
                                modelObject=(elt, otherElt))
            else:
                contAt = elt.get("_continuationElement")
                if contAt is not None:
                    chain.append(elt)
                checkIxContinuationChain(val, contAt, chain)
