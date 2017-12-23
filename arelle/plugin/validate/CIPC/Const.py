'''
Created on Dec 21, 2017

Filer Guidelines: http://www.cipc.co.za/files/8615/1333/0514/25082017_Guidelines_for_Filing__AFSs_in_XBRL_by_Client_Companies_Technical_Aspects_v1-7_HVMZ.pdf

Taxonomy Architecture: http://www.cipc.co.za/files/1715/1325/5802/CIPC_XBRL_Taxonomy_Framework_Architecture_-_2017-12-15.pdf


@author: Mark V Systems Limited
(c) Copyright 2017 Mark V Systems Limited, All rights reserved.
'''
cpicModules = {
    "ca_fas": "ca_fas",
    "full_ifrs": "full-ifrs",
    "ifrs_for_smes": "ifrs-smes"
    }
                    
mandatoryElements = {
    "ca_fas": { 
        "mandatory": {
            "ifrs-full:DateOfEndOfReportingPeriod2013",
            "cipc-ca:SubmissionDate",
            "cipc-ca:NameOfCompany",
            "cipc-ca:RegistrationNumberOfCompany",
            "cipc-ca:NameOfDesignatedPersonResponsibleForFinancialAccountabilityOfCompany",
            "cipc-ca:TelephoneNumberOfDesignatedPersonResponsibleForFinancialAccountabilityOfCompany",
            "cipc-ca:ResponsibilityForRecordingDayToDayFinancialTransactionsAndMaintainingCompanysFinancialRecords",
            "cipc-ca:ResponsibilityForCompilingFinancialInformationAndPreparingReportsOrStatements",
            "cipc-ca:ResponsibilityForProvidingAdviceToCompanyConcerningMaintenanceOfFinancialRecords",
            "cipc-ca:ResponsibilityForPerformingIndependentReviewOfAnnualFinancialStatements",
            "cipc-ca-enum:RecognisedProfessionOfDesignatedPersonPerformingIndependentReviewOfAnnualFinancialStatements",
            "cipc-ca:PracticeNumberOfDesignatedPersonPerformingIndependentReviewOfAnnualFinancialStatements",
            },
        "footnoteIfNil": {
            },
        },
    "full-ifrs": { 
        "mandatory": {
            "ifrs-full:DateOfEndOfReportingPeriod2013",
            "cipc-ca:SubmissionDate",
            "cipc-ca:DisclosureOfDirectorsResponsibilityExplanatory",
            "cipc-ca:DateOfApprovalOfAnnualFinancialStatements",
            "cipc-ca:DisclosureOfDirectorsReportExplanatory",
            "cipc-ca:DateOfPublicationOfFinancialStatements",
            "cipc-ca:DeclarationOfSignatureByAuthorisedDirector",
            "cipc-ca:DeclarationOfBoardsApprovalAGMForCooperatives",
            "cipc-ca:DeclarationOfDirectorsReportPresence",
            "cipc-ca:DeclarationOfAuditorsReportPresence",
            "cipc-ca-enum:ProfessionalDesignationOfIndividualResponsibleForPreparationOrSupervisingPreparationOfFinancialStatements",
            "cipc-ca:NameOfIndividualResponsibleForPreparationOrSupervisingPreparationOfFinancialStatements",
            "ifrs-full:DisclosureOfNotesAndOtherExplanatoryInformationExplanatory",
            "ifrs-full:DisclosureOfSummaryOfSignificantAccountingPoliciesExplanatory",
            "ifrs-full:LevelOfRoundingUsedInFinancialStatements",
            "ifrs-full:DescriptionOfPresentationCurrency",
            "ifrs-full:PeriodCoveredByFinancialStatements",
            "ifrs-full:DescriptionOfNatureOfFinancialStatements",
            "cipc-ca:PostalAddressSameAsBusinessAddress",
            "cipc-ca:BusinessAddressCountry",
            "cipc-ca:BusinessAddressCity",
            "cipc-ca:BusinessAddressPostalCode",
            "cipc-ca:BusinessAddressStreetName",
            "cipc-ca-enum:TypeOfCompany",
            "cipc-ca:FullRegisteredNameOfCompany",
            "cipc-ca:PracticeNumberOfDesignatedPersonPerformingIndependentReviewOfAnnualFinancialStatements",
            "cipc-ca-enum:RecognisedProfessionOfDesignatedPersonPerformingIndependentReviewOfAnnualFinancialStatements",
            "cipc-ca:ResponsibilityForPerformingIndependentReviewOfAnnualFinancialStatements",
            "cipc-ca:ResponsibilityForProvidingAdviceToCompanyConcerningMaintenanceOfFinancialRecords",
            "cipc-ca:ResponsibilityForCompilingFinancialInformationAndPreparingReportsOrStatements",
            "cipc-ca:ResponsibilityForRecordingDayToDayFinancialTransactionsAndMaintainingCompanysFinancialRecords",
            "cipc-ca:TelephoneNumberOfDesignatedPersonResponsibleForFinancialAccountabilityOfCompany",
            "cipc-ca:NameOfDesignatedPersonResponsibleForFinancialAccountabilityOfCompany",
            "cipc-ca:PrincipalPlaceOfBusinessOfCompany",
            "cipc-ca:PrincipalBusinessOfCompany",
            "cipc-ca:EmailAddressOfCompany",
            "cipc-ca:MaximumNumberOfIndividualsWithBeneficialInterestInSecuritiesOfCompanyOrMembersInCaseOfNonProfitCompany",
            "cipc-ca:AverageNumberOfEmployees",
            "cipc-ca:RegistrationNumberOfCompany",
            "cipc-ca:NameOfDesignatedPersonResponsibleForCompliance",
            "cipc-ca:PublicInterestScore",
            "cipc-ca:NameOfCompany",
            "cipc-ca:RegistrationNumberOfCompanyOfDesignatedPersonResponsibleForCompliance",
            "cipc-ca:CustomerCode"
                    },
        "footnoteIfNil": {
            "ifrs-full:Revenue",
            "ifrs-full:ChangesInEquity",
            "ifrs-full:CashAndCashEquivalents",
            "ifrs-full:IncreaseDecreaseInCashAndCashEquivalents",
            "ifrs-full:CashFlowsFromUsedInFinancingActivities",
            "ifrs-full:CashFlowsFromUsedInInvestingActivities",
            "ifrs-full:CashFlowsFromUsedInOperatingActivities",
            "ifrs-full:ComprehensiveIncome",
            "ifrs-full:OtherComprehensiveIncome",
            "ifrs-full:IncomeTaxExpenseContinuingOperations",
            "ifrs-full:ProfitLoss",
            "ifrs-full:ProfitLossBeforeTax",
            "ifrs-full:Assets",
            "ifrs-full:Equity",
            "ifrs-full:EquityAndLiabilities",
            "cipc-ca:CellPhoneNumberOfCompany",
            "ifrs-full:Liabilities"
                    },
        },
    "ifrs-smes": { 
        "mandatory": {
            "ifrs-smes:DateOfEndOfReportingPeriod2013",
            "cipc-ca:SubmissionDate",
            "cipc-ca:DisclosureOfDirectorsResponsibilityExplanatory",
            "cipc-ca:DateOfApprovalOfAnnualFinancialStatements",
            "cipc-ca:DisclosureOfDirectorsReportExplanatory",
            "cipc-ca:DateOfPublicationOfFinancialStatements",
            "cipc-ca:DeclarationOfSignatureByAuthorisedDirector",
            "cipc-ca:DeclarationOfBoardsApprovalAGMForCooperatives",
            "cipc-ca:DeclarationOfDirectorsReportPresence",
            "cipc-ca:DeclarationOfAuditorsReportPresence",
            "cipc-ca-enum:ProfessionalDesignationOfIndividualResponsibleForPreparationOrSupervisingPreparationOfFinancialStatements",
            "cipc-ca:NameOfIndividualResponsibleForPreparationOrSupervisingPreparationOfFinancialStatements",
            "ifrs-smes:DisclosureOfNotesAndOtherExplanatoryInformationExplanatory",
            "ifrs-smes:DisclosureOfSummaryOfSignificantAccountingPoliciesExplanatory",
            "ifrs-smes:LevelOfRoundingUsedInFinancialStatements",
            "ifrs-smes:DescriptionOfPresentationCurrency",
            "ifrs-smes:PeriodCoveredByFinancialStatements",
            "ifrs-smes:DescriptionOfNatureOfFinancialStatements",
            "cipc-ca:PostalAddressSameAsBusinessAddress",
            "cipc-ca:BusinessAddressCountry",
            "cipc-ca:BusinessAddressCity",
            "cipc-ca:BusinessAddressPostalCode",
            "cipc-ca:BusinessAddressStreetName",
            "cipc-ca-enum:TypeOfCompany",
            "cipc-ca:FullRegisteredNameOfCompany",
            "cipc-ca:PracticeNumberOfDesignatedPersonPerformingIndependentReviewOfAnnualFinancialStatements",
            "cipc-ca-enum:RecognisedProfessionOfDesignatedPersonPerformingIndependentReviewOfAnnualFinancialStatements",
            "cipc-ca:ResponsibilityForPerformingIndependentReviewOfAnnualFinancialStatements",
            "cipc-ca:ResponsibilityForProvidingAdviceToCompanyConcerningMaintenanceOfFinancialRecords",
            "cipc-ca:ResponsibilityForCompilingFinancialInformationAndPreparingReportsOrStatements",
            "cipc-ca:ResponsibilityForRecordingDayToDayFinancialTransactionsAndMaintainingCompanysFinancialRecords",
            "cipc-ca:TelephoneNumberOfDesignatedPersonResponsibleForFinancialAccountabilityOfCompany",
            "cipc-ca:NameOfDesignatedPersonResponsibleForFinancialAccountabilityOfCompany",
            "cipc-ca:PrincipalPlaceOfBusinessOfCompany",
            "cipc-ca:PrincipalBusinessOfCompany",
            "cipc-ca:EmailAddressOfCompany",
            "cipc-ca:MaximumNumberOfIndividualsWithBeneficialInterestInSecuritiesOfCompanyOrMembersInCaseOfNonProfitCompany",
            "cipc-ca:AverageNumberOfEmployees",
            "cipc-ca:RegistrationNumberOfCompany",
            "cipc-ca:NameOfDesignatedPersonResponsibleForCompliance",
            "cipc-ca:PublicInterestScore",
            "cipc-ca:NameOfCompany",
            "cipc-ca:RegistrationNumberOfCompanyOfDesignatedPersonResponsibleForCompliance",
            "cipc-ca:CustomerCode"
            },
        "footnoteIfNil": {
            "ifrs-smes:Revenue",
            "ifrs-smes:ChangesInEquity",
            "ifrs-smes:CashAndCashEquivalents",
            "ifrs-smes:IncreaseDecreaseInCashAndCashEquivalents",
            "ifrs-smes:CashFlowsFromUsedInFinancingActivities",
            "ifrs-smes:CashFlowsFromUsedInInvestingActivities",
            "ifrs-smes:CashFlowsFromUsedInOperatingActivities",
            "ifrs-smes:ComprehensiveIncome",
            "ifrs-smes:OtherComprehensiveIncome",
            "ifrs-smes:IncomeTaxExpenseContinuingOperations",
            "ifrs-smes:ProfitLoss",
            "ifrs-smes:ProfitLossBeforeTax",
            "ifrs-smes:Assets",
            "ifrs-smes:Equity",
            "ifrs-smes:EquityAndLiabilities",
            "cipc-ca:CellPhoneNumberOfCompany",
            "ifrs-smes:Liabilities"
            },
        },
    None: {  # allow logic to work with unspecified or ambiguous reporting module 
        "mandatory": {
            },
        "footnoteIfNil": {
            },
        }
     }
                  