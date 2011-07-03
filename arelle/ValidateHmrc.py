'''
Created on May 20, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import xml.dom, xml.parsers
import os, re, collections, datetime
from collections import defaultdict
from arelle import (ModelObject, ModelDocument, ModelValue, ValidateXbrl,
                ModelRelationshipSet, XmlUtil, XbrlConst, UrlUtil,
                ValidateFilingDimensions, ValidateFilingDTS, ValidateFilingText)

class ValidateHmrc(ValidateXbrl.ValidateXbrl):
    def __init__(self, modelXbrl):
        super().__init__(modelXbrl)
        
    def validate(self, modelXbrl, parameters=None):
        if not hasattr(modelXbrl.modelDocument, "xmlDocument"): # not parsed
            return
        
        busNamespacePattern = re.compile(r"^http://www\.xbrl\.org/uk/cd")
        gaapNamespacePattern = re.compile(r"^http://www\.xbrl\.org/uk/fr/gaap/pt")
        ifrsNamespacePattern = re.compile(r"^http://www\.iasb\.org/.*ifrs")
        direpNamespacePattern = re.compile(r"^http://www\.xbrl\.org/uk/fr/gaap/pt")
        
        # note that some XFM tests are done by ValidateXbrl to prevent mulstiple node walks
        super(ValidateHmrc,self).validate(modelXbrl, parameters)
        xbrlInstDoc = modelXbrl.modelDocument.xmlDocument
        self.modelXbrl = modelXbrl
        modelXbrl.modelManager.showStatus(_("validating {0}").format(self.disclosureSystem.name))
        
        isAccounts =  XmlUtil.hasAncestor(modelXbrl.modelDocument.xmlRootElement, 
                                          "http://www.govtalk.gov.uk/taxation/CT/3", 
                                          "Accounts")
        isComputation =  XmlUtil.hasAncestor(modelXbrl.modelDocument.xmlRootElement, 
                                             "http://www.govtalk.gov.uk/taxation/CT/3", 
                                             "Computation")

        # instance checks
        if modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or \
           modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL:
            
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

            for iF1, f1 in enumerate(modelXbrl.facts):
                context = f1.context
                unit = f1.unit
                factElementName = f1.localName
                if busNamespacePattern.match(f1.namespaceURI) and factElementName in busLocalNames:
                        busItems[factElementName] = f1
                elif gaapNamespacePattern.match(f1.namespaceURI) and factElementName in gaapLocalNames:
                        gaapItems[factElementName] = f1
                elif ifrsNamespacePattern.match(f1.namespaceURI) and factElementName in ifrsLocalNames:
                        ifrsItems[factElementName] = f1
                elif direpNamespacePattern.match(f1.namespaceURI) and factElementName in direpLocalNames:
                        direpItems[factElementName] = f1

                if context is not None:
                    for f2 in modelXbrl.facts[iF1:]:
                        if (f1.qname == f2.qname and 
                            f2.context is not None and context.isEqualTo(f2.context) and 
                            ((unit is None and f2.unit is None) or
                             (unit is not None and f2.unit is not None and unit.isEqualTo(f2.unit))) and
                            f1.xmlLang == f2.xmlLang and 
                            f1.effectiveValue != f2.effectiveValue):
                            modelXbrl.error(
                                _("Inconsistent duplicate facts {0} context {1} and {2}.").format(
                                          f1.qname, f1.contextID, f2.contextID), 
                                "err", "HMRC.14")

            if isAccounts:
                if "StartDateForPeriodCoveredByReport" not in busItems:
                    modelXbrl.error(
                        _("Period Start Date (uk-bus:StartDateForPeriodCoveredByReport) is missing."), 
                        "err", "HMRC.02")
                elif busItems["StartDateForPeriodCoveredByReport"].value < "2008-04-06":
                    modelXbrl.error(
                        _("Period Start Date (uk-bus:StartDateForPeriodCoveredByReport) must be 6 April 2008 or later."), 
                        "err", "HMRC.02")
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
                        modelXbrl.error(msg, "err", "HMRC.{0}".format(ref))
                if ("DateApprovalAccounts" not in gaapItems and
                    "DateAuthorisationFinancialStatementsForIssue" not in ifrsItems):
                    modelXbrl.error(
                        _("Name of Director Approving Balance Sheet (uk-gaap:NameDirectorSigningAccounts OR ifrs:ExplanationOfBodyOfAuthorisation) is missing."),
                        "err", "HMRC.08")
                if ("ProfitLossForPeriod" not in gaapItems and
                    "ProfitLoss" not in ifrsItems):
                    modelXbrl.error(
                        _("Profit or Loss for the period (uk-gaap:ProfitLossForPeriod OR ifrs:ProfitLoss) is missing."),
                        "err", "HMRC.11")
                if companyReferenceNumberContexts:
                    if "UKCompaniesHouseRegisteredNumber" not in busItems:
                        modelXbrl.error(
                            _("Company Reference Number (uk-bus:UKCompaniesHouseRegisteredNumber) is missing."), 
                            "err", "HMRC.16.1")
                    else:
                        factCompNbr = busItems["UKCompaniesHouseRegisteredNumber"].value
                        for compRefNbr, contextIds in companyReferenceNumberContexts.items():
                            if compRefNbr != factCompNbr:
                                modelXbrl.error(
                                    _("Context entity identifier ({0}) does not match Company Reference Number (uk-bus:UKCompaniesHouseRegisteredNumber) Location: Accounts (context id {1}).").format(
                                        compRefNbr, ",".join(contextIds)), 
                                    "err", "HMRC.16.2")
