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

datePattern = None
GFMcontextDatePattern = None
signOrCurrencyPattern = None


class ValidateFiling(ValidateXbrl.ValidateXbrl):
    def __init__(self, modelXbrl):
        super().__init__(modelXbrl)
        
        global datePattern, GFMcontextDatePattern, signOrCurrencyPattern
        
        if datePattern is None:
            datePattern = re.compile(r"([12][0-9]{3})-([01][0-9])-([0-3][0-9])")
            GFMcontextDatePattern = re.compile(r"^[12][0-9]{3}-[01][0-9]-[0-3][0-9]$")
            signOrCurrencyPattern = re.compile("^(-)[0-9]+|[^eE](-)[0-9]+|(\\()[0-9].*(\\))|([$\u20ac£¥])")

        
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
                            modelXbrl.error(("EFM.6.05.01", "GFM.1.02.01"),
                                _("Invalid entity identifier scheme: %(scheme)s"),
                                modelObject=entityIdentifierElt, scheme=schemeAttr)
                        entityIdentifier = XmlUtil.text(entityIdentifierElt)
                        if not disclosureSystem.identifierValuePattern.match(entityIdentifier):
                            modelXbrl.error(("EFM.6.05.02", "GFM.1.02.02"),
                                _("Invalid entity identifier %(entityIdentifierName)s: %(entityIdentifer)s"),
                                modelObject=entityIdentifierElt,  
                                entityIdentifierName=disclosureSystem.identifierValueName,
                                entityIdentifer=entityIdentifier)
                        if not entityIdentifierValue:
                            entityIdentifierValue = entityIdentifier
                        elif entityIdentifier != entityIdentifierValue:
                            modelXbrl.error(("EFM.6.05.03", "GFM.1.02.03"),
                                _("Multiple %(entityIdentifierName)ss: %(entityIdentifer)s, %(entityIdentifer2)s"),
                                modelObject=entityIdentifierElt,  
                                entityIdentifierName=disclosureSystem.identifierValueName,
                                entityIdentifer=entityIdentifierValue,
                                entityIdentifer2=entityIdentifier) 
                self.modelXbrl.profileActivity("... filer identifier checks", minTimeToShow=1.0)
    
            #6.5.7 duplicated contexts
            contexts = modelXbrl.contexts.values()
            contextIDs = set()
            uniqueContextHashes = {}
            for context in contexts:
                contextID = context.id
                contextIDs.add(contextID)
                h = context.contextDimAwareHash
                if h in uniqueContextHashes:
                    if context.isEqualTo(uniqueContextHashes[h]):
                        modelXbrl.error(("EFM.6.05.07", "GFM.1.02.07"),
                            _("Context ID %(context)s is equivalent to context ID %(context2)s"),
                            modelObject=context, context=contextID, context2=uniqueContextHashes[h].id)
                else:
                    uniqueContextHashes[h] = context
                    
                #GFM no time in contexts
                if self.validateGFM:
                    for dateElt in XmlUtil.children(context, XbrlConst.xbrli, ("startDate", "endDate", "instant")):
                        dateText = XmlUtil.text(dateElt)
                        if not GFMcontextDatePattern.match(dateText):
                            modelXbrl.error("GFM.1.02.25",
                                _("Context id %(context)s %(elementName)s invalid content %(value)s"),
                                modelObject=dateElt, context=contextID, 
                                elementName=dateElt.prefixedName, value=dateText)
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
                    modelXbrl.error(("EFM.6.05.04", "GFM.1.02.04", "SBR.NL.2.3.5.06"),
                        _("%(elementName)s element not allowed in context Id: %(context)s"),
                        modelObject=context, elementName=notAllowed, context=contextID)
        
                #6.5.5 segment only explicit dimensions
                for contextName in ("{http://www.xbrl.org/2003/instance}segment","{http://www.xbrl.org/2003/instance}scenario"):
                    for segScenElt in context.iterdescendants(contextName):
                        if isinstance(segScenElt,ModelObject):
                            childTags = ", ".join([child.prefixedName for child in segScenElt.iterchildren()
                                                   if isinstance(child,ModelObject) and 
                                                   child.tag != "{http://xbrl.org/2006/xbrldi}explicitMember"])
                            if len(childTags) > 0:
                                modelXbrl.error(("EFM.6.05.05", "GFM.1.02.05"),
                                                _("Segment of context Id %(context)s has disallowed content: %(content)s"),
                                                modelObject=context, context=contextID, content=childTags)
            del uniqueContextHashes
            self.modelXbrl.profileActivity("... filer context checks", minTimeToShow=1.0)
    
    
            #fact items from standard context (no dimension)
            amendmentDescription = None
            amendmentDescriptionFact = None
            amendmentFlag = None
            amendmentFlagFact = None
            documentPeriodEndDate = None
            documentType = None
            documentTypeFact = None
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
                        self.modelXbrl.error(("EFM.6.05.24", "GFM.3.02.02"),
                            _("parameters for cikList and cikNameList different list entry counts: %(cikList)s, %(cikNameList)s"),
                            modelXbrl=modelXbrl, cikList=paramFilerIdentifiers, cikNameList=paramFilerNames)
                        
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
                                ammedmentFlagFact = f
                            elif factElementName == "AmendmentDescription":
                                amendmentDescription = value
                                amendmentDescriptionFact = f
                            elif factElementName == disclosureSystem.deiDocumentPeriodEndDateElement:
                                documentPeriodEndDate = value
                                commonStockMeasurementDatetime = context.endDatetime
                            elif factElementName == "DocumentType":
                                documentType = value
                                documentTypeFact = f
                            elif factElementName == disclosureSystem.deiFilerIdentifierElement:
                                deiItems[factElementName] = value
                                if entityIdentifierValue != value:
                                    self.modelXbrl.error(("EFM.6.05.23", "GFM.3.02.02"),
                                        _("dei:%(elementName)s %(value)s is must match the context entity identifier %(entityIdentifer)s"),
                                        modelObject=f, elementName=disclosureSystem.deiFilerIdentifierElement,
                                        value=value, entityIdentifer=entityIdentifierValue)
                                if paramFilerIdentifier and value != paramFilerIdentifier:
                                    self.modelXbrl.error(("EFM.6.05.23", "GFM.3.02.02"),
                                        _("dei:%(elementName)s %(value)s must match submission: %(filerIdentifer)s"),
                                        modelObject=f, elementName=disclosureSystem.deiFilerIdentifierElement,
                                        value=value, filerIdentifer=paramFilerIdentifier)
                            elif factElementName == disclosureSystem.deiFilerNameElement:
                                deiItems[factElementName] = value
                                if paramFilerIdentifiers and paramFilerNames and entityIdentifierValue in paramFilerIdentifiers:
                                    prefix = paramFilerNames[paramFilerIdentifiers.index(entityIdentifierValue)]
                                    if not value.lower().startswith(prefix.lower()):
                                        self.modelXbrl.error(("EFM.6.05.24", "GFM.3.02.02"),
                                            _("dei:%(elementName)s %(prefix)s should be a case-insensitive prefix of: %(value)s"),
                                            modelObject=f, elementName=disclosureSystem.deiFilerIdentifierElement,
                                            prefix=prefix, value=value)
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
                    modelXbrl.error(("EFM.6.04.03", "GFM.2.01.01"),
                        _("Fact %(fact)s of context %(contextID)s has an XBRL error"),
                        modelObject=f, fact=f.qname, contextID=factContextID)
                else:
                    # note fact concpts used
                    conceptsUsed[concept] = False
                    
                    if concept.isNumeric:
                        if f.precision:
                            modelXbrl.error(("EFM.6.05.17", "GFM.1.02.16"),
                                _("Numeric fact %(fact)s of context %(contextID)s has a precision attribute '%(precision)s'"),
                                modelObject=f, fact=f.qname, contextID=factContextID, precision=f.precision)

                    #6.5.25 domain items as facts
                    if self.validateEFM and concept.type is not None and concept.type.isDomainItemType:
                        modelXbrl.error("EFM.6.05.25",
                            _("Domain item %(fact)s in context %(contextID)s may not appear as a fact"),
                            modelObject=f, fact=f.qname, contextID=factContextID)
    
                    
                if validateInlineXbrlGFM:
                    if f.localName == "nonFraction" or f.localName == "fraction":
                        syms = signOrCurrencyPattern.findall(f.text)
                        if syms:
                            modelXbrl.error(("EFM.N/A", "GFM.1.10.18"),
                                'ix-numeric Fact %(fact)s of context %(contextID)s has a sign or currency symbol "%(value)s" in "%(text)s"',
                                modelObject=f, fact=f.qname, contextID=factContextID, 
                                value="".join(s for t in syms for s in t), text=f.text)
                            
            self.modelXbrl.profileActivity("... filer fact checks", minTimeToShow=1.0)
    
            if len(contextIDs) > 0:
                modelXbrl.error(("EFM.6.05.08", "GFM.1.02.08"),
                                _("The instance document contained a context(s) %(contextIDs)s that was(are) not used in any fact."),
                                modelXbrl=modelXbrl, contextIDs=", ".join(contextIDs))
    
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
                                    modelXbrl.error(("EFM.6.05.09", "GFM.1.2.9"),
                                        _("Context {0} endDate and {1} startDate have a duration of one day; that is inconsistent with document type {2}."),
                                             c1.id, c2.id, documentType), 
                                        "err", )
                            if self.validateEFM and c1 != c2 and c2.isInstantPeriod:
                                duration = c2.endDatetime - start1
                                if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                    modelXbrl.error(
                                        _("Context {0} startDate and {1} end (instant) have a duration of one day; that is inconsistent with document type {2}."),
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
                                        modelXbrl.error(("EFM.6.05.09", "GFM.1.2.9"),
                                            _("Context %(contextID)s endDate and %(contextID2)s startDate have a duration of one day; that is inconsistent with document type %(documentType)s."),
                                            modelObject=cntx, contextID=cntx.id, contextID2=otherCntx.id, documentType=documentType)
                    if self.validateEFM and cntx.isInstantPeriod:
                        for otherStart, otherCntxs in durationCntxStartDatetimes.items():
                            duration = end - otherStart
                            if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                for otherCntx in otherCntxs:
                                    modelXbrl.error("EFM.6.05.10",
                                        _("Context %(contextID)s startDate and %(contextID2)s end (instant) have a duration of one day; that is inconsistent with document type %(documentType)s."),
                                        modelObject=cntx, contextID=cntx.id, contextID2=otherCntx.id, documentType=documentType)
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
                modelXbrl.error(("EFM.6.05.19", "GFM.1.02.18"),
                    _("Required context (no segment) not found for document type %(documentType)s."),
                    modelObject=documentTypeFact, documentType=documentType)
                
            #6.5.11 equivalent units
            uniqueUnitHashes = {}
            for unit in self.modelXbrl.units.values():
                h = unit.hash
                if h in uniqueUnitHashes:
                    if unit.isEqualTo(uniqueUnitHashes[h]):
                        modelXbrl.error(("EFM.6.05.11", "GFM.1.02.10"),
                            _("Units %(unitID)s and %(unitID2)s are equivalent."),
                            modelObject=unit, unitID=unit.id, unitID2=uniqueUnitHashes[h].id)
                else:
                    uniqueUnitHashes[h] = unit
                if self.validateEFM:  # 6.5.38
                    for measureElt in unit.iterdescendants(tag="{http://www.xbrl.org/2003/instance}unit"):
                        text = measureElt.text
                        if text and len(text) > 100 and len(text.encode("utf-8")) > 200:
                            modelXbrl.error("EFM.6.05.38",
                                _("Units %(unitID)s has a measure over 200 bytes long in utf-8, %{measure)s."),
                                modelObject=measureElt, unitID=unit.id, measure=text)
            del uniqueUnitHashes
            self.modelXbrl.profileActivity("... filer unit checks", minTimeToShow=1.0)
   
    
            # EFM.6.05.14, GFM.1.02.13 xml:lang tests, as of v-17, full default lang is compared
            #if self.validateEFM:
            #    factLangStartsWith = disclosureSystem.defaultXmlLang[:2]
            #else:
            #    factLangStartsWith = disclosureSystem.defaultXmlLang
            requiredFactLang = disclosureSystem.defaultXmlLang

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
                    if lang and lang != requiredFactLang: # not lang.startswith(factLangStartsWith):
                        keysNotDefaultLang[langTestKey] = f1
                        
                    if disclosureSystem.GFM and f1.isNumeric and \
                        f1.decimals and f1.decimals != "INF" and not f1.isNil:
                        try:
                            vf = float(f1.value)
                            vround = round(vf, int(f1.decimals))
                            if vf != vround: 
                                modelXbrl.error("GFM.1.02.26",
                                    _("Fact %(fact)s of context %(contextID)s decimals %(decimals)s value %(value)s has insignificant digits %(value2)s."),
                                    modelObject=f1, fact=f1.qname, contextID=f1.contextID, decimals=f1.decimals, value=vf, value2=vf - vround)
                        except (ValueError,TypeError):
                            modelXbrl.error("GFM.1.02.26",
                                _("Fact %(fact)s of context %(contextID)s decimals %(decimals)s value %(value)s causes Value Error exception."),
                                modelObject=f1, fact=f1.qname, contextID=f1.contextID, decimals=f1.decimals, value=f1.value)
                # 6.5.12 test
                h = f1.conceptContextUnitLangHash
                if h in factForConceptContextUnitLangHash:
                    f2 = factForConceptContextUnitLangHash[h]
                    if f1.qname == f2.qname and \
                       f1.contextID == f2.contextID and \
                       f1.unitID == f2.unitID and \
                       f1.xmlLang == f2.xmlLang:
                        modelXbrl.error(("EFM.6.05.12", "GFM.1.02.11"),
                            "Facts %(fact)s of context %(contextID)s and %(contextID2)s are equivalent.",
                            modelObject=f1, fact=f1.qname, contextID=f1.contextID, contextID2=f2.contextID)
                else:
                    factForConceptContextUnitLangHash[h] = f1
                iF1 += 1
            del factForConceptContextUnitLangHash
            self.modelXbrl.profileActivity("... filer fact checks", minTimeToShow=1.0)
    
            #6.5.14 facts without english text
            for keyNotDefaultLang, factNotDefaultLang in keysNotDefaultLang.items():
                anyDefaultLangFact = False
                for fact in factsForLang[keyNotDefaultLang]:
                    if fact.xmlLang == requiredFactLang: #.startswith(factLangStartsWith):
                        anyDefaultLangFact = True
                        break
                if not anyDefaultLangFact:
                    self.modelXbrl.error(("EFM.6.05.14", "GFM.1.02.13"),
                        _("Fact %(fact)s of context %(contextID)s has text of xml:lang '%(lang)s' without corresponding %(lang2)s text"),
                        modelObject=factNotDefaultLang, fact=factNotDefaultLang.qname, contextID=factNotDefaultLang.contextID, 
                        lang=factNotDefaultLang.xmlLang, lang2=requiredFactLang) # factLangStartsWith)
                    
            #label validations
            if not labelsRelationshipSet:
                self.modelXbrl.error(("EFM.6.10.01", "GFM.1.05.01"),
                    _("A label linkbase is required but was not found"), 
                    modelXbrl=modelXbrl)
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
                            modelXbrl.error(("EFM.6.10.02", "GFM.1.5.2"),
                                _("Concept %(concept)s has duplicated labels for role %(role)s lang %(lang)s."),
                                modelObject=concept, concept=concept.qname, 
                                role=dupDetectKey[0], lang=dupDetectKey[1])
                        else:
                            dupLabels.add(dupDetectKey)
                            
                    #6 10.1 en-US standard label
                    if not hasDefaultLangStandardLabel:
                        modelXbrl.error(("EFM.6.10.01", "GFM.1.05.01"),
                            _("Concept %(concept)s is missing an %(lang)s standard label."),
                            modelObject=concept, concept=concept.qname, 
                            lang=disclosureSystem.defaultLanguage)
                        
                    #6 10.3 default lang label for every role
                    dupLabels.add(("zzzz",disclosureSystem.defaultXmlLang)) #to allow following loop
                    priorRole = None
                    hasDefaultLang = True
                    for role, lang in sorted(dupLabels):
                        if role != priorRole:
                            if not hasDefaultLang:
                                modelXbrl.error(("EFM.6.10.03", "GFM.1.5.3"),
                                    _("Concept %(concept)s is missing an %(lang)s label for role %(role)s."),
                                    modelObject=concept, concept=concept.qname, 
                                    lang=disclosureSystem.defaultLanguage, role=priorRole)
                            hasDefaultLang = False
                            priorRole = role
                        if lang is not None and lang.startswith(disclosureSystem.defaultXmlLang):
                            hasDefaultLang = True
                        
    
            #6.5.15 facts with xml in text blocks
            if self.validateEFMorGFM:
                ValidateFilingText.validateTextBlockFacts(modelXbrl)
            
                if amendmentFlag is None:
                    modelXbrl.warning(("EFM.6.05.20", "GFM.3.02.01"),
                        _("%(elementName)s is not found in the default context"),
                        modelXbrl=modelXbrl, elementName=disclosureSystem.deiAmendmentFlagElement)
        
                if not documentPeriodEndDate:
                    modelXbrl.error(("EFM.6.05.20", "GFM.3.02.01"),
                        _("%(elementName)s is required and was not found in the default context"),
                        modelXbrl=modelXbrl, elementName=disclosureSystem.deiDocumentPeriodEndDateElement)
                else:
                    dateMatch = datePattern.match(documentPeriodEndDate)
                    if not dateMatch or dateMatch.lastindex != 3:
                        modelXbrl.error(("EFM.6.05.20", "GFM.3.02.01"),
                            _("%(elementName)s is in the default context is incorrect '%(date)s'"),
                            modelXbrl=modelXbrl, elementName=disclosureSystem.deiDocumentPeriodEndDateElement,
                            date=documentPeriodEndDate)
            self.modelXbrl.profileActivity("... filer label and text checks", minTimeToShow=1.0)
    
            if self.validateEFM:
                if amendmentFlag == "true" and not amendmentDescription:
                    modelXbrl.warning("EFM.6.05.20",
                        _("AmendmentFlag is true in context %(contextID)s so AmendmentDescription is also required"),
                        modelObject=amendmentFlagFact, contextID=amendmentFlagFact.contextID if amendmentFlagFact else "unknown")
        
                if amendmentDescription and ((not amendmentFlag) or amendmentFlag == "false"):
                    modelXbrl.warning("EFM.6.05.20",
                        _("AmendmentDescription can not be provided when AmendmentFlag is not true in context %(contextID)s"),
                        modelObject=amendmentDescriptionFact, contextID=amendmentDescriptionFact.contextID)
                    
                if not documentType:
                    modelXbrl.error("EFM.6.05.20",
                        _("DocumentType is required and was not found in the default context"), 
                        modelXbrl=modelXbrl)
                elif documentType not in {"10", "10-K", "10-KT", "10-Q", "10-QT", "20-F", "40-F", "6-K", "8-K", 
                                          "F-1", "F-10", "F-3", "F-4", "F-9", "S-1", "S-11", 
                                          "S-3", "S-4", "POS AM", "10-KT", "10-QT",
                                          "8-K/A", 
                                          "S-1/A", "S-11/A", "S-3/A", "S-4/A", 
                                          "10-KT/A", "10-QT/A",
                                          "485BPOS", "497 ", "NCSR", "N-CSR", "N-Q", 
                                          "N-Q/A",
                                          "Other"}:
                    modelXbrl.error("EFM.6.05.20",
                        _("DocumentType '%(documentType)s' of context %(contextID)s was not recognized"),
                        modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType)
                    
                # 6.5.21
                for doctypesRequired, deiItemsRequired in (
                      (("10-K", "10-KT",
                        "10-Q", "10-QT",
                        "20-F",
                        "40-F",
                        "6-K", "NCSR", "N-CSR", "N-CSRS", "N-Q",
                        "10", "S-1", "S-3", "S-4", "S-11", "POS AM",
                        "8-K", "F-1", "F-3", "F-10", "497", "485BPOS",
                        "Other"),
                        ("EntityRegistrantName", "EntityCentralIndexKey")),
                      (("10-K", "10-KT",
                        "20-F",
                        "40-F"),
                       ("EntityCurrentReportingStatus",)),
                     (("10-K", "10-KT",),
                      ("EntityVoluntaryFilers", "EntityPublicFloat")),
                      (("10-K", "10-KT",
                        "10-Q", "10-QT",
                        "20-F",
                        "40-F",
                        "6-K", "NCSR", "N-CSR", "N-CSRS", "N-Q"),
                        ("CurrentFiscalYearEndDate", "DocumentFiscalYearFocus", "DocumentFiscalPeriodFocus")),
                      (("10-K", "10-KT",
                        "10-Q", "10-QT",
                        "20-F",
                        "10", "S-1", "S-3", "S-4", "S-11", "POS AM"),
                        ("EntityFilerCategory",)),
                       (("10-K", "10-KT",
                         "20-F"),
                         ("EntityWellKnownSeasonedIssuer",))
                ):
                    if documentType in doctypesRequired:
                        for deiItem in deiItemsRequired:
                            if deiItem not in deiItems or deiItems[deiItem] == "":
                                modelXbrl.error("EFM.6.05.21",
                                    _("dei:%(elementName)s is required for DocumentType '%(documentType)s' of context %(contextID)s"),
                        modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType,
                        elementName=deiItem)
                                
                if documentType in ("10-K", "10-KT", "10-Q", "10-QT", "20-F", "40-F"):
                    defaultSharesOutstanding = deiItems.get("EntityCommonStockSharesOutstanding")
                    if commonSharesClassMembers:
                        if defaultSharesOutstanding:
                            modelXbrl.error("EFM.6.05.26",
                                _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' but not in the default context because there are multiple classes of common shares"),
                                modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType)
                        missingClasses = commonSharesClassMembers - commonSharesItemsByStockClass.keys()
                        if missingClasses:
                            modelXbrl.error("EFM.6.05.26",
                                _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' but missing in these stock classes: %(stockClasses)s"),
                                modelObject=documentTypeFact, documentType=documentType, stockClasses=", ".join([str(c) for c in missingClasses]))
                        for mem, facts in commonSharesItemsByStockClass.items():
                            if len(facts) != 1:
                                modelXbrl.error("EFM.6.05.26",
                                    _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' but only one per stock class %(stockClass)s"),
                                    modelObject=documentTypeFact, documentType=documentType, stockClasse=mem)
                            elif facts[0].context.instantDatetime != commonStockMeasurementDatetime:
                                modelXbrl.error("EFM.6.05.26",
                                    _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' in stock class %(stockClass)s with measurement date %(date)s"),
                                    modelObject=documentTypeFact, documentType=documentType, stockClasse=mem, date=commonStockMeasurementDatetime)
                    elif not defaultSharesOutstanding:
                        modelXbrl.error("EFM.6.05.26",
                            _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' in the default context because there are not multiple classes of common shares"),
                            modelObject=documentTypeFact, documentType=documentType)
                
            elif disclosureSystem.GFM:
                for deiItem in (
                        disclosureSystem.deiCurrentFiscalYearEndDateElement, 
                        disclosureSystem.deiDocumentFiscalYearFocusElement, 
                        disclosureSystem.deiFilerNameElement):
                    if deiItem not in deiItems or deiItems[deiItem] == "":
                        modelXbrl.error("GFM.3.02.01",
                            _("dei:%(elementName)s is required in the default context"),
                            modelXbrl=modelXbrl, elementName=deiItem)
            self.modelXbrl.profileActivity("... filer required facts checks", minTimeToShow=1.0)
    
            #6.5.27 footnote elements, etc
            footnoteLinkNbr = 0
            for footnoteLinkElt in xbrlInstDoc.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}footnoteLink"):
                if isinstance(footnoteLinkElt,ModelObject):
                    footnoteLinkNbr += 1
                    
                    linkrole = footnoteLinkElt.get("{http://www.w3.org/1999/xlink}role")
                    if linkrole != XbrlConst.defaultLinkRole:
                        modelXbrl.error(("EFM.6.05.28", "GFM.1.02.20"),
                            _("FootnoteLink %(footnoteLinkNumber)s has disallowed role %(linkrole)s"),
                            modelObject=footnoteLinkElt, footnoteLinkNumber=footnoteLinkNbr, linkrole=linkrole)
        
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
                                    modelXbrl.error(("EFM.6.05.27", "GFM.1.02.19"),
                                        _("FootnoteLink %(footnoteLinkNumber)s has disallowed child element %(elementName)s"),
                                        modelObject=child, footnoteLinkNumber=footnoteLinkNbr, elementName=child.prefixedName)
                            elif xlinkType == "locator":
                                locNbr += 1
                                locrole = child.get("{http://www.w3.org/1999/xlink}role")
                                if locrole is not None and (disclosureSystem.GFM or \
                                                            not disclosureSystem.uriAuthorityValid(locrole)): 
                                    modelXbrl.error(("EFM.6.05.29", "GFM.1.02.21"),
                                        _("FootnoteLink %(footnoteLinkNumber)s loc %(locNumber)s has disallowed role %(role)s"),
                                        modelObject=child, footnoteLinkNumber=footnoteLinkNbr, 
                                        locNumber=locNbr, role=locrole)
                                href = child.get("{http://www.w3.org/1999/xlink}href")
                                if not href.startswith("#"): 
                                    modelXbrl.error(("EFM.6.05.32", "GFM.1.02.23"),
                                        _("FootnoteLink %(footnoteLinkNumber)s loc %(locNumber)s has disallowed href %(locHref)s"),
                                        modelObject=child, footnoteLinkNumber=footnoteLinkNbr, locNumber=locNbr, locHref=href)
                                else:
                                    label = child.get("{http://www.w3.org/1999/xlink}label")
                            elif xlinkType == "arc":
                                arcNbr += 1
                                arcrole = child.get("{http://www.w3.org/1999/xlink}arcrole")
                                if (self.validateEFM and not disclosureSystem.uriAuthorityValid(arcrole)) or \
                                   (disclosureSystem.GFM  and arcrole != XbrlConst.factFootnote and arcrole != XbrlConst.factExplanatoryFact): 
                                    modelXbrl.error(("EFM.6.05.30", "GFM.1.02.22"),
                                        _("FootnoteLink %(footnoteLinkNumber)s arc %(arcNumber)s has disallowed arcrole %(arcrole)s"),
                                        modelObject=child, footnoteLinkNumber=footnoteLinkNbr, arcNumber=arcNbr, arcrole=arcrole)
                            elif xlinkType == "resource": # footnote
                                footnoterole = child.get("{http://www.w3.org/1999/xlink}role")
                                if footnoterole == "":
                                    modelXbrl.error(("EFM.6.05.28", "GFM.1.2.20"),
                                        _("Footnote %(xlinkLabel)s is missing a role"),
                                        modelObject=child, xlinkLabel=child.get("{http://www.w3.org/1999/xlink}label"))
                                elif (self.validateEFM and not disclosureSystem.uriAuthorityValid(footnoterole)) or \
                                     (disclosureSystem.GFM  and footnoterole != XbrlConst.footnote): 
                                    modelXbrl.error(("EFM.6.05.28", "GFM.1.2.20"),
                                        _("Footnote %(xlinkLabel)s has disallowed role %(role)s"),
                                        modelObject=child, xlinkLabel=child.get("{http://www.w3.org/1999/xlink}label"),
                                        role=footnoterole)
                                if self.validateEFM:
                                    ValidateFilingText.validateFootnote(modelXbrl, child)
                                # find modelResource for this element
                                foundFact = False
                                if XmlUtil.text(child) != "":
                                    for relationship in relationshipSet.toModelObject(child):
                                        if isinstance(relationship.fromModelObject, ModelFact):
                                            foundFact = True
                                            break
                                    if not foundFact:
                                        modelXbrl.error(("EFM.6.05.33", "GFM.1.02.24"),
                                            _("FootnoteLink %(footnoteLinkNumber)s footnote %(xlinkLabel)s has no linked fact"),
                                            modelObject=child, footnoteLinkNumber=footnoteLinkNbr, 
                                            xlinkLabel=child.get("{http://www.w3.org/1999/xlink}label"))
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
                        modelXbrl.error(("EFM.6.10.05", "GFM.1.05.05", "SBR.NL.2.1.0.08"),
                            _("Concept %(concept)s of a standard taxonomy cannot have a documentation label: %(text)s"),
                            modelObject=modelLabel, concept=concept.qname, text=text)
                elif text and lang and lang.startswith(disclosureSystem.defaultXmlLang):
                    if role == XbrlConst.standardLabel:
                        if text in defaultLangStandardLabels:
                            modelXbrl.error(("EFM.6.10.04", "GFM.1.05.04"),
                                _("Same labels for concepts %(concept)s and %(concept2)s for %(lang)s standard role: %(text)s."),
                                modelObject=modelLabel, concept=concept.qname, 
                                concept2=defaultLangStandardLabels[text].qname, 
                                lang=disclosureSystem.defaultLanguage, text=text[:80])
                        else:
                            defaultLangStandardLabels[text] = concept
                        conceptHasDefaultLangStandardLabel = True
                    if len(text) > 511:
                        modelXbrl.error(("EFM.6.10.06", "GFM.1.05.06"),
                            _("Label for concept %(concept)s role %(role)s length %(length)s must be shorter than 511 characters: %(text)s"),
                            modelObject=modelLabel, concept=concept.qname, role=role, length=len(text), text=text[:80])
                    match = modelXbrl.modelManager.disclosureSystem.labelCheckPattern.search(text)
                    if match:
                        modelXbrl.error(("EFM.6.10.06", "GFM.1.05.07", "SBR.NL.2.3.8.07"),
                            'Label for concept %(concept)s role %(role)s has disallowed characters: "%(text)s"',
                            modelObject=modelLabel, concept=concept.qname, role=role, text=match.group())
                if text is not None and len(text) > 0 and \
                   (modelXbrl.modelManager.disclosureSystem.labelTrimPattern.match(text[0]) or \
                    modelXbrl.modelManager.disclosureSystem.labelTrimPattern.match(text[-1])):
                    modelXbrl.error(("EFM.6.10.08", "GFM.1.05.08"),
                        _("Label for concept %(concept)s role %(role)s lang %(lang)s is not trimmed: %(text)s"),
                        modelObject=modelLabel, concept=concept.qname, role=role, lang=lang, text=text)
            for modelRefRel in referencesRelationshipSetWithProhibits.fromModelObject(concept):
                modelReference = modelRefRel.toModelObject
                text = modelReference.text
                #6.18.1 no reference to company extension concepts
                if concept.modelDocument.targetNamespace not in disclosureSystem.standardTaxonomiesDict:
                    modelXbrl.error(("EFM.6.18.01", "GFM.1.9.1"),
                        _("References for extension concept %(concept)s are not allowed: %(text)s"),
                        modelObject=modelReference, concept=concept.qname, text=text)
                elif (self.validateEFM or self.validateSBRNL) and \
                     modelRefRel.modelDocument.uri not in disclosureSystem.standardTaxonomiesDict: 
                    #6.18.2 no extension to add or remove references to standard concepts
                    modelXbrl.error(("EFM.6.18.02", "SBR.NL.2.1.0.08"),
                        _("References for standard taxonomy concept %(concept)s are not allowed in an extension linkbase: %(text)s"),
                        modelObject=modelReference, concept=concept.qname, text=text)
            if self.validateSBRNL:
                if not conceptHasDefaultLangStandardLabel and (concept.isItem or concept.isTuple):
                    modelXbrl.error("SBR.NL.2.2.2.26",
                        _("Concept %(concept)s missing standard label in local language."),
                        modelObject=concept, concept=concept.qname)
                if concept.modelDocument.targetNamespace not in disclosureSystem.standardTaxonomiesDict:
                    if (concept not in presentationRelationshipSet.toModelObject(concept) and
                        concept not in presentationRelationshipSet.fromModelObject(concept)):
                        modelXbrl.error("SBR.NL.2.2.0.21",
                            _("Concept %(concept)s not referred to by presentation relationship."),
                            modelObject=concept, concept=concept.qname)
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
                                self.modelXbrl.error(("EFM.6.09.03", "GFM.1.04.03", "SBR.NL.2.2.1.05"),
                                    _("Ineffective arc %(arc)s in \nlink role %(linkrole)s \narcrole %(arcrole)s \nfrom %(conceptFrom)s \nto %(conceptTo)s \n%(ineffectivity)s"),
                                    modelObject=modelRel, arc=modelRel.qname, linkrole=modelRel.linkrole, arcrole=modelRel.arcrole,
                                    conceptFrom=modelRel.fromModelObject.qname, conceptTo=modelRel.toModelObject.qname, 
                                    ineffectivity=modelRel.ineffectivity)
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
                                        self.modelXbrl.error(("EFM.6.12.05", "GFM.1.06.05"),
                                            _("Concept %(concept)s has duplicate preferred label %(preferredLabel)s in link role %(linkrole)s"),
                                            modelObject=rel, concept=relTo.qname, preferredLabel=preferredLabel, linkrole=rel.linkrole)
                                    else:
                                        preferredLabels.add(preferredLabel)
                                    if relFromUsed:
                                        # 6.14.5
                                        conceptsPresented.add(relFrom.objectIndex)
                                        conceptsPresented.add(relTo.objectIndex)
                                order = rel.order
                                if order in orderRels:
                                    self.modelXbrl.error(("EFM.6.12.02", "GFM.1.06.02", "SBR.NL.2.3.4.05"),
                                        _("Duplicate presentation relations from concept %(conceptFrom)s for order %(order)s in base set role %(linkrole)s to concept %(conceptTo)s and to concept %(conceptTo2)s"),
                                        modelObject=rel, conceptFrom=relFrom.qname, order=order, linkrole=rel.linkrole, 
                                        conceptTo=rel.toModelObject.qname, conceptTo2=orderRels[order].toModelObject.qname)
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
                                        self.modelXbrl.error(("EFM.6.14.03", "GFM.1.07.03"),
                                            "Calculation relationship period types mismatched in base set role %(linkrole)s from %(conceptFrom)s to %(conceptTo)s",
                                            modelObject=rel, linkrole=rel.linkrole, conceptFrom=relFrom.qname, conceptTo=relTo.qname)
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
                                        self.modelXbrl.error(("EFM.N/A", "GFM.1.07.06"),
                                            _("Duplicate calculations relations from concept %(conceptFrom)s for order %(order)s in base set role %(linkrole)s to concept %(conceptTo)s and to concept %(conceptTo2)s"),
                                            modelObject=rel, linkrole=rel.linkrole, conceptFrom=relFrom.qname, order=order,
                                            conceptTo=rel.toModelObject.qname, conceptTo2=orderRels[order].toModelObject.qname)
                                    else:
                                        orderRels[order] = rel
                                if self.directedCycle(relFrom,relFrom,fromRelationships):
                                    self.modelXbrl.error(("EFM.6.14.04", "GFM.1.07.04"),
                                        _("Calculation relationships have a directed cycle in base set role %(linkrole)s starting from %(concept)s"),
                                        modelObject=rels[0], linkrole=ELR, concept=relFrom.qname)
                        elif self.validateSBRNL:
                            # find a calc relationship to get the containing document name
                            for modelRel in self.modelXbrl.relationshipSet(arcrole).modelRelationships:
                                self.modelXbrl.error("SBR.NL.2.3.9.01",
                                    _("Calculation linkbase arcrole %(arcrole)s"),
                                    modelObject=modelRel, arcrole=modelRel.arcrole)
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
                                    self.modelXbrl.error(("EFM.6.16.03", "GFM.1.08.03"),
                                        _("Definition relationship from %(conceptFrom)s to %(conceptTo)s in role %(linkrole)s requires domain item target"),
                                        modelObject=rel, conceptFrom=relFrom.qname, conceptTo=relTo.qname, linkrole=rel.linkrole)

                    elif arcrole == XbrlConst.dimensionDefault and self.validateSBRNL:
                        for modelRel in self.modelXbrl.relationshipSet(arcrole).modelRelationships:
                            self.modelXbrl.error("SBR.NL.2.3.6.05",
                                _("Dimension-default in from %(conceptFrom)s to %(conceptTo)s in role %(linkrole)s is not allowed"),
                                modelObject=modelRel, conceptFrom=modelRel.fromModelObject.qname, conceptTo=modelRel.toModelObject.qname, 
                                linkrole=modelRel.linkrole)
                           
                    # definition tests (GFM only, for now)
                    if XbrlConst.isStandardOrXdtArcrole(arcrole) and disclosureSystem.GFM: 
                        fromRelationships = modelXbrl.relationshipSet(arcrole,ELR).fromModelObjects()
                        for relFrom, rels in fromRelationships.items():
                            orderRels = {}
                            for rel in rels:
                                relTo = rel.toModelObject
                                order = rel.order
                                if order in orderRels and disclosureSystem.GFM:
                                    self.modelXbrl.error("GFM.1.08.10",
                                        _("Duplicate definitions relations from concept %(conceptFrom)s for order %(order)s in base set role %(linkrole)s to concept %(conceptTo)s and to concept %(conceptTo2)s"),
                                        modelObject=rel, conceptFrom=relFrom.qname, order=order, linkrole=rel.linkrole, 
                                        conceptTo=rel.toModelObject.qname, conceptTo2=orderRels[order].toModelObject.qname)
                                else:
                                    orderRels[order] = rel
                                if (arcrole not in (XbrlConst.dimensionDomain, XbrlConst.domainMember) and
                                    rel.get("{http://xbrl.org/2005/xbrldt}usable") == "false"):
                                    self.modelXrl.error("GFM.1.08.11",
                                        _("Disallowed xbrldt:usable='false' attribute on %(arc)s relationship from concept %(conceptFrom)s in base set role %(linkrole)s to concept %(conceptTo)s"),
                                        modelObject=rel, arc=rel.qname, conceptFrom=relFrom.qname, linkrole=rel.linkrole, conceptTo=rel.toModelObject.qname)

        self.modelXbrl.profileActivity("... filer relationships checks", minTimeToShow=1.0)

                                
        # checks on dimensions
        ValidateFilingDimensions.checkDimensions(self, drsELRs)
        self.modelXbrl.profileActivity("... filer dimensions checks", minTimeToShow=1.0)
                                        
        for concept, hasPresentationRelationship in conceptsUsed.items():
            if not hasPresentationRelationship:
                self.modelXbrl.error(("EFM.6.12.03", "GFM.1.6.3"),
                    _("Concept %(concept)s does not participate in an effective presentation relationship"),
                    modelObject=concept, concept=concept.qname)
                
        for fromIndx, toIndxs in usedCalcsPresented.items():
            for toIndx in toIndxs:
                self.modelXbrl.error(("EFM.6.14.05", "GFM.1.7.5"),
                    _("Used calculation relationship from %(conceptFrom)s to %(conceptTo)s does not participate in an effective presentation relationship"),
                    modelObject=self.modelXbrl.modelObject(fromIndx), conceptFrom=self.modelXbrl.modelObject(fromIndx).qname, conceptTo=self.modelXbrl.modelObject(toIndx).qname)
                
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
                    self.modelXbrl.error(("EFM.6.12.04", "GFM.1.06.04"),
                        _("Concept %(concept)s missing %(lang)s preferred labels for role %(preferredLabel)s"),
                        modelObject=concept, concept=concept.qname, 
                        lang=disclosureSystem.defaultLanguage, preferredLabel=preferredLabel)
                
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

