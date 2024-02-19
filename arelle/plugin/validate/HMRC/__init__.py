"""
See COPYRIGHT.md for copyright information.

References:

- <https://xbrl.frc.org.uk> (taxonomies, filing requirements, consistency checks)
- [Joint Filing Common Validation Checks](https://www.gov.uk/government/uploads/system/uploads/attachment_data/file/434597/joint-filing-validation-checks.pdf)
- [HMRC CT Inline XBRL Style Guide](https://www.gov.uk/government/uploads/system/uploads/attachment_data/file/434588/xbrl-style-guide.pdf)
"""
import os
from math import isnan
from arelle import ModelDocument, XmlUtil
from arelle.ModelValue import qname, dateTime, DATE
from arelle.ValidateXbrlCalcs import inferredDecimals, rangeValue, insignificantDigits
from arelle.Version import authorLabel, copyrightLabel
from arelle.XbrlConst import xbrli, qnXbrliXbrl
import regex as re
from collections import defaultdict

from .ValidateHmrc import ValidateHmrc

FRC_URL_DOMAIN = "http://xbrl.frc.org.uk/"
memNameNumPattern = re.compile(r"^([A-Za-z-]+)([0-9]+)$")
compTxmyNamespacePattern = re.compile(r"http://www.govtalk.gov.uk/uk/fr/tax/uk-hmrc-ct/[0-9-]{10}")
# capture background-image or list-style-image with URL function
styleImgUrlPattern = re.compile(r"[a-z]+-image:\s*url[(][^)]+[)]")
EMPTYDICT = {}
_6_APR_2008 = dateTime("2008-04-06", type=DATE)

COMMON_GENERIC_DIMENSIONS = {
    "Chairman": ("NameEntityOfficer",),
    "ChiefExecutive": ("NameEntityOfficer",),
    "ChairmanChiefExecutive": ("NameEntityOfficer",),
    "SeniorPartnerLimitedLiabilityPartnership": ("NameEntityOfficer",),
    "HighestPaidDirector": ("NameEntityOfficer",),
    "CompanySecretary": (1, 2, "NameEntityOfficer",),
    "CompanySecretaryDirector": (1, 2, "NameEntityOfficer",),
    "Director": (1, 40, "NameEntityOfficer",),
    "PartnerLLP": (1, 20, "NameEntityOfficer"),
    "ReportableOperatingSegment": (1, 20, "NameIndividualSegment"),
    "ProductService": (1, 12, "NameIndividualSegment"),
    "MajorCustomer": (1, 12, "NameIndividualSegment"),
    "SpecificBusinessCombination": (1, 10, "NameAcquiredEntity"),
    "ConsumableBiologicalAssetClass": (1, 5, "NameOrDescriptionBiologicalAssetClass"),
    "BearerBiologicalAssetClass": (1, 5, "NameOrDescriptionBiologicalAssetClass"),
    "Subsidiary": (1, 200, "NameSubsidiary"),
    "Associate": (1, 50, "NameAssociate"),
    "JointVenture": (1, 50, "NameJointVenture"),
    "UnconsolidatedStructuredEntity": (1, 5, "NameUnconsolidatedStructuredEntity"),
    "IntermediateParent": (1, 5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
    "EntityWithJointControlOrSignificantInfluence": (1, 5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
    "AnotherGroupMember": (1, 8, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
    "KeyManagementIndividualGroup": (1, 5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
    "CloseFamilyMember": (1, 5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
    "EntityControlledByKeyManagementPersonnel": (1, 5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
    "OtherRelatedPartyRelationshipType1ComponentTotalRelatedParties": ("NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag",),
    "OtherRelatedPartyRelationshipType2ComponentTotalRelatedParties": ("NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag",),
    "OrdinaryShareClass": (1, 5, "DescriptionShareType"),
    "PreferenceShareClass": (1, 5, "DescriptionShareType"),
    "DeferredShareClass": (1, 5, "DescriptionShareType"),
    "OtherShareClass": (1, 5, "DescriptionShareType"),
    "Share-basedArrangement": (1, 8, "NameShare-basedPaymentArrangement"),
    "Grant": (1, 10, "NameOrDescriptionGrantUnderShare-basedPaymentArrangement"),
    "PensionPlan": (1, 6, "NameDefinedContributionPlan", "NameDefinedBenefitPlan"),
    "Post-employmentMedicalPlan": (1, 2, "NameDefinedContributionPlan", "NameDefinedBenefitPlan"),
    "OtherPost-employmentBenefitPlan": (1, 2, "NameDefinedContributionPlan", "NameDefinedBenefitPlan"),
    "OtherContractType": (1, 2, "DescriptionOtherContractType"),
    "OtherDurationType": (1, 2, "DescriptionOtherContractDurationType"),
    "SalesChannel": (1, 2, "DescriptionOtherSalesChannelType"),
}

COMMON_MANDATORY_ITEMS = {
    "EntityCurrentLegalOrRegisteredName", "StartDateForPeriodCoveredByReport",
    "EndDateForPeriodCoveredByReport", "BalanceSheetDate"
}

COMMON_MANDATORY_FRS_ITEMS = COMMON_MANDATORY_ITEMS | {
    "DateAuthorisationFinancialStatementsForIssue", "DirectorSigningFinancialStatements",
    "EntityDormantTruefalse", "EntityTradingStatus",
    "AccountingStandardsApplied", "AccountsStatusAuditedOrUnaudited",
    "LegalFormEntity", "DescriptionPrincipalActivities"
}

MANDATORY_ITEMS = {
    "ukGAAP": COMMON_MANDATORY_ITEMS | {
        "DateApprovalAccounts", "NameDirectorSigningAccounts", "EntityDormant", "EntityTrading",
        "DateSigningDirectorsReport", "DirectorSigningReport"
        },
    "charities": COMMON_MANDATORY_ITEMS | {
        "DateAuthorisationFinancialStatementsForIssue", "DirectorSigningFinancialStatements",
        "EntityDormantTruefalse", "EntityTradingStatus",
        "AccountingStandardsApplied", "AccountsStatusAuditedOrUnaudited"},
    "ukIFRS": COMMON_MANDATORY_ITEMS | {
        "DateAuthorisationFinancialStatementsForIssue", "ExplanationOfBodyOfAuthorisation",
        "EntityDormant", "EntityTrading", "DateSigningDirectorsReport", "DirectorSigningReport"},
    "FRS": COMMON_MANDATORY_FRS_ITEMS | {"AccountsTypeFullOrAbbreviated"},
    "FRS-2022": COMMON_MANDATORY_FRS_ITEMS | {"AccountsType"}
}

MUST_HAVE_ONE_ITEM = {
    "charities": {
        "CharityRegistrationNumberEnglandWales", "CharityRegistrationNumberScotland",
        "CharityRegistrationNumberNorthernIreland",
    }
}

GENERIC_DIMENSION_VALIDATION = {
    # "taxonomyType": { "LocalName": (range of numbers if any, first item name, 2nd choice item name if any)
    "ukGAAP": COMMON_GENERIC_DIMENSIONS,
    "ukIFRS": COMMON_GENERIC_DIMENSIONS,
    "charities": {
        **COMMON_GENERIC_DIMENSIONS,
        **{
            "Trustee": (1, 20, "NameEntityOfficer"),
            "CorporateTrustee": (1, 3, "NameEntityOfficer"),
            "CustodianTrustee": (1, 3, "NameEntityOfficer"),
            "Director1CorporateTrustee": ("NameEntityOfficer",),
            "Director2CorporateTrustee": ("NameEntityOfficer",),
            "Director3CorporateTrustee": ("NameEntityOfficer",),
            "TrusteeTrustees": (1, 5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
            "CloseFamilyMemberTrusteeTrustees": (1, 5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
            "EntityControlledTrustees": (1, 5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
            "Activity": (1, 50, "DescriptionActivity"),
            "MaterialFund": (1, 50, "DescriptionsMaterialFund"),
            "LinkedCharity": (1, 5, "DescriptionActivitiesLinkedCharity"),
            "NameGrantRecipient": (1, 50, "NameSpecificInstitutionalGrantRecipient"),
            "ConcessionaryLoan": (1, 50, "DescriptionConcessionaryLoan"),
        }
    },
    "FRS": COMMON_GENERIC_DIMENSIONS,
    "FRS-2022": COMMON_GENERIC_DIMENSIONS
}

ALLOWED_IMG_MIME_TYPES = (
        "data:image/gif;base64",
        "data:image/jpeg;base64", "data:image/jpg;base64", # note both jpg and jpeg are in use
        "data:image/png;base64"
)


def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("HMRC", "HMRCplugin"),)


def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")


def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateHMRCplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "HMRCplugin", False)
    if not (val.validateHMRCplugin) or not val.modelXbrl.modelDocument:
        return

    if parameters:
        p = parameters.get(qname("type",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:  # override implicit type
            paramType = p[1].lower()
            val.isAccounts = paramType == "accounts"
            val.isComputation = paramType == "computation"
    if not hasattr(val, "isAccounts"):
        val.isComputation = any(compTxmyNamespacePattern.match(doc.targetNamespace)
                                for doc in val.modelXbrl.urlDocs.values()
                                if doc.targetNamespace)
        val.isAccounts = not val.isComputation

    val.txmyType = None
    for ns in val.modelXbrl.prefixedNamespaces.values():
        if ns.startswith("http://www.xbrl.org/uk/char/") or ns.startswith("http://xbrl.frc.org.uk/char/"):
            val.txmyType = "charities"
        elif ns.startswith("http://www.xbrl.org/uk/gaap/"):
            val.txmyType = "ukGAAP"
        elif ns.startswith("http://www.xbrl.org/uk/ifrs/") or ns.startswith("https://xbrl.frc.org.uk/IFRS/"):
            val.txmyType = "ukIFRS"
        elif ns.startswith(FRC_URL_DOMAIN):
            val.txmyType = "FRS"
            for concept in val.modelXbrl.nameConcepts.get("AccountsType", ()):
                if concept.qname.namespaceURI.startswith(FRC_URL_DOMAIN) and concept.modelDocument.inDTS:
                    val.txmyType = "FRS-2022"
                    break
        else:
            continue
        break
    if val.txmyType:
        val.modelXbrl.debug("debug",
                            "HMRC taxonomy type %(taxonomyType)s",
                            modelObject=val.modelXbrl, taxonomyType=val.txmyType)
    else:
        val.modelXbrl.error("HMRC.TBD",
                            _("No recognized standard taxonomy (UK GAAP, UK IFRS, Charity, or FRS)."),
                            modelObject=val.modelXbrl)


def validateXbrlFinally(val, *args, **kwargs):
    if not (val.validateHMRCplugin) or not val.txmyType:
        return

    modelXbrl = val.modelXbrl
    modelDocument = modelXbrl.modelDocument

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)

    if modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):
        labelHasNegativeTermPattern = re.compile(r".*[(].*\w.*[)].*")

        companyReferenceNumberContexts = defaultdict(list)
        for c1 in modelXbrl.contexts.values():
            scheme, identifier = c1.entityIdentifier
            if scheme == "http://www.companieshouse.gov.uk/":
                companyReferenceNumberContexts[identifier].append(c1.id)
        atLeastOneFacts = {}
        uniqueFacts = {}  # key = (qname, context hash, unit hash, lang)
        mandatoryFacts = {}
        mandatoryGDV = defaultdict(set)
        factForConceptContextUnitHash = defaultdict(list)
        hasCompaniesHouseContext = any(cntx.entityIdentifier[0] == "http://www.companieshouse.gov.uk/"
                                       for cntx in val.modelXbrl.contexts.values())

        contextsUsed = set(f.context for f in modelXbrl.factsInInstance if f.context is not None)

        contextsWithScenario = []
        for cntx in contextsUsed:
            for dim in cntx.qnameDims.values():
                if dim.isExplicit:
                    _memName = dim.memberQname.localName
                    m = memNameNumPattern.match(_memName)
                    if m:
                        l = m.group(1)
                        n = int(m.group(2))
                    else:
                        l = _memName
                        n = None
                    gdv = GENERIC_DIMENSION_VALIDATION.get(val.txmyType, EMPTYDICT).get(l)
                    if (gdv and (n is None or
                                 (isinstance(gdv[0],int) and isinstance(gdv[1],int) and n >= gdv[0] and n <= gdv[1]))):
                        gdvFacts = [f for f in gdv if isinstance(f,str)]
                        if len(gdvFacts) == 1:
                            mandatoryGDV[gdvFacts[0]].add(GDV(gdvFacts[0], None, _memName))
                        elif len(gdvFacts) == 2:
                            mandatoryGDV[gdvFacts[0]].add(GDV(gdvFacts[0], gdvFacts[1], _memName))
                            mandatoryGDV[gdvFacts[1]].add(GDV(gdvFacts[1], gdvFacts[0], _memName))
            if XmlUtil.hasChild(cntx, xbrli, "scenario"):
                contextsWithScenario.append(cntx)

        if contextsWithScenario:
            modelXbrl.error("FRC.TG.3.6.1",
                _("Context(s) %(identifiers)s is reported with scenario element."),
                modelObject=contextsWithScenario,
                            identifiers=", ".join(c.id for c in contextsWithScenario))
        del contextsWithScenario

        def checkFacts(facts):
            for f in facts:
                cntx = f.context
                unit = f.unit
                if (f.isNil or getattr(f,"xValid", 0) >= 4) and cntx is not None and f.concept is not None and f.concept.type is not None:
                    factNamespaceURI = f.qname.namespaceURI
                    factLocalName = f.qname.localName
                    if factLocalName in MANDATORY_ITEMS[val.txmyType]:
                        mandatoryFacts[factLocalName] = f
                    if val.txmyType in MUST_HAVE_ONE_ITEM and factLocalName in MUST_HAVE_ONE_ITEM[val.txmyType]:
                        atLeastOneFacts[factLocalName] = f
                    if factLocalName == "UKCompaniesHouseRegisteredNumber" and val.isAccounts:
                        if hasCompaniesHouseContext:
                            mandatoryFacts[factLocalName] = f
                        for _cntx in contextsUsed:
                            _scheme, _identifier = _cntx.entityIdentifier
                            if _scheme == "http://www.companieshouse.gov.uk/" and f.xValue != _identifier:
                                modelXbrl.error("JFCVC.3316",
                                    _("Context entity identifier %(identifier)s does not match Company Reference Number (UKCompaniesHouseRegisteredNumber) Location: Accounts (context id %(id)s)"),
                                    modelObject=(f, _cntx), identifier=_identifier, id=_cntx.id)
                    if f.parentElement.qname == qnXbrliXbrl: # JFCVC v4.0 - only check non-tuple facts
                        factForConceptContextUnitHash[f.conceptContextUnitHash].append(f)

                    if f.isNumeric:
                        if f.precision:
                            modelXbrl.error("HMRC.5.4",
                                _("Numeric fact %(fact)s of context %(contextID)s has a precision attribute '%(precision)s'"),
                                modelObject=f, fact=f.qname, contextID=f.contextID, precision=f.precision)
                        try: # only process validated facts
                            if not f.isNil:
                                if f.xValue < 0:
                                    label = f.concept.label(lang="en")
                                    if not labelHasNegativeTermPattern.match(label):
                                        modelXbrl.error("HMRC.5.3",
                                            _("Numeric fact %(fact)s of context %(contextID)s has a negative value '%(value)s' but label does not have a bracketed negative term (using parentheses): %(label)s"),
                                            modelObject=f, fact=f.qname, contextID=f.contextID, value=f.value, label=label)
                                # 6.5.37 test (insignificant digits due to rounding)
                                if f.decimals and f.decimals != "INF":
                                    try:
                                        insignificance = insignificantDigits(f.xValue, decimals=f.decimals)
                                        if insignificance: # if not None, returns (truncatedDigits, insiginficantDigits)
                                            modelXbrl.error("HMRC.SG.4.5",
                                                _("Fact %(fact)s of context %(contextID)s decimals %(decimals)s value %(value)s has nonzero digits in insignificant portion %(insignificantDigits)s."),
                                                modelObject=f, fact=f.qname, contextID=f.contextID, decimals=f.decimals,
                                                value=f.xValue, truncatedDigits=insignificance[0], insignificantDigits=insignificance[1])
                                    except (ValueError,TypeError):
                                        modelXbrl.error("HMRC.SG.4.5",
                                            _("Fact %(fact)s of context %(contextID)s decimals %(decimals)s value %(value)s causes Value Error exception."),
                                            modelObject=f, fact=f.qname, contextID=f.contextID, decimals=f.decimals, value=f.value)
                        except AttributeError:
                            pass  # if not validated it should have failed with a schema error

                    # check GDV
                    if f.qname.localName in mandatoryGDV:
                        _gdvReqList = mandatoryGDV[factLocalName]
                        _gdvReqRemovals = []
                        for _gdvReq in _gdvReqList:
                            if any(_gdvReq.memLocalName == dim.memberQname.localName
                                   for dim in cntx.qnameDims.values()
                                   if dim.isExplicit):
                                _gdvReqRemovals.append(_gdvReq)
                                if _gdvReq.altFact in mandatoryGDV:
                                    _gdvAltList = mandatoryGDV[_gdvReq.altFact]
                                    _gdvAltRemovals = []
                                    for _gdvAlt in _gdvAltList:
                                        if any(_gdvAlt.memLocalName == dim.memberQname.localName
                                               for dim in cntx.qnameDims.values()
                                               if dim.isExplicit):
                                            _gdvAltRemovals.append(_gdvAlt)
                                    for _gdvAlt in _gdvAltRemovals:
                                        _gdvAltList.remove(_gdvAlt)
                        if _gdvReqRemovals and not f.xValue: # fact was a mandatory name or description
                            modelXbrl.error("JFCVC.3315",
                                            _("Generic dimension members associated name/description has no text: %(fact)s"),
                                            modelObject=f, fact=f.qname)
                        for _gdvReq in _gdvReqRemovals:
                            _gdvReqList.remove(_gdvReq)

                    if f.modelTupleFacts:
                        checkFacts(f.modelTupleFacts)

        checkFacts(modelXbrl.facts)

        if val.isAccounts:
            _missingItems = MANDATORY_ITEMS[val.txmyType] - mandatoryFacts.keys()
            if hasCompaniesHouseContext and "UKCompaniesHouseRegisteredNumber" not in mandatoryFacts:
                _missingItems.add("UKCompaniesHouseRegisteredNumber")
            if _missingItems:
                modelXbrl.error("JFCVC.3312",
                    _("Facts are MANDATORY: %(missingItems)s"),
                    modelObject=modelXbrl, missingItems=", ".join(sorted(_missingItems)))
            if not atLeastOneFacts and val.txmyType in MUST_HAVE_ONE_ITEM:
                modelXbrl.error("JFCVC.3312.atLeastOne",
                                _("At least one of the facts is MANDATORY: %(missingItems)s"),
                                modelObject=modelXbrl, missingItems=", ".join(sorted(MUST_HAVE_ONE_ITEM[val.txmyType])))

            ''' removed with JFCVC v4.0 2020-06-09
            f = mandatoryFacts.get("StartDateForPeriodCoveredByReport")
            if f is not None and (f.isNil or f.xValue < _6_APR_2008):
                modelXbrl.error("JFCVC.3313",
                    _("Period Start Date (StartDateForPeriodCoveredByReport) must be 6 April 2008 or later, but is %(value)s"),
                    modelObject=f, value=f.value)
            '''

            memLocalNamesMissing = set("{}({})".format(_gdvRec.memLocalName, _gdvRec.factNames)
                                       for _gdv in mandatoryGDV.values()
                                       for _gdvRec in _gdv)
            if memLocalNamesMissing:
                modelXbrl.error("JFCVC.3315",
                    _("Generic dimension members have no associated name or description item, member names (name or description item): %(memberNames)s"),
                    modelObject=modelXbrl, memberNames=", ".join(sorted(memLocalNamesMissing)))



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
                                    aMax, bMin, _inclA, _inclB = rangeValue(_v, _d)
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
                                        a, b, _inclA, _inclB = rangeValue(_v, _d)
                                        if a > aMax: aMax = a
                                        if b < bMin: bMin = b
                                    if not _inConsistent:
                                        _inConsistent = (bMin < aMax)
                                    decVals.clear()
                            else:
                                _inConsistent = any(not f.isVEqualTo(f0) for f in fList[1:])
                            if _inConsistent:
                                modelXbrl.error("JFCVC.3314",
                                    "Inconsistent duplicate fact values %(fact)s: %(values)s.",
                                    modelObject=fList, fact=f0.qname, contextID=f0.contextID, values=", ".join(f.value for f in fList))
                aspectEqualFacts.clear()
        del factForConceptContextUnitHash, aspectEqualFacts

    if modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL:
        rootElt = modelXbrl.modelDocument.xmlRootElement
        if rootElt.tag in ("html", "xhtml") or not rootElt.tag.startswith("{http://www.w3.org/1999/xhtml}"):
            modelXbrl.error("HMRC.SG.3.3",
                _("InlineXBRL root element <%(element)s> MUST be html and have the xhtml namespace."),
                modelObject=rootElt, element=rootElt.tag)
        for elt in rootElt.iterdescendants(tag="{http://www.w3.org/1999/xhtml}script"):
            modelXbrl.error("HMRC.SG.3.3",
                _("Script element is disallowed."),
                modelObject=elt)
        for tag, localName, attr in (("{http://www.w3.org/1999/xhtml}a", "a", "href"),
                                     ("{http://www.w3.org/1999/xhtml}img", "img", "src")):
            for elt in rootElt.iterdescendants(tag=tag):
                attrValue = (elt.get(attr) or "").strip()
                if "javascript:" in attrValue:
                    modelXbrl.error("HMRC.SG.3.3",
                        _("Element %(localName)s javascript %(javascript)s is disallowed."),
                        modelObject=elt, localName=localName, javascript=attrValue[:64])
                if localName == "img" and not any(attrValue.startswith(m) for m in ALLOWED_IMG_MIME_TYPES):
                    modelXbrl.error("HMRC.SG.3.8",
                        _("Image scope must be base-64 encoded string (starting with data:image/*;base64), *=gif, jpeg or png.  src disallowed: %(src)s."),
                        modelObject=elt, src=attrValue[:128])
        for elt in rootElt.iterdescendants(tag="{http://www.w3.org/1999/xhtml}style"):
            if elt.text and styleImgUrlPattern.match(elt.text):
                modelXbrl.error("HMRC.SG.3.8",
                    _("Style element has disallowed image reference: %(styleImage)s."),
                    modelObject=elt, styleImage=styleImgUrlPattern.match(elt.text).group(1))
        for elt in rootElt.xpath("//xhtml:*[@style]", namespaces={"xhtml": "http://www.w3.org/1999/xhtml"}):
            for match in styleImgUrlPattern.findall(elt.get("style")):
                modelXbrl.error("HMRC.SG.3.8",
                    _("Element %(elt)s style attribute has disallowed image reference: %(styleImage)s."),
                    modelObject=elt, elt=elt.tag.rpartition("}")[2], styleImage=match)
    hmrc = ValidateHmrc(modelXbrl)
    if val.txmyType != "charities":
        hmrc.validate()
    elif val.txmyType == "charities":
        hmrc.validateCharities()

    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)


class GDV:
    def __init__(self, fact, altFact, memLocalName):
        self.fact = fact
        self.altFact = altFact
        self.memLocalName = memLocalName
        self._hash = hash( (hash(self.fact), hash(self.altFact), hash(self.memLocalName)) )

    @property
    def factNames(self):
        if self.altFact:
            return ", ".join(sorted( (self.fact, self.altFact) ))
        return self.fact

    def __hash__(self):
        return self._hash

    def __eq__(self,other):
        return self.fact == other.fact and self.altFact == other.altFact and self.memLocalName == other.memLocalName

    def __ne__(self,other):
        return not self.__eq__(other)


__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate HMRC',
    'version': '4.0',
    'description': '''HMRC Validation. JFCVC v4.0 2020-06-09.  Style guide v2.2''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,

    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
}
