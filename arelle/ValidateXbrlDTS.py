'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import (ModelDocument, ModelDtsObject, HtmlUtil, UrlUtil, XmlUtil, XbrlUtil, XbrlConst,
                    XmlValidate)
from arelle.arelle_c import ModelObject, ModelComment, ModelXlinkObject, ModelXlinkLocator, ModelXlinkSimple, ModelXlinkExtended, ModelXlinkArc, ModelFact, ModelConcept, QName
from arelle.ModelRelationshipSet import baseSetRelationship
from arelle.ModelValue import qname
from arelle.PluginManager import pluginClassMethods
from arelle.XhtmlValidate import ixMsgCode
from lxml import etree
from collections import defaultdict
try:
    import regex as re
except ImportError:
    import re

instanceSequence = {"schemaRef":1, "linkbaseRef":2, "roleRef":3, "arcroleRef":4}
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
        return arcElement.fromLabel
    else:
        return modelRelationship.fromModelObject.qname

def arcToConceptQname(arcElement):
    modelRelationship = baseSetRelationship(arcElement)
    if modelRelationship is None:
        return arcElement.toLabel
    else:
        return modelRelationship.toModelObject.qname

def checkDTS(val, modelDocument, checkedModelDocuments):
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
    if modelDocument.type == ModelDocument.Type.INLINEXBRL:
        if not val.validateIXDS: # set up IXDS validation
            val.validateIXDS = True
            val.ixdsDocs = []
            val.ixdsFootnotes = {}
            val.ixdsHeaderCount = 0
            val.ixdsTuples = {}
            val.ixdsReferences = defaultdict(list)
            val.ixdsRelationships = []
            val.ixdsRoleRefURIs = val.modelXbrl.targetRoleRefs  # roleRefs defined for all targets
            val.ixdsArcroleRefURIs = val.modelXbrl.targetArcroleRefs  # arcroleRefs defined for all targets
        # accumulate all role/arcrole refs across target document instance files
        val.roleRefURIs = val.ixdsRoleRefURIs
        val.arcroleRefURIs = val.ixdsArcroleRefURIs
        val.ixdsDocs.append(modelDocument)
        
    if modelDocument.type == ModelDocument.Type.SCHEMA: 
        if modelDocument.targetNamespace is not None:
            if modelDocument.targetNamespace == "":
                val.modelXbrl.error("xbrl.5.1:emptyTargetNamespace",
                    "Schema element has an empty targetNamespace",
                    modelObject=modelDocument)
            if val.validateEFM and len(modelDocument.targetNamespace) > 85:
                l = len(modelDocument.targetNamespace.encode("utf-8"))
                if l > 255:
                    val.modelXbrl.error("EFM.6.07.30",
                        _("Schema targetNamespace length (%(length)s) is over 255 bytes long in utf-8 %(targetNamespace)s"),
                        modelObject=modelDocument, length=l, targetNamespace=modelDocument.targetNamespace, value=modelDocument.targetNamespace)

    # check linkbaseRef targets
    for elt in modelDocument.topLinkElements:
        # check href'ed target if a linkbaseRef
        if elt.namespaceURI == XbrlConst.link:
            if elt.localName == "linkbaseRef":
                hrefedDoc = elt.modelHref.modelDocument
                hrefedElt = elt.dereference()
                # check linkbaseRef target
                if (hrefedDoc is None or
                    hrefedDoc.type < ModelDocument.Type.firstXBRLtype or  # range of doc types that can have linkbase
                    hrefedDoc.type > ModelDocument.Type.lastXBRLtype or
                    hrefedElt.namespaceURI != XbrlConst.link or hrefedElt.localName != "linkbase"):
                    val.modelXbrl.error("xbrl.4.3.2:linkbaseRefHref",
                        _("LinkbaseRef %(linkbaseHref)s does not identify an link:linkbase element"),
                        modelObject=(elt, hrefedDoc), 
                        linkbaseHref=elt.href)
                elif elt.role is not None:
                    role = elt.role
                    for linkNode in hrefedElt.iterchildren(ModelXlinkExtended):
                        if (isinstance(linkNode,ModelObject) and
                            linkNode.xlinkType == "extended"):
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
                                    modelObject=elt, 
                                    linkbaseHref=elt.href,
                                    role=role, link=linkNode.prefixedName)
            elif elt.localName == "schemaRef":
                # check schemaRef target
                hrefedDoc = elt.modelHref.modelDocument
                if (hrefedDoc is None or hrefedDoc.type != ModelDocument.Type.SCHEMA):
                    val.modelXbrl.error("xbrl.4.2.2:schemaRefHref",
                        _("SchemaRef %(schemaRef)s does not identify an xsd:schema element"),
                        modelObject=elt, schemaRef=elt.href)
            for hrefElt in elt.iter(ModelXlinkLocator, ModelXlinkSimple):
                if hrefElt.href is None:
                    if isinstance(hrefElt, ModelXlinkLocator):
                        parentElt = hrefElt.getparent()
                        if parentElt and XbrlConst.isStandardResourceOrExtLinkElement(parentElt):
                            val.modelXbrl.error("xbrl.3.5.3.7.2:requiredAttribute",
                                    _('Locator href attribute missing or malformed in standard extended link'),
                                    modelObject=hrefElt)
                        else:
                            val.modelXbrl.warning("arelle:hrefWarning",
                                    _('Locator href attribute missing in non-standard extended link'),
                                    modelObject=hrefElt)
                    continue
                hrefedDoc = hrefElt.modelHref.modelDocument
                hrefFragment = hrefElt.href.fragment
                if hrefFragment:  #check scheme regardless of whether document loaded 
                    # check all xpointer schemes
                    for scheme, path in XmlUtil.xpointerSchemes(hrefFragment):
                        if scheme != "element":
                            val.modelXbrl.error("xbrl.3.5.4:hrefScheme",
                                _("Href %(elementHref)s unsupported scheme: %(scheme)s"),
                                modelObject=hrefElt, 
                                elementHref=hrefElt.href,
                                scheme=scheme)
                            break
                        elif val.validateEFMorGFM:
                            val.modelXbrl.error(("EFM.6.03.06", "GFM.1.01.03"),
                                _("Href %(elementHref)s may only have shorthand xpointers"),
                                modelObject=hrefElt, 
                                elementHref=hrefElt.href)
                    
                if hrefedDoc and hrefedDoc.type != ModelDocument.Type.UnknownNonXML:
                    if hrefFragment:
                        hrefedElt = hrefedDoc.fragmentObject(hrefFragment)
                        if hrefedElt is None:
                            val.modelXbrl.error("xbrl.3.5.4:hrefIdNotFound",
                                _("Href %(elementHref)s not located"),
                                modelObject=hrefElt, elementHref=hrefElt.href)
                    else:
                        hrefedElt = hrefedDoc.xmlRootElement
    
                    # check loc target 
                    if hrefElt.localName == "loc":
                        linkElt = hrefElt.getparent()
                        if linkElt.namespaceURI ==  XbrlConst.link:
                            acceptableTarget = False
                            hrefEltKey = linkElt.localName
                            if hrefElt in val.remoteResourceLocElements:
                                hrefEltKey += "ToResource"
                            for tgtTag in {
                                       "labelLink":("XBRL-concept", "{http://www.xbrl.org/2003/linkbase}label"),
                                       "labelLinkToResource":("{http://www.xbrl.org/2003/linkbase}label",),
                                       "referenceLink":("XBRL-concept", "{http://www.xbrl.org/2003/linkbase}reference"),
                                       "referenceLinkToResource":("{http://www.xbrl.org/2003/linkbase}reference",),
                                       "calculationLink":("XBRL-concept",),
                                       "definitionLink":("XBRL-concept",),
                                       "presentationLink":("XBRL-concept",),
                                       "footnoteLink":("XBRL-item-or-tuple",) }[hrefEltKey]:
                                if tgtTag == "XBRL-item-or-tuple":
                                    acceptableTarget = isinstance(hrefedElt, ModelFact) and (hrefedElt.isItem or hrefedElt.isTuple)
                                elif tgtTag == "XBRL-concept":
                                    acceptableTarget =  isinstance(hrefedElt, ModelConcept)
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
                                     locHref=hrefElt.href,
                                     acceptableTarget= {"labelLink": "concept or label",
                                                        "labelLinkToResource": "label",
                                                        "referenceLink":"concept or reference",
                                                        "referenceLinkToResource":"reference",
                                                        "calculationLink": "concept",
                                                        "definitionLink": "concept",
                                                        "presentationLink": "concept",
                                                        "footnoteLink": "item or tuple" }[hrefEltKey],
                                     messageCodes=("xbrl.5.2.2.1:labelLinkLocTarget", "xbrl.5.2.3.1:referenceLinkLocTarget", "xbrl.5.2.5.1:calculationLinkLocTarget", "xbrl.5.2.6.1:definitionLinkLocTarget", "xbrl.5.2.4.1:presentationLinkLocTarget", "xbrl.4.11.1.1:footnoteLinkLocTarget"))
                            if isInstance and not hrefedElt.isdescendantof(modelDocument.xmlRootElement):
                                val.modelXbrl.error("xbrl.4.11.1.1:instanceLoc",
                                    _("Instance loc's href %(locHref)s not an element in same instance"),
                                     modelObject=hrefElt, locHref=hrefElt.href)
                        ''' is this ever needed???
                        else: # generic link or other non-2.1 link element
                            if (hrefElt.modelDocument.inDTS and 
                                ModelDocument.Type.firstXBRLtype <= hrefElt.modelDocument.type <= ModelDocument.Type.lastXBRLtype and # is a discovered linkbase
                                not ModelDocument.Type.firstXBRLtype <= hrefedDoc.type <= ModelDocument.Type.lastXBRLtype): # must discover schema or linkbase
                                val.modelXbrl.error("xbrl.3.2.3:linkLocTarget",
                                    _("Locator %(xlinkLabel)s on link:loc in a discovered linkbase does not target a schema or linkbase"),
                                    modelObject=(hrefedElt, hrefedDoc),
                                    xlinkLabel=hrefElt.xlinkLabel)
                        '''
                        # non-standard link holds standard loc, href must be discovered document 
                        if (hrefedDoc.type < ModelDocument.Type.firstXBRLtype or  # range of doc types that can have linkbase
                            hrefedDoc.type > ModelDocument.Type.lastXBRLtype or
                            not hrefedDoc.inDTS) and hrefElt.namespaceURI == XbrlConst.link:
                            val.modelXbrl.error("xbrl.3.5.3.7.2:instanceLocInDTS",
                                _("Loc's href %(locHref)s does not identify an element in an XBRL document discovered as part of the DTS"),
                                modelObject=hrefElt, locHref=hrefElt.href)

    # used in linkbase children navigation but may be errant linkbase elements                            
    val.roleRefURIs = {}
    val.arcroleRefURIs = {}
    val.elementIDs = set()
    val.annotationsCount = 0  
            
    # XML validation checks (remove if using validating XML)
    val.extendedElementName = None
    isFilingDocument = False
    if (modelDocument.url.startswith(val.modelXbrl.urlDir) and
        modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces and 
        (modelDocument.xmlRootElement or modelDocument.topLinkElements)):
        isFilingDocument = True
        val.valUsedPrefixes = set()
        val.schemaRoleTypes = {}
        val.schemaArcroleTypes = {}
        val.referencedNamespaces = set()

        val.containsRelationship = False

        if modelDocument.type == ModelDocument.Type.INLINEXBRL:
            val.ixTagWild = modelDocument.ixNStag + "*"
            val.qnIxFractionalTerms = (QName(modelDocument.ixNS, "ix", "numerator"), QName(modelDocument.ixNS, "ix", "denominator"))
            val.qnIxFraction = QName(modelDocument.ixNS, "ix", "fraction")
            val.qnIx11Fraction = QName(XbrlConst.ixbrl11, "ix", "fraction") # inline 1.1 only
            val.qnIxNonFraction = QName(modelDocument.ixNS, "ix", "nonFraction")
            val.qnIxTupleDescendants = (val.qnIxFraction, val.qnIxNonFraction, QName(modelDocument.ixNS, "ix", "nonNumeric"), QName(modelDocument.ixNS, "ix", "tuple"))
        
        checkElements(val, modelDocument, modelDocument.xmlRootElement or modelDocument.topLinkElements)
        
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

def checkElements(val, modelDocument, parent):
    isSchema = modelDocument.type == ModelDocument.Type.SCHEMA
    if isinstance(parent, ModelObject):
        parentXlinkType = getattr(parent, "xlinkType", None)
        isInstance = parent.namespaceURI == XbrlConst.xbrli and parent.localName == "xbrl"
        parentIsLinkbase = parent.namespaceURI == XbrlConst.link and parent.localName == "linkbase"
        parentIsSchema = parent.namespaceURI == XbrlConst.xsd and parent.localName == "schema"
        if isInstance or parentIsLinkbase: # only for non-inline instance
            val.roleRefURIs = {} # uses ixdsRoleRefURIs when inline instance (across all target documents)
            val.arcroleRefURIs = {}
            def linkbaseTopElts():
                for refPass in (True, False): # do roleType and arcroleType before extended links and any other children
                    for child in parent.iterchildren():
                        if refPass == (isinstance(child, ModelObject)
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
        if isinstance(parent, list):
            childrenIter = parent
        else:
            childrenIter = (parent,)
        if isSchema:
            val.inSchemaTop = True

    parentIsAppinfo = False
    if modelDocument.type == ModelDocument.Type.INLINEXBRL:
        if isinstance(parent, ModelObject): # element
            if (parent.localName == "meta" and parent.namespaceURI == XbrlConst.xhtml and 
                (parent.get("http-equiv") or "").lower() == "content-type"):
                val.metaContentTypeEncoding = HtmlUtil.attrValue(parent.get("content"), "charset")
        elif isinstance(parent,etree._ElementTree): # documentNode
            val.documentTypeEncoding = modelDocument.documentEncoding # parent.docinfo.encoding
            val.metaContentTypeEncoding = ""

    instanceOrder = 0
    for elt in childrenIter:
        if isinstance(elt, ModelObject):
            # checks for elements in schemas only
            if isSchema:
                if elt.namespaceURI == XbrlConst.xsd:
                    localName = elt.localName
                    if localName == "annotation":
                        val.annotationsCount += 1
                        
                # check schema roleTypes        
                if elt.localName in ("roleType","arcroleType") and elt.namespaceURI == XbrlConst.link:
                    uriAttr, xbrlSection, roleTypes, localRoleTypes = {
                           "roleType":("roleURI","5.1.3",val.modelXbrl.roleTypes, val.schemaRoleTypes), 
                           "arcroleType":("arcroleURI","5.1.4",val.modelXbrl.arcroleTypes, val.schemaArcroleTypes)
                           }[elt.localName]
                    parentElt = elt.getparent() # None for schema appinfo-located link elements
                    if parentElt and not parentElt.localName == "appinfo" and parentElt.namespaceURI == XbrlConst.xsd:
                        val.modelXbrl.error("xbrl.{0}:{1}Appinfo".format(xbrlSection,elt.localName),
                            _("%(element)s not child of xsd:appinfo"),
                            modelObject=elt, element=elt.qname,
                            messageCodes=("xbrl.5.1.3:roleTypeAppinfo", "xbrl.5.1.4:arcroleTypeAppinfo"))
                    else: # parent is appinfo, element IS in the right location
                        roleURI = getattr(elt, uriAttr)
                        if roleURI is None or not UrlUtil.isValid(roleURI):
                            val.modelXbrl.error("xbrl.{0}:{1}Missing".format(xbrlSection,uriAttr),
                                _("%(element)s missing or invalid %(attribute)s"),
                                modelObject=elt, element=elt.qname, attribute=uriAttr,
                                messageCodes=("xbrl.5.1.3:roleTypeMissing", "xbrl.5.1.4:arcroleTypeMissing"))
                        if roleURI in localRoleTypes:
                            val.modelXbrl.error("xbrl.{0}:{1}Duplicate".format(xbrlSection,elt.localName),
                                _("Duplicate %(element)s %(attribute)s %(roleURI)s"),
                                modelObject=(elt, localRoleTypes[roleURI]), element=elt.qname, attribute=uriAttr, roleURI=roleURI,
                                messageCodes=("xbrl.5.1.3:roleTypeDuplicate", "xbrl.5.1.4:arcroleTypeDuplicate"))
                        else:
                            localRoleTypes[roleURI] = elt
                        for otherRoleType in roleTypes[roleURI]:
                            if elt != otherRoleType and not elt.isEqualTo(otherRoleType):
                                val.modelXbrl.error("xbrl.{0}:{1}s-inequality".format(xbrlSection,elt.localName),
                                    _("%(element)s %(roleURI)s not s-equal in %(otherSchema)s"),
                                    modelObject=elt, element=elt.qname, roleURI=roleURI,
                                    otherSchema=otherRoleType.modelDocument.basename,
                                    messageCodes=("xbrl.5.1.3:roleTypes-inequality", "xbrl.5.1.4:arcroleTypes-inequality"))
                        if elt.localName == "arcroleType":
                            cycles = elt.cyclesAllowed
                            if cycles not in ("any", "undirected", "none"):
                                val.modelXbrl.error("xbrl.{0}:{1}CyclesAllowed".format(xbrlSection,elt.localName),
                                    _("%(element)s %(roleURI)s invalid cyclesAllowed %(value)s"),
                                    modelObject=elt, element=elt.qname, roleURI=roleURI, value=cycles,
                                    messageCodes=("xbrl.5.1.3:roleTypeCyclesAllowed", "xbrl.5.1.4:arcroleTypeCyclesAllowed"))
                        if val.validateEFM and len(roleURI) > 85:
                            l = len(roleURI.encode("utf-8"))
                            if l > 255:
                                val.modelXbrl.error("EFM.6.07.30",
                                    _("Schema %(element)s %(attribute)s length (%(length)s) is over 255 bytes long in utf-8 %(roleURI)s"),
                                    modelObject=elt, element=elt.qname, attribute=uriAttr, length=l, roleURI=roleURI, value=roleURI)
            elif modelDocument.type == ModelDocument.Type.LINKBASE:
                pass
            # check of roleRefs when parent is linkbase or instance element
            if isinstance(elt, ModelXlinkObject):
                xlinkType = getattr(elt, "xlinkType", None) # c-level attribute
                xlinkRole = getattr(elt, "role", None)
            else:
                xlinkType = xlinkRole = None
            if elt.namespaceURI == XbrlConst.link:
                if elt.localName == "linkbase":
                    if elt.parentQName is not None and elt.parentQName not in (XbrlConst.qnXsdAppinfo, XbrlConst.qnXsSyntheticAnnotationAppinfo):
                        val.modelXbrl.error("xbrl.5.2:linkbaseRootElement",
                            "Linkbase must be a root element or child of appinfo, and may not be nested in %(parent)s",
                            parent=elt.parentQName,
                            modelObject=elt)
                elif elt.localName in ("roleRef","arcroleRef"):
                    uriAttr, xbrlSection, roleTypeDefs, refs = {
                           "roleRef":("roleURI","3.5.2.4",val.modelXbrl.roleTypes,val.roleRefURIs), 
                           "arcroleRef":("arcroleURI","3.5.2.5",val.modelXbrl.arcroleTypes,val.arcroleRefURIs)
                           }[elt.localName]
                    if parentIsAppinfo:
                        pass    #ignore roleTypes in appinfo (test case 160 v05)
                    elif not (parentIsLinkbase or isInstance or elt.parentQName in (XbrlConst.qnIXbrlResources, XbrlConst.qnIXbrl11Resources)):
                        val.modelXbrl.info("info:{1}Location".format(xbrlSection,elt.localName),
                            _("Link:%(elementName)s not child of link:linkbase or xbrli:instance"),
                            modelObject=elt, elementName=elt.localName,
                            messageCodes=("info:roleRefLocation", "info:arcroleRefLocation"))
                    else: # parent is linkbase or instance, element IS in the right location
        
                        # check for duplicate roleRefs when parent is linkbase or instance element
                        refUri = getattr(elt, uriAttr)
                        hrefAttr = elt.href
                        hrefUri, hrefId = UrlUtil.splitDecodeFragment(hrefAttr)
                        if refUri == "":
                            val.modelXbrl.error("xbrl.{}.5:{}Missing".format(xbrlSection,elt.localName),
                                _("%(element)s %(refURI)s missing"),
                                modelObject=elt, element=elt.qname, refURI=refUri,
                                messageCodes=("xbrl.3.5.2.4.5:roleRefMissing", "xbrl.3.5.2.5.5:arcroleRefMissing"))
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
    
            # checks for elements in linkbases
            if elt.namespaceURI == XbrlConst.link:
                if elt.localName in ("schemaRef", "linkbaseRef", "roleRef", "arcroleRef"):
                    if xlinkType != "simple":
                        val.modelXbrl.error("xbrl.3.5.1.1:simpleLinkType",
                            _("Element %(element)s missing xlink:type=\"simple\""),
                            modelObject=elt, element=elt.qname)
                    href = elt.href
                    if not href or "xpointer(" in href:
                        val.modelXbrl.error("xbrl.3.5.1.2:simpleLinkHref",
                            _("Element %(element)s missing or invalid href"),
                            modelObject=elt, element=elt.qname)
                    if elt.localName == "linkbaseRef" and \
                        elt.arcrole != XbrlConst.xlinkLinkbase:
                            val.modelXbrl.error("xbrl.4.3.3:linkbaseRefArcrole",
                                _("LinkbaseRef missing arcrole"),
                                modelObject=elt)
                elif elt.localName == "loc":
                    if xlinkType != "locator":
                        val.modelXbrl.error("xbrl.3.5.3.7.1:linkLocType",
                            _("Element %(element)s missing xlink:type=\"locator\""),
                            modelObject=elt, element=elt.qname)
                    for name, errName in (("href","xbrl.3.5.3.7.2:linkLocHref"),
                                          ("xlinkLabel","xbrl.3.5.3.7.3:linkLocLabel")):
                        if getattr(elt, name) is None:
                            val.modelXbrl.error(errName,
                                _("Element %(element)s missing: %(attribute)s"),
                                modelObject=elt, element=elt.qname, attribute=name,
                                messageCodes=("xbrl.3.5.3.7.2:linkLocHref","xbrl.3.5.3.7.3:linkLocLabel"))
                elif xlinkType == "resource":
                    if elt.localName == "footnote" and elt._xmlLang is None:
                        val.modelXbrl.error("xbrl.4.11.1.2.1:footnoteLang",
                            _("Footnote %(xlinkLabel)s element missing xml:lang attribute"),
                            modelObject=elt, xlinkLabel=elt.xlinkLabel)
                    elif elt.localName == "label" and elt._xmlLang is None:
                        val.modelXbrl.error("xbrl.5.2.2.2.1:labelLang",
                            _("Label %(xlinkLabel)s element missing xml:lang attribute"),
                            modelObject=elt, xlinkLabel=elt.xlinkLabel)
                    # TBD: add lang attributes content validation
            if xlinkRole is not None:
                checkLinkRole(val, elt, elt.qname, xlinkRole, xlinkType, val.roleRefURIs)
            if isinstance(elt, ModelXlinkArc):
                checkArcrole(val, elt, elt.qname, elt.arcrole, val.arcroleRefURIs)
    
            #check resources
            if parentXlinkType == "extended":
                parentElt = elt.getparent()
                if elt.localName not in ("documentation", "title") and \
                    xlinkType not in ("arc", "locator", "resource"):
                    val.modelXbrl.error("xbrl.3.5.3.8.1:resourceType",
                        _("Element %(element)s appears to be a resource missing xlink:type=\"resource\""),
                        modelObject=elt, element=elt.qname)
                elif (xlinkType == "locator" and elt.namespaceURI != XbrlConst.link and parentElt and
                      parentElt.namespaceURI == XbrlConst.link and parentElt.localName in link_loc_spec_sections): 
                    val.modelXbrl.error("xbrl.{0}:customLocator".format(link_loc_spec_sections[parent.localName]),
                        _("Element %(element)s is a custom locator in a standard %(link)s"),
                        modelObject=(elt,parentElt), element=elt.qname, link=parentElt.qname,
                        messageCodes=("xbrl.5.2.2.1:customLocator", "xbrl.5.2.3.1:customLocator", "xbrl.5.2.5.1:customLocator", "xbrl.5.2.6.1:customLocator", "xbrl.5.2.4.1:customLocator", "xbrl.4.11.1.1:customLocator"))
                
            if xlinkType == "resource":
                if not elt.xlinkLabel:
                    val.modelXbrl.error("xbrl.3.5.3.8.2:resourceLabel",
                        _("Element %(element)s missing xlink:label"),
                        modelObject=elt, element=elt.qname)
            elif xlinkType == "arc":
                for name, errName in (("fromLabel", "xbrl.3.5.3.9.2:arcFrom"),
                                      ("toLabel", "xbrl.3.5.3.9.2:arcTo")):
                    if not getattr(elt, name):
                        val.modelXbrl.error(errName,
                            _("Element %(element)s missing xlink:%(attribute)s"),
                            modelObject=elt, element=elt.qname, attribute=name,
                            messageCodes=("xbrl.3.5.3.9.2:arcFrom", "xbrl.3.5.3.9.2:arcTo"))
                if val.modelXbrl.hasXDT and elt.targetRole is not None:
                    targetRole = elt.targetRole
                    if not XbrlConst.isStandardRole(targetRole) and \
                       elt.qname == XbrlConst.qnLinkDefinitionArc and \
                       targetRole not in val.roleRefURIs:
                        val.modelXbrl.error("xbrldte:TargetRoleNotResolvedError",
                            _("TargetRole %(targetRole)s is missing a roleRef"),
                            modelObject=elt, element=elt.qname, targetRole=targetRole)
                val.containsRelationship = True
            xmlLang = elt._xmlLang # element's lang, not inherited lang
            if val.validateXmlLang and xmlLang is not None:
                if not val.disclosureSystem.xmlLangPattern.match(xmlLang):
                    val.modelXbrl.error("SBR.NL.2.3.8.01" if (val.validateSBRNL and xmlLang.startswith('nl')) else "SBR.NL.2.3.8.02" if (val.validateSBRNL and xmlLang.startswith('en')) else "arelle:langError",
                        _("Element %(element)s %(xlinkLabel)s has unauthorized xml:lang='%(lang)s'"),
                        modelObject=elt, element=elt.qname,
                        xlinkLabel=elt.xlinkLabel,
                        lang=elt.xmlLang,
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

            if modelDocument.type in (ModelDocument.Type.UnknownXML, ModelDocument.Type.INSTANCE):
                if elt.localName == "xbrl" and elt.namespaceURI == XbrlConst.xbrli:
                    if elt.getparent() is not None:
                        val.modelXbrl.error("xbrl.4:xbrlRootElement",
                            "Xbrl must be a root element, and may not be nested in %(parent)s",
                            parent=elt.parentQName,
                            modelObject=elt)
                elif elt.localName == "schema" and elt.namespaceURI == XbrlConst.xsd:
                    if elt.getparent() is not None:
                        val.modelXbrl.error("xbrl.5.1:schemaRootElement",
                            "Schema must be a root element, and may not be nested in %(parent)s",
                            parent=elt.parentQName,
                            modelObject=elt)
                    
            if modelDocument.type == ModelDocument.Type.INLINEXBRL and elt.namespaceURI in XbrlConst.ixbrlAll: 
                if elt.localName == "footnote":
                    if val.validateGFM:
                        if elt.arcrole != XbrlConst.factFootnote:
                            # must be in a nonDisplay div
                            if not any(inlineDisplayNonePattern.search(e.get("style") or "") # may be un-namespaced html
                                       for e in elt.iterancestors("{http://www.w3.org/1999/xhtml}div", "div")):
                                val.modelXbrl.error(("EFM.N/A", "GFM:1.10.16"),
                                    _("Inline XBRL footnote %(footnoteID)s must be in non-displayable div due to arcrole %(arcrole)s"),
                                    modelObject=elt, footnoteID=elt.get("footnoteID"), 
                                    arcrole=elt.arcrole)
                            
                        if not elt.xmlLang:
                            val.modelXbrl.error(("EFM.N/A", "GFM:1.10.13"),
                                _("Inline XBRL footnote %(footnoteID)s is missing an xml:lang attribute"),
                                modelObject=elt, footnoteID=id)
                    if elt.namespaceURI == XbrlConst.ixbrl:
                        val.ixdsFootnotes[elt.footnoteID] = elt
                    else:
                        checkIxContinuationChain(elt)  
                    if not elt.xmlLang:
                        val.modelXbrl.error(ixMsgCode("footnoteLang", elt, sect="validation"),
                            _("Inline XBRL footnotes require an in-scope xml:lang"),
                            modelObject=elt)
                elif elt.localName == "fraction":
                    ixDescendants = [e for e in elt.iterdescendants(val.ixTagWild)]
                    wrongDescendants = [d
                                        for d in ixDescendants
                                        if d.localName not in ('numerator','denominator','fraction')]
                    if wrongDescendants:
                        val.modelXbrl.error(ixMsgCode("fractionDescendants", elt, sect="validation"),
                            _("Inline XBRL fraction may only contain ix:numerator, ix:denominator, or ix:fraction, but contained %(wrongDescendants)s"),
                            modelObject=[elt] + wrongDescendants, wrongDescendants=", ".join(str(d.elementQName) for d in wrongDescendants))
                    ixDescendants = [e for e in elt.iterdescendants(*val.qnIxFractionalTerms)] # ix elements have xbrli qname field
                    if not elt.isNil:
                        if sorted(d.localName for d in ixDescendants) != ['denominator','numerator']:
                            val.modelXbrl.error(ixMsgCode("fractionTerms", elt, sect="validation"),
                                _("Inline XBRL fraction must have one ix:numerator and one ix:denominator when not nil"),
                                modelObject=[elt] + ixDescendants)
                    else:
                        if ixDescendants: # nil and has fraction term elements
                            val.modelXbrl.error(ixMsgCode("fractionNilTerms", elt, sect="validation"),
                                _("Inline XBRL fraction must not have ix:numerator or ix:denominator when nil"),
                                modelObject=[elt] + ixDescendants)
                        for e2 in elt.iterancestors(val.qnIxFraction):
                            val.modelXbrl.error(ixMsgCode("nestedFractionIsNil", elt, sect="validation"),
                                _("Inline XBRL nil ix:fraction may not have an ancestor ix:fraction"),
                                modelObject=(elt,e2))
                    for e2 in elt.iterancestors(val.qnIx11Fraction): # only ix 1.1
                        if elt.unitID != e2.unitID:
                            val.modelXbrl.error(ixMsgCode("fractionNestedUnitRef", elt),
                                _("Inline XBRL %(fact)s fraction and ancestor fractions must have matching unitRefs: %(unitRef)s, %(unitRef2)s"),
                                modelObject=[elt, e2], fact=elt.qname, unitRef=elt.unitID, unitRef2=e2.unitID)
                elif elt.localName in ("denominator", "numerator"):
                    wrongDescendants = [d for d in elt.iterdescendants()]
                    if wrongDescendants:
                        val.modelXbrl.error(ixMsgCode("fractionTermDescendants", elt, sect="validation"),
                            _("Inline XBRL fraction term ix:%(name)s may only contain text nodes, but contained %(wrongDescendants)s"),
                            modelObject=[elt] + wrongDescendants, name=elt.localName, wrongDescendants=", ".join(str(d.elementQName) for d in wrongDescendants))
                    if elt.format is None and '-' in XmlUtil.innerText(elt):
                        val.modelXbrl.error(ixMsgCode("fractionTermNegative", elt, sect="validation"),
                            _("Inline XBRL ix:numerator or ix:denominator without format attribute must be non-negative"),
                            modelObject=elt)
                elif elt.localName == "header":
                    if not any(inlineDisplayNonePattern.search(e.get("style") or "")  # may be un-namespaced html
                               for e in elt.iterancestors("{http://www.w3.org/1999/xhtml}div", "div")):
                        val.modelXbrl.warning(ixMsgCode("headerDisplayNone", elt, sect="non-validatable"),
                            _("Warning, Inline XBRL ix:header is recommended to be nested in a <div> with style display:none"),
                            modelObject=elt)
                    val.ixdsHeaderCount += 1
                elif elt.localName == "nonFraction":
                    c = [e for e in elt.iterchildren()]
                    # must check _text because textValue and stringValue overridden in ModelInlineValueObject
                    hasText = (elt._text or "") or any((childElt.tail or "") for childElt in c)
                    if elt.isNil:
                        for e2 in elt.iterancestors(val.qnIxNonFraction):
                            val.modelXbrl.error(ixMsgCode("nestedNonFractionIsNil", elt, sect="validation"),
                                _("Inline XBRL nil ix:nonFraction may not have an ancestor ix:nonFraction"),
                                modelObject=(elt,e2))
                        if c or hasText:
                            modelXbrl.error(ixMsgCode("nonFractionTextAndElementChildren", elt),
                                _("Fact %(fact)s is a nil nonFraction and MUST not have an child elements or text"),
                                modelObject=[elt] + c, fact=elt.qname)
                            elt.setInvalid() # prevent further validation or cascading errors
                    else:
                        if ((c and (len(c) != 1 or c[0].namespaceURI != elt.namespaceURI or c[0].localName != "nonFraction")) or
                            (c and hasText)):
                            val.modelXbrl.error(ixMsgCode("nonFractionTextAndElementChildren", elt, sect="validation"),
                                _("Inline XBRL nil ix:nonFraction %(fact)s may only have one child ix:nonFraction"),
                                modelObject=[elt] + c, fact=elt.qname)
                            elt.setInvalid() # prevent further validation or cascading errors
                        for e in c:
                            if (e.namespaceURI == elt.namespaceURI and e.localName == "nonFraction" and
                                (e.format != elt.format or e.scale != elt.scale or e.unitID != elt.unitID)):
                                val.modelXbrl.error(ixMsgCode("nestedNonFractionProperties", e, sect="validation"),
                                    _("Inline XBRL nested ix:nonFraction must have matching format, scale, and unitRef properties"),
                                    modelObject=(elt, e))
                    if elt.format is None and '-' in XmlUtil.innerText(elt):
                        val.modelXbrl.error(ixMsgCode("nonFractionNegative", elt, sect="validation"),
                            _("Inline XBRL ix:nonFraction without format attribute must be non-negative"),
                            modelObject=elt)
                elif elt.localName == "nonNumeric":
                    checkIxContinuationChain(elt)
                elif elt.localName == "references":
                    val.ixdsReferences[elt.get("target")].append(elt)
                elif elt.localName == "relationship":
                    val.ixdsRelationships.append(elt)
                elif elt.localName == "tuple":
                    if not elt.tupleID:
                        if not elt.isNil:
                            if not any(True for e in elt.iterdescendants(*val.qnIxTupleDescendants)):
                                val.modelXbrl.error(ixMsgCode("tupleID", elt, sect="validation"),
                                    _("Inline XBRL non-nil tuples without ix:fraction, ix:nonFraction, ix:nonNumeric or ix:tuple descendants require a tupleID"),
                                    modelObject=elt)
                    else:
                        val.ixdsTuples[elt.tupleID] = elt
                if elt.localName in {"fraction", "nonFraction", "nonNumeric", "references", "relationship", "tuple"}:
                    for attrTag in elt.attrs or ():
                        if attrTag.startswith("{http://www.xbrl.org/2003/instance}"):
                            val.modelXbrl.error(ixMsgCode("qualifiedAttributeDisallowed", elt),
                                _("Inline XBRL element %(element)s has disallowed attribute %(name)s"),
                                modelObject=elt, element=str(elt.elementQName), name=attrTag)
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
                if xlinkType == "resource":
                    if not xlinkRole:
                        val.modelXbrl.error(("EFM.6.09.04", "GFM.1.04.04"),
                            _("%(element)s is missing an xlink:role"),
                            modelObject=elt, element=elt.qname)
                    elif not XbrlConst.isStandardRole(xlinkRole):
                        modelsRole = val.modelXbrl.roleTypes.xlinkRole
                        if (modelsRole is None or len(modelsRole) == 0 or 
                            modelsRole[0].modelDocument.targetNamespace not in val.disclosureSystem.standardTaxonomiesDict):
                            val.modelXbrl.error(("EFM.6.09.05", "GFM.1.04.05", "SBR.NL.2.3.10.14"),
                                _("Resource %(xlinkLabel)s role %(role)s is not a standard taxonomy role"),
                                modelObject=elt, xlinkLabel=elt.xlinkLabel, role=xlinkRole, element=elt.qname,
                                roleDefinition=val.modelXbrl.roleTypeDefinition(xlinkRole))
                if xlinkType == "arc":
                    if elt.priority is not None:
                        priority = elt.priority
                        try:
                            if int(priority) >= 10:
                                val.modelXbrl.error(("EFM.6.09.09", "GFM.1.04.08"),
                                    _("Arc from %(xlinkFrom)s to %(xlinkTo)s priority %(priority)s must be less than 10"),
                                    modelObject=elt, 
                                    arcElement=elt.qname,
                                    xlinkFrom=elt.fromLabel,
                                    xlinkTo=elt.toLabel,
                                    priority=priority)
                        except (ValueError) :
                            val.modelXbrl.error(("EFM.6.09.09", "GFM.1.04.08"),
                                _("Arc from %(xlinkFrom)s to %(xlinkTo)s priority %(priority)s is not an integer"),
                                modelObject=elt, 
                                arcElement=elt.qname,
                                xlinkFrom=elt.fromLabel,
                                xlinkTo=elt.toLabel,
                                priority=priority)
                    if elt.namespaceURI == XbrlConst.link:
                        if elt.localName == "presentationArc" and not elt.order:
                            val.modelXbrl.error(("EFM.6.12.01", "GFM.1.06.01", "SBR.NL.2.3.4.04"),
                                _("PresentationArc from %(xlinkFrom)s to %(xlinkTo)s must have an order"),
                                modelObject=elt, 
                                xlinkFrom=elt.elt.fromLabel,
                                xlinkTo=elt.toLabel,
                                conceptFrom=arcFromConceptQname(elt),
                                conceptTo=arcToConceptQname(elt))
                        elif elt.localName == "calculationArc":
                            if not elt.order:
                                val.modelXbrl.error(("EFM.6.14.01", "GFM.1.07.01"),
                                    _("CalculationArc from %(xlinkFrom)s to %(xlinkTo)s must have an order"),
                                    modelObject=elt, 
                                    xlinkFrom=elt.fromLabel,
                                    xlinkTo=elt.toLabel,
                                    conceptFrom=arcFromConceptQname(elt),
                                    conceptTo=arcToConceptQname(elt))
                            try:
                                weightAttr = elt.weight
                                weight = float(weightAttr)
                                if not weight in (1, -1):
                                    val.modelXbrl.error(("EFM.6.14.02", "GFM.1.07.02"),
                                        _("CalculationArc from %(xlinkFrom)s to %(xlinkTo)s weight %(weight)s must be 1 or -1"),
                                        modelObject=elt, 
                                        xlinkFrom=elt.fromLabel,
                                        xlinkTo=elt.toLabel,
                                        conceptFrom=arcFromConceptQname(elt),
                                        conceptTo=arcToConceptQname(elt),
                                        weight=weightAttr)
                            except ValueError:
                                val.modelXbrl.error(("EFM.6.14.02", "GFM.1.07.02"),
                                    _("CalculationArc from %(xlinkFrom)s to %(xlinkTo)s must have an weight (value error in \"%(weight)s\")"),
                                    modelObject=elt, 
                                    xlinkFrom=elt.fromLabel,
                                    xlinkTo=elt.toLabel,
                                    conceptFrom=arcFromConceptQname(elt),
                                    conceptTo=arcToConceptQname(elt),
                                    weight=weightAttr)
                        elif elt.localName == "definitionArc":
                            if not elt.order:
                                val.modelXbrl.error(("EFM.6.16.01", "GFM.1.08.01"),
                                    _("DefinitionArc from %(xlinkFrom)s to %(xlinkTo)s must have an order"),
                                    modelObject=elt, 
                                    xlinkFrom=elt.fromLabel,
                                    xlinkTo=elt.toLabel,
                                    conceptFrom=arcFromConceptQname(elt),
                                    conceptTo=arcToConceptQname(elt))
    
            checkElements(val, modelDocument, elt)
        elif isinstance(elt,ModelComment): # comment node
            pass
                    
def checkLinkRole(val, elt, linkEltQname, xlinkRole, xlinkType, roleRefURIs):
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
        if elt.namespaceURI == XbrlConst.link:
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
        if not any(linkEltQname in roleType.usedOns for roleType in val.modelXbrl.roleTypes.get(xlinkRole,())):
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
                
def checkArcrole(val, elt, arcEltQname, arcrole, arcroleRefURIs):
    if arcrole == "" and \
        elt.xlinkType == "simple":
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


def checkIxContinuationChain(elt, chain=None):
    if chain is None:
        chain = [elt]
    else:
        for otherElt in chain:
            if elt.isdescendantof(otherElt) or otherElt.isdescendantof(elt):
                elt.modelDocument.modelXbrl.error("ix:continuationDescendancy",
                                _("Inline XBRL continuation chain has elements which are descendants of each other."),
                                modelObject=(elt, otherElt))
            else:
                contAt = elt.get("=continuationElement")
                if contAt is not None:
                    chain.append(elt)
                checkIxContinuationChain(contAt, chain)
