'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import PluginManager
from arelle import ModelDocument, XbrlConst, XmlUtil, UrlUtil
from arelle.HashUtil import md5hash, Md5Sum
from arelle.ModelDtsObject import ModelConcept, ModelType, ModelLocator, ModelResource
from arelle.ModelFormulaObject import Aspect
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname
try:
    import regex as re
except ImportError:
    import re
from lxml import etree
from collections import defaultdict

qnFIndicators = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:fIndicators")
qnFilingIndicator = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:filingIndicator")
qnPercentItemType = qname("{http://www.xbrl.org/dtr/type/numeric}num:percentItemType")
integerItemTypes = {"integerItemType", "nonPositiveIntegerItemType", "negativeIntegerItemType",
                    "longItemType", "intItemType", "shortItemType", "byteItemType",
                    "nonNegativeIntegerItemType", "unsignedLongItemType", "unsignedIntItemType",
                    "unsignedShortItemType", "unsignedByteItemType", "positiveIntegerItemType"}

def dislosureSystemTypes(disclosureSystem):
    return (("EBA", "EBA"),
            ("EIOPA", "EIOPA"))

def disclosureSystemConfigURL(disclosureSystem):
    return os.path.join(os.path.dirname(__file__), "validateEBAconfig.xml")

def setup(val):
    val.validateEBA = val.validateDisclosureSystem and getattr(val.disclosureSystem, "EBA", False)
    val.validateEIOPA = val.validateDisclosureSystem and getattr(val.disclosureSystem, "EIOPA", False)
    if not (val.validateEBA or val.validateEIOPA):
        return

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
                
    
'''
def factCheck(val, fact):
    concept = fact.concept
    context = fact.context
    if concept is None or context is None:
        return # not checkable
    
    try:
    except Exception as err:
'''
    
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
            modelXbrl.warning("EBA.1.1",
                    _('XBRL instance documents SHOULD use the extension ".xbrl" but it is "%(extension)s"'),
                    modelObject=modelDocument, xmlEncoding=os.path.splitext(modelDocument.basename)[1])
        if modelDocument.documentEncoding.lower() not in ("utf-8", "utf-8-sig"):
            modelXbrl.error("EBA.1.4",
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
                        modelXbrl.error("EBA.2.2",
                                _('The link:schemaRef element in submitted instances MUST resolve to the full published entry point URL: %(url)s.'),
                                modelObject=docRef.referringModelObject, url=doc.uri)
                elif docRef.referringModelObject.localName == "linkbaseRef":
                    modelXbrl.error("EBA.2.3",
                            _('The link:linkbaseRef element is not allowed: %(fileName)s.'),
                            modelObject=docRef.referringModelObject, fileName=doc.basename)
        if len(schemaRefFileNames) > 1:
            modelXbrl.error("EBA.1.5",
                    _('XBRL instance documents MUST reference only one entry point schema but %(numEntryPoints)s were found: %(entryPointNames)s'),
                    modelObject=modelDocument, numEntryPoints=len(schemaRefFileNames), entryPointNames=', '.join(sorted(schemaRefFileNames)))
        ### check entry point names appropriate for filing indicator (DPM DB?)
        
        if len(schemaRefElts) != 1:
            modelXbrl.error("EBA.2.3",
                    _('Any reported XBRL instance document MUST contain only one xbrli:xbrl/link:schemaRef node, but %(entryPointCount)s.'),
                    modelObject=schemaRefElts, entryPointCount=len(schemaRefElts))
        filingIndicators = {}
        for fIndicator in modelXbrl.factsByQname(qnFilingIndicator, ()):
            _value = (fIndicator.xValue or fIndicator.value) # use validated xValue if DTS else value for skipDTS 
            if _value in filingIndicators:
                modelXbrl.error("EBA.1.6.1",
                        _('Multiple filing indicators facts for indicator %(filingIndicator)s.'),
                        modelObject=(fIndicator, filingIndicators[_value]), filingIndicator=_value)
            filingIndicators[_value] = fIndicator
        
        if not filingIndicators:
            modelXbrl.error("EBA.1.6",
                    _('Missing filing indicators.  Reported XBRL instances MUST include appropriate filing indicator elements'),
                    modelObject=modelDocument)
            
        # non-streaming EBA checks
        if not getattr(modelXbrl, "isStreamingMode", False):
            
            # check sum of fact md5s
            xbrlFactsCheckVersion = None
            expectedSumOfFactMd5s = None
            for pi in modelXbrl.modelDocument.xmlRootElement.getchildren():
                if isinstance(pi, etree._ProcessingInstruction) and pi.target == "xbrl-facts-check":
                    if "version" in pi.attrib:
                        xbrlFactsCheckVersion = pi.attrib["version"]
                    elif "sum-of-fact-md5s" in pi.attrib:
                        sumOfFactMd5s = Md5Sum(pi.attrib["sum-of-fact-md5s"])
            if xbrlFactsCheckVersion and sumOfFactMd5s:
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
            
            numFilingIndicatorTuples = len(modelXbrl.factsByQname(qnFIndicators, ()))
            if numFilingIndicatorTuples > 1:
                modelXbrl.info("EBA.1.6.2",                            
                        _('Multiple filing indicators tuples when not in streaming mode (info).'),
                        modelObject=modelXbrl.factsByQname(qnFIndicators))
                        
            # note EBA 2.1 is in ModelDocument.py
            
            cntxIDs = set()
            cntxEntities = set()
            cntxDates = defaultdict(list)
            timelessDatePattern = re.compile(r"\s*([0-9]{4})-([0-9]{2})-([0-9]{2})\s*$")
            for cntx in modelXbrl.contexts.values():
                cntxIDs.add(cntx.id)
                cntxEntities.add(cntx.entityIdentifier)
                dateElts = XmlUtil.descendants(cntx, XbrlConst.xbrli, ("startDate","endDate","instant"))
                if any(not timelessDatePattern.match(e.textValue) for e in dateElts):
                    modelXbrl.error("EBA.2.10",
                            _('Period dates must be whole dates without time or timezone: %(dates)s.'),
                            modelObject=cntx, dates=", ".join(e.text for e in dateElts))
                if cntx.isForeverPeriod:
                    modelXbrl.error("EBA.2.11",
                            _('Forever context period is not allowed.'),
                            modelObject=cntx)
                elif cntx.isStartEndPeriod:
                    modelXbrl.error("EBA.2.13",
                            _('Start-End (flow) context period is not allowed.'),
                            modelObject=cntx)
                elif cntx.isInstantPeriod:
                    cntxDates[cntx.instantDatetime].append(cntx)
                if XmlUtil.hasChild(cntx, XbrlConst.xbrli, "segment"):
                    modelXbrl.error("EBA.2.14",
                        _("The segment element not allowed in context Id: %(context)s"),
                        modelObject=cntx, context=cntx.contextID)
                for scenElt in XmlUtil.descendants(cntx, XbrlConst.xbrli, "scenario"):
                    childTags = ", ".join([child.prefixedName for child in scenElt.iterchildren()
                                           if isinstance(child,ModelObject) and 
                                           child.tag != "{http://xbrl.org/2006/xbrldi}explicitMember" and
                                           child.tag != "{http://xbrl.org/2006/xbrldi}typedMember"])
                    if len(childTags) > 0:
                        modelXbrl.error("EBA.2.15",
                            _("Scenario of context Id %(context)s has disallowed content: %(content)s"),
                            modelObject=cntx, context=cntx.id, content=childTags)
            if len(cntxDates) > 1:
                modelXbrl.error("EBA.2.13",
                        _('Contexts must have the same date: %(dates)s.'),
                        modelObject=[_cntx for _cntxs in cntxDates.values() for _cntx in _cntxs], 
                        dates=', '.join(XmlUtil.dateunionValue(_dt, subtractOneDay=True)
                                                               for _dt in cntxDates.keys()))
                
            unusedCntxIDs = cntxIDs - {fact.contextID 
                                       for fact in modelXbrl.factsInInstance
                                       if fact.contextID} # skip tuples
            if unusedCntxIDs:
                modelXbrl.warning("EBA.2.7",
                        _('Unused xbrli:context nodes SHOULD NOT be present in the instance: %(unusedContextIDs)s.'),
                        modelObject=[modelXbrl.contexts[unusedCntxID] for unusedCntxID in unusedCntxIDs], 
                        unusedContextIDs=", ".join(sorted(unusedCntxIDs)))
    
            if len(cntxEntities) > 1:
                modelXbrl.warning("EBA.2.9",
                        _('All entity identifiers and schemes must be the same, %(count)s found: %(entities)s.'),
                        modelObject=modelDocument, count=len(cntxEntities), 
                        entities=", ".join(sorted(str(cntxEntity) for cntxEntity in cntxEntities)))
                
            otherFacts = {} # (contextHash, unitHash, xmlLangHash) : fact
            nilFacts = []
            stringFactsWithoutXmlLang = []
            nonMonetaryNonPureFacts = []
            unitIDsUsed = set()
            currenciesUsed = {}
            for qnameString, facts in modelXbrl.factsByQnameAll():
                for f in facts:
                    if modelXbrl.skipDTS:
                        c = f.qname.localName[0]
                        isNumeric = c in ('m', 'p', 'i')
                        isMonetary = c == 'm'
                        isInteger = c == 'i'
                        isPercent = c == 'p'
                        isString = c == 's'
                    else:
                        concept = f.concept
                        if concept is not None:
                            isNumeric = concept.isNumeric
                            isMonetary = concept.isMonetary
                            isInteger = concept.baseXbrliType in integerItemTypes
                            isPercent = concept.typeQname == qnPercentItemType
                            isString = concept.baseXbrliType in ("stringItemType", "normalizedStringItemType")
                        else:
                            isNumeric = isString = False # error situation
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
                                      (f.unit.isEqualTo(o.unit) if f.unit is not None and o.unit is not None else True) and
                                      (f.xmlLang == o.xmlLang)]
                        if matches:
                            contexts = [f.contextID] + [o.contextID for o in matches]
                            modelXbrl.error("EBA.2.16",
                                            _('Facts are duplicates %(fact)s contexts %(contexts)s.'),
                                            modelObject=[f] + matches, fact=f.qname, contexts=', '.join(contexts))
                        else:
                            otherFacts[k].add(f)
                    if isNumeric:
                        if f.precision:
                            modelXbrl.error("EBA.2.17",
                                _("Numeric fact %(fact)s of context %(contextID)s has a precision attribute '%(precision)s'"),
                                modelObject=f, fact=f.qname, contextID=f.contextID, precision=f.precision)
                        if f.decimals and f.decimals != "INF":
                            try:
                                dec = int(f.decimals)
                                if isMonetary:
                                    if dec < -3:
                                        modelXbrl.error("EBA.2.17",
                                            _("Monetary fact %(fact)s of context %(contextID)s has a decimal attribute < -3: '%(decimals)s'"),
                                            modelObject=f, fact=f.qname, contextID=f.contextID, decimals=f.decimals)
                                elif isInteger:
                                    if dec != 0:
                                        modelXbrl.error("EBA.2.17",
                                            _("Integer fact %(fact)s of context %(contextID)s has a decimal attribute \u2260 0: '%(decimals)s'"),
                                            modelObject=f, fact=f.qname, contextID=f.contextID, decimals=f.decimals)
                                elif isPercent:
                                    if dec < 4:
                                        modelXbrl.error("EBA.2.17",
                                            _("Percent fact %(fact)s of context %(contextID)s has a decimal attribute < 4: '%(decimals)s'"),
                                            modelObject=f, fact=f.qname, contextID=f.contextID, decimals=f.decimals)
                            except ValueError:
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
                                    currenciesUsed[unit.measures[0][0]] = unit
                            elif not unit.isSingleMeasure or unit.measures[0][0] != XbrlConst.qnXbrliPure:
                                nonMonetaryNonPureFacts.append(f)
                    elif isString: 
                        if not f.xmlLang:
                            stringFactsWithoutXmlLang.append(f)
                                
                    if f.unitID is not None:
                        unitIDsUsed.add(f.unitID)
                    if f.isNil:
                        nilFacts.append(f)
                        
            if nilFacts:
                modelXbrl.error("EBA.2.19",
                        _('Nil facts MUST NOT be present in the instance: %(nilFacts)s.'),
                        modelObject=nilFacts, nilFacts=", ".join(str(f.qname) for f in nilFacts))
            if stringFactsWithoutXmlLang:
                modelXbrl.error("EBA.2.20",
                                _("String facts need to report xml:lang: '%(langLessFacts)s'"),
                                modelObject=stringFactsWithoutXmlLang, langLEssFacts=", ".join(str(f.qname) for f in stringFactsWithoutXmlLang))
            if nonMonetaryNonPureFacts:
                modelXbrl.error("EBA.3.2",
                                _("Non monetary (numeric) facts MUST use the pure unit: '%(langLessFacts)s'"),
                                modelObject=nonMonetaryNonPureFacts, langLessFacts=", ".join(str(f.qname) for f in nonMonetaryNonPureFacts))
                
            unusedUnitIDs = modelXbrl.units.keys() - unitIDsUsed
            if unusedUnitIDs:
                modelXbrl.warning("EBA.2.21",
                        _('Unused xbrli:unit nodes SHOULD NOT be present in the instance: %(unusedUnitIDs)s.'),
                        modelObject=[modelXbrl.units[unusedUnitID] for unusedUnitID in unusedUnitIDs], 
                        unusedUnitIDs=", ".join(sorted(unusedUnitIDs)))
                        
            unitHashes = {}
            for unit in modelXbrl.units.values():
                h = hash(unit)
                if h in unitHashes and unit.isEqualTo(unitHashes[h]):
                    modelXbrl.warning("EBA.2.32",
                        _("Duplicate units SHOULD NOT be reported, units %(unit1)s and %(unit2)s have same measures.'"),
                        modelObject=(unit, unitHashes[h]), unit1=unit.id, unit2=unitHashes[h].id)
                else:
                    unitHashes[h] = unit
            if len(currenciesUsed) > 1:
                modelXbrl.error("EBA.3.1",
                    _("There MUST be only one currency but %(numCurrencies)s were found: %(currencies)s.'"),
                    modelObject=currenciesUsed.values(), numCurrencies=len(currenciesUsed), currencies=", ".join(str(c) for c in currenciesUsed.keys()))
                
            namespacePrefixesUsed = defaultdict(set)
            prefixesUnused = set(modelDocument.xmlRootElement.keys()).copy()
            for elt in modelDocument.xmlRootElement.iter():
                if isinstance(elt, ModelObject): # skip comments and processing instructions
                    namespacePrefixesUsed[elt.qname.namespaceURI].add(elt.qname.prefix)
                    prefixesUnused.discard(elt.qname.prefix)
            if prefixesUnused:
                modelXbrl.warning("EBA.3.4",
                    _("There SHOULD be no unused prefixes but these were declared: %(unusedPrefixes)s.'"),
                    modelObject=modelDocument, unusedPrefixes=', '.join(sorted(prefixesUnused)))
            for ns, prefixes in namespacePrefixesUsed.items():
                nsDocs = modelXbrl.namespaceDocs.get(ns)
                if nsDocs:
                    for nsDoc in nsDocs:
                        nsDocPrefix = XmlUtil.xmlnsprefix(nsDoc.xmlRootElement, ns)
                        if any(prefix != nsDocPrefix for prefix in prefixes if prefix is not None):
                            modelXbrl.warning("EBA.3.5",
                                _("Prefix for namespace %(namespace)s is %(declaredPrefix)s but these were found %(foundPrefixes)s"),
                                modelObject=modelDocument, namespace=ns, declaredPrefix=nsDocPrefix, foundPrefixes=', '.join(sorted(prefixes - {None})))                        
    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)

    del val.prefixNamespace, val.namespacePrefix, val.idObjects, val.typedDomainElements
                
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate EBA',
    'version': '0.9',
    'description': '''EBA Validation.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2013 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': setup,
    # 'Validate.SBRNL.Fact': factCheck  (no instances being checked by SBRNL,
    'Validate.XBRL.Finally': final,
}
