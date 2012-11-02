'''
Created on Oct 05, 2012

@author: Mark V Systems Limited
(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''

from arelle import PluginManager
from arelle import ModelDocument, XbrlConst, XmlUtil
from arelle.ModelDtsObject import ModelConcept, ModelType, ModelLocator, ModelResource
from arelle.ModelFormulaObject import Aspect
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname
import re
from lxml import etree
from collections import defaultdict

def setup(val, modelXbrl):
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
    
def final(val, conceptsUsed):
    # 3.2.4.4 check each using prefix against taxonomy declaring the prefix
    for docs in val.modelXbrl.namespaceDocs.values():
        for doc in docs:
            for prefix, NS in doc.xmlRootElement.nsmap.items():
                if NS in val.namespacePrefix and prefix != val.namespacePrefix[NS]:
                    val.modelXbrl.error("SBR.NL.3.2.4.04",
                        _("The assigned namespace prefix %(assignedPrefix)s for the schema that declares the targetnamespace %(namespace)s, MUST be adhired by all other NT schemas, referencedPrefix: %(referencedPrefix)s"),
                        modelObject=doc.xmlRootElement, namespace=NS, assignedPrefix=val.namespacePrefix.get(NS,''), referencedPrefix=prefix)

    # check non-concept elements that can appear in elements for labels (concepts checked by 
    labelsRelationshipSet = val.modelXbrl.relationshipSet((XbrlConst.conceptLabel,XbrlConst.elementLabel))
    standardXbrlSchmas = _DICT_SET(XbrlConst.standardNamespaceSchemaLocations.values())
    for eltDef in val.modelXbrl.qnameConcepts.values():
        if (not (eltDef.isItem or eltDef.isTuple or eltDef.isLinkPart) and
            eltDef.modelDocument.uri not in standardXbrlSchmas):
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
                val.modelXbrl.error("SBR.NL.3.2.15.01",
                    _("XML nodes that can appear in instances MUST have standard labels in the local language: %(element)s"),
                    modelObject=eltDef, element=eltDef.qname)

    del val.prefixNamespace, val.namespacePrefix, val.idObjects

def checkDTSdocument(val, modelDocument):
    if modelDocument.type in (ModelDocument.Type.SCHEMA, ModelDocument.Type.LINKBASE):
        isSchema = modelDocument.type == ModelDocument.Type.SCHEMA
        docinfo = modelDocument.xmlDocument.docinfo
        if docinfo and docinfo.xml_version != "1.0":
            val.modelXbrl.error("SBR.NL.2.2.0.02" if isSchema else "SBR.NL.2.3.0.02",
                    _('%(docType)s xml version must be "1.0" but is "%(xmlVersion)s"'),
                    modelObject=modelDocument, docType=modelDocument.gettype().title(), 
                    xmlVersion=docinfo.xml_version)
        if modelDocument.documentEncoding.lower() != "utf-8":
            val.modelXbrl.error("SBR.NL.2.2.0.03" if isSchema else "SBR.NL.2.3.0.03",
                    _('%(docType)s encoding must be "utf-8" but is "%(xmlEncoding)s"'),
                    modelObject=modelDocument, docType=modelDocument.gettype().title(), 
                    xmlEncoding=modelDocument.documentEncoding)
        lookingForPrecedingComment = True
        for commentNode in modelDocument.xmlRootElement.itersiblings(preceding=True):
            if isinstance(commentNode,etree._Comment):
                if lookingForPrecedingComment:
                    lookingForPrecedingComment = False
                else:
                    val.modelXbrl.error("SBR.NL.2.2.0.05" if isSchema else "SBR.NL.2.3.0.05",
                            _('%(docType)s must have only one comment node before schema element'),
                            modelObject=modelDocument, docType=modelDocument.gettype().title())
        if lookingForPrecedingComment:
            val.modelXbrl.error("SBR.NL.2.2.0.04" if isSchema else "SBR.NL.2.3.0.04",
                _('%(docType)s must have comment node only on line 2'),
                modelObject=modelDocument, docType=modelDocument.gettype().title())
        
        # check namespaces are used
        for prefix, ns in modelDocument.xmlRootElement.nsmap.items():
            if ((prefix not in val.valUsedPrefixes) and
                (modelDocument.type != ModelDocument.Type.SCHEMA or ns != modelDocument.targetNamespace)):
                val.modelXbrl.error("SBR.NL.2.2.0.11" if modelDocument.type == ModelDocument.Type.SCHEMA else "SBR.NL.2.3.0.08",
                    _('%(docType)s namespace declaration "%(declaration)s" is not used'),
                    modelObject=modelDocument, docType=modelDocument.gettype().title(), 
                    declaration=("xmlns" + (":" + prefix if prefix else "") + "=" + ns))
                
        if isSchema and val.annotationsCount > 1:
            val.modelXbrl.error("SBR.NL.2.2.0.22",
                _('Schema has %(annotationsCount)s xs:annotation elements, only 1 allowed'),
                modelObject=modelDocument, annotationsCount=val.annotationsCount)
    if modelDocument.type ==  ModelDocument.Type.LINKBASE:
        if not val.containsRelationship:
            val.modelXbrl.error("SBR.NL.2.3.0.12",
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
                    val.modelXbrl.error("SBR.NL.3.2.1.09",
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
                    val.modelXbrl.error("SBR.NL.3.2.1.10",
                        "Generic linkbase filename expected to end with %(expectedSuffix)s: %(filename)s",
                        modelObject=modelDocument, expectedSuffix=expectedSuffix, filename=modelDocument.uri)
        # label checks
        for qnLabel in (XbrlConst.qnLinkLabel, XbrlConst.qnGenLabel):
            for modelLabel in modelDocument.xmlRootElement.iterdescendants(tag=qnLabel.clarkNotation):
                if isinstance(modelLabel,ModelResource):
                    if not modelLabel.text or not modelLabel.text[:1].isupper():
                        val.modelXbrl.error("SBR.NL.3.2.7.05",
                            _("Labels MUST have a capital first letter, label %(label)s: %(text)s"),
                            modelObject=modelLabel, label=modelLabel.xlinkLabel, text=modelLabel.text[:64])
                    if modelLabel.role in (XbrlConst.standardLabel, XbrlConst.genStandardLabel):
                        if len(modelLabel.text) > 255:
                            val.modelXbrl.error("SBR.NL.3.2.7.06",
                                _("Labels with the 'standard' role MUST NOT exceed 255 characters, label %(label)s: %(text)s"),
                                modelObject=modelLabel, label=modelLabel.xlinkLabel, text=modelLabel.text[:64])
                if modelLabel.role in (XbrlConst.standardLabel, XbrlConst.genStandardLabel):
                    if len(modelLabel.text) > 255:
                        val.modelXbrl.error("SBR.NL.3.2.7.06",
                            _("Labels with the 'standard' role MUST NOT exceed 255 characters, label %(label)s: %(text)s"),
                            modelObject=modelLabel, label=modelLabel.xlinkLabel, text=modelLabel.text[:64])
        for modelResource in modelDocument.modelObjects:
            # locator checks
            if isinstance(modelResource,ModelLocator):
                hrefModelObject = modelResource.dereference()
                if isinstance(hrefModelObject, ModelObject):
                    expectedLocLabel = hrefModelObject.id + "_loc"
                    if modelResource.xlinkLabel != expectedLocLabel:
                        val.modelXbrl.error("SBR.NL.3.2.11.01",
                            _("Locator @xlink:label names MUST be concatenated from: @id from the XML node, underscore, 'loc', expected %(expectedLocLabel)s, found %(foundLocLabel)s"),
                            modelObject=modelResource, expectedLocLabel=expectedLocLabel, foundLocLabel=modelResource.xlinkLabel)
            # xlinkLabel checks
            if isinstance(modelResource, ModelResource):
                if re.match(r"[^a-zA-Z0-9_-]", modelResource.xlinkLabel):
                    val.modelXbrl.error("SBR.NL.3.2.11.03",
                        _("@xlink:label names MUST use a-zA-Z0-9_- characters only: %(xlinkLabel)s"),
                        modelObject=modelResource, xlinkLabel=modelResource.xlinkLabel)
    elif modelDocument.targetNamespace: # SCHEMA with targetNamespace
        # check for unused imports
        for referencedDocument in modelDocument.referencesDocument.keys():
            if (referencedDocument.type == ModelDocument.Type.SCHEMA and
                referencedDocument.targetNamespace not in {XbrlConst.xbrli, XbrlConst.link} and
                referencedDocument.targetNamespace not in val.referencedNamespaces):
                val.modelXbrl.error("SBR.NL.2.2.0.15",
                    _("A schema import schemas of which no content is being addressed: %(importedFile)s"),
                    modelObject=modelDocument, importedFile=referencedDocument.basename)
        if modelDocument.targetNamespace != modelDocument.targetNamespace.lower():
            val.modelXbrl.error("SBR.NL.3.2.3.02",
                _("Namespace URI's MUST be lower case: %(namespaceURI)s"),
                modelObject=modelDocument, namespaceURI=modelDocument.targetNamespace)
        if len(modelDocument.targetNamespace) > 255:
            val.modelXbrl.error("SBR.NL.3.2.3.03",
                _("Namespace URI's MUST NOT be longer than 255 characters: %(namespaceURI)s"),
                modelObject=modelDocument, namespaceURI=modelDocument.targetNamespace)
        if re.match(r"[^a-z0-9_/-]", modelDocument.targetNamespace):
            val.modelXbrl.error("SBR.NL.3.2.3.04",
                _("Namespace URI's MUST use only signs from a-z0-9_-/: %(namespaceURI)s"),
                modelObject=modelDocument, namespaceURI=modelDocument.targetNamespace)
        if not modelDocument.targetNamespace.startswith('http://www.nltaxonomie.nl'):
            val.modelXbrl.error("SBR.NL.3.2.3.05",
                _("Namespace URI's MUST start with 'http://www.nltaxonomie.nl': %(namespaceURI)s"),
                modelObject=modelDocument, namespaceURI=modelDocument.targetNamespace)
        namespacePrefix = XmlUtil.xmlnsprefix(modelDocument.xmlRootElement, modelDocument.targetNamespace)
        if not namespacePrefix:
            val.modelXbrl.error("SBR.NL.3.2.4.01",
                _("TargetNamespaces MUST have a prefix: %(namespaceURI)s"),
                modelObject=modelDocument, namespaceURI=modelDocument.targetNamespace)
        elif namespacePrefix in val.prefixNamespace:
            val.modelXbrl.error("SBR.NL.3.2.4.02",
                _("Namespace prefix MUST be unique within the NT but prefix '%(prefix)s' is used by both %(namespaceURI)s and %(namespaceURI2)s."),
                modelObject=modelDocument, prefix=namespacePrefix, 
                namespaceURI=modelDocument.targetNamespace, namespaceURI2=val.prefixNamespace[namespacePrefix])
        else:
            val.prefixNamespace[namespacePrefix] = modelDocument.targetNamespace
            val.namespacePrefix[modelDocument.targetNamespace] = namespacePrefix
        if namespacePrefix in {"xsi", "xsd", "xs", "xbrli", "link", "xlink", "xbrldt", "xbrldi", "gen", "xl"}:
            val.modelXbrl.error("SBR.NL.3.2.4.03",
                _("Namespace prefix '%(prefix)s' reserved by organizations for international specifications is used %(namespaceURI)s."),
                modelObject=modelDocument, prefix=namespacePrefix, namespaceURI=modelDocument.targetNamespace)
        if len(namespacePrefix) > 20:
            val.modelXbrl.warning("SBR.NL.3.2.4.06",
                _("Namespace prefix '%(prefix)s' SHOULD not exceed 20 characters %(namespaceURI)s."),
                modelObject=modelDocument, prefix=namespacePrefix, namespaceURI=modelDocument.targetNamespace)
        # check every non-targetnamespace prefix against its schema
    requiredLinkrole = None # only set for extension taxonomies
    # check folder names
    if modelDocument.filepathdir.startswith(val.modelXbrl.uriDir):
        partnerPrefix = None
        pathDir = modelDocument.filepathdir[len(val.modelXbrl.uriDir) + 1:].replace("\\", "/")
        for pathSegment in pathDir.split("/"):
            if pathSegment.lower() != pathSegment:
                val.modelXbrl.error("SBR.NL.3.2.1.02",
                    _("Folder names must be in lower case: %(folder)s"),
                    modelObject=modelDocument, folder=pathSegment)
            if len(pathSegment) >= 15 :
                val.modelXbrl.error("SBR.NL.3.2.1.03",
                    _("Folder names must be less than 15 characters: %(folder)s"),
                    modelObject=modelDocument, folder=pathSegment)
            if pathSegment in ("bd", "kvk", "cbs"):
                partnerPrefix = pathSegment + '-'
        if modelDocument.basename.lower() != modelDocument.basename:
            val.modelXbrl.error("SBR.NL.3.2.1.05",
                _("File names must be in lower case: %(file)s"),
                modelObject=modelDocument, folder=modelDocument.basename)
        if partnerPrefix and not modelDocument.basename.startswith(partnerPrefix):
            val.modelXbrl.error("SBR.NL.3.2.2.01",
                "NT Partner DTS files MUST start with %(partnerPrefix)s consistently: %(filename)s",
                modelObject=modelDocument, partnerPrefix=partnerPrefix, filename=modelDocument.uri)
        if modelDocument.type ==  ModelDocument.Type.SCHEMA:
            if modelDocument.targetNamespace:
                nsParts = modelDocument.targetNamespace.split("/")
                # [0] = https, [1] = // [2] = nl.taxonomie  [3] = year
                requiredNamespace = "http://www.nltaxonomie.nl/" + nsParts[3] + "/" + pathDir + "/" + modelDocument.basename[:-4]
                requiredLinkrole = "http://www.nltaxonomie.nl/" + nsParts[3] + "/" + pathDir + "/"
                if modelDocument == val.modelXbrl.modelDocument:  # entry point
                    requiredNamespace += '-' + nsParts[3]
                if not modelDocument.targetNamespace.startswith(requiredNamespace):
                    val.modelXbrl.error("SBR.NL.3.2.3.06",
                        _("Namespace URI's MUST be constructed like %(requiredNamespace)s: %(namespaceURI)s"),
                        modelObject=modelDocument, requiredNamespace=requiredNamespace, namespaceURI=modelDocument.targetNamespace)
            else:
                requiredLinkrole = ''
            # concept checks
            for modelConcept in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/2001/XMLSchema}element"):
                if isinstance(modelConcept,ModelConcept):
                    # 6.7.16 name not duplicated in standard taxonomies
                    name = modelConcept.get("name")
                    if name: 
                        substititutionGroupQname = modelConcept.substitutionGroupQname
                        if substititutionGroupQname:
                            if name.endswith("Member") ^ (substititutionGroupQname.localName == "domainMemberItem" and
                                                          substititutionGroupQname.namespaceURI.endswith("/xbrl/xbrl-syntax-extension")):
                                val.modelXbrl.error("SBR.NL.3.2.5.11",
                                    _("Concept %(concept)s must end in Member to be in sbr:domainMemberItem substitution group"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if name.endswith("Domain") ^ (substititutionGroupQname.localName == "domainItem" and
                                                          substititutionGroupQname.namespaceURI.endswith("/xbrl/xbrl-syntax-extension")):
                                val.modelXbrl.error("SBR.NL.3.2.5.12",
                                    _("Concept %(concept)s must end in Domain to be in sbr:domainItem substitution group"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if name.endswith("TypedAxis") ^ (substititutionGroupQname == XbrlConst.qnXbrldtDimensionItem and
                                                             modelConcept.isTypedDimension):
                                val.modelXbrl.error("SBR.NL.3.2.5.14",
                                    _("Concept %(concept)s must end in TypedAxis to be in xbrldt:dimensionItem substitution group if they represent a typed dimension"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if (name.endswith("Axis") and 
                                not name.endswith("TypedAxis")) ^ (substititutionGroupQname == XbrlConst.qnXbrldtDimensionItem and
                                                                   modelConcept.isExplicitDimension):
                                val.modelXbrl.error("SBR.NL.3.2.5.13",
                                    _("Concept %(concept)s must end in Axis to be in xbrldt:dimensionItem substitution group if they represent an explicit dimension"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if name.endswith("Table") ^ (substititutionGroupQname == XbrlConst.qnXbrldtHypercubeItem):
                                val.modelXbrl.error("SBR.NL.3.2.5.15",
                                    _("Concept %(concept)s must end in Table to be in xbrldt:hypercubeItem substitution group"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if name.endswith("Title") ^ (substititutionGroupQname.localName == "presentationItem" and
                                                         substititutionGroupQname.namespaceURI.endswith("/xbrl/xbrl-syntax-extension")):
                                val.modelXbrl.error("SBR.NL.3.2.5.16",
                                    _("Concept %(concept)s must end in Title to be in sbr:presentationItem substitution group"),
                                    modelObject=modelConcept, concept=modelConcept.qname)
                        if len(name) > 200:
                            val.modelXbrl.error("SBR.NL.3.2.12.02" if modelConcept.isLinkPart 
                                                else "SBR.NL.3.2.5.21" if (modelConcept.isItem or modelConcept.isTuple)
                                                else "SBR.NL.3.2.14.01",
                                _("Concept %(concept)s name length %(namelength)s exceeds 200 characters"),
                                modelObject=modelConcept, concept=modelConcept.qname, namelength=len(name))
            # type checks
            for typeType in ("simpleType", "complexType"):
                for modelType in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/2001/XMLSchema}" + typeType):
                    if isinstance(modelType,ModelType):
                        name = modelType.get("name")
                        if name is None: 
                            name = ""
                            if modelType.get("ref") is not None:
                                continue    # don't validate ref's here
                        if len(name) > 200:
                            val.modelXbrl.error("SBR.NL.3.2.5.21",
                                _("Type %(type)s name length %(namelength)s exceeds 200 characters"),
                                modelObject=modelType, type=modelType.qname, namelength=len(name))
                        if modelType.qnameDerivedFrom and modelType.qnameDerivedFrom.namespaceURI != XbrlConst.xbrli:
                            val.modelXbrl.error("SBR.NL.3.2.8.01",
                                _("Custom datatypes MUST be a restriction from XII defined datatypes: %(type)s"),
                                modelObject=modelType, type=modelType.qname)
                        if re.match(r"[^a-z0-9_/-]", name):
                            val.modelXbrl.error("SBR.NL.3.2.8.02",
                                _("Datatype names MUST use characters a-zA-Z0-9_- only: %(type)s"),
                                modelObject=modelDocument, type=modelType.qname)
                        if modelType.facets and "enumeration" in modelType.facets:
                            if not modelType.qnameDerivedFrom == XbrlConst.qnXbrliStringItemType:
                                val.modelXbrl.error("SBR.NL.3.2.13.01",
                                    _("Enumerations MUST use a restriction on xbrli:stringItemType: %(type)s"),
                                    modelObject=modelDocument, type=modelType.qname)
    # check for idObject conflicts
    for id, modelObject in modelDocument.idObjects.items():
        if id in val.idObjects:
            val.modelXbrl.error("SBR.NL.3.2.6.01",
                _("ID %(id)s must be unique in the DTS but is present on two elements."),
                modelObject=(modelObject, val.idObjects[id]), id=id)
        else:
            val.idObjects[id] = modelObject

            
    for roleURI, modelRoleTypes in val.modelXbrl.roleTypes.items():
        if not roleURI.startswith("http://www.xbrl.org"):
            usedOns = set.union(*[modelRoleType.usedOns for modelRoleType in modelRoleTypes])
            # check roletypes for linkroles (only)
            if usedOns & {XbrlConst.qnLinkPresentationLink, XbrlConst.qnLinkCalculationLink, XbrlConst.qnLinkDefinitionLink,
                          XbrlConst.qnLinkLabel, XbrlConst.qnLinkReference, XbrlConst.qnLinkFootnote}:
                if len(modelRoleTypes) > 1:
                    val.modelXbrl.error("SBR.NL.3.2.9.01",
                        _("Linkrole URI's MUST be unique in the NT: %(linkrole)s"),
                        modelObject=modelRoleTypes, linkrole=roleURI)
                if roleURI.lower() != roleURI:
                    val.modelXbrl.error("SBR.NL.3.2.9.02",
                        _("Linkrole URI's MUST be in lowercase: %(linkrole)s"),
                        modelObject=modelRoleTypes, linkrole=roleURI)
                if re.match(r"[^a-z0-9_/-]", roleURI):
                    val.modelXbrl.error("SBR.NL.3.2.9.03",
                        _("Linkrole URI's MUST use characters a-z0-9_-/ only: %(linkrole)s"),
                        modelObject=modelRoleTypes, linkrole=roleURI)
                if len(roleURI) > 255:
                    val.modelXbrl.error("SBR.NL.3.2.9.04",
                        _("Linkrole URI's MUST NOT be longer than 255 characters, length is %(len)s: %(linkrole)s"),
                        modelObject=modelRoleTypes, len=len(roleURI), linkrole=roleURI)
                if not roleURI.startswith('http://www.nltaxonomie.nl'):
                    val.modelXbrl.error("SBR.NL.3.2.9.05",
                        _("Linkrole URI's MUST start with 'http://www.nltaxonomie.nl': %(linkrole)s"),
                        modelObject=modelRoleTypes, linkrole=roleURI)
                if (requiredLinkrole and 
                    not roleURI.startswith(requiredLinkrole) and 
                    re.match(r".*(domain$|axis$|table$|lineitem$)", roleURI)):
                        val.modelXbrl.error("SBR.NL.3.2.9.06",
                            _("Linkrole URI's MUST have the following construct: http://www.nltaxonomie.nl / {folder path} / {functional name} - {domain or axis or table or lineitem}: %(linkrole)s"),
                            modelObject=modelRoleTypes, linkrole=roleURI)
                for modelRoleType in modelRoleTypes:
                    if len(modelRoleType.id) > 255:
                        val.modelXbrl.error("SBR.NL.3.2.10.02",
                            _("Linkrole @id MUST NOT exceed 255 characters, length is %(length)s: %(linkroleID)s"),
                            modelObject=modelRoleType, length=len(modelRoleType.id), linkroleID=modelRoleType.id)

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate SBR-NL',
    'version': '0.9',
    'description': '''SBR-NL Validation.''',
    'license': 'Apache-2',
    'author': 'S. Bee Are',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Validate.SBRNL.Start': setup,
    # 'Validate.SBRNL.Fact': factCheck  (no instances being checked by SBRNL,
    'Validate.SBRNL.Finally': final,
    'Validate.SBRNL.DTS.document': checkDTSdocument,
}
