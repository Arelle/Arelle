from arelle import PluginManager
from arelle import ModelDocument, XbrlConst, XmlUtil
import re
from lxml import etree

def setup(val):
    cntlr = val.modelXbrl.modelManager.cntlr


'''
def factCheck(val, fact):
    concept = fact.concept
    context = fact.context
    if concept is None or context is None:
        return # not checkable
    
    try:

    except Exception as err:
        val.modelXbrl.log('WARNING-SEMANTIC', "SBR-NL.testingException",
            _("%(fact)s in context %(contextID)s unit %(unitID)s value %(value)s cannot be tested due to: %(err)s"),
            modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
            value=fact.effectiveValue, err=err)
'''
def final(val, conceptsUsed):
    pass

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
    else: # SCHEMA
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
    # check folder names
    if modelDocument.filepathdir.startswith(val.modelXbrl.uriDir):
        partnerPrefix = None
        pathDir = modelDocument.filepathdir[len(val.modelXbrl.uriDir) + 1:]
        for pathSegment in pathDir.replace("\\", "/").split("/"):
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
    #dirpart = modelDocument.val.modelXbrl.uriDir
    
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate SBR-NL',
    'version': '0.9',
    'description': '''SBR-NL Validation.''',
    'license': 'Apache-2',
    'author': 'S. Bee Are',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Validate.EFM.Start': setup,
    #'Validate.EFM.Fact': factCheck,
    'Validate.EFM.Finally': final,
    'Validate.SBRNL.DTS.document': checkDTSdocument,
}
