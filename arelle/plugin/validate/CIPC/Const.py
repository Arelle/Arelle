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
          
''' these validations now done by CIPC formulas                  
mandatoryElements = {
    "ca_fas": { 
        "mandatory": {
            #ec_01: "ifrs-full:DateOfEndOfReportingPeriod2013",
            #ec_01: "cipc-ca:SubmissionDate",
            #ec_58: "cipc-ca:NameOfCompany",
            #ec_55: "cipc-ca:RegistrationNumberOfCompany",
            #ec_40: "cipc-ca:NameOfDesignatedPersonResponsibleForFinancialAccountabilityOfCompany",
            #ec_46: "cipc-ca:TelephoneNumberOfDesignatedPersonResponsibleForFinancialAccountabilityOfCompany",
            #ec_45: "cipc-ca:ResponsibilityForRecordingDayToDayFinancialTransactionsAndMaintainingCompanysFinancialRecords",
            #ec_44: "cipc-ca:ResponsibilityForCompilingFinancialInformationAndPreparingReportsOrStatements",
            #ec_43: "cipc-ca:ResponsibilityForProvidingAdviceToCompanyConcerningMaintenanceOfFinancialRecords",
            #ec_42: "cipc-ca:ResponsibilityForPerformingIndependentReviewOfAnnualFinancialStatements",
            #ec_41: "cipc-ca-enum:RecognisedProfessionOfDesignatedPersonPerformingIndependentReviewOfAnnualFinancialStatements",
            #ec_40: "cipc-ca:PracticeNumberOfDesignatedPersonPerformingIndependentReviewOfAnnualFinancialStatements",
            },
        "footnoteIfNil": {
            },
        },
    "full-ifrs": { 
        "mandatory": {
            #ea_01: "ifrs-full:DateOfEndOfReportingPeriod2013",
            #ec_01: "cipc-ca:SubmissionDate",
            #ec_17: "cipc-ca:DisclosureOfDirectorsResponsibilityExplanatory",
            #ec_18: "cipc-ca:DateOfApprovalOfAnnualFinancialStatements",
            #ec_19: "cipc-ca:DisclosureOfDirectorsReportExplanatory",
            #ec_20: "cipc-ca:DateOfPublicationOfFinancialStatements",
            #ec_21: "cipc-ca:DeclarationOfSignatureByAuthorisedDirector",
            #ec_22: "cipc-ca:DeclarationOfBoardsApprovalAGMForCooperatives",
            #ec_23: "cipc-ca:DeclarationOfDirectorsReportPresence",
            #ec_24: "cipc-ca:DeclarationOfAuditorsReportPresence",
            #ec_25: "cipc-ca-enum:ProfessionalDesignationOfIndividualResponsibleForPreparationOrSupervisingPreparationOfFinancialStatements",
            #ec_26: "cipc-ca:NameOfIndividualResponsibleForPreparationOrSupervisingPreparationOfFinancialStatements",
            #ec_27: "ifrs-full:DisclosureOfNotesAndOtherExplanatoryInformationExplanatory",
            #ec_28: "ifrs-full:DisclosureOfSummaryOfSignificantAccountingPoliciesExplanatory",
            #ec_29: "ifrs-full:LevelOfRoundingUsedInFinancialStatements",
            #ec_30: "ifrs-full:DescriptionOfPresentationCurrency",
            #ec_31: "ifrs-full:PeriodCoveredByFinancialStatements",
            #ec_32: "ifrs-full:DescriptionOfNatureOfFinancialStatements",
            #ec_33: "cipc-ca:PostalAddressSameAsBusinessAddress",
            #ec_34: "cipc-ca:BusinessAddressCountry",
            #ec_35: "cipc-ca:BusinessAddressCity",
            #ec_36: "cipc-ca:BusinessAddressPostalCode",
            #ec_37: "cipc-ca:BusinessAddressStreetName",
            #ec_38: "cipc-ca-enum:TypeOfCompany",
            #ec_39: "cipc-ca:FullRegisteredNameOfCompany",
            #ec_40: "cipc-ca:PracticeNumberOfDesignatedPersonPerformingIndependentReviewOfAnnualFinancialStatements",
            #ec_41: "cipc-ca-enum:RecognisedProfessionOfDesignatedPersonPerformingIndependentReviewOfAnnualFinancialStatements",
            #ec_42: "cipc-ca:ResponsibilityForPerformingIndependentReviewOfAnnualFinancialStatements",
            #ec_43: "cipc-ca:ResponsibilityForProvidingAdviceToCompanyConcerningMaintenanceOfFinancialRecords",
            #ec_44: "cipc-ca:ResponsibilityForCompilingFinancialInformationAndPreparingReportsOrStatements",
            #ec_45: "cipc-ca:ResponsibilityForRecordingDayToDayFinancialTransactionsAndMaintainingCompanysFinancialRecords",
            #ec_46: "cipc-ca:TelephoneNumberOfDesignatedPersonResponsibleForFinancialAccountabilityOfCompany",
            #ec_40: "cipc-ca:NameOfDesignatedPersonResponsibleForFinancialAccountabilityOfCompany",
            #ec_48: "cipc-ca:PrincipalPlaceOfBusinessOfCompany",
            #ec_49: "cipc-ca:PrincipalBusinessOfCompany",
            #ec_50: "cipc-ca:EmailAddressOfCompany",
            #ec_53: "cipc-ca:MaximumNumberOfIndividualsWithBeneficialInterestInSecuritiesOfCompanyOrMembersInCaseOfNonProfitCompany",
            #ec_54: "cipc-ca:AverageNumberOfEmployees",
            #ec_55: "cipc-ca:RegistrationNumberOfCompany",
            #ec_56: "cipc-ca:NameOfDesignatedPersonResponsibleForCompliance",
            #ec_57: "cipc-ca:PublicInterestScore",
            #ec_58: "cipc-ca:NameOfCompany",
            #ec_59: "cipc-ca:RegistrationNumberOfCompanyOfDesignatedPersonResponsibleForCompliance",
            #ec_60: "cipc-ca:CustomerCode"
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
            #ec_01: "ifrs-smes:DateOfEndOfReportingPeriod2013",
            #ec_01: "cipc-ca:SubmissionDate",
            #ec_17: "cipc-ca:DisclosureOfDirectorsResponsibilityExplanatory",
            #ec_18: "cipc-ca:DateOfApprovalOfAnnualFinancialStatements",
            #ec_19: "cipc-ca:DisclosureOfDirectorsReportExplanatory",
            #ec_20: "cipc-ca:DateOfPublicationOfFinancialStatements",
            #ec_21: "cipc-ca:DeclarationOfSignatureByAuthorisedDirector",
            #ec_22: "cipc-ca:DeclarationOfBoardsApprovalAGMForCooperatives",
            #ec_23: "cipc-ca:DeclarationOfDirectorsReportPresence",
            #ec_24: "cipc-ca:DeclarationOfAuditorsReportPresence",
            #ec_25: "cipc-ca-enum:ProfessionalDesignationOfIndividualResponsibleForPreparationOrSupervisingPreparationOfFinancialStatements",
            #ec_26: "cipc-ca:NameOfIndividualResponsibleForPreparationOrSupervisingPreparationOfFinancialStatements",
            #ec_27: "ifrs-smes:DisclosureOfNotesAndOtherExplanatoryInformationExplanatory",
            #ec_28: "ifrs-smes:DisclosureOfSummaryOfSignificantAccountingPoliciesExplanatory",
            #ec_29: "ifrs-smes:LevelOfRoundingUsedInFinancialStatements",
            #ec_30: "ifrs-smes:DescriptionOfPresentationCurrency",
            #ec_31: "ifrs-smes:PeriodCoveredByFinancialStatements",
            #ec_32: "ifrs-smes:DescriptionOfNatureOfFinancialStatements",
            #ec_33: "cipc-ca:PostalAddressSameAsBusinessAddress",
            #ec_34: "cipc-ca:BusinessAddressCountry",
            #ec_35: "cipc-ca:BusinessAddressCity",
            #ec_36: "cipc-ca:BusinessAddressPostalCode",
            #ec_37: "cipc-ca:BusinessAddressStreetName",
            #ec_38: "cipc-ca-enum:TypeOfCompany",
            #ec_39: "cipc-ca:FullRegisteredNameOfCompany",
            #ec_40: "cipc-ca:PracticeNumberOfDesignatedPersonPerformingIndependentReviewOfAnnualFinancialStatements",
            #ec_41: "cipc-ca-enum:RecognisedProfessionOfDesignatedPersonPerformingIndependentReviewOfAnnualFinancialStatements",
            #ec_42: "cipc-ca:ResponsibilityForPerformingIndependentReviewOfAnnualFinancialStatements",
            #ec_43: "cipc-ca:ResponsibilityForProvidingAdviceToCompanyConcerningMaintenanceOfFinancialRecords",
            #ec_44: "cipc-ca:ResponsibilityForCompilingFinancialInformationAndPreparingReportsOrStatements",
            #ec_45: "cipc-ca:ResponsibilityForRecordingDayToDayFinancialTransactionsAndMaintainingCompanysFinancialRecords",
            #ec_46: "cipc-ca:TelephoneNumberOfDesignatedPersonResponsibleForFinancialAccountabilityOfCompany",
            #ec_40: "cipc-ca:NameOfDesignatedPersonResponsibleForFinancialAccountabilityOfCompany",
            #ec_48: "cipc-ca:PrincipalPlaceOfBusinessOfCompany",
            #ec_49: "cipc-ca:PrincipalBusinessOfCompany",
            #ec_50: "cipc-ca:EmailAddressOfCompany",
            #ec_53: "cipc-ca:MaximumNumberOfIndividualsWithBeneficialInterestInSecuritiesOfCompanyOrMembersInCaseOfNonProfitCompany",
            #ec_54: "cipc-ca:AverageNumberOfEmployees",
            #ec_55: "cipc-ca:RegistrationNumberOfCompany",
            #ec_56: "cipc-ca:NameOfDesignatedPersonResponsibleForCompliance",
            #ec_57: "cipc-ca:PublicInterestScore",
            #ec_58: "cipc-ca:NameOfCompany",
            #ec_59: "cipc-ca:RegistrationNumberOfCompanyOfDesignatedPersonResponsibleForCompliance",
            #ec_60: "cipc-ca:CustomerCode"
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
'''            