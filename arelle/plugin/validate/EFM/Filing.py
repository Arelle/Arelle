# -*- coding: utf-8 -*-
'''
This is a collective work.
See COPYRIGHT.md for copyright information for original work.
Subsequent validations and enhancements created by staff of the U.S. Securities and Exchange Commission.
Data and content created by government employees within the scope of their employment are not subject
to domestic copyright protection. 17 U.S.C. 105.
Implementation of DQC rules invokes https://xbrl.us/dqc-license and https://xbrl.us/dqc-patent

'''
import re, datetime, decimal, json, unicodedata, holidays, fnmatch
from math import isnan, pow
from collections import defaultdict, OrderedDict
from pytz import timezone
from arelle import (ModelDocument, ModelValue, ModelRelationshipSet,
                    XmlUtil, XbrlConst, ValidateFilingText)
from arelle.ModelValue import qname, QName, dateUnionEqual
from arelle.ValidateXbrlCalcs import insignificantDigits
from arelle.ModelObject import ModelObject
from arelle.ModelInstanceObject import ModelFact, ModelInlineFact, ModelInlineFootnote
from arelle.ModelDtsObject import ModelConcept, ModelResource
from arelle.ModelXbrl import NONDEFAULT
from arelle.PluginManager import pluginClassMethods
from arelle.PrototypeDtsObject import LinkPrototype, LocPrototype, ArcPrototype
from arelle.PythonUtil import pyNamedObject, strTruncate, flattenSequence, flattenToSet, OrderedSet
from arelle.UrlUtil import isHttpUrl
from arelle.ValidateXbrlCalcs import inferredDecimals, rangeValue, roundValue, ONE
from arelle.XmlValidate import VALID
from .DTS import checkFilingDTS
from .Consts import submissionTypesAllowingWellKnownSeasonedIssuer, \
                    submissionTypesNotRequiringPeriodEndDate, \
                    submissionTypesAllowingEntityInvCompanyType, docTypesRequiringEntityFilerCategory, \
                    submissionTypesAllowingAcceleratedFilerStatus, submissionTypesAllowingShellCompanyFlag, \
                    submissionTypesAllowingEdgarSmallBusinessFlag, submissionTypesAllowingEmergingGrowthCompanyFlag, \
                    submissionTypesAllowingExTransitionPeriodFlag, submissionTypesAllowingSeriesClasses, \
                    submissionTypesExemptFromRoleOrder, docTypesExemptFromRoleOrder, \
                    submissionTypesAllowingPeriodOfReport, docTypesRequiringPeriodOfReport, \
                    docTypesRequiringEntityWellKnownSeasonedIssuer, invCompanyTypesAllowingSeriesClasses, \
                    submissionTypesAllowingVoluntaryFilerFlag, docTypesNotAllowingInlineXBRL, \
                    docTypesRequiringRrSchema, docTypesNotAllowingIfrs, \
                    untransformableTypes, rrUntransformableEltsPattern, \
                    docTypes20F, hideableNamespacesPattern, linkbaseValidations

from .Dimensions import checkFilingDimensions
from .PreCalAlignment import checkCalcsTreeWalk
from .Util import conflictClassFromNamespace, abbreviatedNamespace, NOYEAR, WITHYEARandWILD, loadDeprecatedConceptDates, \
                    loadCustomAxesReplacements, loadNonNegativeFacts, loadDeiValidations, loadOtherStandardTaxonomies, \
                    loadUgtRelQnames, loadDqcRules, factBindings, leastDecimals, axisMemQnames, memChildQnames, \
                    loadTaxonomyCompatibility, loadIxTransformRegistries

MIN_DOC_PER_END_DATE = ModelValue.dateTime("1980-01-01", type=ModelValue.DATE)
MAX_DOC_PER_END_DATE = ModelValue.dateTime("2050-12-31", type=ModelValue.DATE)
ONE_DAY = datetime.timedelta(days=1)
EMPTY_DICT = {}
EMPTY_SET = set()
EMPTY_LIST = []

def sevMessageArgValue(x):
    if isinstance(x, bool):
        return ("false", "true")[x]
    return str(x)

def logMsg(msg):
    return re.sub(r"{(\w+)}", r"%(\1)s", msg) # replace {...} args with %(...)s args for modelXbrl.log functionality

def validateFiling(val, modelXbrl, isEFM=False, isGFM=False):
    if not modelXbrl.modelDocument or not hasattr(modelXbrl.modelDocument, "xmlDocument"): # not parsed
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
    efmRoleDefinitionPattern = re.compile(r"([0-9]+) - (Statement|Disclosure|Schedule|Document) - (.+)")
    messageKeySectionPattern = re.compile(r"(.*[{]efmSection[}]|[a-z]{2}-[0-9]{4})(.*)")
    secDomainPattern = re.compile(r"(fasb\.org|xbrl\.sec\.gov)")

    val._isStandardUri = {}
    modelXbrl.modelManager.disclosureSystem.loadStandardTaxonomiesDict()


    datetimeNowAtSEC = ModelValue.dateTime(
        val.params.get("datetimeForTesting",
        datetime.datetime.now(tz=timezone("US/Eastern")).isoformat()[:19])) # re-strip time zone
    upcomingSECHolidays = holidays.US(state=None, years=[datetimeNowAtSEC.year, datetimeNowAtSEC.year+1])


    # note that some XFM tests are done by ValidateXbrl to prevent mulstiple node walks
    disclosureSystem = val.disclosureSystem
    val.disclosureSystemVersion = disclosureSystemVersion = disclosureSystem.version

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
        raise pyNamedObject(val.modelXbrl.arelleUnitTests["EFM/Filing.py#validateFiling_start"], "EFM/Filing.py#validateFiling_start")

    # instance checks
    val.fileNameBasePart = None # prevent testing on fileNameParts if not instance or invalid
    val.fileNameDate = None
    val.entityRegistrantName = None
    val.requiredContext = None
    documentType = None # needed for non-instance validation too
    submissionType = val.params.get("submissionType", "")
    requiredFactLang = disclosureSystem.defaultXmlLang.lower() if disclosureSystem.defaultXmlLang else disclosureSystem.defaultXmlLang
    hasSubmissionType = bool(submissionType)
    dqcRules = {}
    isInlineXbrl = modelXbrl.modelDocument.type in (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET)
    if isEFM:
        val.otherStandardTaxonomies = loadOtherStandardTaxonomies(modelXbrl, val)
        compatibleTaxonomies = loadTaxonomyCompatibility(modelXbrl)
    if modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or isInlineXbrl:
        deprecatedConceptDates = {}
        deprecatedConceptFacts = defaultdict(list) # index by concept Qname, value is list of facts
        deprecatedConceptContexts = defaultdict(list) # index by contextID, value is list of concept QNames of deprecated dimensions, members

        if isEFM:
            loadDeprecatedConceptDates(val, deprecatedConceptDates)
            customAxesReplacements = loadCustomAxesReplacements(modelXbrl)
            deiValidations = loadDeiValidations(modelXbrl, isInlineXbrl)
            dqcRules = loadDqcRules(modelXbrl) # empty {} if no rules for filing
            ugtRels = loadUgtRelQnames(modelXbrl, dqcRules) # None if no rels applicable
            nonNegFacts = loadNonNegativeFacts(modelXbrl, dqcRules, ugtRels) # none if dqcRules are used after 2020
            ixTrRegistries = loadIxTransformRegistries(modelXbrl)


        # inline doc set has multiple instance names to check
        if modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRLDOCUMENTSET:
            instanceNames = [ixDoc.basename
                             for ixDoc in modelXbrl.modelDocument.referencesDocument.keys()
                             if ixDoc.type == ModelDocument.Type.INLINEXBRL]
            xbrlInstRoots = modelXbrl.ixdsHtmlElements
        else: # single instance document to check is the entry point document
            instanceNames = [modelXbrl.modelDocument.basename]
            xbrlInstRoots = [modelXbrl.modelDocument.xmlDocument.getroot()]
        #6.3.3 filename check
        for instanceName in instanceNames:
            m = instanceFileNamePattern.match(instanceName)
            if isInlineXbrl:
                m = htmlFileNamePattern.match(instanceName)
                if m:
                    val.fileNameBasePart = None # html file name not necessarily parseable.
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
            for xbrlInstRoot in xbrlInstRoots: # check all inline docs in ix doc set
                for entityIdentifierElt in xbrlInstRoot.iterdescendants("{http://www.xbrl.org/2003/instance}identifier"):
                    if isinstance(entityIdentifierElt,ModelObject):
                        schemeAttr = entityIdentifierElt.get("scheme","")
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
                                filerIdentifier=",".join(sorted(val.params["cikNameList"].keys()) if "cikNameList" in val.params else []))
            val.modelXbrl.profileActivity("... filer identifier checks", minTimeToShow=1.0)

        #6.5.7 duplicated contexts
        contexts = modelXbrl.contexts.values()
        contextIDs = set()
        contextsWithNonNilFacts = set()
        uniqueContextHashes = {}
        contextsWithDisallowedOCEs = []
        contextsWithDisallowedOCEcontent = []
        nonStandardTypedDimensions = defaultdict(set)
        nonStandardReplacableDimensions = defaultdict(set)
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
                if isEFM and dim.dimension is not None and dim.dimensionQname.namespaceURI not in disclosureSystem.standardTaxonomiesDict:
                    if dim.isTyped:
                        nonStandardTypedDimensions[dim.dimensionQname].add(context)
                    if customAxesReplacements.customNamePatterns.match(dim.dimensionQname.localName):
                        nonStandardReplacableDimensions[dim.dimensionQname].add(context)
                for _qname in (dim.dimensionQname, dim.memberQname):
                    if _qname in deprecatedConceptDates: # none if typed and then won't be in deprecatedConceptDates
                        deprecatedConceptContexts[contextID].append(_qname)
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
                edgarCode="cp-0539-Typed-Dimension-Not-Standard",
                contextIDs=", ".join(sorted(cntx.id for cntx in set.union(*nonStandardTypedDimensions.values()))),
                dimensions=", ".join(sorted(str(qn) for qn in nonStandardTypedDimensions.keys())))
        for qn, contexts in sorted(nonStandardReplacableDimensions.items(), key=lambda i:str(i[0])):
            try:
                replacableAxisMatch = customAxesReplacements.customNamePatterns.match(qn.localName)
                axis = [customAxesReplacements.standardAxes[k] for k,v in replacableAxisMatch.groupdict().items() if v is not None][0]
                if replacableAxisMatch and any(v is not None for v in replacableAxisMatch.groupdict().values()):
                    val.modelXbrl.warning("EFM.6.05.44.customAxis",
                        _("Contexts %(contextIDs)s use dimension %(dimension)s in namespace %(namespace)s but %(axis)s in %(taxonomy)s is preferred."),
                        edgarCode="dq-0544-Custom-Axis",
                        modelObject=contexts, dimension=qn.localName, namespace=qn.namespaceURI,
                        axis=axis.partition(":")[2], taxonomy=axis.partition(":")[0],
                        contextIDs=", ".join(sorted(c.id for c in contexts)))
            except (AttributeError, IndexError):
                pass # something wrong with match table
        del uniqueContextHashes, contextsWithDisallowedOCEs, contextsWithDisallowedOCEcontent, nonStandardTypedDimensions, nonStandardReplacableDimensions
        val.modelXbrl.profileActivity("... filer context checks", minTimeToShow=1.0)


        #fact items from standard context (no dimension)
        amendmentFlag = None
        amendmentFlagFact = None
        documentPeriodEndDate = None # date or None
        documentPeriodEndDateFact = None
        documentTypeFact = None
        documentTypeFactContextID = None
        deiItems = {}
        deiFacts = {}
        def hasDeiFact(deiName):
            return deiName in deiFacts and not deiFacts[deiName].isNil

        extractedCoverFacts = defaultdict(list) # key concept localname

        commonSharesItemsByStockClass = defaultdict(list)
        commonSharesClassMembers = None
        commonSharesClassAxisQName = None
        deiSharesClassMembers = set()

        # hasDefinedStockAxis = False
        hasCommonSharesOutstandingDimensionedFactWithDefaultStockClass = False
        # commonSharesClassUndefinedMembers = None
        # commonStockMeasurementDatetime = None

        deiNamespaceURI = None
        deiCheckLocalNames = {
            disclosureSystem.deiCurrentFiscalYearEndDateElement,
            disclosureSystem.deiDocumentFiscalYearFocusElement,
            "CurrentFiscalYearEndDate",
            "DocumentFiscalPeriodFocus",
            "EntityCommonStockSharesOutstanding",
            "EntityCurrentReportingStatus",
            "EntityEmergingGrowthCompany",
            "EntityExTransitionPeriod",
            "EntityFilerCategory",
            "EntityInvCompanyType",
            "EntityPublicFloat",
            "EntityRegistrantName",
            "EntityReportingCurrencyISOCode",
            "EntityShellCompany",
            "EntitySmallBusiness",
            "EntityVoluntaryFilers",
            "EntityWellKnownSeasonedIssuer"
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
                if factInDeiNamespace and deiNamespaceURI is None:
                    deiNamespaceURI = factQname.namespaceURI
                    deiADRmember = qname(deiNamespaceURI, "AdrMember")
            else:
                factInDeiNamespace = None
            # standard dei items from required context
            if context is not None and f.xValid >= VALID: # tests do not apply to tuples
                if not context.hasSegment and not context.hasScenario:
                    #required context
                    if factInDeiNamespace and (
                        not f.concept.type.isWgnStringFactType or f.xmlLang.lower() == requiredFactLang):
                        value = f.xValue
                        if factElementName == disclosureSystem.deiAmendmentFlagElement:
                            amendmentFlag = value
                            amendmentFlagFact = f
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
                            documentTypeFactContextID = factContextID
                            if not hasSubmissionType: # wch 18/aug/18
                                modelXbrl.info("info",_("Setting submissionType %(documentType)s"),documentType=documentType)
                                submissionType = documentType #wch 18/aug/18
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
                                commonSharesClassAxisQName = dimConcept.qname
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
                            if factInDeiNamespace and dimConcept is not None and dimConcept.name in ("StatementClassOfStockAxis", "ClassesOfShareCapitalAxis") and memConcept is not None:
                                deiSharesClassMembers.add(memConcept.qname)

                    if isEntityCommonStockSharesOutstanding and not hasClassOfStockMember:
                        hasCommonSharesOutstandingDimensionedFactWithDefaultStockClass = True   # absent dimension, may be no def LB

                # 6.5.43 signs - applies to all facts having a context.
                if (isEFM and nonNegFacts and f.qname in nonNegFacts.concepts and f.isNumeric and not f.isNil and f.xValue < 0 and (
                    all(dim.isTyped or (
                        (dim.dimensionQname not in nonNegFacts.excludedAxesMembers or
                         ("*" not in nonNegFacts.excludedAxesMembers[dim.dimensionQname] and
                          dim.memberQname not in nonNegFacts.excludedAxesMembers[dim.dimensionQname])) and
                         dim.memberQname not in nonNegFacts.excludedMembers and
                         (nonNegFacts.excludedMemberNamesPattern is None or
                          not nonNegFacts.excludedMemberNamesPattern.search(dim.memberQname.localName)))
                        for dim in context.qnameDims.values()))):
                    modelXbrl.warning("EFM.6.05.43",
                        _("Concept %(element)s in %(taxonomy)s has a negative value %(value)s in context %(context)s.  Correct the sign, use a more appropriate concept, or change the context."),
                        edgarCode="dq-0543-Negative-Fact-Value",
                        modelObject=f, element=f.qname.localName, taxonomy=abbreviatedNamespace(f.qname.namespaceURI),
                        value=f.value, context=f.contextID)

                if not f.isNil:
                    contextsWithNonNilFacts.add(context)
                    if f.qname.localName in deiValidations["extraction-cover-tags"]:
                        extractedCoverFacts[f.qname.localName].append(f)

                if isEFM: # note that this is in the "if context is not None" region.  It does receive nil facts.
                    for pluginXbrlMethod in pluginClassMethods("Validate.EFM.Fact"):
                        pluginXbrlMethod(val, f)
            #6.5.17 facts with precision
            concept = f.concept
            if concept is not None:
                # note fact concepts used
                conceptsUsed[concept] = False

                if concept.isNumeric:
                    if f.precision is not None:
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

                if concept.qname in deprecatedConceptDates:
                    deprecatedConceptFacts[concept.qname].append(f)

                if concept.isEnumeration and not f.isNil:
                    for qnEnum in flattenSequence(f.xValue):
                        if qnEnum in deprecatedConceptDates:
                            deprecatedConceptFacts[qnEnum].append(f)

            if factContextID in deprecatedConceptContexts: # deprecated dimension and member qnames
                for _qname in deprecatedConceptContexts[factContextID]:
                    deprecatedConceptFacts[_qname].append(f)

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
                value = deiItems.get(disclosureSystem.deiFilerIdentifierElement)
                if entityIdentifierValue != value:
                    val.modelXbrl.error(("EFM.6.05.23", "GFM.3.02.02"),
                        _("The EntityCentralIndexKey, %(value)s, does not match the context identifier CIK %(entityIdentifier)s.  "
                          "Please include a correct matching EntityCentralIndexKey and context identifier CIK(s) in the filing."),
                        edgarCode="cp-0523-Non-Matching-Cik",
                        modelObject=deiFilerIdentifierFact, elementName=disclosureSystem.deiFilerIdentifierElement,
                        value=value, entityIdentifier=entityIdentifierValue)
                if "cikNameList" in val.params:
                    if value not in val.params["cikNameList"]:
                        val.modelXbrl.error(("EFM.6.05.23.submissionIdentifier", "GFM.3.02.02"),
                            _("The submission CIK, %(filerIdentifier)s does not match the EntityCentralIndexKey.  "
                              "Please include a correct matching EntityCentralIndexKey in the filing."),
                            edgarCode="cp-0523-Non-Matching-Cik",
                            modelObject=deiFilerIdentifierFact, elementName=disclosureSystem.deiFilerIdentifierElement,
                            value=value, filerIdentifier=",".join(sorted(val.params["cikNameList"].keys())))
                elif val.params.get("cik") and value != val.params["cik"]:
                    val.modelXbrl.error(("EFM.6.05.23.submissionIdentifier", "GFM.3.02.02"),
                        _("The submission CIK, %(filerIdentifier)s does not match the %(elementName)s.  "
                          "Please include a correct matching %(elementName)s in the filing."),
                        edgarCode="cp-0523-Non-Matching-Cik",
                        modelObject=deiFilerIdentifierFact, elementName=disclosureSystem.deiFilerIdentifierElement,
                        value=value, filerIdentifier=val.params["cik"])
            if disclosureSystem.deiFilerNameElement in deiItems:
                value = deiItems[disclosureSystem.deiFilerNameElement]
                if "cikNameList" in val.params and entityIdentifierValue in val.params["cikNameList"]:
                    prefix = val.params["cikNameList"][entityIdentifierValue]
                    if prefix is not None:
                        if ((isInlineXbrl and not re.match(cleanedCompanyName(prefix).replace("-", r"[\s-]?"),
                                                          cleanedCompanyName(value), flags=re.IGNORECASE)) or
                            (not isInlineXbrl and not value.casefold().startswith(prefix.casefold()))): # casefold needed for some non-en languages
                            val.modelXbrl.error(("EFM.6.05.24", "GFM.3.02.02"),
                                _("The Official Registrant name, %(prefix)s, does not match the value %(value)s in the Required Context.  "
                                  "Please correct dei:%(elementName)s."),
                                edgarCode="cp-0524-Registrant-Name-Mismatch",
                                modelObject=deiFilerNameFact, elementName=disclosureSystem.deiFilerNameElement,
                                prefix=prefix, value=value)

        if isEFM and disclosureSystem.deiNamespacePattern is not None and deiNamespaceURI is None:
            modelXbrl.error("EFM.6.05.20.deiFactsMissing",
                _("DEI facts are missing."),
                edgarCode="dq-{efmSection}-{tag}-Missing",
                modelObject=modelXbrl, subType=submissionType, efmSection="0520", severityVerb="must", tag="DEI-Facts", context="Required Context")

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
                modelObject=modelXbrl, documentType=documentType)

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
                                edgarCode="du-0536-Name-Length-Limit",
                                modelObject=measureElt, unitID=unit.id, measure=measureElt.xValue.localName, length=l)
        del uniqueUnitHashes

        # 6.5.42 deprecated concepts
        if deprecatedConceptFacts:
            for conceptQn, facts in sorted(deprecatedConceptFacts.items(), key=lambda i:[0]):
                date = deprecatedConceptDates[conceptQn]
                version1 = abbreviatedNamespace(conceptQn.namespaceURI)
                modelXbrl.warning("EFM.6.05.42",
                    _("Concept %(element)s in %(version1)s used in %(count)s facts was deprecated in %(version2)s as of %(date)s and should not be used."),
                    edgarCode="dq-0542-Deprecated-Concept",
                    modelObject=facts, element=conceptQn.localName, count=len(facts), date=date,
                    version1=version1, version2=version1[:-4]+date[0:4])

        del deprecatedConceptContexts, deprecatedConceptFacts, deprecatedConceptDates, nonNegFacts
        val.modelXbrl.profileActivity("... filer unit checks", minTimeToShow=1.0)


        # EFM.6.05.14, GFM.1.02.13 xml:lang tests, as of v-17, full default lang is compared
        #if val.validateEFM:
        #    factLangStartsWith = disclosureSystem.defaultXmlLang[:2]
        #else:
        #    factLangStartsWith = disclosureSystem.defaultXmlLang

        #6.5.12 equivalent facts
        factsForLang = {}
        factForConceptContextUnitHash = defaultdict(list)
        keysNotDefaultLang = {}
        for f1 in modelXbrl.facts:
            if f1.context is not None and f1.concept is not None and f1.concept.type is not None and getattr(f1,"xValid", 0) >= VALID:
                # build keys table for 6.5.14
                if not f1.isNil:
                    langTestKey = "{0},{1},{2}".format(f1.qname, f1.contextID, f1.unitID)
                    factsForLang.setdefault(langTestKey, []).append(f1)
                    lang = f1.xmlLang
                    if lang and lang.lower() != requiredFactLang: # not lang.startswith(factLangStartsWith):
                        keysNotDefaultLang[langTestKey] = f1

                    # 6.5.37 test (insignificant digits due to rounding)
                    if f1.isNumeric and f1.decimals and f1.decimals != "INF":
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
                factForConceptContextUnitHash[f1.conceptContextUnitHash].append(f1)
        # 6.5.12 test
        aspectEqualFacts = defaultdict(list)
        decVals = {}
        for hashEquivalentFacts in factForConceptContextUnitHash.values():
            if len(hashEquivalentFacts) > 1:
                for f in hashEquivalentFacts:
                    aspectEqualFacts[(f.qname,f.contextID,f.unitID,
                                      f.xmlLang.lower() if f.concept.type.isWgnStringFactType else None)].append(f)
                for fList in aspectEqualFacts.values():
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
                        modelXbrl.error(("EFM.6.05.12", "GFM.1.02.11"),
                            "The instance document contained an element, %(fact)s that was used more than once in contexts equivalent to %(contextID)s: values %(values)s.  "
                            "Please ensure there are no duplicate combinations of concept and context in the instance.",
                            edgarCode="du-0512-Duplicate-Facts",
                            modelObject=fList, fact=f0.qname, contextID=f0.contextID, values=", ".join(strTruncate(f.value, 128) for f in fList))
                aspectEqualFacts.clear()
        del factForConceptContextUnitHash, aspectEqualFacts
        val.modelXbrl.profileActivity("... filer fact checks", minTimeToShow=1.0)

        #6.5.14 facts without english text
        for keyNotDefaultLang, factNotDefaultLang in keysNotDefaultLang.items():
            anyDefaultLangFact = False
            for fact in factsForLang[keyNotDefaultLang]:
                if fact.xmlLang.lower() == requiredFactLang: #.startswith(factLangStartsWith):
                    anyDefaultLangFact = True
                    break
            if not anyDefaultLangFact:
                val.modelXbrl.error(("EFM.6.05.14", "GFM.1.02.13"),
                    _("Element %(fact)s in context %(contextID)s has text with xml:lang other than '%(lang2)s' (%(lang)s) without matching English text.  "
                      "Please provide a fact with xml:lang equal to '%(lang2)s'."),
                    edgarCode="du-0514-English-Text-Missing",
                    modelObject=factNotDefaultLang, fact=factNotDefaultLang.qname, contextID=factNotDefaultLang.contextID,
                    lang=factNotDefaultLang.xmlLang, lang2=disclosureSystem.defaultXmlLang) # report lexical format default lang

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

        isDei2018orLater = any(doc.targetNamespace.startswith("http://xbrl.sec.gov/dei/") and doc.targetNamespace >= "http://xbrl.sec.gov/dei/2018"
                               for doc in modelXbrl.urlDocs.values() if doc.targetNamespace)

        isRR = any(doc.targetNamespace.startswith("http://xbrl.sec.gov/rr/")
                   for doc in modelXbrl.urlDocs.values() if doc.targetNamespace)

         # seriesId 6.5.41
        if submissionType in submissionTypesAllowingSeriesClasses and deiItems.get("EntityInvCompanyType") in invCompanyTypesAllowingSeriesClasses:
            legalEntityAxis = modelXbrl.nameConcepts.get("LegalEntityAxis",())
            if len(legalEntityAxis) > 0:
                legalEntityAxisQname = legalEntityAxis[0].qname
                if legalEntityAxisQname.namespaceURI.startswith("http://xbrl.sec.gov/dei/"):
                    legalEntityAxisRelationshipSet = modelXbrl.modelXbrl.relationshipSet("XBRL-dimensions")
                    if val.params.get("rptIncludeAllSeriesFlag") in (True, "Yes", "yes", "Y", "y"):
                        seriesIds = val.params.get("newClass2.seriesIds", ())
                    else:
                        seriesIds = val.params.get("rptSeriesClassInfo.seriesIds", ())
                    for seriesId in sorted(set(seriesIds)): # series Ids are a hierarchy and need to be de-duplicated and ordered
                        seriesIdMemberName = seriesId + "Member"
                        seriesIdMember = None
                        for c in modelXbrl.nameConcepts.get(seriesIdMemberName, ()):
                            if c.type.isDomainItemType:
                                seriesIdMember = c
                                break
                        if seriesIdMember is None:
                            xsds = [doc for url, doc in modelXbrl.urlDocs.items()  # all filer schemas
                                    if doc.type == ModelDocument.Type.SCHEMA and
                                    url not in disclosureSystem.standardTaxonomiesDict]
                            modelXbrl.warning("EFM.6.05.41.seriesIdMemberNotDeclared",
                                _("Submission type %(subType)s should have %(seriesIdMember)s declared as a domainItemType element."),
                                edgarCode="dq-0541-Series-Id-Member-Not-Declared",
                                modelObject=xsds, seriesIdMember=seriesIdMemberName, subType=submissionType)
                        elif not legalEntityAxisRelationshipSet.isRelated(legalEntityAxis[0],"descendant", seriesIdMember):
                            defLBs = [doc for url, doc in modelXbrl.urlDocs.items()  # all filer def LBs
                                      if doc.type == ModelDocument.Type.LINKBASE and
                                      url not in disclosureSystem.standardTaxonomiesDict and
                                      url.endswith("_def.xml")]
                            modelXbrl.warning("EFM.6.05.41.seriesIdMemberNotAxisMember",
                                _("Submission type %(subType)s should have %(seriesIdMember)s as a member of the Legal Entity Axis."),
                                edgarCode="dq-0541-Series-Id-Member-Not-Axis-Member",
                                modelObject=[seriesIdMember, defLBs], seriesIdMember=seriesIdMemberName, subType=submissionType)
                        elif not any(cntx.hasDimension(legalEntityAxisQname) and seriesIdMember == cntx.qnameDims[legalEntityAxisQname].member
                                     for cntx in contextsWithNonNilFacts):
                            modelXbrl.warning("EFM.6.05.41.seriesIdMemberNotInContext",
                                _("Submission type %(subType)s should have a context with %(seriesIdMember)s as a member of the Legal Entity Axis."),
                                edgarCode="dq-0541-Series-Id-Member-Not-In-Context",
                                modelObject=(modelXbrl,seriesIdMember), seriesIdMember=seriesIdMemberName, subType=submissionType)
        val.modelXbrl.profileActivity("... filer label and text checks", minTimeToShow=1.0)

        if isEFM:
            if val.params.get("exhibitType") and documentType is not None:
                _exhibitType = val.params["exhibitType"]
                if (documentType in ("SD", "SD/A")) != (_exhibitType == "EX-2.01"):
                    modelXbrl.error({"EX-100":"EFM.6.23.04",
                                     "EX-101":"EFM.6.23.04",
                                     "EX-99.K SDR.INS":"EFM.6.23.04",
                                     "EX-99.L SDR.INS":"EFM.6.23.04",
                                     "EX-2.01":"EFM.6.23.05"}.get(_exhibitType,"EX-101"),
                        #edgarCode
                        _("The value for dei:DocumentType, %(documentType)s, is not allowed for %(exhibitType)s attachments."),
                        modelObject=documentTypeFact, contextID=documentTypeFactContextID, documentType=documentType, exhibitType=_exhibitType,
                        messageCodes=("EFM.6.23.04", "EFM.6.23.04", "EFM.6.23.05"))
                elif (((documentType == "K SDR") != (_exhibitType in ("EX-99.K SDR", "EX-99.K SDR.INS"))) or
                      ((documentType == "L SDR") != (_exhibitType in ("EX-99.L SDR", "EX-99.L SDR.INS")))):
                    modelXbrl.error("EFM.6.05.20.exhibitDocumentType",
                        _("The value for dei:DocumentType, '%(documentType)s' is not allowed for %(exhibitType)s attachments."),
                        modelObject=documentTypeFact, contextID=documentTypeFactContextID, documentType=documentType, exhibitType=_exhibitType)

            # Table driven validations
            def sevMessage(sev, messageKey=None, **kwargs):
                logArgs = kwargs.copy()
                validation = deiValidations["validations"][sev["validation"]]
                severity = kwargs.get("severity", validation["severity"]).upper()
                if severity == "WARNINGIFPRAGMATICELSEERROR":
                    severity = "WARNING" if validateEFMpragmatic else "ERROR"
                if messageKey is None:
                    messageKey = validation[kwargs.get("validationMessage", "message")]
                if messageKey is None:
                    return # not a m
                if "severityVerb" not in logArgs:
                    logArgs["severityVerb"] = (validation.get("severityVerb") or
                                               {"WARNING":"should","ERROR":"must"}[severity])
                if "efmSection" not in logArgs:
                    logArgs["efmSection"] = sev.get("efm")
                efm = logArgs["efmSection"].split(".")
                logArgs["efmSection"] = "{}{}".format(efm[1].zfill(2), efm[2].zfill(2))
                logArgs["edgarCode"] = messageKey # edgar code is the un-expanded key for message with {...}'s
                logArgs["arelleCode"] = "EFM.{}.{}.{}".format(efm[0], efm[1].zfill(2), efm[2].zfill(2))
                try:
                    keyAfterSection = messageKeySectionPattern.match(messageKey).group(2)
                    arelleCode = "{arelleCode}.".format(**logArgs) + keyAfterSection.format(**logArgs) \
                                  .replace(",", "").replace(".","").replace(" ","") # replace commas in names embedded in message code portion
                except KeyError as err:
                    modelXbrl.error("arelle:loadDeiValidations",
                                    _("Missing field %(field)s from messageKey %(messageKey)s, validation %(validation)s."),
                                    field=err, messageKey=messageKey, validation=sev)
                    return
                arelleCodeSections = arelleCode.split("-")
                if len(arelleCodeSections) > 1 and arelleCodeSections[1]:
                    arelleCodeSections[1] = arelleCodeSections[1][0].lower() + arelleCodeSections[1][1:] # start with lowercase
                arelleCode = "".join(arelleCodeSections)
                axisKey = sev.get("axis","")
                axesValidations = deiValidations["axis-validations"][axisKey]
                logArgs["axis"] = " or ".join(axesValidations["axes"])
                logArgs["member"] = " or ".join(axesValidations["members"])
                if "context" in logArgs:
                    pass # custom content for context argument
                elif not axisKey:
                    logArgs["context"] = "Required Context"
                elif axisKey == "c":
                    if not commonSharesClassMembers or len(commonSharesClassMembers) == 1:
                        logArgs["context"] = "Required Context (one class of stock axis)"
                    else:
                        logArgs["context"] = "context corresponding to the Required Context with at least one of {}".format(
                            logArgs["axis"])
                else:
                    logArgs["context"] = "context with {} and {}".format(
                            logArgs["axis"], logArgs["member"])
                if "modelObject" in logArgs and "contextID" not in logArgs:
                    modelObjects = logArgs["modelObject"]
                    for f in modelObjects if isinstance(modelObjects, (tuple, set, list)) else (modelObjects,):
                        if isinstance(f, ModelFact):
                            logArgs["contextID"] = f.contextID
                            break
                if logArgs.get("modelObject") is None: # no modelObject, default to the entry document
                    logArgs["modelObject"] = modelXbrl
                if "value" in logArgs:
                    v = logArgs["value"]
                    if isinstance(v, list):
                        if len(v) == 1:
                            logArgs["value"] = sevMessageArgValue(v[0])
                        else:
                            logArgs["value"] = "one of {}".format(", ".join(sevMessageArgValue(_v) for _v in v))
                if "subType" in logArgs: # provide item 5.03 friendly format for submission type
                    logArgs["subType"] = logArgs["subType"].replace("+5.03", " (with item 5.03)")
                message = deiValidations["messages"][messageKey]
                modelXbrl.log(severity, arelleCode, logMsg(message), **logArgs)

            sevs = deiValidations["sub-type-element-validations"]
            deiCAxes = deiValidations["axis-validations"]["c"]["axes"]
            # Its possible that extension concepts could have prefixes that match `cef` or `vip`
            # and EFM.6.5.55 or EFM.6.5.56 validations so we exclude all extension namespaces by
            # filtering out prefix namespace combos where the namespace matches known SEC domains.
            deiDefaultPrefixedNamespaces = {
                prefix: namespace for prefix, namespace in deiValidations["prefixed-namespaces"].items() if secDomainPattern.search(namespace)
            }
            # called with sev, returns iterator of sev facts for names and axes matching
            # called with sev and name, returns single fact for name matching axesMembers (if any)
            def sevFacts(sev=None, name=None, otherFact=None, requiredContext=False, axisKey=None, deduplicate=False):
                if deduplicate:
                    previouslyYieldedFacts = set()
                    def notdup(f):
                        dedupKey = (f.qname, f.context.contextDimAwareHash, f.xmlLang if f.isMultiLanguage else None)
                        if dedupKey not in previouslyYieldedFacts:
                            previouslyYieldedFacts.add(dedupKey)
                            return True
                        return False
                if isinstance(sev, int):
                    sev = sevs[sev] # convert index to sev object
                if isinstance(name, list):
                    names = name
                elif name:
                    names = (name,)
                else:
                    names = sev.get("xbrl-names", ())
                langPattern = sev.get("langPattern")
                if axisKey is None:
                    axisKey = sev.get("axis","")
                axesValidations = deiValidations["axis-validations"][axisKey]
                axes = axesValidations["axes"]
                members = axesValidations["members"]

                for name in names:
                    for f in modelXbrl.factsByQname.get(qname(name, deiDefaultPrefixedNamespaces), EMPTY_SET):
                        if langPattern is not None and not langPattern.match(f.xmlLang):
                            continue
                        context = f.context
                        if context is not None and f.xValid >= VALID and not f.isNil:
                            if otherFact is not None:
                                if context.isEqualTo(otherFact.context):
                                    if not deduplicate or notdup(f):
                                        yield f
                            elif requiredContext and documentType:
                                if ((context.isInstantPeriod and not context.qnameDims) or
                                    (context.isStartEndPeriod and context.isEqualTo(documentTypeFact.context))):
                                    if not deduplicate or notdup(f):
                                        yield f
                            elif not context.qnameDims and (not axes or axisKey == "c"):
                                if not deduplicate or notdup(f):
                                    yield f
                            elif context.qnameDims: # has dimensions
                                excludesAxes = "!not!" in axes
                                hasDimMatch = False
                                for dim in context.qnameDims.values():
                                    if dim.dimensionQname.localName in axes:
                                        if (not members or
                                            dim.memberQname.localName in members):
                                            hasDimMatch = True
                                            if not deduplicate or notdup(f):
                                                if not excludesAxes:
                                                    yield f
                                            break
                                if excludesAxes and not hasDimMatch:
                                    yield f

            # return first of matching facts or None
            def sevFact(sev=None, name=None, otherFact=None, requiredContext=False):
                if isinstance(name, list):
                    for _name in name:
                        f = sevFact(sev, _name, otherFact, requiredContext)
                        if f is not None:
                            return f
                else:
                    for f in sevFacts(sev, name, otherFact, requiredContext):
                        return f
                return None

            def isADR(f):
                return f is not None and f.context is not None and (
                    any(d.dimensionQname.localName in deiValidations["axis-validations"]["c"]["axes"]
                        and d.memberQname == deiADRmember
                        for d in f.context.qnameDims.values()))

            unexpectedDeiNameEfmSects = defaultdict(set) # name and sev(s)
            expectedDeiNames = defaultdict(set)
            coverVisibleQNames = {}  # true if error, false if warning when not visible
            unexpectedEloParams = set()
            expectedEloParams = set()
            storeDbObjectFacts = defaultdict(dict)
            eloValueFactNames = set(n for sev in sevs if "store-db-name" in sev for n in sev.get("xbrl-names", ())) # fact names producing elo values
            missingReqInlineTag = False
            reportDate = val.params.get("periodOfReport")
            if reportDate:
                reportDate = "{2}-{0}-{1}".format(*str(reportDate   ).split('-')) # mm-dd-yyyy
            elif documentPeriodEndDate:
                reportDate = str(documentPeriodEndDate)
            elif val.requiredContext is not None:
                reportDate = str(XmlUtil.dateunionValue(val.requiredContext.endDatetime, subtractOneDay=True))
            for sevIndex, sev in enumerate(sevs):
                subTypes = sev.get("subTypeSet", EMPTY_SET) # compiled set of sub-types
                subTypesPattern = sev.get("subTypesPattern")
                names = sev.get("xbrl-names", ())
                eloName = sev.get("elo-name")
                storeDbName = sev.get("store-db-name")
                storeDbObject = sev.get("store-db-object")
                efmSection = sev.get("efm")
                validation = sev.get("validation")
                checkAfter = sev.get("check-after")
                axisKey = sev.get("axis","")
                value = sev.get("value")
                isCoverVisible = {"cover":False, "COVER":True, "dei": None, None: None
                                  }[sev.get("dei/cover")]
                referenceTag = sev.get("references")
                referenceValue = sev.get("reference-value")
                if checkAfter and reportDate and checkAfter >= reportDate:
                    continue
                subFormTypesCheck = {submissionType, "{}§{}".format(submissionType, documentType)}
                if (subTypes != "all"
                    and (subFormTypesCheck.isdisjoint(subTypes) ^ ("!not!" in subTypes))
                    and (not subTypesPattern or not subTypesPattern.match(submissionType))):
                    if validation is not None: # don't process name for sev's which only store-db-field
                        for name in names:
                            if name.endswith(":*") and validation == "(supported-taxonomy)": # taxonomy-prefix filter
                                txPrefix = name[:-2]
                                ns = deiDefaultPrefixedNamespaces.get(txPrefix)
                                if ns:
                                    unexpectedFacts = set()
                                    for qn, facts in modelXbrl.factsByQname.items():
                                        if qn.namespaceURI == ns:
                                            unexpectedFacts |= facts
                                    if unexpectedFacts:
                                        sevMessage(sev, subType=submissionType, modelObject=unexpectedFacts, taxonomy=txPrefix)
                            if sevFact(sev, name) is not None:
                                unexpectedDeiNameEfmSects[name,axisKey].add(sevIndex)
                        if eloName:
                            unexpectedEloParams.add(eloName)
                    continue
                # name is expected for this form
                if validation is not None: # don't process name for sev's which only store-db-field
                    for name in names:
                        expectedDeiNames[name,axisKey].add(sevIndex)
                        if isCoverVisible is not None:
                            coverVisibleQNames[qname(name, deiDefaultPrefixedNamespaces)] = isCoverVisible
                # last validation for unexpected items which were not bound to a validation for submission form type
                if validation in ("(blank)", "(blank-error)"):
                    includeNames = sev.get("include-xbrl-names")
                    excludeNames = sev.get("exclude-xbrl-names")
                    for nameAxisKey, sevIndices in unexpectedDeiNameEfmSects.items():
                        efmSection = sevs[sorted(sevIndices)[0]].get("efm") # use first section
                        if nameAxisKey not in expectedDeiNames:
                            name, axisKey = nameAxisKey
                            if (includeNames is None or name in includeNames) and (excludeNames is None or name not in excludeNames):
                                sevMessage(sev, subType=submissionType, efmSection=efmSection, tag=name,
                                                modelObject=[f for i in sevIndices for f in sevFacts(i, name)],
                                                typeOfContext="Required Context")
                elif validation == "(elo-unexpected)":
                    for eloName in sorted(unexpectedEloParams - expectedEloParams):
                        if eloName in val.params:
                            sevMessage(sev, subType=submissionType, efmSection="6.5.40",
                                       modelObject=modelXbrl, headerTag=eloName, value=val.params[eloName])
                elif validation == "(earliest-taxonomy)":
                    for et in sev.get("earliest-taxonomies", ()):
                        txPrefix = et.partition("/")[0]
                        ns = deiDefaultPrefixedNamespaces.get(txPrefix)
                        if ns:
                            foundVersion = abbreviatedNamespace(ns)
                            if foundVersion and foundVersion < et:
                                sevMessage(sev, subType=submissionType, modelObject=modelXbrl, taxonomy=txPrefix, earliestVersion=et)
                elif validation == "taxonomy-version-required":
                    if len(names) != value:
                        et = sev["earliest-taxonomy"]
                        sevMessage(sev, subType=submissionType, efmSection=efmSection, taxonomy=et.partition('/')[0], earliestTaxonomy=et)
                elif validation == "taxonomy-url-required-in-dts":
                    if not any(fnmatch.fnmatch(url, value) for url in modelXbrl.urlDocs.keys()):
                        sevMessage(sev, subType=submissionType, efmSection=efmSection, taxonomy=value, docType=documentType)
                # type-specific validations
                elif len(names) == 0:
                    pass # no name entries if all dei names of this validation weren't in the loaded dei taxonomy (i.e., pre 2019)
                elif validation == "tf3": # exactly one of names should have value if inline or if noninline and any present
                    numFactWithValue = numFactsNotValue = 0
                    for name in names:
                        f = sevFact(sev, name) # these all are required context
                        if f is not None:
                            if f.xValue == value[0]: # first value is exclusive fact, second is other facts
                                numFactWithValue += 1
                            elif f.xValue == value[1]:
                                numFactsNotValue += 1
                    if (isInlineXbrl or numFactWithValue or numFactsNotValue) and (numFactWithValue != 1 or numFactsNotValue != 2):
                        sevMessage(sev, subType=submissionType,
                                        modelObject=sevFacts(sev), tags=", ".join(names), value=value[0], otherValue=value[1])
                elif validation in ("ws", "wv"): # only one of names should have value
                    numFactWithValue = 0
                    for name in names:
                        f = sevFact(sev, name) # these all are required context
                        if f is not None:
                            if f.xValue in value: # List of values which may be Yes, true, etc...
                                numFactWithValue += 1
                    if numFactWithValue > 1:
                        sevMessage(sev, subType=submissionType,
                                        modelObject=sevFacts(sev), tags=", ".join(names), value=value)
                elif validation in ("o2", "o3"): # at least one present
                    f2 = None
                    numFacts = 0
                    if referenceTag:
                        f2 = sevFact(sev, referenceTag) # f and dependent fact are in same context
                        if f2 is None:
                            numFacts = 999 # block following message because no dependent (e.g., addressLine1)
                    for name in names:
                        f = sevFact(sev, name, f2)
                        if f is not None:
                            f2 = f # align next fact to this context
                            numFacts += 1
                    if numFacts == 0:
                        sevMessage(sev, subType=submissionType, modelObject=sevFacts(sev), tags=", ".join(names))
                elif validation == "op": # all or neither must have a value
                    if 0 < sum(sevFact(sev, name) is not None for name in names) < len(names): # default context for all
                        sevMessage(sev, subType=submissionType, modelObject=sevFacts(sev), tags=", ".join(names))
                elif validation == "et1": # "og":
                    ogfacts = set()
                    for fr in sevFacts(sev, referenceTag, deduplicate=True):
                        if fr.xValue == referenceValue:
                            numOgFacts = 0
                            for f in sevFacts(sev, names, fr):
                                ogfacts.add(f)
                                numOgFacts += 1
                            if numOgFacts == 0:
                                sevMessage(sev, subType=submissionType, modelObject=fr, tag=names[0], value=referenceValue, otherTag=referenceTag, contextID=fr.contextID)
                                if any(name in eloValueFactNames for name in names):
                                    missingReqInlineTag = True
                    # find any facts without a referenceTag fact = value, note these are warning severity
                    for f in sevFacts(sev, names, deduplicate=True):
                        if f not in ogfacts:
                            fr = sevFact(sev, referenceTag, f)
                            if (fr is None or fr.xValue != referenceValue):
                                sevMessage(sev, severity="warning", subType=submissionType, modelObject=f, tag=names[0], value=referenceValue, otherTag=referenceTag, contextID=f.contextID)
                    del ogfacts # dereference
                elif validation == "f2":
                    f = sevFact(sev, referenceTag) # f and dependent fact are in same context
                    if f is not None and not any(sevFact(sev, name, f) is not None for name in names):
                        sevMessage(sev, subType=submissionType, modelObject=f, tag=referenceTag, otherTags=", ".join(names))
                elif validation in ("ol1", "ol2"):
                    for name in names:
                        f = sevFact(sev, name) # referenced fact must be same context as this fact
                        if f is not None and sevFact(sev, referenceTag, f) is None:
                            sevMessage(sev, subType=submissionType, modelObject=sevFacts(sev), tag=name, otherTag=referenceTag, contextID=f.contextID)
                elif validation == "oph":
                    f = sevFact(sev, referenceTag)
                    for name in names:
                        if f is None:
                            f2 = sevFact(sev, name)
                        if ((f is not None and sevFact(sev, name, f) is None) or
                            (f is None and f2 is not None and sevFact(sev, referenceTag, f2) is None)):
                            sevMessage(sev, subType=submissionType, modelObject=f, tag=name, otherTag=referenceTag,
                                       contextID=f.contextID if f is not None else f2.contextID)
                elif validation in ("a", "sr", "oth", "tb", "n2e"): #, "et1"):
                    for name in names:
                        f = sevFact(sev, name)
                        fr = sevFact(sev, referenceTag, f) # dependent fact is of context of f or for "c" inherited context (less disaggregatedd)
                        if ((fr is not None and ((f is not None and fr.xValue != referenceValue) or
                                                 (f is None and fr.xValue == referenceValue))) or
                            (fr is None and f is not None)):
                            sevMessage(sev, subType=submissionType, modelObject=sevFacts(sev), tag=name, otherTag=referenceTag, value=referenceValue,
                                       contextID=f.contextID if f is not None else fr.contextID if fr is not None else "N/A")
                elif validation in ("rt",):
                    for name in names:
                        f = sevFact(sev, name)
                        fr = sevFact(sev, referenceTag, f) # dependent fact is of context of f or for "c" inherited context (less disaggregatedd)
                        if ((fr is not None and ((fr.xValue == referenceValue) ^ (f is not None))) or
                            (fr is None and f is not None)):
                            _facts = [_f for _f in (f, fr) if _f is not None]
                            sevMessage(sev, subType=submissionType, modelObject=_facts, tag=name, otherTag=referenceTag, value=referenceValue, contextID=_facts[0].contextID )
                elif validation in ("n2e",):
                    for name in names:
                        f = sevFact(sev, name)
                        if f is not None and f.xValue == referenceValue:
                            fr = sevFact(sev, referenceTag, f) # dependent fact is of context of f or for "c" inherited context (less disaggregatedd)
                            if ((fr is not None and fr.xValue != referenceValue) or
                                fr is None):
                                sevMessage(sev, subType=submissionType, modelObject=sevFacts(sev), tag=name, otherTag=referenceTag, value=referenceValue,
                                           contextID=f.contextID if f is not None else fr.contextID if fr is not None else "N/A")
                elif validation == "ra":
                    fr = sevFact(sev, referenceTag)
                    for name in names:
                        f = sevFact(sev, name, fr)
                        if fr is not None and fr.xValue in referenceValue and f is None:
                            sevMessage(sev, subType=submissionType, modelObject=sevFacts(sev), tag=referenceTag, otherTag=name, value=fr.xValue, contextID=fr.contextID)
                elif validation == "t":
                    frs = [f for f in sevFacts(sev, referenceTag)] # all reference facts from generator
                    for name in names:
                        for f in sevFacts(sev, name):
                            fr = sevFact(sev, referenceTag, f) # dependent fact is of context of f or for "c" inherited context (less disaggregated)
                            if fr is not None:
                                frs.remove(fr) # this referenced object has been covered by a referencing fact
                            if ((fr is not None and f is None) or
                                (fr is None and f is not None)):
                                sevMessage(sev, subType=submissionType, modelObject=(f,fr), tag=name, otherTag=referenceTag)
                    for fr in frs:
                        for name in names:
                            if sevFact(sev, name, fr) is None: # no corresponding fact to an unreferenced reference fact
                                sevMessage(sev, subType=submissionType, modelObject=fr, tag=referenceTag, otherTag=name)
                elif validation == "te":
                    tefacts = set()
                    for fr in sevFacts(sev, referenceTag, deduplicate=True):
                        flist = [f for f in sevFacts(sev, names, fr, deduplicate=True)] # just 1 name for te
                        tefacts.update(flist)
                        #revision of 2019-07-16, no warning if no trading symbol (it's now "may" exist)
                        #if len(flist) < 1 and (fr.qname.localName == "TradingSymbol"):
                        #    sevMessage(sev, subType=submissionType, modelObject=[fr]+flist, tag=fr.qname.localName, otherTag=names[0],
                        #               validationMessage="message-missing-exchange")
                    # find any facts without a securities12b
                    for f in sevFacts(sev, names, deduplicate=True): # just 1 name for te
                        if f not in tefacts:
                            if sevFact(sev, referenceTag, f) is None:
                                sevMessage(sev, subType=submissionType, modelObject=f, tag=names[0], otherTags=", ".join(referenceTag), severityVerb="may")
                    del tefacts # dereference
                elif validation in ("ot1", "n2bn1"):
                    for i, name1 in enumerate(names):
                        for fr in sevFacts(sev, name1, deduplicate=True):
                            flist = [sevFact(sev, name2, fr) for name2 in names[i+1:]]
                            if sum(f is not None for f in flist) > 0:
                                sevMessage(sev, subType=submissionType, modelObject=[fr]+flist, tags=", ".join(names))
                elif validation == "t1":
                    t1facts = set()
                    for fr in sevFacts(sev, referenceTag, deduplicate=True):
                        flist = [f for f in sevFacts(sev, names, fr, deduplicate=True)]
                        t1facts.update(flist)
                        if len(flist) > 1: # note that reference tag is a list here
                            sevMessage(sev, subType=submissionType, modelObject=[fr]+flist, tags=", ".join(names), otherTags=", ".join(referenceTag),
                                       severityVerb="may")
                        """
                        if isADR(fr):
                            f = sevFact(sev, "TradingSymbol", fr)
                            if f is not None and sevFact(sev, "SecurityExchangeName", fr) is None:
                                sevMessage(sev, subType=submissionType, modelObject=f,
                                           tag="TradingSymbol", otherTag="SecurityExchangeName", contextID=f.contextID,
                                           validationMessage="message-ADR-no-exchange")
                        """
                    # find any facts without a securities12b
                    for f in sevFacts(sev, names, deduplicate=True):
                        if f not in t1facts:
                            if sevFact(sev, referenceTag, f) is None: # note that reference tag is a list here
                                sevMessage(sev, subType=submissionType, modelObject=f, tags=", ".join(names), otherTags=", ".join(referenceTag), severityVerb="may")
                    del t1facts # dereference
                elif validation in ("de", "de5pm"):
                    t = datetimeNowAtSEC
                    if validation == "de5pm" and (17,31) <= (t.hour, t.minute) <= (23,0):
                        while True: # add 1 day until on a business day
                            t += datetime.timedelta(1)
                            if t.weekday() < 5 and t not in upcomingSECHolidays: # break when not holiday and not weekend
                                break
                    for f in sevFacts(sev, names, deduplicate=True):
                        if not (MIN_DOC_PER_END_DATE <= f.xValue <= t): # f.xValue is a date only, not a date-time
                            sevMessage(sev, subType=submissionType, modelObject=f, tag=name,
                                       value="between 1980-01-01 and {}".format(t.date().isoformat()))
                elif validation == "e503" and "itemsList" in val.params: # don't validate if no itemList (e.g. stand alone)
                    e503facts = set()
                    for f in sevFacts(sev, names, deduplicate=True):
                        e503facts.add(f)
                        if "5.03" not in val.params["itemsList"]:
                            sevMessage(sev, subType=submissionType, modelObject=f, tag=name, headerTag="5.03")
                    if "5.03" in val.params["itemsList"] and not e503facts: # missing a required fact
                        sevMessage(sev, subType=submissionType, modelObject=modelXbrl, tag=names[0], headerTag="5.03")
                elif validation == "503-header-field":
                    if "5.03" not in val.params.get("itemsList",()):
                        eloName = None # cancel validation "elo-name": "submissionHeader.fyEnd"
                elif validation == "sb":
                    _fileNum = val.params.get("entity.repFileNum", "")
                    for f in sevFacts(sev):
                        if f.xValue and (_fileNum.startswith("811-") or _fileNum.startswith("814-")):
                            sevMessage(sev, subType=submissionType, modelObject=f, tag=f.qname.localName, otherTag="entity file number",
                                       value="not starting with 811- or 814-", contextID=f.contextID)
                elif validation in ("x", "xv", "r", "y", "n"):
                    for name in names:
                        f = sevFact(sev, name, requiredContext=not axisKey) # required context match only
                        if f is None or (((f.xValue not in value) ^ ("!not!" in value)) if isinstance(value, (set,list))
                                         else (value is not None and f.xValue != value)):
                            sevMessage(sev, subType=submissionType, modelObject=f, efmSection=efmSection, tag=name, value=value)
                        if f is None and name in eloValueFactNames:
                            missingReqInlineTag = True
                elif validation  == "not-in-future":
                    for name in names:
                        for f in sevFacts(sev, name):
                            if documentType and f.context.endDatetime > documentTypeFact.context.endDatetime:
                                sevMessage(sev, subType=submissionType, modelObject=f, efmSection=efmSection, tag=name, context="context " + f.contextID)

                elif validation in ("ru", "ou"):
                    foundNonUS = None # false means found a us state, true means found a non-us state
                    for name in names:
                        f = sevFact(sev, name)
                        if f is not None:
                            foundNonUS = f.xValue not in value # value is set
                    if foundNonUS == True or (validation == "ru" and foundNonUS is None):
                        sevMessage(sev, subType=submissionType, modelObject=f, efmSection=efmSection, tag=name, value="U.S. state codes")
                elif validation in ("o", "ov"):
                    for name in names:
                        f = sevFact(sev, name)
                        if f is not None and (((f.xValue not in value) ^ ("!not!" in value)) if isinstance(value, (set,list))
                                              else (value is not None and f.xValue != value)):
                            sevMessage(sev, subType=submissionType, modelObject=f, efmSection=efmSection, tag=name, value=value)
                elif validation == "security-axis":
                    for name in names:
                        facts = tuple(f for f in sevFacts(sev, name, deduplicate=True))
                        hasNonDimContext = any((not f.context.qnameDims) for f in facts)
                        hasADRmember = any(isADR(f) for f in facts)
                        if (len(facts) == 1 and not hasNonDimContext and not hasADRmember) or (len(facts) > 1 and hasNonDimContext):
                            sevMessage(sev, subType=submissionType, modelObject=facts, tag=name,
                                       contextIDs=", ".join(sorted(f.contextID for f in facts)))
                elif validation in ("md", "n2c"):
                    mdfacts = defaultdict(set)
                    for f in sevFacts(sev, names, deduplicate=True):
                        if f is not None and (value is None or (
                                              ((f.xValue not in value) ^ ("!not!" in value)) if isinstance(value, (set,list))
                                              else (value is not None and f.xValue != value))):
                            mdfacts[f.context.contextDimAwareHash].add(f)
                    for mdfactset in mdfacts.values():
                        if len(mdfactset) != (1 if validation == "n2c" else len(names)):
                            sevMessage(sev, subType=submissionType, modelObject=mdfactset, tags=", ".join(names))
                    del mdfacts # dereference
                elif validation == "md-unexpected":
                    for f in sevFacts(sev, names, deduplicate=True):
                        sevMessage(sev, subType=submissionType, modelObject=f, tag=f.qname.localName, context=f.contextID)
                elif validation == "n2bn2":
                    for f in sevFacts(sev):
                        if not f.xValue.startswith("814-"):
                            sevMessage(sev, subType=submissionType, modelObject=f, tag=f.qname.localName,
                                       value="a value starting with 814-", contextID=f.contextID)
                elif validation == "n2d":
                    for name in names:
                        f = sevFact(sev, name)
                        fr = sevFact(sev, referenceTag, f)
                        if fr is None and f is not None:
                            sevMessage(sev, subType=submissionType, modelObject=sevFacts(sev), tag=name, otherTag=referenceTag, value=fr.xValue, contextID=fr.contextID)
                if eloName:
                    expectedEloParams.add(eloName)
                    for name in names:
                        f = sevFact(sev, name)
                        if f is not None and eloName in val.params and not deiParamEqual(name, f.xValue, val.params[eloName]):
                            sevMessage(sev, messageKey=sev.get("elo-match-message", "dq-0540-{tag}-Value"),
                                       subType=submissionType, modelObject=f, efmSection="6.5.40",
                                       tag=name, value=str(f.xValue), headerTag=eloName, valueOfHeaderTag=val.params[eloName])

                if storeDbName:
                    f = sevFact(sev, names)
                    if f is not None:
                        storeDbObjectFacts[storeDbObject][storeDbName] = eloValueOfFact(names[0], f.xValue)
                    elif storeDbName not in storeDbObjectFacts:
                        storeDbObjectFacts[storeDbObject][storeDbName] = None


            del unexpectedDeiNameEfmSects, expectedDeiNames # dereference

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

        # log extracted facts
        if isInlineXbrl and (extractedCoverFacts or storeDbObjectFacts):
            if storeDbObjectFacts.get("eloValuesFromFacts"):
                storeDbObjectFacts["eloValuesFromFacts"]["missingReqInlineTag"] = ["no", "yes"][missingReqInlineTag]
            contextualFactNameSets = (("Security12bTitle", "TradingSymbol"), ("Security12gTitle", "TradingSymbol"))
            exchangeFactName = "SecurityExchangeName"
            exchangeAxisQN = qname(deiNamespaceURI, "EntityListingsExchangeAxis")
            hasADR = False
            cEqualCoverFacts = defaultdict(dict)
            # find c-equivalent Title, Registration and Symbols
            for name, facts in extractedCoverFacts.items():
                for f in facts:
                    cEqualCoverFacts[f.context.contextDimAwareHash][name] = f
                    if not hasADR and any(d.dimensionQname.localName in deiCAxes
                                          and d.memberQname == deiADRmember
                                          for d in f.context.qnameDims.values()):
                        hasADR = True
            hasOTC = not hasADR and not extractedCoverFacts.get(exchangeFactName, ())
            # organize by "record" of in hierarchical order of extractionCoverTagNames
            coverFactRecords = set()
            def addCoverFactRecord(facts):
                nameValuePairs = []
                for f in facts:
                    if isinstance(f, tuple):
                        nameValuePairs.append(f)
                    elif f is not None:
                        nameValuePairs.append( (f.qname.localName, f.xValue) )
                coverFactRecords.add(tuple(sorted(nameValuePairs)))

            if hasOTC:
                for contextualFactNames in contextualFactNameSets:
                    for cEqualFacts in cEqualCoverFacts.values():
                        if contextualFactNames == cEqualFacts.keys(): # context has all OTC facts
                            addCoverFactRecord(list(cEqualFacts.values()) + [(exchangeFactName,None)])
            else:
                for contextualFactNames in contextualFactNameSets:
                    for cEqualFacts in cEqualCoverFacts.values():
                        if set(contextualFactNames) <= cEqualFacts.keys(): # context has all OTC facts
                            cntx = cEqualFacts[contextualFactNames[0]].context # can be any fact's context as they're all same context
                            classOfStockDim = None
                            for d in cntx.qnameDims.values():
                                if d.dimensionQname.localName in deiCAxes:
                                    classOfStockDim = d
                                    break
                            if hasADR and (d is None or d.memberQname != deiADRmember):
                                continue
                            rec = [cEqualFacts[name] for name in contextualFactNames]
                            if exchangeFactName in cEqualFacts:
                                rec.append(cEqualFacts[exchangeFactName])
                                addCoverFactRecord(rec)
                            else:
                                for f in extractedCoverFacts[exchangeFactName]:
                                    fdims = f.context.qnameDims
                                    addThisExchFact = False
                                    if exchangeAxisQN in cntx.qnameDims:
                                        if cntx.qnameDims[exchangeAxisQN].isEqualTo(fdims.get(exchangeAxisQN)):
                                            addThisExchFact = True
                                    elif classOfStockDim is not None and classOfStockDim.dimensionQname in fdims:
                                        if classOfStockDim.isEqualTo(fdims[classOfStockDim.dimensionQname]):
                                            addThisExchFact = True
                                    # may need better disaggregation control
                                    else:
                                        addThisExchFact = True
                                    if addThisExchFact:
                                        rec.append(f)
                                        # override any inherited facts with exch c-equal facts
                                        exchCEqualFacts = cEqualCoverFacts[f.context.contextDimAwareHash]
                                        for name in contextualFactNames:
                                            if name in exchCEqualFacts:
                                                rec.append(f)
                                        addCoverFactRecord(rec)
            jsonParam = OrderedDict()
            jsonParam["coverFacts"] = [dict(keyval for keyval in rec) for rec in sorted(coverFactRecords)]
            for _objName, _objFacts in sorted(storeDbObjectFacts.items(), key=lambda i:i[0]):
                jsonParam[_objName] = _objFacts
            modelXbrl.log("INFO-RESULT",
                          "EFM.coverFacts",
                          "Extracted cover facts returned as json parameter",
                          modelXbrl=modelXbrl,
                          json=json.dumps(jsonParam))

        #6.5.27 footnote elements, etc
        footnoteLinkNbr = 0
        if isInlineXbrl and isEFM:
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
                                    edgarCode="du-0528-Footnote-Role-Missing",
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
    if isInlineXbrl and isEFM:
        hiddenEltIds = {}
        presentedHiddenEltIds = defaultdict(list)
        eligibleForTransformHiddenFacts = []
        requiredToDisplayFacts = []
        requiredToDisplayFactIds = {}
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements: # ix root elements
            ixdsHtmlTree = ixdsHtmlRootElt.getroottree()
            if ixdsHtmlRootElt.tag in ("html", "xhtml") or (
                    isinstance(ixdsHtmlRootElt, ModelObject) and not ixdsHtmlRootElt.namespaceURI):
                modelXbrl.error("EFM.5.02.05.xhtmlNamespaceMissing",
                    _("InlineXBRL root element <%(element)s> MUST be html and have the xhtml namespace."),
                    modelObject=ixdsHtmlRootElt, element=ixdsHtmlRootElt.tag)
            nsRequiredPrefixes = {"http://www.w3.org/1999/xhtml": "xhtml",
                                  "http://www.xbrl.org/2013/inlineXBRL": "ix",
                                  "http://www.xbrl.org/inlineXBRL/transformation/2015-02-26": "ixt",
                                  "http://www.sec.gov/inlineXBRL/transformation/2015-08-31": "ixt-sec"}
            for prefix, ns in ((None, "http://www.w3.org/1999/xhtml"),
                               ("ix", "http://www.xbrl.org/2013/inlineXBRL")):
                for _prefix, _ns in ixdsHtmlRootElt.nsmap.items():
                    if _ns == ns and _prefix != prefix:
                        modelXbrl.error("EFM.5.02.05.standardNamespacePrefix",
                            _("The prefix %(submittedPrefix)s must be replaced by %(recommendedPrefix)s for standard namespace %(namespace)s."),
                            edgarCode="ix-0502-Standard-Namespace-Prefix",
                            modelObject=ixdsHtmlRootElt, submittedPrefix=_prefix, recommendedPrefix=prefix, namespace=ns)
            ixNStag = ixdsHtmlRootElt.modelDocument.ixNStag
            ixTags = set(ixNStag + ln for ln in ("nonNumeric", "nonFraction", "references", "relationship"))
            unsupportedTrFacts = []
            unsupportedTrNamespaces = set()
            unsupportedNamespacePrefixes = defaultdict(set)
            for tag in ixTags:
                for ixElt in ixdsHtmlRootElt.iterdescendants(tag=tag):
                    if isinstance(ixElt,ModelObject):
                        if ixElt.get("target"):
                            modelXbrl.error("EFM.5.02.05.targetDisallowed",
                                _("Inline element %(localName)s has disallowed target attribute '%(target)s'."),
                                modelObject=ixElt, localName=ixElt.elementQname, target=ixElt.get("target"))
                        if isinstance(ixElt, ModelInlineFact):
                            format = ixElt.format
                            if format:
                                if format.namespaceURI not in ixTrRegistries:
                                    unsupportedTrNamespaces.add(format.namespaceURI)
                                    unsupportedTrFacts.append(ixElt)
                                elif format.prefix != ixTrRegistries[format.namespaceURI]:
                                    unsupportedNamespacePrefixes[(format.prefix,format.namespaceURI)].add(ixElt)
            if unsupportedTrFacts:
                modelXbrl.error("EFM.5.02.05.12.unupportedTransformationRegistry",
                    _("Inline elements have disallowed transformation registries %(unsupportedRegistries)s."),
                    edgarCode="ix-0512-Unsupported-Transformation-Registry",
                    modelObject=unsupportedTrFacts, unsupportedRegistries=", ".join(sorted(unsupportedTrNamespaces)))
            for (pfx,ns),facts in unsupportedNamespacePrefixes.items():
                modelXbrl.error("EFM.5.02.05.standardNamespacePrefix",
                    _("The prefix %(submittedPrefix)s must be replaced by %(recommendedPrefix)s for standard namespace %(namespace)s."),
                    edgarCode="ix-0502-Standard-Namespace-Prefix",
                    modelObject=facts, submittedPrefix=pfx, recommendedPrefix=ixTrRegistries[ns], namespace=ns)

            del unsupportedTrFacts, unsupportedTrNamespaces, unsupportedNamespacePrefixes
            for ixElt in ixdsHtmlRootElt.iterdescendants(tag=ixNStag+"tuple"):
                if isinstance(ixElt,ModelObject):
                    modelXbrl.error("EFM.5.02.05.tupleDisallowed",
                        _("Inline tuple %(qname)s is disallowed."),
                        modelObject=ixElt, qname=ixElt.qname)
            for ixElt in ixdsHtmlRootElt.iterdescendants(tag=ixNStag+"fraction"):
                if isinstance(ixElt,ModelObject):
                    modelXbrl.error("EFM.5.02.05.fractionDisallowed",
                        _("Inline fraction %(qname)s is disallowed."),
                        modelObject=ixElt, qname=ixElt.qname)
            if ixdsHtmlRootElt.getroottree().docinfo.doctype:
                modelXbrl.error("EFM.5.02.05.doctypeDisallowed",
                    _("Inline HTML %(doctype)s is disallowed."),
                    modelObject=ixdsHtmlRootElt, doctype=modelXbrl.modelDocument.xmlDocument.docinfo.doctype)

            for ixHiddenElt in ixdsHtmlRootElt.iterdescendants(tag=ixNStag + "hidden"):
                for tag in (ixNStag + "nonNumeric", ixNStag+"nonFraction"):
                    for ixElt in ixHiddenElt.iterdescendants(tag=tag):
                        if (getattr(ixElt, "xValid", 0) >= VALID and # may not be validated
                            (ixElt.qname in coverVisibleQNames
                             or not hideableNamespacesPattern.match(ixElt.qname.namespaceURI)) and
                            (not isRR or not rrUntransformableEltsPattern.match(ixElt.qname.localName)
                                      or abbreviatedNamespace(ixElt.qname.namespaceURI, NOYEAR) != "rr")):
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
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
            for ixElt in ixdsHtmlRootElt.getroottree().iterfind("//{http://www.w3.org/1999/xhtml}*[@style]"):
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
                (ixElt.qname in coverVisibleQNames
                 or not ixElt.qname.namespaceURI.startswith("http://xbrl.sec.gov/dei/")) and
                (ixElt.concept.baseXsdType in untransformableTypes or ixElt.isNil)):
                requiredToDisplayFacts.append(ixElt)
        undisplayedCoverFacts = dict((f, coverVisibleQNames[f.qname])
                                 for f in requiredToDisplayFacts
                                 if f.qname in coverVisibleQNames)
        for f in undisplayedCoverFacts:
            requiredToDisplayFacts.remove(f)
        if requiredToDisplayFacts:
            modelXbrl.warning("EFM.5.02.05.14.hidden-fact-not-referenced",
                _("%(countUnreferenced)s fact(s) appearing in ix:hidden were not referenced by any -sec-ix-hidden style property: %(elements)s"),
                edgarCode="ix-0514-Hidden-Fact-Not-Referenced",
                modelObject=requiredToDisplayFacts,
                countUnreferenced=len(requiredToDisplayFacts),
                elements=", ".join(sorted(set(str(f.qname) for f in requiredToDisplayFacts))))
        if undisplayedCoverFacts:
            for level, err, verb in (("WARNING", False, "should"), ("ERROR", True, "MUST")):
                facts = [f for f, _err in undisplayedCoverFacts.items() if _err == err]
                if facts:
                    modelXbrl.log(level, "EFM.6.05.45.cover-page-fact-not-visible",
                        _("Submission type %(subType)s has %(countUnreferenced)s cover page fact(s) in ix:hidden that %(verb)s be visible or referenced by an -sec-ix-hidden style property: %(elements)s"),
                        edgarCode="dq-0545-Cover-Page-Fact-Not-Visible",
                        modelObject=facts, subType=submissionType, countUnreferenced=len(facts), verb=verb,
                        elements=", ".join(sorted(set(f.qname.localName for f in facts))))
                del facts
        del eligibleForTransformHiddenFacts, hiddenEltIds, presentedHiddenEltIds, requiredToDisplayFacts, undisplayedCoverFacts
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
                if (concept.modelDocument.targetNamespace not in disclosureSystem.standardTaxonomiesDict and
                    concept.modelDocument.targetNamespace not in val.otherStandardTaxonomies):
                    modelXbrl.error(("EFM.6.18.01", "GFM.1.9.1"),
                        _("Your filing provides a reference, '%(xml)s', for an custom concept in extension taxonomy, %(concept)s.  "
                          "Please remove this reference."),
                        edgarCode="cp-1801-Custom-Element-Has-Reference",
                        modelObject=modelReference, concept=concept.qname, text=text, xml=XmlUtil.xmlstring(modelReference, stripXmlns=True, contentsOnly=True))
                elif isEFM and not isStandardUri(val, modelRefRel.modelDocument.uri) and concept.modelDocument.targetNamespace not in val.otherStandardTaxonomies:
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
    def elementsReferencingTxClass(txClass):
        return set(rd.referringModelObject
                   for t in flattenSequence(txClass)
                   for doc in modelXbrl.urlDocs.values()
                   for d, rd in doc.referencesDocument.items()
                   if t in abbreviatedNamespace(d.targetNamespace,WITHYEARandWILD))
    if isEFM:
        t = set(conflictClassFromNamespace(d.targetNamespace) for d in modelXbrl.urlDocs.values())
        t &= compatibleTaxonomies["checked-taxonomies"] # only consider checked taxonomy classes
        conflictClass = None
        for ti, ts in compatibleTaxonomies["compatible-classes"].items(): # OrderedDict
            if ti in t:
                conflictClasses = t - {ti} - ts
                if conflictClasses:
                    conflictClass = "-".join([ti] + sorted(conflictClasses))
                break # match found
        if not conflictClass: # look for same taxonomy class in multiple years
            for ti in t:
                tiClass = ti.partition('/')[0]
                if any(ts.startswith(tiClass) for ts in (t - {ti})):
                    conflictClasses = sorted(ts for ts in t if ts.startswith(tiClass))
                    conflictClass = "-".join(conflictClasses)
        if conflictClass:
            modelXbrl.error("EFM.6.22.03.incompatibleSchemas",
                _("References for conflicting standard taxonomies %(conflictClass)s are not allowed in same DTS %(namespaceConflicts)s"),
                edgarCode="cp-2203-Incompatible-Taxonomy-Versions", conflictClass=conflictClass,
                modelObject=elementsReferencingTxClass(conflictClasses), namespaceConflicts=", ".join(sorted(t)))
        if any(ti.startswith("rr/") for ti in t) and documentType not in docTypesRequiringRrSchema:
            modelXbrl.error("EFM.6.22.03.incompatibleTaxonomyDocumentType",
                _("Taxonomy class %(conflictClass)s may not be used with document type %(documentType)s"),
                modelObject=elementsReferencingTxClass("rr/*"), conflictClass="rr/*", documentType=documentType)
        if any(ti.startswith("ifrs/") for ti in t) and documentType in docTypesNotAllowingIfrs:
            modelXbrl.error("EFM.6.22.03.incompatibleTaxonomyDocumentType",
                _("Taxonomy class %(conflictClass)s may not be used with document type %(documentType)s"),
                modelObject=elementsReferencingTxClass("ifrs/*"), conflictClass="ifrs/*", documentType=documentType)
        if isInlineXbrl and documentType in docTypesNotAllowingInlineXBRL:
            modelXbrl.error("EFM.6.22.03.incompatibleInlineDocumentType",
                _("Inline XBRL may not be used with document type %(documentType)s"),
                modelObject=modelXbrl, conflictClass="inline XBRL", documentType=documentType)
        if documentType is not None and not val.hasExtensionSchema and documentType != "L SDR": # and disclosureSystemVersion[0] <= 58:
            modelXbrl.error("EFM.6.03.10",
                            _("%(documentType)s report is missing a extension schema file."),
                            edgarCode="cp-0310-Missing-Schema",
                            modelObject=modelXbrl, documentType=documentType)

        # 6.7.12: check link role orders
        if submissionType not in submissionTypesExemptFromRoleOrder and documentType not in docTypesExemptFromRoleOrder:
            seqDefRoleTypes = []
            for roleURI in modelXbrl.relationshipSet(XbrlConst.parentChild).linkRoleUris:
                for roleType in modelXbrl.roleTypes.get(roleURI,()):
                    match = efmRoleDefinitionPattern.match(roleType.definitionNotStripped)
                    if match and modelXbrl.relationshipSet(XbrlConst.parentChild, roleURI).modelRelationships:
                        seqDefRoleTypes.append((match.group(1), roleType))
            priorLevel = level = (0, None, None, None) # (sort order, level, description)
            for seq, roleType in sorted(seqDefRoleTypes, key=lambda s: s[0]): # sort on sequence only
                definition = roleType.definitionNotStripped
                if '- Document - ' in definition: level = (0, "0, Cover", definition, roleType)
                elif ' - Statement - ' in definition: level = (1, "1, Statement", definition, roleType)
                elif ' (Detail' in definition: level = (5, "4, Detail", definition, roleType)
                elif ' (Table' in definition: level = (4, "3, Table", definition, roleType)
                elif ' (Polic' in definition: level = (3, "2, Policy", definition, roleType)
                else: level = (2, "1, Note", definition, roleType)
                if priorLevel[1] is not None and level[0] < priorLevel[0]:
                    modelXbrl.warning("EFM.6.07.12.presentationBaseSetOrder",
                                      _("Role '%(descriptionX)s', a level %(levelX)s role, appears before '%(descriptionY)s', a level %(levelY)s role."),
                                        edgarCode="dq-0712-Presentation-Base-Set-Order",
                                        modelObject=(priorLevel[3], level[3]), descriptionX=priorLevel[2], levelX=priorLevel[1],
                                        descriptionY=level[2], levelY=level[1])
                priorLevel = level
            del seqDefRoleTypes, priorLevel, level # dereference

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
                            if order in orderRels and relTo is not None:
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
                                            modelObject=(relFrom,relTo), axis=relFrom.qname,
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

    # 6.9.10 checks on custom arcs
    if isEFM:
        # find CEF,  VIP or ECD
        for d in modelXbrl.urlDocs.values():
            ns = d.targetNamespace
            lbVal = linkbaseValidations.get(abbreviatedNamespace(d.targetNamespace, NOYEAR))
            if d.type == ModelDocument.Type.SCHEMA and lbVal:
                preSrcConcepts = set(modelXbrl.qnameConcepts.get(qname(ns,c)) for c in lbVal.preSources)
                if lbVal.efmPre:
                    for rel in modelXbrl.relationshipSet(XbrlConst.parentChild).modelRelationships:
                        if not isStandardUri(val, rel.modelDocument.uri) and rel.modelDocument.targetNamespace not in val.otherStandardTaxonomies:
                            relFrom = rel.fromModelObject
                            relTo = rel.toModelObject
                            if relFrom is not None and relTo is not None:
                                relset = modelXbrl.relationshipSet(XbrlConst.parentChild, rel.linkrole)
                                roleMatch = lbVal.elrPre.match(rel.linkrole)
                                if ((roleMatch and relTo.qname.namespaceURI != ns and (
                                             not relTo.type.isDomainItemType or (lbVal.preSources and not
                                             any(relset.isRelated(c, "descendant-or-self", relFrom) for c in preSrcConcepts))))
                                    or
                                    (not roleMatch and not lbVal.preCustELRs and  (relFrom.qname.namespaceURI == ns or relTo.qname.namespaceURI == ns))):
                                    modelXbrl.error(f"EFM.{lbVal.efmPre}.relationshipNotPermitted",
                                        _("The %(arcrole)s relationship from %(conceptFrom)s to %(conceptTo)s, link role %(linkroleDefinition)s, is not permitted."),
                                        edgarCode=f"du-{lbVal.efmPre[2:4]}{lbVal.efmPre[5:]}-Relationship-Not-Permitted",
                                        modelObject=(rel,relFrom,relTo), arc=rel.qname, arcrole=rel.arcrole,
                                        linkrole=rel.linkrole, linkroleDefinition=modelXbrl.roleTypeDefinition(rel.linkrole),
                                        conceptFrom=relFrom.qname, conceptTo=relTo.qname)
                for rel in modelXbrl.relationshipSet(XbrlConst.summationItem).modelRelationships:
                    if not isStandardUri(val, rel.modelDocument.uri) and rel.modelDocument.targetNamespace not in val.otherStandardTaxonomies:
                        relFrom = rel.fromModelObject
                        relTo = rel.toModelObject
                        if relFrom is not None and relTo is not None:
                            if relFrom.qname.namespaceURI == ns or relTo.qname.namespaceURI == ns:
                                modelXbrl.error(f"EFM.{lbVal.efmCal}.relationshipNotPermitted",
                                    _("The %(arcrole)s relationship from %(conceptFrom)s to %(conceptTo)s, link role %(linkroleDefinition)s, is not permitted."),
                                    edgarCode=f"du-{lbVal.efmCal[2:4]}{lbVal.efmCal[5:]}-Relationship-Not-Permitted",
                                    modelObject=(rel,relFrom,relTo), arc=rel.qname, arcrole=rel.arcrole,
                                    linkrole=rel.linkrole, linkroleDefinition=modelXbrl.roleTypeDefinition(rel.linkrole),
                                    conceptFrom=relFrom.qname, conceptTo=relTo.qname)
                for rel in modelXbrl.relationshipSet("XBRL-dimensions").modelRelationships:
                    if not isStandardUri(val, rel.modelDocument.uri) and rel.modelDocument.targetNamespace not in val.otherStandardTaxonomies:
                        relFrom = rel.fromModelObject
                        relTo = rel.toModelObject
                        if relFrom is not None and relTo is not None:
                            if ((relFrom.qname.namespaceURI == ns or relTo.qname.namespaceURI == ns)
                                and not (
                                  rel.arcrole == XbrlConst.domainMember and (
                                    (relFrom.qname.namespaceURI == ns and relTo.qname.namespaceURI == ns and lbVal.elrDefInNs.match(rel.linkrole))
                                    or
                                    (relFrom.qname.namespaceURI == ns and lbVal.elrDefExNs.match(rel.linkrole))
                                  ))):
                                modelXbrl.error(f"EFM.{lbVal.efmDef}.relationshipNotPermitted",
                                    _("The %(arcrole)s relationship from %(conceptFrom)s to %(conceptTo)s, link role %(linkroleDefinition)s, is not permitted."),
                                    edgarCode=f"du-{lbVal.efmDef[2:4]}{lbVal.efmDef[5:]}-Relationship-Not-Permitted",
                                    modelObject=(rel,relFrom,relTo), arc=rel.qname, arcrole=rel.arcrole,
                                    linkrole=rel.linkrole, linkroleDefinition=modelXbrl.roleTypeDefinition(rel.linkrole),
                                    conceptFrom=relFrom.qname, conceptTo=relTo.qname)


    del localPreferredLabels # dereference
    del usedCalcFromTosELR

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

    # DQC.US rules
    for dqcRuleName, dqcRule in dqcRules.items(): # note this is an OrderedDict to preserve rule execution order
        if dqcRuleName == "copyright": # first in JSON OrderedDict, initialize common variables for rule
            if ugtRels:
                ugtAxisDefaults = ugtRels["axis-defaults"]
            hasDocPerEndDateFact = documentPeriodEndDateFact is not None and documentPeriodEndDateFact.xValid >= VALID and documentPeriodEndDateFact.xValue and documentPeriodEndDateFact.context.endDatetime
            if hasDocPerEndDateFact and documentPeriodEndDate:
                maxEndDate = max(documentPeriodEndDate, documentPeriodEndDateFact.context.endDatetime)
            else:
                maxEndDate = documentPeriodEndDate # note that this may be None if there is no documentPeriodEndDate
            continue
        elif not dqcRuleName.startswith("DQC.US."):
            continue # skip description and any other non-rule entries
        msg = dqcRule.get("message")
        edgarCode = "dqc-{}-{}".format(dqcRuleName[-4:], "-".join(dqcRule["name"].title().split()))
        if dqcRuleName == "DQC.US.0001" and ugtRels:
            ugtAxisMembers = ugtRels["axes"]
            warnedFactsByQn = defaultdict(list)
            for id, rule in dqcRule["rules"].items():
                for axisConcept in modelXbrl.nameConcepts.get(rule["axis"],()):
                    membersOfExtensionAxis = axisMemQnames(modelXbrl, axisConcept.qname, rule["extensions-allowed"] == "Yes") # set of QNames
                    allowableMembers = ugtAxisMembers[axisConcept.name] if rule["axis-descendants"] == "Yes" else set()
                    for otherAxis in rule.get("additional-axes",EMPTY_LIST):
                        allowableMembers |= ugtAxisMembers[otherAxis]
                    for otherMemName in rule.get("additional-members",EMPTY_LIST) + rule.get("extension-members",EMPTY_LIST):
                        for otherMemConcept in modelXbrl.nameConcepts.get(otherMemName,()):
                            allowableMembers.add(otherMemConcept.qname)
                    for childExtensionMember in rule.get("child-extension-members",EMPTY_LIST):
                        allowableMembers |= memChildQnames(modelXbrl, childExtensionMember)
                    unallowedMembers = membersOfExtensionAxis - allowableMembers
                    if "unallowed-axes" in rule:
                        unallowedMembers &= set.union(*(ugtAxisMembers[a] for a in rule.get("unallowed-axes")))
                    unallowedMembersUsedByFacts = set()
                    if unallowedMembers:
                        for f in modelXbrl.factsByDimMemQname(axisConcept.qname, None): # None also includes default members
                            dimValueQname = f.context.dimMemberQname(axisConcept.qname) # include default members
                            if dimValueQname in unallowedMembers:
                                unallowedMembersUsedByFacts.add(dimValueQname)
                                if dimValueQname.namespaceURI not in disclosureSystem.standardTaxonomiesDict: # is extension member concept
                                    issue = {"No": "Extension members should not be used with this axis. ",
                                             "Limited": "This extension member should not be used with this axis. ",
                                             "Yes": "Extension member is not allowed by rule. "
                                             }[rule["extensions-allowed"]]
                                elif rule["axis-descendants"] == "None":
                                    issue = "Only extension members can be used with this axis. "
                                else:
                                    issue = "Base taxonomy member is not allowed by rule. "
                                if not any(f.isDuplicateOf(warnedFact) for warnedFact in warnedFactsByQn[f.qname]):
                                    warnedFactsByQn[f.qname].append(f)
                                    modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg)),
                                        modelObject=f, name=f.qname, value=strTruncate(f.value,128), axis=axisConcept.qname, member=dimValueQname, issue=issue,
                                        contextID=f.context.id, unitID=f.unit.id if f.unit is not None else "(none)",
                                        edgarCode=edgarCode, ruleElementId=id)
                    unusedUnallowed = unallowedMembers - unallowedMembersUsedByFacts
                    for unusedMember in unusedUnallowed: # report one member per message for result comparability to XBRL-US implementation
                        modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(dqcRule["message-unreported"])),
                            modelObject=modelXbrl, axis=axisConcept.qname, member=unusedMember,
                            edgarCode=edgarCode+"-Unreported", ruleElementId=id)
                    if rule.get("axis-default-must-match-UGT") == "Yes" and rule["axis"] in ugtAxisDefaults:
                        ugtDefaultMem = ugtAxisDefaults[rule["axis"]]
                        for dimDefRel in modelXbrl.relationshipSet(XbrlConst.dimensionDefault).fromModelObject(axisConcept):
                            if dimDefRel.toModelObject is not None:
                                extDefaultQname = dimDefRel.toModelObject.qname
                                if extDefaultQname.localName != ugtDefaultMem:
                                    modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(dqcRule["message-disallowed-default"])),
                                        modelObject=modelXbrl, axis=axisConcept.qname, default=extDefaultQname, allowedDefault=ugtDefaultMem,
                                        edgarCode=edgarCode+"-Disallowed-Default", ruleElementId=id)
            del warnedFactsByQn # dereference objects

        elif dqcRuleName == "DQC.US.0004":
            for id, rule in dqcRule["rules"].items():
                # first check if there's a calc-sum and calc-items
                sumLn = rule.get("calc-sum")
                blkAxis = rule.get("blocking-axes",())
                alts = rule.get("alternatives",EMPTY_DICT)
                tolerance = rule["tolerance"]
                linkroleURIs = (None,) # for IDs without calc network evaluation
                if sumLn in modelXbrl.nameConcepts and "calc-items" in rule: # (dqc_us_rules/pull/544)
                    sumConcept = modelXbrl.nameConcepts[sumLn][0]
                    linkroleURIs = OrderedSet(modelLink.role
                                              for modelLink in val.modelXbrl.baseSets[(XbrlConst.summationItem,None,None,None)]
                                              if modelXbrl.relationshipSet(XbrlConst.summationItem, modelLink.role , None, None).fromModelObject(sumConcept))

                for linkroleUri in linkroleURIs: # evaluate by network where applicable to ID
                    itemWeights = {}
                    summingNetworkChildren = False
                    if linkroleUri: # has calc network evaluation
                        itemWeights = dict((rel.toModelObject.name, rel.weightDecimal)
                                            for rel in modelXbrl.relationshipSet(XbrlConst.summationItem, linkroleUri, None, None).fromModelObject(sumConcept)
                                            if rel.toModelObject is not None)
                        if set(rule.get("calc-items")) <= itemWeights.keys():
                            itemLns = list(itemWeights.keys())
                            sumLn = rule.get("calc-sum") # may be reset on previous linkroleUri in loop
                            summingNetworkChildren = True
                        else:
                            sumLn = None
                    if not sumLn:
                        sumLn = rule["sum"]
                        itemLns = rule["items"]
                    bindings = factBindings(val.modelXbrl, flattenToSet( (sumLn, itemLns, alts.values() )), nils=False)
                    for b in bindings.values():
                        _itemLns = itemLns.copy() # need fresh array to use for substituting
                        _sumLn = sumLn
                        for iLn in itemLns: # check if substitution is necessary
                            if iLn not in b and iLn in alts:
                                for aLns in alts[iLn]:
                                    if all(aLn in b for aLn in aLns):
                                        p = _itemLns.index(iLn) # replace iLn with alts that all are in binding
                                        _itemLns[p:p+1] = aLns
                                        break
                        if _sumLn not in b and _sumLn in alts:
                            for aLns in alts[sumLn]:
                                if aLns and aLns[0] in b:
                                    _sumLn = aLns[0]
                                    break
                        if summingNetworkChildren: # use actually-present contributing items in binding
                            _itemLns = b.keys() - {_sumLn}
                        if _sumLn in b and _itemLns and all(ln in b for ln in _itemLns) and not (
                            any(ax in f.context.qnameDims for ax in blkAxis for f in b.values())):
                            dec = leastDecimals(b, flattenToSet( (_sumLn, _itemLns) ))
                            sumFact = b[_sumLn]
                            itemFacts = [b[ln] for ln in _itemLns]
                            sfNil = sumFact.isNil
                            allIfNil = itemFacts and all(f.isNil for f in itemFacts)
                            if sfNil:
                                sumValue = "(nil)"
                            else:
                                sumValue = roundValue(sumFact.xValue, decimals=dec)
                            if not allIfNil:
                                itemValues = tuple(roundValue(f.xValue * itemWeights.get(f.qname.localName, ONE), decimals=dec)
                                                   for f in itemFacts if not f.isNil)
                            try:
                                if ((not (sfNil & allIfNil)) and (
                                    (sfNil ^ allIfNil) or
                                    abs(sumValue - sum(itemValues)) > pow(10, -dec) * tolerance)):
                                    modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg)),
                                        modelObject=b.values(), sumName=_sumLn, sumValue=str(sumValue),
                                        itemNames=", ".join(_itemLns), itemValues=" + ".join(str(v) for v in itemValues),
                                        contextID=sumFact.context.id, unitID=sumFact.unit.id if sumFact.unit is not None else "(none)",
                                        edgarCode=edgarCode, ruleElementId=id)
                            except:
                                print("exception")
        elif dqcRuleName == "DQC.US.0005" and  documentType not in dqcRule["excluded-document-types"] and maxEndDate:
            for id, rule in dqcRule["rules"].items():
                msg = rule.get("message") # each rule has a message
                if "name" in rule:
                    facts = modelXbrl.factsByLocalName.get(rule["name"],())
                    maxEndDateComparedTo = maxEndDate.__gt__ # f.endDate < maxEndDate
                elif "axis" in rule and rule["axis"] in modelXbrl.nameConcepts:
                    axisQn = modelXbrl.nameConcepts[rule["axis"]][0].qname
                    if rule.get("member") in modelXbrl.nameConcepts:
                        memQn = modelXbrl.nameConcepts[rule.get("member")][0].qname
                    else:
                        memQn = NONDEFAULT
                    facts = modelXbrl.factsByDimMemQname(axisQn, memQn)
                    maxEndDateComparedTo = maxEndDate.__ge__ # f.endDate <= maxEndDate
                else:
                    continue
                for f in facts:
                    if maxEndDateComparedTo(f.context.endDatetime):
                        modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg)),
                                          modelObject=f, name=f.qname.localName, value=f.xValue,
                                          date=XmlUtil.dateunionValue(f.context.endDatetime, subtractOneDay=True),
                                          endDate=XmlUtil.dateunionValue(maxEndDate, subtractOneDay=True),
                                          axis=rule.get("axis"), member=rule.get("member"),
                                          contextID=f.context.id, unitID=f.unit.id if f.unit is not None else "(none)",
                                          edgarCode=edgarCode + '-' + id, ruleElementId=id)
        elif (dqcRuleName == "DQC.US.0006"
              and documentType not in dqcRule["excluded-document-types"]
              and documentType and "T" not in documentType):
            for id, rule in dqcRule["rules"].items():
                focusRange = rule["focus-range"].get(deiItems.get("DocumentFiscalPeriodFocus"))
                if focusRange and not any(modelXbrl.factsByLocalName.get(n,()) for n in rule["blocking-names"]):
                    def r6facts():
                        for n in rule["names"]:
                            for f in modelXbrl.factsByLocalName.get(n,()):
                                yield f
                        for n in ("{http://www.xbrl.org/dtr/type/non-numeric}textBlockItemType",
                                  "{http://www.xbrl.org/dtr/type/2020-01-21}textBlockItemType"):
                            for f in modelXbrl.factsByDatatype(True, qname(n)):
                                yield f
                    for f in r6facts():
                        durationDays = (f.context.endDatetime - f.context.startDatetime).days
                        if not (focusRange[0] <= durationDays <= focusRange[1]):
                            modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg)),
                                              modelObject=f, name=f.qname.localName, durationDays=durationDays, documentFiscalPeriodFocus=deiItems.get("DocumentFiscalPeriodFocus"),
                                              startDate=XmlUtil.dateunionValue(f.context.startDatetime), endDate=XmlUtil.dateunionValue(f.context.endDatetime, subtractOneDay=True),
                                              contextID=f.context.id, unitID=f.unit.id if f.unit is not None else "(none)",
                                              edgarCode=edgarCode, ruleElementId=id)
        elif dqcRuleName == "DQC.US.0008" and ugtRels:
            for id, rule in dqcRule["rules"].items():
                ugtCalcs = ugtRels["calcs"]
                for rel in val.summationItemRelsSetAllELRs.modelRelationships:
                    relFrom = rel.fromModelObject
                    relTo = rel.toModelObject
                    if (relFrom is not None and relTo is not None and
                        relFrom.qname in ugtCalcs.get(rel.weight,EMPTY_DICT).get(relTo.qname,EMPTY_DICT)):
                        modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg)),
                                          modelObject=rel, linkrole=rel.linkrole, linkroleDefinition=modelXbrl.roleTypeDefinition(rel.linkrole),
                                          conceptFrom=relFrom.qname, conceptTo=relTo.qname,
                                          edgarCode=edgarCode, ruleElementId=id)

        elif dqcRuleName == "DQC.US.0009":
            for id, rule in dqcRule["rules"].items():
                lesserLn = rule["lesser"]
                greaterLn = rule["greater"]
                msg = rule.get("use-message","message") # general message defaults to "message"
                ruleMsg = dqcRule[msg]
                ruleEdgarCode = edgarCode + msg.title()[7:]
                bindings = factBindings(val.modelXbrl, (lesserLn, greaterLn) )
                for b in bindings.values():
                    if lesserLn in b and greaterLn in b:
                        dec = leastDecimals(b, (lesserLn, greaterLn) )
                        lesserFact = b[lesserLn]
                        lesserValue = roundValue(lesserFact.xValue, decimals=dec)
                        greaterValue = roundValue(b[greaterLn].xValue, decimals=dec)
                        if lesserValue > greaterValue:
                            modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(ruleMsg)),
                                modelObject=b.values(), lesserName=lesserLn, lesserValue=str(lesserValue), greaterName=greaterLn, greaterValue=str(greaterValue),
                                contextID=lesserFact.context.id, unitID=lesserFact.unit.id if lesserFact.unit is not None else "(none)",
                                edgarCode=ruleEdgarCode, ruleElementId=id)
        elif dqcRuleName == "DQC.US.0015" and "DQC.US.0015" in ugtRels:
            dqc0015 = ugtRels["DQC.US.0015"]
            warnedFactsByQn = defaultdict(list)
            for f in modelXbrl.facts:
                if (f.qname in dqc0015.concepts and f.isNumeric and not f.isNil and f.xValid >= VALID and f.xValue < 0 and (
                    all(d.isTyped or (
                        (d.dimensionQname not in dqc0015.excludedAxesMembers or
                         ("*" not in dqc0015.excludedAxesMembers[d.dimensionQname] and
                          d.memberQname not in dqc0015.excludedAxesMembers[d.dimensionQname])) and
                         d.memberQname not in dqc0015.excludedMembers and
                         (dqc0015.excludedMemberNamesPattern is None or
                          not dqc0015.excludedMemberNamesPattern.search(d.memberQname.localName)))
                        for d in f.context.qnameDims.values()))):
                    id = dqc0015.conceptRuleIDs.get(f.qname, 9999)
                    if not any(f.isDuplicateOf(warnedFact) for warnedFact in warnedFactsByQn[f.qname]):
                        warnedFactsByQn[f.qname].append(f)
                        modelXbrl.warning("{}.{}".format(dqcRuleName, id), _(logMsg(msg)),
                            modelObject=f, name=f.qname, value=f.value, contextID=f.contextID, unitID=f.unit.id if f.unit is not None else "(none)",
                            edgarCode=edgarCode, ruleElementId=id)
            del warnedFactsByQn # dereference objects
        elif (dqcRuleName == "DQC.US.0033" and hasDocPerEndDateFact
              and not (documentType == "8K" and any(f.get("xValue") for f in modelXbrl.factsByLocalName.get("AmendmentFlag",())))
              and abs((documentPeriodEndDate + ONE_DAY - documentPeriodEndDateFact.context.endDatetime).days) == 0): # was 3
            for id, rule in dqcRule["rules"].items():
                for n in rule["names"]:
                    for f in modelXbrl.factsByLocalName.get(n,()):
                        if not dateUnionEqual(documentPeriodEndDate, f.context.endDatetime, instantEndDate=True):
                            modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg)),
                                              modelObject=f, name=f.qname.localName, endDate=XmlUtil.dateunionValue(f.context.endDatetime, subtractOneDay=True),
                                              documentPeriodEndDate=documentPeriodEndDate,
                                              contextID=f.context.id, unitID=f.unit.id if f.unit is not None else "(none)",
                                              edgarCode=edgarCode, ruleElementId=id)
        elif dqcRuleName == "DQC.US.0036" and hasDocPerEndDateFact:
            for id, rule in dqcRule["rules"].items():
                if abs((documentPeriodEndDate + ONE_DAY - documentPeriodEndDateFact.context.endDatetime).days) > 1: # was 3
                    modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg)),
                                      modelObject=f, name=documentPeriodEndDateFact.qname.localName,
                                      endDate=XmlUtil.dateunionValue(documentPeriodEndDateFact.context.endDatetime, subtractOneDay=True),
                                      documentPeriodEndDate=documentPeriodEndDate,
                                      contextID=documentPeriodEndDateFact.context.id,
                                      edgarCode=edgarCode, ruleElementId=id)
        elif dqcRuleName == "DQC.US.0041":
            ugtAxisDefaults = ugtRels["axis-defaults"]
            for id, rule in dqcRule["rules"].items():
                for rel in modelXbrl.relationshipSet(XbrlConst.dimensionDefault).modelRelationships:
                    if (rel.fromModelObject is not None and rel.toModelObject is not None
                        and rel.fromModelObject.qname in ugtAxisDefaults
                        and ugtAxisDefaults[rel.fromModelObject.qname] != rel.toModelObject.qname):
                        modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg)),
                                          modelObject=(rel, rel.fromModelObject), axisName=rel.fromModelObject.qname,
                                          axisDefaultName=ugtAxisDefaults[rel.fromModelObject.qname],
                                          extensionDefaultName=rel.toModelObject.qname,
                                          edgarCode=edgarCode, ruleElementId=id)
        elif dqcRuleName == "DQC.US.0043":
            incomeNames = dqcRule["income-names"]
            def descendantWeights(fromConcept, ELR=None, effectiveWeight=1, bottomWeights=None, visited=None):
                if visited is None:
                    visited = set()
                    bottomWeights = set()
                visited.add(fromConcept)
                for rel in modelXbrl.relationshipSet(XbrlConst.summationItem, ELR).fromModelObject(fromConcept):
                    if rel.toModelObject is not None and rel.toModelObject.name not in incomeNames:
                        w = effectiveWeight * rel.weight
                        bottomWeights.add((rel.toModelObject, w))
                        descendantWeights(rel.toModelObject, rel.linkrole, w, bottomWeights, visited)
                visited.discard(fromConcept)
                return bottomWeights

            for id, rule in dqcRule["rules"].items():
                topName = rule["parent-name"]
                if (modelXbrl.factsByLocalName.get(topName,())
                    and ("excluded-name" not in rule or not modelXbrl.factsByLocalName.get(rule["excluded-name"],()))):
                    top = modelXbrl.nameConcepts[topName][0]
                    for bottom, effectiveWeight in descendantWeights(top): # don't include stopping income concept
                        if ((bottom.balance == "credit" and effectiveWeight > 0)
                            or (bottom.balance == "debit" and effectiveWeight < 0)):
                            modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg[bottom.balance or ""])),
                                              modelObject=(top, bottom), topName=top.name, bottomName=bottom.name,
                                              edgarCode=f"{edgarCode}-{bottom.balance}", ruleElementId=id)

        elif dqcRuleName == "DQC.US.0044":
            ugtAccrualItems = ugtRels["accrual-items"]
            for id, rule in dqcRule["rules"].items():
                def checkAccrualDescendants(rel, visited):
                    if rel.toModelObject is not None:
                        name = rel.toModelObject.name
                        if name in ugtAccrualItems:
                            for f in modelXbrl.factsByLocalName[name]:
                                if f.xValue != 0:
                                    modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg)),
                                        modelObject=f, name=name, contextID=f.context.id, unitID=f.unit.id if f.unit is not None else "(none)", value=f.xValue,
                                        edgarCode=edgarCode, ruleElementId=id)
                        if name not in visited:
                            visited.add(name)
                            for childRel in modelXbrl.relationshipSet(rel.arcrole, rel.consecutiveLinkrole).fromModelObject(rel.toModelObject):
                                checkAccrualDescendants(childRel, visited)
                            visited.discard(name)
                for parentLn in rule["summation-items"]:
                    for parentConcept in modelXbrl.nameConcepts[parentLn]:
                        for rel in val.summationItemRelsSetAllELRs.fromModelObject(parentConcept):
                            checkAccrualDescendants(rel, set())
        elif dqcRuleName == "DQC.US.0048" and documentType not in dqcRule["excluded-document-types"]:
            # 0048 has only one id, rule
            id, rule = next(iter(dqcRule["rules"].items()))
            # check if calc root check is blocked
            blockRootCheck = any(f.xValue == v for ln,v in dqcRule["blocking-facts"].items() for f in modelXbrl.factsByLocalName.get(ln,()))
            # find presentation ELR of interest
            preCashFlowLinkRoles = set()
            calcCashFlowLinkRoles = set()
            calcCashFlowLinkRolesMissingRoots = set()
            linkroleUris = OrderedSet(modelLink.role for modelLink in val.modelXbrl.baseSets[(XbrlConst.parentChild,None,None,None)])
            for linkroleUri in linkroleUris: # role ELRs may be repeated in pre LB
                roleTypes = val.modelXbrl.roleTypes.get(linkroleUri)
                definition = (roleTypes[0].definition or linkroleUri) if roleTypes else linkroleUri
                preRoots = val.modelXbrl.relationshipSet(XbrlConst.parentChild, linkroleUri, None, None).rootConcepts
                if ((any(c.name == "StatementOfCashFlowsAbstract" for c in preRoots) or
                     'cashflow' in linkroleUri.lower())
                    and '- Statement ' in definition and 'parenthetical' not in linkroleUri.lower()):
                    preCashFlowLinkRoles.add(linkroleUri)
                    calcRelationshipSet = val.modelXbrl.relationshipSet(XbrlConst.summationItem, linkroleUri, None, None)
                    calcRoots = calcRelationshipSet.rootConcepts
                    if calcRoots:
                        calcCashFlowLinkRoles.add(linkroleUri)
                        roots = rule["roots"]
                        if not (blockRootCheck or
                                any(all(any(c.name == rName for c in calcRoots) for rName in rNames) for rNames in roots)):
                            calcCashFlowLinkRolesMissingRoots.add(linkroleUri)
            if preCashFlowLinkRoles:
                if not calcCashFlowLinkRoles:
                    modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(dqcRule["message-no-roles"])),
                        modelObject=modelXbrl,
                        linkRoles=(", ".join(sorted(preCashFlowLinkRoles))),
                        edgarCode=edgarCode+"-No-Roles", ruleElementId=id)
                elif calcCashFlowLinkRolesMissingRoots == calcCashFlowLinkRoles: # every calc is missing the roots
                    for linkRole in calcCashFlowLinkRolesMissingRoots:
                        modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg)),
                            modelObject=val.modelXbrl.baseSets[(XbrlConst.summationItem,linkroleUri,None,None)] or modelXbrl, # may be no base sets, in which case just show the instance
                            linkRole=linkroleUri, linkroleDefinition=definition,
                            rootNames=(", ".join(r.name for r in calcRoots) or "(none)"),
                            edgarCode=edgarCode, ruleElementId=id)
        elif dqcRuleName == "DQC.US.0060":
            for id, rule in dqcRule["rules"].items():
                for eltLn, depLns in rule["element-dependencies"].items():
                    bindings = factBindings(val.modelXbrl, flattenToSet( (eltLn, depLns )), nils=False, noAdditionalDims=True)
                    for b in bindings.values():
                        if eltLn in b and not any(depLn in b for depLn in depLns):
                            f = b[eltLn]
                            modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg)),
                                modelObject=b.values(), name=eltLn, value=f.xValue,
                                dependentElements=", ".join(depLns),
                                contextID=f.context.id, unitID=f.unit.id if f.unit is not None else "(none)",
                                edgarCode=edgarCode, ruleElementId=id)
        elif dqcRuleName == "DQC.US.0079":
            for id, rule in dqcRule["rules"].items():
                ignoreDims = rule["acceptable-dimensions"]
                replacementMembers = rule["replacement-members"]
                def checkMember(axis, rel, visited):
                    if rel.toModelObject is not None:
                        name = rel.toModelObject.name
                        if name.lower() in replacementMembers and rel.toModelObject.qname.namespaceURI not in val.disclosureSystem.standardTaxonomiesDict:
                            modelXbrl.warning(f"{dqcRuleName}.{id}", _(logMsg(msg)),
                                modelObject=(rel, rel.toModelObject), member=rel.toModelObject.qname, axis=axis.qname,
                                replacement=replacementMembers[name.lower()],
                                edgarCode=edgarCode, ruleElementId=id)
                        if name not in visited:
                                visited.add(name)
                                for childRel in modelXbrl.relationshipSet(XbrlConst.domainMember, rel.consecutiveLinkrole).fromModelObject(rel.toModelObject):
                                    checkMember(axis, childRel, visited)
                                visited.discard(name)
                for rel in modelXbrl.relationshipSet(XbrlConst.dimensionDomain).modelRelationships:
                    if rel.fromModelObject is not None and rel.fromModelObject.name not in ignoreDims:
                        checkMember(rel.fromModelObject, rel, set())



    del val.summationItemRelsSetAllELRs

    if "EFM/Filing.py#validateFiling_end" in val.modelXbrl.arelleUnitTests:
        raise pyNamedObject(val.modelXbrl.arelleUnitTests["EFM/Filing.py#validateFiling_end"], "EFM/Filing.py#validateFiling_end")

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
                    edgarCode="cp-1002-Element-Used-Has-Duplicate-Label",
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

def deiParamEqual(deiName, xbrlVal, secVal):
    if xbrlVal is None: # nil fact
        return False
    if deiName == "DocumentPeriodEndDate":
        x = str(xbrlVal).split('-')
        s = secVal.split('-')
        return (x[0]==s[2] and x[1]==s[0] and x[2]==s[1])
    elif deiName == "CurrentFiscalYearEndDate":
        x = str(xbrlVal).lstrip('-').split('-')
        s = secVal.split('/')
        return (len(secVal) == 5 and secVal[2] == '/' and x[0] == s[0] and x[1] == s[1])
    elif deiName in {"EntityEmergingGrowthCompany", "EntityExTransitionPeriod", "EntityShellCompany",
                     "EntitySmallBusiness", "EntityVoluntaryFilers", "EntityWellKnownSeasonedIssuer",
                     "IcfrAuditorAttestationFlag",
                     "cef:IntervalFundFlag", "cef:NewCefOrBdcRegistrantFlag", "cef:PrimaryShelfQualifiedFlag"}:
        return {"y": True, "yes": True, "true": True, "n": False, "no": False, "false": False
                }.get(str(xbrlVal).lower()) == {
                "yes":True, "Yes":True, "y":True, "Y":True, "no":False, "No":False, "N":False, "n":False
                }.get(secVal,secVal)
    elif deiName == "EntityFileNumber":
        return secVal == xbrlVal
    elif deiName == "EntityInvCompanyType":
        return xbrlVal in {"N-1A":("N-1A",), "N-1":("N-1",), "N-2":("N-2"), "N-3":("N-3",), "N-4":("N-4",), "N-5":("N-5",),
                           "N-6":("N-6",), "S-1":("S-1","S-3"), "S-3":("S-1","S-3"),"S-6":("S-6")}.get(secVal,())
    elif deiName == "EntityFilerCategory":
        return xbrlVal in {"Non-Accelerated Filer":("Non-accelerated Filer", "Smaller Reporting Company"),
                           "Accelerated Filer":("Accelerated Filer", "Smaller Reporting Accelerated Filer"),
                           "Large Accelerated Filer":("Large Accelerated Filer",),
                           "Not Applicable":("Non-accelerated Filer", "Smaller Reporting Company")}.get(secVal,())
    elif deiName == "2014EntityFilerCategory":
        return xbrlVal in {True:("Smaller Reporting Company", "Smaller Reporting Accelerated Filer"),
                           False:("Non-accelerated Filer", "Accelerated Filer", "Large Accelerated Filer")}.get(secVal,())
    return False # unhandled deiName

def eloValueOfFact(deiName, xbrlVal):
    if xbrlVal is None: # nil fact
        return None
    if deiName == "DocumentPeriodEndDate":
        return ("{1}-{2}-{0}".format(*str(xbrlVal).split('-')))
    elif deiName == "CurrentFiscalYearEndDate":
        return ("{0}/{1}".format(*str(xbrlVal).lstrip('-').split('-')))
    elif deiName in {"EntityEmergingGrowthCompany", "EntityExTransitionPeriod", "EntityShellCompany",
                     "EntitySmallBusiness", "EntityVoluntaryFilers", "EntityWellKnownSeasonedIssuer",
                     "IcfrAuditorAttestationFlag",
                     "cef:NewCefOrBdcRegistrantFlag", "cef:NewCefOrBdcRegistrantFlag", "cef:NewCefOrBdcRegistrantFlag"}:
        return {"y": "yes", "yes": "yes", "true": "yes", "n": "no", "no": "no", "false": "no"
                }.get(str(xbrlVal).lower())
    elif deiName == "EntityFileNumber":
        return xbrlVal
    elif deiName == "EntityInvCompanyType":
        return xbrlVal
    elif deiName == "EntityFilerCategory":
        return xbrlVal
    return None # unhandled deiName


def cleanedCompanyName(name):
    for pattern, replacement in (
                                 (r"\s&(?=\s)", " and "),  # Replace & with and
                                 (r"/.+/|\\.+\\", " "),  # Remove any "/../" , "\...\" or "/../../" expression.
                                 (r"\s*[(].+[)]$", " "),  # Remove any parenthetical expression if it occurs at the END of the string.
                                 (r"[\u058A\u05BE\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D]", "-"),  # Normalize fancy dashes.
                                 (r"-", ""),  #dash to space
                                 (r"[\u2019']", ""),  #Apostrophe to space
                                 (r"^\s*the(?=\s)", ""),  # Remove the word "THE" (i.e., followed by space) from the beginning.
                                 (r"[^\w-]", " "),  # Remove any punctuation.
                                 (r"^\w(?=\s)|\s\w(?=\s)|\s\w$", " "),  # Remove single letter words
                                 (r"^INCORPORATED(?=\s|$)|(?<=\s)INCORPORATED(?=\s|$)", "INC"),  # Truncate the word INCORPORATED (case insensitive) to INC
                                 (r"^CORPORATION(?=\s|$)|(?<=\s)CORPORATION(?=\s|$)", "CORP"),  # Truncate the word CORPORATION (case insensitive) to CORP
                                 (r"^COMPANY(?=\s|$)|(?<=\s)COMPANY(?=\s|$)", "CO"),  # Truncate the word CORPORATION (case insensitive) to CORP
                                 (r"^LIMITED(?=\s|$)|(?<=\s)LIMITED(?=\s|$)", "LTD"),  # Truncate the word LIMITED (case insensitive) to LTD
                                 (r"^AND(?=\s|$)|(?<=\s)AND(?=\s|$)", "&"),  # Replace the word AND with an ampersand (&)
                                 (r"\s+", " "),  # Normalize all spaces (i.e., trim, collapse, map &#xA0; to &#xA; and so forth)
                                 (r"\s", "")  # remove space to nothing for comparison
                                 ):
        name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)
    return unicodedata.normalize('NFKD', name.strip().lower()).encode('ASCII', 'ignore').decode()  # remove diacritics
