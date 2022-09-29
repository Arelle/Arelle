'''
See COPYRIGHT.md for copyright information.
'''
from arelle import ModelDocument, XmlUtil, XbrlConst
from arelle.ModelDtsObject import ModelConcept, ModelLocator, ModelResource, ModelType
from arelle.ModelValue import qname
from arelle.ModelObject import ModelObject, ModelComment
from arelle.ValidateXbrlDTS import arcFromConceptQname, arcToConceptQname
from arelle import XmlValidate
from lxml import etree
import regex as re

xsd1_1datatypes = {qname(XbrlConst.xsd,'anyAtomicType'), qname(XbrlConst.xsd,'yearMonthDuration'), qname(XbrlConst.xsd,'dayTimeDuration'), qname(XbrlConst.xsd,'dateTimeStamp'), qname(XbrlConst.xsd,'precisionDecimal')}

def checkDTSdocument(val, modelDocument, isFilingDocument):
    if not isFilingDocument:
        return  # not a filing's extension document

    val.valUsedPrefixes = set()
    val.referencedNamespaces = set()
    val.substititutionGroupQname = {}

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

        if isSchema:
            for elt in modelDocument.xmlRootElement.iter(tag="{http://www.w3.org/2001/XMLSchema}*"):
                parent = elt.getparent()
                parentIsSchema = parent is not None and parent.tag == "{http://www.w3.org/2001/XMLSchema}schema"
                localName = elt.localName
                if localName == "schema":
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
                else:
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
                    elif localName == "appinfo":
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
                    elif localName == "annotation":
                        val.annotationsCount += 1
                        if not XmlUtil.hasChild(elt,XbrlConst.xsd,"appinfo"):
                            val.modelXbrl.error("SBR.NL.2.2.0.12",
                                _('Schema file annotation missing appinfo element must be be behind schema and before import'),
                                modelObject=elt)
                    elif localName in {"all", "documentation", "any", "anyAttribute", "attributeGroup",
                                       # comment out per R.H. 2011-11-16 "complexContent", "complexType", "extension",
                                       "field", "group", "key", "keyref",
                                       "list", "notation", "redefine", "selector", "unique"}:
                        val.modelXbrl.error("SBR.NL.2.2.11.{0:02}".format({"all":1, "documentation":2, "any":3, "anyAttribute":4, "attributeGroup":7,
                                                                  "complexContent":10, "complexType":11, "extension":12, "field":13, "group":14, "key":15, "keyref":16,
                                                                  "list":17, "notation":18, "redefine":20, "selector":22, "unique":23}[localName]),
                            _('Schema file element must not be used "%(element)s"'),
                            modelObject=elt, element=elt.qname,
                            messageCodes=("SBR.NL.2.2.11.01", "SBR.NL.2.2.11.02", "SBR.NL.2.2.11.03", "SBR.NL.2.2.11.04", "SBR.NL.2.2.11.07", "SBR.NL.2.2.11.10", "SBR.NL.2.2.11.11", "SBR.NL.2.2.11.12",
                                          "SBR.NL.2.2.11.13", "SBR.NL.2.2.11.14", "SBR.NL.2.2.11.15", "SBR.NL.2.2.11.16", "SBR.NL.2.2.11.17", "SBR.NL.2.2.11.18", "SBR.NL.2.2.11.20", "SBR.NL.2.2.11.22", "SBR.NL.2.2.11.23"))
                if not elt.prefix:
                        val.modelXbrl.error("SBR.NL.2.2.0.06",
                                'Schema element is not prefixed: "%(element)s"',
                                modelObject=elt, element=elt.qname)
            for elt in modelDocument.xmlRootElement.iter(tag="{http://www.xbrl.org/2003/linkbase}*"):
                if elt.localName in ("roleType","arcroleType"):
                    uriAttr = {"roleType":"roleURI",
                               "arcroleType":"arcroleURI"}[elt.localName]
                    XmlValidate.validate(val.modelXbrl, elt) # validate [arc]roleType
                    roleURI = elt.get(uriAttr)
                    if elt.localName == "arcroleType":
                        val.modelXbrl.error("SBR.NL.2.2.4.01",
                                _('ArcroleType is not allowed %(roleURI)s'),
                                modelObject=elt, roleURI=roleURI)
                    else: # roleType
                        roleTypeModelObject = modelDocument.idObjects.get(elt.get("id"))
                        if roleTypeModelObject is not None and not roleTypeModelObject.genLabel(lang="nl"):
                            val.modelXbrl.error("SBR.NL.2.3.8.05",
                                _('RoleType %(roleURI)s must have a label in lang "nl"'),
                                modelObject=elt, roleURI=roleURI)
                    # check for used on duplications
                    usedOns = set()
                    for usedOn in elt.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}usedOn"):
                        if isinstance(usedOn,ModelObject):
                            qName = qname(usedOn, XmlUtil.text(usedOn))
                            val.valUsedPrefixes.add(qName.prefix)
                            if qName == XbrlConst.qnLinkCalculationLink:
                                val.modelXbrl.error("SBR.NL.2.2.3.01",
                                    _("%(element)s usedOn must not be link:calculationLink"),
                                    modelObject=elt, element=elt.qname, value=qName)
                            if elt.localName == "roleType" and qName in XbrlConst.standardExtLinkQnames:
                                if not any((key[1] == roleURI  and key[2] == qName)
                                           for key in val.modelXbrl.baseSets.keys()):
                                    val.modelXbrl.error("SBR.NL.2.2.3.02",
                                        _("%(element)s usedOn %(usedOn)s not addressed for role %(role)s"),
                                        modelObject=elt, element=elt.qname, usedOn=qName, role=roleURI)
            if val.annotationsCount > 1:
                modelXbrl.error("SBR.NL.2.2.0.22",
                    _('Schema has %(annotationsCount)s xs:annotation elements, only 1 allowed'),
                    modelObject=modelDocument, annotationsCount=val.annotationsCount)
    if modelDocument.type == ModelDocument.Type.LINKBASE:
        for elt in modelDocument.xmlRootElement.iter():
            if isinstance(elt, ModelObject) and not elt.prefix:
                val.modelXbrl.error("SBR.NL.2.2.0.06",
                    _('Linkbase element is not prefixed: "%(element)s"'),
                    modelObject=elt, element=elt.qname)
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

    for elt in modelDocument.xmlRootElement.iter():
        if isinstance(elt, ModelObject):
            xlinkType = elt.get("{http://www.w3.org/1999/xlink}type")
            xlinkRole = elt.get("{http://www.w3.org/1999/xlink}role")
            if elt.tag in ("{http://www.xbrl.org/2003/linkbase}arcroleRef", "{http://www.xbrl.org/2003/linkbase}roleRef"):
                if elt.tag =="{http://www.xbrl.org/2003/linkbase}arcroleRef": # corrected merge of pre-plugin code per LOGIUS
                    for attrName, errCode in (("{http://www.w3.org/1999/xlink}arcrole","SBR.NL.2.3.2.05"),("{http://www.w3.org/1999/xlink}role","SBR.NL.2.3.2.06")):
                        if elt.get(attrName):
                            val.modelXbrl.error(errCode,
                                _("Arcrole %(refURI)s arcroleRef %(xlinkHref)s must not have an %(attribute)s attribute"),
                                modelObject=elt, refURI=elt.get("arcroleURI"),
                                xlinkHref=elt.get("{http://www.w3.org/1999/xlink}href"), attribute=attrName,
                                messageCodes=("SBR.NL.2.3.2.05", "SBR.NL.2.3.2.06"))
                elif elt.tag == "{http://www.xbrl.org/2003/linkbase}roleRef": # corrected merge of pre-plugin code per LOGIUS
                    for attrName, errCode in (("{http://www.w3.org/1999/xlink}arcrole","SBR.NL.2.3.10.09"),("{http://www.w3.org/1999/xlink}role","SBR.NL.2.3.10.10")):
                        if elt.get(attrName):
                            val.modelXbrl.error(errCode,
                                _("Role %(refURI)s roleRef %(xlinkHref)s must not have an %(attribute)s attribute"),
                                modelObject=elt, refURI=elt.get("roleURI"),
                                xlinkHref=elt.get("{http://www.w3.org/1999/xlink}href"), attribute=attrName,
                                messageCodes=("SBR.NL.2.3.10.09", "SBR.NL.2.3.10.10"))
                if not xlinkType:
                    val.modelXbrl.error("SBR.NL.2.3.0.01",
                        _("Xlink 1.1 simple type is not allowed (xlink:type is missing)"),
                        modelObject=elt)
            if xlinkType == "resource":
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
                # corrected merge of pre-plugin code per LOGIUS
                if not XbrlConst.isStandardRole(xlinkRole):
                    modelsRole = val.modelXbrl.roleTypes.get(xlinkRole)
                    if (modelsRole is None or len(modelsRole) == 0 or
                        modelsRole[0].modelDocument.targetNamespace not in val.disclosureSystem.standardTaxonomiesDict):
                        val.modelXbrl.error("SBR.NL.2.3.10.14",
                            _("Resource %(xlinkLabel)s role %(role)s is not a standard taxonomy role"),
                            modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"), role=xlinkRole, element=elt.qname,
                            roleDefinition=val.modelXbrl.roleTypeDefinition(xlinkRole))
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
            elif xlinkType == "extended":
                if xlinkRole is None: # no @role on extended link
                    val.modelXbrl.error("SBR.NL.2.3.10.13",
                        _("Extended link %(element)s must have an xlink:role attribute"),
                        modelObject=elt, element=elt.elementQname)
                if not val.extendedElementName:
                    val.extendedElementName = elt.qname
                elif val.extendedElementName != elt.qname:
                    val.modelXbrl.error("SBR.NL.2.3.0.11",
                        _("Extended element %(element)s must be the same as %(element2)s"),
                        modelObject=elt, element=elt.qname, element2=val.extendedElementName)
            elif xlinkType == "locator":
                if elt.qname != XbrlConst.qnLinkLoc:
                    val.modelXbrl.error("SBR.NL.2.3.0.11",
                        _("Loc element %(element)s may not be contained in a linkbase with %(element2)s"),
                        modelObject=elt, element=elt.qname, element2=val.extendedElementName)
            elif xlinkType == "arc":
                if elt.namespaceURI == XbrlConst.link:
                    if elt.localName == "presentationArc" and not elt.get("order"):
                        val.modelXbrl.error("SBR.NL.2.3.4.04",
                            _("PresentationArc from %(xlinkFrom)s to %(xlinkTo)s must have an order"),
                            modelObject=elt,
                            xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                            xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                            conceptFrom=arcFromConceptQname(elt),
                            conceptTo=arcToConceptQname(elt))
                if elt.namespaceURI == XbrlConst.link:
                    arcrole = elt.get("{http://www.w3.org/1999/xlink}arcrole")
                    if elt.localName == "definitionArc":
                        if arcrole in (XbrlConst.essenceAlias, XbrlConst.similarTuples, XbrlConst.requiresElement):
                            val.modelXbrl.error({XbrlConst.essenceAlias: "SBR.NL.2.3.2.02",
                                              XbrlConst.similarTuples: "SBR.NL.2.3.2.03",
                                              XbrlConst.requiresElement: "SBR.NL.2.3.2.04"}[arcrole],
                                _("DefinitionArc from %(xlinkFrom)s to %(xlinkTo)s has unauthorized arcrole %(arcrole)s"),
                                modelObject=elt,
                                xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                                arcrole=arcrole,
                                messageCodes=("SBR.NL.2.3.2.02", "SBR.NL.2.3.2.03", "SBR.NL.2.3.2.04"))
                    elif elt.localName == "referenceArc":
                        if elt.get("order"):
                            val.modelXbrl.error("SBR.NL.2.3.3.05",
                                _("ReferenceArc from %(xlinkFrom)s to %(xlinkTo)s has an order"),
                                modelObject=elt,
                                xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"))
                    if elt.get("use") == "prohibited" and elt.getparent().tag in (
                            "{http://www.xbrl.org/2003/linkbase}presentationLink",
                            "{http://www.xbrl.org/2003/linkbase}labelLink",
                            "{http://xbrl.org/2008/generic}link",
                            "{http://www.xbrl.org/2003/linkbase}referenceLink"):
                        val.modelXbrl.error("SBR.NL.2.3.0.10",
                            _("%(arc)s must not contain use='prohibited'"),
                            modelObject=elt, arc=elt.getparent().qname)
                if elt.qname not in {
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
                if elt.qname == XbrlConst.qnLinkLabelArc and elt.get("order"):
                    val.modelXbrl.error("SBR.NL.2.3.8.08",
                        _("labelArc may not be contain order (%(order)s)"),
                        modelObject=elt, order=elt.get("order"))

            xmlLang = elt.get("{http://www.w3.org/XML/1998/namespace}lang")
            if val.validateXmlLang and xmlLang is not None:
                if not val.disclosureSystem.xmlLangPattern.match(xmlLang): # corrected merge of pre-plugin code per LOGIUS
                    val.modelXbrl.error("SBR.NL.2.3.8.01" if xmlLang.startswith('nl') else "SBR.NL.2.3.8.02" if xmlLang.startswith('en') else "arelle:langError",
                        _("Element %(element)s %(xlinkLabel)s has unauthorized xml:lang='%(lang)s'"),
                        modelObject=elt, element=elt.qname,
                        xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"),
                        lang=elt.get("{http://www.w3.org/XML/1998/namespace}lang"),
                        messageCodes=("SBR.NL.2.3.8.01", "SBR.NL.2.3.8.02", "arelle:langError"))
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
        elif isinstance(elt,ModelComment): # comment node
            if elt.itersiblings(preceding=True): # corrected merge of pre-plugin code per LOGIUS
                val.modelXbrl.error("SBR.NL.2.2.0.05" if isSchema else "SBR.NL.2.3.0.05",
                        _('%(fileType)s must have only one comment node before schema element: "%(value)s"'),
                        modelObject=elt, fileType=modelDocument.gettype().title(), value=elt.text,
                        messageCodes=("SBR.NL.2.2.0.05", "SBR.NL.2.3.0.05"))

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
    for modelObject in modelDocument.xmlRootElement.iter():
        if isinstance(modelObject,ModelObject):
            id = modelObject.id
            if id:
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

    if modelDocument.type in (ModelDocument.Type.SCHEMA, ModelDocument.Type.LINKBASE):
        # check namespaces are used
        for prefix, ns in modelDocument.xmlRootElement.nsmap.items():
            if ((prefix not in val.valUsedPrefixes) and
                (modelDocument.type != ModelDocument.Type.SCHEMA or ns != modelDocument.targetNamespace)):
                modelXbrl.error("SBR.NL.2.2.0.11" if modelDocument.type == ModelDocument.Type.SCHEMA else "SBR.NL.2.3.0.08",
                    _('%(docType)s namespace declaration "%(declaration)s" is not used'),
                    modelObject=modelDocument, docType=modelDocument.gettype().title(),
                    declaration=("xmlns" + (":" + prefix if prefix else "") + "=" + ns))

    del val.valUsedPrefixes
