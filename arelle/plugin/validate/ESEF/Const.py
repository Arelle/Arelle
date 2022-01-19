'''
Created on June 6, 2018

Filer Guidelines: esma32-60-254_esef_reporting_manual.pdf



@author: Mark V Systems Limited
(c) Copyright 2018 Mark V Systems Limited, All rights reserved.
'''

try:
    import regex as re
except ImportError:
    import re
from arelle.ModelValue import qname
from arelle.XbrlConst import all, notAll, hypercubeDimension, dimensionDomain, domainMember, dimensionDefault, widerNarrower

browserMaxBase64ImageLength = 5242880 # 5MB

standardTaxonomyURIs = {
    "http://www.esma.europa.eu/",
    "https://www.esma.europa.eu/",
    "http://xbrl.ifrs.org/taxonomy/",
    "https://xbrl.ifrs.org/taxonomy/",
    "http://www.xbrl.org/taxonomy/int/lei/",
    "https://www.xbrl.org/taxonomy/int/lei/",
    "http://www.xbrl.org/20",
    "https://www.xbrl.org/20",
    "http://www.xbrl.org/dtr/",
    "https://www.xbrl.org/dtr/",
    "http://www.xbrl.org/lrr/",
    "https://www.xbrl.org/lrr/",
    "http://www.xbrl.org/utr/",
    "https://www.xbrl.org/utr/",
    "http://www.w3.org/1999/xlink/",
    "https://www.w3.org/1999/xlink/",
    }

esefTaxonomyNamespaceURIs = {
    "http://xbrl.ifrs.org/taxonomy/20",
    "http://xbrl.ifrs.org/taxonomy/20",
    }

outdatedTaxonomyURLs = {
    "http://www.esma.europa.eu/taxonomy/2017-03-31/esef_cor.xsd",
    "https://www.esma.europa.eu/taxonomy/2017-03-31/esef_cor.xsd",
    }

esefTaxonomyURLs = {
    "http://www.esma.europa.eu/taxonomy/2019-03-27/esef_cor.xsd",
    "https://www.esma.europa.eu/taxonomy/2019-03-27/esef_cor.xsd",
    "http://www.esma.europa.eu/taxonomy/2020-03-16/esef_cor.xsd",
    "https://www.esma.europa.eu/taxonomy/2020-03-16/esef_cor.xsd",
    "http://www.esma.europa.eu/taxonomy/2021-03-24/esef_cor.xsd",
    "https://www.esma.europa.eu/taxonomy/2021-03-24/esef_cor.xsd",
    }

disallowedURIsPattern = re.compile(
    "http://xbrl.ifrs.org/taxonomy/[0-9-]{10}/full_ifrs/full_ifrs-cor_[0-9-]{10}[.]xsd|"
    "http://www.esma.europa.eu/taxonomy/[0-9-]{10}/esef_all.xsd"
    )


esefFormulaMessagesURLs = {
    "http://www.esma.europa.eu/taxonomy/2019-03-27/esef_cor.xsd":
        "http://www.esma.europa.eu/taxonomy/2019-03-27/esef_cor-gen-en.xml",
    "https://www.esma.europa.eu/taxonomy/2019-03-27/esef_cor.xsd":
        "https://www.esma.europa.eu/taxonomy/2019-03-27/esef_cor-gen-en.xml",
    "http://www.esma.europa.eu/taxonomy/2020-03-16/esef_cor.xsd":
        "http://www.esma.europa.eu/taxonomy/2020-03-16/esef_cor-gen-en.xml",
    "https://www.esma.europa.eu/taxonomy/2020-03-16/esef_cor.xsd":
        "https://www.esma.europa.eu/taxonomy/2020-03-16/esef_cor-gen-en.xml",
    }

DefaultDimensionLinkroles = ("http://www.esma.europa.eu/xbrl/role/cor/ifrs-dim_role-990000",)
LineItemsNotQualifiedLinkrole = "http://www.esma.europa.eu/xbrl/role/cor/esef_role-999999"

qnDomainItemTypes = {qname("{http://www.xbrl.org/dtr/type/non-numeric}nonnum:domainItemType"),
                     qname("{http://www.xbrl.org/dtr/type/2020-01-21}nonnum:domainItemType")}


filenamePatterns = {
    "cal": re.compile(r"(.{1,})-[0-9]{4}-[0-9]{2}-[0-9]{2}_cal[.]xml$"),
    "def": re.compile(r"(.{1,})-[0-9]{4}-[0-9]{2}-[0-9]{2}_def[.]xml$"),
    "lab": re.compile(r"(.{1,})-[0-9]{4}-[0-9]{2}-[0-9]{2}_lab-[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*[.]xml$"),
    "pre": re.compile(r"(.{1,})-[0-9]{4}-[0-9]{2}-[0-9]{2}_pre[.]xml$"),
    "ref": re.compile(r"(.{1,})-[0-9]{4}-[0-9]{2}-[0-9]{2}_ref[.]xml$")
    }

linkbaseRefFilenamePatterns = {
    "http://www.xbrl.org/2003/role/calculationLinkbaseRef": "cal",
    "http://www.xbrl.org/2003/role/definitionLinkbaseRef": "def",
    "http://www.xbrl.org/2003/role/labelLinkbaseRef": "lab",
    "http://www.xbrl.org/2003/role/presentationLinkbaseRef": "pre",
    "http://www.xbrl.org/2003/role/referenceLinkbaseRef": "ref"
    }

mandatory = set() # mandatory element qnames

# hidden references
untransformableTypes = {"anyURI", "base64Binary", "hexBinary", "NOTATION", "QName", "time",
                        "token", "language"}

esefDefinitionArcroles = {
    all, notAll, hypercubeDimension, dimensionDomain, domainMember, dimensionDefault,
    widerNarrower
    }

esefPrimaryStatementPlaceholderNames = (
    # to be augmented with future IFRS releases as they come known, as well as further PFS placeholders
    "StatementOfFinancialPositionAbstract",
    "IncomeStatementAbstract",
    "StatementOfComprehensiveIncomeAbstract",
    "StatementOfCashFlowsAbstract",
    "StatementOfChangesInEquityAbstract",
    "StatementOfChangesInNetAssetsAvailableForBenefitsAbstract",
    "StatementOfProfitOrLossAndOtherComprehensiveIncomeAbstract"
    )

esefStatementsOfMonetaryDeclarationNames = {
    # from Annex II para 1
    "StatementOfFinancialPositionAbstract",
    "StatementOfProfitOrLossAndOtherComprehensiveIncomeAbstract"
    "StatementOfChangesInEquityAbstract",
    "StatementOfCashFlowsAbstract",
    }

esefMandatoryElementNames2020 = (
    "NameOfReportingEntityOrOtherMeansOfIdentification",
    "ExplanationOfChangeInNameOfReportingEntityOrOtherMeansOfIdentificationFromEndOfPrecedingReportingPeriod",
    "DomicileOfEntity",
    "LegalFormOfEntity",
    "CountryOfIncorporation",
    "AddressOfRegisteredOfficeOfEntity",
    "PrincipalPlaceOfBusiness",
    "DescriptionOfNatureOfEntitysOperationsAndPrincipalActivities",
    "NameOfParentEntity",
    "NameOfUltimateParentOfGroup"
    )     

esefMandatoryElementNames2022 = (
    "AddressOfRegisteredOfficeOfEntity",
    "CountryOfIncorporation",
    "DescriptionOfAccountingPolicyForAvailableforsaleFinancialAssetsExplanatory",
    "DescriptionOfAccountingPolicyForBiologicalAssetsExplanatory",
    "DescriptionOfAccountingPolicyForBorrowingCostsExplanatory",
    "DescriptionOfAccountingPolicyForBorrowingsExplanatory",
    "DescriptionOfAccountingPolicyForBusinessCombinationsExplanatory",
    "DescriptionOfAccountingPolicyForBusinessCombinationsAndGoodwillExplanatory",
    "DescriptionOfAccountingPolicyForCashFlowsExplanatory",
    "DescriptionOfAccountingPolicyForCollateralExplanatory",
    "DescriptionOfAccountingPolicyForConstructionInProgressExplanatory",
    "DescriptionOfAccountingPolicyForContingentLiabilitiesAndContingentAssetsExplanatory",
    "DescriptionOfAccountingPolicyForCustomerAcquisitionCostsExplanatory",
    "DescriptionOfAccountingPolicyForCustomerLoyaltyProgrammesExplanatory",
    "DescriptionOfAccountingPolicyForDecommissioningRestorationAndRehabilitationProvisionsExplanatory",
    "DescriptionOfAccountingPolicyForDeferredAcquisitionCostsArisingFromInsuranceContractsExplanatory",
    "DescriptionOfAccountingPolicyForDeferredIncomeTaxExplanatory",
    "DescriptionOfAccountingPolicyForDepreciationExpenseExplanatory",
    "DescriptionOfAccountingPolicyForDerecognitionOfFinancialInstrumentsExplanatory",
    "DescriptionOfAccountingPolicyForDerivativeFinancialInstrumentsExplanatory",
    "DescriptionOfAccountingPolicyForDerivativeFinancialInstrumentsAndHedgingExplanatory",
    "DescriptionOfAccountingPolicyToDetermineComponentsOfCashAndCashEquivalents",
    "DescriptionOfAccountingPolicyForDiscontinuedOperationsExplanatory",
    "DescriptionOfAccountingPolicyForDiscountsAndRebatesExplanatory",
    "DescriptionOfAccountingPolicyForDividendsExplanatory",
    "DescriptionOfAccountingPolicyForEarningsPerShareExplanatory",
    "DescriptionOfAccountingPolicyForEmissionRightsExplanatory",
    "DescriptionOfAccountingPolicyForEmployeeBenefitsExplanatory",
    "DescriptionOfAccountingPolicyForEnvironmentRelatedExpenseExplanatory",
    "DescriptionOfAccountingPolicyForExceptionalItemsExplanatory",
    "DescriptionOfAccountingPolicyForExpensesExplanatory",
    "DescriptionOfAccountingPolicyForExplorationAndEvaluationExpenditures",
    "DescriptionOfAccountingPolicyForFairValueMeasurementExplanatory",
    "DescriptionOfAccountingPolicyForFeeAndCommissionIncomeAndExpenseExplanatory",
    "DescriptionOfAccountingPolicyForFinanceCostsExplanatory",
    "DescriptionOfAccountingPolicyForFinanceIncomeAndCostsExplanatory",
    "DescriptionOfAccountingPolicyForFinancialAssetsExplanatory",
    "DescriptionOfAccountingPolicyForFinancialGuaranteesExplanatory",
    "DescriptionOfAccountingPolicyForFinancialInstrumentsExplanatory",
    "DescriptionOfAccountingPolicyForFinancialInstrumentsAtFairValueThroughProfitOrLossExplanatory",
    "DescriptionOfAccountingPolicyForFinancialLiabilitiesExplanatory",
    "DescriptionOfAccountingPolicyForForeignCurrencyTranslationExplanatory",
    "DescriptionOfAccountingPolicyForFranchiseFeesExplanatory",
    "DescriptionOfAccountingPolicyForFunctionalCurrencyExplanatory",
    "DescriptionOfAccountingPolicyForGoodwillExplanatory",
    "DescriptionOfAccountingPolicyForGovernmentGrants",
    "DescriptionOfAccountingPolicyForHedgingExplanatory",
    "DescriptionOfAccountingPolicyForHeldtomaturityInvestmentsExplanatory",
    "DescriptionOfAccountingPolicyForImpairmentOfAssetsExplanatory",
    "DescriptionOfAccountingPolicyForImpairmentOfFinancialAssetsExplanatory",
    "DescriptionOfAccountingPolicyForImpairmentOfNonfinancialAssetsExplanatory",
    "DescriptionOfAccountingPolicyForIncomeTaxExplanatory",
    "DescriptionOfAccountingPolicyForInsuranceContracts",
    "DescriptionOfAccountingPolicyForIntangibleAssetsAndGoodwillExplanatory",
    "DescriptionOfAccountingPolicyForIntangibleAssetsOtherThanGoodwillExplanatory",
    "DescriptionOfAccountingPolicyForInterestIncomeAndExpenseExplanatory",
    "DescriptionOfAccountingPolicyForInvestmentInAssociates",
    "DescriptionOfAccountingPolicyForInvestmentInAssociatesAndJointVenturesExplanatory",
    "DescriptionOfAccountingPolicyForInvestmentPropertyExplanatory",
    "DescriptionOfAccountingPolicyForInvestmentsInJointVentures",
    "DescriptionOfAccountingPolicyForInvestmentsOtherThanInvestmentsAccountedForUsingEquityMethodExplanatory",
    "DescriptionOfAccountingPolicyForIssuedCapitalExplanatory",
    "DescriptionOfAccountingPolicyForLeasesExplanatory",
    "DescriptionOfAccountingPolicyForLoansAndReceivablesExplanatory",
    "DescriptionOfAccountingPolicyForMeasuringInventories",
    "DescriptionOfAccountingPolicyForMiningAssetsExplanatory",
    "DescriptionOfAccountingPolicyForMiningRightsExplanatory",
    "DescriptionOfAccountingPolicyForNoncurrentAssetsOrDisposalGroupsClassifiedAsHeldForSaleExplanatory",
    "DescriptionOfAccountingPolicyForNoncurrentAssetsOrDisposalGroupsClassifiedAsHeldForSaleAndDiscontinuedOperationsExplanatory",
    "DescriptionOfAccountingPolicyForOffsettingOfFinancialInstrumentsExplanatory",
    "DescriptionOfAccountingPolicyForOilAndGasAssetsExplanatory",
    "DescriptionOfAccountingPolicyForProgrammingAssetsExplanatory",
    "DescriptionOfAccountingPolicyForPropertyPlantAndEquipmentExplanatory",
    "DescriptionOfAccountingPolicyForProvisionsExplanatory",
    "DescriptionOfAccountingPolicyForReclassificationOfFinancialInstrumentsExplanatory",
    "DescriptionOfAccountingPolicyForRecognisingDifferenceBetweenFairValueAtInitialRecognitionAndAmountDeterminedUsingValuationTechniqueExplanatory",
    "DescriptionOfAccountingPolicyForRecognitionOfRevenue",
    "DescriptionOfAccountingPolicyForRegulatoryDeferralAccountsExplanatory",
    "DescriptionOfAccountingPolicyForReinsuranceExplanatory",
    "DescriptionOfAccountingPolicyForRepairsAndMaintenanceExplanatory",
    "DescriptionOfAccountingPolicyForRepurchaseAndReverseRepurchaseAgreementsExplanatory",
    "DescriptionOfAccountingPolicyForResearchAndDevelopmentExpenseExplanatory",
    "DescriptionOfAccountingPolicyForRestrictedCashAndCashEquivalentsExplanatory",
    "DescriptionOfAccountingPolicyForSegmentReportingExplanatory",
    "DescriptionOfAccountingPolicyForServiceConcessionArrangementsExplanatory",
    "DescriptionOfAccountingPolicyForSharebasedPaymentTransactionsExplanatory",
    "DescriptionOfAccountingPolicyForStrippingCostsExplanatory",
    "DescriptionOfAccountingPolicyForSubsidiariesExplanatory",
    "DescriptionOfAccountingPolicyForTaxesOtherThanIncomeTaxExplanatory",
    "DescriptionOfAccountingPolicyForTerminationBenefits",
    "DescriptionOfAccountingPolicyForTradeAndOtherPayablesExplanatory",
    "DescriptionOfAccountingPolicyForTradeAndOtherReceivablesExplanatory",
    "DescriptionOfAccountingPolicyForTradingIncomeAndExpenseExplanatory",
    "DescriptionOfAccountingPolicyForTransactionsWithNoncontrollingInterestsExplanatory",
    "DescriptionOfAccountingPolicyForTransactionsWithRelatedPartiesExplanatory",
    "DescriptionOfAccountingPolicyForTreasurySharesExplanatory",
    "DescriptionOfAccountingPolicyForWarrantsExplanatory",
    "DescriptionOfReasonWhyFinancialStatementsAreNotEntirelyComparable",
    "DescriptionOfNatureOfEntitysOperationsAndPrincipalActivities",
    "DescriptionOfOtherAccountingPoliciesRelevantToUnderstandingOfFinancialStatements",
    "DescriptionOfReasonForUsingLongerOrShorterReportingPeriod",
    "DisclosureOfAccountingJudgementsAndEstimatesExplanatory",
    "DisclosureOfAccruedExpensesAndOtherLiabilitiesExplanatory",
    "DisclosureOfAllowanceForCreditLossesExplanatory",
    "DisclosureOfAssetsAndLiabilitiesWithSignificantRiskOfMaterialAdjustmentExplanatory",
    "DisclosureOfSignificantInvestmentsInAssociatesExplanatory",
    "DisclosureOfAuditorsRemunerationExplanatory",
    "DisclosureOfAuthorisationOfFinancialStatementsExplanatory",
    "DisclosureOfAvailableforsaleAssetsExplanatory",
    "DisclosureOfBasisOfConsolidationExplanatory",
    "DisclosureOfBasisOfPreparationOfFinancialStatementsExplanatory",
    "DisclosureOfBiologicalAssetsAndGovernmentGrantsForAgriculturalActivityExplanatory",
    "DisclosureOfBorrowingsExplanatory",
    "DisclosureOfBusinessCombinationsExplanatory",
    "DisclosureOfCashAndBankBalancesAtCentralBanksExplanatory",
    "DisclosureOfCashAndCashEquivalentsExplanatory",
    "DisclosureOfCashFlowStatementExplanatory",
    "DisclosureOfChangesInAccountingPoliciesExplanatory",
    "DisclosureOfChangesInAccountingPoliciesAccountingEstimatesAndErrorsExplanatory",
    "DisclosureOfClaimsAndBenefitsPaidExplanatory",
    "DisclosureOfCollateralExplanatory",
    "DisclosureOfCommitmentsExplanatory",
    "DisclosureOfCommitmentsAndContingentLiabilitiesExplanatory",
    "DisclosureOfContingentLiabilitiesExplanatory",
    "DisclosureOfCostOfSalesExplanatory",
    "DisclosureOfCreditRiskExplanatory",
    "DisclosureOfDebtSecuritiesExplanatory",
    "DisclosureOfDeferredAcquisitionCostsArisingFromInsuranceContractsExplanatory",
    "DisclosureOfDeferredIncomeExplanatory",
    "DisclosureOfDeferredTaxesExplanatory",
    "DisclosureOfDepositsFromBanksExplanatory",
    "DisclosureOfDepositsFromCustomersExplanatory",
    "DisclosureOfDepreciationAndAmortisationExpenseExplanatory",
    "DisclosureOfDerivativeFinancialInstrumentsExplanatory",
    "DisclosureOfDiscontinuedOperationsExplanatory",
    "DisclosureOfDividendsExplanatory",
    "DisclosureOfEarningsPerShareExplanatory",
    "DisclosureOfEffectOfChangesInForeignExchangeRatesExplanatory",
    "DisclosureOfEmployeeBenefitsExplanatory",
    "DisclosureOfEntitysReportableSegmentsExplanatory",
    "DisclosureOfEventsAfterReportingPeriodExplanatory",
    "DisclosureOfExpensesExplanatory",
    "DisclosureOfExpensesByNatureExplanatory",
    "DisclosureOfExplorationAndEvaluationAssetsExplanatory",
    "DisclosureOfFairValueMeasurementExplanatory",
    "DisclosureOfFairValueOfFinancialInstrumentsExplanatory",
    "DisclosureOfFeeAndCommissionIncomeExpenseExplanatory",
    "DisclosureOfFinanceCostExplanatory",
    "DisclosureOfFinanceIncomeExpenseExplanatory",
    "DisclosureOfFinanceIncomeExplanatory",
    "DisclosureOfFinancialAssetsHeldForTradingExplanatory",
    "DisclosureOfFinancialInstrumentsExplanatory",
    "DisclosureOfFinancialInstrumentsAtFairValueThroughProfitOrLossExplanatory",
    "DisclosureOfFinancialInstrumentsDesignatedAtFairValueThroughProfitOrLossExplanatory",
    "DisclosureOfFinancialInstrumentsHeldForTradingExplanatory",
    "DisclosureOfFinancialLiabilitiesHeldForTradingExplanatory",
    "DisclosureOfFinancialRiskManagementExplanatory",
    "DisclosureOfFirstTimeAdoptionExplanatory",
    "DisclosureOfGeneralAndAdministrativeExpenseExplanatory",
    "DisclosureOfGeneralInformationAboutFinancialStatementsExplanatory",
    "DisclosureOfGoingConcernExplanatory",
    "DisclosureOfGoodwillExplanatory",
    "DisclosureOfGovernmentGrantsExplanatory",
    "DisclosureOfImpairmentOfAssetsExplanatory",
    "DisclosureOfIncomeTaxExplanatory",
    "DisclosureOfInformationAboutEmployeesExplanatory",
    "DisclosureOfInformationAboutKeyManagementPersonnelExplanatory",
    "DisclosureOfInsuranceContractsExplanatory",
    "DisclosureOfInsurancePremiumRevenueExplanatory",
    "DisclosureOfIntangibleAssetsExplanatory",
    "DisclosureOfIntangibleAssetsAndGoodwillExplanatory",
    "DisclosureOfInterestExpenseExplanatory",
    "DisclosureOfInterestIncomeExpenseExplanatory",
    "DisclosureOfInterestIncomeExplanatory",
    "DisclosureOfInventoriesExplanatory",
    "DisclosureOfInvestmentContractsLiabilitiesExplanatory",
    "DisclosureOfInvestmentPropertyExplanatory",
    "DisclosureOfInvestmentsAccountedForUsingEquityMethodExplanatory",
    "DisclosureOfInvestmentsOtherThanInvestmentsAccountedForUsingEquityMethodExplanatory",
    "DisclosureOfIssuedCapitalExplanatory",
    "DisclosureOfJointVenturesExplanatory",
    "DisclosureOfLeasePrepaymentsExplanatory",
    "DisclosureOfLeasesExplanatory",
    "DisclosureOfLiquidityRiskExplanatory",
    "DisclosureOfLoansAndAdvancesToBanksExplanatory",
    "DisclosureOfLoansAndAdvancesToCustomersExplanatory",
    "DisclosureOfMarketRiskExplanatory",
    "DisclosureOfNetAssetValueAttributableToUnitholdersExplanatory",
    "DisclosureOfNoncontrollingInterestsExplanatory",
    "DisclosureOfNoncurrentAssetsHeldForSaleAndDiscontinuedOperationsExplanatory",
    "DisclosureOfNoncurrentAssetsOrDisposalGroupsClassifiedAsHeldForSaleExplanatory",
    "DisclosureOfObjectivesPoliciesAndProcessesForManagingCapitalExplanatory",
    "DisclosureOfOtherAssetsExplanatory",
    "DisclosureOfOtherCurrentAssetsExplanatory",
    "DisclosureOfOtherCurrentLiabilitiesExplanatory",
    "DisclosureOfOtherLiabilitiesExplanatory",
    "DisclosureOfOtherNoncurrentAssetsExplanatory",
    "DisclosureOfOtherNoncurrentLiabilitiesExplanatory",
    "DisclosureOfOtherOperatingExpenseExplanatory",
    "DisclosureOfOtherOperatingIncomeExpenseExplanatory",
    "DisclosureOfOtherOperatingIncomeExplanatory",
    "DisclosureOfPrepaymentsAndOtherAssetsExplanatory",
    "DisclosureOfProfitLossFromOperatingActivitiesExplanatory",
    "DisclosureOfPropertyPlantAndEquipmentExplanatory",
    "DisclosureOfOtherProvisionsExplanatory",
    "DisclosureOfReclassificationOfFinancialInstrumentsExplanatory",
    "DisclosureOfReclassificationsOrChangesInPresentationExplanatory",
    "DisclosureOfRecognisedRevenueFromConstructionContractsExplanatory"
    "DisclosureOfReinsuranceExplanatory",
    "DisclosureOfRelatedPartyExplanatory",
    "DisclosureOfRepurchaseAndReverseRepurchaseAgreementsExplanatory",
    "DisclosureOfResearchAndDevelopmentExpenseExplanatory",
    "DisclosureOfReservesAndOtherEquityInterestExplanatory",
    "DisclosureOfRestrictedCashAndCashEquivalentsExplanatory",
    "DisclosureOfRevenueExplanatory",
    "DisclosureOfServiceConcessionArrangementsExplanatory",
    "DisclosureOfShareCapitalReservesAndOtherEquityInterestExplanatory",
    "DisclosureOfSharebasedPaymentArrangementsExplanatory",
    "DisclosureOfSummaryOfSignificantAccountingPoliciesExplanatory",
    "DisclosureOfSubordinatedLiabilitiesExplanatory",
    "DisclosureOfSignificantInvestmentsInSubsidiariesExplanatory",
    "DisclosureOfTaxReceivablesAndPayablesExplanatory",
    "DisclosureOfTradeAndOtherPayablesExplanatory",
    "DisclosureOfTradeAndOtherReceivablesExplanatory",
    "DisclosureOfTradingIncomeExpenseExplanatory",
    "DisclosureOfTreasurySharesExplanatory",
    "DescriptionOfUncertaintiesOfEntitysAbilityToContinueAsGoingConcern",
    "DividendsProposedOrDeclaredBeforeFinancialStatementsAuthorisedForIssueButNotRecognisedAsDistributionToOwners",
    "DividendsProposedOrDeclaredBeforeFinancialStatementsAuthorisedForIssueButNotRecognisedAsDistributionToOwnersPerShare",
    "DividendsRecognisedAsDistributionsToOwnersPerShare",
    "DomicileOfEntity",
    "ExplanationOfDepartureFromIFRS",
    "ExplanationOfFactAndBasisForPreparationOfFinancialStatementsWhenNotGoingConcernBasis",
    "ExplanationOfFinancialEffectOfDepartureFromIFRS",
    "ExplanationOfAssumptionAboutFutureWithSignificantRiskOfResultingInMaterialAdjustments",
    "ExplanationWhyFinancialStatementsNotPreparedOnGoingConcernBasis",
    "LegalFormOfEntity",
    "LengthOfLifeOfLimitedLifeEntity",
    "NameOfParentEntity",
    "NameOfReportingEntityOrOtherMeansOfIdentification",
    "NameOfUltimateParentOfGroup",
    "PrincipalPlaceOfBusiness",
    "StatementOfIFRSCompliance",
)            