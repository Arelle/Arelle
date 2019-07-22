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
from arelle.PythonUtil import strTruncate
from arelle.ValidateXbrlCalcs import inferredDecimals, rangeValue
from arelle.XbrlConst import ixbrlAll, xhtml, link, parentChild, summationItem, dimensionDomain, domainMember
from .Const import allowedImgMimeTypes, browserMaxBase64ImageLength, mandatory, untransformableTypes
from .Dimensions import checkFilingDimensions
from .DTS import checkFilingDTS

datetimePattern = re.compile(r"\s*([0-9]{4})-([0-9]{2})-([0-9]{2})([T ]([0-9]{2}):([0-9]{2}):([0-9]{2}))?\s*")
styleIxHiddenPattern = re.compile(r"(.*[^\w]|^)-esef-ix-hidden\s*:\s*([\w.-]+).*")

def etreeIterWithDepth(node, depth=0):
    yield (node, depth)
    for child in node.iterchildren():
        etreeIterWithDepth(child, depth+1)
                
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
    
    reportXmlLang = None
    firstRootmostXmlLangDepth = 9999999
    
    
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
        

    if modelDocument.type in (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET, ModelDocument.Type.INSTANCE):
        footnotesRelationshipSet = modelXbrl.relationshipSet("XBRL-footnotes")
        orphanedFootnotes = set()
        noLangFootnotes = set()
        footnoteRoleErrors = set()
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
                
        # check file name of each inline document (which might be below a top-level IXDS)
        for doc in modelXbrl.urlDocs.values():
            if doc.type == ModelDocument.Type.INLINEXBRL:
                _baseName, _baseExt = os.path.splitext(doc.basename)
                if _baseExt not in (".xhtml",):
                    modelXbrl.warning("esma:TBD.fileNameExtension",
                        _("FileName should have the extension .xhtml: %(fileName)s"),
                        modelObject=doc, fileName=doc.basename)
                
        if modelDocument.type in (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET):
            ixNStag = modelXbrl.modelDocument.ixNStag
            ixTags = set(ixNStag + ln for ln in ("nonNumeric", "nonFraction", "references", "relationship"))
            ixTextTags = set(ixNStag + ln for ln in ("nonFraction", "continuation", "footnote"))
            ixExcludeTag = ixNStag + "exclude"
            ixTupleTag = ixNStag + "tuple"
            ixFractionTag = ixNStag + "fraction"
            hiddenEltIds = {}
            presentedHiddenEltIds = defaultdict(list)
            eligibleForTransformHiddenFacts = []
            requiredToDisplayFacts = []
            requiredToDisplayFactIds = {}
            firstIxdsDoc = True
            for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements: # ix root elements for all ix docs in IXDS
                for elt, depth in etreeIterWithDepth(ixdsHtmlRootElt):
                    eltTag = elt.tag
                    if isinstance(elt, ModelObject) and elt.namespaceURI == xhtml:
                        eltTag = elt.localName
                        if firstIxdsDoc and (not reportXmlLang or depth < firstRootmostXmlLangDepth):
                            xmlLang = elt.get("{http://www.w3.org/XML/1998/namespace}lang")
                            if xmlLang:
                                reportXmlLang = xmlLang
                                firstRootmostXmlLangDepth = depth
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
                                    modelXbrl.error("esma.2.5.1.imageInIXbrlElementNotEmbedded",
                                        _("Images appearing within an inline XBRL element MUST be embedded regardless of their size."),
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
                        elif eltTag == "base" or elt.tag == "{http://www.w3.org/XML/1998/namespace}base":
                            modelXbrl.error("esma.2.4.2.htmlOrXmlBaseUsed",
                                _("The HTML <base> elements and xml:base attributes MUST NOT be used in the Inline XBRL document."),
                                modelObject=elt, element=eltTag)
                            
                    if eltTag in ixTags and elt.get("target"):
                        modelXbrl.error("esma.2.5.3.targetAttributeUsed",
                            _("Target attribute MUST not be used: element %(localName)s, target attribute %(target)s."),
                            modelObject=elt, localName=elt.elementQname, target=elt.get("target"))
                    if eltTag == ixTupleTag:
                        modelXbrl.error("esma.2.4.1.tupleElementUsed",
                            _("The ix:tuple element MUST not be used in the Inline XBRL document."),
                            modelObject=elt)
                    if eltTag == ixFractionTag:
                        modelXbrl.error("esma.2.4.1.fractionElementUsed",
                            _("The ix:fraction element MUST not be used in the Inline XBRL document."),
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
                for ixHiddenElt in ixdsHtmlRootElt.iterdescendants(tag=ixNStag + "hidden"):
                    for tag in (ixNStag + "nonNumeric", ixNStag+"nonFraction"):
                        for ixElt in ixHiddenElt.iterdescendants(tag=tag):
                            if (getattr(ixElt, "xValid", 0) >= VALID  # may not be validated
                                ): # add future "and" conditions on elements which can be in hidden
                                if (ixElt.concept.baseXsdType not in untransformableTypes and
                                    not ixElt.isNil):
                                    eligibleForTransformHiddenFacts.append(ixElt)
                                elif ixElt.id is None:
                                    requiredToDisplayFacts.append(ixElt)
                            if ixElt.id:
                                hiddenEltIds[ixElt.id] = ixElt
                firstIxdsDoc = False
            if eligibleForTransformHiddenFacts:
                modelXbrl.warning("esma.2.4.1.transformableElementIncludedInHiddenSection",
                    _("The ix:hidden section of Inline XBRL document MUST not include elements eligible for transformation. "
                      "%(countEligible)s fact(s) were eligible for transformation: %(elements)s"),
                    modelObject=eligibleForTransformHiddenFacts, 
                    countEligible=len(eligibleForTransformHiddenFacts),
                    elements=", ".join(sorted(set(str(f.qname) for f in eligibleForTransformHiddenFacts))))
            for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
                for ixElt in ixdsHtmlRootElt.getroottree().iterfind("//{http://www.w3.org/1999/xhtml}*[@style]"):
                    hiddenFactRefMatch = styleIxHiddenPattern.match(ixElt.get("style",""))
                    if hiddenFactRefMatch:
                        hiddenFactRef = hiddenFactRefMatch.group(2)
                        if hiddenFactRef not in hiddenEltIds:
                            modelXbrl.error("esma.2.4.1.esefIxHiddenStyleNotLinkingFactInHiddenSection",
                                _("\"-esef-ix-hidden\" style identifies @id, %(id)s of a fact that is not in ix:hidden section."),
                                modelObject=ixElt, id=hiddenFactRef)
                        else:
                            presentedHiddenEltIds[hiddenFactRef].append(ixElt)
            for hiddenEltId, ixElt in hiddenEltIds.items():
                if (hiddenEltId not in presentedHiddenEltIds and
                    getattr(ixElt, "xValid", 0) >= VALID and # may not be validated
                    (ixElt.concept.baseXsdType in untransformableTypes or ixElt.isNil)):
                    requiredToDisplayFacts.append(ixElt)
            if requiredToDisplayFacts:
                modelXbrl.warning("esma.2.4.1.factInHiddenSectionNotInReport",
                    _("The ix:hidden section contains %(countUnreferenced)s fact(s) whose @id is not applied on any \"-esef-ix- hidden\" style: %(elements)s"),
                    modelObject=requiredToDisplayFacts, 
                    countUnreferenced=len(requiredToDisplayFacts),
                    elements=", ".join(sorted(set(str(f.qname) for f in requiredToDisplayFacts))))
            del eligibleForTransformHiddenFacts, hiddenEltIds, presentedHiddenEltIds, requiredToDisplayFacts
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
        
        # identify unique contexts and units
        mapContext = {}
        mapUnit = {}
        uniqueContextHashes = {}
        for context in modelXbrl.contexts.values():
            h = context.contextDimAwareHash
            if h in uniqueContextHashes:
                if context.isEqualTo(uniqueContextHashes[h]):
                    mapContext[context] = uniqueContextHashes[h]
            else:
                uniqueContextHashes[h] = context
        del uniqueContextHashes
        uniqueUnitHashes = {}
        for unit in modelXbrl.units.values():
            h = unit.hash
            if h in uniqueUnitHashes:
                if unit.isEqualTo(uniqueUnitHashes[h]):
                    mapUnit[unit] = uniqueUnitHashes[h]
            else:
                uniqueUnitHashes[h] = unit
        del uniqueUnitHashes
        
        reportedMandatory = set()
        precisionFacts = set()
        numFactsByConceptContextUnit = defaultdict(list)
        textFactsByConceptContext = defaultdict(list)
        footnotesRelationshipSet = modelXbrl.relationshipSet(XbrlConst.factFootnote, XbrlConst.defaultLinkRole)
        noLangFacts = []
        textFactsMissingReportLang = []
        conceptsUsed = set()
                
        for qn, facts in modelXbrl.factsByQname.items():
            if qn in mandatory:
                reportedMandatory.add(qn)
            for f in facts:
                if f.precision is not None:
                    precisionFacts.add(f)
                if f.isNumeric:
                    numFactsByConceptContextUnit[(f.qname, mapContext.get(f.context,f.context), mapUnit.get(f.unit, f.unit))].append(f)
                elif f.concept is not None and f.concept.type is not None:
                    if f.concept.type.isOimTextFactType:
                        if not f.xmlLang:
                            noLangFacts.append(f)
                        elif f.context is not None:
                            textFactsByConceptContext[(f.qname, mapContext.get(f.context,f.context))].append(f)
                conceptsUsed.add(f.concept)
                if f.context is not None:
                    for dim in f.context.qnameDims.values():
                        conceptsUsed.add(dim.dimension)
                        if dim.isExplicit:
                            conceptsUsed.add(dim.member)
                        elif dim.isTyped:
                            conceptsUsed.add(dim.typedMember)
                    
        if noLangFacts:
            modelXbrl.error("esma.2.5.2.undefinedLanguageForTextFact",
                _("Each tagged text fact MUST have the 'xml:lang' attribute assigned or inherited."),
                modelObject=noLangFacts)
            
        # missing report lang text facts
        for fList in textFactsByConceptContext.values():
            if not any(f.xmlLang == reportXmlLang for f in fList):
                modelXbrl.error("esma.2.5.2.taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport",
                    _("Each tagged text fact MUST have the 'xml:lang' provided in at least the language of the report: %(element)s"),
                    modelObject=fList, element=fList[0].qname)
        
            
        # 2.2.4 test
        for fList in numFactsByConceptContextUnit.values():
            if len(fList) > 1:
                f0 = fList[0]
                if any(f.isNil for f in fList):
                    _inConsistent = not all(f.isNil for f in fList)
                elif all(inferredDecimals(f) == inferredDecimals(f0) for f in fList[1:]): # same decimals
                    v0 = rangeValue(f0.value)
                    _inConsistent = not all(rangeValue(f.value) == v0 for f in fList[1:])
                else: # not all have same decimals
                    aMax, bMin = rangeValue(f0.value, inferredDecimals(f0))
                    for f in fList[1:]:
                        a, b = rangeValue(f.value, inferredDecimals(f))
                        if a > aMax: aMax = a
                        if b < bMin: bMin = b
                    _inConsistent = (bMin < aMax)
                if _inConsistent:
                    modelXbrl.error(("esma:2.2.4.inconsistentDuplicateNumericFactInInlineXbrlDocument"),
                        "Inconsistent duplicate numeric facts MUST NOT appear in the content of an inline XBRL document. %(fact)s that was used more than once in contexts equivalent to %(contextID)s: values %(values)s.  ",
                        modelObject=fList, fact=f0.qname, contextID=f0.contextID, values=", ".join(strTruncate(f.value, 128) for f in fList))

        if precisionFacts:
            modelXbrl.warning("esma:2.2.1.precisionAttributeUsed",
                            _("The accuracy of numeric facts SHOULD be defined with the 'decimals' attribute rather than the 'precision' attribute: %(elements)s."), 
                            modelObject=precisionFacts, elements=", ".join(sorted(str(qn) for qn in precisionFacts)))
            
        missingElements = (mandatory - reportedMandatory) 
        if missingElements:
            modelXbrl.error("esma:???.missingRequiredElements",
                            _("Required elements missing from document: %(elements)s."), 
                            modelObject=modelXbrl, elements=", ".join(sorted(str(qn) for qn in missingElements)))
            
        if transformRegistryErrors:
            modelXbrl.warning("esma:2.2.3.transformRegistry",
                              _("ESMA recommends applying the latest available version of the Transformation Rules Registry marked with 'Recommendation' status for these elements: %(elements)s."), 
                              modelObject=transformRegistryErrors, 
                              elements=", ".join(sorted(str(fact.qname) for fact in transformRegistryErrors)))
            
        if orphanedFootnotes:
            modelXbrl.error("esma.2.3.1.unusedFootnote",
                _("Non-empty footnotes must be connected to fact(s)."),
                modelObject=orphanedFootnotes)

        if noLangFootnotes:
            modelXbrl.error("esma.2.3.2.undefinedLanguageForFootnote",
                _("Each footnote MUST have the 'xml:lang' attribute whose value corresponds to the language of the text in the content of the respective footnote."),
                modelObject=noLangFootnotes)
            
        if footnoteRoleErrors:
            modelXbrl.error("esma.2.3.2.nonStandardRoleForFootnote",
                _("The xlink:role attribute of a link:footnote and link:footnoteLink element as well as xlink:arcrole attribute of a link:footnoteArc MUST be defined in the XBRL Specification 2.1."),
                modelObject=footnoteRoleErrors)
            
        nonStdFootnoteElts = list()
        for modelLink in modelXbrl.baseSets[("XBRL-footnotes",None,None,None)]:
            for elt in ixdsHtmlRootElt.iter():
                if isinstance(elt, (_ElementTree, _Comment, _ProcessingInstruction)):
                    continue # comment or other non-parsed element
                if elt.namespaceURI != link or elt.localName not in ("loc", "link", "footnoteArc"):
                    nonStdFootnoteElts.append(elt)

        if nonStdFootnoteElts:
            modelXbrl.error("esma.2.3.2.nonStandardElementInFootnote",
                _("A link:footnoteLink element MUST have no children other than link:loc, link:footnote, and link:footnoteArc."),
                modelObject=nonStdFootnoteElts)
        
        for qn in modelXbrl.qnameDimensionDefaults.values():
            conceptsUsed.add(modelXbrl.qnameConcepts.get(qn))
            
        # unused elements in linkbases
        for arcroles, err in (((parentChild,), "elementsNotUsedForTaggingAppliedInPresentationLinkbase"),
                              ((summationItem,), "elementsNotUsedForTaggingAppliedInCalculationLinkbase"),
                              ((dimensionDomain,domainMember), "elementsNotUsedForTaggingAppliedInDefinitionLinkbase")):
            lbElts = set()
            for arcrole in arcroles:
                for rel in modelXbrl.relationshipSet(arcrole).modelRelationships:
                    fr = rel.fromModelObject
                    to = rel.toModelObject
                    if arcrole in (parentChild, summationItem):
                        if fr is not None and not fr.isAbstract:
                            lbElts.add(fr)
                        if to is not None and not to.isAbstract:
                            lbElts.add(to)
                    elif arcrole == dimensionDomain:
                        if fr is not None: # dimension, always abstract
                            lbElts.add(fr)
                        if to is not None and rel.isUsable:
                            lbElts.add(to)
                    elif arcrole == domainMember:
                        if to is not None and rel.isUsable:
                            lbElts.add(to)
            unreportedLbElts = lbElts - conceptsUsed
            if unreportedLbElts:
                modelXbrl.error("esma.3.2.6." + err,
                    _("All usable concepts in extension taxonomy relationships MUST be applied by tagged facts: %(elements)s."),
                    modelObject=unreportedLbElts, elements=", ".join(sorted((str(c.qname) for c in unreportedLbElts))))

    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)
    

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate ESMA',
    'version': '1.2019.07',
    'description': '''ESEF Reporting Manual Validations.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2018-19 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
}