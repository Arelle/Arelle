'''
Created on Jul 5, 2021

Filer Guidelines: 
    Basically EFM 5.2.2.1, 5.2.2.6,  5.2.2.10,  5.2.5.4, 5.2.5.5(Inline XBRL), 5.2.5.6(Inline XBRL), 
                  5.2.5.7, 5.2.5.8, 5.2.5.9, 5.2.5.10, 
                  6.5.3, 6.5.4, 6.5.7, 6.5.8, 6.5.14, 6.5.15, 6.5.16, 6.5.17
    Filers can only submit an instance so EFM DTS checks are not needed.
                  
@author: Mark V Systems Limited
(c) Copyright 2021 Mark V Systems Limited, All rights reserved.
'''
import os, re
from collections import defaultdict
from math import isnan
from arelle import ModelDocument, ValidateFilingText, XmlUtil
from arelle.ModelInstanceObject import ModelFact, ModelInlineFact, ModelInlineFootnote
from arelle.ModelObject import ModelObject
from arelle.PrototypeDtsObject import LinkPrototype, LocPrototype, ArcPrototype
from arelle.ValidateXbrlCalcs import inferredDecimals, rangeValue
from arelle.XbrlConst import xbrli, xhtml
from arelle.XmlValidate import VALID

def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("FERC", "FERCplugin"),) # FERC disclosure system

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateFERCplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "FERCplugin", False)
    if not (val.validateFERCplugin):
        return
    
    # use UTR validation if list of URLs was provided
    val.validateUTR = bool(val.disclosureSystem.utrUrl)
    
def validateXbrlFinally(val, *args, **kwargs):
    if not (val.validateFERCplugin):
        return

    _xhtmlNs = "{{{}}}".format(xhtml)
    _xhtmlNsLen = len(_xhtmlNs)
    modelXbrl = val.modelXbrl
    modelDocument = modelXbrl.modelDocument
    if not modelDocument:
        return # never loaded properly
    disclosureSystem = val.disclosureSystem

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)

    isInlineXbrl = modelXbrl.modelDocument.type in (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET)
    requiredFactLang = disclosureSystem.defaultXmlLang.lower() if disclosureSystem.defaultXmlLang else disclosureSystem.defaultXmlLang

    # inline doc set has multiple instance names to check
    if modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRLDOCUMENTSET:
        instanceNames = [ixDoc.basename
                         for ixDoc in modelXbrl.modelDocument.referencesDocument.keys()
                         if ixDoc.type == ModelDocument.Type.INLINEXBRL]
        xbrlInstRoots = modelXbrl.ixdsHtmlElements
    else: # single instance document to check is the entry point document
        instanceNames = [modelXbrl.modelDocument.basename]
        xbrlInstRoots = [modelXbrl.modelDocument.xmlDocument.getroot()]
            
    #6.5.15 facts with xml in text blocks
    ValidateFilingText.validateTextBlockFacts(modelXbrl, {
                                    True: ("gif", "jpg", "jpeg", "png"), # img file extensions
                                    False: ("gif", "jpeg", "png") # mime types: jpg is not a valid mime type
                                    })
    
    # check footnotes text
    if isInlineXbrl:
        _linkEltIter = (linkPrototype
                        for linkKey, links in modelXbrl.baseSets.items()
                        for linkPrototype in links
                        if linkPrototype.modelDocument.type in (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET)
                        and linkKey[1] and linkKey[2] and linkKey[3]  # fully specified roles
                        and linkKey[0] != "XBRL-footnotes")
    else: 
        _linkEltIter = xbrlInstRoots[0].iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}footnoteLink")
    for footnoteLinkElt in _linkEltIter:
        if isinstance(footnoteLinkElt, (ModelObject,LinkPrototype)):
            for child in footnoteLinkElt:
                if isinstance(child,(ModelObject,LocPrototype,ArcPrototype)):
                    xlinkType = child.get("{http://www.w3.org/1999/xlink}type")
                    if xlinkType == "resource" or isinstance(child,ModelInlineFootnote): # footnote
                        if not isInlineXbrl: # inline content was validated before and needs continuations assembly
                            ValidateFilingText.validateFootnote(modelXbrl, child)

    # same identifier in all contexts (EFM 6.5.3)
    entityIdentifiers = set()
    for xbrlInstRoot in xbrlInstRoots: # check all inline docs in ix doc set
        for entityIdentifierElt in xbrlInstRoot.iterdescendants("{http://www.xbrl.org/2003/instance}identifier"):
            if isinstance(entityIdentifierElt,ModelObject):
                entityIdentifiers.add("{}#{}".format(entityIdentifierElt.get("scheme"), XmlUtil.text(entityIdentifierElt)))
    if len(entityIdentifiers) > 1:
        modelXbrl.error("FERC.6.05.03",
            _("There are more than one entity identifiers: %(entityIdentifiers)s."),
            modelObject=modelXbrl,
            entityIdentifiers=", ".join(sorted(entityIdentifiers)))
    for ei in sorted(entityIdentifiers):
        scheme, _sep, identifier = ei.rpartition("#")
        if not disclosureSystem.identifierSchemePattern.match(scheme) or not disclosureSystem.identifierValuePattern.match(identifier):
            modelXbrl.error("FERC.6.05.01",
                _("Entity identifier %(identifier)s, or scheme %(scheme)s does not adhere "
                  "to the standard naming convention of <identifier scheme='http://www.ferc.gov/CID'>Cnnnnnn</identifier>'.  "),
                modelObject=modelXbrl, scheme=scheme, identifier=identifier)

    #6.5.4 scenario
    segContexts = set()
    uniqueContextHashes = {}
    contextIDs = set()
    precisionFacts = set()
    formType = None
    formEntrySchema = None
    factsForLang = {}
    keysNotDefaultLang = {}
    allFormEntryXsd = () 
       
    for c in modelXbrl.contexts.values():
        if XmlUtil.hasChild(c, xbrli, "segment"):
            segContexts.add(c)
        h = c.contextDimAwareHash
        if h in uniqueContextHashes:
            if c.isEqualTo(uniqueContextHashes[h]):
                modelXbrl.error("FERC.6.05.07",
                    _("The instance document contained more than one context equivalent to %(context)s (%(context2)s).  "
                      "Please remove duplicate contexts from the instance."),
                    modelObject=(c, uniqueContextHashes[h]), context=c.id, context2=uniqueContextHashes[h].id)
        else:
            uniqueContextHashes[h] = c
        contextIDs.add(c.id)

    if segContexts:
        modelXbrl.error("FERC.6.05.04",
            _("There must be no contexts with segment, but %(count)s was(were) found: %(context)s."),
            modelObject=segContexts, count=len(segContexts), context=", ".join(sorted(c.id for c in segContexts)))

    factForConceptContextUnitHash = defaultdict(list)
    # unused contexts
    for f in modelXbrl.facts:
        factContextID = f.contextID
        contextIDs.discard(factContextID)
        if f.isNumeric:
            if f.precision is not None:
                precisionFacts.add(f)
        elif not f.isNil:
            langTestKey = "{0},{1}".format(f.qname, f.contextID)
            factsForLang.setdefault(langTestKey, []).append(f)
            lang = f.xmlLang
            if lang and lang.lower() != requiredFactLang: # not lang.startswith(factLangStartsWith):
                keysNotDefaultLang[langTestKey] = f
        if getattr(f, "xValid", 0) >= VALID:
            if f.qname.localName == "FormType":
                formType = f.xValue
                formNum = re.sub("([0-9]+).*", r"\1", formType)
                formLtr = re.match("[^A-Z]*([A-Z]?)", formType).group(1)
                txDate = re.sub("http://ferc.gov/form/([0-9]{4}-[0-9]{2}-[0-9]{2})/ferc", r"\1", f.qname.namespaceURI)

                formEntryXsd = "https://eCollection.ferc.gov/taxonomy/form{}/{}/form/form{}{}/form-{}{}_{}.xsd".format(formNum, txDate, formNum, formLtr, formNum, formLtr, txDate)

                formEntryXsdUAT = formEntryXsd.replace("eCollection","uat.eforms")
                formEntryXsdTest = formEntryXsd.replace("eCollection","test.eforms")
                formEntryXsdDev = formEntryXsd.replace("eCollection","dev.eforms")

                confFormEntryXsd = "https://eCollection.ferc.gov/taxonomy/form{}/{}/ferc-core-footnote-roles_{}.xsd".format(formNum, txDate,txDate)

                confFormEntryXsdUAT = confFormEntryXsd.replace("eCollection","uat.eforms")
                confFormEntryXsdTest = confFormEntryXsd.replace("eCollection","test.eforms")
                confFormEntryXsdDev = confFormEntryXsd.replace("eCollection","dev.eforms")

                allFormEntryXsd = [formEntryXsd, formEntryXsdUAT, formEntryXsdTest, formEntryXsdDev, confFormEntryXsd, confFormEntryXsdUAT, confFormEntryXsdTest, confFormEntryXsdDev]
            factForConceptContextUnitHash[f.conceptContextUnitHash].append(f)
                
    unexpectedXsds = set(doc.modelDocument.uri
                         for doc, referencingDoc in modelXbrl.modelDocument.referencesDocument.items()
                         if "href" in referencingDoc.referenceTypes
                         if doc.modelDocument.uri not in allFormEntryXsd)
    if unexpectedXsds:
        modelXbrl.error("FERC.22.00",
                        _("The instance document contained unexpected schema references %(schemaReferences)s."),
                        modelXbrl=modelXbrl, schemaReferences=", ".join(sorted(unexpectedXsds)))
                
    if contextIDs: # check if contextID is on any undefined facts
        for undefinedFact in modelXbrl.undefinedFacts:
            contextIDs.discard(undefinedFact.get("contextRef"))
        if contextIDs:
            modelXbrl.error("FERC.6.05.08",
                            _("The instance document contained context(s) %(contextIDs)s that was(were) not used in any fact."),
                            modelXbrl=modelXbrl, contextIDs=", ".join(str(c) for c in contextIDs))
    if precisionFacts:
            modelXbrl.error("FERC.6.05.17",
                _("The instance document contains elements using the precision attribute."),
                modelObject=precisionFacts)
            
    # check for inconsistent duplicates (same check as in plugin/validate/HMRC
    aspectEqualFacts = defaultdict(dict) # dict [(qname,lang)] of dict(cntx,unit) of [fact, fact] 
    for hashEquivalentFacts in factForConceptContextUnitHash.values():
        if len(hashEquivalentFacts) > 1:
            for f in hashEquivalentFacts: # check for hash collision by value checks on context and unit
                if getattr(f,"xValid", 0) >= 4:
                    cuDict = aspectEqualFacts[(f.qname,
                                               (f.xmlLang or "").lower() if f.concept.type.isWgnStringFactType else None)]
                    _matched = False
                    for (_cntx,_unit),fList in cuDict.items():
                        if (((_cntx is None and f.context is None) or (f.context is not None and f.context.isEqualTo(_cntx))) and
                            ((_unit is None and f.unit is None) or (f.unit is not None and f.unit.isEqualTo(_unit)))):
                            _matched = True
                            fList.append(f)
                            break
                    if not _matched:
                        cuDict[(f.context,f.unit)] = [f]
            decVals = {}
            for cuDict in aspectEqualFacts.values(): # dups by qname, lang
                for fList in cuDict.values():  # dups by equal-context equal-unit
                    if len(fList) > 1:
                        f0 = fList[0]
                        if f0.concept.isNumeric:
                            if any(f.isNil for f in fList):
                                _inConsistent = not all(f.isNil for f in fList)
                            else: # not all have same decimals
                                _d = inferredDecimals(f0)
                                _v = f0.xValue
                                _inConsistent = isnan(_v) # NaN is incomparable, always makes dups inconsistent
                                decVals[_d] = _v
                                aMax, bMin = rangeValue(_v, _d)
                                for f in fList[1:]:
                                    _d = inferredDecimals(f)
                                    _v = f.xValue
                                    if isnan(_v):
                                        _inConsistent = True
                                        break
                                    if _d in decVals:
                                        _inConsistent |= _v != decVals[_d]
                                    else:
                                        decVals[_d] = _v
                                    a, b = rangeValue(_v, _d)
                                    if a > aMax: aMax = a
                                    if b < bMin: bMin = b
                                if not _inConsistent:
                                    _inConsistent = (bMin < aMax)
                                decVals.clear()
                        else:
                            _inConsistent = any(not f.isVEqualTo(f0) for f in fList[1:])
                        if _inConsistent:
                            modelXbrl.error("FERC.6.05.12",
                                "Inconsistent duplicate fact values %(fact)s: %(values)s.",
                                modelObject=fList, fact=f0.qname, contextID=f0.contextID, values=", ".join(f.value for f in fList))
            aspectEqualFacts.clear()
    del factForConceptContextUnitHash, aspectEqualFacts

    #6.5.14 facts without english text
    for keyNotDefaultLang, factNotDefaultLang in keysNotDefaultLang.items():
        anyDefaultLangFact = False
        for fact in factsForLang[keyNotDefaultLang]:
            if fact.xmlLang.lower() == requiredFactLang: #.startswith(factLangStartsWith):
                anyDefaultLangFact = True
                break
        if not anyDefaultLangFact:
            val.modelXbrl.error("FERC.6.05.14",
                _("Element %(fact)s in context %(contextID)s has text with xml:lang other than '%(lang2)s' (%(lang)s) without matching English text.  "),
                modelObject=factNotDefaultLang, fact=factNotDefaultLang.qname, contextID=factNotDefaultLang.contextID, 
                lang=factNotDefaultLang.xmlLang, lang2=disclosureSystem.defaultXmlLang) # report lexical format default lang

    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)
    

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate FERC',
    'version': '1.0',
    'description': '''FERC (US) Validation.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2021 Mark V Systems Limited, All rights reserved.',
    'import': ('inlineXbrlDocumentSet', ), # import dependent modules
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
}