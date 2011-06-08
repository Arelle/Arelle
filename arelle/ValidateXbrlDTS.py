'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import (ModelDocument, ModelObject, UrlUtil, XmlUtil, XbrlUtil, XbrlConst)
from arelle.ModelValue import (qname)

instanceSequence = {"schemaRef":1, "linkbaseRef":2, "roleRef":3, "arcroleRef":4}
xsd1_1datatypes = {qname(XbrlConst.xsd,'anyAtomicType'), qname(XbrlConst.xsd,'yearMonthDuration'), qname(XbrlConst.xsd,'dayTimeDuration'), qname(XbrlConst.xsd,'dateTimeStamp'), qname(XbrlConst.xsd,'precisionDecimal')}

def checkDTS(val, modelDocument, visited):
    visited.append(modelDocument)
    for referencedDocument in modelDocument.referencesDocument.items():
        if referencedDocument[0] not in visited:
            checkDTS(val, referencedDocument[0], visited)
            
    # skip processing versioning report here
    if modelDocument.type == ModelDocument.Type.VERSIONINGREPORT:
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
    
    for hrefElt, hrefedDoc, hrefId in modelDocument.hrefObjects:
        hrefedObj = None
        hrefedElt = None
        if hrefedDoc is None:
            val.modelXbrl.error(
                _("Xbrl file {0} href {1} file not found").format(
                      modelDocument.basename,
                      hrefElt.getAttributeNS(XbrlConst.xlink, "href")), 
                "err", "xbrl:hrefFileNotFound")
        elif hrefId:
            if hrefId in hrefedDoc.idObjects:
                hrefedObj = hrefedDoc.idObjects[hrefId]
                hrefedElt = hrefedObj.element
            else:
                hrefedElt = XmlUtil.xpointerElement(hrefedDoc,hrefId)
                if hrefedElt is None:
                    val.modelXbrl.error(
                        _("Xbrl file {0} href {1} not located").format(
                              modelDocument.basename,
                              hrefElt.getAttributeNS(XbrlConst.xlink, "href")), 
                        "err", "xbrl.3.5.4:hrefIdNotFound")
                else:
                    # find hrefObj
                    for docModelObject in hrefedDoc.modelObjects:
                        if docModelObject.element == hrefedElt:
                            hrefedObj = docModelObject
                            break
        else:
            hrefedElt = hrefedDoc.xmlRootElement
            hrefedObj = hrefedDoc
            
        if hrefId:  #check scheme regardless of whether document loaded 
            # check all xpointer schemes
            for scheme, path in XmlUtil.xpointerSchemes(hrefId):
                if scheme != "element":
                    val.modelXbrl.error(
                        _("Xbrl file {0} href {1} unsupported scheme: {2}").format(
                              modelDocument.basename,
                              hrefElt.getAttributeNS(XbrlConst.xlink, "href"), scheme), 
                        "err", "xbrl.3.5.4:hrefScheme")
                    break
                elif val.validateDisclosureSystem:
                    val.modelXbrl.error(
                        _("Xbrl file {0} href {1} may only have shorthand xpointers").format(
                            modelDocument.basename,
                            hrefElt.getAttributeNS(XbrlConst.xlink, "href")), 
                        "err", "EFM.6.03.06", "GFM.1.01.03")
        # check href'ed target if a linkbaseRef
        if hrefElt.namespaceURI == XbrlConst.link and hrefedElt:
            if hrefElt.localName == "linkbaseRef":
                # check linkbaseRef target
                if hrefedElt.namespaceURI != XbrlConst.link or hrefedElt.localName != "linkbase":
                    val.modelXbrl.error(
                        _("Xbrl file {0} linkbaseRef {1} does not identify an link:linkbase element").format(
                              modelDocument.basename,
                              hrefElt.getAttributeNS(XbrlConst.xlink, "href")), 
                        "err", "xbrl.4.3.2:linkbaseRefHref")
                if hrefElt.hasAttributeNS(XbrlConst.xlink, "role"):
                    role = hrefElt.getAttributeNS(XbrlConst.xlink, "role")
                    for linkNode in hrefedElt.childNodes:
                        if linkNode.nodeType == 1: #element
                            if linkNode.getAttributeNS(XbrlConst.xlink, "type") == "extended":
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
                                    val.modelXbrl.error(
                                        _("Xbrl file {0} linkbaseRef {1} role {2} has wrong extended link {3}").format(
                                              modelDocument.basename,
                                              hrefElt.getAttributeNS(XbrlConst.xlink, "href"), role, linkNode.tagName), 
                                        "err", "xbrl.4.3.4:linkbaseRefLinks")
            elif hrefElt.localName == "schemaRef":
                # check schemaRef target
                if hrefedElt.namespaceURI != XbrlConst.xsd or hrefedElt.localName != "schema":
                    val.modelXbrl.error(
                        _("Xbrl file {0} schemaRef {1} does not identify an xsd:schema element").format(
                              modelDocument.basename,
                              hrefElt.getAttributeNS(XbrlConst.xlink, "href")), 
                        "err", "xbrl.4.2.2:schemaRefHref")
            # check loc target 
            elif hrefElt.localName == "loc":
                linkElt = hrefElt.parentNode
                if linkElt.namespaceURI ==  XbrlConst.link:
                    acceptableTarget = False
                    hrefEltKey = linkElt.localName
                    if hrefElt in val.remoteResourceLocElements:
                        hrefEltKey += "ToResource"
                    for tgtNS, tgtLN in {
                               "labelLink":((XbrlConst.xsd, "element"),(XbrlConst.link, "label")),
                               "labelLinkToResource":((XbrlConst.link, "label"),),
                               "referenceLink":((XbrlConst.xsd, "element"),(XbrlConst.link, "reference")),
                               "referenceLinkToResource":((XbrlConst.link, "reference"),),
                               "calculationLink":((XbrlConst.xsd, "element"),),
                               "definitionLink":((XbrlConst.xsd, "element"),),
                               "presentationLink":((XbrlConst.xsd, "element"),),
                               "footnoteLink":(("XBRL-item-or-tuple",None),) }[hrefEltKey]:
                        if tgtNS == "XBRL-item-or-tuple":
                            concept = val.modelXbrl.qnameConcepts.get(qname(hrefedElt))
                            acceptableTarget =  isinstance(concept, ModelObject.ModelConcept) and \
                                                (concept.isItem or concept.isTuple)
                        elif hrefedElt.namespaceURI == tgtNS and hrefedElt.localName == tgtLN:
                            acceptableTarget = True
                    if not acceptableTarget:
                        val.modelXbrl.error(
                             _("Xbrl file {0} {1} loc href {2} must identify a concept or label").format(
                               modelDocument.basename,
                               linkElt.localName,
                               hrefElt.getAttributeNS(XbrlConst.xlink, "href")), 
                              "err", "xbrl.{0}:{1}LocTarget".format(
                                        {"labelLink":"5.2.5.1",
                                         "referenceLink":"5.2.3.1",
                                         "calculationLink":"5.2.5.1",
                                         "definitionLink":"5.2.6.1",
                                         "presentationLink":"5.2.4.1"}[linkElt.localName],
                                         linkElt.localName))
                    if isInstance and not XmlUtil.isDescendantOf(hrefedElt, modelDocument.xmlRootElement):
                        val.modelXbrl.error(
                            _("Xbrl file {0} instance loc's href {1} not an element in same instance").format(
                                  modelDocument.basename,
                                  hrefElt.getAttributeNS(XbrlConst.xlink, "href")), 
                            "err", "xbrl.4.11.1.1:instanceLoc")
                # non-standard link holds standard loc, href must be discovered document 
                if not hrefedDoc.inDTS:
                    val.modelXbrl.error(
                        _("Xbrl file {0} loc's href {1} does not identify an element in an XBRL document discovered as part of the DTS").format(
                              modelDocument.basename,
                              hrefElt.getAttributeNS(XbrlConst.xlink, "href")), 
                        "err", "xbrl.3.5.3.7.2:instanceLocInDTS")

    # used in linkbase children navigation but may be errant linkbase elements                            
    val.roleRefURIs = {}
    val.arcroleRefURIs = {}
    val.elementIDs = set()

        
            
    # XML validation checks (remove if using validating XML)
    val.extendedElementName = None
    if (modelDocument.uri.startswith(val.modelXbrl.uriDir) and
        modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces and 
        modelDocument.xmlDocument):
        val.valUsedPrefixes = set()
        val.schemaRoleTypes = {}
        val.schemaArcroleTypes = {}

        val.containsRelationship = False
        
        checkElements(val, modelDocument, modelDocument.xmlDocument)
        
        if (modelDocument.type == ModelDocument.Type.INLINEXBRL and 
            val.validateGFM and
            (val.documentTypeEncoding.lower() != 'utf-8' or val.metaContentTypeEncoding.lower() != 'utf-8')):
            val.modelXbrl.error(_("XML declaration encoding {0} and meta content type encoding {1} must both be utf-8").format(
                     val.documentTypeEncoding, val.metaContentTypeEncoding), 
                "err", "GFM.1.10.4")
        if val.validateSBRNL:
            if modelDocument.type in (ModelDocument.Type.SCHEMA, ModelDocument.Type.LINKBASE):
                isSchema = modelDocument.type == ModelDocument.Type.SCHEMA
                if modelDocument.xmlDocument.version != "1.0":
                    val.modelXbrl.error(_('{0} file {1} xml version must be "1.0" but is "{2}"').format(
                            modelDocument.gettype().title(), modelDocument.basename, modelDocument.xmlDocument.version), 
                        "err", "SBR.NL.2.2.0.02" if isSchema else "SBR.NL.2.3.0.02")
                if modelDocument.xmlDocument.encoding.lower() != "utf-8":
                    val.modelXbrl.error(_('{0} file {1} encoding must be "utf-8" but is "{2}"').format(
                            modelDocument.gettype().title(), modelDocument.basename, modelDocument.xmlDocument.encoding), 
                        "err", "SBR.NL.2.2.0.03" if isSchema else "SBR.NL.2.3.0.03")
                commentNode = modelDocument.xmlDocument.firstChild
                if commentNode.nodeType != 8 or modelDocument.xmlRootElement.previousSibling != commentNode:
                    val.modelXbrl.error(_('{0} file {1} must have comment node only on line 2').format(
                            modelDocument.gettype().title(), modelDocument.basename), 
                        "err", "SBR.NL.2.2.0.04" if isSchema else "SBR.NL.2.3.0.04")
                elif modelDocument.xmlRootElement.previousSibling != commentNode:
                    val.modelXbrl.error(_('{0} file {1} must have only one comment node before schema element').format(
                            modelDocument.gettype().title(), modelDocument.basename), 
                        "err", "SBR.NL.2.2.0.05,07" if isSchema else "SBR.NL.2.3.0.05")
                
                # check namespaces are used
                for i in range(len(modelDocument.xmlRootElement.attributes)):
                    attribute = modelDocument.xmlRootElement.attributes.item(i)
                    if (((attribute.prefix == "xmlns" and attribute.localName not in val.valUsedPrefixes) or
                         (attribute.name == "xmlns" and None not in val.valUsedPrefixes)) and
                        (modelDocument.type != ModelDocument.Type.SCHEMA or attribute.value != modelDocument.targetNamespace)):
                        val.modelXbrl.error(
                            _('{0} file {1} namespace declaration {2}="{3}" is not used').format(
                                  modelDocument.gettype().title(), modelDocument.basename, attribute.name, attribute.value), 
                            "err", "SBR.NL.2.2.0.11" if modelDocument.type == ModelDocument.Type.SCHEMA else "SBR.NL.2.3.0.08")
            if modelDocument.type ==  ModelDocument.Type.LINKBASE:
                if not val.containsRelationship:
                    val.modelXbrl.error(
                        _("Linkbase file {0} has no relationships").format(
                              modelDocument.gettype().title(), modelDocument.basename, attribute.localName), 
                        "err", "SBR.NL.2.3.0.12")
        del val.valUsedPrefixes
        del val.schemaRoleTypes
        del val.schemaArcroleTypes

    val.roleRefURIs = None
    val.arcroleRefURIs = None
    val.elementIDs = None

def checkElements(val, modelDocument, parent):
    if parent.nodeType == 1:
        parentXlinkType = parent.getAttributeNS(XbrlConst.xlink, "type")
        isInstance = parent.namespaceURI == XbrlConst.xbrli and parent.localName == "xbrl"
        parentIsLinkbase = parent.namespaceURI == XbrlConst.link and parent.localName == "linkbase"
        if isInstance or parentIsLinkbase:
            val.roleRefURIs = {}
            val.arcroleRefURIs = {}

    else: # parent is document node, not an element
        parentXlinkType = None
        isInstance = False
        parentIsLinkbase = False
    isSchema = modelDocument.type == ModelDocument.Type.SCHEMA

    parentIsAppinfo = False
    if modelDocument.type == ModelDocument.Type.INLINEXBRL:
        if parent.nodeType == 1: # element
            if parent.localName == "meta" and parent.namespaceURI == XbrlConst.xhtml and \
            parent.getAttribute("http-equiv").lower() == "content-type":
                from arelle.HtmlUtil import attrValue
                val.metaContentTypeEncoding = attrValue(parent.getAttribute("content"), "charset")
        elif parent.nodeType == 9: # documentNode
            val.documentTypeEncoding = parent._get_encoding()
            val.metaContentTypeEncoding = ""
        elif parent.nodeType == 10: # document type node
            val.documentTypeEncoding = parent.getAttribute("encoding")

    instanceOrder = 0
    if modelDocument.type == ModelDocument.Type.SCHEMA:
        ncnameTests = (("id","xbrl:xmlElementId"), 
                       ("name","xbrl.5.1.1:conceptName"))
    else:
        ncnameTests = (("id","xbrl:xmlElementId"),)
    for elt in parent.childNodes:
        if elt.nodeType == 1:
            for name, errCode in ncnameTests:
                if elt.hasAttribute(name):
                    attrValue = elt.getAttribute(name)
                    if not val.NCnamePattern.match(attrValue):
                        val.modelXbrl.error(
                            _("File {0} element {1} attribute {2} '{3}' is not an NCname").format(
                                  modelDocument.basename,
                                  elt.tagName, 
                                  name,
                                  attrValue), 
                            "err", errCode)
                    if name == "id" and attrValue in val.elementIDs:
                        val.modelXbrl.error(
                            _("File {0} element {1} id {2} is duplicated").format(
                                  modelDocument.basename,
                                  elt.tagName, 
                                  attrValue), 
                            "err", "xmlschema2.3.2.10:idDuplicated")
                    val.elementIDs.add(attrValue)
                    
            # checks for elements in schemas only
            if isSchema:
                if elt.namespaceURI == XbrlConst.xsd:
                    if elt.localName == "schema":
                        if elt.hasAttribute("targetNamespace") and elt.getAttribute("targetNamespace") == "":
                            val.modelXbrl.error(_("Taxonomy file {0} has an empty targetNamespace").format(
                                      modelDocument.basename), 
                                "err", "xbrl.5.1:emptyTargetNamespace")
                        if val.validateSBRNL:
                            if not elt.hasAttribute("targetNamespace"):
                                val.modelXbrl.error(_('Schema file {0} <schema> must have a targetNamespace attribute').format(
                                        modelDocument.basename), 
                                    "err", "SBR.NL.2.2.0.08")
                            if (elt.getAttribute("attributeFormDefault") != "unqualified" or
                                elt.getAttribute("elementFormDefault") != "qualified"):
                                val.modelXbrl.error(_('Schema file {0} schema attributeFormDefault must be "unqualified" and elementFormDefault must be "qualified"').format(
                                        modelDocument.basename), 
                                    "err", "SBR.NL.2.2.0.09")
                            for attrName in ("blockDefault", "finalDefault", "version"):
                                if elt.hasAttribute(attrName):
                                    val.modelXbrl.error(_('Schema file {0} <schema> must not have a {1} attribute').format(
                                            modelDocument.basename, attrName), 
                                        "err", "SBR.NL.2.2.0.10")
                    elif val.validateSBRNL:
                        if elt.localName in ("assert", "openContent", "fallback"):
                            val.modelXbrl.error(
                                _('Schema file {0} contains XSD 1.1 content "xs:{1}"').format(
                                    modelDocument.basename, elt.localName), 
                                "err", "SBR.NL.2.2.0.01")
                                                    
                        if elt.localName == "element":
                            for attr, presence, errCode in (("block", False, "2.2.2.09"),
                                                            ("final", False, "2.2.2.10"),
                                                            ("fixed", False, "2.2.2.11"),
                                                            ("form", False, "2.2.2.12"),):
                                if elt.hasAttribute(attr) != presence:
                                    val.modelXbrl.error(
                                        _('Schema file {0} element {1} {2} contain attribute {3}').format(
                                            modelDocument.basename, elt.getAttribute("name"), (_("MUST NOT"),_("MUST"))[presence], attr), 
                                        "err", "SBR.NL.{0}".format(errCode))
                            type = qname(elt, elt.getAttribute("type"))
                            eltQname = qname(modelDocument.targetNamespace, elt.getAttribute("name"))
                            if type in xsd1_1datatypes:
                                val.modelXbrl.error(
                                    _('Schema file {0} element {1} contains XSD 1.1 datatype "{2}"').format(
                                        modelDocument.basename, elt.getAttribute("name"), type), 
                                    "err", "SBR.NL.2.2.0.01")
                            if parent.localName != "schema": # root element
                                if elt.hasAttribute("name"):
                                    val.modelXbrl.error(
                                        _('Schema file {0} contains an element definition not at the root level: {1}').format(
                                            modelDocument.basename, elt.getAttribute("name")), 
                                        "err", "SBR.NL.2.2.2.01")
                            elif eltQname not in val.typedDomainQnames:
                                for attr, presence, errCode in (("abstract", True, "2.2.2.08"),
                                                                ("id", True, "2.2.2.13"),
                                                                ("nillable", True, "2.2.2.15"),
                                                                ("substitutionGroup", True, "2.2.2.18"),):
                                    if elt.hasAttribute(attr) != presence:
                                        val.modelXbrl.error(
                                            _('Schema file {0} root element {1} {2} contain attribute {3}').format(
                                                modelDocument.basename, elt.getAttribute("name"), (_("MUST NOT"),_("MUST"))[presence], attr), 
                                            "err", "SBR.NL.{0}".format(errCode))
                            # semantic checks
                            modelConcept = modelDocument.idObjects.get(elt.getAttribute("id"))
                            if modelConcept:
                                if modelConcept.isTuple:
                                    val.hasTuple = True
                                elif modelConcept.isLinkPart:
                                    val.hasLinkPart = True
                                elif modelConcept.isItem:
                                    if modelConcept.isDimensionItem:
                                        val.hasDimension = True
                                    #elif modelConcept.substitutesFor()
                                    if modelConcept.isAbstract:
                                        val.hasAbstractItem = True
                                    else:
                                        val.hasNonAbstraceElement = True
                                if modelConcept.isAbstract and modelConcept.isItem:
                                    val.hasAbstractItem = True
                        elif (elt.localName in ("sequence","choice") and 
                              ((elt.hasAttribute("minOccurs") and elt.getAttribute("minOccurs") != "1") or
                               (elt.hasAttribute("maxOccurs") and elt.getAttribute("maxOccurs") != "1"))):
                            val.modelXbrl.error(
                                _('Schema file {0} {1} must have minOccurs and maxOccurs = "1"').format(
                                modelDocument.basename, elt.tagName), 
                                "err", "SBR.NL.2.2.2.33")
                        elif (elt.localName == "enumeration" and 
                              qname(elt.parentNode, elt.parentNode.getAttribute("base")) != XbrlConst.qnXbrliStringItemType):
                            val.modelXbrl.error(
                            _('Schema file {0} enumeration {1} must be a xbrli:stringItemType restriction').format(
                            modelDocument.basename, elt.getAttribute("value")), 
                            "err", "SBR.NL.2.2.7.04")
                    if elt.localName == "redefine":
                        val.modelXbrl.error(
                            _("Taxonomy {0} redefine not allowed").format(
                                  modelDocument.basename),
                            "err", "xbrl.5.6.1:Redefine")
                    if elt.localName == "appinfo":
                        if val.validateSBRNL:
                            if (parent.localName != "annotation" or parent.namespaceURI != XbrlConst.xsd or
                                parent.parentNode.localName != "schema" or parent.parentNode.namespaceURI != XbrlConst.xsd or
                                XmlUtil.previousSiblingElement(parent) != None):
                                val.modelXbrl.error(
                                    _('Schema file {0} annotation/appinfo record must be be behind schema and before import').format(
                                        modelDocument.basename, elt.localName), 
                                    "err", "SBR.NL.2.2.0.12")
                            nextSiblingElement = XmlUtil.nextSiblingElement(parent)
                            if nextSiblingElement and nextSiblingElement.localName != "import":
                                val.modelXbrl.error(
                                    _('Schema file {0} annotation/appinfo record must be followed only by import').format(
                                        modelDocument.basename, elt.localName), 
                                    "err", "SBR.NL.2.2.0.14")
                    if elt.localName == "annotation" and val.validateSBRNL and not XmlUtil.hasChild(elt,XbrlConst.xsd,"appinfo"):
                        val.modelXbrl.error(
                            _('Schema file annotation missing appinfo element must be be behind schema and before import').format(
                                modelDocument.basename), 
                            "err", "SBR.NL.2.2.0.12")

                    if val.validateSBRNL and elt.localName in {"all", "documentation", "any", "anyAttribute", "attributeGroup",
                                                                "complexContent", "extension", "field", "group", "key", "keyref",
                                                                "list", "notation", "redefine", "selector", "unique"}:
                        val.modelXbrl.error(
                            _('Schema file {0} element must not be used "xs:{1}"').format(
                                modelDocument.basename, elt.localName), 
                            "err", "SBR.NL.2.2.11.{0:02}".format({"all":1, "documentation":2, "any":3, "anyAttribute":4, "attributeGroup":7,
                                                                  "complexContent":10, "extension":12, "field":13, "group":14, "key":15, "keyref":16,
                                                                  "list":17, "notation":18, "redefine":20, "selector":22, "unique":23}[elt.localName]))
                # check schema roleTypes        
                if elt.localName in ("roleType","arcroleType") and elt.namespaceURI == XbrlConst.link:
                    uriAttr, xbrlSection, roleTypes, localRoleTypes = {
                           "roleType":("roleURI","5.1.3",val.modelXbrl.roleTypes, val.schemaRoleTypes), 
                           "arcroleType":("arcroleURI","5.1.4",val.modelXbrl.arcroleTypes, val.schemaArcroleTypes)
                           }[elt.localName]
                    if not parent.localName == "appinfo" and parent.namespaceURI == XbrlConst.xsd:
                        val.modelXbrl.error(
                            _("Taxonomy {0} link:{1} not child of xsd:appinfo").format(
                                  modelDocument.basename, elt.localName),
                            "err", "xbrl.{0}:{1}Appinfo".format(xbrlSection,elt.localName))
                    else: # parent is appinfo, element IS in the right location
                        roleURI = elt.getAttribute(uriAttr)
                        if not UrlUtil.isValid(roleURI):
                            val.modelXbrl.error(
                                _("Taxonomy {0} {1} missing or invalid {2}").format(
                                      modelDocument.basename, elt.localName, uriAttr),
                                "err", "xbrl.{0}:{1}Missing".format(xbrlSection,uriAttr))
                        if roleURI in localRoleTypes:
                            val.modelXbrl.error(
                                _("Taxonomy {0} {1} duplicate {2} {3}").format(
                                      modelDocument.basename, elt.localName, uriAttr, roleURI),
                                "err", "xbrl.{0}:{1}Duplicate".format(xbrlSection,elt.localName))
                        else:
                            localRoleTypes[roleURI] = elt
                        for otherRoleType in roleTypes[roleURI]:
                            if elt != otherRoleType.element and not XbrlUtil.sEqual(val.modelXbrl, elt, otherRoleType.element):
                                val.modelXbrl.error(
                                    _("Taxonomy {0} {1} {2} not s-equal in {3}").format(
                                          modelDocument.basename, elt.localName, roleURI,
                                          otherRoleType.modelDocument.basename),
                                    "err", "xbrl.{0}:{1}s-inequality".format(xbrlSection,elt.localName))
                        if elt.localName == "arcroleType":
                            if elt.getAttribute("cyclesAllowed") not in ("any", "undirected", "none"):
                                val.modelXbrl.error(
                                    _("Taxonomy {0} {1} {2} invalid cyclesAllowed").format(
                                          modelDocument.basename, elt.localName, roleURI),
                                    "err", "xbrl.{0}:{1}CyclesAllowed".format(xbrlSection,elt.localName))
                            if val.validateSBRNL:
                                val.modelXbrl.error(_('Schema file {0} arcroleType is not allowed {1}').format(
                                        modelDocument.basename, roleURI), 
                                    "err", "SBR.NL.2.2.4.01")
                        else: # roleType
                            if val.validateSBRNL:
                                roleTypeModelObject = modelDocument.idObjects.get(elt.getAttribute("id"))
                                if roleTypeModelObject is not None and not roleTypeModelObject.genLabel(lang="nl"):
                                    val.modelXbrl.error(_('Schema file {0} roleType {1} must have a label in lang "nl"').format(
                                            modelDocument.basename, roleURI), 
                                        "err", "SBR.NL.2.3.8.05")
                    # check for used on duplications
                    usedOns = set()
                    for usedOn in elt.getElementsByTagNameNS(XbrlConst.link, "usedOn"):
                        qName = qname(usedOn, XmlUtil.text(usedOn))
                        if qName not in usedOns:
                            usedOns.add(qName)
                        else:
                            val.modelXbrl.error(
                                _("Taxonomy {0} {1} {2} usedOn {3} on has s-equal duplicate").format(
                                      modelDocument.basename, elt.localName, roleURI,
                                      qName),
                                "err", "xbrl.{0}:{1}s-inequality".format(xbrlSection,elt.localName))
                        if val.validateSBRNL:
                            val.valUsedPrefixes.add(qName.prefix)
                            if qName == XbrlConst.qnLinkCalculationLink:
                                val.modelXbrl.error(
                                    _("Taxonomy {0} {1} {2} usedOn must not be link:calculationLink").format(
                                          modelDocument.basename, parent.tagName, qName), 
                                    "err", "SBR.NL.2.2.3.01")
            elif modelDocument.type == ModelDocument.Type.LINKBASE:
                if val.validateSBRNL and not elt.prefix:
                        val.modelXbrl.error(_('Linkbase file {0} element is not prefixed: "{1}"').format(
                                modelDocument.basename, elt.localName), 
                            "err", "SBR.NL.2.3.0.06")
            # check of roleRefs when parent is linkbase or instance element
            if elt.localName in ("roleRef","arcroleRef") and elt.namespaceURI == XbrlConst.link:
                uriAttr, xbrlSection, roleTypeDefs, refs = {
                       "roleRef":("roleURI","3.5.2.4",val.modelXbrl.roleTypes,val.roleRefURIs), 
                       "arcroleRef":("arcroleURI","3.5.2.5",val.modelXbrl.arcroleTypes,val.arcroleRefURIs)
                       }[elt.localName]
                if parentIsAppinfo:
                    pass    #ignore roleTypes in appinfo (test case 160 v05)
                elif not (parentIsLinkbase or isInstance):
                    val.modelXbrl.error(
                        _("Xbrl file {0} link:{1} not child of link:linkbase or xbrli:instance").format(
                              modelDocument.basename, elt.localName),
                        "err", "xbrl.{0}:{1}Location".format(xbrlSection,elt.localName))
                else: # parent is linkbase or instance, element IS in the right location

                    # check for duplicate roleRefs when parent is linkbase or instance element
                    refUri = elt.getAttribute(uriAttr)
                    hrefAttr = elt.getAttributeNS(XbrlConst.xlink, "href")
                    hrefUri, hrefId = UrlUtil.splitDecodeFragment(hrefAttr)
                    if refUri == "":
                        val.modelXbrl.error(
                            _("Xbrl file {0} {1} {3} missing").format(
                                  modelDocument.basename,
                                  elt.localName, 
                                  refUri), 
                            "err", "xbrl.3.5.2.4.5:{0}Missing".format(elt.localName))
                    elif refUri in refs:
                        val.modelXbrl.error(
                            _("Xbrl file {0} {1} is duplicated for {2}").format(
                                  modelDocument.basename,
                                  elt.localName, 
                                  refUri), 
                            "err", "xbrl.3.5.2.4.5:{0}Duplicate".format(elt.localName))
                    elif refUri not in roleTypeDefs:
                        val.modelXbrl.error(
                            _("Xbrl file {0} {1} is not defined").format(
                                  modelDocument.basename,
                                  elt.localName, 
                                  refUri), 
                            "err", "xbrl.3.5.2.4.5:{0}NotDefined".format(elt.localName))
                    else:
                        refs[refUri] = hrefUri
                    
                    if val.validateDisclosureSystem:
                        if elt.localName == "arcroleRef":
                            if hrefUri not in val.disclosureSystem.standardTaxonomiesDict:
                                val.modelXbrl.error(
                                    _("Xbrl file {0} arcrole {1} arcroleRef {2} must be a standard taxonomy").format(
                                        modelDocument.basename,
                                        refUri, hrefUri), 
                                    "err", "EFM.6.09.06", "GFM.1.04.06")
                            if val.validateSBRNL:
                                for attrName, errCode in (("arcrole","SBR.NL.2.3.2.05"),("role","SBR.NL.2.3.2.06")):
                                    if elt.hasAttributeNS(XbrlConst.xlink,attrName):
                                        val.modelXbrl.error(
                                            _("Xbrl file {0} arcrole {1} arcroleRef {2} must not have an xlink:{3} attribute").format(
                                                modelDocument.basename, refUri, hrefUri, attrName), 
                                            "err", errCode)
                        elif elt.localName == "roleRef":
                            if val.validateSBRNL:
                                for attrName, errCode in (("arcrole","SBR.NL.2.3.10.09"),("role","SBR.NL.2.3.10.10")):
                                    if elt.hasAttributeNS(XbrlConst.xlink,attrName):
                                        val.modelXbrl.error(
                                            _("Xbrl file {0} role {1} roleRef {2} must not have an xlink:{3} attribute").format(
                                                modelDocument.basename, refUri, hrefUri, attrName), 
                                            "err", errCode)

            # checks for elements in linkbases
            xlinkType = elt.getAttributeNS(XbrlConst.xlink, "type")
            if elt.namespaceURI == XbrlConst.link:
                if elt.localName in ("schemaRef", "linkbaseRef", "roleRef", "arcroleRef"):
                    if xlinkType != "simple":
                        val.modelXbrl.error(
                            _("Taxonomy file {0} element {1} missing slink:type=\"simple\"").format(
                                  modelDocument.basename,
                                  elt.tagName), 
                            "err", "xbrl.3.5.1.1:simpleLinkType")
                    href = elt.getAttributeNS(XbrlConst.xlink,"href")
                    if href == "" or "xpointer(" in href:
                        val.modelXbrl.error(
                            _("Taxonomy file {0} element {1} missing or invalid href").format(
                                  modelDocument.basename,
                                  elt.tagName), 
                            "err", "xbrl.3.5.1.2:simpleLinkHref")
                    for name in ("role", "arcrole"):
                        if elt.hasAttributeNS(XbrlConst.xlink,name) and \
                           elt.getAttributeNS(XbrlConst.xlink,name) == "":
                            val.modelXbrl.error(
                                _("Taxonomy file {0} element {1} has empty {2}").format(
                                      modelDocument.basename,
                                      elt.tagName, name), 
                                "err", "xbrl.3.5.1.2:simpleLink" + name)
                    if elt.localName == "linkbaseRef" and \
                        elt.getAttributeNS(XbrlConst.xlink, "arcrole") != XbrlConst.xlinkLinkbase:
                            val.modelXbrl.error(
                                _("Instance file {0} linkbaseRef missing arcrole").format(
                                      modelDocument.basename), 
                                "err", "xbrl.4.3.3:linkbaseRefArcrole")
                elif elt.localName == "loc":
                    if xlinkType != "locator":
                        val.modelXbrl.error(
                            _("Taxonomy file {0} element {1} missing xlink:type=\"locator\"").format(
                                  modelDocument.basename,
                                  elt.tagName), 
                            "err", "xbrl.3.5.3.7.1:linkLocType")
                    for name, errName in (("href","xbrl.3.5.3.7.2:linkLocHref"),
                                          ("label","xbrl.3.5.3.7.3:linkLocLabel")):
                        if not elt.hasAttributeNS(XbrlConst.xlink,name):
                            val.modelXbrl.error(
                                _("Taxonomy file {0} element {1} missing xlink:{2}").format(
                                      modelDocument.basename,
                                      elt.tagName, name), 
                                "err", errName)
                elif xlinkType == "resource":
                    if elt.localName == "footnote" and not elt.hasAttribute("xml:lang"):
                        val.modelXbrl.error(
                            _("Footnote {0} element missing xml:lang attribute").format(
                                  elt.getAttribute("label")), 
                            "err", "xbrl.4.11.1.2.1:footnoteLang")
                    elif elt.localName == "footnote" and not elt.hasAttribute("xml:lang"):
                        val.modelXbrl.error(
                            _("Label {0} element missing xml:lang attribute").format(
                                  elt.getAttribute("label")), 
                            "err", "xbrl.5.2.2.2.1:labelLang")
                    # TBD: add lang attributes content validation
                        
            xlinkRole = None
            if elt.hasAttributeNS(XbrlConst.xlink,"role"):
                xlinkRole = elt.getAttributeNS(XbrlConst.xlink,"role")
                if xlinkRole == "" and xlinkType == "simple":
                    val.modelXbrl.error(
                        _("XBRL file {0} simple link role {1} is empty").format(
                              modelDocument.basename,
                              xlinkRole), 
                        "err", "xbrl.3.5.1.3:emptySimpleLinkRole")
                elif xlinkRole == "" and xlinkType == "extended" and \
                     XbrlConst.isStandardResourceOrExtLinkElement(elt):
                    val.modelXbrl.error(
                        _("XBRL file {0} standard extended link role {1} is empty").format(
                              modelDocument.basename,
                              xlinkRole), 
                        "err", "xbrl.3.5.3.3:emptyStdExtLinkRole")
                elif not xlinkRole.startswith("http://"):
                    if XbrlConst.isStandardResourceOrExtLinkElement(elt):
                        val.modelXbrl.error(
                            _("XBRL file {0} role {1} is not absolute").format(
                                  modelDocument.basename, xlinkRole), 
                            "err", "xbrl.3.5.2.4:roleNotAbsolute")
                    elif val.isGenericLink(elt):
                        val.modelXbrl.error(
                            _("XBRL file {0} generic link role {1} is not absolute").format(
                                  modelDocument.basename, xlinkRole), 
                            "err", "xbrlgene:nonAbsoluteLinkRoleURI")
                    elif val.isGenericResource(elt):
                        val.modelXbrl.error(
                            _("XBRL file {0} generic resource role {1} is not absolute").format(
                                  modelDocument.basename, xlinkRole), 
                            "err", "xbrlgene:nonAbsoluteResourceRoleURI")
                elif not XbrlConst.isStandardRole(xlinkRole):
                    if xlinkRole not in val.roleRefURIs:
                        if XbrlConst.isStandardResourceOrExtLinkElement(elt):
                            val.modelXbrl.error(
                                _("XBRL file {0} role {1} is missing a roleRef").format(
                                      modelDocument.basename, xlinkRole), 
                                "err", "xbrl.3.5.2.4:missingRoleRef")
                        elif val.isGenericLink(elt):
                            val.modelXbrl.error(
                                _("XBRL file {0} generic link role {1} is missing a roleRef").format(
                                      modelDocument.basename, xlinkRole), 
                                "err", "xbrlgene:missingRoleRefForLinkRole")
                        elif val.isGenericResource(elt):
                            val.modelXbrl.error(
                                _("XBRL file {0} generic resource role {1} is missing a roleRef").format(
                                      modelDocument.basename, xlinkRole), 
                                "err", "xbrlgene:missingRoleRefForResourceRole")
                    modelsRole = val.modelXbrl.roleTypes.get(xlinkRole)
                    if modelsRole is None or len(modelsRole) == 0 or qname(elt) not in modelsRole[0].usedOns:
                        if XbrlConst.isStandardResourceOrExtLinkElement(elt):
                            val.modelXbrl.error(
                                _("XBRL file {0} role {1} missing usedOn for {2}").format(
                                      modelDocument.basename, xlinkRole, elt.tagName), 
                                "err", "xbrl.5.1.3.4:custRoleUsedOn")
                        elif val.isGenericLink(elt):
                            val.modelXbrl.error(
                                _("XBRL file {0} generic link role {1} missing usedOn for {2}").format(
                                      modelDocument.basename, xlinkRole, elt.tagName), 
                                "err", "xbrlgene:missingLinkRoleUsedOnValue")
                        elif val.isGenericResource(elt):
                            val.modelXbrl.error(
                                _("XBRL file {0} generic resource role {1} missing usedOn for {2}").format(
                                      modelDocument.basename, xlinkRole, elt.tagName), 
                                "err", "xbrlgene:missingResourceRoleUsedOnValue")
            elif xlinkType == "extended" and val.validateSBRNL: # no @role on extended link
                val.modelXbrl.error(
                    _("Xbrl file {0} extended link {1} must have an xlink:role attribute").format(
                        modelDocument.basename, elt.tagName), 
                    "err", "SBR.NL.2.3.10.13")
            if elt.hasAttributeNS(XbrlConst.xlink,"arcrole"):
                arcrole = elt.getAttributeNS(XbrlConst.xlink,"arcrole")
                if arcrole == "" and \
                    elt.getAttributeNS(XbrlConst.xlink,"type") == "simple":
                    val.modelXbrl.error(
                        _("XBRL file {0} arcrole {1} is empty").format(
                              modelDocument.basename,
                              arcrole), 
                        "err", "xbrl.3.5.1.4:emptyXlinkArcrole")
                elif not arcrole.startswith("http://"):
                    if XbrlConst.isStandardArcInExtLinkElement(elt):
                        val.modelXbrl.error(
                            _("XBRL file {0} arcrole {1} is not absolute").format(
                                  modelDocument.basename, arcrole), 
                            "err", "xbrl.3.5.2.5:arcroleNotAbsolute")
                    elif val.isGenericArc(elt):
                        val.modelXbrl.error(
                            _("XBRL file {0} generic arc arcrole {1} is not absolute").format(
                                  modelDocument.basename, arcrole), 
                            "err", "xbrlgene:nonAbsoluteArcRoleURI")
                elif not XbrlConst.isStandardArcrole(arcrole):
                    if arcrole not in val.arcroleRefURIs:
                        if XbrlConst.isStandardArcInExtLinkElement(elt):
                            val.modelXbrl.error(
                                _("XBRL file {0} arcrole {1} is missing an arcroleRef").format(
                                      modelDocument.basename, arcrole), 
                                "err", "xbrl.3.5.2.5:missingArcroleRef")
                        elif val.isGenericArc(elt):
                            val.modelXbrl.error(
                                _("XBRL file {0} generic arc arcrole {1} is missing an arcroleRef").format(
                                      modelDocument.basename, arcrole), 
                                "err", "xbrlgene:missingRoleRefForArcRole")
                    modelsRole = val.modelXbrl.arcroleTypes.get(arcrole)
                    if modelsRole is None or len(modelsRole) == 0 or qname(elt) not in modelsRole[0].usedOns:
                        if XbrlConst.isStandardArcInExtLinkElement(elt):
                            val.modelXbrl.error(
                                _("XBRL file {0} arcrole {1} missing usedOn for {2}").format(
                                      modelDocument.basename, arcrole, elt.tagName), 
                                "err", "xbrl.5.1.4.5:custArcroleUsedOn")
                        elif val.isGenericArc(elt):
                            val.modelXbrl.error(
                                _("XBRL file {0} generic arc arcrole {1} missing usedOn for {2}").format(
                                      modelDocument.basename, arcrole, elt.tagName), 
                                "err", "xbrlgene:missingArcRoleUsedOnValue")
                elif XbrlConst.isStandardArcElement(elt):
                    if XbrlConst.standardArcroleArcElement(arcrole) != elt.localName:
                        val.modelXbrl.error(
                            _("XBRL file {0} standard arcrole {1} used on wrong arc {2}").format(
                                  modelDocument.basename,
                                  arcrole, elt.tagName), 
                            "err", "xbrl.5.1.4.5:custArcroleUsedOn")

            #check resources
            if parentXlinkType == "extended":
                if elt.localName not in ("documentation", "title") and \
                    xlinkType not in ("arc", "locator", "resource"):
                    val.modelXbrl.error(
                         _("XBRL file {0} element {1} appears to be a resource missing xlink:type=\"resource\"").format(
                          modelDocument.basename,
                          elt.tagName), 
                    "err", "xbrl.3.5.3.8.1:resourceType")
            if xlinkType == "resource":
                if not elt.hasAttributeNS(XbrlConst.xlink,"label"):
                    val.modelXbrl.error(
                        _("Taxonomy file {0} element {1} missing xlink:label").format(
                              modelDocument.basename,
                              elt.tagName), 
                        "err", "xbrl.3.5.3.8.2:resourceLabel")
            elif xlinkType == "arc":
                for name, errName in (("from", "xbrl.3.5.3.9.2:arcFrom"),
                                      ("to", "xbrl.3.5.3.9.2:arcTo")):
                    if not elt.hasAttributeNS(XbrlConst.xlink, name):
                        val.modelXbrl.error(
                            _("Taxonomy file {0} element {1} missing xlink:{2}").format(
                                  modelDocument.basename,
                                  elt.tagName, name), 
                            "err", errName)
                if val.modelXbrl.hasXDT and elt.hasAttributeNS(XbrlConst.xbrldt,"targetRole"):
                    targetRole = elt.getAttributeNS(XbrlConst.xbrldt,"targetRole")
                    if not XbrlConst.isStandardRole(targetRole) and \
                       targetRole not in val.roleRefURIs:
                        val.modelXbrl.error(
                            _("XBRL file {0} targetRole {1} is missing a roleRef").format(
                                  modelDocument.basename,
                                  targetRole), 
                            "err", "xbrldte:TargetRoleNotResolvedError")
                val.containsRelationship = True
            if val.validateXmlLang and elt.hasAttribute("xml:lang"):
                if not val.disclosureSystem.xmlLangPattern.search(elt.getAttribute("xml:lang")):
                    val.modelXbrl.error(
                        _("XBRL file {0} element {1} {2} has unauthorized xml:lang='{2}'").format(
                              modelDocument.basename, elt.tagName, elt.getAttributeNS(XbrlConst.xlink,"label"),
                              elt.getAttribute("xml:lang")),
                        "err", "SBR.NL.2.3.8.01,02")
                 
            if isInstance:
                if elt.namespaceURI == XbrlConst.xbrli:
                    expectedSequence = instanceSequence.get(elt.localName,9)
                else:
                    expectedSequence = 9    #itdms last
                if instanceOrder > expectedSequence:
                    val.modelXbrl.error(
                        _("Instance file {0} element {1} out of order").format(
                              modelDocument.basename,
                              elt.tagName), 
                        "err", "xbrl.4.7:instanceElementOrder")
                else:
                    instanceOrder = expectedSequence
                    
            if modelDocument.type == ModelDocument.Type.INLINEXBRL:
                if elt.namespaceURI == XbrlConst.ixbrl and val.validateGFM:
                    if elt.localName == "footnote":
                        if elt.getAttribute("arcrole") != XbrlConst.factFootnote:
                            # must be in a nonDisplay div
                            inNondisplayDiv = False
                            ancestor = elt.parentNode
                            while ancestor.nodeType == 1:
                                if (ancestor.localName == "div" and ancestor.namespaceURI == XbrlConst.xhtml and 
                                    ancestor.getAttribute("style") == "display:none"):
                                    inNondisplayDiv = True
                                    break
                                ancestor = ancestor.parentNode
                            if not inNondisplayDiv:
                                val.modelXbrl.error(
                                    _("Inline XBRL footnote {0} must be in non-displayable div due to arcrole {1}").format(
                                          elt.getAttribute("footnoteID"), elt.getAttribute("arcrole")),
                                    "err", "EFM.N/A", "GFM:1.10.16")
                        id = elt.getAttribute("footnoteID")
                        if id not in val.footnoteRefs and XmlUtil.innerText(elt):
                            val.modelXbrl.error(
                                _("Inline XBRL non-empty footnote {0} is not referenced by any fact").format(
                                      elt.getAttribute("footnoteID")),
                                "err", "EFM.N/A", "GFM:1.10.15")
                            
                        if not elt.getAttribute("xml:lang"):
                            val.modelXbrl.error(
                                _("Inline XBRL footnote {0} is missing an xml:lang attribute").format(
                                      elt.getAttribute("footnoteID")),
                                "err", "EFM.N/A", "GFM:1.10.13")
                        
            if val.validateDisclosureSystem:
                if xlinkType == "extended":
                    if not xlinkRole or xlinkRole == "":
                        val.modelXbrl.error(
                            _("XBRL file {0} {1} is missing an xlink:role").format(
                                  modelDocument.basename,
                                  elt.tagName), 
                            "err", "EFM.6.09.04", "GFM.1.04.04")
                    eltNsName = (elt.namespaceURI,elt.localName)
                    if not val.extendedElementName:
                        val.extendedElementName = eltNsName
                    elif val.extendedElementName != eltNsName:
                        val.modelXbrl.error(
                            _("XBRL file {0} extended element {1} must be the same as {2}").format(
                                  modelDocument.basename,
                                  eltNsName, val.extendedElementName), 
                            "err", "EFM.6.09.07", "GFM:1.04.07", "SBR.NL.2.3.0.11")
                if xlinkType == "resource":
                    if not xlinkRole or xlinkRole == "":
                        val.modelXbrl.error(
                            _("XBRL file {0} {1} is missing an xlink:role").format(
                                  modelDocument.basename,
                                  elt.tagName), 
                            "err", "EFM.6.09.04", "GFM.1.04.04")
                    elif not (XbrlConst.isStandardRole(xlinkRole) or 
                              val.roleRefURIs.get(xlinkRole) in val.disclosureSystem.standardTaxonomiesDict):
                        val.modelXbrl.error(
                            _("XBRL file {0} resource {1} role {2} is not a standard taxonomy role").format(
                                  modelDocument.basename,
                                  elt.getAttributeNS(XbrlConst.xlink,"label"),
                                  xlinkRole), 
                            "err", "EFM.6.09.05", "GFM.1.04.05", "SBR.NL.2.3.10.14")
                    if elt.localName == "reference" and val.validateSBRNL:
                        for child in elt.getElementsByTagNameNS("*","*"):
                            if child.namespaceURI != "http://www.xbrl.org/2006/ref":
                                val.modelXbrl.error(
                                    _("XBRL file {0} reference {1} has unauthorized part element {2}").format(
                                          modelDocument.basename,
                                          elt.getAttributeNS(XbrlConst.xlink,"label"),
                                          qname(child)),
                                    "err", "SBR.NL.2.3.3.01")
                        id = elt.getAttribute("id")
                        if not id:
                            val.modelXbrl.error(
                                _("XBRL file {0} reference {1} is missing an id attribute").format(
                                      modelDocument.basename,
                                      elt.getAttributeNS(XbrlConst.xlink,"label")), 
                                "err", "SBR.NL.2.3.3.02")
                        elif id in val.DTSreferenceResourceIDs:
                            val.modelXbrl.error(
                                _("XBRL file {0} reference {1} has duplicated id {2} also in linkbase {1}").format(
                                      modelDocument.basename,
                                      elt.getAttributeNS(XbrlConst.xlink,"label"),
                                      val.DTSreferenceResourceIDs[id]), 
                                "err", "SBR.NL.2.3.3.03")
                        else:
                            val.DTSreferenceResourceIDs[id] = modelDocument.basename
                if xlinkType == "arc":
                    if elt.hasAttribute("priority"):
                        priority = elt.getAttribute("priority")
                        try:
                            if int(priority) >= 10:
                                val.modelXbrl.error(
                                    _("XBRL file {0} arc from {1} to {2} priority {3} must be less than 10").format(
                                          modelDocument.basename,
                                          elt.getAttributeNS(XbrlConst.xlink,"from"),
                                          elt.getAttributeNS(XbrlConst.xlink,"to"),
                                          priority), 
                                    "err", "EFM.6.09.09", "GFM.1.04.08")
                        except (ValueError) :
                            val.modelXbrl.error(
                                _("XBRL file {0} arc from {1} to {2} priority {3} is not an integer").format(
                                      modelDocument.basename,
                                      elt.getAttributeNS(XbrlConst.xlink,"from"),
                                      elt.getAttributeNS(XbrlConst.xlink,"to"),
                                      priority), 
                                "err", "EFM.6.09.09", "GFM.1.04.08")
                    if elt.namespaceURI == XbrlConst.link:
                        if elt.localName == "presentationArc" and elt.getAttribute("order") == "":
                            val.modelXbrl.error(
                                _("XBRL file {0} presentationArc from {1} to {2} must have an order").format(
                                      modelDocument.basename,
                                      elt.getAttributeNS(XbrlConst.xlink,"from"),
                                      elt.getAttributeNS(XbrlConst.xlink,"to")), 
                                "err", "EFM.6.12.01", "GFM.1.06.01", "SBR.NL.2.3.4.04")
                        elif elt.localName == "calculationArc":
                            if elt.getAttribute("order") == "":
                                val.modelXbrl.error(
                                    _("XBRL file {0} calculationArc from {1} to {2} must have an order").format(
                                          modelDocument.basename,
                                          elt.getAttributeNS(XbrlConst.xlink,"from"),
                                          elt.getAttributeNS(XbrlConst.xlink,"to")), 
                                    "err", "EFM.6.14.01", "GFM.1.07.01")
                            try:
                                weight = float(elt.getAttribute("weight"))
                                if not weight in (1, -1):
                                    val.modelXbrl.error(
                                        _("XBRL file {0} calculationArc from {1} to {2} weight {3} must be 1 or -1").format(
                                              modelDocument.basename,
                                              elt.getAttributeNS(XbrlConst.xlink,"from"),
                                              elt.getAttributeNS(XbrlConst.xlink,"to"),
                                              weight), 
                                        "err", "EFM.6.14.02", "GFM.1.07.02")
                            except ValueError:
                                val.modelXbrl.error(
                                    _("XBRL file {0} calculationArc from {1} to {2} must have an weight").format(
                                          modelDocument.basename,
                                          elt.getAttributeNS(XbrlConst.xlink,"from"),
                                          elt.getAttributeNS(XbrlConst.xlink,"to")), 
                                    "err", "EFM.6.14.02", "GFM.1.07.02")
                        elif elt.localName == "definitionArc":
                            if elt.getAttribute("order") == "":
                                val.modelXbrl.error(
                                    _("XBRL file {0} definitionnArc from {1} to {2} must have an order").format(
                                          modelDocument.basename,
                                          elt.getAttributeNS(XbrlConst.xlink,"from"),
                                          elt.getAttributeNS(XbrlConst.xlink,"to")), 
                                    "err", "EFM.6.16.01", "GFM.1.08.01")
                            if val.validateSBRNL and arcrole in (
                                  XbrlConst.essenceAlias, XbrlConst.similarTuples, XbrlConst.requiresElement):
                                val.modelXbrl.error(
                                    _("XBRL file {0} definitionArc from {1} to {2} has unauthorized arcrole {3}").format(
                                          modelDocument.basename,
                                          elt.getAttributeNS(XbrlConst.xlink,"from"),
                                          elt.getAttributeNS(XbrlConst.xlink,"to"),
                                          arcrole), 
                                    "err", "SBR.NL.2.3.2.02-04")
                        elif elt.localName == "referenceArc" and val.validateSBRNL:
                            if elt.getAttribute("order") != "":
                                val.modelXbrl.error(
                                    _("XBRL file {0} referenceArc from {1} to {2} has an order").format(
                                          modelDocument.basename,
                                          elt.getAttributeNS(XbrlConst.xlink,"from"),
                                          elt.getAttributeNS(XbrlConst.xlink,"to")), 
                                    "err", "SBR.NL.2.3.3.05")
                if val.validateSBRNL:
                    if not elt.prefix:
                            val.modelXbrl.error(_('Schema file {0} element is not prefixed: "{1}"').format(
                                    modelDocument.basename, elt.localName), 
                                "err", "SBR.NL.2.2.0.06")
                    # check attributes for prefixes and xmlns
                    val.valUsedPrefixes.add(elt.prefix)
                    for i in range(len(elt.attributes)):
                        attribute = elt.attributes.item(i)
                        prefix = attribute.prefix
                        if attribute.name == "xmlns" or prefix == "xmlns":
                            if parent.nodeType == 1: # not for linkbase or schema, which are parented by document element
                                val.modelXbrl.error(
                                    _("XBRL file {0} {1} element {2} must not have {3}").format(
                                          modelDocument.basename,
                                          "schema" if isSchema else "linkbase" ,
                                          elt.tagName, attribute.name), 
                                    "err", "SBR.NL.2.2.0.19" if isSchema else "SBR.NL.2.3.1.01")
                        else: # not an xmlns
                            if prefix:  # don't add None for unprefixed attributes
                                val.valUsedPrefixes.add(prefix)
                                # check for disalloed prefixes
                                if attribute.namespaceURI not in (XbrlConst.xbrli, XbrlConst.xbrldt):
                                    val.modelXbrl.error(
                                        _("XBRL file {0} {1} element {2} must not have {3}").format(
                                              modelDocument.basename,
                                              "schema" if isSchema else "linkbase" ,
                                              elt.tagName, attribute.name), 
                                        "err", "SBR.NL.2.2.0.20")
                            if isSchema and attribute.name in ("base", "ref", "substitutionGroup", "type"):
                                valuePrefix, sep, valueName = attribute.value.partition(":")
                                if sep:
                                    val.valUsedPrefixes.add(valuePrefix)
                            
                    if elt.localName == "roleType" and not elt.hasAttribute("id"): 
                        val.modelXbrl.error(
                            _("XBRL file {0} roleType {1} missing id attribute").format(
                                  modelDocument.basename,
                                  elt.getAttribute("roleURI")), 
                            "err", "SBR.NL.2.3.10.11")
                    elif elt.localName == "loc" and elt.hasAttributeNS(XbrlConst.xlink,"role"): 
                        val.modelXbrl.error(
                            _("XBRL file {0} loc {1} has unauthorized role attribute").format(
                                  modelDocument.basename,
                                  elt.getAttributeNS(XbrlConst.xlink,"label")), 
                            "err", "SBR.NL.2.3.10.08")
                    elif elt.localName == "title": 
                        val.modelXbrl.error(
                            _("XBRL file {0} title element must not be used: {1}").format(
                                  modelDocument.basename,
                                  XmlUtil.text(elt)), 
                            "err", "SBR.NL.2.3.10.12")
                    if elt.localName == "linkbase":
                        for attrNS, attrName, errCode in ((None, "id", "SBR.NL.2.3.10.04"),
                                                          (XbrlConst.xsi,"nil", "SBR.NL.2.3.10.05"),
                                                          (XbrlConst.xsi,"noNamespaceSchemaLocation", "SBR.NL.2.3.10.06"),
                                                          (XbrlConst.xsi,"type", "SBR.NL.2.3.10.07")):
                            if elt.hasAttributeNS(attrNS, attrName): 
                                val.modelXbrl.error(
                                    _("XBRL file {0} linkbase element must not have element {1}").format(
                                          modelDocument.basename, attrName), 
                                    "err", errCode)
                    for attrNS, attrName, errCode in ((XbrlConst.xlink,"actuate", "SBR.NL.2.3.10.01"),
                                                      (XbrlConst.xlink,"show", "SBR.NL.2.3.10.02"),
                                                      (XbrlConst.xlink,"title", "SBR.NL.2.3.10.03")):
                        if elt.hasAttributeNS(attrNS, attrName): 
                            val.modelXbrl.error(
                                _("XBRL file {0} linkbase element {1} must not have attribute xlink:{2}").format(
                                      modelDocument.basename, elt.tagName, attrName), 
                                "err", errCode)

            checkElements(val, modelDocument, elt)
        elif elt.nodeType == 8: # comment node
            if val.validateSBRNL:
                if modelDocument.xmlRootElement.previousSibling != elt:
                    val.modelXbrl.error(_('{0} file {1} must have only one comment node before schema element: "{2}"').format(
                            modelDocument.gettype().title(), modelDocument.basename, elt.data), 
                        "err", "SBR.NL.2.2.0.05")

    # dereference at end of processing children of instance linkbase
    if isInstance or parentIsLinkbase:
        val.roleRefURIs = {}
        val.arcroleRefURIs = {}


