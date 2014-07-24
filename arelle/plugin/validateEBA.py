'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import PluginManager
from arelle import ModelDocument, XbrlConst, XmlUtil, UrlUtil
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

qnFilingIndicators = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:filingIndicators")
qnFilingIndicator = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:filingIndicator")

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
    modelXbrl = val.modelXbrl
    # moved from ValidateFiling
    for qname, modelType in modelXbrl.qnameTypes.items():
        if qname.namespaceURI not in val.disclosureSystem.baseTaxonomyNamespaces:
            facets = modelType.facets
            if facets:
                lengthFacets = _DICT_SET(facets.keys()) & {"minLength", "maxLength", "length"}
                if lengthFacets:
                    modelXbrl.error("SBR.NL.2.2.7.02",
                        _("Type %(typename)s has length restriction facets %(facets)s"),
                        modelObject=modelType, typename=modelType.qname, facets=", ".join(lengthFacets))
                if "enumeration" in facets and not modelType.isDerivedFrom(XbrlConst.qnXbrliStringItemType):
                    modelXbrl.error("SBR.NL.2.2.7.04",
                        _("Concept %(concept)s has enumeration and is not based on stringItemType"),
                        modelObject=modelType, concept=modelType.qname)

    ''' removed RH 2011-12-23, corresponding use of nameWordsTable in ValidateFilingDTS
    # build camelCasedNamesTable
    self.nameWordsTable = {}
    for name in modelXbrl.nameConcepts.keys():
        words = []
        wordChars = []
        lastchar = ""
        for c in name:
            if c.isupper() and lastchar.islower(): # it's another word
                partialName = ''.join(wordChars)
                if partialName in modelXbrl.nameConcepts:
                    words.append(partialName)
            wordChars.append(c)
            lastchar = c
        if words:
            self.nameWordsTable[name] = words
    self.modelXbrl.profileActivity("... build name words table", minTimeToShow=1.0)
    '''
    
    
    
    # check presentation link roles for generic linkbase order number
    ordersRelationshipSet = modelXbrl.relationshipSet("http://www.nltaxonomie.nl/2011/arcrole/linkrole-order")
    presLinkroleNumberURI = {}
    presLinkrolesCount = 0
    for countLinkroles in (True, False):
        for roleURI, modelRoleTypes in modelXbrl.roleTypes.items():
            for modelRoleType in modelRoleTypes:
                if XbrlConst.qnLinkPresentationLink in modelRoleType.usedOns:
                    if countLinkroles:
                        presLinkrolesCount += 1
                    else:
                        if not ordersRelationshipSet:
                            modelXbrl.error("SBR.NL.2.2.3.06",
                                _("Presentation linkrole %(linkrole)s missing order number relationship set"),
                                modelObject=modelRoleType, linkrole=modelRoleType.roleURI)
                        else:
                            order = None
                            for orderNumRel in ordersRelationshipSet.fromModelObject(modelRoleType):
                                order = getattr(orderNumRel.toModelObject, "xValue", "(noPSVIvalue)")
                                if order in presLinkroleNumberURI:
                                    modelXbrl.error("SBR.NL.2.2.3.06",
                                        _("Presentation linkrole order number %(order)s of %(linkrole)s also used in %(otherLinkrole)s"),
                                        modelObject=modelRoleType, order=order, linkrole=modelRoleType.roleURI, otherLinkrole=presLinkroleNumberURI[order])
                                else:
                                    presLinkroleNumberURI[order] = modelRoleType.roleURI
                            if not order:
                                modelXbrl.error("SBR.NL.2.2.3.06",
                                    _("Presentation linkrole %(linkrole)s missing order number"),
                                    modelObject=modelRoleType, linkrole=modelRoleType.roleURI)
        if countLinkroles and presLinkrolesCount < 2:
            break   # don't check order numbers if only one presentation linkrole
    # check arc role definitions for labels
    for arcroleURI, modelRoleTypes in modelXbrl.arcroleTypes.items():
        for modelRoleType in modelRoleTypes:
            if (not arcroleURI.startswith("http://xbrl.org/") and 
                modelRoleType.modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces and
                (not modelRoleType.genLabel(lang="nl") or not modelRoleType.genLabel(lang="en"))):
                modelXbrl.error("SBR.NL.2.2.4.02",
                    _("ArcroleType missing nl or en generic label: %(arcrole)s"),
                    modelObject=modelRoleType, arcrole=arcroleURI)

    for domainElt in val.typedDomainElements:
        if domainElt.modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces:
            if not domainElt.genLabel(fallbackToQname=False, lang="nl"):
                modelXbrl.error("SBR.NL.2.2.8.01",
                    _("Typed dimension domain element %(concept)s must have a generic label"),
                    modelObject=domainElt, concept=domainElt.qname)
            if domainElt.type is not None and domainElt.type.localName == "complexType":
                modelXbrl.error("SBR.NL.2.2.8.02",
                    _("Typed dimension domain element %(concept)s has disallowed complex content"),
                    modelObject=domainElt, concept=domainElt.qname)
            
    modelXbrl.profileActivity("... SBR role types and type facits checks", minTimeToShow=1.0)
    # end moved from ValidateFiling

    # 3.2.4.4 check each using prefix against taxonomy declaring the prefix
    for docs in modelXbrl.namespaceDocs.values():
        for doc in docs:
            for prefix, NS in doc.xmlRootElement.nsmap.items():
                if NS in val.namespacePrefix and prefix != val.namespacePrefix[NS]:
                    modelXbrl.error("SBR.NL.3.2.4.04",
                        _("The assigned namespace prefix %(assignedPrefix)s for the schema that declares the targetnamespace %(namespace)s, MUST be adhired by all other NT schemas, referencedPrefix: %(referencedPrefix)s"),
                        modelObject=doc.xmlRootElement, namespace=NS, assignedPrefix=val.namespacePrefix.get(NS, ''), referencedPrefix=prefix)

    # check non-concept elements that can appear in elements for labels (concepts checked by 
    labelsRelationshipSet = modelXbrl.relationshipSet((XbrlConst.conceptLabel, XbrlConst.elementLabel))
    standardXbrlSchmas = _DICT_SET(XbrlConst.standardNamespaceSchemaLocations.values())
    baseTaxonomyNamespaces = val.disclosureSystem.baseTaxonomyNamespaces
    for eltDef in modelXbrl.qnameConcepts.values():
        if (not (eltDef.isItem or eltDef.isTuple or eltDef.isLinkPart) and
            eltDef.qname.namespaceURI not in baseTaxonomyNamespaces):
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
                modelXbrl.error("SBR.NL.3.2.15.01",
                    _("XML nodes that can appear in instances MUST have standard labels in the local language: %(element)s"),
                    modelObject=eltDef, element=eltDef.qname)

    del val.prefixNamespace, val.namespacePrefix, val.idObjects

def checkDTSdocument(val, modelDocument):
    modelXbrl = val.modelXbrl
    if modelDocument.type == ModelDocument.Type.INSTANCE:
        
        if not modelDocument.uri.endswith(".xbrl"):
            modelXbrl.warning("EBA.1.1",
                    _('XBRL instance documents SHOULD use the extension ".xbrl" encoding but it is "%(extension)s"'),
                    modelObject=modelDocument, xmlEncoding=os.path.splitext(modelDocument.basename)[1])
        if modelDocument.documentEncoding.lower() != "utf-8":
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
        for fIndicator in modelXbrl.factsByQname[qnFilingIndicator]:
            if fIndicator.xValue in filingIndicators:
                modelXbrl.error("EBA.1.6.1",
                        _('Multiple filing indicators facts for indicator %(filingIndicator)s.'),
                        modelObject=(fIndicator, filingIndicators[filingIndicators]), fIndicator.xValue)
            filingIndicators[fIndicator.xValue] = fIndicator
        
        if not filingIndicators:
            modelXbrl.error("EBA.1.6",
                    _('Missing filing indicators.  Reported XBRL instances MUST include appropriate filing indicator elements'),
                    modelObject=modelDocument)
            
        numFilingIndicatorTuples = len(modelXbrl.factsByQname[qnFilingIndicators])
        if numFilingIndicatorTuples > 1 and not getattr(modelXbrl, "isStreamingMode", False):
            modelXbrl.info("EBA.1.6.2",                            
                    _('Multiple filing indicators tuples when not in streaming mode (info).'),
                    modelObject=modelXbrl.factsByQname[qnFilingIndicators])
                    
        # note EBA 2.1 is in ModelDocument.py
        
        cntxIDs = set()
        cntxEntities = set()
        timelessDatePattern = re.compile(r"\s*([0-9]{4})-([0-9]{2})-([0-9]{2})\s*$")
        for cntx in modelXbrl.contexts.values():
            cntxIDs.add(cntx.contextID)
            cntxEntities.add(cntx.entityIdentifier)
            dateElts = XmlUtil.descendants(cntx, XbrlConst.xbrli, ("startDate","endDate","instant"))
            if any(not timelessDatePattern.matches(e) for e in dateElts):
                modelXbrl.error("EBA.2.10",
                        _('Period dates must be whole dates without time or timezone: %(dates)s.'),
                        modelObject=cntx, dates=", ".join(e.text for e in dateElts))
            if cntx.isForever:
                modelXbrl.error("EBA.2.11",
                        _('Forever context period is not allowed.'),
                        modelObject=cntx)
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
                        modelObject=cntx, context=cntx.contextID, content=childTags)
                
        unusedCntxIDs = cntxIDs - {fact.contextID for fact in modelXbrl.facts}
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
        unitIDsUsed = set()
        currenciesUsed = {}
        for qname, facts in modelXbrl.factsByQname:
            for f in facts:
                concept = f.concept
                k = (f.context.contextDimAwareHash if f.context is not None else None,
                     f.unit.hash if f.unit is not None else None,
                     hash(f.xmlLang))
                if k not in otherFacts:
                    otherFacts[k] = {fact}
                else:
                    matches = [o
                               for o in otherFacts[k]
                               if (f.context.isEqualTo(o.context) if f.context is not None and o.context is not None else True) and
                                  (f.unit.isEqualTo(o.unit) if f.unit is not None and o.unit is not None else True) and
                                  (f.xmlLang == o.xmlLang)]
                    if matches:
                        modelXbrl.error("EBA.2.16",
                                        _('Facts are duplicates %(fact)s and %(otherFacts)s.'),
                                        modelObject=[f] + matches, fact=f.qname, otherFacts=', '.join(str(f.qname) for f in matches))
                    else:
                        otherFacts[k].add(f)    
                if concept is not None and concept.isNumeric:
                    if f.precision:
                        modelXbrl.error("EBA.2.17",
                            _("Numeric fact %(fact)s of context %(contextID)s has a precision attribute '%(precision)s'"),
                            modelObject=f, fact=f.qname, contextID=f.contextID, precision=f.precision)
                    '''' (not intended by EBA 2.18)
                    if f.decimals and f.decimals != "INF" and not f.isNil and getattr(f,"xValid", 0) == 4:
                        try:
                            insignificance = insignificantDigits(f.xValue, decimals=f.decimals)
                            if insignificance: # if not None, returns (truncatedDigits, insiginficantDigits)
                                modelXbrl.error(("EFM.6.05.37", "GFM.1.02.26"),
                                    _("Fact %(fact)s of context %(contextID)s decimals %(decimals)s value %(value)s has nonzero digits in insignificant portion %(insignificantDigits)s."),
                                    modelObject=f1, fact=f1.qname, contextID=f1.contextID, decimals=f1.decimals, 
                                    value=f1.xValue, truncatedDigits=insignificance[0], insignificantDigits=insignificance[1])
                        except (ValueError,TypeError):
                            modelXbrl.error(("EFM.6.05.37", "GFM.1.02.26"),
                                _("Fact %(fact)s of context %(contextID)s decimals %(decimals)s value %(value)s causes Value Error exception."),
                                modelObject=f1, fact=f1.qname, contextID=f1.contextID, decimals=f1.decimals, value=f1.value)
                    '''
                    unit = f.unit
                    if concept.isMonetary and unit is not None and unit.measures[0]:
                        currenciesUsed.add(unit.measures[0][0])
                if f.unitID is not None:
                    unitIDsUsed.add(f.unitID)
                if f.isNil:
                    nilFacts.append(f)
                    
        if nilFacts:
            modelXbrl.warning("EBA.2.19",
                    _('Nil facts SHOULD NOT be present in the instance: %(nilFacts)s.'),
                    modelObject=nilFacts, nilFacts=", ".join(str(f.qname) for f in nilFacts))
                
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
                modelXbrl.error("EBA.2.32",
                    _("Units %(unit1)s and %(unit2)s have same measures.'"),
                    modelObject=(unit, unitHashes[h]), unit1=unit.id, unit2=unitHashes[h].id)
            else:
                unitHashes[h] = f.unit
        if len(currenciesUsed) > 1:
            modelXbrl.error("EBA.3.1",
                _("There MUST be only one currency but %(numCurrencies)s were found: %(currencies)s.'"),
                modelObject=currenciesUsed.values(), numCurrencies=len(currenciesUsed), currencies=", ".join(str(c) for c in currenciesUsed.keys()))
            
        namespacePrefixesUsed = defaultdict(set)
        prefixesUnused = set(modelDocument.xmlRootElement.keys()).copy
        for elt in modelDocument.xmlRootElement.iter():
            namespacePrefixesUsed[elt.qname.namespaceURI].add(elt.qname.prefix)
            prefixesUnused.discard(elt.qname.prefix)
        if prefixesUnused:
            modelXbrl.warning("EBA.3.4",
                _("There SHOULD be no unused prefixes but these were declared: %(unusedPrefixes)s.'"),
                modelObject=modelDocument, prefixesUnused=', '.join(sorted(prefixesUnused)))
        for ns, prefixes in namespacePrefixesUsed.items():
            nsDocs = modelXbrl.namespaceDocs.get(ns)
            if nsDocs:
                for nsDoc in nsDocs:
                    nsDocPrefix = XmlUtil.xmlnsprefix(nsDoc.xmlRootElement, ns)
                    if any(prefix != nsDocPrefix for prefix in prefixes):
                        modelXbrl.warning("EBA.3.5",
                            _("Prefix for namespace %(namespace)s is %(declaredPrefix)s but these were found %(foundPrefixes)s"),
                            modelObject=modelDocument, namespace=ns, declaredPrefix=nsDocPrefix, foundPrefixes=', '.join(sorted(prefixes)))                        
                
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate EBA',
    'version': '0.9',
    'description': '''EBA Validation.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2013 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Validate.SBRNL.Start': setup,
    # 'Validate.SBRNL.Fact': factCheck  (no instances being checked by SBRNL,
    'Validate.SBRNL.Finally': final,
    'Validate.SBRNL.DTS.document': checkDTSdocument,
    'ModelDocument.CustomLoader': checkForBOMs
}
