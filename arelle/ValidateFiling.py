'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import xml.dom, xml.parsers
import os, re, collections, datetime
from collections import defaultdict
from arelle import (ModelDocument, ModelValue, ValidateXbrl,
                ModelRelationshipSet, XmlUtil, XbrlConst, UrlUtil,
                ValidateFilingDimensions, ValidateFilingDTS, ValidateFilingText)
from arelle.ModelObject import ModelObject
from arelle.ModelInstanceObject import ModelFact

class ValidateFiling(ValidateXbrl.ValidateXbrl):
    def __init__(self, modelXbrl):
        super().__init__(modelXbrl)
        
        self.datePattern = re.compile(r"([12][0-9]{3})-([01][0-9])-([0-3][0-9])")
        self.GFMcontextDatePattern = re.compile(r"^[12][0-9]{3}-[01][0-9]-[0-3][0-9]$")
        self.targetNamespaceDatePattern = re.compile(r"/([12][0-9]{3})-([01][0-9])-([0-3][0-9])|"
                                                r"/([12][0-9]{3})([01][0-9])([0-3][0-9])|")
        self.roleTypePattern = re.compile(r".*/role/[^/]+")
        self.arcroleTypePattern = re.compile(r".*/arcrole/[^/]+")
        self.arcroleDefinitionPattern = re.compile(r"^.*[^\\s]+.*$")  # at least one non-whitespace character
        
        self.signOrCurrency = re.compile("^(-)[0-9]+|[^eE](-)[0-9]+|(\\()[0-9].*(\\))|([$\u20ac£¥])")

        
    def validate(self, modelXbrl, parameters=None):
        if not hasattr(modelXbrl.modelDocument, "xmlDocument"): # not parsed
            return
        
        modelXbrl.modelManager.disclosureSystem.loadStandardTaxonomiesDict()
        
        # find typedDomainRefs before validateXBRL pass
        if modelXbrl.modelManager.disclosureSystem.SBRNL:
            self.typedDomainQnames = set()
            for modelConcept in modelXbrl.qnameConcepts.values():
                if modelConcept.isTypedDimension:
                    typedDomainElement = modelConcept.typedDomainElement
                    if typedDomainElement is not None:
                        self.typedDomainQnames.add(typedDomainElement.qname)
        
        # note that some XFM tests are done by ValidateXbrl to prevent mulstiple node walks
        super(ValidateFiling,self).validate(modelXbrl, parameters)
        xbrlInstDoc = modelXbrl.modelDocument.xmlDocument.getroot()
        disclosureSystem = self.disclosureSystem
        self.modelXbrl = modelXbrl
        modelXbrl.modelManager.showStatus(_("validating {0}").format(disclosureSystem.name))
        
        self.modelXbrl.profileActivity()
        conceptsUsed = {} # key=concept object value=True if has presentation label
        labelsRelationshipSet = modelXbrl.relationshipSet(XbrlConst.conceptLabel)
        presentationRelationshipSet = modelXbrl.relationshipSet(XbrlConst.parentChild)
        referencesRelationshipSetWithProhibits = modelXbrl.relationshipSet(XbrlConst.conceptReference, includeProhibits=True)
        self.modelXbrl.profileActivity("... cache lbl, pre, ref relationships", minTimeToShow=1.0)
        
        validateInlineXbrlGFM = (modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL and
                                 self.validateGFM)
        
        # instance checks
        if modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or \
           modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL:
            #6.5.1 scheme, 6.5.2, 6.5.3 identifier
            entityIdentifierValue = None
            if disclosureSystem.identifierValueName:   # omit if no checks
                for entityIdentifierElt in xbrlInstDoc.iterdescendants("{http://www.xbrl.org/2003/instance}identifier"):
                    if isinstance(entityIdentifierElt,ModelObject):
                        schemeAttr = entityIdentifierElt.get("scheme")
                        if not disclosureSystem.identifierSchemePattern.match(schemeAttr):
                            modelXbrl.error(
                                _("Invalid entity identifier scheme: {0}").format(schemeAttr), 
                                "err", "EFM.6.05.01", "GFM.1.02.01")
                        entityIdentifier = XmlUtil.text(entityIdentifierElt)
                        if not disclosureSystem.identifierValuePattern.match(entityIdentifier):
                            modelXbrl.error(
                                _("Invalid entity identifier {0}: {1}").format(
                                           disclosureSystem.identifierValueName,
                                           entityIdentifier), 
                                "err", "EFM.6.05.02", "GFM.1.02.02")
                        if not entityIdentifierValue:
                            entityIdentifierValue = entityIdentifier
                        elif entityIdentifier != entityIdentifierValue:
                            modelXbrl.error(
                                _("Multiple {0}s: {1}, {2}").format(
                                           disclosureSystem.identifierValueName,
                                           entityIdentifierValue, entityIdentifier), 
                                "err", "EFM.6.05.03", "GFM.1.02.03")
                self.modelXbrl.profileActivity("... filer identifier checks", minTimeToShow=1.0)
    
            #6.5.7 duplicated contextx
            contexts = modelXbrl.contexts.values()
            contextIDs = set()
            uniqueContextHashes = {}
            for context in contexts:
                contextID = context.id
                contextIDs.add(contextID)
                h = context.contextDimAwareHash
                if h in uniqueContextHashes:
                    if context.isEqualTo(uniqueContextHashes[h]):
                        modelXbrl.error(
                            _("Context ID {0} is equivalent to context ID {1}").format(
                                 contextID, uniqueContextHashes[h].id), 
                            "err", "EFM.6.05.07", "GFM.1.02.07    ")
                else:
                    uniqueContextHashes[h] = context
                    
                #GFM no time in contexts
                if self.validateGFM:
                    for dateElt in XmlUtil.children(context, XbrlConst.xbrli, ("startDate", "endDate", "instant")):
                        dateText = XmlUtil.text(dateElt)
                        if not self.GFMcontextDatePattern.match(dateText):
                            modelXbrl.error(
                                _("Context id {0} {1} invalid content {2}").format(
                                     contextID, dateElt.prefixedName, dateText), 
                                "err", "GFM.1.02.25")
                #6.5.4 scenario
                hasSegment = XmlUtil.hasChild(context, XbrlConst.xbrli, "segment")
                hasScenario = XmlUtil.hasChild(context, XbrlConst.xbrli, "scenario")
                notAllowed = None
                if disclosureSystem.contextElement == "segment" and hasScenario:
                    notAllowed = _("Scenario")
                elif disclosureSystem.contextElement == "scenario" and hasSegment:
                    notAllowed = _("Segment")
                elif disclosureSystem.contextElement == "either" and hasSegment and hasScenario:
                    notAllowed = _("Both segment and scenario")
                elif disclosureSystem.contextElement == "none" and (hasSegment or hasScenario):
                    notAllowed = _("Neither segment nor scenario")
                if notAllowed:
                    modelXbrl.error(
                        _("{0} element not allowed in context Id: {1}").format(
                             notAllowed, contextID), 
                        "err", "EFM.6.05.04", "GFM.1.02.04", "SBR.NL.2.3.5.06")
        
                #6.5.5 segment only explicit dimensions
                for contextName in ("{http://www.xbrl.org/2003/instance}segment","{http://www.xbrl.org/2003/instance}scenario"):
                    for segScenElt in context.iterdescendants(contextName):
                        if isinstance(segScenElt,ModelObject):
                            childTags = ", ".join([child.prefixedName for child in segScenElt.iterchildren()
                                                   if isinstance(child,ModelObject) and 
                                                   child.tag != "{http://xbrl.org/2006/xbrldi}explicitMember"])
                            if len(childTags) > 0:
                                modelXbrl.error(_("Segment of context Id {0} has disallowed content: {1}").format(
                                         contextID, childTags), 
                                    "err", "EFM.6.05.05", "GFM.1.02.05")
            del uniqueContextHashes
            self.modelXbrl.profileActivity("... filer context checks", minTimeToShow=1.0)
    
    
            #fact items from standard context (no dimension)
            amendmentDescription = None
            amendmentFlag = None
            documentPeriodEndDate = None
            documentType = None
            deiItems = {}
            commonSharesItemsByStockClass = defaultdict(list)
            commonSharesClassMembers = None
            commonStockMeasurementDatetime = None
    
            # parameter-provided CIKs and registrant names
            paramFilerIdentifier = None
            paramFilerIdentifiers = None
            paramFilerNames = None
            if self.validateEFM and self.parameters:
                p = self.parameters.get(ModelValue.qname("CIK",noPrefixIsNoNamespace=True))
                if p and len(p) == 2:
                    paramFilerIdentifier = p[1]
                p = self.parameters.get(ModelValue.qname("cikList",noPrefixIsNoNamespace=True))
                if p and len(p) == 2:
                    paramFilerIdentifiers = p[1].split(",")
                p = self.parameters.get(ModelValue.qname("cikNameList",noPrefixIsNoNamespace=True))
                if p and len(p) == 2:
                    paramFilerNames = p[1].split("|Edgar|")
                    if paramFilerIdentifiers and len(paramFilerIdentifiers) != len(paramFilerNames):
                        self.modelXbrl.error(
                            _("parameters for cikList and cikNameList different list entry counts: {0}, {1}").format(
                                  paramFilerIdentifiers, paramFilerNames), 
                            "err", "EFM.6.05.24", "GFM.3.02.02")
                        
            deiCheckLocalNames = {
                "EntityRegistrantName", 
                "EntityCommonStockSharesOutstanding",
                "EntityCurrentReportingStatus", 
                "EntityVoluntaryFilers", 
                disclosureSystem.deiCurrentFiscalYearEndDateElement, 
                "EntityFilerCategory", 
                "EntityWellKnownSeasonedIssuer", 
                "EntityPublicFloat", 
                disclosureSystem.deiDocumentFiscalYearFocusElement, 
                "DocumentFiscalPeriodFocus"
                 }
            #6.5.8 unused contexts
            for f in modelXbrl.facts:
                factContextID = f.contextID
                if factContextID in contextIDs:
                    contextIDs.remove(factContextID)
                    
                context = f.context
                factElementName = f.localName
                if disclosureSystem.deiNamespacePattern is not None:
                    factInDeiNamespace = disclosureSystem.deiNamespacePattern.match(f.namespaceURI)
                else:
                    factInDeiNamespace = None
                # standard dei items from required context
                if context is not None: # tests do not apply to tuples
                    if not context.hasSegment and not context.hasScenario: 
                        #default context
                        if factInDeiNamespace:
                            value = f.value
                            if factElementName == disclosureSystem.deiAmendmentFlagElement:
                                amendmentFlag = value
                            elif factElementName == "AmendmentDescription":
                                amendmentDescription = value
                            elif factElementName == disclosureSystem.deiDocumentPeriodEndDateElement:
                                documentPeriodEndDate = value
                                commonStockMeasurementDatetime = context.endDatetime
                            elif factElementName == "DocumentType":
                                documentType = value
                            elif factElementName == disclosureSystem.deiFilerIdentifierElement:
                                deiItems[factElementName] = value
                                if entityIdentifierValue != value:
                                    self.modelXbrl.error(
                                        _("dei:{0} {1} is must match the context entity identifier {2}").format(
                                              disclosureSystem.deiFilerIdentifierElement,
                                              value, entityIdentifierValue), 
                                        "err", "EFM.6.05.23", "GFM.3.02.02")
                                if paramFilerIdentifier and value != paramFilerIdentifier:
                                    self.modelXbrl.error(
                                        _("dei:{0} {1} must match submission: {2}").format(
                                              disclosureSystem.deiFilerIdentifierElement,
                                              value, paramFilerIdentifier), 
                                        "err", "EFM.6.05.23", "GFM.3.02.02")
                            elif factElementName == disclosureSystem.deiFilerNameElement:
                                deiItems[factElementName] = value
                                if paramFilerIdentifiers and paramFilerNames and entityIdentifierValue in paramFilerIdentifiers:
                                    prefix = paramFilerNames[paramFilerIdentifiers.index(entityIdentifierValue)]
                                    if not value.lower().startswith(prefix.lower()):
                                        self.modelXbrl.error(
                                            _("dei:{0} {1} be a case-insensitive prefix of: {2}").format(
                                                  disclosureSystem.deiFilerNameElement,
                                                  prefix, value), 
                                            "err", "EFM.6.05.24", "GFM.3.02.02")
                            elif factElementName in deiCheckLocalNames:
                                deiItems[factElementName] = value
                    else:
                        # segment present
                        
                        # note all concepts used in explicit dimensions
                        for dimValue in context.qnameDims.values():
                            if dimValue.isExplicit:
                                dimConcept = dimValue.dimension
                                memConcept = dimValue.member
                                for dConcept in (dimConcept, memConcept):
                                    if dConcept is not None:
                                        conceptsUsed[dConcept] = False
                                if (factElementName == "EntityCommonStockSharesOutstanding" and
                                    dimConcept.name == "StatementClassOfStockAxis"):
                                    commonSharesItemsByStockClass[memConcept.qname].append(f)
                                    if commonSharesClassMembers is None:
                                        commonSharesClassMembers = self.getDimMembers(dimConcept)
                                    
                #6.5.17 facts with precision
                concept = f.concept
                if concept is None:
                    modelXbrl.error(
                        _("Fact {0} of context {1} has an XBRL error").format(
                                  f.qname, f.contextID), 
                        "err", "EFM.6.04.03", "GFM.2.01.01")
                else:
                    # note fact concpts used
                    conceptsUsed[concept] = False
                    
                    if concept.isNumeric:
                        if f.precision:
                            modelXbrl.error(
                                _("Numeric fact {0} of context {1} has a precision attribute '{2}'").format(
                                          f.qname, f.contextID, f.precision), 
                                "err", "EFM.6.05.17", "GFM.1.02.16")
                    
                if validateInlineXbrlGFM:
                    if f.localName == "nonFraction" or f.localName == "fraction":
                        syms = self.signOrCurrency.findall(f.text)
                        if syms:
                            modelXbrl.error(_('ix-numeric Fact {0} of context {1} has a sign or currency symbol "{2}" in "{3}"').format(
                                     f.qname, f.contextID, "".join(s for t in syms for s in t), f.text),
                                "err", "EFM.N/A", "GFM.1.10.18")
            self.modelXbrl.profileActivity("... filer fact checks", minTimeToShow=1.0)
    
            if len(contextIDs) > 0:
                modelXbrl.error(_("The instance document contained a context(s) {0} that was(are) not used in any fact.").format(
                         ", ".join(contextIDs)), 
                    "err", "EFM.6.05.08", "GFM.1.02.08")
    
            #6.5.9 start-end durations
            if disclosureSystem.GFM or \
               documentType in ('20-F', '40-F', '10-Q', '10-K', '10', 'N-CSR', 'N-CSRS', 'NCSR', 'N-Q'):
                '''
                for c1 in contexts:
                    if c1.isStartEndPeriod:
                        end1 = c1.endDatetime
                        start1 = c1.startDatetime
                        for c2 in contexts:
                            if c1 != c2 and c2.isStartEndPeriod:
                                duration = end1 - c2.startDatetime
                                if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                    modelXbrl.error(
                                        _("Context {0} endDate and {1} startDate have a duration of one day; that is inconsistent with document type {2}.").format(
                                             c1.id, c2.id, documentType), 
                                        "err", "EFM.6.05.09", "GFM.1.2.9")
                            if self.validateEFM and c1 != c2 and c2.isInstantPeriod:
                                duration = c2.endDatetime - start1
                                if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                    modelXbrl.error(
                                        _("Context {0} startDate and {1} end (instant) have a duration of one day; that is inconsistent with document type {2}.").format(
                                             c1.id, c2.id, documentType), 
                                        "err", "EFM.6.05.10")
                '''
                durationCntxStartDatetimes = defaultdict(list)
                for cntx in contexts:
                    if cntx.isStartEndPeriod:
                        durationCntxStartDatetimes[cntx.startDatetime].append(cntx)
                for cntx in contexts:
                    end = cntx.endDatetime
                    if cntx.isStartEndPeriod:
                        for otherStart, otherCntxs in durationCntxStartDatetimes.items():
                            duration = end - otherStart
                            if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                for otherCntx in otherCntxs:
                                    if cntx != otherCntx:
                                        modelXbrl.error(
                                            _("Context {0} endDate and {1} startDate have a duration of one day; that is inconsistent with document type {2}.").format(
                                                 cntx.id, otherCntx.id, documentType), 
                                            "err", "EFM.6.05.09", "GFM.1.2.9")
                    if self.validateEFM and cntx.isInstantPeriod:
                        for otherStart, otherCntxs in durationCntxStartDatetimes.items():
                            duration = end - otherStart
                            if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                for otherCntx in otherCntxs:
                                    modelXbrl.error(
                                        _("Context {0} startDate and {1} end (instant) have a duration of one day; that is inconsistent with document type {2}.").format(
                                             otherCntx.id, cntx.id, documentType), 
                                        "err", "EFM.6.05.10")
                del durationCntxStartDatetimes
                self.modelXbrl.profileActivity("... filer instant-duration checks", minTimeToShow=1.0)
                
            #6.5.19 required context
            foundRequiredContext = False
            for c in contexts:
                if c.isStartEndPeriod:
                    if not c.hasSegment:
                        foundRequiredContext = True
                        break
            if not foundRequiredContext:
                modelXbrl.error(
                    _("Required context (no segment) not found for document type {0}.").format(
                         documentType), 
                    "err", "EFM.6.05.19", "GFM.1.02.18")
                
            #6.5.11 equivalent units
            uniqueUnitHashes = {}
            for unit in self.modelXbrl.units.values():
                h = unit.hash
                if h in uniqueUnitHashes:
                    if unit.isEqualTo(uniqueUnitHashes[h]):
                        modelXbrl.error(
                            _("Units {0} and {1} are equivalent.").format(unit.id, uniqueUnitHashes[h].id), 
                            "err", "EFM.6.05.11", "GFM.1.02.10")
                else:
                    uniqueUnitHashes[h] = unit
            del uniqueUnitHashes
            self.modelXbrl.profileActivity("... filer unit checks", minTimeToShow=1.0)
   
    
            # EFM.6.05.14, GFM.1.02.13 xml:lang tests, EFM is just 'en', GFM is full default lang
            if self.validateEFM:
                factLangStartsWith = disclosureSystem.defaultXmlLang[:2]
            else:
                factLangStartsWith = disclosureSystem.defaultXmlLang

            #6.5.12 equivalent facts
            factsForLang = {}
            factForConceptContextUnitLangHash = {}
            keysNotDefaultLang = {}
            iF1 = 1
            for f1 in modelXbrl.facts:
                # build keys table for 6.5.14
                if not f1.isNil:
                    langTestKey = "{0},{1},{2}".format(f1.qname, f1.contextID, f1.unitID)
                    factsForLang.setdefault(langTestKey, []).append(f1)
                    lang = f1.xmlLang
                    if lang and not lang.startswith(factLangStartsWith):
                        keysNotDefaultLang[langTestKey] = f1
                        
                    if disclosureSystem.GFM and f1.isNumeric and \
                        f1.decimals and f1.decimals != "INF" and not f1.isNil:
                        try:
                            vf = float(f1.value)
                            vround = round(vf, int(f1.decimals))
                            if vf != vround: 
                                modelXbrl.error(
                                    _("Fact {0} of context {1} decimals {2} value {3} has insignificant digits {4}.").format(
                                          f1.qname, f1.contextID, f1.decimals, vf, vf - vround), 
                                    "err", "GFM.1.02.26")
                        except (ValueError,TypeError):
                            modelXbrl.error(
                                _("Fact {0} of context {1} decimals {2} value {3} causes Value Error exception.").format(
                                      f1.qname, f1.contextID, f1.decimals, f1.value), 
                                "err", "GFM.1.02.26")
                # 6.5.12 test
                h = f1.conceptContextUnitLangHash
                if h in factForConceptContextUnitLangHash:
                    f2 = factForConceptContextUnitLangHash[h]
                    if f1.qname == f2.qname and \
                       f1.contextID == f2.contextID and \
                       f1.unitID == f2.unitID and \
                       f1.xmlLang == f2.xmlLang:
                        modelXbrl.error(
                            _("Facts {0} of context {1} and {2} are equivalent.").format(
                                      f1.qname, f1.contextID, f2.contextID), 
                            "err", "EFM.6.05.12", "GFM.1.02.11")
                else:
                    factForConceptContextUnitLangHash[h] = f1
                iF1 += 1
            del factForConceptContextUnitLangHash
            self.modelXbrl.profileActivity("... filer fact checks", minTimeToShow=1.0)
    
            #6.5.14 facts without english text
            for keyNotDefaultLang, factNotDefaultLang in keysNotDefaultLang.items():
                anyDefaultLangFact = False
                for fact in factsForLang[keyNotDefaultLang]:
                    if fact.xmlLang.startswith(factLangStartsWith):
                        anyDefaultLangFact = True
                        break
                if not anyDefaultLangFact:
                    self.modelXbrl.error(
                        _("Fact {0} of context {1} has text of xml:lang '{2}' without corresponding {3} text").format(
                                  factNotDefaultLang.qname, factNotDefaultLang.contextID, factNotDefaultLang.xmlLang,
                                  factLangStartsWith), 
                        "err", "EFM.6.05.14", "GFM.1.02.13")
                    
            #label validations
            if not labelsRelationshipSet:
                self.modelXbrl.error(
                    _("A label linkbase is required but was not found"), 
                    "err", "EFM.6.10.01", "GFM.1.05.01")
            else:
                for concept in conceptsUsed.keys():
                    hasDefaultLangStandardLabel = False
                    dupLabels = set()
                    for modelLabelRel in labelsRelationshipSet.fromModelObject(concept):
                        modelLabel = modelLabelRel.toModelObject
                        if modelLabel.xmlLang.startswith(disclosureSystem.defaultXmlLang) and \
                           modelLabel.role == XbrlConst.standardLabel:
                            hasDefaultLangStandardLabel = True
                        dupDetectKey = (modelLabel.role,modelLabel.xmlLang)
                        if dupDetectKey in dupLabels:
                            modelXbrl.error(
                                _("Concept {0} has duplicated labels for role {1} lang {2}.").format(
                                    concept.qname, dupDetectKey[0], dupDetectKey[1]),
                                "err", "EFM.6.10.02", "GFM.1.5.2")
                        else:
                            dupLabels.add(dupDetectKey)
                            
                    #6 10.1 en-US standard label
                    if not hasDefaultLangStandardLabel:
                        modelXbrl.error(
                            _("Concept {0} is missing an {1} standard label.").format(
                                concept.qname, disclosureSystem.defaultLanguage),
                            "err", "EFM.6.10.01", "GFM.1.05.01")
                        
                    #6 10.3 default lang label for every role
                    dupLabels.add(("zzzz",disclosureSystem.defaultXmlLang)) #to allow following loop
                    priorRole = None
                    hasDefaultLang = True
                    for role, lang in sorted(dupLabels):
                        if role != priorRole:
                            if not hasDefaultLang:
                                modelXbrl.error(
                                    _("Concept {0} is missing an {1} label for role {2}.").format(
                                        concept.qname, disclosureSystem.defaultLanguage, priorRole),
                                    "err", "EFM.6.10.03", "GFM.1.5.3")
                            hasDefaultLang = False
                            priorRole = role
                        if lang is not None and lang.startswith(disclosureSystem.defaultXmlLang):
                            hasDefaultLang = True
                        
    
            #6.5.15 facts with xml in text blocks
            if self.validateEFMorGFM:
                ValidateFilingText.validateTextBlockFacts(modelXbrl)
            
                if amendmentFlag is None:
                    modelXbrl.error(
                        _("{0} is not found in the default context").format(
                            disclosureSystem.deiAmendmentFlagElement), 
                        "wrn", "EFM.6.05.20", "GFM.3.02.01")
        
                if not documentPeriodEndDate:
                    modelXbrl.error(
                        _("{0} is required and was not found in the default context").format(
                           disclosureSystem.deiDocumentPeriodEndDateElement), 
                        "err", "EFM.6.05.20", "GFM.3.02.01")
                else:
                    dateMatch = self.datePattern.match(documentPeriodEndDate)
                    if not dateMatch or dateMatch.lastindex != 3:
                        modelXbrl.error(
                            _("{0} is in the default context is incorrect '{1}'").format(
                                disclosureSystem.deiDocumentPeriodEndDateElement,
                                documentPeriodEndDate), 
                            "err", "EFM.6.05.20", "GFM.3.02.01")
            self.modelXbrl.profileActivity("... filer label and text checks", minTimeToShow=1.0)
    
            if self.validateEFM:
                if amendmentFlag == "true" and not amendmentDescription:
                    modelXbrl.error(
                        _("AmendmentFlag is true in context {0} so AmendmentDescription is also required").format(
                                  f.contextID), 
                        "wrn", "EFM.6.05.20")
        
                if amendmentDescription and ((not amendmentFlag) or amendmentFlag == "false"):
                    modelXbrl.error(
                        _("AmendmentDescription can not be provided when AmendmentFlag is not true in context {0}").format(
                                  f.contextID), 
                        "wrn", "EFM.6.05.20")
                    
                if not documentType:
                    modelXbrl.error(
                        _("DocumentType is required and was not found in the default context"), 
                        "err", "EFM.6.05.20")
                elif documentType not in ("10", "10-K", "10-Q", "20-F", "40-F", "6-K", "8-K", 
                                          "F-1", "F-10", "F-3", "F-4", "F-9", "S-1", "S-11", 
                                          "S-3", "S-4", 
                                          "8-K/A", 
                                          "S-1/A", "S-11/A", "S-3/A", "S-4/A", 
                                          "485BPOS", "497 ", "NCSR", "N-CSR", "N-Q", 
                                          "N-Q/A",
                                          "Other"):
                    modelXbrl.error(
                        _("DocumentType '{0}' of the default context was not recognized").format(
                              documentType), 
                        "err", "EFM.6.05.20")
                    
                # 6.5.21
                for doctypesRequired, deiItemsRequired in (
                      (("10-K",
                        "10-Q",
                        "20-F",
                        "40-F",
                        "6-K", "NCSR", "N-CSR", "N-CSRS", "N-Q",
                        "10", "S-1", "S-3", "S-4", "S-11",
                        "8-K", "F-1", "F-3", "F-10", "497", "485BPOS",
                        "Other"),
                        ("EntityRegistrantName", "EntityCentralIndexKey")),
                      (("10-K",
                        "20-F",
                        "40-F"),
                       ("EntityCurrentReportingStatus",)),
                     (("10-K",),
                      ("EntityVoluntaryFilers", "EntityPublicFloat")),
                      (("10-K",
                        "10-Q",
                        "20-F",
                        "40-F",
                        "6-K", "NCSR", "N-CSR", "N-CSRS", "N-Q"),
                        ("CurrentFiscalYearEndDate", "DocumentFiscalYearFocus", "DocumentFiscalPeriodFocus")),
                      (("10-K",
                        "10-Q",
                        "20-F",
                        "10", "S-1", "S-3", "S-4", "S-11"),
                        ("EntityFilerCategory",)),
                       (("10-K",
                         "20-F"),
                         ("EntityWellKnownSeasonedIssuer",))
                ):
                    if documentType in doctypesRequired:
                        for deiItem in deiItemsRequired:
                            if deiItem not in deiItems or deiItems[deiItem] == "":
                                modelXbrl.error(
                                    _("dei:{0} is required for DocumentType '{1}' in the default context").format(
                                          deiItem, documentType), 
                                    "err", "EFM.6.05.21")
                                
                if documentType in ("10-K", "10-Q", "20-F", "40-F"):
                    defaultSharesOutstanding = deiItems.get("EntityCommonStockSharesOutstanding")
                    if commonSharesClassMembers:
                        if defaultSharesOutstanding:
                            modelXbrl.error(
                                _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '{0}' but not in the default context because there are multiple classes of common shares").format(
                                      documentType), 
                                "err", "EFM.6.05.26")
                        missingClasses = commonSharesClassMembers - commonSharesItemsByStockClass.keys()
                        if missingClasses:
                            modelXbrl.error(
                                _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '{0}' but missing in these stock classes: {1}").format(
                                      documentType, ", ".join([str(c) for c in missingClasses])), 
                                "err", "EFM.6.05.26")
                        for mem, facts in commonSharesItemsByStockClass.items():
                            if len(facts) != 1:
                                modelXbrl.error(
                                    _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '{0}' but only one per stock class {1}").format(
                                          documentType, mem), 
                                    "err", "EFM.6.05.26")
                            elif facts[0].context.instantDatetime != commonStockMeasurementDatetime:
                                modelXbrl.error(
                                    _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '{0}' in stock class {1} with measurement date {2}").format(
                                          documentType, mem, commonStockMeasurementDatetime), 
                                    "err", "EFM.6.05.26")
                    elif not defaultSharesOutstanding:
                        modelXbrl.error(
                            _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '{0}' in the default context because there are not multiple classes of common shares").format(
                                  documentType), 
                            "err", "EFM.6.05.26")
                
            elif disclosureSystem.GFM:
                for deiItem in (
                        disclosureSystem.deiCurrentFiscalYearEndDateElement, 
                        disclosureSystem.deiDocumentFiscalYearFocusElement, 
                        disclosureSystem.deiFilerNameElement):
                    if deiItem not in deiItems or deiItems[deiItem] == "":
                        modelXbrl.error(
                            _("dei:{0} is required in the default context").format(
                                  deiItem), 
                            "err", "GFM.3.02.01")
            self.modelXbrl.profileActivity("... filer required facts checks", minTimeToShow=1.0)
    
            #6.5.25 domain items as facts
            if self.validateEFM:
                for f in modelXbrl.facts:
                    concept = f.concept
                    if concept is not None and concept.type is not None and concept.type.isDomainItemType:
                        modelXbrl.error(
                            _("Domain item {0} in context {1} may not appear as a fact").format(
                                f.qname, f.contextID), 
                            "err", "EFM.6.05.25")
    
            #6.5.27 footnote elements, etc
            footnoteLinkNbr = 0
            for footnoteLinkElt in xbrlInstDoc.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}footnoteLink"):
                if isinstance(footnoteLinkElt,ModelObject):
                    footnoteLinkNbr += 1
                    
                    linkrole = footnoteLinkElt.get("{http://www.w3.org/1999/xlink}role")
                    if linkrole != XbrlConst.defaultLinkRole:
                        modelXbrl.error(
                            _("FootnoteLink {0} has disallowed role {1}").format(
                                footnoteLinkNbr, linkrole), 
                            "err", "EFM.6.05.28", "GFM.1.02.20")
        
                    # find modelLink of this footnoteLink
                    modelLink = modelXbrl.baseSetModelLink(footnoteLinkElt)
                    relationshipSet = modelXbrl.relationshipSet("XBRL-footnotes", linkrole)
                    if (modelLink is None) or (not relationshipSet):
                        continue    # had no child elements to parse
                    locNbr = 0
                    arcNbr = 0
                    for child in footnoteLinkElt.getchildren():
                        if isinstance(child,ModelObject):
                            xlinkType = child.get("{http://www.w3.org/1999/xlink}type")
                            if child.namespaceURI != XbrlConst.link or \
                               xlinkType not in ("locator", "resource", "arc") or \
                               child.localName not in ("loc", "footnote", "footnoteArc"):
                                    modelXbrl.error(
                                        _("FootnoteLink {0} has disallowed child element <{1}>").format(
                                            footnoteLinkNbr, child.prefixedName), 
                                        "err", "EFM.6.05.27", "GFM.1.02.19")
                            elif xlinkType == "locator":
                                locNbr += 1
                                locrole = child.get("{http://www.w3.org/1999/xlink}role")
                                if locrole is not None and (disclosureSystem.GFM or \
                                                            not disclosureSystem.uriAuthorityValid(locrole)): 
                                    modelXbrl.error(
                                        _("FootnoteLink {0} loc {1} has disallowed role {2}").format(
                                            footnoteLinkNbr, locNbr, locrole), 
                                        "err", "EFM.6.05.29", "GFM.1.02.21")
                                href = child.get("{http://www.w3.org/1999/xlink}href")
                                if not href.startswith("#"): 
                                    modelXbrl.error(
                                        _("FootnoteLink {0} loc {1} has disallowed href {2}").format(
                                            footnoteLinkNbr, locNbr, href), 
                                        "err", "EFM.6.05.32", "GFM.1.02.23")
                                else:
                                    label = child.get("{http://www.w3.org/1999/xlink}label")
                            elif xlinkType == "arc":
                                arcNbr += 1
                                arcrole = child.get("{http://www.w3.org/1999/xlink}arcrole")
                                if (self.validateEFM and not disclosureSystem.uriAuthorityValid(arcrole)) or \
                                   (disclosureSystem.GFM  and arcrole != XbrlConst.factFootnote and arcrole != XbrlConst.factExplanatoryFact): 
                                    modelXbrl.error(
                                        _("FootnoteLink {0} arc {1} has disallowed arcrole {2}").format(
                                            footnoteLinkNbr, arcNbr, arcrole), 
                                        "err", "EFM.6.05.30", "GFM.1.02.22")
                            elif xlinkType == "resource": # footnote
                                footnoterole = child.get("{http://www.w3.org/1999/xlink}role")
                                if footnoterole == "":
                                    modelXbrl.error(
                                        _("Footnote {0} is missing a role").format(
                                            child.get("{http://www.w3.org/1999/xlink}label")), 
                                        "err", "EFM.6.05.28", "GFM.1.2.20")
                                elif (self.validateEFM and not disclosureSystem.uriAuthorityValid(footnoterole)) or \
                                     (disclosureSystem.GFM  and footnoterole != XbrlConst.footnote): 
                                    modelXbrl.error(
                                        _("Footnote {0} has disallowed role {1}").format(
                                            child.get("{http://www.w3.org/1999/xlink}label"),
                                            footnoterole), 
                                        "err", "EFM.6.05.28", "GFM.1.2.20")
                                if self.validateEFM:
                                    ValidateFilingText.validateFootnote(modelXbrl, child)
                                # find modelResource for this element
                                modelResource = modelLink.modelResourceOfResourceElement(child)
                                foundFact = False
                                if XmlUtil.text(child) != "":
                                    for relationship in relationshipSet.toModelObject(modelResource):
                                        if isinstance(relationship.fromModelObject, ModelFact):
                                            foundFact = True
                                            break
                                    if not foundFact:
                                        modelXbrl.error(
                                            _("FootnoteLink {0} footnote {1} has no linked fact").format(
                                                footnoteLinkNbr, 
                                                child.get("{http://www.w3.org/1999/xlink}label")), 
                                            "err", "EFM.6.05.33", "GFM.1.02.24")
            self.modelXbrl.profileActivity("... filer rfootnotes checks", minTimeToShow=1.0)

        # all-labels and references checks
        defaultLangStandardLabels = {}
        for concept in modelXbrl.qnameConcepts.values():
            conceptHasDefaultLangStandardLabel = False
            for modelLabelRel in labelsRelationshipSet.fromModelObject(concept):
                modelLabel = modelLabelRel.toModelObject
                role = modelLabel.role
                text = modelLabel.text
                lang = modelLabel.xmlLang
                if role == XbrlConst.documentationLabel:
                    if concept.modelDocument.targetNamespace in disclosureSystem.standardTaxonomiesDict:
                        modelXbrl.error(
                            _("Concept {0} of a standard taxonomy cannot have a documentation label, in {1}.").format(
                                concept.qname, text, modelLabel.modelDocument.basename),
                            "err", "EFM.6.10.05", "GFM.1.05.05", "SBR.NL.2.1.0.08")
                elif text and lang and lang.startswith(disclosureSystem.defaultXmlLang):
                    if role == XbrlConst.standardLabel:
                        if text in defaultLangStandardLabels:
                            modelXbrl.error(
                                _("Same labels for concepts {0} and {1} for {2} standard role: {3}, in {4}.").format(
                                    concept.qname, defaultLangStandardLabels[text].qname, disclosureSystem.defaultLanguage, text, modelLabel.modelDocument.basename),
                                "err", "EFM.6.10.04", "GFM.1.05.04")
                        else:
                            defaultLangStandardLabels[text] = concept
                        conceptHasDefaultLangStandardLabel = True
                    if len(text) > 511:
                        modelXbrl.error(
                            _("Xbrl File {0}, label for concept {1} role {2} length {3} must be shorter than 511 characters: {4}").format(
                                modelLabel.modelDocument.basename, concept.qname, role, len(text), text[:80]),
                            "err", "EFM.6.10.06", "GFM.1.05.06")
                    match = modelXbrl.modelManager.disclosureSystem.labelCheckPattern.search(text)
                    if match:
                        modelXbrl.error(
                            _('Xbrl File {0}, label for concept {1} role {2} has disallowed characters: "{3}"').format(
                                modelLabel.modelDocument.basename, concept.qname, role, match.group()),
                            "err", "EFM.6.10.06", "GFM.1.05.07", "SBR.NL.2.3.8.07")
                if text is not None and len(text) > 0 and \
                   (modelXbrl.modelManager.disclosureSystem.labelTrimPattern.match(text[0]) or \
                    modelXbrl.modelManager.disclosureSystem.labelTrimPattern.match(text[-1])):
                    modelXbrl.error(
                        _("Xbrl File {0}, label for concept {1} role {2} lang {3} is not trimmed: {4}").format(
                            modelLabel.modelDocument.basename, concept.qname, role, lang, text),
                        "err", "EFM.6.10.08", "GFM.1.05.08")
            for modelRefRel in referencesRelationshipSetWithProhibits.fromModelObject(concept):
                modelReference = modelRefRel.toModelObject
                text = modelReference.text
                #6.18.1 no reference to company extension concepts
                if concept.modelDocument.targetNamespace not in disclosureSystem.standardTaxonomiesDict:
                    modelXbrl.error(
                        _("Xbrl File {0}, references for extension concept {0} are not allowed: {1}").format(
                            modelReference.modelDocument.basename, concept.qname, text),
                        "err", "EFM.6.18.01", "GFM.1.9.1")
                elif (self.validateEFM or self.validateSBRNL) and \
                     modelRefRel.modelDocument.uri not in disclosureSystem.standardTaxonomiesDict: 
                    #6.18.2 no extension to add or remove references to standard concepts
                    modelXbrl.error(
                        _("Xbrl File {0}, references for standard taxonomy concept {0} are not allowed in an extension linkbase: {1}").format(
                            modelReference.modelDocument.basename, concept.qname, text),
                        "err", "EFM.6.18.02", "SBR.NL.2.1.0.08")
            if self.validateSBRNL:
                if not conceptHasDefaultLangStandardLabel and (concept.isItem or concept.isTuple):
                    modelXbrl.error(
                        _("Concept {0} missing standard label in local language.").format(
                            concept.qname),
                        "err", "SBR.NL.2.2.2.26")
                if concept.modelDocument.targetNamespace not in disclosureSystem.standardTaxonomiesDict:
                    if (concept not in presentationRelationshipSet.toModelObject(concept) and
                        concept not in presentationRelationshipSet.fromModelObject(concept)):
                        modelXbrl.error(
                            _("Concept {0} not referred to by presentation relationship.").format(
                                concept.qname),
                            "err", "SBR.NL.2.2.0.21")
        self.modelXbrl.profileActivity("... filer concepts checks", minTimeToShow=1.0)

        defaultLangStandardLabels = None #dereference

        # checks on all documents: instance, schema, instance                                
        ValidateFilingDTS.checkDTS(self, modelXbrl.modelDocument, [])
        self.modelXbrl.profileActivity("... filer DTS checks", minTimeToShow=1.0)

        
        conceptsUsedWithPreferredLabels = defaultdict(list)
        usedCalcsPresented = defaultdict(set) # pairs of concepts objectIds used in calc
        drsELRs = set()
        
        # do calculation, then presentation, then other arcroles
        for arcroleFilter in (XbrlConst.summationItem, XbrlConst.parentChild, "*"):
            for baseSetKey, baseSetModelLinks  in modelXbrl.baseSets.items():
                arcrole, ELR, linkqname, arcqname = baseSetKey
                if ELR and not arcrole.startswith("XBRL-"):
                    # assure summationItem, then parentChild, then others
                    if not (arcroleFilter == arcrole or
                            arcroleFilter == "*" and arcrole not in (XbrlConst.summationItem, XbrlConst.parentChild)):
                        continue
                    if self.validateEFMorGFM or (self.validateSBRNL and arcrole in (XbrlConst.conceptLabel, XbrlConst.elementLabel)):
                        ineffectiveArcs = ModelRelationshipSet.ineffectiveArcs(baseSetModelLinks, arcrole)
                        #validate ineffective arcs
                        for modelRel in ineffectiveArcs:
                            if modelRel.fromModelObject is not None and modelRel.toModelObject is not None:
                                self.modelXbrl.error(
                                    _("Linkbase {0} ineffective arc {1} in link role {2} arcrole {3} from {4} to {5}").format(
                                          modelRel.modelDocument.basename,
                                          modelRel.qname, modelRel.linkrole, modelRel.arcrole,
                                          modelRel.fromModelObject.qname, modelRel.toModelObject.qname), 
                                    "err", "EFM.6.09.03", "GFM.1.04.03", "SBR.NL.2.2.1.05")
                    if arcrole == XbrlConst.parentChild:
                        conceptsPresented = set()
                        # 6.12.2 check for distinct order attributes
                        for relFrom, rels in modelXbrl.relationshipSet(
                                 arcrole, ELR).fromModelObjects().items():
                            targetConceptPreferredLabels = defaultdict(set)
                            orderRels = {}
                            firstRel = True
                            relFromUsed = True
                            for rel in rels:
                                if firstRel:
                                    firstRel = False
                                    if relFrom in conceptsUsed:
                                        conceptsUsed[relFrom] = True # 6.12.3, has a pres relationship
                                        relFromUsed = True
                                relTo = rel.toModelObject
                                if relTo in conceptsUsed:
                                    conceptsUsed[relTo] = True # 6.12.3, has a pres relationship
                                    preferredLabel = rel.preferredLabel
                                    if preferredLabel and preferredLabel != "":
                                        conceptsUsedWithPreferredLabels[relTo].append(preferredLabel)
                                    # 6.12.5 distinct preferred labels in base set
                                    preferredLabels = targetConceptPreferredLabels[relTo]
                                    if preferredLabel in preferredLabels:
                                        self.modelXbrl.error(
                                            _("Concept {0} has duplicate preferred label {1} in link role {2}").format(
                                                  relTo.qname, preferredLabel, rel.linkrole), 
                                            "err", "EFM.6.12.05", "GFM.1.06.05")
                                    else:
                                        preferredLabels.add(preferredLabel)
                                    if relFromUsed:
                                        # 6.14.5
                                        conceptsPresented.add(relFrom.objectIndex)
                                        conceptsPresented.add(relTo.objectIndex)
                                order = rel.order
                                if order in orderRels:
                                    self.modelXbrl.error(
                                        _("Duplicate presentation relations from concept {0} for order {1} in base set role {2} to concept {3} and to concept {4}").format(
                                              relFrom.qname, order, rel.linkrole, 
                                              rel.toModelObject.qname, orderRels[order].toModelObject.qname), 
                                        "err", "EFM.6.12.02", "GFM.1.06.02", "SBR.NL.2.3.4.05")
                                else:
                                    orderRels[order] = rel
                        for conceptPresented in conceptsPresented:
                            if conceptPresented in usedCalcsPresented:
                                usedCalcPairingsOfConcept = usedCalcsPresented[conceptPresented]
                                if len(usedCalcPairingsOfConcept & conceptsPresented) > 0:
                                    usedCalcPairingsOfConcept -= conceptsPresented
                    elif arcrole == XbrlConst.summationItem:
                        if self.validateEFMorGFM:
                            # 6.14.3 check for relation concept periods
                            fromRelationships = modelXbrl.relationshipSet(arcrole,ELR).fromModelObjects()
                            for relFrom, rels in fromRelationships.items():
                                orderRels = {}
                                for rel in rels:
                                    relTo = rel.toModelObject
                                    # 6.14.03 must have matched period types across relationshp
                                    if relFrom.periodType != relTo.periodType:
                                        self.modelXbrl.error(
                                            _("Calculation relationship period types mismatched in base set role {0} from {1} to {2}").format(
                                                  rel.linkrole, relFrom.qname, relTo.qname), 
                                            "err", "EFM.6.14.03", "GFM.1.07.03")
                                    # 6.14.5 concepts used must have pres in same ext link
                                    if relFrom in conceptsUsed and relTo in conceptsUsed:
                                        fromObjId = relFrom.objectIndex
                                        toObjId = relTo.objectIndex
                                        if fromObjId < toObjId:
                                            usedCalcsPresented[fromObjId].add(toObjId)
                                        else:
                                            usedCalcsPresented[toObjId].add(fromObjId)
                                            
                                    order = rel.order
                                    if order in orderRels and disclosureSystem.GFM:
                                        self.modelXbrl.error(
                                            _("Duplicate calculations relations from concept {0} for order {1} in base set role {2} to concept {3} and to concept {4}").format(
                                                  relFrom.qname, order, rel.linkrole, 
                                                  rel.toModelObject.qname, orderRels[order].toModelObject.qname), 
                                            "err", "EFM.N/A", "GFM.1.07.06")
                                    else:
                                        orderRels[order] = rel
                                if self.directedCycle(relFrom,relFrom,fromRelationships):
                                    self.modelXbrl.error(
                                        _("Calculation relationships have a directed cycle in base set role {0} starting from {1}").format(
                                              ELR, relFrom.qname), 
                                        "err", "EFM.6.14.04", "GFM.1.07.04")
                        elif self.validateSBRNL:
                            # find a calc relationship to get the containing document name
                            for modelRel in self.modelXbrl.relationshipSet(arcrole).modelRelationships:
                                self.modelXbrl.error(
                                    _("Calculation linkbase {0}").format(
                                          modelRel.modelDocument.basename, modelRel.arcrole), 
                                    "err", "SBR.NL.2.3.9.01")
                                break
                                
                    elif arcrole == XbrlConst.all or arcrole == XbrlConst.notAll:
                        drsELRs.add(ELR)
                        
                    elif arcrole == XbrlConst.dimensionDomain or arcrole == XbrlConst.dimensionDefault and \
                         self.validateEFMorGFM:
                        # 6.16.3 check domain targets in extension linkbases are domain items
                        fromRelationships = modelXbrl.relationshipSet(arcrole,ELR).fromModelObjects()
                        for relFrom, rels in fromRelationships.items():
                            for rel in rels:
                                relTo = rel.toModelObject
    
                                if not (relTo.type is not None and relTo.type.isDomainItemType) and \
                                   rel.modelDocument.uri not in disclosureSystem.standardTaxonomiesDict:
                                    self.modelXbrl.error(
                                        _("Definition relationship from {0} to {1} in role {2} requires domain item target").format(
                                              relFrom.qname, relTo.qname, rel.linkrole), 
                                        "err", "EFM.6.16.03", "GFM.1.08.03")

                    elif arcrole == XbrlConst.dimensionDefault and self.validateSBRNL:
                        for modelRel in self.modelXbrl.relationshipSet(arcrole).modelRelationships:
                            self.modelXbrl.error(
                                _("Dimension-default in linkbase {0} from {1} to {2} in role {3} is not allowed").format(
                                      modelRel.modelDocument.basename,
                                      modelRel.fromModelObject.qname, modelRel.toModelObject.qname, 
                                      modelRel.arcrole), 
                                "err", "SBR.NL.2.3.6.05")
                           
                    # definition tests (GFM only, for now)
                    if XbrlConst.isStandardOrXdtArcrole(arcrole) and disclosureSystem.GFM: 
                        fromRelationships = modelXbrl.relationshipSet(arcrole,ELR).fromModelObjects()
                        for relFrom, rels in fromRelationships.items():
                            orderRels = {}
                            for rel in rels:
                                relTo = rel.toModelObject
                                order = rel.order
                                if order in orderRels and disclosureSystem.GFM:
                                    self.modelXbrl.error(
                                        _("Duplicate definitions relations from concept {0} for order {1} in base set role {2} to concept {3} and to concept {4}").format(
                                              relFrom.qname, order, rel.linkrole, 
                                              rel.toModelObject.qname, orderRels[order].toModelObject.qname), 
                                        "err", "GFM.1.08.10")
                                else:
                                    orderRels[order] = rel
                                if (arcrole not in (XbrlConst.dimensionDomain, XbrlConst.domainMember) and
                                    rel.get("{http://xbrl.org/2005/xbrldt}usable") == "false"):
                                    self.modelXbrl.error(
                                        _("Disallowed xbrldt:usable='false' attribute on {0} relationship from concept {1} in base set role {2} to concept {3}").format(
                                              os.path.basename(arcrole), relFrom.qname, rel.linkrole, rel.toModelObject.qname), 
                                        "err", "GFM.1.08.11")

        self.modelXbrl.profileActivity("... filer relationships checks", minTimeToShow=1.0)

                                
        # checks on dimensions
        ValidateFilingDimensions.checkDimensions(self, drsELRs)
        self.modelXbrl.profileActivity("... filer dimensions checks", minTimeToShow=1.0)
                                        
        for concept, hasPresentationRelationship in conceptsUsed.items():
            if not hasPresentationRelationship:
                self.modelXbrl.error(
                    _("Concept {0} does not participate in an effective presentation relationship").format(
                          concept.qname), 
                    "err", "EFM.6.12.03", "GFM.1.6.3")
                
        for fromIndx, toIndxs in usedCalcsPresented.items():
            for toIndx in toIndxs:
                self.modelXbrl.error(
                    _("Used calculation relationship from {0} to {1} does not participate in an effective presentation relationship").format(
                          self.modelXbrl.modelObject(fromIndx).qname, self.modelXbrl.modelObject(toIndx).qname), 
                    "err", "EFM.6.14.05", "GFM.1.7.5")
                
        for concept, preferredLabels in conceptsUsedWithPreferredLabels.items():
            for preferredLabel in preferredLabels:
                hasDefaultLangPreferredLabel = False
                for modelLabelRel in labelsRelationshipSet.fromModelObject(concept):
                    modelLabel = modelLabelRel.toModelObject
                    if modelLabel.xmlLang.startswith(disclosureSystem.defaultXmlLang) and \
                       modelLabel.role == preferredLabel:
                        hasDefaultLangPreferredLabel = True
                        break
                if not hasDefaultLangPreferredLabel:
                    self.modelXbrl.error(
                        _("Concept {0} missing {1} preferred labels for role {2}").format(
                            concept.qname, disclosureSystem.defaultLanguage, preferredLabel),
                        "err", "EFM.6.12.04", "GFM.1.06.04")
                
        # 6 16 4, 1.16.5 Base sets of Domain Relationship Sets testing

        modelXbrl.modelManager.showStatus(_("ready"), 2000)
                    
    def directedCycle(self, relFrom, origin, fromRelationships):
        if relFrom in fromRelationships:
            for rel in fromRelationships[relFrom]:
                relTo = rel.toModelObject
                if relTo == origin or self.directedCycle(relTo, origin, fromRelationships):
                    return True
        return False
    
    def getDimMembers(self, dim, default=None, rels=None, members=None, visited=None):
        if rels is None: 
            visited = set()
            members = set()
            for rel in self.modelXbrl.relationshipSet(XbrlConst.dimensionDefault).fromModelObject(dim):
                default = rel.toModelObject
            rels = self.modelXbrl.relationshipSet(XbrlConst.dimensionDomain).fromModelObject(dim)
        for rel in rels:
            relTo = rel.toModelObject
            if rel.isUsable and relTo != default:
                members.add(relTo.qname)
            toELR = rel.targetRole
            if not toELR: toELR = rel.linkrole
            if relTo not in visited:
                visited.add(relTo)
                domMbrRels = self.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(relTo)
                self.getDimMembers(dim, default, domMbrRels, members, visited)
                visited.discard(relTo)
        return members   

