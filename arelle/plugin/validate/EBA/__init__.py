'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
import os, sys, re
from arelle import PluginManager
from arelle import ModelDocument, XbrlConst, XmlUtil, UrlUtil, LeiUtil
from arelle.HashUtil import md5hash, Md5Sum
from arelle.ModelDtsObject import ModelConcept, ModelType, ModelLocator, ModelResource
from arelle.ModelFormulaObject import Aspect
from arelle.ModelObject import ModelObject
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelValue import qname, qnameEltPfxName
from arelle.ValidateUtr import ValidateUtr
from arelle.XbrlConst import qnEnumerationItemType
try:
    import regex as re
except ImportError:
    import re
from lxml import etree
from collections import defaultdict

qnFIndicators = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:fIndicators")
qnFilingIndicator = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:filingIndicator")
qnPercentItemType = qname("{http://www.xbrl.org/dtr/type/numeric}num:percentItemType")
qnPureItemType = qname("{http://www.xbrl.org/2003/instance}xbrli:pureItemType")
integerItemTypes = {"integerItemType", "nonPositiveIntegerItemType", "negativeIntegerItemType",
                    "longItemType", "intItemType", "shortItemType", "byteItemType",
                    "nonNegativeIntegerItemType", "unsignedLongItemType", "unsignedIntItemType",
                    "unsignedShortItemType", "unsignedByteItemType", "positiveIntegerItemType"}
schemaRefDatePattern = re.compile(r".*/([0-9]{4}-[01][0-9]-[0-3][0-9])/mod.*")


def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("EBA", "EBA"),
            ("EIOPA", "EIOPA"))

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateSetup(val, parameters=None, *args, **kwargs):
    val.validateEBA = val.validateDisclosureSystem and getattr(val.disclosureSystem, "EBA", False)
    val.validateEIOPA = val.validateDisclosureSystem and getattr(val.disclosureSystem, "EIOPA", False)
    if not (val.validateEBA or val.validateEIOPA):
        return
    
    val.validateUTR = False # do not use default UTR validation, it's at error level and not streamable
    val.utrValidator = ValidateUtr(val.modelXbrl, 
                                   "WARNING",  # EBA specifies SHOULD on UTR validation
                                   "EBA.2.23") # override utre error-severity message code

    val.isEIOPAfullVersion = False
    modelDocument = val.modelXbrl.modelDocument
    if modelDocument.type == ModelDocument.Type.INSTANCE:
        for doc, docRef in modelDocument.referencesDocument.items():
            if docRef.referenceType == "href":
                if docRef.referringModelObject.localName == "schemaRef":
                    _match = schemaRefDatePattern.match(doc.uri)
                    if _match:
                        val.isEIOPAfullVersion = _match.group(1) > "2015-02-28"
                        break
                    
    val.prefixNamespace = {}
    val.namespacePrefix = {}
    val.idObjects = {}
    
    val.typedDomainQnames = set()
    val.typedDomainElements = set()
    for modelConcept in val.modelXbrl.qnameConcepts.values():
        if modelConcept.isTypedDimension:
            typedDomainElement = modelConcept.typedDomainElement
            if isinstance(typedDomainElement, ModelConcept):
                val.typedDomainQnames.add(typedDomainElement.qname)
                val.typedDomainElements.add(typedDomainElement)
                
    val.filingIndicators = {}
    val.numFilingIndicatorTuples = 0
                
    val.cntxEntities = set()
    val.cntxDates = defaultdict(set)
    val.unusedCntxIDs = set()
    val.unusedUnitIDs = set()
    val.currenciesUsed = {}
    val.namespacePrefixesUsed = defaultdict(set)
    val.prefixesUnused = set(val.modelXbrl.modelDocument.xmlRootElement.nsmap.keys()).copy()
    val.firstFactObjectIndex = sys.maxsize
    val.firstFact = None
    val.footnotesRelationshipSet = ModelRelationshipSet(val.modelXbrl, "XBRL-footnotes")

def validateStreamingFacts(val, factsToCheck, *args, **kwargs):
    if not (val.validateEBA or val.validateEIOPA):
        return True
    validateFacts(val, factsToCheck)
    
def validateFacts(val, factsToCheck):
    # may be called in streaming batches or all at end (final) if not streaming
    
    modelXbrl = val.modelXbrl
    modelDocument = modelXbrl.modelDocument
    
    # note EBA 2.1 is in ModelDocument.py
    
    timelessDatePattern = re.compile(r"\s*([0-9]{4})-([0-9]{2})-([0-9]{2})\s*$")
    for cntx in modelXbrl.contexts.values():
        if getattr(cntx, "_batchChecked", False):
            continue # prior streaming batch already checked
        cntx._batchChecked = True
        val.cntxEntities.add(cntx.entityIdentifier)
        dateElts = XmlUtil.descendants(cntx, XbrlConst.xbrli, ("startDate","endDate","instant"))
        if any(not timelessDatePattern.match(e.textValue) for e in dateElts):
            modelXbrl.error(("EBA.2.10","EIOPA.2.10"),
                    _('Period dates must be whole dates without time or timezone: %(dates)s.'),
                    modelObject=cntx, dates=", ".join(e.text for e in dateElts))
        if cntx.isForeverPeriod:
            modelXbrl.error(("EBA.2.11","EIOPA.N.2.11"),
                    _('Forever context period is not allowed.'),
                    modelObject=cntx)
        elif cntx.isStartEndPeriod:
            modelXbrl.error(("EBA.2.13","EIOPA.N.2.11"),
                    _('Start-End (flow) context period is not allowed.'),
                    modelObject=cntx)
        elif cntx.isInstantPeriod:
            # cannot pass context object to final() below, for error logging, if streaming mode
            val.cntxDates[cntx.instantDatetime].add(modelXbrl if getattr(val.modelXbrl, "isStreamingMode", False)
                                                    else cntx)
        if cntx.hasSegment:
            modelXbrl.error(("EBA.2.14","EIOPA.N.2.14"),
                _("Contexts MUST NOT contain xbrli:segment values: %(cntx)s.'"),
                modelObject=cntx, cntx=cntx.id)
        if cntx.nonDimValues("scenario"):
            modelXbrl.error(("EBA.2.15","EIOPA.S.2.15" if val.isEIOPAfullVersion else "EIOPA.N.2.15"),
                _("Contexts MUST NOT contain non-dimensional xbrli:scenario values: %(cntx)s.'"),
                modelObject=cntx, cntx=cntx.id, 
                messageCodes=("EBA.2.15","EIOPA.N.2.15","EIOPA.S.2.15"))
        val.unusedCntxIDs.add(cntx.id)

    for unit in modelXbrl.units.values():
        if getattr(unit, "_batchChecked", False):
            continue # prior streaming batch already checked
        unit._batchChecked = True
        val.unusedUnitIDs.add(unit.id)
        
    factsByQname = defaultdict(set) # top level for this
    for f in factsToCheck: 
        factsByQname[f.qname].add(f)
        val.unusedCntxIDs.discard(f.contextID)
        val.unusedUnitIDs.discard(f.unitID)
        if f.objectIndex < val.firstFactObjectIndex:
            val.firstFactObjectIndex = f.objectIndex
            val.firstFact = f
        

    for fIndicators in factsByQname[qnFIndicators]:
        val.numFilingIndicatorTuples += 1
        for fIndicator in fIndicators.modelTupleFacts:
            _value = (getattr(fIndicator, "xValue", None) or fIndicator.value) # use validated xValue if DTS else value for skipDTS 
            if _value in val.filingIndicators:
                modelXbrl.error(("EBA.1.6.1", "EIOPA.1.6.1"),
                        _('Multiple filing indicators facts for indicator %(filingIndicator)s.'),
                        modelObject=(fIndicator, val.filingIndicators[_value]), filingIndicator=_value)
            val.filingIndicators[_value] = fIndicator.get("{http://www.eurofiling.info/xbrl/ext/filing-indicators}filed", "true") in ("true", "1")
            val.unusedCntxIDs.discard(fIndicator.contextID)
            cntx = fIndicator.context
            if cntx is not None and (cntx.hasSegment or cntx.hasScenario):
                modelXbrl.error("EIOPA.N.1.6.d" if val.isEIOPAfullVersion else "EIOPA.S.1.6.d",
                        _('Filing indicators must not contain segment or scenario elements %(filingIndicator)s.'),
                        modelObject=fIndicator, filingIndicator=_value)
        if fIndicators.objectIndex > val.firstFactObjectIndex:
            modelXbrl.warning("EIOPA.1.6.2",
                    _('Filing indicators should precede first fact %(firstFact)s.'),
                    modelObject=(fIndicators, val.firstFact), firstFact=val.firstFact.qname)
    
    if val.isEIOPAfullVersion:
        for fIndicator in factsByQname[qnFilingIndicator]:
            if fIndicator.getparent().qname == XbrlConst.qnXbrliXbrl:
                _isPos = fIndicator.get("{http://www.eurofiling.info/xbrl/ext/filing-indicators}filed", "true") in ("true", "1")
                _value = (getattr(fIndicator, "xValue", None) or fIndicator.value) # use validated xValue if DTS else value for skipDTS 
                modelXbrl.error("EIOPA.1.6.a" if _isPos else "EIOPA.1.6.b",
                        _('Filing indicators must be in a tuple %(filingIndicator)s.'),
                        modelObject=fIndicator, filingIndicator=_value,
                        messageCodes=("EIOPA.1.6.a", "EIOPA.1.6.b"))
                
    otherFacts = {} # (contextHash, unitHash, xmlLangHash) : fact
    nilFacts = []
    # removed in current draft: stringFactsWithoutXmlLang = []
    nonMonetaryNonPureFacts = []
    for qname, facts in factsByQname.items():
        for f in facts:
            if modelXbrl.skipDTS:
                c = f.qname.localName[0]
                isNumeric = c in ('m', 'p', 'r', 'i')
                isMonetary = c == 'm'
                isInteger = c == 'i'
                isPercent = c == 'p'
                isString = c == 's'
                isEnum = c == 'e'
            else:
                concept = f.concept
                if concept is not None:
                    isNumeric = concept.isNumeric
                    isMonetary = concept.isMonetary
                    isInteger = concept.baseXbrliType in integerItemTypes
                    isPercent = concept.typeQname in (qnPercentItemType, qnPureItemType)
                    isString = concept.baseXbrliType in ("stringItemType", "normalizedStringItemType")
                    isEnum = concept.typeQname == qnEnumerationItemType
                else:
                    isNumeric = isString = isEnum = False # error situation
            k = (f.getparent().objectIndex,
                 f.qname,
                 f.context.contextDimAwareHash if f.context is not None else None,
                 f.unit.hash if f.unit is not None else None,
                 hash(f.xmlLang))
            if f.qname == qnFIndicators and val.validateEIOPA:
                pass
            elif k not in otherFacts:
                otherFacts[k] = {f}
            else:
                matches = [o
                           for o in otherFacts[k]
                           if (f.getparent().objectIndex == o.getparent().objectIndex and
                               f.qname == o.qname and
                               f.context.isEqualTo(o.context) if f.context is not None and o.context is not None else True) and
                               # (f.unit.isEqualTo(o.unit) if f.unit is not None and o.unit is not None else True) and
                              (f.xmlLang == o.xmlLang)]
                if matches:
                    contexts = [f.contextID] + [o.contextID for o in matches]
                    modelXbrl.error(("EBA.2.16", "EIOPA.S.2.16" if val.isEIOPAfullVersion else "EIOPA.S.2.16.a"),
                                    _('Facts are duplicates %(fact)s contexts %(contexts)s.'),
                                    modelObject=[f] + matches, fact=f.qname, contexts=', '.join(contexts),
                                    messageCodes=("EBA.2.16", "EIOPA.S.2.16", "EIOPA.S.2.16.a"))
                else:
                    otherFacts[k].add(f)
            if isNumeric:
                if f.precision:
                    modelXbrl.error(("EBA.2.17", "EIOPA.2.18.a"),
                        _("Numeric fact %(fact)s of context %(contextID)s has a precision attribute '%(precision)s'"),
                        modelObject=f, fact=f.qname, contextID=f.contextID, precision=f.precision)
                if f.decimals and not f.isNil:
                    if f.decimals == "INF":
                        if not val.isEIOPAfullVersion:
                            modelXbrl.error("EIOPA.S.2.18.f",
                                _("Monetary fact %(fact)s of context %(contextID)s has a decimal attribute INF: '%(decimals)s'"),
                                modelObject=f, fact=f.qname, contextID=f.contextID, decimals=f.decimals)
                    else:
                        try:
                            xValue = f.xValue
                            dec = int(f.decimals)
                            if isMonetary:
                                if dec < -3:
                                    modelXbrl.error(("EBA.2.18","EIOPA.S.2.18.c"),
                                        _("Monetary fact %(fact)s of context %(contextID)s has a decimals attribute < -3: '%(decimals)s'"),
                                        modelObject=f, fact=f.qname, contextID=f.contextID, decimals=f.decimals)
                                else: # apply dynamic decimals check
                                    if  -.1 < xValue < .1: dMin = 2
                                    elif -1 < xValue < 1: dMin = 1
                                    elif -10 < xValue < 10: dMin = 0
                                    elif -100 < xValue < 100: dMin = -1
                                    elif -1000 < xValue < 1000: dMin = -2
                                    else: dMin = -3
                                    if dMin > dec:
                                        modelXbrl.warning("EIOPA:factDecimalsWarning",
                                            _("Monetary fact %(fact)s of context %(contextID)s value %(value)s has an imprecise decimals attribute: %(decimals)s, minimum is %(mindec)s"),
                                            modelObject=f, fact=f.qname, contextID=f.contextID, value=xValue, decimals=f.decimals, mindec=dMin)
                            elif isInteger:
                                if dec != 0:
                                    modelXbrl.error(("EBA.2.18","EIOPA.S.2.18.d"),
                                        _("Integer fact %(fact)s of context %(contextID)s has a decimals attribute \u2260 0: '%(decimals)s'"),
                                        modelObject=f, fact=f.qname, contextID=f.contextID, decimals=f.decimals)
                            elif isPercent:
                                if dec < 4:
                                    modelXbrl.error(("EBA.2.18","EIOPA.S.2.18.e"),
                                        _("Percent fact %(fact)s of context %(contextID)s has a decimals attribute < 4: '%(decimals)s'"),
                                        modelObject=f, fact=f.qname, contextID=f.contextID, decimals=f.decimals)
                            else:
                                if -.001 < xValue < .001: dMin = 4
                                elif -.01 < xValue < .01: dMin = 3
                                elif -.1 < xValue < .1: dMin = 2
                                elif  -1 < xValue < 1: dMin = 1
                                else: dMin = 0
                                if dMin > dec:
                                    modelXbrl.warning("EIOPA:factDecimalsWarning",
                                        _("Numeric fact %(fact)s of context %(contextID)s value %(value)s has an imprecise decimals attribute: %(decimals)s, minimum is %(mindec)s"),
                                        modelObject=f, fact=f.qname, contextID=f.contextID, value=xValue, decimals=f.decimals, mindec=dMin)
                        except (AttributeError, ValueError):
                            pass # should have been reported as a schema error by loader
                        '''' (not intended by EBA 2.18, paste here is from EFM)
                        if not f.isNil and getattr(f,"xValid", 0) == 4:
                            try:
                                insignificance = insignificantDigits(f.xValue, decimals=f.decimals)
                                if insignificance: # if not None, returns (truncatedDigits, insiginficantDigits)
                                    modelXbrl.error(("EFM.6.05.37", "GFM.1.02.26"),
                                        _("Fact %(fact)s of context %(contextID)s decimals %(decimals)s value %(value)s has nonzero digits in insignificant portion %(insignificantDigits)s."),
                                        modelObject=f1, fact=f1.qname, contextID=f1.contextID, decimals=f1.decimals, 
                                        value=f1.xValue, truncatedDigits=insignificance[0], insignificantDigits=insignificance[1])
                            except (ValueError,TypeError):
                                modelXbrl.error(("EBA.2.18"),
                                    _("Fact %(fact)s of context %(contextID)s decimals %(decimals)s value %(value)s causes Value Error exception."),
                                    modelObject=f1, fact=f1.qname, contextID=f1.contextID, decimals=f1.decimals, value=f1.value)
                        '''
                unit = f.unit
                if unit is not None:
                    if isMonetary:
                        if unit.measures[0]:
                            val.currenciesUsed[unit.measures[0][0]] = unit
                    elif not unit.isSingleMeasure or unit.measures[0][0] != XbrlConst.qnXbrliPure:
                        nonMonetaryNonPureFacts.append(f)
            if isEnum:
                _eQn = getattr(f,"xValue", None) or qnameEltPfxName(f, f.value)
                if _eQn:
                    val.namespacePrefixesUsed[_eQn.namespaceURI].add(_eQn.prefix)
                    val.prefixesUnused.discard(_eQn.prefix)
            ''' removed in current draft
            elif isString: 
                if not f.xmlLang:
                    stringFactsWithoutXmlLang.append(f)
            '''
                        
            if f.isNil:
                nilFacts.append(f)
                
            if val.footnotesRelationshipSet.fromModelObject(f):
                modelXbrl.warning("EIOPA.S.19",
                    _("Fact %(fact)s of context %(contextID)s has footnotes.'"),
                    modelObject=f, fact=f.qname, contextID=f.contextID)
                
    if nilFacts:
        modelXbrl.error(("EBA.2.19", "EIOPA.S.2.19"),
                _('Nil facts MUST NOT be present in the instance: %(nilFacts)s.'),
                modelObject=nilFacts, nilFacts=", ".join(str(f.qname) for f in nilFacts))
    ''' removed in current draft
    if stringFactsWithoutXmlLang:
        modelXbrl.error("EBA.2.20",
                        _("String facts need to report xml:lang: '%(langLessFacts)s'"),
                        modelObject=stringFactsWithoutXmlLang, langLessFacts=", ".join(set(str(f.qname) for f in stringFactsWithoutXmlLang)))
    '''
    if nonMonetaryNonPureFacts:
        modelXbrl.error(("EBA.3.2","EIOPA.3.2.a"),
                        _("Non monetary (numeric) facts MUST use the pure unit: '%(langLessFacts)s'"),
                        modelObject=nonMonetaryNonPureFacts, langLessFacts=", ".join(set(str(f.qname) for f in nonMonetaryNonPureFacts)))

    val.utrValidator.validateFacts() # validate facts for UTR at logLevel WARNING
    
    unitHashes = {}
    for unit in modelXbrl.units.values():
        h = unit.hash
        if h in unitHashes and unit.isEqualTo(unitHashes[h]):
            modelXbrl.warning("EBA.2.21",
                _("Duplicate units SHOULD NOT be reported, units %(unit1)s and %(unit2)s have same measures.'"),
                modelObject=(unit, unitHashes[h]), unit1=unit.id, unit2=unitHashes[h].id)
            if not getattr(modelXbrl, "isStreamingMode", False):
                modelXbrl.error("EIOPA.2.21",
                    _("Duplicate units MUST NOT be reported, units %(unit1)s and %(unit2)s have same measures.'"),
                    modelObject=(unit, unitHashes[h]), unit1=unit.id, unit2=unitHashes[h].id)
        else:
            unitHashes[h] = unit
        for _measures in unit.measures:
            for _measure in _measures:
                val.namespacePrefixesUsed[_measure.namespaceURI].add(_measure.prefix)
                val.prefixesUnused.discard(_measure.prefix)
                
    del unitHashes
    
    cntxHashes = {}
    for cntx in modelXbrl.contexts.values():
        h = cntx.contextDimAwareHash
        if h in cntxHashes and cntx.isEqualTo(cntxHashes[h]):
            if not getattr(modelXbrl, "isStreamingMode", False):
                modelXbrl.log("WARNING" if val.isEIOPAfullVersion else "ERROR",
                    "EIOPA.S.2.7.b",
                    _("Duplicate contexts MUST NOT be reported, contexts %(cntx1)s and %(cntx2)s are equivalent.'"),
                    modelObject=(cntx, cntxHashes[h]), cntx1=cntx.id, cntx2=cntxHashes[h].id)
        else:
            cntxHashes[h] = cntx
        for _dim in cntx.qnameDims.values():
            _dimQn = _dim.dimensionQname
            val.namespacePrefixesUsed[_dimQn.namespaceURI].add(_dimQn.prefix)
            val.prefixesUnused.discard(_dimQn.prefix)
            if _dim.isExplicit:
                _memQn = _dim.memberQname
            else:
                _memQn = _dim.typedMember.qname
            if _memQn:
                val.namespacePrefixesUsed[_memQn.namespaceURI].add(_memQn.prefix)
                val.prefixesUnused.discard(_memQn.prefix)

    for elt in modelDocument.xmlRootElement.iter():
        if isinstance(elt, ModelObject): # skip comments and processing instructions
            val.namespacePrefixesUsed[elt.qname.namespaceURI].add(elt.qname.prefix)
            val.prefixesUnused.discard(elt.qname.prefix)
            for attrTag in elt.keys():
                if attrTag.startswith("{"):
                    _prefix, _NS, _localName = XmlUtil.clarkNotationToPrefixNsLocalname(elt, attrTag, isAttribute=True)
                    if _prefix:
                        val.namespacePrefixesUsed[_NS].add(_prefix)
                        val.prefixesUnused.discard(_prefix)
                   
def validateNonStreamingFinish(val, *args, **kwargs):
    # non-streaming EBA checks, ignore when streaming (first all from ValidateXbrl.py)
    if not getattr(val.modelXbrl, "isStreamingMode", False):
        final(val)
        
def validateStreamingFinish(val, *args, **kwargs):
    final(val)  # always finish validation when streaming
    
def final(val):
    if not (val.validateEBA or val.validateEIOPA):
        return
    
    modelXbrl = val.modelXbrl
    modelDocument = modelXbrl.modelDocument

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)
    
    if modelDocument.type == ModelDocument.Type.INSTANCE and (val.validateEBA or val.validateEIOPA):

        if not modelDocument.uri.endswith(".xbrl"):
            modelXbrl.warning(("EBA.1.1", "EIOPA.S.1.1.a"),
                    _('XBRL instance documents SHOULD use the extension ".xbrl" but it is "%(extension)s"'),
                    modelObject=modelDocument, extension=os.path.splitext(modelDocument.basename)[1])
        if modelDocument.documentEncoding.lower() not in ("utf-8", "utf-8-sig"):
            modelXbrl.error(("EBA.1.4", "EIOPA.1.4"),
                    _('XBRL instance documents MUST use "UTF-8" encoding but is "%(xmlEncoding)s"'),
                    modelObject=modelDocument, xmlEncoding=modelDocument.documentEncoding)

        schemaRefElts = []
        schemaRefFileNames = []
        for doc, docRef in modelDocument.referencesDocument.items():
            if docRef.referenceType == "href":
                if docRef.referringModelObject.localName == "schemaRef":
                    schemaRefElts.append(docRef.referringModelObject)
                    schemaRefFileNames.append(doc.basename)
                    if not UrlUtil.isAbsolute(doc.uri):
                        modelXbrl.error(("EBA.2.2", "EBA.S.1.5.a" if val.isEIOPAfullVersion else "EBA.S.1.5.b"),
                                _('The link:schemaRef element in submitted instances MUST resolve to the full published entry point URL: %(url)s.'),
                                modelObject=docRef.referringModelObject, url=doc.uri,
                                messageCodes=("EBA.2.2", "EBA.S.1.5.a","EBA.S.1.5.b"))
                elif docRef.referringModelObject.localName == "linkbaseRef":
                    modelXbrl.error(("EBA.2.3","EBA.S.1.5.a"),
                            _('The link:linkbaseRef element is not allowed: %(fileName)s.'),
                            modelObject=docRef.referringModelObject, fileName=doc.basename)
        _numSchemaRefs = len(XmlUtil.children(modelDocument.xmlRootElement, XbrlConst.link, "schemaRef"))
        if _numSchemaRefs > 1:
            modelXbrl.error(("EIOPA.S.1.5.a", "EBA.1.5"),
                    _('XBRL instance documents MUST reference only one entry point schema but %(numEntryPoints)s were found: %(entryPointNames)s'),
                    modelObject=modelDocument, numEntryPoints=_numSchemaRefs, entryPointNames=', '.join(sorted(schemaRefFileNames)))
        ### check entry point names appropriate for filing indicator (DPM DB?)
        
        if len(schemaRefElts) != 1:
            modelXbrl.error("EBA.2.3",
                    _('Any reported XBRL instance document MUST contain only one xbrli:xbrl/link:schemaRef node, but %(entryPointCount)s.'),
                    modelObject=schemaRefElts, entryPointCount=len(schemaRefElts))
        # non-streaming EBA checks
        if not getattr(modelXbrl, "isStreamingMode", False):
            validateFacts(val, modelXbrl.facts)

            # check sum of fact md5s (otherwise checked in streaming process)
            xbrlFactsCheckVersion = None
            expectedSumOfFactMd5s = None
            for pi in modelDocument.xmlRootElement.getchildren():
                if isinstance(pi, etree._ProcessingInstruction) and pi.target == "xbrl-facts-check":
                    _match = re.search("([\\w-]+)=[\"']([^\"']+)[\"']", pi.text)
                    if _match:
                        _matchGroups = _match.groups()
                        if len(_matchGroups) == 2:
                            if _matchGroups[0] == "version":
                                xbrlFactsCheckVersion = _matchGroups[1]
                            elif _matchGroups[0] == "sum-of-fact-md5s":
                                try:
                                    expectedSumOfFactMd5s = Md5Sum(_matchGroups[1])
                                except ValueError:
                                    modelXbrl.error("EIOPA:xbrlFactsCheckError",
                                            _("Invalid sum-of-md5s %(sumOfMd5)s"),
                                            modelObject=modelXbrl, sumOfMd5=_matchGroups[1])
            if xbrlFactsCheckVersion and expectedSumOfFactMd5s:
                sumOfFactMd5s = Md5Sum()
                for f in modelXbrl.factsInInstance:
                    sumOfFactMd5s += f.md5sum
                if sumOfFactMd5s != expectedSumOfFactMd5s:
                    modelXbrl.warning("EIOPA:xbrlFactsCheckWarning",
                            _("XBRL facts sum of md5s expected %(expectedMd5)s not matched to actual sum %(actualMd5Sum)s"),
                            modelObject=modelXbrl, expectedMd5=expectedSumOfFactMd5s, actualMd5Sum=sumOfFactMd5s)
                else:
                    modelXbrl.info("info",
                            _("Successful XBRL facts sum of md5s."),
                            modelObject=modelXbrl)
            
        if not val.filingIndicators:
            modelXbrl.error(("EBA.1.6", "EIOPA.1.6.a"),
                    _('Missing filing indicators.  Reported XBRL instances MUST include appropriate (positive) filing indicator elements'),
                    modelObject=modelDocument)
        elif all(filed == False for filed in val.filingIndicators.values()):
            modelXbrl.error(("EBA.1.6", "EIOPA.1.6.a"),
                    _('All filing indicators are filed="false".  Reported XBRL instances MUST include appropriate (positive) filing indicator elements'),
                    modelObject=modelDocument)
    
        if val.numFilingIndicatorTuples > 1:
            modelXbrl.warning("EBA.1.6.2|EIOPA.1.6.2",                            
                    _('Multiple filing indicators tuples when not in streaming mode (info).'),
                    modelObject=modelXbrl.factsByQname[qnFIndicators])

        if len(val.cntxDates) > 1:
            modelXbrl.error("EBA.2.13",
                    _('Contexts must have the same date: %(dates)s.'),
                    # when streaming values are no longer available, but without streaming they can be logged
                    modelObject=set(_cntx for _cntxs in val.cntxDates.values() for _cntx in _cntxs), 
                    dates=', '.join(XmlUtil.dateunionValue(_dt, subtractOneDay=True)
                                                           for _dt in val.cntxDates.keys()))

        if val.unusedCntxIDs:
            modelXbrl.warning(("EBA.2.7", "EIOPA.2.7"),
                    _('Unused xbrli:context nodes SHOULD NOT be present in the instance: %(unusedContextIDs)s.'),
                    modelObject=[modelXbrl.contexts[unusedCntxID] for unusedCntxID in val.unusedCntxIDs if unusedCntxID in modelXbrl.contexts], 
                    unusedContextIDs=", ".join(sorted(val.unusedCntxIDs)))
    
        if len(val.cntxEntities) > 1:
            modelXbrl.warning(("EBA.2.9", "EIOPA.2.9"),
                    _('All entity identifiers and schemes must be the same, %(count)s found: %(entities)s.'),
                    modelObject=modelDocument, count=len(val.cntxEntities), 
                    entities=", ".join(sorted(str(cntxEntity) for cntxEntity in val.cntxEntities)))
            
        for _scheme, _LEI in val.cntxEntities:
            if (_scheme in ("http://standard.iso.org/iso/17442", "LEI") or
                (not val.isEIOPAfullVersion and _scheme == "PRE-LEI")):
                result = LeiUtil.checkLei(_LEI)
                if result == LeiUtil.LEI_INVALID_LEXICAL:
                    modelXbrl.error("EIOPA.S.2.8.c",
                        _("Context has lexically invalid LEI %(lei)s."),
                        modelObject=modelDocument, lei=_LEI)
                elif result == LeiUtil.LEI_INVALID_CHECKSUM:
                    modelXbrl.error("EIOPA.S.2.8.c",
                        _("Context has LEI checksum error in %(lei)s."),
                        modelObject=modelDocument, lei=_LEI)
            elif _scheme == "SC":
                pass # anything is ok for Specific Code
            else:
                modelXbrl.error("EIOPA.S.2.8.c",
                    _("Context has unrecognized entity scheme %(scheme)s."),
                    modelObject=modelDocument, scheme=_scheme)
        
        if val.unusedUnitIDs:
            modelXbrl.warning(("EBA.2.22", "EIOPA.2.22"),
                    _('Unused xbrli:unit nodes SHOULD NOT be present in the instance: %(unusedUnitIDs)s.'),
                    modelObject=[modelXbrl.units[unusedUnitID] for unusedUnitID in val.unusedUnitIDs if unusedUnitID in modelXbrl.units], 
                    unusedUnitIDs=", ".join(sorted(val.unusedUnitIDs)))
                    
        if len(val.currenciesUsed) > 1:
            modelXbrl.error(("EBA.3.1","EIOPA.3.1"),
                _("There MUST be only one currency but %(numCurrencies)s were found: %(currencies)s.'"),
                modelObject=val.currenciesUsed.values(), numCurrencies=len(val.currenciesUsed), currencies=", ".join(str(c) for c in val.currenciesUsed.keys()))
            
        if val.prefixesUnused:
            modelXbrl.warning(("EBA.3.4", "EIOPA.3.4"),
                _("There SHOULD be no unused prefixes but these were declared: %(unusedPrefixes)s.'"),
                modelObject=modelDocument, unusedPrefixes=', '.join(sorted(val.prefixesUnused)))
        for ns, prefixes in val.namespacePrefixesUsed.items():
            nsDocs = modelXbrl.namespaceDocs.get(ns)
            if nsDocs:
                for nsDoc in nsDocs:
                    nsDocPrefix = XmlUtil.xmlnsprefix(nsDoc.xmlRootElement, ns)
                    if any(prefix != nsDocPrefix for prefix in prefixes if prefix is not None):
                        modelXbrl.warning(("EBA.3.5", "EIOPA.3.5"),
                            _("Prefix for namespace %(namespace)s is %(declaredPrefix)s but these were found %(foundPrefixes)s"),
                            modelObject=modelDocument, namespace=ns, declaredPrefix=nsDocPrefix, foundPrefixes=', '.join(sorted(prefixes - {None})))
   
    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)

    del val.prefixNamespace, val.namespacePrefix, val.idObjects, val.typedDomainElements
    del val.utrValidator, val.firstFact, val.footnotesRelationshipSet
                
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate EBA, EIOPA',
    'version': '1.2',
    'description': 'EBA (2.3), EIOPA (2.0.0) Filing Rules Validation.',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2015 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateSetup,
    'Validate.XBRL.Finally': validateNonStreamingFinish,
    'Streaming.ValidateFacts': validateStreamingFacts,
    'Streaming.ValidateFinish': validateStreamingFinish,
}
