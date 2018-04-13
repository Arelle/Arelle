'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import re, datetime
from collections import defaultdict
from arelle import (ModelDocument, ModelValue, ModelRelationshipSet, 
                    XmlUtil, XbrlConst, ValidateFilingText)
from arelle.ModelValue import qname
from arelle.ValidateXbrlCalcs import insignificantDigits
from arelle.ModelObject import ModelObject
from arelle.ModelInstanceObject import ModelFact, ModelInlineFootnote
from arelle.ModelDtsObject import ModelConcept, ModelResource
from arelle.PluginManager import pluginClassMethods
from arelle.PrototypeDtsObject import LinkPrototype, LocPrototype, ArcPrototype
from arelle.PythonUtil import pyNamedObject, strTruncate
from arelle.UrlUtil import isHttpUrl
from arelle.ValidateXbrlCalcs import inferredDecimals
from arelle.XmlValidate import VALID
from .DTS import checkFilingDTS, usNamespacesConflictPattern, ifrsNamespacesConflictPattern
from .Dimensions import checkFilingDimensions
from .PreCalAlignment import checkCalcsTreeWalk

#qnFasbExtensibleListItemTypes = (qname("{http://fasb.org/us-types/2017-01-31}us-types:extensibleListItemType"),
#                                 qname("{http://fasb.org/srt-types/2018-01-31}srt-types:extensibleListItemType"))

ifrsSrtConcepts = { # concepts of ifrs items or axes which have a corresponding srt element
    "CounterpartiesAxis": "CounterpartyNameAxis",
    "MajorCustomersAxis": "MajorCustomersAxis",
    "ProductsAndServicesAxis": "ProductOrServiceAxis",
    "RangeAxis": "RangeAxis"
    }
srtAxisIfrsMembers = { # members of IFRS axes which have SRT corresponding member elements
    "CounterpartyNameAxis": {"CounterpartiesMember", "IndividuallyInsignificantCounterpartiesMember"},
    "MajorCustomersAxis": {"MajorCustomersMember", "GovernmentMember"},
    "ProductOrServiceAxis": {"ProductsAndServicesMember"},
    "RangeAxis": {"RangesMember", "BottomOfRangeMember", "WeightedAverageMember", "TopOfRangeMember"}    }

def validateFiling(val, modelXbrl, isEFM=False, isGFM=False):
    if not hasattr(modelXbrl.modelDocument, "xmlDocument"): # not parsed
        return
    
    datePattern = re.compile(r"([12][0-9]{3})-([01][0-9])-([0-3][0-9])")
    GFMcontextDatePattern = re.compile(r"^[12][0-9]{3}-[01][0-9]-[0-3][0-9]$")
    # note \u20zc = euro, \u00a3 = pound, \u00a5 = yen
    signOrCurrencyPattern = re.compile("^(-)[0-9]+|[^eE](-)[0-9]+|(\\()[0-9].*(\\))|([$\u20ac\u00a3\00a5])")
    instanceFileNamePattern = re.compile(r"^(\w+)-([12][0-9]{3}[01][0-9][0-3][0-9]).xml$")
    htmlFileNamePattern = re.compile(r"([a-zA-Z0-9][._a-zA-Z0-9-]*)\.htm$")
    linkroleDefinitionStatementSheet = re.compile(r"[^-]+-\s+Statement\s+-\s+.*", # no restriction to type of statement
                                                  re.IGNORECASE)
    efmCIKpattern = re.compile(r"^[0-9]{10}$")
    instantPreferredLabelRolePattern = re.compile(r".*[pP]eriod(Start|End)")
    embeddingCommandPattern = re.compile(r"[^~]*~\s*()[^~]*~")
    styleIxHiddenPattern = re.compile(r"(.*[^\w]|^)-sec-ix-hidden\s*:\s*([\w.-]+).*")
    
    val._isStandardUri = {}
    modelXbrl.modelManager.disclosureSystem.loadStandardTaxonomiesDict()
    
    # note that some XFM tests are done by ValidateXbrl to prevent mulstiple node walks
    xbrlInstDoc = modelXbrl.modelDocument.xmlDocument.getroot()
    disclosureSystem = val.disclosureSystem
    disclosureSystemVersion = disclosureSystem.version
    
    modelXbrl.modelManager.showStatus(_("validating {0}").format(disclosureSystem.name))
    
    val.modelXbrl.profileActivity()
    conceptsUsed = {} # key=concept object value=True if has presentation label
    labelsRelationshipSet = modelXbrl.relationshipSet(XbrlConst.conceptLabel)
    # genLabelsRelationshipSet = modelXbrl.relationshipSet(XbrlConst.elementLabel)
    # presentationRelationshipSet = modelXbrl.relationshipSet(XbrlConst.parentChild)
    referencesRelationshipSetWithProhibits = modelXbrl.relationshipSet(XbrlConst.conceptReference, includeProhibits=True)
    val.modelXbrl.profileActivity("... cache lbl, pre, ref relationships", minTimeToShow=1.0)
    
    validateInlineXbrlGFM = (modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL and
                             isGFM)
    validateEFMpragmatic = disclosureSystem.names and "efm-pragmatic" in disclosureSystem.names
    val.validateLoggingSemantic = validateLoggingSemantic = (
          modelXbrl.isLoggingEffectiveFor(level="WARNING-SEMANTIC") or 
          modelXbrl.isLoggingEffectiveFor(level="ERROR-SEMANTIC"))
    
    if isEFM:
        for pluginXbrlMethod in pluginClassMethods("Validate.EFM.Start"):
            pluginXbrlMethod(val)
            
    if "EFM/Filing.py#validateFiling_start" in val.modelXbrl.arelleUnitTests:
        raise pyNamedObject(val.modelXbrl.arelleUnitTests["EFM/Filing.py#validateFiling_start"])

    # instance checks
    val.fileNameBasePart = None # prevent testing on fileNameParts if not instance or invalid
    val.fileNameDate = None
    val.entityRegistrantName = None
    val.requiredContext = None
    val.standardNamespaceConflicts = defaultdict(set)
    documentType = None # needed for non-instance validation too
    isInlineXbrl = modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL
    if modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or isInlineXbrl:
        instanceName = modelXbrl.modelDocument.basename
        
        #6.3.3 filename check
        m = instanceFileNamePattern.match(instanceName)
        if isInlineXbrl:
            m = htmlFileNamePattern.match(instanceName)
            if m:
                val.fileNameBasePart     = None # html file name not necessarily parseable.
                val.fileNameDatePart = None
            else:
                modelXbrl.error(val.EFM60303,
                                _('Invalid inline xbrl document in {base}.htm": %(filename)s'),
                                modelObject=modelXbrl.modelDocument, filename=instanceName,
                                messageCodes=("EFM.6.03.03",))
        elif m:
            val.fileNameBasePart = m.group(1)
            val.fileNameDatePart = m.group(2)
            if not val.fileNameBasePart:
                modelXbrl.error((val.EFM60303, "GFM.1.01.01"),
                    _('Invalid instance document base name part (ticker or mnemonic name) in "{base}-{yyyymmdd}.xml": %(filename)s'),
                    modelObject=modelXbrl.modelDocument, filename=modelXbrl.modelDocument.basename,
                    messageCodes=("EFM.6.03.03", "EFM.6.23.01", "GFM.1.01.01"))
            else:
                try:
                    val.fileNameDate = datetime.datetime.strptime(val.fileNameDatePart,"%Y%m%d").date()
                except ValueError:
                    modelXbrl.error((val.EFM60303, "GFM.1.01.01"),
                        _('Invalid instance document base name part (date) in "{base}-{yyyymmdd}.xml": %(filename)s'),
                        modelObject=modelXbrl.modelDocument, filename=modelXbrl.modelDocument.basename,
                        messageCodes=("EFM.6.03.03", "EFM.6.23.01", "GFM.1.01.01"))
        else:
            modelXbrl.error((val.EFM60303, "GFM.1.01.01"),
                _('Invalid instance document name, must match "{base}-{yyyymmdd}.xml": %(filename)s'),
                modelObject=modelXbrl.modelDocument, filename=modelXbrl.modelDocument.basename,
                messageCodes=("EFM.6.03.03", "EFM.6.23.01", "GFM.1.01.01"))
        
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
                            _("Your identifier for the CIK code, %(identifier)s, or scheme %(scheme)s, in context %(context)s, did not adhere "
                              "to the standard naming convention of <identifier scheme='http://www.sec.gov/CIK'>xxxxxxxxxx</identifier>'.  "
                              "Please recheck your submission and comply with the standard naming convention."),
                            edgarCode="cp-0501-Entity-Identifier-Scheme",
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
                        entityIdentifierValueElt = entityIdentifierElt
                        if isEFM and not efmCIKpattern.match(entityIdentifierValue):
                            val.modelXbrl.error("EFM.6.05.23.cikValue",
                                _("The context identifier CIK %(entityIdentifier)s is not 10 digits, for required context(s).  "
                                  "Please include a correct context identifier CIK in the filing."),
                                edgarCode="cp-0523-Non-Matching-Cik",
                                modelObject=entityIdentifierElt, entityIdentifier=entityIdentifierValue)
                    elif entityIdentifier != entityIdentifierValue:
                        modelXbrl.error(("EFM.6.05.03", "GFM.1.02.03"),
                            _("The submission CIK, %(filerIdentifier)s does not match either the EntityCentralIndexKey, %(entityIdentifer)s, "
                              "or context identifier CIK(s) %(entityIdentifer)s, %(entityIdentifer2)s, or is not 10 digits, for required context(s).  "
                              "Please include a correct matching EntityCentralIndexKey and context identifier CIK(s) in the filing."),
                            edgarCode="cp-0523-Non-Matching-Cik",
                            modelObject=(entityIdentifierElt, entityIdentifierValueElt),  
                            entityIdentifierName=disclosureSystem.identifierValueName,
                            entityIdentifer=entityIdentifierValue,
                            entityIdentifer2=entityIdentifier,
                            filerIdentifier=",".join(sorted(val.paramFilerIdentifierNames.keys()) if val.paramFilerIdentifierNames else []))
            val.modelXbrl.profileActivity("... filer identifier checks", minTimeToShow=1.0)

        #6.5.7 duplicated contexts
        contexts = modelXbrl.contexts.values()
        contextIDs = set()
        uniqueContextHashes = {}
        contextsWithDisallowedOCEs = []
        contextsWithDisallowedOCEcontent = []
        nonStandardTypedDimensions = defaultdict(set)
        for context in contexts:
            contextID = context.id
            contextIDs.add(contextID)
            h = context.contextDimAwareHash
            if h in uniqueContextHashes:
                if context.isEqualTo(uniqueContextHashes[h]):
                    modelXbrl.error(("EFM.6.05.07", "GFM.1.02.07"),
                        _("The instance document contained more than one context equivalent to %(context)s (%(context2)s).  "
                          "Please remove duplicate contexts from the instance."),
                        edgarCode="du-0507-Duplicate-Contexts",
                        modelObject=(context, uniqueContextHashes[h]), context=contextID, context2=uniqueContextHashes[h].id)
            else:
                uniqueContextHashes[h] = context
                
            #GFM no time in contexts
            if isGFM:
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
                if validateEFMpragmatic:
                    contextsWithDisallowedOCEs.append(context)
                else:
                    modelXbrl.error(("EFM.6.05.04", "GFM.1.02.04"),
                        _("There must be no contexts with %(elementName)s, but %(count)s was(were) found: %(context)s."),
                        edgarCode="cp-0504-No-Scenario",
                        modelObject=context, elementName=notAllowed, context=contextID, count=1)
    
            #6.5.5 segment only explicit dimensions
            for contextName in {"segment": ("{http://www.xbrl.org/2003/instance}segment",),
                                "scenario": ("{http://www.xbrl.org/2003/instance}scenario",),
                                "either": ("{http://www.xbrl.org/2003/instance}segment","{http://www.xbrl.org/2003/instance}scenario"),
                                "both": ("{http://www.xbrl.org/2003/instance}segment","{http://www.xbrl.org/2003/instance}scenario"),
                                "none": [], None:[]
                                }[disclosureSystem.contextElement]:
                for segScenElt in context.iterdescendants(contextName):
                    if isinstance(segScenElt,ModelObject):
                        _childTagNames = [child.prefixedName for child in segScenElt.iterchildren()
                                          if isinstance(child,ModelObject) and 
                                             child.tag not in ("{http://xbrl.org/2006/xbrldi}explicitMember",
                                                               "{http://xbrl.org/2006/xbrldi}typedMember")]
                        childTags = ", ".join(_childTagNames)
                        if len(childTags) > 0:
                            if validateEFMpragmatic:
                                contextsWithDisallowedOCEcontent.append(context)
                            else:
                                modelXbrl.error(("EFM.6.05.05", "GFM.1.02.05"),
                                                _("There must be no %(elementName)s with non-explicitDimension content, but %(count)s was(were) found: %(content)s."),
                                                edgarCode="cp-0505-Segment-Child-Not-Explicit-Member",
                                                modelObject=context, context=contextID, content=childTags, count=len(_childTagNames),
                                                elementName=contextName.partition("}")[2].title())
            for dim in context.qnameDims.values():
                if dim.isTyped and dim.dimensionQname.namespaceURI not in disclosureSystem.standardTaxonomiesDict:
                    nonStandardTypedDimensions[dim.dimensionQname].add(context)
            #6.5.38 period forever
            if context.isForeverPeriod:
                val.modelXbrl.error("EFM.6.05.38",
                    _("Context %(contextID)s uses period <xbrli:forever>. Please remove it and resubmit."),
                    edgarCode="du-0538-Context-Has-Period-Forever",
                    modelObject=context, contextID=contextID)
        if validateEFMpragmatic: # output combined count message
            if contextsWithDisallowedOCEs:
                modelXbrl.error(("EFM.6.05.04", "GFM.1.02.04"),
                    _("There must be no contexts with %(elementName)s, but %(count)s was(were) found: %(context)s."),
                    edgarCode="cp-0504-No-Scenario",
                    modelObject=contextsWithDisallowedOCEs, elementName=notAllowed, 
                    count=len(contextsWithDisallowedOCEs), context=', '.join(c.id for c in contextsWithDisallowedOCEs))
            if contextsWithDisallowedOCEcontent:
                modelXbrl.error(("EFM.6.05.05", "GFM.1.02.05"),
                    _("There must be no %(elementName)s with non-explicitDimension content, but %(count)s was(were) found: %(context)s."),
                    edgarCode="cp-0505-Segment-Child-Not-Explicit-Member",
                    modelObject=contextsWithDisallowedOCEcontent, elementName=disclosureSystem.contextElement, 
                    count=len(contextsWithDisallowedOCEcontent), context=', '.join(c.id for c in contextsWithDisallowedOCEcontent))
        if nonStandardTypedDimensions:
            val.modelXbrl.error("EFM.6.05.39",
                _("Typed dimensions must be defined in standard taxonomy schemas, contexts: %(contextIDs)s dimensions: %(dimensions)s."),
                modelObject=set.union(*nonStandardTypedDimensions.values()), 
                contextIDs=", ".join(sorted(cntx.id for cntx in set.union(*nonStandardTypedDimensions.values()))),
                dimensions=", ".join(sorted(str(qn) for qn in nonStandardTypedDimensions.keys())))
        del uniqueContextHashes, contextsWithDisallowedOCEs, contextsWithDisallowedOCEcontent, nonStandardTypedDimensions
        val.modelXbrl.profileActivity("... filer context checks", minTimeToShow=1.0)


        #fact items from standard context (no dimension)
        amendmentDescription = None
        amendmentDescriptionFact = None
        amendmentFlag = None
        amendmentFlagFact = None
        documentPeriodEndDate = None # date or None
        documentPeriodEndDateFact = None
        documentTypeFact = None
        deiItems = {}
        deiFacts = {}
        commonSharesItemsByStockClass = defaultdict(list)
        commonSharesClassMembers = None
        # hasDefinedStockAxis = False
        hasCommonSharesOutstandingDimensionedFactWithDefaultStockClass = False
        # commonSharesClassUndefinedMembers = None
        # commonStockMeasurementDatetime = None

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
            "DocumentFiscalPeriodFocus",
            "EntityReportingCurrencyISOCode", # for SD 
             }
        #6.5.8 unused contexts
        #candidateRequiredContexts = set()
        for f in modelXbrl.facts:
            factContextID = f.contextID
            contextIDs.discard(factContextID)
                
            context = f.context
            factQname = f.qname # works for both inline and plain instances
            factElementName = factQname.localName
            if disclosureSystem.deiNamespacePattern is not None:
                factInDeiNamespace = disclosureSystem.deiNamespacePattern.match(factQname.namespaceURI)
            else:
                factInDeiNamespace = None
            # standard dei items from required context
            if context is not None: # tests do not apply to tuples
                if not context.hasSegment and not context.hasScenario and f.xValid >= VALID: 
                    #required context
                    if factInDeiNamespace:
                        value = f.xValue
                        if factElementName == disclosureSystem.deiAmendmentFlagElement:
                            amendmentFlag = value
                            amendmentFlagFact = f
                        elif factElementName == "AmendmentDescription":
                            amendmentDescription = value
                            amendmentDescriptionFact = f
                        elif factElementName == disclosureSystem.deiDocumentPeriodEndDateElement:
                            documentPeriodEndDate = value
                            documentPeriodEndDateFact = f
                            # commonStockMeasurementDatetime = context.endDatetime
                            #if (context.isStartEndPeriod and context.startDatetime is not None and context.endDatetime is not None):
                            #    if context.endDatetime.time() == datetime.time(0): # midnight of subsequent day
                            #        if context.endDatetime - datetime.timedelta(1) == f.xValue:
                            #            candidateRequiredContexts.add(context)
                            #    elif context.endDatetime.date() == f.xValue: # not midnight, only day portion matches
                            #        candidateRequiredContexts.add(context)
                        elif factElementName == "DocumentType":
                            documentType = value
                            documentTypeFact = f
                        elif factElementName == disclosureSystem.deiFilerIdentifierElement:
                            deiItems[factElementName] = value
                            deiFilerIdentifierFact = f
                        elif factElementName == disclosureSystem.deiFilerNameElement:
                            deiItems[factElementName] = value
                            deiFilerNameFact = f
                        elif factElementName in deiCheckLocalNames:
                            deiItems[factElementName] = value
                            deiFacts[factElementName] = f
                            if (val.requiredContext is None and context.isStartEndPeriod and
                                context.startDatetime is not None and context.endDatetime is not None):
                                val.requiredContext = context
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
                                dimConcept is not None and
                                dimConcept.name in ("StatementClassOfStockAxis", "ClassesOfShareCapitalAxis") and
                                dimConcept.modelDocument.targetNamespace in disclosureSystem.standardTaxonomiesDict):
                                commonSharesItemsByStockClass[memConcept.qname].append(f)
                                ''' per discussion with Dean R, remove use of LB defined members from this test
                                if commonSharesClassMembers is None:
                                    commonSharesClassMembers, hasDefinedStockAxis = val.getDimMembers(dimConcept)
                                if not hasDefinedStockAxis: # no def LB for stock axis, note observed members
                                    commonSharesClassMembers.add(memConcept.qname) 
                                #following is replacement:'''
                                if commonSharesClassMembers is None:
                                    commonSharesClassMembers = set()
                                commonSharesClassMembers.add(memConcept.qname) # only note the actually used members, not any defined members
                                #end of replacement 
                                hasClassOfStockMember = True
                                
                    if isEntityCommonStockSharesOutstanding and not hasClassOfStockMember:
                        hasCommonSharesOutstandingDimensionedFactWithDefaultStockClass = True   # absent dimension, may be no def LB

                if isEFM: # note that this is in the "if context is not None" region
                    for pluginXbrlMethod in pluginClassMethods("Validate.EFM.Fact"):
                        pluginXbrlMethod(val, f)
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
                            _("Your filing contained elements using the precision attribute.  Please recheck your submission and replace "
                              "the precision attribute with the decimals attribute."),
                            edgarCode="fs-0517-Decimals-Not-Precision",
                            modelObject=f, fact=f.qname, contextID=factContextID, precision=f.precision)

                #6.5.25 domain items as facts
                if isEFM and concept.type is not None and concept.type.isDomainItemType:
                    modelXbrl.error("EFM.6.05.25",
                        _("The domain item %(fact)s cannot appear as a fact.  Please remove the fact from context %(contextID)s."),
                        edgarCode="du-0525-Domain-As-Fact",
                        modelObject=f, fact=f.qname, contextID=factContextID)
                    
                # fasb extensibleListItemType checks (2017-2018 only)
                #if concept.instanceOfType(qnFasbExtensibleListItemTypes):
                #    qnEnumsInvalid = []
                #    for qnToken in value.split():
                #        for qnValue in qnameEltPfxName(f, qnToken):
                #            qnConcept = modelXbrl.qnameConcepts.get(qnValue)
                #            if qnConcept is None:
                #                qnEnumsInvalid.append(qnToken)
                #            else:
                #                conceptsUsed[qnConcept] = False
                #    if qnEnumsInvalid:
                #        modelXbrl.error("EFM.tbd",
                #            _("The fact %(fact)s contains inappropriate enumeration items %(enumerationItems)s in context %(contextID)s.  Please remove the inappropriate enumeratiuon items."),
                #            edgarCode="du-tbd",
                #            modelObject=f, fact=f.qname, contextID=factContextID, enumerationItems=", ".join(qnEnumsInvalid))
                
            if validateInlineXbrlGFM:
                if f.localName == "nonFraction" or f.localName == "fraction":
                    syms = signOrCurrencyPattern.findall(f.text)
                    if syms:
                        modelXbrl.error(("EFM.N/A", "GFM.1.10.18"),
                            'ix-numeric Fact %(fact)s of context %(contextID)s has a sign or currency symbol "%(value)s" in "%(text)s"',
                            modelObject=f, fact=f.qname, contextID=factContextID, 
                            value="".join(s for t in syms for s in t), text=f.text)
                        
        val.entityRegistrantName = deiItems.get("EntityRegistrantName") # used for name check in 6.8.6
        
        # 6.05..23,24 check (after dei facts read)
        if not (isEFM and documentType == "L SDR"): # allow entityIdentifierValue == "0000000000" or any other CIK value
            if disclosureSystem.deiFilerIdentifierElement in deiItems:
                value = deiItems[disclosureSystem.deiFilerIdentifierElement]
                if entityIdentifierValue != value:
                    val.modelXbrl.error(("EFM.6.05.23", "GFM.3.02.02"),
                        _("The EntityCentralIndexKey, %(value)s, does not match the context identifier CIK %(entityIdentifier)s.  "
                          "Please include a correct matching EntityCentralIndexKey and context identifier CIK(s) in the filing."),
                        edgarCode="cp-0523-Non-Matching-Cik",
                        modelObject=f, elementName=disclosureSystem.deiFilerIdentifierElement,
                        value=value, entityIdentifier=entityIdentifierValue)
                if val.paramFilerIdentifierNames:
                    if value not in val.paramFilerIdentifierNames:
                        val.modelXbrl.error(("EFM.6.05.23.submissionIdentifier", "GFM.3.02.02"),
                            _("The submission CIK, %(filerIdentifier)s does not match the EntityCentralIndexKey.  "
                              "Please include a correct matching EntityCentralIndexKey in the filing."),
                            edgarCode="cp-0523-Non-Matching-Cik",
                            modelObject=f, elementName=disclosureSystem.deiFilerIdentifierElement,
                            value=value, filerIdentifier=",".join(sorted(val.paramFilerIdentifierNames.keys())))
                elif val.paramFilerIdentifier and value != val.paramFilerIdentifier:
                    val.modelXbrl.error(("EFM.6.05.23.submissionIdentifier", "GFM.3.02.02"),
                        _("The submission CIK, %(filerIdentifier)s does not match the %(elementName)s.  "
                          "Please include a correct matching %(elementName)s in the filing."),
                        edgarCode="cp-0523-Non-Matching-Cik",
                        modelObject=f, elementName=disclosureSystem.deiFilerIdentifierElement,
                        value=value, filerIdentifier=val.paramFilerIdentifier)
            if disclosureSystem.deiFilerNameElement in deiItems:
                value = deiItems[disclosureSystem.deiFilerNameElement]
                if val.paramFilerIdentifierNames and entityIdentifierValue in val.paramFilerIdentifierNames:
                    prefix = val.paramFilerIdentifierNames[entityIdentifierValue]
                    if prefix is not None and not value.lower().startswith(prefix.lower()):
                        val.modelXbrl.error(("EFM.6.05.24", "GFM.3.02.02"),
                            _("The Official Registrant name, %(prefix)s, does not match the value %(value)s in the Required Context.  "
                              "Please correct dei:%(elementName)s."),
                            edgarCode="cp-0524-Registrant-Name-Mismatch",
                            modelObject=f, elementName=disclosureSystem.deiFilerNameElement,
                            prefix=prefix, value=value)
                        
        val.modelXbrl.profileActivity("... filer fact checks", minTimeToShow=1.0)

        if len(contextIDs) > 0: # check if contextID is on any undefined facts
            for undefinedFact in modelXbrl.undefinedFacts:
                contextIDs.discard(undefinedFact.get("contextRef"))
            if len(contextIDs) > 0:
                modelXbrl.error(("EFM.6.05.08", "GFM.1.02.08"),
                                _("The instance document contained a context %(contextIDs)s that was not used in any fact. Please remove the context from the instance."),
                                edgarCode="du-0508-Unused-Context",
                                modelXbrl=modelXbrl, contextIDs=", ".join(str(c) for c in contextIDs))

        #6.5.9, .10 start-end durations
        if disclosureSystem.GFM or \
           disclosureSystemVersion[0] >= 27 or \
           documentType in {
                    '20-F', '40-F', '10-Q', '10-QT', '10-K', '10-KT', '10', 'N-CSR', 'N-CSRS', 'N-Q',
                    '20-F/A', '40-F/A', '10-Q/A', '10-QT/A', '10-K/A', '10-KT/A', '10/A', 'N-CSR/A', 'N-CSRS/A', 'N-Q/A'}:
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
                        if isEFM and c1 != c2 and c2.isInstantPeriod:
                            duration = c2.endDatetime - start1
                            if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                modelXbrl.error(
                                    _("Context {0} startDate and {1} end (instant) have a duration of one day; that is inconsistent with document type {2}."),
                                         c1.id, c2.id, documentType), 
                                    "err", "EFM.6.05.10")
            '''
            durationCntxStartDatetimes = defaultdict(set)
            for cntx in contexts:
                if cntx.isStartEndPeriod and cntx.startDatetime is not None:
                    durationCntxStartDatetimes[cntx.startDatetime].add(cntx)
            probStartEndCntxsByEnd = defaultdict(set)
            startEndCntxsByEnd = defaultdict(set)
            probInstantCntxsByEnd = defaultdict(set)
            probCntxs = set()
            for cntx in contexts:
                end = cntx.endDatetime
                if end is not None:
                    if cntx.isStartEndPeriod:
                        thisStart = cntx.startDatetime
                        for otherStart, otherCntxs in durationCntxStartDatetimes.items():
                            duration = end - otherStart
                            if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                if disclosureSystemVersion[0] < 27:
                                    probCntxs |= otherCntxs - {cntx}
                                elif thisStart is not None and end - thisStart > datetime.timedelta(1):
                                    for otherCntx in otherCntxs:
                                        if otherCntx is not cntx and otherCntx.endDatetime != end and otherStart != cntx.startDatetime:
                                            probCntxs.add(otherCntx)
                        if probCntxs:
                            probStartEndCntxsByEnd[end] |= probCntxs
                            startEndCntxsByEnd[end] |= {cntx}
                            probCntxs.clear()
                    if isEFM and cntx.isInstantPeriod:
                        for otherStart, otherCntxs in durationCntxStartDatetimes.items():
                            duration = end - otherStart
                            if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                probCntxs |= otherCntxs
                        if probCntxs:
                            probInstantCntxsByEnd[end] |= ( probCntxs | {cntx} )
                            probCntxs.clear()
            del probCntxs
            for end, probCntxs in probStartEndCntxsByEnd.items():
                endCntxs = startEndCntxsByEnd[end]
                modelXbrl.error(("EFM.6.05.09", "GFM.1.2.9"),
                    _("Context %(endContexts)s endDate and %(startContexts)s startDate have a duration of one day; that is inconsistent "
                      "with document type %(documentType)s."),
                    edgarCode="fs-0509-Start-And-End-Dates-Not-Distinct-Inconsistent-With-Document-Type",
                    modelObject=probCntxs, endDate=XmlUtil.dateunionValue(end, subtractOneDay=True), 
                    endContexts=', '.join(sorted(c.id for c in endCntxs)),
                    startContexts=', '.join(sorted(c.id for c in probCntxs)), 
                    documentType=documentType)
            if disclosureSystemVersion[0] < 27:
                for end, probCntxs in probInstantCntxsByEnd.items():
                    modelXbrl.error("EFM.6.05.10",
                        _("Contexts %(contexts)s have an overlap of one day; that is inconsistent with document type %(documentType)s."),
                        edgarCode="fs-0510-Start-And-Instant-Dates-Not-Distinct-Inconsistent-With-Document-Type",
                        modelObject=probCntxs, endDate=XmlUtil.dateunionValue(end, subtractOneDay=True), 
                        contexts=', '.join(sorted(c.id for c in probCntxs)), 
                        documentType=documentType)
            del probStartEndCntxsByEnd, startEndCntxsByEnd, probInstantCntxsByEnd
            del durationCntxStartDatetimes
            val.modelXbrl.profileActivity("... filer instant-duration checks", minTimeToShow=1.0)
            
        #6.5.19 required context
        #for c in sorted(candidateRequiredContexts, key=lambda c: (c.endDatetime, c.endDatetime-c.startDatetime), reverse=True):
        #    val.requiredContext = c
        #    break # longest duration is first
        
        # pre-16.1 code to accept any duration period as start-end (per WH/HF e-mails 2016-03-13)
        if val.requiredContext is None: # possibly there is no document period end date with matching context
            for c in contexts:
                if c.isStartEndPeriod and not c.hasSegment and c.startDatetime is not None and c.endDatetime is not None:
                    val.requiredContext = c
                    break

        if val.requiredContext is None:
            modelXbrl.error(("EFM.6.05.19", "GFM.1.02.18"),
                _("Required context (no segment) not found for document type %(documentType)s."),
                edgarCode="cp-0519-Required-Context",
                modelObject=documentTypeFact, documentType=documentType)
            
        #6.5.11 equivalent units
        uniqueUnitHashes = {}
        for unit in val.modelXbrl.units.values():
            h = unit.hash
            if h in uniqueUnitHashes:
                if unit.isEqualTo(uniqueUnitHashes[h]):
                    modelXbrl.error(("EFM.6.05.11", "GFM.1.02.10"),
                        _("There is more than one unit equivalent to %(unitID)s (%(unitID2)s).  Please remove all but one and resubmit."),
                        edgarCode="du-0511-Duplicate-Units",
                        modelObject=(unit, uniqueUnitHashes[h]), unitID=unit.id, unitID2=uniqueUnitHashes[h].id)
            else:
                uniqueUnitHashes[h] = unit
            if isEFM:  # 6.5.38
                for measureElt in unit.iterdescendants(tag="{http://www.xbrl.org/2003/instance}measure"):
                    if isinstance(measureElt.xValue, ModelValue.QName) and len(measureElt.xValue.localName) > 65:
                        l = len(measureElt.xValue.localName.encode("utf-8"))
                        if l > 200:
                            modelXbrl.error("EFM.6.05.36",
                                _("Unit %(unitID)s contains a measure element whose local-name in UTF-8, length %(length)s, has more than 200 bytes:  %(measure)s.  Shorten the measure name."),
                                edgarCode="du-0536-name-length-limit",
                                modelObject=measureElt, unitID=unit.id, measure=measureElt.xValue.localName, length=l)
        del uniqueUnitHashes
        val.modelXbrl.profileActivity("... filer unit checks", minTimeToShow=1.0)


        # EFM.6.05.14, GFM.1.02.13 xml:lang tests, as of v-17, full default lang is compared
        #if val.validateEFM:
        #    factLangStartsWith = disclosureSystem.defaultXmlLang[:2]
        #else:
        #    factLangStartsWith = disclosureSystem.defaultXmlLang
        requiredFactLang = disclosureSystem.defaultXmlLang

        #6.5.12 equivalent facts
        factsForLang = {}
        factForConceptContextUnitLangHash = defaultdict(list)
        keysNotDefaultLang = {}
        for f1 in modelXbrl.facts:
            if f1.context is not None and f1.concept is not None:
                # build keys table for 6.5.14
                if not f1.isNil:
                    langTestKey = "{0},{1},{2}".format(f1.qname, f1.contextID, f1.unitID)
                    factsForLang.setdefault(langTestKey, []).append(f1)
                    lang = f1.xmlLang
                    if lang and lang != requiredFactLang: # not lang.startswith(factLangStartsWith):
                        keysNotDefaultLang[langTestKey] = f1
                        
                    # 6.5.37 test (insignificant digits due to rounding)
                    if f1.isNumeric and f1.decimals and f1.decimals != "INF" and not f1.isNil and getattr(f1,"xValid", 0) >= VALID:
                        try:
                            insignificance = insignificantDigits(f1.xValue, decimals=f1.decimals)
                            if insignificance: # if not None, returns (truncatedDigits, insiginficantDigits)
                                modelXbrl.error(("EFM.6.05.37", "GFM.1.02.26"),
                                    _("Fact %(fact)s of context %(contextID)s decimals %(decimals)s value %(value)s has insignificant digits %(insignificantDigits)s.  "
                                      "Please correct the fact value and resubmit."),
                                    edgarCode="du-0537-Nonzero-Digits-Truncated",
                                    modelObject=f1, fact=f1.qname, contextID=f1.contextID, decimals=f1.decimals, 
                                    value=f1.xValue, truncatedDigits=insignificance[0], insignificantDigits=insignificance[1])
                        except (ValueError,TypeError):
                            modelXbrl.error(("EFM.6.05.37", "GFM.1.02.26"),
                                _("Fact %(fact)s of context %(contextID)s decimals %(decimals)s value %(value)s causes a Value Error exception.  "
                                  "Please correct the fact value and resubmit."),
                                edgarCode="du-0537-Nonzero-Digits-Truncated",
                                modelObject=f1, fact=f1.qname, contextID=f1.contextID, decimals=f1.decimals, value=f1.value)
                # 6.5.12 test
                factForConceptContextUnitLangHash[f1.conceptContextUnitLangHash].append(f1)
        # 6.5.12 test
        aspectEqualFacts = defaultdict(list)
        for hashEquivalentFacts in factForConceptContextUnitLangHash.values():
            if len(hashEquivalentFacts) > 1:
                for f in hashEquivalentFacts:
                    aspectEqualFacts[(f.qname,f.contextID,f.unitID,f.xmlLang)].append(f)
                for fList in aspectEqualFacts.values():
                    fList.sort(key=lambda f: inferredDecimals(f), reverse=True)
                    f0 = fList[0]
                    if any(not f.isVEqualTo(f0) for f in fList[1:]):
                        modelXbrl.error(("EFM.6.05.12", "GFM.1.02.11"),
                            "The instance document contained an element, %(fact)s that was used more than once in contexts equivalent to %(contextID)s: values %(values)s.  "
                            "Please ensure there are no duplicate combinations of concept and context in the instance.",
                            edgarCode="du-0512-Duplicate-Facts",
                            modelObject=fList, fact=f0.qname, contextID=f0.contextID, values=", ".join(strTruncate(f.value, 128) for f in fList))
                aspectEqualFacts.clear()
        del factForConceptContextUnitLangHash, aspectEqualFacts
        val.modelXbrl.profileActivity("... filer fact checks", minTimeToShow=1.0)

        #6.5.14 facts without english text
        for keyNotDefaultLang, factNotDefaultLang in keysNotDefaultLang.items():
            anyDefaultLangFact = False
            for fact in factsForLang[keyNotDefaultLang]:
                if fact.xmlLang == requiredFactLang: #.startswith(factLangStartsWith):
                    anyDefaultLangFact = True
                    break
            if not anyDefaultLangFact:
                val.modelXbrl.error(("EFM.6.05.14", "GFM.1.02.13"),
                    _("Element %(fact)s in context %(contextID)s has text with xml:lang other than '%(lang2)s' (%(lang)s) without matching English text.  "
                      "Please provide a fact with xml:lang equal to '%(lang2)s'."),
                    edgarCode="du-0514-English-Text-Missing",
                    modelObject=factNotDefaultLang, fact=factNotDefaultLang.qname, contextID=factNotDefaultLang.contextID, 
                    lang=factNotDefaultLang.xmlLang, lang2=requiredFactLang) # factLangStartsWith)
                
        #label validations
        if not labelsRelationshipSet:
            val.modelXbrl.error(("EFM.6.10.01.missingLabelLinkbase", "GFM.1.05.01"),
                _("A label linkbase is required but was not found"), 
                modelXbrl=modelXbrl)
        elif disclosureSystem.defaultXmlLang:  # cannot check if no defaultXmlLang specified
            for concept in conceptsUsed.keys():
                checkConceptLabels(val, modelXbrl, labelsRelationshipSet, disclosureSystem, concept)
                    

        #6.5.15 facts with xml in text blocks
        ValidateFilingText.validateTextBlockFacts(modelXbrl)
    
        if amendmentFlag is None:
            modelXbrl.log("WARNING" if validateEFMpragmatic else "ERROR",
                          ("EFM.6.05.20.missingAmendmentFlag", "GFM.3.02.01"),
                _("You did not include the following data: %(elementName)s.  Please include %(elementName)s."),
                edgarCode="cp-0521-Amendment-Flag-Existence",
                modelXbrl=modelXbrl, elementName=disclosureSystem.deiAmendmentFlagElement)

        if not documentPeriodEndDate:
            modelXbrl.error(("EFM.6.05.20.missingDocumentPeriodEndDate", "GFM.3.02.01"),
                _("You did not include the following data: %(elementName)s.  Please include %(elementName)s."),
                edgarCode="cp-0520-Document-Period-End-Date-Existence",
                modelXbrl=modelXbrl, elementName=disclosureSystem.deiDocumentPeriodEndDateElement)
        """ not required, now handled by schema validation
        else:
            dateMatch = datePattern.match(documentPeriodEndDate)
            if not dateMatch or dateMatch.lastindex != 3:
                modelXbrl.error(("EFM.6.05.20", "GFM.3.02.01"),
                    _("%(elementName)s is in the required context is incorrect '%(date)s'"),
                    modelXbrl=modelXbrl, elementName=disclosureSystem.deiDocumentPeriodEndDateElement,
                    date=documentPeriodEndDate)
        """
        val.modelXbrl.profileActivity("... filer label and text checks", minTimeToShow=1.0)

        if isEFM:
            if amendmentFlag == True and amendmentDescription is None:
                modelXbrl.log("WARNING" if validateEFMpragmatic else "ERROR",
                              "EFM.6.05.20.missingAmendmentDescription",
                    _("AmendmentFlag is true in context %(contextID)s, so you must also provide an AmendmentDescription in that context."),
                    edgarCode="fs-0520-Amendment-Flag-Without-Amendment-Description",
                    modelObject=amendmentFlagFact, contextID=amendmentFlagFact.contextID if amendmentFlagFact is not None else "unknown")
    
            if amendmentDescription is not None and amendmentFlag != True:
                modelXbrl.log("WARNING" if validateEFMpragmatic else "ERROR",
                              "EFM.6.05.20.extraneous",
                    _("AmendmentFlag is not true in context %(contextID)s, so do not provide an AmendmentDescription in that context."),
                    edgarCode="fs-0520-Amendment-Description-Without-Amendment-Flag",
                    modelObject=amendmentDescriptionFact, contextID=amendmentDescriptionFact.contextID)
                
            if documentType is None:
                modelXbrl.error("EFM.6.05.20.missingDocumentType",
                    _("You did not include the following data: DocumentType  Please include DocumentType."), 
                    edgarCode="cp-0520-Document-Type-Existence",
                    modelXbrl=modelXbrl)
            elif documentType not in {
                                        "10-12B",
                                        "10-12B/A",
                                        "10-12G",
                                        "10-12G/A",
                                        "10-K",
                                        "10-K/A",
                                        "10-KT",
                                        "10-KT/A",
                                        "10-Q",
                                        "10-Q/A",
                                        "10-QT",
                                        "10-QT/A",
                                        "20-F",
                                        "20-F/A",
                                        "20FR12B",
                                        "20FR12B/A",
                                        "20FR12G",
                                        "20FR12G/A",
                                        "40-F",
                                        "40-F/A",
                                        "40FR12B",
                                        "40FR12B/A",
                                        "40FR12G",
                                        "40FR12G/A",
                                        "485BPOS",
                                        "497",
                                        "6-K",
                                        "6-K/A",
                                        "8-K",
                                        "8-K/A",
                                        "8-K12B",
                                        "8-K12B/A",
                                        "8-K12G3",
                                        "8-K12G3/A",
                                        "8-K15D5",
                                        "8-K15D5/A",
                                        "F-1",
                                        "F-1/A",
                                        "F-10",
                                        "F-10/A",
                                        "F-10EF",
                                        "F-10POS",
                                        "F-1MEF",
                                        "F-3",
                                        "F-3/A",
                                        "F-3ASR",
                                        "F-3D",
                                        "F-3DPOS",
                                        "F-3MEF",
                                        "F-4 POS",
                                        "F-4",
                                        "F-4/A",
                                        "F-4EF",
                                        "F-4MEF",
                                        "F-6",
                                        "F-9 POS",
                                        "F-9",
                                        "F-9/A",
                                        "F-9EF",
                                        "K SDR",
                                        "L SDR",
                                        "N-1A",
                                        "N-1A/A",
                                        "N-CSR",
                                        "N-CSR/A",
                                        "N-CSRS",
                                        "N-CSRS/A",
                                        "N-Q",
                                        "N-Q/A",
                                        "Other",
                                        "POS AM",
                                        "POS EX",
                                        "POS462B",
                                        "POS462C",
                                        "POSASR",
                                        "S-1",
                                        "S-1/A",
                                        "S-11",
                                        "S-11/A",
                                        "S-11MEF",
                                        "S-1MEF",
                                        "S-20",
                                        "S-3",
                                        "S-3/A",
                                        "S-3ASR",
                                        "S-3D",
                                        "S-3DPOS",
                                        "S-3MEF",
                                        "S-4 POS",
                                        "S-4",
                                        "S-4/A",
                                        "S-4EF",
                                        "S-4MEF",
                                        "S-B",
                                        "S-BMEF",
                                        "SD",
                                        "SD",
                                        "SD/A",
                                        "SD/A",
                                        "SP 15D2",
                                        "SP 15D2/A"
                                      }:
                modelXbrl.error("EFM.6.05.20.documentTypeValue",
                    _("Your dei:DocumentType has an illegal value, %(documentType)s, in context %(contextID)s.  Please correct it."),
                    edgarCode="cp-0520-Document-Type-Value",
                    modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType)
            elif val.paramSubmissionType:
                expectedDocumentTypes = { 
                                        "10-12B": ("10-12B", "Other"),
                                        "10-12B/A": ("10-12B/A", "Other"),
                                        "10-12G": ("10-12G", "Other"),
                                        "10-12G/A": ("10-12G/A", "Other"),
                                        "10-K": ("10-K",),
                                        "10-K/A": ("10-K", "10-K/A"),
                                        "10-KT": ("10-K","10-KT","Other"),
                                        "10-KT/A": ("10-K", "10-KT", "10-KT/A", "Other"),
                                        "10-Q": ("10-Q",),
                                        "10-Q/A": ("10-Q", "10-Q/A"),
                                        "10-QT": ("10-Q", "10-QT", "Other"),
                                        "10-QT/A": ("10-Q", "10-QT", "10-QT/A", "Other"),
                                        "20-F": ("20-F",),
                                        "20-F/A": ("20-F", "20-F/A"),
                                        "20FR12B": ("20FR12B", "Other"),
                                        "20FR12B/A": ("20FR12B/A", "Other"),
                                        "20FR12G": ("20FR12G", "Other"),
                                        "20FR12G/A": ("20FR12G/A", "Other"),
                                        "40-F": ("40-F",),
                                        "40-F/A": ("40-F", "40-F/A"),
                                        "40FR12B": ("40FR12B", "Other"),
                                        "40FR12B/A": ("40FR12B/A", "Other"),
                                        "40FR12G": ("40FR12G", "Other"),
                                        "40FR12G/A": ("40FR12G/A", "Other"),
                                        "485BPOS": ("485BPOS",),
                                        "497": ("497", "Other"),
                                        "6-K": ("6-K",),
                                        "6-K/A": ("6-K", "6-K/A"),
                                        "8-K": ("8-K",),
                                        "8-K/A": ("8-K", "8-K/A"),
                                        "8-K12B": ("8-K12B", "Other"),
                                        "8-K12B/A": ("8-K12B/A", "Other"),
                                        "8-K12G3": ("8-K12G3", "Other"),
                                        "8-K12G3/A": ("8-K12G3/A", "Other"),
                                        "8-K15D5": ("8-K15D5", "Other"),
                                        "8-K15D5/A": ("8-K15D5/A", "Other"),
                                        "F-1": ("F-1",),
                                        "F-1/A": ("F-1", "F-1/A"),
                                        "F-10": ("F-10",),
                                        "F-10/A": ("F-10", "F-10/A"),
                                        "F-10EF": ("F-10EF", "Other"),
                                        "F-10POS": ("F-10POS", "Other"),
                                        "F-1MEF": ("F-1MEF",),
                                        "F-3": ("F-3",),
                                        "F-3/A": ("F-3", "F-3/A"),
                                        "F-3ASR": ("F-3", "F-3ASR"),
                                        "F-3D": ("F-3", "F-3D"),
                                        "F-3DPOS": ("F-3", "F-3DPOS"),
                                        "F-3MEF": ("F-3MEF",),
                                        "F-4": ("F-4",),
                                        "F-4 POS": ("F-4", "F-4 POS"),
                                        "F-4/A": ("F-4", "F-4/A"),
                                        "F-4EF": ("F-4", "F-4EF"),
                                        "F-4MEF": ("F-4MEF",),
                                        "F-9": ("F-9",),
                                        "F-9 POS": ("F-9", "F-9 POS"),
                                        "F-9/A": ("F-9", "F-9/A"),
                                        "F-9EF": ("F-9", "F-9EF"),
                                        "N-1A": ("N-1A",),
                                        "N-1A/A": ("N-1A/A", "Other"),
                                        "N-CSR": ("N-CSR",),
                                        "N-CSR/A": ("N-CSR/A",),
                                        "N-CSRS": ("N-CSRS",),
                                        "N-CSRS/A": ("N-CSRS/A",),
                                        "N-Q": ("N-Q",),
                                        "N-Q/A": ("N-Q/A",),
                                        "POS AM": ("F-1", "F-3", "F-4", "F-6", "Other", 
                                                   "POS AM", "S-1", "S-11", "S-20", "S-3", "S-4", "S-B"),
                                        "POS EX": ("F-3", "F-4", "Other", 
                                                   "POS EX", "S-1", "S-3", "S-4"),
                                        "POS462B": ("F-1MEF", "F-3MEF", "F-4MEF", "Other", 
                                                    "POS462B", "POS462C", "S-11MEF", "S-1MEF", "S-3MEF", "S-BMEF"),
                                        "POSASR": ("F-3", "Other", "POSASR", "S-3"),
                                        "S-1": ("S-1",),
                                        "S-1/A": ("S-1", "S-1/A"),
                                        "S-11": ("S-11",),
                                        "S-11/A": ("S-11/A",),
                                        "S-11MEF": ("S-11MEF",),
                                        "S-1MEF": ("S-1MEF",),
                                        "S-3": ("S-3",),
                                        "S-3/A": ("S-3", "S-3/A"),
                                        "S-3ASR": ("S-3", "S-3ASR"),
                                        "S-3D": ("S-3", "S-3D"),
                                        "S-3DPOS": ("S-3", "S-3DPOS"),
                                        "S-3MEF": ("S-3MEF",),
                                        "S-4": ("S-4",),
                                        "S-4 POS": ("S-4", "S-4 POS"),
                                        "S-4/A": ("S-4", "S-4/A"),
                                        "S-4EF": ("S-4", "S-4EF"),
                                        "S-4MEF": ("S-4MEF",),
                                        "SD": ("SD",),
                                        "SD/A": ("SD/A",),
                                        "SP 15D2": ("SP 15D2",),
                                        "SP 15D2/A": ("SP 15D2/A",),
                                        "SDR": ("K SDR", "L SDR"),
                                        "SDR/A": ("K SDR", "L SDR"),
                                        "SDR-A": ("K SDR", "L SDR"),
                                        "SDR/W ": ("K SDR", "L SDR")
                        }.get(val.paramSubmissionType)
                if expectedDocumentTypes and documentType not in expectedDocumentTypes:
                    modelXbrl.error("EFM.6.05.20.submissionDocumentType" if val.paramExhibitType != "EX-2.01" else "EFM.6.23.03",
                        _("The value for dei:DocumentType, %(documentType)s, does not match the submission type, %(submissionType)s, in context %(contextID)s. "
                          "EDGAR Filer Manual section 6.5.20 lists allowed submission types."),
                        #edgarCode="cp-0520-Document-Type-Not-Matched-To-Submission-Type",
                        modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType, submissionType=val.paramSubmissionType,
                        messageCodes=("EFM.6.05.20.submissionDocumentType", "EFM.6.23.03"))
            if val.paramExhibitType and documentType is not None:
                if (documentType in ("SD", "SD/A")) != (val.paramExhibitType == "EX-2.01"):
                    modelXbrl.error({"EX-100":"EFM.6.23.04",
                                     "EX-101":"EFM.6.23.04",    
                                     "EX-99.K SDR.INS":"EFM.6.23.04",
                                     "EX-99.L SDR.INS":"EFM.6.23.04",
                                     "EX-2.01":"EFM.6.23.05"}.get(val.paramExhibitType,"EX-101"),
                        #edgarCode
                        _("The value for dei:DocumentType, %(documentType)s, is not allowed for %(exhibitType)s attachments."),
                        modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType, exhibitType=val.paramExhibitType,
                        messageCodes=("EFM.6.23.04", "EFM.6.23.04", "EFM.6.23.05"))
                elif (((documentType == "K SDR") != (val.paramExhibitType in ("EX-99.K SDR", "EX-99.K SDR.INS"))) or
                      ((documentType == "L SDR") != (val.paramExhibitType in ("EX-99.L SDR", "EX-99.L SDR.INS")))):
                    modelXbrl.error("EFM.6.05.20.exhibitDocumentType",
                        _("The value for dei:DocumentType, '%(documentType)s' is not allowed for %(exhibitType)s attachments."),
                        modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType, exhibitType=val.paramExhibitType)
                
            # 6.5.21
            for doctypesRequired, deiItemsRequired in (
                  (("10-K", "10-KT", "10-Q", "10-QT", "20-F", "40-F",
                    "10-K/A", "10-KT/A", "10-Q/A", "10-QT/A", "20-F/A", "40-F/A",
                    "6-K", "NCSR", "N-CSR", "N-CSRS", "N-Q",
                    "6-K/A", "NCSR/A", "N-CSR/A", "N-CSRS/A", "N-Q/A",
                    "10", "S-1", "S-3", "S-4", "S-11", "POS AM",
                    "10/A", "S-1/A", "S-3/A", "S-4/A", "S-11/A", 
                    "8-K", "F-1", "F-3", "F-10", "497", "485BPOS",
                    "8-K/A", "F-1/A", "F-3/A", "F-10/A", "K SDR", "L SDR",
                    "Other"),
                    ("EntityRegistrantName", "EntityCentralIndexKey")),
                  (("10-K", "10-KT", "20-F", "40-F",
                    "10-K/A", "10-KT/A", "20-F/A", "40-F/A"),
                   ("EntityCurrentReportingStatus",)),
                 (("10-K", "10-KT", "10-K/A", "10-KT/A",),
                  ("EntityVoluntaryFilers", "EntityPublicFloat")),
                  (("10-K", "10-KT", "10-Q", "10-QT", "20-F", "40-F",
                    "10-K/A", "10-KT/A", "10-Q/A", "10-QT/A", "20-F/A", "40-F/A",
                    "6-K", "NCSR", "N-CSR", "N-CSRS", "N-Q",
                    "6-K/A", "NCSR/A", "N-CSR/A", "N-CSRS/A", "N-Q/A", "K SDR", "L SDR"),
                    ("CurrentFiscalYearEndDate", "DocumentFiscalYearFocus", "DocumentFiscalPeriodFocus")),
                  (("10-K", "10-KT", "10-Q", "10-QT", "20-F",
                    "10-K/A", "10-KT/A", "10-Q/A", "10-QT/A", "20-F/A",
                    "10", "S-1", "S-3", "S-4", "S-11", "POS AM",
                    "10/A", "S-1/A", "S-3/A", "S-4/A", "S-11/A"),
                    ("EntityFilerCategory",)),
                   (("10-K", "10-KT", "20-F", "10-K/A", "10-KT/A", "20-F/A"),
                     ("EntityWellKnownSeasonedIssuer",)),
                   (("SD", "SD/A"),
                     ("EntityReportingCurrencyISOCode", ))
            ):
                if documentType in doctypesRequired:
                    for deiItem in deiItemsRequired:
                        if deiItem not in deiItems or deiItems[deiItem] is None: #must exist and value must be non-empty (incl not nil)
                            modelXbrl.log(("WARNING" if validateEFMpragmatic and deiItem in {
                                             "CurrentFiscalYearEndDate", "DocumentFiscalPeriodFocus", "DocumentFiscalYearFocus",
                                             "EntityCurrentReportingStatus", "EntityFilerCategory", "EntityPublicFloat", 
                                             "EntityVoluntaryFilers", "EntityWellKnownSeasonedIssuer" 
                                            } else "ERROR"), 
                                          ("EFM.6.05.21.{0}".format(deiItem) if validateEFMpragmatic and deiItem in {
                                             "CurrentFiscalYearEndDate", "DocumentFiscalPeriodFocus", "DocumentFiscalYearFocus",
                                             "EntityRegistrantName", "EntityCentralIndexKey",
                                             "EntityCurrentReportingStatus", "EntityFilerCategory", "EntityPublicFloat", 
                                             "EntityVoluntaryFilers", "EntityWellKnownSeasonedIssuer"
                                            } else "EFM.6.23.36" if deiItem == "EntityReportingCurrencyISOCode"
                                              else "EFM.6.05.21"),
                                            _("Element dei:%(elementName)s is required for DocumentType '%(documentType)s' of context %(contextID)s.  Please include it."),
                    #edgarCode
                    modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType,
                    elementName=deiItem,
                    messageCodes=("EFM.6.05.21.CurrentFiscalYearEndDate", "EFM.6.05.21.DocumentFiscalPeriodFocus", "EFM.6.05.21.DocumentFiscalYearFocus",
                                  "EFM.6.05.21.EntityRegistrantName", "EFM.6.05.21.EntityCentralIndexKey",
                                  "EFM.6.05.21.EntityCurrentReportingStatus", "EFM.6.05.21.EntityFilerCategory", "EFM.6.05.21.EntityPublicFloat", 
                                  "EFM.6.05.21.EntityVoluntaryFilers", "EFM.6.05.21.EntityWellKnownSeasonedIssuer",
                                  "EFM.6.23.36", "EFM.6.05.21"))
                            
            if documentType in {"10-K", "10-KT", "10-Q", "10-QT", "20-F", "40-F",
                                "10-K/A", "10-KT/A", "10-Q/A", "10-QT/A", "20-F/A", "40-F/A"}:
                defaultContextSharesOutstandingValue = deiItems.get("EntityCommonStockSharesOutstanding")
                errLevel = "WARNING" if validateEFMpragmatic else "ERROR"
                if commonSharesClassMembers:
                    if defaultContextSharesOutstandingValue is not None: # checks that it exists and is not empty or nil
                        modelXbrl.log(errLevel, "EFM.6.05.26",
                            _("An instance with dei:DocumentType of %(documentType)s must have one dei:EntityCommonStockSharesOutstanding fact for each class of stock or units outstanding."),
                            edgarCode="im-0526-Entity-Common-Shares-Outstanding",
                            modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType)
                    elif len(commonSharesClassMembers) == 1: # and not hasDefinedStockAxis:
                        modelXbrl.log(errLevel, "EFM.6.05.26",
                            _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' but but a required-context because only one class of stock"),
                            #edgarCode
                            modelObject=documentTypeFact, documentType=documentType)
                    ''' per Dean R, this test no longer makes sense because we don't check against def LB defined members
                    missingClasses = commonSharesClassMembers - _DICT_SET(commonSharesItemsByStockClass.keys())
                    if missingClasses:
                        modelXbrl.log(errLevel, "EFM.6.05.26",
                            _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' but missing in these stock classes: %(stockClasses)s"),
                            modelObject=documentTypeFact, documentType=documentType, stockClasses=", ".join([str(c) for c in missingClasses]))
                    '''
                    for mem, facts in commonSharesItemsByStockClass.items():
                        if len(facts) != 1:
                            modelXbrl.log(errLevel, "EFM.6.05.26",
                                _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' but only one per stock class %(stockClass)s"),
                                #edgarCode
                                modelObject=documentTypeFact, documentType=documentType, stockClass=mem)
                        ''' removed per ARELLE-124 (should check measurement date vs report date)
                        elif facts[0].context.instantDatetime != commonStockMeasurementDatetime:
                            modelXbrl.log(errLevel, "EFM.6.05.26",
                                _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' in stock class %(stockClass)s with measurement date %(date)s"),
                                modelObject=documentTypeFact, documentType=documentType, stockClass=mem, date=commonStockMeasurementDatetime)
                        '''
                elif hasCommonSharesOutstandingDimensionedFactWithDefaultStockClass and defaultContextSharesOutstandingValue is None:
                        modelXbrl.log(errLevel, "EFM.6.05.26",
                            _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' but missing for a non-required-context fact"),
                            modelObject=documentTypeFact, documentType=documentType)
                elif defaultContextSharesOutstandingValue is None: # missing, empty, or nil
                    modelXbrl.log(errLevel, "EFM.6.05.26",
                        _("dei:EntityCommonStockSharesOutstanding is required for DocumentType '%(documentType)s' in the required context because there are not multiple classes of common shares"),
                        modelObject=documentTypeFact, documentType=documentType)
            if documentType in ("SD", "SD/A"): # SD documentType
                val.modelXbrl.profileActivity("... filer required facts checks (other than SD)", minTimeToShow=1.0)
                rxdNs = None # find RXD schema
                rxdDoc = None
                hasRxdPre = hasRxdDef = False
                for rxdLoc in disclosureSystem.familyHrefs["RXD"]:
                    rxdUri = rxdLoc.href
                    if rxdUri in modelXbrl.urlDocs:
                        if rxdUri.endswith(".xsd") and rxdLoc.elements == "1":
                            if rxdNs is None:
                                rxdDoc = modelXbrl.urlDocs[rxdUri]
                                rxdNs = rxdDoc.targetNamespace
                            else:
                                modelXbrl.error("EFM.6.23.10",
                                    _("The DTS of $(instance) must use only one version of the RXD schema."),
                                    edgarCode="rxd-2310-RXD-Version-Value",
                                    modelObject=(rxdDoc, modelXbrl.urlDocs[rxdUri]), instance=instanceName)
                        elif "/rxd-pre-" in rxdUri:
                            hasRxdPre = True
                        elif "/rxd-def-" in rxdUri:
                            hasRxdDef = True
                if not hasRxdPre:
                    modelXbrl.error("EFM.6.23.08",
                        _("The DTS of %(instance)s must use a standard presentation linkbase from Family RXD in edgartaxonomies.xml."),
                        edgarCode="rxd-2308-RXD-Presentation-Existence",
                        modelObject=modelXbrl, instance=instanceName)
                if not hasRxdDef:
                    modelXbrl.error("EFM.6.23.09",
                        _("The DTS of %(instance)s must use a standard definition linkbase from Family RXD in edgartaxonomies.xml."),
                        edgarCode="rxd-2309-RXD-Definition-Existence",
                        modelObject=modelXbrl, instance=instanceName)
                countryNs = None
                deiNS = None
                for url, doc in modelXbrl.urlDocs.items():
                    if doc.type == ModelDocument.Type.SCHEMA:
                        if url.startswith("http://xbrl.sec.gov/country/"):
                            if countryNs is None:
                                countryNs = doc.targetNamespace
                            else:
                                modelXbrl.error("EFM.6.23.11",
                                    _("The DTS of %(instance)s must use only one version of the COUNTRY schema."),
                                    edgarCode="rxd-2311-Country-Version-Value",
                                    modelObject=(doc
                                                 for url,doc in modelXbrl.urlDocs.items()
                                                 if url.startswith("http://xbrl.sec.gov/country/")), instance=instanceName)
                        if disclosureSystem.deiNamespacePattern.match(doc.targetNamespace):
                            deiNS = doc.targetNamespace

                if rxdNs:
                    qn = qname(rxdNs, "AmendmentNumber")
                    if amendmentFlag == True and (
                                qn not in modelXbrl.factsByQname or not any(
                                       f.context is not None and not f.context.hasSegment 
                                       for f in modelXbrl.factsByQname[qn])):
                        modelXbrl.error("EFM.6.23.06",
                            _("The value for dei:DocumentType, %(documentType)s, requires a value for rxd:AmendmentNumber in the Required Context."),
                            edgarCode="rxd-2306-Amendment-Number-Existence",
                            modelObject=modelXbrl, documentType=documentType)
                else:
                    modelXbrl.error("EFM.6.23.07",
                        _("The DTS of %(instance)s must use a standard schema from Family SD in edgartaxonomies.xml."),
                        edgarCode="rxd-2307-RXD-Schema-Existence",
                        modelObject=modelXbrl, instance=instanceName)
                class Rxd(): # fake class of rxd qnames based on discovered rxd namespace
                    def __init__(self):
                        for name in ("CountryAxis", "GovernmentAxis", "PaymentTypeAxis", "ProjectAxis","PmtAxis",
                                    "AllGovernmentsMember", "AllProjectsMember","BusinessSegmentAxis", "EntityDomain", 
                                    "A", "Cm", "Co", "Cu", "D", "Gv", "E", "K", "Km", "P", "Payments", "Pr", "Sm"):
                            setattr(self, name, qname(rxdNs, "rxd:" + name))

                rxd = Rxd()
                f1 = deiFacts.get(disclosureSystem.deiCurrentFiscalYearEndDateElement)
                if f1 is not None and documentPeriodEndDateFact is not None and f1.xValid >= VALID and documentPeriodEndDateFact.xValid >= VALID:
                    d = ModelValue.dateunionDate(documentPeriodEndDateFact.xValue)# is an end date, convert back to a start date without midnight part
                    if f1.xValue.month != d.month or f1.xValue.day != d.day:
                        modelXbrl.error("EFM.6.23.26",
                            _("The financial period %(reportingPeriod)s does not match the fiscal year end %(fyEndDate)s."),
                            edgarCode="rxd-2326-Fiscal-Year-End-Date-Value",
                            modelObject=(f1,documentPeriodEndDateFact), fyEndDate=f1.value, reportingPeriod=documentPeriodEndDateFact.value)
                if (documentPeriodEndDateFact is not None and documentPeriodEndDateFact.xValid >= VALID and
                    not any(f2.xValue == documentPeriodEndDateFact.xValue
                            for f2 in modelXbrl.factsByQname[rxd.D]
                            if f2.xValid >= VALID)):
                    modelXbrl.error("EFM.6.23.27",
                        _("The financial period %(reportingPeriod)s does not match rxd:D in any facts."),
                        edgarCode="rxd-2327-Payment-Financial-Period-Existence",
                        modelObject=documentPeriodEndDateFact, reportingPeriod=documentPeriodEndDateFact.value)
                for url,doc in modelXbrl.urlDocs.items():
                    if (url not in disclosureSystem.standardTaxonomiesDict and
                        doc.inDTS and # ignore EdgarRenderer-loaded non-DTS schemas
                        doc.type == ModelDocument.Type.SCHEMA):
                        for concept in XmlUtil.children(doc.xmlRootElement, XbrlConst.xsd, "element"):
                            name = concept.name
                            if not concept.isAbstract and not concept.isTextBlock:
                                modelXbrl.error("EFM.6.23.12",
                                    _("%(schemaName)s contained a non-abstract declaration for %(name)s that is not a Text Block.  "
                                      "Use a standard element or change the type to Text Block."),
                                    edgarCode="rxd-2312-Custom-Element-Value",
                                    modelObject=concept, schemaName=doc.basename, name=concept.name, concept=concept.qname)
                            elif name.endswith("Table") or name.endswith("Axis") or name.endswith("Domain"):
                                modelXbrl.error("EFM.6.23.13",
                                    _("%(schemaName)s contained a declaration for %(name)s that is not allowed.  "
                                      "Use dimensions from a standard schema instead."),
                                    edgarCode="rxd-2313-Custom-Dimension-Existence",
                                    modelObject=concept, schemaName=doc.basename, name=concept.name, concept=concept.qname)
                val.modelXbrl.profileActivity("... SD checks 6-13, 26-27", minTimeToShow=1.0)
                dimDefRelSet = modelXbrl.relationshipSet(XbrlConst.dimensionDefault)
                dimDomRelSet = modelXbrl.relationshipSet(XbrlConst.dimensionDomain)
                hypDimRelSet = modelXbrl.relationshipSet(XbrlConst.hypercubeDimension)
                hasHypRelSet = modelXbrl.relationshipSet(XbrlConst.all)
                for rel in dimDomRelSet.modelRelationships:
                    if (isinstance(rel.fromModelObject, ModelConcept) and isinstance(rel.toModelObject, ModelConcept) and 
                        not dimDefRelSet.isRelated(rel.fromModelObject, "child", rel.toModelObject)):
                        modelXbrl.error("EFM.6.23.14",
                            _("In %(linkbaseName)s the target of the dimension-domain relationship in role %(linkrole)s from "
                              "%(source)s to %(target)s must be the default member of %(source)s."),
                            edgarCode="rxd-2314-Dimension-Domain-Relationship-Existence",
                            modelObject=(rel, rel.fromModelObject, rel.toModelObject), 
                            linkbaseName=rel.modelDocument.basename, linkrole=rel.linkrole,
                            source=rel.fromModelObject.qname, target=rel.toModelObject.qname)
                domMemRelSet = modelXbrl.relationshipSet(XbrlConst.domainMember)
                memDim = {}
                def checkMemMultDims(memRel, dimRel, elt, ELR, visited):
                    if elt not in visited:
                        visited.add(elt)
                        for rel in domMemRelSet.toModelObject(elt):
                            if rel.consecutiveLinkrole == ELR and isinstance(rel.fromModelObject, ModelConcept):
                                checkMemMultDims(memRel, None, rel.fromModelObject, rel.linkrole, visited)
                        for rel in dimDomRelSet.toModelObject(elt):
                            if rel.consecutiveLinkrole == ELR:
                                dim = rel.fromModelObject
                                mem = memRel.toModelObject
                                if isinstance(dim, ModelConcept) and isinstance(mem, ModelConcept):
                                    if dim.qname == rxd.PaymentTypeAxis and not mem.modelDocument.targetNamespace.startswith("http://xbrl.sec.gov/rxd/"):
                                        modelXbrl.error("EFM.6.23.17",
                                            _("The member %(member)s of dimension rxd:PaymentTypeAxis in link role %(linkrole)s must be a QName "
                                              "with namespace that begins with 'http://xbrl.sec.gov/rxd/'."),
                                            edgarCode="rxd-2317-Payment-Type-Dimension-Value",
                                            modelObject=(rel, memRel, dim, mem), member=mem.qname, linkrole=rel.linkrole)
                                    if dim.qname == rxd.CountryAxis and not mem.modelDocument.targetNamespace.startswith("http://xbrl.sec.gov/country/"):
                                        modelXbrl.error("EFM.6.23.18",
                                            _("The member %(member)s of dimension rxd:CountryAxisAxis in link role %(linkrole)s must be a QName with namespace "
                                              "that begins with 'http://xbrl.sec.gov/country/'."),
                                            edgarCode="rxd-2318-Country-Dimension-Member-Value",
                                            modelObject=(rel, memRel, dim, mem), member=mem.qname, linkrole=rel.linkrole)
                                    checkMemMultDims(memRel, rel, rel.fromModelObject, rel.linkrole, visited)
                        for rel in hypDimRelSet.toModelObject(elt):
                            if rel.consecutiveLinkrole == ELR and isinstance(rel.fromModelObject, ModelConcept):
                                checkMemMultDims(memRel, dimRel, rel.fromModelObject, rel.linkrole, visited)
                        for rel in hasHypRelSet.toModelObject(elt):
                            if rel.consecutiveLinkrole == ELR and isinstance(rel.fromModelObject, ModelConcept):
                                linkrole = rel.linkrole
                                mem = memRel.toModelObject
                                if (mem,linkrole) not in memDim:
                                    memDim[mem,linkrole] = (dimRel, memRel)
                                else:
                                    otherDimRel, otherMemRel = memDim[mem,linkrole]
                                    modelXbrl.error("EFM.6.23.16",
                                        _("Member element %(member)s appears in more than one axis: %(dimension1)s and %(dimension2)s.  "
                                          "Use distinct members for the Project, Country, Government, Legal Entity, Business Segment and Payment Type axes."),
                                        edgarCode="rxd-2316-Member-Multiple-Axis-Existence",
                                        modelObject=(dimRel, otherDimRel, memRel, otherMemRel, dimRel.fromModelObject, otherDimRel.fromModelObject),
                                        member=mem.qname, dimension1=dimRel.fromModelObject.qname, linkrole1=linkrole, 
                                        dimension2=otherDimRel.fromModelObject.qname, linkrole2=otherDimRel.linkrole)
                        visited.discard(elt)
                for rel in domMemRelSet.modelRelationships:
                    if isinstance(rel.fromModelObject, ModelConcept) and isinstance(rel.toModelObject, ModelConcept):
                        for rel2 in modelXbrl.relationshipSet(XbrlConst.domainMember, rel.consecutiveLinkrole).fromModelObject(rel.toModelObject):
                            if isinstance(rel2.fromModelObject, ModelConcept) and isinstance(rel2.toModelObject, ModelConcept):
                                modelXbrl.error("EFM.6.23.15",
                                    _("The domain-member relationship in %(linkrole)s from %(source)s to %(target)s is consecutive with domain-member relationship in %(linkrole2)s to %(target2)s."),
                                    edgarCode="rxd-2315-Consecutive-Domain-Member-Relationships-Existence",
                                    modelObject=(rel, rel.fromModelObject, rel.toModelObject), 
                                    linkrole=rel.linkrole, linkrole2=rel2.linkrole,
                                    source=rel.fromModelObject.qname, target=rel.toModelObject.qname, target2=rel2.toModelObject.qname)
                        checkMemMultDims(rel, None, rel.fromModelObject, rel.linkrole, set())
                val.modelXbrl.profileActivity("... SD checks 14-18", minTimeToShow=1.0)
                qnDeiEntityDomain = qname(deiNS, "dei:EntityDomain")
                for relSet, dom, priItem, errCode in ((domMemRelSet, rxd.AllProjectsMember, rxd.Pr, "EFM.6.23.30"),
                                                      (domMemRelSet, rxd.AllGovernmentsMember, rxd.Gv, "EFM.6.23.31"),
                                                      (dimDomRelSet, rxd.BusinessSegmentAxis, rxd.Sm, "EFM.6.23.33"),
                                                      (domMemRelSet, qnDeiEntityDomain, rxd.E, "EFM.6.23.34")):
                    for f in modelXbrl.factsByQname[priItem]:
                        if (not f.isNil and f.xValid >= VALID and
                            not relSet.isRelated(dom, "descendant", f.xValue, isDRS=True)):
                            modelXbrl.error(errCode,
                                _("The %(fact)s %(value)s in context %(context)s is not a %(domain)s."),
                                modelObject=f, fact=priItem, value=f.xValue, context=f.context.id, domain=dom,
                                messageCodes=("EFM.6.23.30", "EFM.6.23.31", "EFM.6.23.33", "EFM.6.23.34"))
                val.modelXbrl.profileActivity("... SD checks 30, 31, 33, 34", minTimeToShow=1.0)
                cntxEqualFacts = defaultdict(list)
                for f in modelXbrl.facts:
                    if f.context is not None:
                        cntxEqualFacts[f.context.contextDimAwareHash].append(f)
                val.modelXbrl.profileActivity("... SD prepare facts by context", minTimeToShow=1.0)
                
                qnCurrencyMeasure = XbrlConst.qnIsoCurrency(deiItems.get("EntityReportingCurrencyISOCode"))
                currencyMeasures = ([qnCurrencyMeasure],[])
                qnAllCountriesDomain = qname(countryNs, "country:AllCountriesDomain")
                for cntxFacts in cntxEqualFacts.values():
                    qnameFacts = dict((f.qname,f) for f in cntxFacts)
                    context = cntxFacts[0].context
                    contextDims = cntxFacts[0].context.qnameDims
                    # required priItem values based on context dimension
                    for dim, priItem, errCode in ((rxd.PmtAxis, rxd.P, "EFM.6.23.20"),
                                                  (rxd.GovernmentAxis, rxd.Payments, "EFM.6.23.22")):
                        if context.hasDimension(dim) and (priItem not in qnameFacts or qnameFacts[priItem].isNil): 
                            modelXbrl.error(errCode,
                                _("The Context %(context)s has dimension %(dimension)s member %(member)s but is missing required fact %(fact)s"),
                                modelObject=context, context=context.id, dimension=dim, member=context.dimMemberQname(dim), fact=priItem,
                                messageCodes=("EFM.6.23.20", "EFM.6.23.22"))
                    if (rxd.Co in qnameFacts and not qnameFacts[rxd.Co].isNil and
                        not domMemRelSet.isRelated(qnAllCountriesDomain, "descendant", qnameFacts[rxd.Co].xValue, isDRS=True)):
                        modelXbrl.error("EFM.6.23.44",
                            _("The value of rxd:Co in context %(context)s, %(value)s, is not in the domain of rxd:CountryAxis. "
                              "Change the value of rxd:Co or add it %(value)s to the Country Axis."),
                            edgarCode="rxd-2344-Country-Value",
                            modelObject=f, context=context.id, value=qnameFacts[rxd.Co].value)
                    # required present facts based on other present fact
                    for qnF, fNilOk, qnG, gNilOk, errCode in ((rxd.A, True, rxd.Cu, False, "EFM.6.23.24"),
                                                              (rxd.A, True, rxd.D, False, "EFM.6.23.25"),
                                                              (rxd.A, False, rxd.Gv, False, "EFM.6.23.28"),
                                                              (rxd.A, False, rxd.Co, False, "EFM.6.23.29"),
                                                              (rxd.Km, False, rxd.K, False, "EFM.6.23.35"),
                                                              (rxd.K, False, rxd.Km, False, "EFM.6.23.35"),
                                                              (rxd.Cm, False, rxd.Cu, False, "EFM.6.23.39"),
                                                              (rxd.K, False, rxd.A, False, "EFM.6.23.42"),
                                                              (rxd.Pr, False, rxd.A, False, "EFM.6.23.43")):
                        if (qnF in qnameFacts and (fNilOk or not qnameFacts[qnF].isNil) and
                            (qnG not in qnameFacts or (not gNilOk and qnameFacts[qnG].isNil))): 
                            modelXbrl.error(errCode,
                                _("The Context %(context)s has a %(fact1)s and is missing required %(fact2NotNil)sfact %(fact2)s"),
                                modelObject=qnameFacts[qnF], context=context.id, fact1=qnF, fact2=qnG, fact2NotNil="" if gNilOk else "non-nil ",
                                messageCodes=("EFM.6.23.24", "EFM.6.23.25", "EFM.6.23.28", "EFM.6.23.29", "EFM.6.23.35",
                                              "EFM.6.23.35", "EFM.6.23.39", "EFM.6.23.42", "EFM.6.23.43"))
                    for f in cntxFacts:
                        if (not context.hasDimension(rxd.PmtAxis) and f.isNumeric and 
                            f.unit is not None and f.unit.measures != currencyMeasures):
                            modelXbrl.error("EFM.6.23.37",
                                _("An %(fact)s fact in context %(context)s has unit %(unit)s not matching the dei:EntityReportingCurrencyISOCode %(currency)s."),
                                edgarCode="rxd-2337-Payment-Unit-Value",
                                modelObject=f, fact=f.qname, context=context.id, unit=f.unit.value, currency=qnCurrencyMeasure)
                    
                    if (rxd.A in qnameFacts and not qnameFacts[rxd.A].isNil and
                        rxd.Cm in qnameFacts and not qnameFacts[rxd.Cm].isNil and
                        qnameFacts[rxd.A].unit is not None and qnameFacts[rxd.A].unit.measures == currencyMeasures): 
                        modelXbrl.error("EFM.6.23.38",
                            _("A value cannot be given for rxd:Cm in context %(context)s because the payment is in the reporting currency %(currency)s."),
                            edgarCode="rxd-2338-Conversion-Method-Value",
                            modelObject=(qnameFacts[rxd.A],qnameFacts[rxd.Cm]), context=context.id, currency=qnCurrencyMeasure)
                    if (rxd.A in qnameFacts and 
                        rxd.Cu in qnameFacts and not qnameFacts[rxd.Cu].isNil and
                        qnameFacts[rxd.A].unit is not None and qnameFacts[rxd.A].unit.measures != ([XbrlConst.qnIsoCurrency(qnameFacts[rxd.Cu].xValue)],[])): 
                        modelXbrl.error("EFM.6.23.41",
                            _("The unit %(unit)s of rxd:A in context %(context)s is not consistent with the value %(currency)s of rxd:Cu.  "
                              "Change one or the other to match."),
                            edgarCode="rxd-2341-Amount-Currency-Existence",
                            modelObject=(qnameFacts[rxd.A],qnameFacts[rxd.Cu]), context=context.id, unit=qnameFacts[rxd.A].unit.value, currency=qnameFacts[rxd.Cu].value)
                                                
                    if (context.hasDimension(rxd.ProjectAxis) and
                        not any(f.xValue == m
                                for m in (contextDims[rxd.ProjectAxis].memberQname,)
                                for f in modelXbrl.factsByQname[rxd.Pr]
                                if f.context is not None)):
                        modelXbrl.error("EFM.6.23.19",
                            _("A payment for each project axis member is required.  Provide a value for element rxd:Pr with value %(dimension)s in context %(context)s."),
                            edgarCode="rxd-2319-Project-Payment-Amount-Existence",
                            modelObject=context, context=context.id, dimension=rxd.GovernmentAxis)
                    if (context.hasDimension(rxd.GovernmentAxis) and
                        not any(f.xValue == m and f.context.hasDimension(rxd.PmtAxis)
                                for m in (contextDims[rxd.GovernmentAxis].memberQname,)
                                for f in modelXbrl.factsByQname[rxd.Gv]
                                if f.context is not None)):
                        modelXbrl.error("EFM.6.23.21",
                            _("A payment amount for each government is required.  Provide a value for element rxd:Gv with value %(member)s."),
                            edgarCode="rxd-2321-Government-Payment-Amount-Existence",
                            modelObject=context, context=context.id, dimension=rxd.GovernmentAxis, member=context.dimMemberQname(rxd.GovernmentAxis))
                    if rxd.P in qnameFacts and not any(f.context is not None and not f.context.hasSegment
                                                       for f in modelXbrl.factsByQname.get(qnameFacts[rxd.P].xValue,())):
                        modelXbrl.error("EFM.6.23.23",
                            _("Payment type %(paymentType)s was reported in context %(context)s but there is no fact with element %(paymentType)s in the Required Context."),
                            edgarCode="rxd-2323-Category-Total-Existence",
                            modelObject=context, context=context.id, paymentType=qnameFacts[rxd.P].xValue)
                    if not context.hasDimension(rxd.PmtAxis) and rxd.A in qnameFacts and not qnameFacts[rxd.A].isNil:
                        modelXbrl.error("EFM.6.23.40",
                            _("There is a fact with element rxd:A in context %(context)s not defining its payment number on axis rxd:PmtAxis."),
                            edgarCode="rxd-2340-Amount-Line-Existence",
                            modelObject=(context, qnameFacts[rxd.A]), context=context.id)
                val.modelXbrl.profileActivity("... SD by context for 19-25, 28-29, 35, 37-39, 40-44", minTimeToShow=1.0)
                for f in modelXbrl.factsByQname[rxd.D]:
                    if not f.isNil and f.xValid >= VALID and f.xValue + datetime.timedelta(1) != f.context.endDatetime: # date needs to be midnite to compare to datetime
                        modelXbrl.error("EFM.6.23.32",
                            _("The value of rxd:D in context %(context)s, %(value)s, is not equal to %(endDate)s.  Change the context end date or the value."),
                            edgarCode="rxd-2332-Date-Value",
                            modelObject=f, value=f.xValue, context=f.context.id, endDate=XmlUtil.dateunionValue(f.context.endDatetime, subtractOneDay=True))
                val.modelXbrl.profileActivity("... SD checks 32 (last SD check)", minTimeToShow=1.0)
                # deference object references no longer needed
                del rxdDoc, cntxEqualFacts
                # dereference compatibly with 2.7 (as these may be used in nested contexts above
                hasHypRelSet = hypDimRelSet = dimDefRelSet = domMemRelSet = dimDomRelSet = None
                memDim.clear()
            else: # non-SD documentType
                pass # no non=SD tests yet
        elif disclosureSystem.GFM:
            for deiItem in (
                    disclosureSystem.deiCurrentFiscalYearEndDateElement, 
                    disclosureSystem.deiDocumentFiscalYearFocusElement, 
                    disclosureSystem.deiFilerNameElement):
                if deiItem not in deiItems or deiItems[deiItem] == "":
                    modelXbrl.error("GFM.3.02.01",
                        _("dei:%(elementName)s was not found in the required context"),
                        modelXbrl=modelXbrl, elementName=deiItem)
        if documentType not in ("SD", "SD/A"):
            val.modelXbrl.profileActivity("... filer required facts checks", minTimeToShow=1.0)

        #6.5.27 footnote elements, etc
        footnoteLinkNbr = 0
        if isInlineXbrl and isEFM:
            _linkEltIter = (linkPrototype
                            for linkKey, links in modelXbrl.baseSets.items()
                            for linkPrototype in links
                            if linkPrototype.modelDocument.type == ModelDocument.Type.INLINEXBRL
                            and linkKey[1] and linkKey[2] and linkKey[3]  # fully specified roles
                            and linkKey[0] != "XBRL-footnotes")
        else: 
            _linkEltIter = xbrlInstDoc.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}footnoteLink")
        for footnoteLinkElt in _linkEltIter:
            if isinstance(footnoteLinkElt, (ModelObject,LinkPrototype)):
                footnoteLinkNbr += 1
                
                linkrole = footnoteLinkElt.get("{http://www.w3.org/1999/xlink}role")
                if linkrole != XbrlConst.defaultLinkRole:
                    modelXbrl.error(("EFM.6.05.28.linkrole", "GFM.1.02.20"),
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
                    if isinstance(child,(ModelObject,LocPrototype,ArcPrototype)):
                        xlinkType = child.get("{http://www.w3.org/1999/xlink}type")
                        if (not isinstance(child,ModelInlineFootnote) and
                            (child.namespaceURI != XbrlConst.link or 
                             xlinkType not in ("locator", "resource", "arc") or
                             child.localName not in ("loc", "footnote", "footnoteArc"))):
                                modelXbrl.error(("EFM.6.05.27", "GFM.1.02.19"),
                                    _("Footnote link %(footnoteLinkNumber)s has a child element %(elementName)s that is not allowed.  Please remove it."),
                                    edgarCode="du-0527-Footnote-Substitution-Group",
                                    modelObject=child, footnoteLinkNumber=footnoteLinkNbr, elementName=child.prefixedName)
                        elif xlinkType == "locator":
                            locNbr += 1
                            locrole = child.get("{http://www.w3.org/1999/xlink}role")
                            if locrole is not None and (disclosureSystem.GFM or \
                                                        not disclosureSystem.uriAuthorityValid(locrole)): 
                                modelXbrl.error(("EFM.6.05.29", "GFM.1.02.21"),
                                    _("Footnote locator %(xlinkLabel)s has a custom role, %(role)s that is not allowed.  Please replace it with the default footnote role."),
                                    edgarCode="du-0529-Footnote-Custom-Loc-Role",
                                    modelObject=child, footnoteLinkNumber=footnoteLinkNbr, 
                                    xlinkLabel=child.xlinkLabel,
                                    locNumber=locNbr, role=locrole)
                            href = child.get("{http://www.w3.org/1999/xlink}href")
                            if not href.startswith("#"): 
                                modelXbrl.error(("EFM.6.05.32", "GFM.1.02.23"),
                                    _("Footnote %(locLabel)s refers to a location, %(locHref)s, that does not begin with '#' so that any change to the file name would render the XBRL invalid."),
                                    edgarCode="du-0532-Footnote-Locator-Portable",
                                    modelObject=child, footnoteLinkNumber=footnoteLinkNbr, locNumber=locNbr, locHref=href,
                                    locLabel=child.get("{http://www.w3.org/1999/xlink}label"))
                            #else:
                            #    label = child.get("{http://www.w3.org/1999/xlink}label")
                        elif xlinkType == "arc":
                            arcNbr += 1
                            arcrole = child.get("{http://www.w3.org/1999/xlink}arcrole")
                            if (isEFM and not disclosureSystem.uriAuthorityValid(arcrole)) or \
                               (disclosureSystem.GFM  and arcrole != XbrlConst.factFootnote and arcrole != XbrlConst.factExplanatoryFact): 
                                modelXbrl.error(("EFM.6.05.30", "GFM.1.02.22"),
                                    _("Footnote relationship %(arcToLabel)s has a custom arc role %(arcrole)s that is not allowed.  "
                                      "Please replace it with the default (fact-footnote) arcrole."),
                                    edgarCode="du-0530-Footnote-Custom-Arcrole",
                                    modelObject=child, footnoteLinkNumber=footnoteLinkNbr, arcNumber=arcNbr, 
                                    arcToLabel=child.get("{http://www.w3.org/1999/xlink}to"),
                                    arcrole=arcrole)
                        elif xlinkType == "resource" or isinstance(child,ModelInlineFootnote): # footnote
                            footnoterole = child.role if isinstance(child,ModelInlineFootnote) else child.get("{http://www.w3.org/1999/xlink}role")
                            if footnoterole == "":
                                modelXbrl.error(("EFM.6.05.28.missingRole", "GFM.1.2.20"),
                                    _("Footnote %(xlinkLabel)s is missing a role. Please provide the default footnote role."),
                                    edgarCode="du-0528-Footnote-Custom-Footnote-Role",
                                    modelObject=child, xlinkLabel=getattr(child, "xlinkLabel", None))
                            elif (isEFM and not disclosureSystem.uriAuthorityValid(footnoterole)) or \
                                 (disclosureSystem.GFM  and footnoterole != XbrlConst.footnote): 
                                modelXbrl.error(("EFM.6.05.28", "GFM.1.2.20"),
                                    _("Footnote %(xlinkLabel)s has a role %(role)s that is not allowed. "
                                      "Please replace it with the default footnote role."),
                                    edgarCode="du-0528-Footnote-Custom-Footnote-Role",
                                    modelObject=child, xlinkLabel=getattr(child, "xlinkLabel", None),
                                    role=footnoterole)
                            if isEFM and not isInlineXbrl: # inline content was validated before and needs continuations assembly
                                ValidateFilingText.validateFootnote(modelXbrl, child)
                            # find modelResource for this element
                            foundFact = False
                            if XmlUtil.text(child) != "" and not isInlineXbrl:
                                if relationshipSet:
                                    for relationship in relationshipSet.toModelObject(child):
                                        if isinstance(relationship.fromModelObject, ModelFact):
                                            foundFact = True
                                            break
                                if not foundFact:
                                    modelXbrl.error(("EFM.6.05.33", "GFM.1.02.24"),
                                        _("The footnote with label %(footnoteLabel)s and text '%(text)s' is not connected to any fact.  "
                                          "Please remove the footnote, or link it to a fact."),
                                        edgarCode="cp-0533-Dangling-Footnote",
                                        modelObject=child, footnoteLinkNumber=footnoteLinkNbr, 
                                        footnoteLabel=getattr(child, "xlinkLabel", None),
                                        text=XmlUtil.text(child)[:100])
        val.modelXbrl.profileActivity("... filer rfootnotes checks", minTimeToShow=1.0)

    # entry point schema checks
    elif modelXbrl.modelDocument.type == ModelDocument.Type.SCHEMA:
        pass
    
    # inline-only checks
    if modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL and isEFM:
        elt = modelXbrl.modelDocument.xmlRootElement
        if elt.tag in ("html", "xhtml") or (isinstance(elt, ModelObject) and not elt.namespaceURI):
            modelXbrl.error("EFM.5.02.05.xhtmlNamespaceMissing",
                _("InlineXBRL root element <%(element)s> MUST be html and have the xhtml namespace."),
                modelObject=elt, element=elt.tag)
        nsRequiredPrefixes = {"http://www.w3.org/1999/xhtml": "xhtml",
                              "http://www.xbrl.org/2013/inlineXBRL": "ix",
                              "http://www.xbrl.org/inlineXBRL/transformation/2015-02-26": "ixt",
                              "http://www.sec.gov/inlineXBRL/transformation/2015-08-31": "ixt-sec"}
        for prefix, ns in ((None, "http://www.w3.org/1999/xhtml"),
                           ("ix", "http://www.xbrl.org/2013/inlineXBRL"),
                           ("ixt", "http://www.xbrl.org/inlineXBRL/transformation/2015-02-26"),
                           ("ixt-sec", "http://www.sec.gov/inlineXBRL/transformation/2015-08-31")):
            for _prefix, _ns in elt.nsmap.items():
                if _ns == ns and _prefix != prefix:
                    modelXbrl.error("EFM.5.02.05.standardNamespacePrefix",
                        _("The prefix %(submittedPrefix)s must be replaced by %(recommendedPrefix)s for standard namespace %(namespace)s."),
                        edgarCode="ix-0502-Standard-Namespace-Prefix",
                        modelObject=elt, submittedPrefix=_prefix, recommendedPrefix=prefix, namespace=ns)
        ixNStag = modelXbrl.modelDocument.ixNStag
        ixTags = set(ixNStag + ln for ln in ("nonNumeric", "nonFraction", "references", "relationship"))
        for tag in ixTags:
            for ixElt in modelXbrl.modelDocument.xmlRootElement.iterdescendants(tag=tag):
                if isinstance(ixElt,ModelObject):
                    if ixElt.get("target"):
                        modelXbrl.error("EFM.5.02.05.targetDisallowed",
                            _("Inline element %(localName)s has disallowed target attribute %(target)s."),
                            modelObject=ixElt, localName=ixElt.elementQname, target=ixElt.get("target"))
        for ixElt in modelXbrl.modelDocument.xmlRootElement.iterdescendants(tag=ixNStag+"tuple"):
            if isinstance(ixElt,ModelObject):
                modelXbrl.error("EFM.5.02.05.tupleDisallowed",
                    _("Inline tuple %(qname)s is disallowed."),
                    modelObject=ixElt, qname=ixElt.qname)
        for ixElt in modelXbrl.modelDocument.xmlRootElement.iterdescendants(tag=ixNStag+"fraction"):
            if isinstance(ixElt,ModelObject):
                modelXbrl.error("EFM.5.02.05.fractionDisallowed",
                    _("Inline fraction %(qname)s is disallowed."),
                    modelObject=ixElt, qname=ixElt.qname)
        if modelXbrl.modelDocument.xmlDocument.docinfo.doctype:
            modelXbrl.error("EFM.5.02.05.doctypeDisallowed",
                _("Inline HTML %(doctype)s is disallowed."),
                modelObject=ixElt, doctype=modelXbrl.modelDocument.xmlDocument.docinfo.doctype)

        # hidden references
        untransformableTypes = {"anyURI", "base64Binary", "hexBinary", "NOTATION", "QName", "time",
                                "token", "language"}
        hiddenEltIds = {}
        presentedHiddenEltIds = defaultdict(list)
        eligibleForTransformHiddenFacts = []
        requiredToDisplayFacts = []
        requiredToDisplayFactIds = {}
        for ixHiddenElt in modelXbrl.modelDocument.xmlRootElement.iterdescendants(tag=ixNStag + "hidden"):
            for tag in (ixNStag + "nonNumeric", ixNStag+"nonFraction"):
                for ixElt in ixHiddenElt.iterdescendants(tag=tag):
                    if (getattr(ixElt, "xValid", 0) >= VALID and # may not be validated
                        not ixElt.qname.namespaceURI.startswith("http://xbrl.sec.gov/dei/")):
                        if (ixElt.concept.baseXsdType not in untransformableTypes and
                            not ixElt.isNil):
                            eligibleForTransformHiddenFacts.append(ixElt)
                        elif ixElt.id is None:
                            requiredToDisplayFacts.append(ixElt)
                    if ixElt.id:
                        hiddenEltIds[ixElt.id] = ixElt
        if eligibleForTransformHiddenFacts:
            modelXbrl.warning("EFM.5.02.05.14.hidden-fact-eligible-for-transform",
                _("%(countEligible)s fact(s) appearing in ix:hidden were eligible for transformation: %(elements)s"),
                edgarCode="ix-0514-Hidden-Fact-Eligible-For-Transform",
                modelObject=eligibleForTransformHiddenFacts, 
                countEligible=len(eligibleForTransformHiddenFacts),
                elements=", ".join(sorted(set(str(f.qname) for f in eligibleForTransformHiddenFacts))))
        for ixElt in modelXbrl.modelDocument.xmlDocument.iterfind("//{http://www.w3.org/1999/xhtml}*[@style]"):
            hiddenFactRefMatch = styleIxHiddenPattern.match(ixElt.get("style",""))
            if hiddenFactRefMatch:
                hiddenFactRef = hiddenFactRefMatch.group(2)
                if hiddenFactRef not in hiddenEltIds:
                    modelXbrl.error("EFM.5.02.05.14.hidden-fact-not-found",
                        _("The value of the -sec-ix-hidden style property, %(id)s, does not correspond to the id of any hidden fact."),
                        edgarCode="ix-0514-Hidden-Fact-Not-Found",
                        modelObject=ixElt, id=hiddenFactRef)
                else:
                    presentedHiddenEltIds[hiddenFactRef].append(ixElt)
        for hiddenFactRef, ixElts in presentedHiddenEltIds.items():
            if len(ixElts) > 1 and hiddenFactRef in hiddenEltIds:
                fact = hiddenEltIds[hiddenFactRef]
                modelXbrl.warning("EFM.5.02.05.14.hidden-fact-multiple-references",
                    _("Fact %(element)s, id %(id)s, is referenced from %(countReferences)s elements."),
                    edgarCode="ix-0514-Hidden-Fact-Multiple-References",
                    modelObject=ixElts + [fact], id=hiddenFactRef, element=fact.qname, countReferences=len(ixElts))
        for hiddenEltId, ixElt in hiddenEltIds.items():
            if (hiddenEltId not in presentedHiddenEltIds and
                getattr(ixElt, "xValid", 0) >= VALID and # may not be validated
                not ixElt.qname.namespaceURI.startswith("http://xbrl.sec.gov/dei/") and
                (ixElt.concept.baseXsdType in untransformableTypes or ixElt.isNil)):
                requiredToDisplayFacts.append(ixElt)
        if requiredToDisplayFacts:
            modelXbrl.warning("EFM.5.02.05.14.hidden-fact-not-referenced",
                _("%(countUnreferenced)s fact(s) appearing in ix:hidden were not referenced by any -sec-ix-hidden style property: %(elements)s"),
                edgarCode="ix-0514-Hidden-Fact-Not-Referenced",
                modelObject=requiredToDisplayFacts, 
                countUnreferenced=len(requiredToDisplayFacts),
                elements=", ".join(sorted(set(str(f.qname) for f in requiredToDisplayFacts))))
        del eligibleForTransformHiddenFacts, hiddenEltIds, presentedHiddenEltIds, requiredToDisplayFacts
    # all-labels and references checks
    defaultLangStandardLabels = {}
    for concept in modelXbrl.qnameConcepts.values():
        # conceptHasDefaultLangStandardLabel = False
        for modelLabelRel in labelsRelationshipSet.fromModelObject(concept):
            if modelLabelRel.modelDocument.inDTS: # ignore documentation labels added by EdgarRenderer not in DTS
                modelLabel = modelLabelRel.toModelObject
                role = modelLabel.role
                text = modelLabel.text
                lang = modelLabel.xmlLang
                if role == XbrlConst.documentationLabel:
                    if concept.modelDocument.targetNamespace in disclosureSystem.standardTaxonomiesDict:
                        modelXbrl.error(("EFM.6.10.05", "GFM.1.05.05"),
                            _("Your filing attempted to add a new definition, '%(text)s', to an existing concept in the standard taxonomy, %(concept)s.  Please remove this definition."),
                            edgarCode="cp-1005-Custom-Documentation-Standard-Element",
                            modelObject=modelLabel, concept=concept.qname, text=text)
                elif text and lang and disclosureSystem.defaultXmlLang and lang.startswith(disclosureSystem.defaultXmlLang):
                    if role == XbrlConst.standardLabel:
                        if text in defaultLangStandardLabels:
                            concept2, modelLabel2 = defaultLangStandardLabels[text]
                            modelXbrl.error(("EFM.6.10.04", "GFM.1.05.04"),
                                _("More than one element has %(text)s as its English standard label (%(concept)s and %(concept2)s).  "
                                  "Please change or remove all but one label."),
                                edgarCode="du-1004-English-Standard-Labels-Duplicated",
                                modelObject=(concept, modelLabel, concept2, modelLabel2), 
                                concept=concept.qname, 
                                concept2=concept2.qname, 
                                lang=disclosureSystem.defaultLanguage, text=text[:80])
                        else:
                            defaultLangStandardLabels[text] = (concept, modelLabel)
                        # conceptHasDefaultLangStandardLabel = True
                    if len(text) > 511:
                        modelXbrl.error(("EFM.6.10.06", "GFM.1.05.06"),
                            _("Element %(concept)s, label length %(length)s, has more than 511 characters or contains a left-angle-bracket character in the label for role %(role)s. "
                              "Please correct the label."),
                            edgarCode="rq-1006-Label-Disallowed",
                            modelObject=modelLabel, concept=concept.qname, role=role, length=len(text), text=text[:80])
                    match = modelXbrl.modelManager.disclosureSystem.labelCheckPattern.search(text)
                    if match:
                        modelXbrl.error(("EFM.6.10.06", "GFM.1.05.07"),
                            'Label for concept %(concept)s role %(role)s has disallowed characters: "%(text)s"',
                            modelObject=modelLabel, concept=concept.qname, role=role, text=match.group())
                if (text is not None and len(text) > 0 and 
                    modelXbrl.modelManager.disclosureSystem.labelTrimPattern and
                   (modelXbrl.modelManager.disclosureSystem.labelTrimPattern.match(text[0]) or \
                    modelXbrl.modelManager.disclosureSystem.labelTrimPattern.match(text[-1]))):
                    modelXbrl.error(("EFM.6.10.08", "GFM.1.05.08"),
                        _("The label %(text)s of element %(concept)s has leading or trailing white space in role %(role)s for lang %(lang)s.  Please remove it."),
                        edgarCode="du-1008-Label-Not-Trimmed",
                        modelObject=modelLabel, concept=concept.qname, role=role, lang=lang, text=text)
        for modelRefRel in referencesRelationshipSetWithProhibits.fromModelObject(concept):
            if modelRefRel.modelDocument.inDTS: # ignore references added by EdgarRenderer that are not in DTS
                modelReference = modelRefRel.toModelObject
                text = XmlUtil.innerText(modelReference)
                #6.18.1 no reference to company extension concepts
                if concept.modelDocument.targetNamespace not in disclosureSystem.standardTaxonomiesDict:
                    modelXbrl.error(("EFM.6.18.01", "GFM.1.9.1"),
                        _("Your filing provides a reference, '%(xml)s', for an custom concept in extension taxonomy, %(concept)s.  "
                          "Please remove this reference."),
                        edgarCode="cp-1801-Custom-Element-Has-Reference",
                        modelObject=modelReference, concept=concept.qname, text=text, xml=XmlUtil.xmlstring(modelReference, stripXmlns=True, contentsOnly=True))
                elif isEFM and not isStandardUri(val, modelRefRel.modelDocument.uri): 
                    #6.18.2 no extension to add or remove references to standard concepts
                    modelXbrl.error(("EFM.6.18.02"),
                        _("Your filing attempted to add a new reference, '%(xml)s', to an existing concept in the standard taxonomy, %(concept)s.  "
                          "Please remove this reference."),
                        edgarCode="cp-1802-Standard-Element-Has-Reference",
                        modelObject=modelReference, concept=concept.qname, text=text, xml=XmlUtil.xmlstring(modelReference, stripXmlns=True, contentsOnly=True))

    # role types checks
    # 6.7.10 only one role type declaration in DTS
    for roleURI, modelRoleTypes in modelXbrl.roleTypes.items():
        countInDTS = sum(1 for m in modelRoleTypes if m.modelDocument.inDTS)
        if countInDTS > 1:
            modelXbrl.error(("EFM.6.07.10", "GFM.1.03.10"),
                _("Role %(roleType)s was declared more than once (%(numberOfDeclarations)s times.).  "
                  "Please remove all but one declaration."),
                edgarCode="du-0710-Role-Type-Duplicates",
                modelObject=modelRoleTypes, roleType=roleURI, numberOfDeclarations=countInDTS)
    # 6.7.14 only one arcrole type declaration in DTS
    for arcroleURI, modelRoleTypes in modelXbrl.arcroleTypes.items():
        countInDTS = sum(1 for m in modelRoleTypes if m.modelDocument.inDTS)
        if countInDTS > 1:
            modelXbrl.error(("EFM.6.07.14", "GFM.1.03.16"),
                _("Relationship arc role %(arcroleType)s is declared more than once (%(numberOfDeclarations)s duplicates).  "
                  "Please remove all but one of them."),
                edgarCode="du-0714-Arcrole-Type-Duplicates",
                modelObject=modelRoleTypes, arcroleType=arcroleURI, numberOfDeclarations=countInDTS )
                

    val.modelXbrl.profileActivity("... filer concepts checks", minTimeToShow=1.0)

    del defaultLangStandardLabels #dereference
    
    # checks on all documents: instance, schema, instance
    val.hasExtensionSchema = False
    checkFilingDTS(val, modelXbrl.modelDocument, isEFM, isGFM, [])
    val.modelXbrl.profileActivity("... filer DTS checks", minTimeToShow=1.0)

    # checks for namespace clashes
    if isEFM:
        # check number of us-roles taxonomies referenced
        for conflictClass, modelDocuments in val.standardNamespaceConflicts.items():                                                                
            if (len(modelDocuments) > 1 and 
                (conflictClass != 'srt+us-gaap' or ('us-types' in val.standardNamespaceConflicts and
                                                    'srt-types' in val.standardNamespaceConflicts)) and # ignore multi us-gaap/srt conflicts without the other
                (conflictClass != 'ifrs+us-gaap' or ('us-types' in val.standardNamespaceConflicts and
                                                     'ifrs-full' in val.standardNamespaceConflicts)) # ignore multi us-gaap/ifrs conflicts without the other
                ):
                if conflictClass == 'ifrs+us-gaap':
                    if set(d.targetNamespace for d in val.standardNamespaceConflicts['ifrs+us-gaap']) >= {
                        "http://xbrl.ifrs.org/taxonomy/2018-03-16/ifrs-full", "http://fasb.org/us-gaap/2017-01-31"}:
                        conflictClass = 'ifrs-2018+us-gaap-2017'
                    else:
                        continue
                modelXbrl.error("EFM.6.22.03.incompatibleSchemas",
                    _("References for conflicting standard taxonomies %(conflictClass)s are not allowed in same DTS %(namespaceConflicts)s"),
                    edgarCode="cp-2203-Incompatible-Taxonomy-Versions",
                    modelObject=modelXbrl, conflictClass=conflictClass,
                    namespaceConflicts=", ".join(sorted([conflictClassFromNamespace(d.targetNamespace) for d in modelDocuments])))
        if 'rr' in val.standardNamespaceConflicts and documentType not in {"485BPOS", "497"}:
            modelXbrl.error("EFM.6.22.03.incompatibleTaxonomyDocumentType",
                _("Taxonomy class %(conflictClass)s may not be used with document type %(documentType)s"),
                modelObject=modelXbrl, conflictClass="RR", documentType=documentType)
        if 'ifrs-full' in val.standardNamespaceConflicts and documentType in {"485BPOS", "497", "K SDR", "L SDR",
                                                                              "N-CSR", "N-CSR/A", "N-CSRS", "N-CSRS/A", "N-Q", "N-Q/A"}:
            modelXbrl.error("EFM.6.22.03.incompatibleTaxonomyDocumentType",
                _("Taxonomy class %(conflictClass)s may not be used with document type %(documentType)s"),
                modelObject=modelXbrl, conflictClass="IFRS", documentType=documentType)
        if 'ifrs-full' in val.standardNamespaceConflicts:
            ifrsNS = next(iter(val.standardNamespaceConflicts['ifrs-full'])).targetNamespace
            srtNS = None
            for ns in modelXbrl.namespaceDocs:
                if "fasb.org/srt/" in ns:
                    srtNS = ns
                    break
            ifrsSrtConceptQNs = set(qname(ifrsNS, ifrsConceptName) for ifrsConceptName in ifrsSrtConcepts.keys())
            ifrsSrtConceptsUsed = set(c.qname for c in conceptsUsed if c.qname in ifrsSrtConceptQNs)
            if ifrsSrtConceptsUsed and srtNS:
                ifrsSrtObjs = set(f for f in modelXbrl.facts if f.qname in ifrsSrtConceptsUsed
                                  ) | set(c for c in modelXbrl.contexts.values() if _DICT_SET(c.qnameDims.keys()) & ifrsSrtConceptsUsed)
                modelXbrl.warning("EFM.6.05.40.srtConceptsForIFRSConcepts",
                    _("Taxonomy concepts from the SRT taxonomy should be used for the following IFRS concepts: %(ifrsSrtConceptsUsed)s"),
                    edgarCode="cp-0540-SRT-Concepts-For-IFRS-Concepts",
                    modelObject=ifrsSrtObjs, ifrsSrtConceptsUsed=", ".join(str(qn) for qn in sorted(ifrsSrtConceptsUsed)))
            srtAxesIfrsMemberQNs = {}
            for srtAxisName, ifrsMems in srtAxisIfrsMembers.items():
                srtAxisQn = qname(srtNS, srtAxisName)
                srtAxisConcept = modelXbrl.qnameConcepts.get(srtAxisQn)
                if srtAxisConcept in conceptsUsed:
                    srtAxesIfrsMemberQNs[srtAxisQn] = set(qname(ifrsNS, ifrsMem) for ifrsMem in ifrsMems)
            if srtAxesIfrsMemberQNs:
                ifrsSrtMembersUsed = set(dim.memberQname 
                                         for c in modelXbrl.contexts.values()
                                         for dim in c.qnameDims.values()
                                         if dim.dimensionQname in srtAxesIfrsMemberQNs and dim.memberQname in srtAxesIfrsMemberQNs[dim.dimensionQname])
                if ifrsSrtMembersUsed:
                    ifrsSrtObjs = set(c for c in modelXbrl.contexts.values() for dim in c.qnameDims.values()
                                      if dim.dimensionQname in srtAxesIfrsMemberQNs and dim.memberQname in srtAxesIfrsMemberQNs[dim.dimensionQname])
                    modelXbrl.warning("EFM.6.05.40.srtMembersForSRTAxes",
                        _("Taxonomy axes from the SRT taxonomy should use SRT or extension members for the following IFRS member concepts: %(ifrsSrtConceptsUsed)s."),
                        edgarCode="cp-0540-SRT-Members-For-SRT-Axes",
                        modelObject=ifrsSrtObjs, ifrsSrtConceptsUsed=", ".join(str(qn) for qn in sorted(ifrsSrtMembersUsed)))
        if isInlineXbrl and documentType in {
            "485BPOS", "497", "K SDR", "L SDR",
            "S-1", "S-1/A", "S-1MEF", "S-3", "S-3/A", "S-3ASR", "S-3D", "S-3DPOS", "S-3MEF", "S-4", "S-4/A", "S-4EF", 
            "S-4MEF", "S-4 POS", "S-11", "S-11/A", "S-11MEF", "F-1", "F-1/A", "F-1MEF", "F-3", "F-3/A", "F-3ASR", 
            "F-3D", "F-3DPOS", "F-3MEF", "F-4", "F-4/A", "F-4EF", "F-4MEF", "F-4 POS", "F-10", "F-10/A", "F-10EF", 
            "F-10POS", "N-Q", "N-Q/A", "N-CSR", "N-CSR/A", "N-CSRS", "N-CSRS/A"}:
            modelXbrl.error("EFM.6.22.03.incompatibleInlineDocumentType",
                _("Inline XBRL may not be used with document type %(documentType)s"),
                modelObject=modelXbrl, conflictClass="inline XBRL", documentType=documentType)
        if documentType is not None and not val.hasExtensionSchema and documentType != "L SDR":
            modelXbrl.error("EFM.6.03.10",
                            _("%(documentType)s report is missing a extension schema file."),
                            modelObject=modelXbrl, documentType=documentType)
            
        
    conceptRelsUsedWithPreferredLabels = defaultdict(list)
    usedCalcsPresented = defaultdict(set) # pairs of concepts objectIds used in calc
    usedCalcFromTosELR = {}
    localPreferredLabels = defaultdict(set)
    drsELRs = set()
    
    # do calculation, then presentation, then other arcroles
    val.summationItemRelsSetAllELRs = modelXbrl.relationshipSet(XbrlConst.summationItem)
    for arcroleFilter in (XbrlConst.summationItem, XbrlConst.parentChild, "*"):
        for baseSetKey, baseSetModelLinks  in modelXbrl.baseSets.items():
            arcrole, ELR, linkqname, arcqname = baseSetKey
            if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-"):
                # assure summationItem, then parentChild, then others
                if not (arcroleFilter == arcrole or
                        arcroleFilter == "*" and arcrole not in (XbrlConst.summationItem, XbrlConst.parentChild)):
                    continue
                ineffectiveArcs = ModelRelationshipSet.ineffectiveArcs(baseSetModelLinks, arcrole)
                #validate ineffective arcs
                for modelRel in ineffectiveArcs:
                    if isinstance(modelRel.fromModelObject, ModelObject) and isinstance(modelRel.toModelObject, ModelObject):
                        modelXbrl.error(("EFM.6.09.03", "GFM.1.04.03"),
                            _("The %(arcrole)s relationship from %(conceptFrom)s to %(conceptTo)s, link role %(linkroleDefinition)s, in the submission is ineffectual.  Please remove or correct the relationship."),
                            edgarCode="du-0903-Relationship-Ineffectual",
                            modelObject=modelRel, arc=modelRel.qname, arcrole=modelRel.arcrole,
                            linkrole=modelRel.linkrole, linkroleDefinition=modelXbrl.roleTypeDefinition(modelRel.linkrole), 
                            conceptFrom=modelRel.fromModelObject.qname, conceptTo=modelRel.toModelObject.qname, 
                            ineffectivity=modelRel.ineffectivity)
                if arcrole == XbrlConst.parentChild:
                    isStatementSheet = any(linkroleDefinitionStatementSheet.match(roleType.definition or '')
                                           for roleType in val.modelXbrl.roleTypes.get(ELR,()))
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
                                    conceptRelsUsedWithPreferredLabels[relTo].append(rel)
                                # 6.12.5 distinct preferred labels in base set
                                preferredLabels = targetConceptPreferredLabels[relTo]
                                if preferredLabel in preferredLabels:
                                    if preferredLabel in preferredLabels:
                                        rel2, relTo2 = preferredLabels[preferredLabel]
                                    else:
                                        rel2 = relTo2 = None
                                    modelXbrl.error(("EFM.6.12.05", "GFM.1.06.05"),
                                        _("Relationships from %(fromConcept)s to %(concept)s in role %(linkroleDefinition)s do not have distinct values for "
                                          "the preferredLabel attribute, %(preferredLabel)s.  Change all but one value of preferredLabel."),
                                        edgarCode="rq-1205-Preferred-Label-Duplicates",
                                        modelObject=(rel, relTo, rel2, relTo2), 
                                        concept=relTo.qname, fromConcept=rel.fromModelObject.qname,
                                        preferredLabel=preferredLabel, linkrole=rel.linkrole, linkroleDefinition=modelXbrl.roleTypeDefinition(rel.linkrole))
                                else:
                                    preferredLabels[preferredLabel] = (rel, relTo)
                                if relFromUsed:
                                    # 6.14.5
                                    conceptsPresented.add(relFrom.objectIndex)
                                    conceptsPresented.add(relTo.objectIndex)
                            order = rel.order
                            if order in orderRels:
                                modelXbrl.error(("EFM.6.12.02", "GFM.1.06.02"),
                                    _("More than one presentation relationship in role %(linkroleDefinition)s has order value %(order)s, from concept %(conceptFrom)s.  "
                                      "Change all but one so they are distinct."),
                                    edgarCode="rq-1202-Presentation-Order-Duplicates",
                                    modelObject=(rel, orderRels[order]), conceptFrom=relFrom.qname, order=rel.arcElement.get("order"), linkrole=rel.linkrole, 
                                    linkroleDefinition=modelXbrl.roleTypeDefinition(rel.linkrole), linkroleName=modelXbrl.roleTypeName(rel.linkrole),
                                    conceptTo=relTo.qname, conceptTo2=orderRels[order].toModelObject.qname)
                            else:
                                orderRels[order] = rel
                            if isinstance(relTo, ModelConcept):
                                if relTo.periodType == "duration" and instantPreferredLabelRolePattern.match(preferredLabel or ""): 
                                    modelXbrl.warning("EFM.6.12.07",
                                        _("In \"%(linkrole)s\", element %(conceptTo)s has period type 'duration' but is given a preferred label %(preferredLabel)s "
                                          "when shown under parent %(conceptFrom)s.  The preferred label will be ignored."),
                                        modelObject=(rel, relTo), conceptTo=relTo.qname, conceptFrom=relFrom.qname, order=rel.arcElement.get("order"), linkrole=rel.linkrole, linkroleDefinition=modelXbrl.roleTypeDefinition(rel.linkrole),
                                        linkroleName=modelXbrl.roleTypeName(rel.linkrole),
                                        conceptTo2=orderRels[order].toModelObject.qname, 
                                        preferredLabel=preferredLabel, preferredLabelValue=preferredLabel.rpartition("/")[2])
                                if (relTo.isExplicitDimension and not any(
                                    isinstance(_rel.toModelObject, ModelConcept) and _rel.toModelObject.type is not None and _rel.toModelObject.type.isDomainItemType
                                    for _rel in parentChildRels.fromModelObject(relTo))):
                                        modelXbrl.warning("EFM.6.12.08",
                                            _("In \"%(linkrole)s\" axis %(axis)s has no domain element children, which effectively filters out every fact."),
                                            modelObject=relFrom, axis=relFrom.qname, 
                                            linkrole=ELR, linkroleDefinition=modelXbrl.roleTypeDefinition(ELR), linkroleName=modelXbrl.roleTypeName(ELR))
                                if (relFrom.isExplicitDimension and not any(
                                    isinstance(_rel.toModelObject, ModelConcept) and _rel.toModelObject.type is not None and _rel.toModelObject.type.isDomainItemType
                                    for _rel in siblingRels)):
                                        modelXbrl.warning("EFM.6.12.08",
                                            _("In \"%(linkrole)s\" axis %(axis)s has no domain element children, which effectively filters out every fact."),
                                            modelObject=relFrom, axis=relFrom.qname, 
                                            linkrole=ELR, linkroleDefinition=modelXbrl.roleTypeDefinition(ELR), linkroleName=modelXbrl.roleTypeName(ELR))
                        targetConceptPreferredLabels.clear()
                        orderRels.clear()
                    localPreferredLabels.clear() # clear for next relationship
                    for conceptPresented in conceptsPresented:
                        if conceptPresented in usedCalcsPresented:
                            usedCalcPairingsOfConcept = usedCalcsPresented[conceptPresented]
                            if len(usedCalcPairingsOfConcept & conceptsPresented) > 0:
                                usedCalcPairingsOfConcept -= conceptsPresented
                    # 6.15.02, 6.15.03 semantics checks for totals and calc arcs (by tree walk)
                    if validateLoggingSemantic:
                        for rootConcept in parentChildRels.rootConcepts:
                            checkCalcsTreeWalk(val, parentChildRels, rootConcept, isStatementSheet, False, conceptsUsed, set())
                    # 6.12.6 
                    if len(parentChildRels.rootConcepts) > 1:
                        val.modelXbrl.warning("EFM.6.12.06",
                            _("Presentation relationship set role %(linkrole)s has multiple (%(numberRootConcepts)s) root nodes.  "
                              "XBRL allows unordered root nodes, but rendering requires ordering.  They will instead be ordered by their labels.  "
                              "To avoid undesirable ordering of axes and primary items across multiple root nodes, rearrange the presentation relationships to have only a single root node."),
                            modelObject=(rel,parentChildRels.rootConcepts), linkrole=ELR, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR),
                            linkroleName=val.modelXbrl.roleTypeName(ELR),
                            numberRootConcepts=len(parentChildRels.rootConcepts))
                elif arcrole == XbrlConst.summationItem:
                    # 6.14.3 check for relation concept periods
                    fromRelationships = modelXbrl.relationshipSet(arcrole,ELR).fromModelObjects()
                    # allElrRelSet = modelXbrl.relationshipSet(arcrole)
                    for relFrom, rels in fromRelationships.items():
                        orderRels = {}
                        for rel in rels:
                            relTo = rel.toModelObject
                            # 6.14.03 must have matched period types across relationshp
                            if isinstance(relTo, ModelConcept) and relFrom.periodType != relTo.periodType:
                                val.modelXbrl.error(("EFM.6.14.03", "GFM.1.07.03"),
                                    "Element %(conceptFrom)s and element %(conceptTo)s have different period types, but there is a calculation relationship between them in role %(linkroleDefinition)s. "
                                    "Please recheck submission calculation links.",
                                    edgarCode="fs-1403-Calculation-Relationship-Has-Different-Period-Types",
                                    modelObject=rel, linkrole=rel.linkrole, conceptFrom=relFrom.qname, conceptTo=relTo.qname, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR))
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
                                val.modelXbrl.error(("EFM.N/A", "GFM.1.07.06"),
                                    _("Duplicate calculations relations from concept %(conceptFrom)s for order %(order)s in base set role %(linkrole)s to concept %(conceptTo)s and to concept %(conceptTo2)s"),
                                    modelObject=(rel, orderRels[order]), linkrole=rel.linkrole, conceptFrom=relFrom.qname, order=order,
                                    conceptTo=rel.toModelObject.qname, conceptTo2=orderRels[order].toModelObject.qname)
                            else:
                                orderRels[order] = rel
                        directedCycleRels = directedCycle(val, relFrom,relFrom,fromRelationships,{relFrom})
                        if directedCycleRels is not None:
                            val.modelXbrl.error(("EFM.6.14.04", "GFM.1.07.04"),
                                _("Element %(concept)s is summed into itself in calculation group %(linkroleDefinition)s.  Please recheck submission."),
                                edgarCode="fs-1404-Circular-Calculation",
                                modelObject=[relFrom] + directedCycleRels, linkrole=ELR, concept=relFrom.qname, linkroleDefinition=val.modelXbrl.roleTypeDefinition(ELR))
                        orderRels.clear()
                        # if relFrom used by fact and multiple calc networks from relFrom, test 6.15.04
                        if rels and relFrom in conceptsUsed:
                            relFromAndTos = (relFrom.objectIndex,) + tuple(sorted((rel.toModelObject.objectIndex 
                                                                                   for rel in rels if isinstance(rel.toModelObject, ModelConcept))))
                            if relFromAndTos in usedCalcFromTosELR:
                                otherRels = usedCalcFromTosELR[relFromAndTos]
                                otherELR = otherRels[0].linkrole
                                val.modelXbrl.log("WARNING-SEMANTIC", ("EFM.6.15.04", "GFM.2.06.04"),
                                    _("Calculation relationships should have a same set of targets in %(linkrole)s and %(linkrole2)s starting from %(concept)s"),
                                    modelObject=[relFrom] + rels + otherRels, linkrole=ELR, linkrole2=otherELR, concept=relFrom.qname)
                            else:
                                usedCalcFromTosELR[relFromAndTos] = rels
                                                            
                elif arcrole == XbrlConst.all or arcrole == XbrlConst.notAll:
                    drsELRs.add(ELR)
                    
                elif arcrole == XbrlConst.dimensionDomain or arcrole == XbrlConst.dimensionDefault:
                    # 6.16.3 check domain targets in extension linkbases are domain items
                    fromRelationships = modelXbrl.relationshipSet(arcrole,ELR).fromModelObjects()
                    for relFrom, rels in fromRelationships.items():
                        for rel in rels:
                            relTo = rel.toModelObject

                            if not (isinstance(relTo, ModelConcept) and relTo.type is not None and relTo.type.isDomainItemType) and not isStandardUri(val, rel.modelDocument.uri):
                                val.modelXbrl.error(("EFM.6.16.03", "GFM.1.08.03"),
                                    _("There is a dimension-domain relationship from %(conceptFrom)s but its target element %(conceptTo)s is not a domain.  "
                                      "Please change the relationship or change the type of the target element."),
                                    edgarCode="du-1603-Dimension-Domain-Target-Mismatch",
                                    modelObject=(rel, relFrom, relTo), conceptFrom=relFrom.qname, conceptTo=(relTo.qname if relTo is not None else None), linkrole=rel.linkrole)

                       
                # definition tests (GFM only, for now)
                if XbrlConst.isDefinitionOrXdtArcrole(arcrole) and disclosureSystem.GFM: 
                    fromRelationships = modelXbrl.relationshipSet(arcrole,ELR).fromModelObjects()
                    for relFrom, rels in fromRelationships.items():
                        orderRels = {}
                        for rel in rels:
                            relTo = rel.toModelObject
                            order = rel.order
                            if order in orderRels and disclosureSystem.GFM:
                                val.modelXbrl.error("GFM.1.08.10",
                                    _("Duplicate definitions relations from concept %(conceptFrom)s for order %(order)s in base set role %(linkrole)s "
                                      "to concept %(conceptTo)s and to concept %(conceptTo2)s"),
                                    modelObject=(rel, relFrom, relTo), conceptFrom=relFrom.qname, order=order, linkrole=rel.linkrole, 
                                    conceptTo=rel.toModelObject.qname, conceptTo2=orderRels[order].toModelObject.qname)
                            else:
                                orderRels[order] = rel
                            if (arcrole not in (XbrlConst.dimensionDomain, XbrlConst.domainMember) and
                                rel.get("{http://xbrl.org/2005/xbrldt}usable") == "false"):
                                val.modelXrl.error("GFM.1.08.11",
                                    _("Disallowed xbrldt:usable='false' attribute on %(arc)s relationship from concept %(conceptFrom)s in "
                                      "base set role %(linkrole)s to concept %(conceptTo)s"),
                                    modelObject=(rel, relFrom, relTo), arc=rel.qname, conceptFrom=relFrom.qname, linkrole=rel.linkrole, conceptTo=rel.toModelObject.qname)

    del localPreferredLabels # dereference
    del usedCalcFromTosELR
    del val.summationItemRelsSetAllELRs

    val.modelXbrl.profileActivity("... filer relationships checks", minTimeToShow=1.0)

                            
    # checks on dimensions
    checkFilingDimensions(val, drsELRs)
    val.modelXbrl.profileActivity("... filer dimensions checks", minTimeToShow=1.0)
                                    
    for concept, hasPresentationRelationship in conceptsUsed.items():
        if not hasPresentationRelationship:
            val.modelXbrl.error(("EFM.6.12.03", "GFM.1.6.3"),
                _("Element %(concept)s is used in a fact or context in the instance, but is not in any presentation relationships.  "
                  "Add the element to at least one presentation group."),
                edgarCode="cp-1203-Element-Used-Not-Presented",
                modelObject=[concept] + list(modelXbrl.factsByQname[concept.qname]), concept=concept.qname)
            
    for fromIndx, toIndxs in usedCalcsPresented.items():
        for toIndx in toIndxs:
            fromModelObject = val.modelXbrl.modelObject(fromIndx)
            toModelObject = val.modelXbrl.modelObject(toIndx)
            calcRels = modelXbrl.relationshipSet(XbrlConst.summationItem) \
                                .fromToModelObjects(fromModelObject, toModelObject, checkBothDirections=True)
            fromFacts = val.modelXbrl.factsByQname[fromModelObject.qname]
            toFacts = val.modelXbrl.factsByQname[toModelObject.qname]
            fromFactContexts = set(f.context.contextNonDimAwareHash for f in fromFacts if f.context is not None)
            contextId = backupId = None # for EFM message
            for f in toFacts:
                if f.context is not None:
                    if f.context.contextNonDimAwareHash in fromFactContexts:
                        contextId = f.context.id
                        break
                    backupId = f.context.id
            if contextId is None:
                contextId = backupId
            val.modelXbrl.error(("EFM.6.14.05", "GFM.1.7.5"),
                _("Context %(contextId)s has facts of elements %(conceptFrom)s and %(conceptTo)s, with a calculation relationship in %(linkroleDefinition)s, "
                  "but these elements are not in any common corresponding presentation relationship group."),
                edgarCode="du-1405-Facts-In-Calculations-Presentation-Missing",
                modelObject=calcRels + [fromModelObject, toModelObject],
                linkroleDefinition=val.modelXbrl.roleTypeDefinition(calcRels[0].linkrole if calcRels else None),
                conceptFrom=val.modelXbrl.modelObject(fromIndx).qname, conceptTo=val.modelXbrl.modelObject(toIndx).qname, contextId=contextId)
            
    if disclosureSystem.defaultXmlLang:
        for concept, preferredLabelRels in conceptRelsUsedWithPreferredLabels.items():
            for preferredLabelRel in preferredLabelRels:
                preferredLabel = preferredLabelRel.preferredLabel
                hasDefaultLangPreferredLabel = False
                for modelLabelRel in labelsRelationshipSet.fromModelObject(concept):
                    modelLabel = modelLabelRel.toModelObject
                    if modelLabel.xmlLang.startswith(disclosureSystem.defaultXmlLang) and \
                       modelLabel.role == preferredLabel:
                        hasDefaultLangPreferredLabel = True
                        break
                if not hasDefaultLangPreferredLabel:
                    val.modelXbrl.error("GFM.1.06.04", # 6.12.04 now reserved: ("EFM.6.12.04", "GFM.1.06.04"),
                        _("Concept %(concept)s missing %(lang)s preferred labels for role %(preferredLabel)s"),
                        modelObject=(preferredLabelRel, concept), concept=concept.qname, fromConcept=preferredLabelRel.fromModelObject.qname,
                        lang=disclosureSystem.defaultLanguage, preferredLabel=preferredLabel)
    del conceptRelsUsedWithPreferredLabels
    
    # 6 16 4, 1.16.5 Base sets of Domain Relationship Sets testing
    val.modelXbrl.profileActivity("... filer preferred label checks", minTimeToShow=1.0)
    
    if "EFM/Filing.py#validateFiling_end" in val.modelXbrl.arelleUnitTests:
        raise pyNamedObject(val.modelXbrl.arelleUnitTests["EFM/Filing.py#validateFiling_end"])

    if isEFM:
        for pluginXbrlMethod in pluginClassMethods("Validate.EFM.Finally"):
            pluginXbrlMethod(val, conceptsUsed)
    val.modelXbrl.profileActivity("... plug in '.Finally' checks", minTimeToShow=1.0)
    val.modelXbrl.profileStat(_("validate{0}").format(modelXbrl.modelManager.disclosureSystem.validationType))
    
    modelXbrl.modelManager.showStatus(_("ready"), 2000)
                
def isStandardUri(val, uri):
    try:
        return val._isStandardUri[uri]
    except KeyError:
        isStd = (uri in val.disclosureSystem.standardTaxonomiesDict or
                 (not isHttpUrl(uri) and 
                  # try 2011-12-23 RH: if works, remove the localHrefs
                  # any(u.endswith(e) for u in (uri.replace("\\","/"),) for e in disclosureSystem.standardLocalHrefs)
                  "/basis/sbr/" in uri.replace("\\","/")
                  ))
        val._isStandardUri[uri] = isStd
        return isStd

def directedCycle(val, relFrom, origin, fromRelationships, path):
    if relFrom in fromRelationships:
        for rel in fromRelationships[relFrom]:
            relTo = rel.toModelObject
            if relTo == origin:
                return [rel]
            if relTo not in path: # report cycle only where origin causes the cycle
                path.add(relTo)
                foundCycle = directedCycle(val, relTo, origin, fromRelationships, path)
                if foundCycle is not None:
                    foundCycle.insert(0, rel)
                    return foundCycle
                path.discard(relTo)
    return None


def checkConceptLabels(val, modelXbrl, labelsRelationshipSet, disclosureSystem, concept):
    hasDefaultLangStandardLabel = False
    dupLabels = {}
    for modelLabelRel in labelsRelationshipSet.fromModelObject(concept):
        modelLabel = modelLabelRel.toModelObject
        if isinstance(modelLabel, ModelResource) and modelLabel.xmlLang and modelLabel.modelDocument.inDTS:
            if modelLabel.xmlLang.startswith(disclosureSystem.defaultXmlLang) and \
               modelLabel.role == XbrlConst.standardLabel:
                hasDefaultLangStandardLabel = True
            dupDetectKey = ( (modelLabel.role or ''), modelLabel.xmlLang)
            if dupDetectKey in dupLabels:
                modelXbrl.error(("EFM.6.10.02", "GFM.1.5.2"),
                    _("Concept %(concept)s has duplicated labels for role %(role)s lang %(lang)s."),
                    modelObject=(modelLabel, dupLabels[dupDetectKey]), # removed concept from modelObjects
                    concept=concept.qname, role=dupDetectKey[0], lang=dupDetectKey[1])
            else:
                dupLabels[dupDetectKey] = modelLabel
            
    #6 10.1 en-US standard label
    if not hasDefaultLangStandardLabel:
        modelXbrl.error(("EFM.6.10.01", "GFM.1.05.01"),
            _("You have submitted an instance using an element without an %(lang)s standard label %(concept)s. Please check your submission and correct the labels."),
            # concept must be the first referenced modelObject
            edgarCode="cp-1001-Element-Used-Standard-Label",    
            modelObject=[concept] + list(modelXbrl.factsByQname[concept.qname]), concept=concept.qname, 
            lang=disclosureSystem.defaultLanguage)
        
    #6 10.3 default lang label for every role
    try:
        dupLabels[("zzzz",disclosureSystem.defaultXmlLang)] = None #to allow following loop
        priorRole = None
        priorLang = None
        hasDefaultLang = True
        for role, lang in sorted(dupLabels.keys()):
            if role != priorRole:
                if not hasDefaultLang:
                    modelXbrl.error(("EFM.6.10.03", "GFM.1.5.3"),
                        _("You have submitted an instance using an element %(concept)s with %(lang)s for role %(role)s. Please check your submission and correct the labels."),
                        edgarCode="cp-1003-Element-Used-Standard-English-Label",
                        modelObject=list(modelXbrl.factsByQname[concept.qname]) + [dupLabels[(priorRole,priorLang)]], 
                        concept=concept.qname, 
                        lang=disclosureSystem.defaultLanguage, role=priorRole)
                hasDefaultLang = False
                priorLang = lang
                priorRole = role
            if lang is not None and lang.startswith(disclosureSystem.defaultXmlLang):
                hasDefaultLang = True
    except Exception:
        pass

def conflictClassFromNamespace(namespaceURI):
    for pattern, _classIndex, _yearIndex in ((ifrsNamespacesConflictPattern, 2, 1),
                                             (usNamespacesConflictPattern, 2, 3)):
        match = pattern.match(namespaceURI)
        if match:
            _class = match.group(_classIndex)
            _year = match.group(_yearIndex)
            if _class.startswith("ifrs"):
                _class = "ifrs"
            if _year:
                _year = _year.partition("-")[0]
            return "{}/{}".format(_class, _year)
