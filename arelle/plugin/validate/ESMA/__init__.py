'''
Created on June 6, 2018

Filer Guidelines: esma32-60-254_esef_reporting_manual.pdf

Taxonomy Architecture: 

Taxonomy package expected to be installed: 

@author: Mark V Systems Limited
(c) Copyright 2018 Mark V Systems Limited, All rights reserved.
'''
import os, re
from collections import defaultdict
from lxml.etree import _ElementTree, _Comment, _ProcessingInstruction
from arelle import LeiUtil, ModelDocument, XbrlConst, XmlUtil
from arelle.ModelDtsObject import ModelResource
from arelle.ModelInstanceObject import ModelFact, ModelInlineFact, ModelInlineFootnote
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname
from arelle.XbrlConst import ixbrlAll, xhtml
from .Const import allowedImgMimeTypes, browserMaxBase64ImageLength, mandatory
from .Dimensions import checkFilingDimensions
from .DTS import checkFilingDTS

datetimePattern = re.compile(r"\s*([0-9]{4})-([0-9]{2})-([0-9]{2})([T ]([0-9]{2}):([0-9]{2}):([0-9]{2}))?\s*")
                
def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("ESMA", "ESMAplugin"),)

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateESMAplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "ESMAplugin", False)
    if not (val.validateESMAplugin):
        return
    

def validateXbrlFinally(val, *args, **kwargs):
    if not (val.validateESMAplugin):
        return

    _xhtmlNs = "{{{}}}".format(xhtml)
    _xhtmlNsLen = len(_xhtmlNs)
    modelXbrl = val.modelXbrl
    modelDocument = modelXbrl.modelDocument

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)
    
    
    if modelDocument.type == ModelDocument.Type.INSTANCE:
        modelXbrl.error("esma:instanceShallBeInlineXBRL",
                        _("RTS on ESEF requires inline XBRL instances."), 
                        modelObject=modelXbrl)
        
    checkFilingDimensions(val) # sets up val.primaryItems and val.domainMembers
    val.hasExtensionSchema = val.hasExtensionPre = val.hasExtensionCal = val.hasExtensionDef = val.hasExtensionLbl = False
    checkFilingDTS(val, modelXbrl.modelDocument, [])
    modelXbrl.profileActivity("... filer DTS checks", minTimeToShow=1.0)
    
    if not (val.hasExtensionSchema and val.hasExtensionPre and val.hasExtensionCal and val.hasExtensionDef and val.hasExtensionLbl):
        missingFiles = []
        if not val.hasExtensionSchema: missingFiles.append("schema file")
        if not val.hasExtensionPre: missingFiles.append("presentation linkbase")
        if not val.hasExtensionCal: missingFiles.append("calculation linkbase")
        if not val.hasExtensionDef: missingFiles.append("definition linkbase")
        if not val.hasExtensionLbl: missingFiles.append("label linkbase")
        modelXbrl.warning("esma:3.1.1.extensionTaxonomyWrongFilesStructure",
            _("Extension taxonomies MUST consist of at least a schema file and presentation, calculation, definition and label linkbases"
              ": missing %(missingFiles)s"),
            modelObject=modelXbrl, missingFiles=", ".join(missingFiles))
        

    if modelDocument.type in (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INSTANCE):
        footnotesRelationshipSet = modelXbrl.relationshipSet("XBRL-footnotes")
        orphanedFootnotes = set()
        noLangFootnotes = set()
        foonoteRoleErrors = set()
        transformRegistryErrors = set()
        def checkFootnote(elt, text):
            if text: # non-empty footnote must be linked to a fact if not empty
                if not any(isinstance(rel.fromModelObject, ModelFact)
                           for rel in footnotesRelationshipSet.toModelObject(elt)):
                    orphanedFootnotes.add(elt)
            if not elt.xmlLang:
                noLangFootnotes.add(elt)
            if elt.role != XbrlConst.footnote or not all(
                rel.arcrole == XbrlConst.factFootnote and rel.linkrole == XbrlConst.defaultLinkRole
                for rel in footnotesRelationshipSet.toModelObject(elt)):
                footnoteRoleErrors.add(elt)
                
        if modelDocument.type == ModelDocument.Type.INLINEXBRL:
            _baseName, _baseExt = os.path.splitext(modelDocument.basename)
            if _baseExt not in (".xhtml",):
                modelXbrl.warning("esma:TBD.fileNameExtension",
                    _("FileName should have the extension .xhtml: %(fileName)s"),
                    modelObject=modelXbrl, fileName=modelDocument.basename)
            ixNStag = modelXbrl.modelDocument.ixNStag
            ixTags = set(ixNStag + ln for ln in ("nonNumeric", "nonFraction", "references", "relationship"))
            ixTextTags = set(ixNStag + ln for ln in ("nonFraction", "continuation", "footnote"))
            ixExcludeTag = ixNStag + "exclude"
            ixTupleTag = ixNStag + "tuple"
            ixFractionTag = ixNStag + "fraction"
            rootElt = modelDocument.xmlRootElement
            for elt in rootElt.iter():
                eltTag = elt.tag
                if isinstance(elt, ModelObject) and elt.namespaceURI == xhtml:
                    eltTag = elt.localName
                elif isinstance(elt, (_ElementTree, _Comment, _ProcessingInstruction)):
                    continue # comment or other non-parsed element
                else:
                    eltTag = elt.tag
                    if eltTag.startswith(_xhtmlNs):
                        eltTag = eltTag[_xhtmlNsLen:]
                    if ((eltTag in ("object", "script")) or
                        (eltTag == "a" and "javascript:" in elt.get("href","")) or
                        (eltTag == "img" and "javascript:" in elt.get("src",""))):
                        modelXbrl.error("esma.2.5.1.executableCodePresent",
                            _("Inline XBRL documents MUST NOT contain executable code: %(element)s"),
                            modelObject=elt, element=eltTag)
                    elif eltTag == "img":
                        src = elt.get("src","").strip()
                        hasParentIxTextTag = False # check if image is in an ix text-bearing element
                        _ancestorElt = elt
                        while (_ancestorElt is not None):
                            if _ancestorElt.tag == ixExcludeTag: # excluded from any parent text-bearing ix element
                                break
                            if _ancestorElt.tag in ixTextTags:
                                hasParentIxTextTag = True
                                break
                            _ancestorElt = _ancestorElt.getparent()                        
                        if scheme(href) in ("http", "https", "ftp"):
                            modelXbrl.error("esma.3.5.1.inlinXbrlContainsExternalReferences",
                                _("Inline XBRL instance documents MUST NOT contain any reference pointing to resources outside the reporting package: %(element)s"),
                                modelObject=elt, element=eltTag)
                        if not src.startswith("data:image"):
                            if hasParentIxTextTag:
                                modelXbrl.error("esma.2.5.1.embeddedImageNotUsingBase64Encoding",
                                    _("Images MUST be included in the XHTML document as a base64 encoded string unless their size exceeds support of browsers."),
                                    modelObject=elt)
                            else:
                                # presume it to be an image file, check image contents
                                try:
                                    base = elt.modelDocument.baseForElement(elt)
                                    normalizedUri = elt.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(graphicFile, base)
                                    if not elt.modelXbrl.fileSource.isInArchive(normalizedUri):
                                        normalizedUri = elt.modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri)
                                        imglen = 0
                                        with elt.modelXbrl.fileSource.file(normalizedUri,binary=True)[0] as fh:
                                            imglen += len(fh.read())
                                    if imglen < browserMaxBase64ImageLength:
                                        modelXbrl.error("esma.2.5.1.embeddedImageNotUsingBase64Encoding",
                                            _("Images MUST be included in the XHTML document as a base64 encoded string unless their size exceeds support of browsers."),
                                            modelObject=elt)
                                except IOError as err:
                                    modelXbrl.error("esma.2.5.1.imageFileCannotBeLoaded",
                                        _("Image file which isn't openable '%(src)s', error: %(error)s"),
                                        modelObject=elt, src=src, error=err)
                        elif not any(src.startswith(m) for m in allowedImgMimeTypes):
                                modelXbrl.error("esma.2.5.1.embeddedImageNotUsingBase64Encoding",
                                    _("Images MUST be included in the XHTML document as a base64 encoded string, encoding disallowed: %(src)s."),
                                    modelObject=elt, src=attrValue[:128])
                    elif eltTag == "a":
                        href = elt.get("href","").strip()
                        if scheme(href) in ("http", "https", "ftp"):
                            modelXbrl.error("esma.3.5.1.inlinXbrlContainsExternalReferences",
                                _("Inline XBRL instance documents MUST NOT contain any reference pointing to resources outside the reporting package: %(element)s"),
                                modelObject=elt, element=eltTag)
                        
                if eltTag in ixTags and elt.get("target"):
                    modelXbrl.error("esma.2.5.3.targetAttributeUsed",
                        _("Target attribute MUST not be used: element %(localName)s, target attribute %(target)s."),
                        modelObject=elt, localName=elt.elementQname, target=elt.get("target"))
                if eltTag == ixTupleTag:
                    modelXbrl.error("esma.2.5.3.tupleElementUsed",
                        _("The ix:tuple element MUST not be used."),
                        modelObject=elt)
                if eltTag == ixFractionTag:
                    modelXbrl.error("esma.2.5.3.fractionElementUsed",
                        _("The ix:fraction element MUST not be used."),
                        modelObject=elt)
                if elt.get("{http://www.w3.org/XML/1998/namespace}base") is not None:
                    modelXbrl.error("esma.2.4.1.xmlBaseUsed",
                        _("xml:base attributes MUST NOT be used in the Inline XBRL document: element %(localName)s, base attribute %(base)s."),
                        modelObject=elt, localName=elt.elementQname, base=elt.get("{http://www.w3.org/XML/1998/namespace}base"))
                if isinstance(elt, ModelInlineFootnote):
                    checkFootnote(elt, elt.value)
                elif isinstance(elt, ModelResource) and elt.qname == XbrlConst.qnLinkFootnote:
                    checkFootnote(elt, elt.value)
                elif isinstance(elt, ModelInlineFact):
                    if elt.format is not None and elt.format.namespaceURI != 'http://www.xbrl.org/inlineXBRL/transformation/2015-02-26':
                        transformRegistryErrors.add(elt)
        elif modelDocument.type == ModelDocument.Type.INSTANCE:
            for elt in modelDocument.xmlRootElement.iter():
                if elt.qname == XbrlConst.qnLinkFootnote: # for now assume no private elements extend link:footnote
                    checkFootnote(elt, elt.stringValue)
                        
               
        contextsWithDisallowedOCEs = []
        contextsWithDisallowedOCEcontent = []
        contextsWithPeriodTime = []
        contextsWithPeriodTimeZone = []
        contextIdentifiers = defaultdict(list)
        nonStandardTypedDimensions = defaultdict(set)
        for context in modelXbrl.contexts.values():
            if XmlUtil.hasChild(context, XbrlConst.xbrli, "segment"):
                contextsWithDisallowedOCEs.append(context)
            for segScenElt in context.iterdescendants("{http://www.xbrl.org/2003/instance}scenario"):
                if isinstance(segScenElt,ModelObject):
                    if any(True for child in segScenElt.iterchildren()
                                if isinstance(child,ModelObject) and 
                                   child.tag not in ("{http://xbrl.org/2006/xbrldi}explicitMember",
                                                     "{http://xbrl.org/2006/xbrldi}typedMember")):
                        contextsWithDisallowedOCEcontent.append(context)
            # check periods here
            contextIdentifiers[context.entityIdentifier].append(context)
                
        if contextsWithDisallowedOCEs:
            modelXbrl.error("esma.2.1.3.segmentUsed",
                _("xbrli:segment container MUST NOT be used in contexts: %(contextIds)s"),
                modelObject=contextsWithDisallowedOCEs, contextIds=", ".join(c.id for c in contextsWithDisallowedOCEs))
        if contextsWithDisallowedOCEcontent:
            modelXbrl.error("esma.2.1.3.scenarioContainsNonDimensionalContent",
                _("xbrli:scenario in contexts MUST NOT contain any other content than defined in XBRL Dimensions specification: %(contextIds)s"),
                modelObject=contextsWithDisallowedOCEcontent, contextIds=", ".join(c.id for c in contextsWithDisallowedOCEcontent))
        if len(contextIdentifiers) > 1:
            modelXbrl.error("esma.2.1.4.multipleIdentifiers",
                _("All entity identifiers in contexts MUST have identical content: %(contextIdentifiers)s"),
                modelObject=modelXbrl, contextIds=", ".join(i[1] for i in contextIdentifiers))
        for (contextScheme, contextIdentifier), contextElts in contextIdentifiers.items():
            if contextScheme != "http://standards.iso.org/iso/17442":
                modelXbrl.warning("esma.2.1.1.nonLEIContextScheme",
                    _("The scheme attribute of the xbrli:identifier element should have \"http://standards.iso.org/iso/17442\" as its content: %(scheme)s"),
                    modelObject=contextElts, scheme=contextScheme)
            else:
                leiValidity = LeiUtil.checkLei(contextIdentifier)
                if leiValidity == LeiUtil.LEI_INVALID_LEXICAL:
                    modelXbrl.warning("esma.2.1.1.invalidIdentifierFormat",
                        _("The LEI context idenntifier has an invalid format: %(identifier)s"),
                        modelObject=contextElts, identifier=contextIdentifier)
                elif leiValidity == LeiUtil.LEI_INVALID_CHECKSUM:
                    modelXbrl.warning("esma.2.1.1.invalidIdentifier",
                        _("The LEI context idenntifier has checksum error: %(identifier)s"),
                        modelObject=contextElts, identifier=contextIdentifier)
        if contextsWithPeriodTime:
            modelXbrl.warning("esma.2.1.2.periodWithTimeContent",
                _("Context period startDate, endDate and instant elements should be in whole days without time: %(contextIds)s"),
                modelObject=contextsWithPeriodTime, contextIds=", ".join(c.id for c in contextsWithPeriodTime))
        if contextsWithPeriodTimeZone:
            modelXbrl.warning("esma.2.1.2.periodWithTimeZone",
                _("Context period startDate, endDate and instant elements should be in whole days without a timezone: %(contextIds)s"),
                modelObject=contextsWithPeriodTimeZone, contextIds=", ".join(c.id for c in contextsWithPeriodTimeZone))
                
        
        reportedMandatory = set()
        footnotesRelationshipSet = modelXbrl.relationshipSet(XbrlConst.factFootnote, XbrlConst.defaultLinkRole)
                
        for qn, facts in modelXbrl.factsByQname.items():
            if qn in mandatory:
                reportedMandatory.add(qn)
            
        missingElements = (mandatory - reportedMandatory) 
        if missingElements:
            modelXbrl.error("esma:???.missingRequiredElements",
                            _("Required elements missing from document: %(elements)s."), 
                            modelObject=modelXbrl, elements=", ".join(sorted(str(qn) for qn in missingElements)))
            
        if transformRegistryErrors:
            modelXbrl.info("esma:???.transformRegistry",
                              _("Transformation Registry 3 should be used for facts: %(elements)s."), 
                              modelObject=transformRegistryErrors, 
                              elements=", ".join(sorted(str(fact.qname) for fact in transformRegistryErrors)))
            
        if orphanedFootnotes:
            modelXbrl.error("esma.2.3.1.unusedFootnote",
                _("Non-empty footnotes must be connected to fact(s)."),
                modelObject=orphanedFootnotes)

        if noLangFootnotes:
            modelXbrl.error("esma.2.3.2.undefinedLanguageForFootnote",
                _("FEach footnote MUST have the 'xml:lang' attribute whose value corresponds to the language of the text in the content of the respective footnote."),
                modelObject=noLangFootnotes)
            
        if foonoteRoleErrors:
            modelXbrl.error("esma.2.3.2.nonStandardRoleForFootnote",
                _("The xlink:role attribute of a link:footnote and link:loc element as well as xlink:arcrole attribute of a link:footnoteArc MUST be defined in the XBRL Specification 2.1."),
                modelObject=foonoteRoleErrors)

    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)
    

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate ESMA',
    'version': '1.0',
    'description': '''ESEF Reporting Manual Validations.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2018 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
}