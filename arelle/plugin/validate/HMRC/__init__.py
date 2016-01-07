'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.

References:
  https://xbrl.frc.org.uk (taxonomies, filing requirements, consistency checks)
  https://www.gov.uk/government/uploads/system/uploads/attachment_data/file/434597/joint-filing-validation-checks.pdf
'''
import os
from arelle import ModelDocument, ModelValue, XmlUtil
from arelle.ModelValue import qname
try:
    import regex as re
except ImportError:
    import re
from collections import defaultdict

memNameNumPattern = re.compile(r"^([A-Za-z-]+)([0-9]+)$")
compTxmyNamespacePattern = re.compile(r"http://www.govtalk.gov.uk/uk/fr/tax/uk-hmrc-ct/[0-9-]{10}")
busTxmyNamespacePattern = re.compile(r"http://www.xbrl.org/uk/cd/business/[0-9-]{10}")
EMPTYDICT = {}

commonMandatoryItems = {
    "EntityCurrentLegalOrRegisteredName", "StartDateForPeriodCoveredByReport", 
    "EndDateForPeriodCoveredByReport", "BalanceSheetDate"}
mandatoryItems = {
    "ukGAAP": commonMandatoryItems | {
        "DateApprovalAccounts", "NameDirectorSigningAccounts", "EntityDormant", "EntityTrading",
        "DateSigningDirectorsReport", "DirectorSigningReport"},
    "charities": commonMandatoryItems | {
        "DateApprovalAccounts", "NameTrusteeSigningAccounts", "EntityDormant", "EntityTrading",
        "DateSigningTrusteesReport", "TrusteeSigningReport"},
    "ukIFRS": commonMandatoryItems | {
        "DateAuthorisationFinancialStatementsForIssue", "ExplanationOfBodyOfAuthorisation", 
        "EntityDormant", "EntityTrading", "DateSigningDirectorsReport", "DirectorSigningReport"},
    "FRS": commonMandatoryItems | {
        "DateAuthorisationFinancialStatementsForIssue", "DirectorSigningFinancialStatements",
        "EntityDormantTruefalse", "EntityTradingStatus", "EntityTradingStatus", "DirectorSigningDirectorsReport"}
    }

genericDimensionValidation = {
    # "taxonomyType": { "LocalName": (range of numbers if any, first item name, 2nd choice item name if any)
    "ukGAAP": {"Acquisition": (1,10,"NameAcquisition"),
        "Associate": (1,30,"NameAssociate"),    
        "BusinessSegment": (1,30,"NameBusinessSegment", "DescriptionBusinessSegment"),
        "Disposal": (1,10,"NameOrDescriptionDisposal"),
        "Joint-venture": (1,30,"NameJoint-venture"),    
        "OtherInvestment": (1,5,"NameOtherParticipatingInterestOrInvestment",    "DescriptionOtherParticipatingInterestOrInvestment"),
        "OtherParticipatingInterest1": (1,5,"NameOtherParticipatingInterestOrInvestment",    "DescriptionOtherParticipatingInterestOrInvestment"),
        "PensionScheme": (1,8,"NameDefinedContributionScheme","DescriptionContributionScheme"),
        "Post-employmentMedicalScheme": (1,8,"NameDefinedBenefitScheme"    "DescriptionDefinedBenefitScheme"),
        "Share-basedScheme": (1,8,"NameShare-basedArrangement","DescriptionShare-basedArrangement"),
        "Subsidiary": (1,30, "NameSubsidiary")},
    "ukIFRS":    {"Associate": (1,50, "NameAssociate"),
        "Joint-venture": (1,50, "NameJoint-venture"),
        "MajorCustomer": (1,12,"NameIndividualSegmentMember"),
        "PensionScheme": (1,10,"NameDefinedContributionScheme","DescriptionContributionScheme"),
        "Post-employmentMedicalScheme": (1,4, "NameDefinedBenefitScheme", "DescriptionDefinedBenefitScheme"),
        "ProductService": (1,12,"NameIndividualSegmentMember"),
        "ReportableOperatingSegment": (1,20,"NameIndividualSegmentMember"),
        "Share-basedScheme": (1,8,"NameShare-basedPaymentArrangement"),
        "SpecificBusinessCombination": (1,10,"NameOfAcquiree"),
        "SpecificDiscontinuedOperation": (1,8,"DescriptionNon-currentAssetOrDisposalGroup",     "DescriptionFactsCircumstancesSaleOrExpectedDisposal"),
        "SpecificDisposalGroupHeldForSale": (1,8,"DescriptionNon-currentAssetOrDisposalGroup",    "DescriptionFactsCircumstancesSaleOrExpectedDisposal"),
        "Subsidiary": (1,50,"NameSubsidiary")},
    "business":    {"Director": (1,40,"NameEntityOfficer"),
        "Chairman": ("NameEntityOfficer",),
        "ChiefExecutive": ("NameEntityOfficer",),
        "ChairmanChiefExecutive":  ("NameEntityOfficer",),
        "ChiefPartnerLimitedLiabilityPartnership": ("NameEntityOfficer",),
        "CompanySecretary": ("NameEntityOfficer",),
        "CompanySecretaryDirector": ("NameEntityOfficer",),
        "OrdinaryShareClass": (1,5,"DescriptionShareType"),
        "PartnerLLP": (1,20,"NameEntityOfficer"),
        "PreferenceShareClass": (1,5,"DescriptionShareType"),
        "JointAgent": (1,3,"NameThirdPartyAgent"),
        "PrincipalAgent": ("NameThirdPartyAgent",),
        "Chairman": ("NameEntityOfficer",),
        "ChiefExecutive": ("NameEntityOfficer",),
        "ChairmanChiefExecutive": ("NameEntityOfficer",),
        "SeniorPartnerLimitedLiabilityPartnership": ("NameEntityOfficer",),
        "CompanySecretary1": ("NameEntityOfficer",),
        "CompanySecretary2": ("NameEntityOfficer",),
        "CompanySecretaryDirector1": ("NameEntityOfficer",),
        "CompanySecretaryDirector2": ("NameEntityOfficer",),
        "Director": (1,40,"NameEntityOfficer"),
        "PartnerLLP": (1,20,"NameEntityOfficer"),
        "OrdinaryShareClass": (1,5, "DescriptionShareType"),
        "PreferenceShareClass": (1,5, "DescriptionShareType"),
        "DeferredShareClass": (1,5, "DescriptionShareType"),        
        "OtherShareClass": (1,4, "DescriptionShareType"),    
        "Share-basedArrangement": (1,8, "NameShare-basedPaymentArrangement"),
        "Grant": (1,10, "NameOrDescriptionGrantUnderShare-basedPaymentArrangement"),
        "PensionPlan": (1,6, "NameDefinedContributionPlan", "NameDefinedBenefitPlan"),
        "Post-employmentMedicalPlan": (1,2, "NameDefinedContributionPlan", "NameDefinedBenefitPlan"),
        "OtherPost-employmentBenefitPlan": (1,2, "NameDefinedContributionPlan", "NameDefinedBenefitPlan")},
    "charities":    {"Trustee": (1,40,"NameTrustee"),
        "ChairTrustees": ("NameTrustee",),
        "ChiefExecutiveCharity": ("NameTrustee",)},
    "dpl":    {"CombinedCross-sectorActivities": (1,4, "DescriptionActivity"),
        "OtherSpecificActivity": (1,5, "DescriptionActivity")},
    "FRS":    {"SpecificDiscontinuedOperation": (1,8,"DescriptionDiscontinuedOperationOrNon-currentAssetsOrDisposalGroupHeldForSale"),
        "SpecificNon-currentAssetsDisposalGroupHeldForSale": (1,8,"DescriptionDiscontinuedOperationOrNon-currentAssetsOrDisposalGroupHeldForSale"),
        "ReportableOperatingSegment": (1,20,"NameIndividualSegment"),
        "ProductService": (1,12, "NameIndividualSegment"),
        "MajorCustomer": (1,12, "NameIndividualSegment"),
        "SpecificBusinessCombination": (1,10, "NameAcquiredEntity"),
        "ConsumableBiologicalAssetClass": (1,5, "NameOrDescriptionBiologicalAssetClass"),
        "BearerBiologicalAssetClass": (1,5, "NameOrDescriptionBiologicalAssetClass"),
        "Subsidiary": (1,50, "NameSubsidiary"),
        "Associate": (1,50, "NameAssociate"),
        "JointVenture": (1,50, "NameJointVenture"),
        "UnconsolidatedStructuredEntity": (1,5, "NameUnconsolidatedStructuredEntity"),
        "IntermediateParent": (1,5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
        "EntityWithJointControlOrSignificantInfluence": (1,5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
        "OtherGroupMember": (1,8, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
        "KeyManagementIndividualGroup": (1,5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
        "CloseFamilyMember": (1,5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
        "EntityControlledByKeyManagementPersonnel": (1,5, "NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag"),
        "OtherRelatedPartyRelationshipType1ComponentTotalRelatedParties": ("NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag",),
        "OtherRelatedPartyRelationshipType2ComponentTotalRelatedParties": ("NameOrDescriptionRelatedPartyIfNotDefinedByAnotherTag",)}}

def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("HMRC", "HMRCplugin"),)

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateHMRCplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "HMRCplugin", False)
    if not (val.validateHMRCplugin):
        return
    
    if parameters:
        p = parameters.get(ModelValue.qname("type",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:  # override implicit type
            paramType = p[1].lower()
            val.isAccounts = paramType == "accounts"
            val.isComputation = paramType == "computation"
    if not hasattr(val, "isAccounts"):
        val.isComputation = any(compTxmyNamespacePattern.match(doc.targetNamespace)
                                for doc in val.modelXbrl.urlDocs.values()
                                if doc.targetNamespace)
        val.isAccounts = not val.isComputation
    val.isBusiness = any(busTxmyNamespacePattern.match(doc.targetNamespace)
                        for doc in val.modelXbrl.urlDocs.values()
                        if doc.targetNamespace)
            
    val.txmyType = None
    for doc in val.modelXbrl.modelDocument.referencesDocument:
        ns = doc.targetNamespace
        if ns:
            if ns.startswith("http://www.xbrl.org/uk/char/"): val.txmyType = "charities"
            elif ns.startswith("http://www.xbrl.org/uk/gaap/"): val.txmyType = "ukGAAP"
            elif ns.startswith("http://www.xbrl.org/uk/ifrs/"): val.txmyType = "ukIFRS"
            elif ns.startswith("http://xbrl.frc.org.uk/"): val.txmyType = "FRS"
            else: continue
            break
    if not val.txmyType:
        modelXbrl.error("HMRC.TBD",
                        _("No recognized standard taxonomy (UK GAAP, UK IFRS, Charity, or FRS)."),
                        modelObject=val.modelXbrl)


def validateXbrlFinally(val, *args, **kwargs):
    if not (val.validateHMRCplugin):
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

        uniqueFacts = {}  # key = (qname, context hash, unit hash, lang)
        mandatoryFacts = {}
        mandatoryGDV = defaultdict(list)
        factForConceptContextUnitLangHash = defaultdict(list)
        hasCompaniesHouseContext = any(cntx.entityIdentifier[0] == "http://www.companieshouse.gov.uk/"
                                       for cntx in val.modelXbrl.contexts.values())
        
        contextsUsed = set(f.context for f in modelXbrl.factsInInstance if f.context is not None)
        
        gdvSearch = [val.txmyType]
        if val.isBusiness:
            gdvSearch.append("business")
        
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
                    for _gdvType in gdvSearch: # e.g., look in ukIfrs + business if is business
                        gdv = genericDimensionValidation.get(_gdvType,EMPTYDICT).get(l)
                        if gdv: # take first match
                            break
                    if (gdv and (n is None or 
                                 (isinstance(gdv[0],int) and isinstance(gdv[1],int) and n >= gdv[0] and n <= gdv[1]))):
                        gdvFacts = [f for f in gdv if isinstance(f,str)]
                        if len(gdvFacts) == 1:
                            mandatoryGDV[gdvFacts[0]].append(GDV(gdvFacts[0], None, _memName))
                        elif len(gdvFacts) == 2:
                            mandatoryGDV[gdvFacts[0]].append(GDV(gdvFacts[0], gdvFacts[1], _memName))
                            mandatoryGDV[gdvFacts[1]].append(GDV(gdvFacts[1], gdvFacts[0], _memName))

        def checkFacts(facts):
            for f1 in facts:
                cntx = f1.context
                unit = f1.unit
                if getattr(f1,"xValid", 0) >= 4 and cntx is not None and f1.concept is not None:
                    factNamespaceURI = f1.qname.namespaceURI
                    factLocalName = f1.qname.localName
                    if factLocalName in mandatoryItems[val.txmyType]:
                        mandatoryFacts[factLocalName] = f1
                    if factLocalName == "UKCompaniesHouseRegisteredNumber" and val.isAccounts:
                        if hasCompaniesHouseContext:
                            mandatoryFacts[factLocalName] = f1
                        for _cntx in val.modelXbrl.contexts.values():
                            _scheme, _identifier = _cntx.entityIdentifier
                            if _scheme == "http://www.companieshouse.gov.uk/" and f1.xValue != _identifier:
                                modelXbrl.error("JFCVC.3316",
                                    _("Context entity identifier %(identifier)s does not match Company Reference Number (UKCompaniesHouseRegisteredNumber) Location: Accounts (context id %(id)s)"), 
                                    modelObject=(f1, _cntx), identifier=_identifier, id=_cntx.id)
                    if not f1.isNil:
                        factForConceptContextUnitLangHash[f1.conceptContextUnitLangHash].append(f1)
                            
                    if f1.isNumeric:
                        if f1.precision:
                            modelXbrl.error("HMRC.5.4",
                                _("Numeric fact %(fact)s of context %(contextID)s has a precision attribute '%(precision)s'"),
                                modelObject=f1, fact=f1.qname, contextID=f1.contextID, precision=f1.precision)
                        try: # only process validated facts    
                            if f1.xValue < 0: 
                                label = f1.concept.label(lang="en")
                                if not labelHasNegativeTermPattern.match(label):
                                    modelXbrl.error("HMRC.5.3",
                                        _("Numeric fact %(fact)s of context %(contextID)s has a negative value '%(value)s' but label does not have a bracketed negative term (using parentheses): %(label)s"),
                                        modelObject=f1, fact=f1.qname, contextID=f1.contextID, value=f1.value, label=label)
                        except AttributeError:
                            pass  # if not validated it should have failed with a schema error
                        
                    # check GDV
                    if f1.qname.localName in mandatoryGDV:
                        _gdvReqList = mandatoryGDV[factLocalName]
                        for _gdvReq in _gdvReqList:
                            if any(_gdvReq.memLocalName == dim.memberQname.localName           
                                   for dim in cntx.qnameDims.values()
                                   if dim.isExplicit):
                                _gdvReqList.remove(_gdvReq)
                                if _gdvReq.altFact in mandatoryGDV:
                                    _gdvAltList = mandatoryGDV[_gdvReq.altFact]
                                    for _gdvAlt in _gdvAltList:
                                        if any(_gdvAlt.memLocalName == dim.memberQname.localName           
                                               for dim in cntx.qnameDims.values()
                                               if dim.isExplicit):
                                            _gdvAltList.remove(_gdvAlt)
                                    
                    if f1.modelTupleFacts:
                        checkFacts(f1.modelTupleFacts)
                    
        checkFacts(modelXbrl.facts)
        
        if val.isAccounts:
            _missingItems = mandatoryItems[val.txmyType] - mandatoryFacts.keys()
            if hasCompaniesHouseContext and "UKCompaniesHouseRegisteredNumber" not in mandatoryFacts:
                _missingItems.add("UKCompaniesHouseRegisteredNumber")
            if _missingItems:
                modelXbrl.error("JFCVC.3312",
                    _("Mandatory facts missing: %(missingItems)s"), 
                    modelObject=modelXbrl, missingItems=", ".join(_missingItems))
    
            if ("StartDateForPeriodCoveredByReport" in mandatoryItems and
                mandatoryItems["StartDateForPeriodCoveredByReport"].value < "2008-04-06"):
                modelXbrl.error("JFCVC.3313",
                    _("Period Start Date (StartDateForPeriodCoveredByReport) must be 6 April 2008 or later."),
                    modelObject=mandatoryItems["StartDateForPeriodCoveredByReport"])
            
            memLocalNamesMissing = set("{}({})".format(_gdvRec.memLocalName, _gdvRec.factNames)
                                       for _gdv in mandatoryGDV.values()
                                       for _gdvRec in _gdv)
            if memLocalNamesMissing:
                modelXbrl.error("JFCVC.3315",
                    _("Generic dimension members have no associated name or description item, member names (name or description item): %(memberNames)s"), 
                    modelObject=modelXbrl, memberNames=", ".join(sorted(memLocalNamesMissing)))
                


        aspectEqualFacts = defaultdict(list)
        for hashEquivalentFacts in factForConceptContextUnitLangHash.values():
            if len(hashEquivalentFacts) > 1:
                for f in hashEquivalentFacts:
                    aspectEqualFacts[(f.qname,f.contextID,f.unitID,f.xmlLang)].append(f)
                for fList in aspectEqualFacts.values():
                    f0 = fList[0]
                    if any(not f.isVEqualTo(f0) for f in fList[1:]):
                        modelXbrl.error("HMRC.3314",
                            "Inconsistent duplicate fact values %(fact)s: %(values)s.",
                            modelObject=fList, fact=f0.qname, contextID=f0.contextID, values=", ".join(f.value for f in fList))
                aspectEqualFacts.clear()
        del factForConceptContextUnitLangHash, aspectEqualFacts
 
    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)
    
class GDV:
    def __init__(self, fact, altFact, memLocalName):
        self.fact = fact
        self.altFact = altFact
        self.memLocalName = memLocalName
        
    @property
    def factNames(self):
        if self.altFact:
            return ", ".join(sorted(self.fact, self.altFact))
        return self.fact

                
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate HMRC',
    'version': '1.0',
    'description': '''HMRC Validation.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2013-15 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
}
