'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import ModelDocument, ModelValue, XmlUtil
from arelle.ModelValue import qname
try:
    import regex as re
except ImportError:
    import re
from collections import defaultdict

qnFIndicators = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:fIndicators")
qnFilingIndicator = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:filingIndicator")
qnPercentItemType = qname("{http://www.xbrl.org/dtr/type/numeric}num:percentItemType")
integerItemTypes = {"integerItemType", "nonPositiveIntegerItemType", "negativeIntegerItemType",
                    "longItemType", "intItemType", "shortItemType", "byteItemType",
                    "nonNegativeIntegerItemType", "unsignedLongItemType", "unsignedIntItemType",
                    "unsignedShortItemType", "unsignedByteItemType", "positiveIntegerItemType"}

def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("HMRC", "HMRCplugin"),)

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateHMRCplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "HMRCplugin", False)
    if not (val.validateHMRCplugin):
        return

    val.isAccounts =  XmlUtil.hasAncestor(val.modelXbrl.modelDocument.xmlRootElement, 
                                          "http://www.govtalk.gov.uk/taxation/CT/3", 
                                          "Accounts")
    val.isComputation =  XmlUtil.hasAncestor(val.modelXbrl.modelDocument.xmlRootElement, 
                                             "http://www.govtalk.gov.uk/taxation/CT/3", 
                                             "Computation")
    if parameters:
        p = parameters.get(ModelValue.qname("type",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:  # override implicit type
            paramType = p[1].lower()
            val.isAccounts = paramType == "accounts"
            val.isComputation = paramType == "computation"

def validateXbrlFinally(val, *args, **kwargs):
    if not (val.validateHMRCplugin):
        return

    modelXbrl = val.modelXbrl
    modelDocument = modelXbrl.modelDocument

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)
    
    if modelDocument.type == ModelDocument.Type.INSTANCE and (val.validateEBA or val.validateEIOPA):
        busNamespacePattern = re.compile(r"^http://www\.xbrl\.org/uk/cd/business")
        gaapNamespacePattern = re.compile(r"^http://www\.xbrl\.org/uk/gaap/core")
        ifrsNamespacePattern = re.compile(r"^http://www\.iasb\.org/.*ifrs")
        direpNamespacePattern = re.compile(r"^http://www\.xbrl\.org/uk/reports/direp")
        labelHasNegativeTermPattern = re.compile(r".*[(].*\w.*[)].*")
        
        companyReferenceNumberContexts = defaultdict(list)
        for c1 in modelXbrl.contexts.values():
            scheme, identifier = c1.entityIdentifier
            if scheme == "http://www.companieshouse.gov.uk/":
                companyReferenceNumberContexts[identifier].append(c1.id)

        busLocalNames = {
            "EntityCurrentLegalOrRegisteredName", 
            "StartDateForPeriodCoveredByReport",
            "EndDateForPeriodCoveredByReport",
            "BalanceSheetDate",
            "DateApprovalAccounts",
            "NameDirectorSigningAccounts",
            "EntityDormant",
            "EntityTrading",
            "UKCompaniesHouseRegisteredNumber"
             }
        busItems = {}
        
        gaapLocalNames = {
            "DateApprovalAccounts",
            "NameDirectorSigningAccounts",
            "ProfitLossForPeriod"
            }
        gaapItems = {}
        
        ifrsLocalNames = {
            "DateAuthorisationFinancialStatementsForIssue",
            "ExplanationOfBodyOfAuthorisation",
            "ProfitLoss"
            }
        ifrsItems = {}
        
        direpLocalNames = {
            "DateSigningDirectorsReport",
            "DirectorSigningReport"
            }
        direpItems = {}
        
        uniqueFacts = {}  # key = (qname, context hash, unit hash, lang)
        
        def checkFacts(facts):
            for f1 in facts:
                context = f1.context
                unit = f1.unit
                if getattr(f1,"xValid", 0) >= 4:
                    factNamespaceURI = f1.qname.namespaceURI
                    factLocalName = f1.qname.localName
                    if busNamespacePattern.match(factNamespaceURI) and factLocalName in busLocalNames:
                            busItems[factLocalName] = f1
                    elif gaapNamespacePattern.match(factNamespaceURI) and factLocalName in gaapLocalNames:
                            gaapItems[factLocalName] = f1
                    elif ifrsNamespacePattern.match(factNamespaceURI) and factLocalName in ifrsLocalNames:
                            ifrsItems[factLocalName] = f1
                    elif direpNamespacePattern.match(factNamespaceURI) and factLocalName in direpLocalNames:
                            direpItems[factLocalName] = f1
                            
                    dupKey = (f1.concept,
                              context.contextDimAwareHash if context is not None else None,
                              unit.hash if unit is not None else None,
                              f1.xmlLang)
    
                    if context is not None:
                        if f1 in uniqueFacts:
                            f2 = uniqueFacts[f1]
                            if (f1.effectiveValue != f2.effectiveValue):
                                modelXbrl.error("HMRC.14",
                                    _("Inconsistent duplicate facts %(fact)s context %(contextID)s and %(contextID2)s."),
                                    modelObject=(f1, f2), fact=f1.qname, contextID=f1.contextID, contextID2=f2.contextID)
                    uniqueFacts[dupKey] = f1
                                                    
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
                    if f1.modelTupleFacts:
                        checkFacts(f1.modelTupleFacts)
                    
        checkFacts(modelXbrl.facts)

        if val.isAccounts:
            if "StartDateForPeriodCoveredByReport" not in busItems:
                modelXbrl.error("HMRC.02",
                    _("Period Start Date (uk-bus:StartDateForPeriodCoveredByReport) is missing."), 
                    modelObject=modelXbrl)
            elif busItems["StartDateForPeriodCoveredByReport"].value < "2008-04-06":
                modelXbrl.error("HMRC.02",
                    _("Period Start Date (uk-bus:StartDateForPeriodCoveredByReport) must be 6 April 2008 or later."),
                    modelObject=modelXbrl)
            for items, name, msg, ref in (
                      (busItems,"EntityCurrentLegalOrRegisteredName",
                       _("Company Name (uk-bus:EntityCurrentLegalOrRegisteredName) is missing."),
                       "01"),
                      (busItems,"EndDateForPeriodCoveredByReport",
                       _("Period End Date (uk-bus:EndDateForPeriodCoveredByReport) is missing."), 
                       "03"),
                      (busItems,"BalanceSheetDate",
                       _("Balance Sheet Date (uk-bus:BalanceSheetDate) is missing."), 
                       "06"),
                      (busItems,"EntityDormant",
                       _("Dormant/non-dormant indicator (uk-bus:EntityDormant) is missing."), 
                       "09"),
                      (busItems,"EntityTrading",
                       _("Trading/non-trading indicator (uk-bus:EntityTrading) is missing."), 
                       "10"),
                      (direpItems,"DateSigningDirectorsReport",
                       _("Date of signing Directors Report (uk-direp:DateSigningDirectorsReport) is missing."), 
                       "12"),
                      (direpItems,"DirectorSigningReport",
                       _("Name of Director signing Directors Report (uk-direp:DirectorSigningReport) is missing."), 
                       "13"),
                       ):
                if name not in items:
                    modelXbrl.error("HMRC.{0}".format(ref), msg, modelObject=modelXbrl,
                                    messageCodes=("HMRC.01","HMRC.03","HMRC.06","HMRC.09","HMRC.10","HMRC.12","HMRC.13"))
            if ("DateApprovalAccounts" not in gaapItems and
                "DateAuthorisationFinancialStatementsForIssue" not in ifrsItems):
                modelXbrl.error("HMRC.07",
                    _("Balance Sheet Date of Approval (uk-gaap:DateApprovalAccounts) is missing OR Balance Sheet Date of Approval (uk-ifrs:DateAuthorisationFinancialStatementsForIssue) is missing."),
                    modelObject=modelXbrl)
            if ("NameDirectorSigningAccounts" not in gaapItems and
                "ExplanationOfBodyOfAuthorisation" not in ifrsItems):
                modelXbrl.error("HMRC.08",
                    _("Name of Director Approving Balance Sheet (uk-gaap:NameDirectorSigningAccounts) is missing OR Name of Director Approving Balance Sheet (ifrs:ExplanationOfBodyOfAuthorisation) is missing."),
                    modelObject=modelXbrl)
            if ("ProfitLossForPeriod" not in gaapItems and
                "ProfitLoss" not in ifrsItems):
                modelXbrl.error("HMRC.11",
                    _("Profit or Loss for the period (uk-gaap:ProfitLossForPeriod OR ifrs:ProfitLoss) is missing."),
                    modelObject=modelXbrl)
            if companyReferenceNumberContexts:
                if "UKCompaniesHouseRegisteredNumber" not in busItems:
                    modelXbrl.error("HMRC.16.1",
                        _("Company Reference Number (uk-bus:UKCompaniesHouseRegisteredNumber) is missing."), 
                        modelObject=modelXbrl)
                else:
                    factCompNbr = busItems["UKCompaniesHouseRegisteredNumber"].value
                    for compRefNbr, contextIds in companyReferenceNumberContexts.items():
                        if compRefNbr != factCompNbr:
                            modelXbrl.error("HMRC.16.2",
                                _("Context entity identifier (%(entityIdentifier)s) does not match Company Reference Number (uk-bus:UKCompaniesHouseRegisteredNumber) Location: Accounts (context id %(contextID)s)."),
                                modelObject=modelXbrl, entityIdentifier=compRefNbr, contextID=",".join(contextIds))
 
    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)

                
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
