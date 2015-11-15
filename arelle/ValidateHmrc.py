'''
Created on May 20, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.

based on http://www.hmrc.gov.uk/ebu/ct_techpack/joint-filing-validation-checks.pdf

Deprecated Nov 15, 2015.  Use plugin/validate/HMRC/__init__.py

'''
import xml.dom, xml.parsers
import os, re, collections, datetime
from collections import defaultdict
from arelle import (ModelObject, ModelDocument, ModelValue, ValidateXbrl,
                ModelRelationshipSet, XmlUtil, XbrlConst, UrlUtil,
                ValidateFilingDimensions, ValidateFilingDTS, ValidateFilingText)
from arelle.XmlValidate import UNVALIDATED, VALID

class ValidateHmrc(ValidateXbrl.ValidateXbrl):
    def __init__(self, modelXbrl):
        super(ValidateHmrc, self).__init__(modelXbrl)
        
    def validate(self, modelXbrl, parameters=None):
        if not hasattr(modelXbrl.modelDocument, "xmlDocument"): # not parsed
            return
        
        busNamespacePattern = re.compile(r"^http://www\.xbrl\.org/uk/cd/business")
        gaapNamespacePattern = re.compile(r"^http://www\.xbrl\.org/uk/gaap/core")
        ifrsNamespacePattern = re.compile(r"^http://www\.iasb\.org/.*ifrs")
        direpNamespacePattern = re.compile(r"^http://www\.xbrl\.org/uk/reports/direp")
        labelHasNegativeTermPattern = re.compile(r".*[(].*\w.*[)].*")
        
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
        if parameters:
            p = self.parameters.get(ModelValue.qname("type",noPrefixIsNoNamespace=True))
            if p and len(p) == 2:  # override implicit type
                paramType = p[1].lower()
                isAccounts = paramType == "accounts"
                isComputation = paramType == "computation"

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

            if isAccounts:
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

        modelXbrl.modelManager.showStatus(_("ready"), 2000)
