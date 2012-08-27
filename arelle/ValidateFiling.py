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
from arelle.ModelDtsObject import ModelConcept
from arelle.PluginManager import pluginClassMethods

datePattern = None
linkroleDefinitionStatementSheet = None

class ValidateFiling(ValidateXbrl.ValidateXbrl):
    def __init__(self, modelXbrl):
        super(ValidateFiling, self).__init__(modelXbrl)
        
        global datePattern, GFMcontextDatePattern, signOrCurrencyPattern, usTypesPattern, usRolesPattern, usDeiPattern, instanceFileNamePattern, linkroleDefinitionStatementSheet
        
        if datePattern is None:
            datePattern = re.compile(r"([12][0-9]{3})-([01][0-9])-([0-3][0-9])")
            GFMcontextDatePattern = re.compile(r"^[12][0-9]{3}-[01][0-9]-[0-3][0-9]$")
            # note \u20zc = euro, \u00a3 = pound, \u00a5 = yen
            signOrCurrencyPattern = re.compile("^(-)[0-9]+|[^eE](-)[0-9]+|(\\()[0-9].*(\\))|([$\u20ac\u00a3\00a5])")
            usTypesPattern = re.compile(r"^http://(xbrl.us|fasb.org)/us-types/")
            usRolesPattern = re.compile(r"^http://(xbrl.us|fasb.org)/us-roles/")
            usDeiPattern = re.compile(r"http://(xbrl.us|xbrl.sec.gov)/dei/")
            instanceFileNamePattern = re.compile(r"^(\w+)-([12][0-9]{3}[01][0-9][0-3][0-9]).xml$")
            linkroleDefinitionStatementSheet = re.compile(r"[^-]+-\s+Statement\s+-\s+.*", # no restriction to type of statement
                                                          re.IGNORECASE)
        
    def validate(self, modelXbrl, parameters=None):
        if not hasattr(modelXbrl.modelDocument, "xmlDocument"): # not parsed
            return
        
        self._isStandardUri = {}
        modelXbrl.modelManager.disclosureSystem.loadStandardTaxonomiesDict()
        
        # find typedDomainRefs before validateXBRL pass
        if modelXbrl.modelManager.disclosureSystem.SBRNL:
            self.qnSbrLinkroleorder = ModelValue.qname("http://www.nltaxonomie.nl/5.0/basis/sbr/xbrl/xbrl-syntax-extension","linkroleOrder")

            self.typedDomainQnames = set()
            typedDomainElements = set()
            for modelConcept in modelXbrl.qnameConcepts.values():
                if modelConcept.isTypedDimension:
                    typedDomainElement = modelConcept.typedDomainElement
                    if typedDomainElement is not None:
                        self.typedDomainQnames.add(typedDomainElement.qname)
                        typedDomainElements.add(typedDomainElement)
        
        # note that some XFM tests are done by ValidateXbrl to prevent mulstiple node walks
        super(ValidateFiling,self).validate(modelXbrl, parameters)
        xbrlInstDoc = modelXbrl.modelDocument.xmlDocument.getroot()
        disclosureSystem = self.disclosureSystem
        
        modelXbrl.modelManager.showStatus(_("validating {0}").format(disclosureSystem.name))
        
        self.modelXbrl.profileActivity()
        conceptsUsed = {} # key=concept object value=True if has presentation label
        labelsRelationshipSet = modelXbrl.relationshipSet(XbrlConst.conceptLabel)
        if self.validateSBRNL:  # include generic labels in a (new) set
            genLabelsRelationshipSet = modelXbrl.relationshipSet(XbrlConst.elementLabel)
        presentationRelationshipSet = modelXbrl.relationshipSet(XbrlConst.parentChild)
        referencesRelationshipSetWithProhibits = modelXbrl.relationshipSet(XbrlConst.conceptReference, includeProhibits=True)
        self.modelXbrl.profileActivity("... cache lbl, pre, ref relationships", minTimeToShow=1.0)
        
        validateInlineXbrlGFM = (modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL and
                                 self.validateGFM)
        
        if self.validateEFM:
            for pluginXbrlMethod in pluginClassMethods("Validate.EFM.Start"):
                pluginXbrlMethod(self)
                
        # instance checks
        self.fileNameBasePart = None # prevent testing on fileNameParts if not instance or invalid
        self.fileNameDate = None
        self.entityRegistrantName = None
        self.requiredContext = None
        if modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or \
           modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL:
            #6.3.3 filename check
            m = instanceFileNamePattern.match(modelXbrl.modelDocument.basename)
            if m:  # has acceptable pattern
                self.fileNameBasePart = m.group(1)
                self.fileNameDatePart = m.group(2)
                if not self.fileNameBasePart:
                    modelXbrl.error(("EFM.6.03.03", "GFM.1.01.01"),
                        _('Invalid instance document base name part (ticker or mnemonic name) in "{base}-{yyyymmdd}.xml": %(filename)s'),
                        modelObject=modelXbrl.modelDocument, filename=modelXbrl.modelDocument.basename)
                else:
                    try:
                        self.fileNameDate = datetime.datetime.strptime(self.fileNameDatePart,"%Y%m%d").date()
                    except ValueError:
                        modelXbrl.error(("EFM.6.03.03", "GFM.1.01.01"),
                            _('Invalid instance document base name part (date) in "{base}-{yyyymmdd}.xml": %(filename)s'),
                            modelObject=modelXbrl.modelDocument, filename=modelXbrl.modelDocument.basename)
            else:
                modelXbrl.error(("EFM.6.03.03", "GFM.1.01.01"),
                    _('Invalid instance document name, must match "{base}-{yyyymmdd}.xml": %(filename)s'),
                    modelObject=modelXbrl.modelDocument, filename=modelXbrl.modelDocument.basename)
            
            #6.5.1 scheme, 6.5.2, 6.5.3 identifier
            entityIdentifierValue = None
            entityIdentifierValueElt = None
            if disclosureSystem.identifierValueName:   # omit if no checks
                for entityIdentifierElt in xbrlInstDoc.iterdescendants("{http://www.xbrl.org/2003/instance}identifier"):
                    if isinstance(entityIdentifierElt,ModelObject):
                        schemeAttr = entityIdentifierElt.get("scheme")
                        entityIdentifier = XmlUtil.text(entityIdentifierElt)
                        if not disclosureSystem.identifierSchemePattern.match(schemeAttr):
                            try:
                                contextId = entityIdentifierElt.getparent().getparent().id
                            except AttributeError:
                                contextId = "not available"
                            modelXbrl.error(("EFM.6.05.01", "GFM.1.02.01"),
                                _("Invalid entity identifier scheme %(scheme)s in context %(context)s for identifier %(identifier)s"),
                                modelObject=entityIdentifierElt, scheme=schemeAttr,
                                context=contextId, identifier=entityIdentifier)
                        if not disclosureSystem.identifierValuePattern.match(entityIdentifier):
                            modelXbrl.error(("EFM.6.05.02", "GFM.1.02.02"),
                                _("Invalid entity identifier %(entityIdentifierName)s: %(entityIdentifer)s"),
                                modelObject=entityIdentifierElt,  
                                entityIdentifierName=disclosureSystem.identifierValueName,
                                entityIdentifer=entityIdentifier)
                        if not entityIdentifierValue:
                            entityIdentifierValue = entityIdentifier
                            entityIdentifierValueElt = entityIdentifier
                        elif entityIdentifier != entityIdentifierValue:
                            modelXbrl.error(("EFM.6.05.03", "GFM.1.02.03"),
                                _("Multiple %(entityIdentifierName)ss: %(entityIdentifer)s, %(entityIdentifer2)s"),
                                modelObject=(entityIdentifierElt, entityIdentifierValueElt),  
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
                            modelObject=(context, uniqueContextHashes[h]), context=contextID, context2=uniqueContextHashes[h].id)
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
            hasDefinedStockAxis = False
            hasUndefinedDefaultStockMember = False
            commonSharesClassUndefinedMembers = None
            commonStockMeasurementDatetime = None
    
            # parameter-provided CIKs and registrant names
            paramFilerIdentifier = None
            paramFilerIdentifiers = None
            paramFilerNames = None
            submissionType = None
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
                p = self.parameters.get(ModelValue.qname("submissionType",noPrefixIsNoNamespace=True))
                if p and len(p) == 2:
                    submissionType = p[1]
                        
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
                                        _("dei:%(elementName)s %(value)s must match the context entity identifier %(entityIdentifer)s"),
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
                                if self.requiredContext is None and context.isStartEndPeriod:
                                    self.requiredContext = context
                    else:
                        # segment present
                        isEntityCommonStockSharesOutstanding = factElementName == "EntityCommonStockSharesOutstanding"
                        hasClassOfStockMember = False
                        
                        # note all concepts used in explicit dimensions
                        for dimValue in context.qnameDims.values():
                            if dimValue.isExplicit:
                                dimConcept = dimValue.dimension
                                memConcept = dimValue.member
                                for dConcept in (dimConcept, memConcept):
                                    if dConcept is not None:
                                        conceptsUsed[dConcept] = False
                                if (isEntityCommonStockSharesOutstanding and
                                    dimConcept.name == "StatementClassOfStockAxis"):
                                    commonSharesItemsByStockClass[memConcept.qname].append(f)
                                    if commonSharesClassMembers is None:
                                        commonSharesClassMembers, hasDefinedStockAxis = self.getDimMembers(dimConcept)
                                    if not hasDefinedStockAxis: # no def LB for stock axis, note observed members
                                        commonSharesClassMembers.add(memConcept.qname) 
                                    hasClassOfStockMember = True
                                    
                        if isEntityCommonStockSharesOutstanding and not hasClassOfStockMember:
                            hasUndefinedDefaultStockMember = True   # absent dimension, may be no def LB
                    if self.validateEFM:
                        for pluginXbrlMethod in pluginClassMethods("Validate.EFM.Fact"):
                            pluginXbrlMethod(self, f)
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
                            
            self.entityRegistrantName = deiItems.get("EntityRegistrantName") # used for name check in 6.8.6
                            
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
                                            modelObject=(cntx, otherCntx), contextID=cntx.id, contextID2=otherCntx.id, documentType=documentType)
                    if self.validateEFM and cntx.isInstantPeriod:
                        for otherStart, otherCntxs in durationCntxStartDatetimes.items():
                            duration = end - otherStart
                            if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                for otherCntx in otherCntxs:
                                    modelXbrl.error("EFM.6.05.10",
                                        _("Context %(contextID)s startDate and %(contextID2)s end (instant) have a duration of one day; that is inconsistent with document type %(documentType)s."),
                                        modelObject=(cntx, otherCntx), contextID=cntx.id, contextID2=otherCntx.id, documentType=documentType)
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
                            modelObject=(unit, uniqueUnitHashes[h]), unitID=unit.id, unitID2=uniqueUnitHashes[h].id)
                else:
                    uniqueUnitHashes[h] = unit
                if self.validateEFM:  # 6.5.38
                    for measureElt in unit.iterdescendants(tag="{http://www.xbrl.org/2003/instance}measure"):
                        if isinstance(measureElt.xValue, ModelValue.QName) and len(measureElt.xValue.localName) > 65:
                            l = len(measureElt.xValue.localName.encode("utf-8"))
                            if l > 200:
                                modelXbrl.error("EFM.6.05.36",
                                    _("Unit has a measure  with localName length (%(length)s) over 200 bytes long in utf-8, %(measure)s."),
                                    modelObject=measureElt, measure=measureElt.xValue.localName, length=l)
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
                            vround = round(vf, _INT(f1.decimals))
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
                            modelObject=(f1, f2), fact=f1.qname, contextID=f1.contextID, contextID2=f2.contextID)
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
                    self.checkConceptLabels(modelXbrl, labelsRelationshipSet, disclosureSystem, concept)
                        
    
            #6.5.15 facts with xml in text blocks
            if self.validateEFMorGFM:
                ValidateFilingText.validateTextBlockFacts(modelXbrl)
            
                if amendmentFlag is None:
                    modelXbrl.error(("EFM.6.05.20", "GFM.3.02.01"),
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
                    modelXbrl.error("EFM.6.05.20",
                        _("AmendmentFlag is true in context %(contextID)s so AmendmentDescription is also required"),
                        modelObject=amendmentFlagFact, contextID=amendmentFlagFact.contextID if amendmentFlagFact else "unknown")
        
                if amendmentDescription and ((not amendmentFlag) or amendmentFlag == "false"):
                    modelXbrl.error("EFM.6.05.20.extraneous",
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
                elif submissionType:
                    expectedDocumentType = {
                            "10": "10", 
                            "10/A": "10", "10-K": "10-K", "10-K/A": "10-K", "10-Q": "10-Q", "10-Q/A": "10-Q", 
                            "20-F": "20-F", "20-F/A": "20-F", "40-F": "40-F", "40-F/A": "40-F", "485BPOS": "485BPOS", 
                            "6-K": "6-K", "6-K/A": "6-K", "8-K": "8-K", "F-1": "F-1", "F-1/A": "F-1", 
                            "F-10": "F-10", "F-10/A": "F-10", "F-3": "F-3", "F-3/A": "F-3", 
                            "F-4": "F-4", "F-4/A": "F-4", "F-9": "F-9", "F-9/A": "F-9", "N-1A": "N-1A", 
                            "NCSR": "NCSR", "NCSR/A": "NCSR", "NCSRS": "NCSR", "NCSRS/A": "NCSR", 
                            "N-Q": "N-Q", "N-Q/A": "N-Q", "S-1": "S-1", "S-1/A": "S-1", "S-11": "S-11", "S-11/A": "S-11", 
                            "S-3": "S-3", "S-3/A": "S-3", "S-4": "S-4", "S-4/A": "S-4", "N-CSR": "NCSR", "N-CSR/A": "NCSR", "N-CSRS": "NCSR", "NCSRS/A": "NCSR", 
                            "497": "Other", 
                            }.get(submissionType)
                    if expectedDocumentType and expectedDocumentType != documentType:
                        modelXbrl.error("EFM.6.05.20",
                            _("DocumentType '%(documentType)s' of context %(contextID)s inapplicable to submission form %(submissionType)s"),
                            modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType, submissionType=submissionType)
                    
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
                        elif len(commonSharesClassMembers) == 1 and not hasDefinedStockAxis:
                            modelXbrl.error("EFM.6.05.26",
                                _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' but but a default-context because only one class of stock"),
                                modelObject=documentTypeFact, documentType=documentType)
                        missingClasses = commonSharesClassMembers - _DICT_SET(commonSharesItemsByStockClass.keys())
                        if missingClasses:
                            modelXbrl.error("EFM.6.05.26",
                                _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' but missing in these stock classes: %(stockClasses)s"),
                                modelObject=documentTypeFact, documentType=documentType, stockClasses=", ".join([str(c) for c in missingClasses]))
                        for mem, facts in commonSharesItemsByStockClass.items():
                            if len(facts) != 1:
                                modelXbrl.error("EFM.6.05.26",
                                    _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' but only one per stock class %(stockClass)s"),
                                    modelObject=documentTypeFact, documentType=documentType, stockClasse=mem)
                            ''' removed per ARELLE-124 (should check measurement date vs report date)
                            elif facts[0].context.instantDatetime != commonStockMeasurementDatetime:
                                modelXbrl.error("EFM.6.05.26",
                                    _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' in stock class %(stockClass)s with measurement date %(date)s"),
                                    modelObject=documentTypeFact, documentType=documentType, stockClass=mem, date=commonStockMeasurementDatetime)
                            '''
                    elif hasUndefinedDefaultStockMember and not defaultSharesOutstanding:
                            modelXbrl.error("EFM.6.05.26",
                                _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' but missing for a non-default-context fact"),
                                modelObject=documentTypeFact, documentType=documentType)
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
                    # modelLink = modelXbrl.baseSetModelLink(footnoteLinkElt)
                    relationshipSet = modelXbrl.relationshipSet("XBRL-footnotes", linkrole)
                    #if (modelLink is None) or (not relationshipSet):
                    #    continue    # had no child elements to parse
                    locNbr = 0
                    arcNbr = 0
                    for child in footnoteLinkElt:
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
                                    if relationshipSet:
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

        # entry point schema checks
        elif modelXbrl.modelDocument.type == ModelDocument.Type.SCHEMA:
            if self.validateSBRNL:
                # entry must have a P-link
                if not any(hrefElt.localName == "linkbaseRef" and hrefElt.get("{http://www.w3.org/1999/xlink}role") == "http://www.xbrl.org/2003/role/presentationLinkbaseRef"
                           for hrefElt, hrefDoc, hrefId in modelXbrl.modelDocument.hrefObjects):
                    modelXbrl.error("SBR.NL.2.2.10.01",
                        'Entrypoint schema must have a presentation linkbase', modelObject=modelXbrl.modelDocument)
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
                            concept2, modelLabel2 = defaultLangStandardLabels[text]
                            modelXbrl.error(("EFM.6.10.04", "GFM.1.05.04"),
                                _("Same labels for concepts %(concept)s and %(concept2)s for %(lang)s standard role: %(text)s."),
                                modelObject=(concept, modelLabel, concept2, modelLabel2), 
                                concept=concept.qname, 
                                concept2=concept2.qname, 
                                lang=disclosureSystem.defaultLanguage, text=text[:80])
                        else:
                            defaultLangStandardLabels[text] = (concept, modelLabel)
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
                elif (self.validateEFM or self.validateSBRNL) and not self.isStandardUri(modelRefRel.modelDocument.uri): 
                    #6.18.2 no extension to add or remove references to standard concepts
                    modelXbrl.error(("EFM.6.18.02", "SBR.NL.2.1.0.08"),
                        _("References for standard taxonomy concept %(concept)s are not allowed in an extension linkbase: %(text)s"),
                        modelObject=modelReference, concept=concept.qname, text=text)
            if self.validateSBRNL and (concept.isItem or concept.isTuple):
                if concept.modelDocument.targetNamespace not in disclosureSystem.standardTaxonomiesDict:
                    if not conceptHasDefaultLangStandardLabel:
                        modelXbrl.error("SBR.NL.2.2.2.26",
                            _("Concept %(concept)s missing standard label in local language."),
                            modelObject=concept, concept=concept.qname)
                    subsGroup = concept.get("substitutionGroup")
                    if ((not concept.isAbstract or subsGroup == "sbr:presentationItem") and
                        not (presentationRelationshipSet.toModelObject(concept) or
                             presentationRelationshipSet.fromModelObject(concept))):
                        modelXbrl.error("SBR.NL.2.2.2.04",
                            _("Concept %(concept)s not referred to by presentation relationship."),
                            modelObject=concept, concept=concept.qname)
                    elif ((concept.isDimensionItem or
                          (subsGroup and (subsGroup.endswith(":domainItem") or subsGroup.endswith(":domainMemberItem")))) and
                        not (presentationRelationshipSet.toModelObject(concept) or
                             presentationRelationshipSet.fromModelObject(concept))):
                        modelXbrl.error("SBR.NL.2.2.10.03",
                            _("DTS concept %(concept)s not referred to by presentation relationship."),
                            modelObject=concept, concept=concept.qname)
                    if (concept.substitutionGroupQname and 
                        concept.substitutionGroupQname.namespaceURI not in disclosureSystem.baseTaxonomyNamespaces):
                        modelXbrl.error("SBR.NL.2.2.2.05",
                            _("Concept %(concept)s has a substitutionGroup of a non-standard concept."),
                            modelObject=concept, concept=concept.qname)
                            
                    if concept.isTuple: # verify same presentation linkbase nesting
                        for missingQname in set(concept.type.elements) ^ pLinkedNonAbstractDescendantQnames(modelXbrl, concept):
                            modelXbrl.error("SBR.NL.2.3.4.01",
                                _("Tuple %(concept)s has mismatch between content and presentation children: %(missingQname)s."),
                                modelObject=concept, concept=concept.qname, missingQname=missingQname)
                self.checkConceptLabels(modelXbrl, labelsRelationshipSet, disclosureSystem, concept)
                self.checkConceptLabels(modelXbrl, genLabelsRelationshipSet, disclosureSystem, concept)

        if self.validateSBRNL:
            for qname, modelType in modelXbrl.qnameTypes.items():
                if qname.namespaceURI not in disclosureSystem.baseTaxonomyNamespaces:
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
                        
        self.modelXbrl.profileActivity("... filer concepts checks", minTimeToShow=1.0)

        del defaultLangStandardLabels #dereference
        
        ''' removed RH 2011-12-23, corresponding use of nameWordsTable in ValidateFilingDTS
        if self.validateSBRNL: # build camelCasedNamesTable
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
        
        # checks on all documents: instance, schema, instance
        ValidateFilingDTS.checkDTS(self, modelXbrl.modelDocument, [])
        ''' removed RH 2011-12-23, corresponding use of nameWordsTable in ValidateFilingDTS
        if self.validateSBRNL:
            del self.nameWordsTable
        '''
        self.modelXbrl.profileActivity("... filer DTS checks", minTimeToShow=1.0)

        # checks for namespace clashes
        if self.validateEFM:
            # check number of us-roles taxonomies referenced
            for nsPattern in (usTypesPattern, usRolesPattern, usDeiPattern):
                usTypesURIs = set(ns for ns in modelXbrl.namespaceDocs.keys() if nsPattern.match(ns))
                if len(usTypesURIs) > 1:
                    modelXbrl.error("EFM.6.22.03",
                        _("References for conflicting standard taxonomies %(namespaceConflicts)s are not allowed in same DTS"),
                        modelObject=modelXbrl, namespaceConflicts=usTypesURIs)
            
        conceptsUsedWithPreferredLabels = defaultdict(list)
        usedCalcsPresented = defaultdict(set) # pairs of concepts objectIds used in calc
        usedCalcFromTosELR = {}
        localPreferredLabels = defaultdict(set)
        drsELRs = set()
        
        # do calculation, then presentation, then other arcroles
        for arcroleFilter in (XbrlConst.summationItem, XbrlConst.parentChild, "*"):
            for baseSetKey, baseSetModelLinks  in modelXbrl.baseSets.items():
                arcrole, ELR, linkqname, arcqname = baseSetKey
                if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-"):
                    # assure summationItem, then parentChild, then others
                    if not (arcroleFilter == arcrole or
                            arcroleFilter == "*" and arcrole not in (XbrlConst.summationItem, XbrlConst.parentChild)):
                        continue
                    if self.validateEFMorGFM or (self.validateSBRNL and arcrole == XbrlConst.parentChild):
                        ineffectiveArcs = ModelRelationshipSet.ineffectiveArcs(baseSetModelLinks, arcrole)
                        #validate ineffective arcs
                        for modelRel in ineffectiveArcs:
                            if modelRel.fromModelObject is not None and modelRel.toModelObject is not None:
                                self.modelXbrl.error(("EFM.6.09.03", "GFM.1.04.03", "SBR.NL.2.3.4.06"),
                                    _("Ineffective arc %(arc)s in \nlink role %(linkrole)s \narcrole %(arcrole)s \nfrom %(conceptFrom)s \nto %(conceptTo)s \n%(ineffectivity)s"),
                                    modelObject=modelRel, arc=modelRel.qname, linkrole=modelRel.linkrole, arcrole=modelRel.arcrole,
                                    conceptFrom=modelRel.fromModelObject.qname, conceptTo=modelRel.toModelObject.qname, 
                                    ineffectivity=modelRel.ineffectivity)
                    if arcrole == XbrlConst.parentChild:
                        isStatementSheet = any(linkroleDefinitionStatementSheet.match(roleType.definition)
                                               for roleType in self.modelXbrl.roleTypes.get(ELR,()))
                        conceptsPresented = set()
                        # 6.12.2 check for distinct order attributes
                        parentChildRels = modelXbrl.relationshipSet(arcrole, ELR)
                        for relFrom, siblingRels in parentChildRels.fromModelObjects().items():
                            targetConceptPreferredLabels = defaultdict(dict)
                            orderRels = {}
                            firstRel = True
                            relFromUsed = True
                            for rel in siblingRels:
                                if firstRel:
                                    firstRel = False
                                    if relFrom in conceptsUsed:
                                        conceptsUsed[relFrom] = True # 6.12.3, has a pres relationship
                                        relFromUsed = True
                                relTo = rel.toModelObject
                                preferredLabel = rel.preferredLabel
                                if relTo in conceptsUsed:
                                    conceptsUsed[relTo] = True # 6.12.3, has a pres relationship
                                    if preferredLabel and preferredLabel != "":
                                        conceptsUsedWithPreferredLabels[relTo].append(preferredLabel)
                                        if self.validateSBRNL and preferredLabel in ("periodStart","periodEnd"):
                                            self.modelXbrl.error("SBR.NL.2.3.4.03",
                                                _("Preferred label on presentation relationships not allowed"), modelObject=modelRel)
                                    # 6.12.5 distinct preferred labels in base set
                                    preferredLabels = targetConceptPreferredLabels[relTo]
                                    if (preferredLabel in preferredLabels or
                                        (self.validateSBRNL and not relFrom.isTuple and
                                         (not preferredLabel or None in preferredLabels))):
                                        if preferredLabel in preferredLabels:
                                            rel2, relTo2 = preferredLabels[preferredLabel]
                                        else:
                                            rel2 = relTo2 = None
                                        self.modelXbrl.error(("EFM.6.12.05", "GFM.1.06.05", "SBR.NL.2.3.4.06"),
                                            _("Concept %(concept)s has duplicate preferred label %(preferredLabel)s in link role %(linkrole)s"),
                                            modelObject=(rel, relTo, rel2, relTo2), 
                                            concept=relTo.qname, preferredLabel=preferredLabel, linkrole=rel.linkrole)
                                    else:
                                        preferredLabels[preferredLabel] = (rel, relTo)
                                    if relFromUsed:
                                        # 6.14.5
                                        conceptsPresented.add(relFrom.objectIndex)
                                        conceptsPresented.add(relTo.objectIndex)
                                order = rel.order
                                if order in orderRels:
                                    self.modelXbrl.error(("EFM.6.12.02", "GFM.1.06.02", "SBR.NL.2.3.4.05"),
                                        _("Duplicate presentation relations from concept %(conceptFrom)s for order %(order)s in base set role %(linkrole)s to concept %(conceptTo)s and to concept %(conceptTo2)s"),
                                        modelObject=(rel, orderRels[order]), conceptFrom=relFrom.qname, order=order, linkrole=rel.linkrole, 
                                        conceptTo=rel.toModelObject.qname, conceptTo2=orderRels[order].toModelObject.qname)
                                else:
                                    orderRels[order] = rel
                                if self.validateSBRNL and not relFrom.isTuple:
                                    if relTo in localPreferredLabels:
                                        if {None, preferredLabel} & localPreferredLabels[relTo]:
                                            self.modelXbrl.error("SBR.NL.2.3.4.06",
                                                _("Non-distinguished preferredLabel presentation relations from concept %(conceptFrom)s in base set role %(linkrole)s"),
                                                modelObject=rel, conceptFrom=relFrom.qname, linkrole=rel.linkrole, conceptTo=relTo.qname)
                                    localPreferredLabels[relTo].add(preferredLabel)
                            targetConceptPreferredLabels.clear()
                            orderRels.clear()
                        localPreferredLabels.clear() # clear for next relationship
                        for conceptPresented in conceptsPresented:
                            if conceptPresented in usedCalcsPresented:
                                usedCalcPairingsOfConcept = usedCalcsPresented[conceptPresented]
                                if len(usedCalcPairingsOfConcept & conceptsPresented) > 0:
                                    usedCalcPairingsOfConcept -= conceptsPresented
                        # 6.15.02, 6.15.03 semantics checks for totals and calc arcs (by tree walk)
                        for rootConcept in parentChildRels.rootConcepts:
                            self.checkCalcsTreeWalk(parentChildRels, rootConcept, isStatementSheet, False, conceptsUsed, set())
                    elif arcrole == XbrlConst.summationItem:
                        if self.validateEFMorGFM:
                            # 6.14.3 check for relation concept periods
                            fromRelationships = modelXbrl.relationshipSet(arcrole,ELR).fromModelObjects()
                            allElrRelSet = modelXbrl.relationshipSet(arcrole)
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
                                            modelObject=(rel, orderRels[order]), linkrole=rel.linkrole, conceptFrom=relFrom.qname, order=order,
                                            conceptTo=rel.toModelObject.qname, conceptTo2=orderRels[order].toModelObject.qname)
                                    else:
                                        orderRels[order] = rel
                                if self.directedCycle(relFrom,relFrom,fromRelationships):
                                    self.modelXbrl.error(("EFM.6.14.04", "GFM.1.07.04"),
                                        _("Calculation relationships have a directed cycle in base set role %(linkrole)s starting from %(concept)s"),
                                        modelObject=[relFrom] + rels, linkrole=ELR, concept=relFrom.qname)
                                orderRels.clear()
                            # if relFrom used by fact and multiple calc networks from relFrom, test 6.15.04
                            if rels and relFrom in conceptsUsed:
                                relFromAndTos = (relFrom.objectIndex,) + tuple(sorted((rel.toModelObject.objectIndex 
                                                                                           for rel in rels)))
                                if relFromAndTos in usedCalcFromTosELR:
                                    otherRels = usedCalcFromTosELR[relFromAndTos]
                                    otherELR = otherRels[0].linkrole
                                    self.modelXbrl.error(("EFM.6.15.04", "GFM.2.06.04"),
                                        _("Calculation relationships have a same set of targets in %(linkrole)s and %(linkrole2)s starting from %(concept)s"),
                                        modelObject=[relFrom] + rels + otherRels, linkrole=ELR, linkrole2=otherELR, concept=relFrom.qname)
                                else:
                                    usedCalcFromTosELR[relFromAndTos] = rels
                                    
                        elif self.validateSBRNL:
                            # find a calc relationship to get the containing document name
                            for modelRel in self.modelXbrl.relationshipSet(arcrole, ELR).modelRelationships:
                                self.modelXbrl.error("SBR.NL.2.3.9.01",
                                    _("Calculation linkbase linkrole %(linkrole)s"),
                                    modelObject=modelRel, linkrole=ELR)
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
    
                                if not (relTo.type is not None and relTo.type.isDomainItemType) and not self.isStandardUri(rel.modelDocument.uri):
                                    self.modelXbrl.error(("EFM.6.16.03", "GFM.1.08.03"),
                                        _("Definition relationship from %(conceptFrom)s to %(conceptTo)s in role %(linkrole)s requires domain item target"),
                                        modelObject=(rel, relFrom, relTo), conceptFrom=relFrom.qname, conceptTo=relTo.qname, linkrole=rel.linkrole)

                    elif self.validateSBRNL:
                        if arcrole == XbrlConst.dimensionDefault:
                            for modelRel in self.modelXbrl.relationshipSet(arcrole).modelRelationships:
                                self.modelXbrl.error("SBR.NL.2.3.6.05",
                                    _("Dimension-default in from %(conceptFrom)s to %(conceptTo)s in role %(linkrole)s is not allowed"),
                                    modelObject=modelRel, conceptFrom=modelRel.fromModelObject.qname, conceptTo=modelRel.toModelObject.qname, 
                                    linkrole=modelRel.linkrole)
                        if not (XbrlConst.isStandardArcrole(arcrole) or XbrlConst.isDefinitionOrXdtArcrole(arcrole)):
                            for modelRel in self.modelXbrl.relationshipSet(arcrole).modelRelationships:
                                relTo = modelRel.toModelObject
                                relFrom = modelRel.fromModelObject
                                if not ((isinstance(relFrom,ModelConcept) and isinstance(relTo,ModelConcept)) or
                                        (relFrom.modelDocument.inDTS and
                                         (relTo.qname == XbrlConst.qnGenLabel and modelRel.arcrole == XbrlConst.elementLabel) or
                                         (relTo.qname == XbrlConst.qnGenReference and modelRel.arcrole == XbrlConst.elementReference) or
                                         (relTo.qname == self.qnSbrLinkroleorder))):
                                    self.modelXbrl.error("SBR.NL.2.3.2.07",
                                        _("The source and target of an arc must be in the DTS from %(elementFrom)s to %(elementTo)s, in linkrole %(linkrole)s, arcrole %(arcrole)s"),
                                        modelObject=modelRel, elementFrom=relFrom.qname, elementTo=relTo.qname, 
                                        linkrole=modelRel.linkrole, arcrole=arcrole)
                            
                           
                    # definition tests (GFM only, for now)
                    if XbrlConst.isDefinitionOrXdtArcrole(arcrole) and disclosureSystem.GFM: 
                        fromRelationships = modelXbrl.relationshipSet(arcrole,ELR).fromModelObjects()
                        for relFrom, rels in fromRelationships.items():
                            orderRels = {}
                            for rel in rels:
                                relTo = rel.toModelObject
                                order = rel.order
                                if order in orderRels and disclosureSystem.GFM:
                                    self.modelXbrl.error("GFM.1.08.10",
                                        _("Duplicate definitions relations from concept %(conceptFrom)s for order %(order)s in base set role %(linkrole)s to concept %(conceptTo)s and to concept %(conceptTo2)s"),
                                        modelObject=(rel, relFrom, relTo), conceptFrom=relFrom.qname, order=order, linkrole=rel.linkrole, 
                                        conceptTo=rel.toModelObject.qname, conceptTo2=orderRels[order].toModelObject.qname)
                                else:
                                    orderRels[order] = rel
                                if (arcrole not in (XbrlConst.dimensionDomain, XbrlConst.domainMember) and
                                    rel.get("{http://xbrl.org/2005/xbrldt}usable") == "false"):
                                    self.modelXrl.error("GFM.1.08.11",
                                        _("Disallowed xbrldt:usable='false' attribute on %(arc)s relationship from concept %(conceptFrom)s in base set role %(linkrole)s to concept %(conceptTo)s"),
                                        modelObject=(rel, relFrom, relTo), arc=rel.qname, conceptFrom=relFrom.qname, linkrole=rel.linkrole, conceptTo=rel.toModelObject.qname)

        del localPreferredLabels # dereference
        del usedCalcFromTosELR
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
                fromModelObject = self.modelXbrl.modelObject(fromIndx)
                toModelObject = self.modelXbrl.modelObject(toIndx)
                self.modelXbrl.error(("EFM.6.14.05", "GFM.1.7.5"),
                    _("Used calculation relationship from %(conceptFrom)s to %(conceptTo)s does not participate in an effective presentation relationship"),
                    modelObject=[fromModelObject, toModelObject] +
                                 modelXbrl.relationshipSet(XbrlConst.summationItem)
                                 .fromToModelObjects(fromModelObject, toModelObject),
                    conceptFrom=self.modelXbrl.modelObject(fromIndx).qname, conceptTo=self.modelXbrl.modelObject(toIndx).qname)
                
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
        self.modelXbrl.profileActivity("... filer preferred label checks", minTimeToShow=1.0)
        
        if self.validateSBRNL:
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
                                        order = orderNumRel.toModelObject.xValue
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
                    if not arcroleURI.startswith("http://xbrl.org/") and (
                       not modelRoleType.genLabel(lang="nl") or not modelRoleType.genLabel(lang="en")):
                        modelXbrl.error("SBR.NL.2.2.4.02",
                            _("ArcroleType missing nl or en generic label: %(arcrole)s"),
                            modelObject=modelRoleType, arcrole=arcroleURI)

            for domainElt in typedDomainElements:
                if domainElt.modelDocument.targetNamespace not in disclosureSystem.baseTaxonomyNamespaces:
                    if not domainElt.genLabel(fallbackToQname=False,lang="nl"):
                        modelXbrl.error("SBR.NL.2.2.8.01",
                            _("Typed dimension domain element %(concept)s must have a generic label"),
                            modelObject=domainElt, concept=domainElt.qname)
                    if domainElt.type is not None and domainElt.type.localName == "complexType":
                        modelXbrl.error("SBR.NL.2.2.8.02",
                            _("Typed dimension domain element %(concept)s has disallowed complex content"),
                            modelObject=domainElt, concept=domainElt.qname)
                    
            self.modelXbrl.profileActivity("... SBR role types and type facits checks", minTimeToShow=1.0)

        if self.validateEFM:
            for pluginXbrlMethod in pluginClassMethods("Validate.EFM.Finally"):
                pluginXbrlMethod(self, conceptsUsed)
        self.modelXbrl.profileActivity("... plug in '.Finally' checks", minTimeToShow=1.0)
        self.modelXbrl.profileStat(_("validate") + modelXbrl.modelManager.disclosureSystem.validationType)
        
        modelXbrl.modelManager.showStatus(_("ready"), 2000)
                    
    def isStandardUri(self, uri):
        try:
            return self._isStandardUri[uri]
        except KeyError:
            isStd = (uri in self.disclosureSystem.standardTaxonomiesDict or
                     (not uri.startswith("http://") and 
                      # try 2011-12-23 RH: if works, remove the localHrefs
                      # any(u.endswith(e) for u in (uri.replace("\\","/"),) for e in disclosureSystem.standardLocalHrefs)
                      "/basis/sbr/" in uri.replace("\\","/")
                      ))
            self._isStandardUri[uri] = isStd
            return isStd

    def directedCycle(self, relFrom, origin, fromRelationships):
        if relFrom in fromRelationships:
            for rel in fromRelationships[relFrom]:
                relTo = rel.toModelObject
                if relTo == origin or self.directedCycle(relTo, origin, fromRelationships):
                    return True
        return False
    
    def getDimMembers(self, dim, default=None, rels=None, members=None, visited=None):
        hasDefinedRelationship = False
        if rels is None: 
            visited = set()
            members = set()
            for rel in self.modelXbrl.relationshipSet(XbrlConst.dimensionDefault).fromModelObject(dim):
                default = rel.toModelObject
            rels = self.modelXbrl.relationshipSet(XbrlConst.dimensionDomain).fromModelObject(dim)
        for rel in rels:
            hasDefinedRelationship = True
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
        return (members,hasDefinedRelationship)   

    def checkConceptLabels(self, modelXbrl, labelsRelationshipSet, disclosureSystem, concept):
        hasDefaultLangStandardLabel = False
        dupLabels = {}
        for modelLabelRel in labelsRelationshipSet.fromModelObject(concept):
            modelLabel = modelLabelRel.toModelObject
            if modelLabel is not None and modelLabel.xmlLang:
                if modelLabel.xmlLang.startswith(disclosureSystem.defaultXmlLang) and \
                   modelLabel.role == XbrlConst.standardLabel:
                    hasDefaultLangStandardLabel = True
                dupDetectKey = ( (modelLabel.role or ''), modelLabel.xmlLang)
                if dupDetectKey in dupLabels:
                    modelXbrl.error(("EFM.6.10.02", "GFM.1.5.2", "SBR.NL.2.2.1.05"),
                        _("Concept %(concept)s has duplicated labels for role %(role)s lang %(lang)s."),
                        modelObject=(concept, modelLabel, dupLabels[dupDetectKey]), 
                        concept=concept.qname, role=dupDetectKey[0], lang=dupDetectKey[1])
                else:
                    dupLabels[dupDetectKey] = modelLabel
                if modelLabel.role in (XbrlConst.periodStartLabel, XbrlConst.periodEndLabel):
                    modelXbrl.error("SBR.NL.2.3.8.03",
                        _("Concept %(concept)s has label for semantical role %(role)s."),
                        modelObject=modelLabel, concept=concept.qname, role=modelLabel.role)
        if self.validateSBRNL: # check for missing nl labels
            for role, lang in dupLabels.keys():
                if role and lang != disclosureSystem.defaultXmlLang and (role,disclosureSystem.defaultXmlLang) not in dupLabels:
                    modelXbrl.error("SBR.NL.2.3.8.05",
                        _("Concept %(concept)s has en but no nl label in role %(role)s."),
                        modelObject=(concept,dupLabels[(role,lang)]), concept=concept.qname, role=role)
                
        #6 10.1 en-US standard label
        if not hasDefaultLangStandardLabel:
            modelXbrl.error(("EFM.6.10.01", "GFM.1.05.01"),
                _("Concept %(concept)s is missing an %(lang)s standard label."),
                modelObject=concept, concept=concept.qname, 
                lang=disclosureSystem.defaultLanguage)
            
        #6 10.3 default lang label for every role
        try:
            dupLabels[("zzzz",disclosureSystem.defaultXmlLang)] = None #to allow following loop
            priorRole = None
            hasDefaultLang = True
            for role, lang in sorted(dupLabels.keys()):
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
        except Exception as err:
            pass
        
    # check if concept is behaving as a total based on role, deed, or circumstances
    def presumptionOfTotal(self, rel, siblingRels, iSibling, isStatementSheet, nestedInTotal, checkLabelRoleOnly):
        concept = rel.toModelObject
        if concept.isNumeric:
            preferredLabel = rel.preferredLabel
            if XbrlConst.isTotalRole(preferredLabel):
                return _("preferredLabel {0}").format(os.path.basename(preferredLabel))
            if concept.isMonetary and not checkLabelRoleOnly: 
                effectiveLabel = concept.label(lang="en-US", fallbackToQname=False, preferredLabel=preferredLabel)
                ''' word total in label/name does not seem to be a good indicator, 
                    e.g., Google Total in label for ShareBasedCompensationArrangementByShareBasedPaymentAwardGrantDateFairValueOfOptionsVested followed by 
                    label with Aggregate but name has Total
                    ... so only perform this test on last monetary in a Note 
                if 'Total' in effectiveLabel: # also check for Net ???
                    return _("word 'Total' in effective label {0}").format(effectiveLabel)
                if 'Total' in concept.name: # also check for Net ???
                    return _("word 'Total' in concept name {0}").format(concept.name)
                '''
                parent = rel.fromModelObject
                if (len(siblingRels) > 1 and
                    iSibling == len(siblingRels) - 1 and 
                    parent.name not in {
                        "SupplementalCashFlowInformationAbstract"
                    } and
                    siblingRels[iSibling - 1].toModelObject.isMonetary):
                    # last fact, may be total
                    if isStatementSheet:
                        # check if facts add up??
                        if (parent.isAbstract or not parent.isMonetary) and not nestedInTotal:
                            return _("last monetary item in statement sheet monetary line items parented by nonMonetary concept")
                        elif 'Total' in effectiveLabel: 
                            return _("last monetary item in statement sheet monetary line items with word 'Total' in effective label {0}").format(effectiveLabel)
                        elif 'Total' in concept.name:
                            return _("last monetary item in statement sheet monetary line items with word 'Total' in concept name {0}").format(concept.name)
                    ''' for now unreliable to use total words for notes
                    else:
                        if 'Total' in effectiveLabel: # also check for Net ???
                            return _("last monetary item in note with word 'Total' in effective label {0}").format(effectiveLabel)
                        if 'Total' in concept.name: # also check for Net ???
                            return _("last monetary item in note with word 'Total' in concept name {0}").format(concept.name)
                    '''
        return None

    # 6.15.02, 6.15.03
    def checkCalcsTreeWalk(self, parentChildRels, concept, isStatementSheet, inNestedTotal, conceptsUsed, visited):
        if concept not in visited:
            visited.add(concept)
            siblingRels = parentChildRels.fromModelObject(concept)
            foundTotalAtThisLevel = False
            for iSibling, rel in enumerate(siblingRels):
                reasonPresumedTotal = self.presumptionOfTotal(rel, siblingRels, iSibling, isStatementSheet, False, inNestedTotal)
                if reasonPresumedTotal:
                    foundTotalAtThisLevel = True
                    self.checkForCalculations(parentChildRels, siblingRels, iSibling, rel.toModelObject, rel, reasonPresumedTotal, isStatementSheet, conceptsUsed, False, set())
            if foundTotalAtThisLevel: # try nested tree walk to look for lower totals
                inNestedTotal = True
            for rel in siblingRels:
                self.checkCalcsTreeWalk(parentChildRels, rel.toModelObject, isStatementSheet, inNestedTotal, conceptsUsed, visited)
            visited.remove(concept)

    def checkForCalculations(self, parentChildRels, siblingRels, iSibling, totalConcept, totalRel, reasonPresumedTotal, isStatementSheet, conceptsUsed, nestedItems, contributingItems):
        # compatible preceding sibling facts must have calc relationship to toal
        for iContributingRel in range(iSibling - 1, -1, -1):
            contributingRel = siblingRels[iContributingRel]
            siblingConcept = contributingRel.toModelObject
            if siblingConcept is totalConcept: # direct cycle loop likely, possibly among children of abstract sibling
                break
            isContributingTotal = self.presumptionOfTotal(contributingRel, siblingRels, iContributingRel, isStatementSheet, True, False)
            if siblingConcept.isAbstract:
                childRels = parentChildRels.fromModelObject(siblingConcept)
                self.checkForCalculations(parentChildRels, childRels, len(childRels), totalConcept, totalRel, reasonPresumedTotal, isStatementSheet, conceptsUsed, True, contributingItems) 
            elif (siblingConcept in conceptsUsed and
                  siblingConcept.isNumeric and
                  siblingConcept.periodType == totalConcept.periodType):
                contributingItems.add(siblingConcept)
            if isContributingTotal:
                break
        if not nestedItems and contributingItems:
            # must check each totalFact and compatible items for a relationship set separately
            # (because different sets of sums/items could, on edge case, be in different ELRs)
            compatibleItemsFacts = defaultdict(set)
            for totalFact in self.modelXbrl.factsByQname[totalConcept.qname]:
                if (not isStatementSheet or
                    (self.requiredContext is None or
                     self.requiredContext.startDatetime <= totalFact.context.endDatetime <= self.requiredContext.endDatetime)): 
                    compatibleItemConcepts = set()
                    compatibleFacts = {totalFact}
                    for itemConcept in contributingItems:
                        for itemFact in self.modelXbrl.factsByQname[itemConcept.qname]:
                            if (totalFact.context.isEqualTo(itemFact.context) and
                                totalFact.unit.isEqualTo(itemFact.unit)):
                                compatibleItemConcepts.add(itemConcept)
                                compatibleFacts.add(itemFact)
                    if compatibleItemConcepts:
                        compatibleItemsFacts[frozenset(compatibleItemConcepts)].update(compatibleFacts)
            for compatibleItemConcepts, compatibleFacts in compatibleItemsFacts.items():
                foundSummationItemSet = False 
                leastMissingItemsSet = compatibleItemConcepts
                for ELR in self.modelXbrl.relationshipSet(XbrlConst.summationItem).linkRoleUris:
                    missingItems = (compatibleItemConcepts - 
                                    frozenset(r.toModelObject 
                                              for r in self.modelXbrl.relationshipSet(XbrlConst.summationItem,ELR).fromModelObject(totalConcept)))
                    if missingItems:
                        if len(missingItems) < len(leastMissingItemsSet):
                            leastMissingItemsSet = missingItems
                    else: 
                        foundSummationItemSet = True
                if not foundSummationItemSet:
                    if isStatementSheet:
                        errs = ("EFM.6.15.02,6.13.02,6.13.03", "GFM.2.06.02,2.05.02,2.05.03")
                        msg = _("Financial statement calculation relationship missing from total concept to item concepts, based on required presentation of line items and totals.  "
                                "\n\nPresentation link role: \n%(linkrole)s. "
                                "\n\nTotal concept: \n%(conceptSum)s.  "
                                "\n\nReason presumed total: \n%(reasonPresumedTotal)s.  "
                                "\n\nSummation items missing: \n%(missingConcepts)s.  "
                                "\n\nExpected item concepts: \n%(itemConcepts)s.  "
                                "\n\nCorresponding facts in contexts: \n%(contextIDs)s\n")
                    else:
                        errs = ("EFM.6.15.03,6.13.02,6.13.03", "GFM.2.06.03,2.05.02,2.05.03")
                        msg = _("Notes calculation relationship missing from total concept to item concepts, based on required presentation of line items and totals. "
                                "\n\nPresentation link role: \n%(linkrole)s. "
                                "\n\nTotal concept: \n%(conceptSum)s.  "
                                "\n\nReason presumed total: \n%(reasonPresumedTotal)s.  "
                                "\n\nSummation items missing \n%(missingConcepts)s.  "
                                "\n\nExpected item concepts \n%(itemConcepts)s.  "
                                "\n\nCorresponding facts in contexts: \n%(contextIDs)s\n")
                    self.modelXbrl.log("ERROR-SEMANTIC", errs, msg,
                        modelObject=[totalConcept, totalRel, siblingConcept, contributingRel] + [f for f in compatibleFacts], 
                        conceptSum=totalConcept.qname, linkrole=contributingRel.linkrole,
                        reasonPresumedTotal=reasonPresumedTotal,
                        itemConcepts=', \n'.join(sorted(set(str(c.qname) for c in compatibleItemConcepts))),
                        missingConcepts = ', \n'.join(sorted(set(str(c.qname) for c in leastMissingItemsSet))),
                        contextIDs=', '.join(sorted(set(f.contextID for f in compatibleFacts))))
                del foundSummationItemSet 
                del leastMissingItemsSet
            del compatibleItemsFacts # dereference object references
        
# for SBR 2.3.4.01
def pLinkedNonAbstractDescendantQnames(modelXbrl, concept, descendants=None):
    if descendants is None: descendants = set()
    for rel in modelXbrl.relationshipSet(XbrlConst.parentChild).fromModelObject(concept):
        child = rel.toModelObject
        if child is not None:
            if child.isAbstract:
                pLinkedNonAbstractDescendantQnames(modelXbrl, child, descendants)
            else:
                descendants.add(child.qname)
    return descendants
