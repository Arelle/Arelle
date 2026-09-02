"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from arelle.Cntlr import Cntlr
from arelle.ModelValue import QName, qname
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.validate.ValidationPlugin import ValidationPlugin

from .PluginValidationDataExtension import PluginValidationDataExtension

TC_NAMESPACE = "http://xbrl.ird.gov.hk/taxonomy/2026-04-01/ird_tc"


def tcQn(local: str) -> QName:
    return qname(f"{{{TC_NAMESPACE}}}{local}")


class ValidationPluginExtension(ValidationPlugin):
    def newPluginData(
        self,
        cntlr: Cntlr,
        validateXbrl: ValidateXbrl | None,
    ) -> PluginValidationDataExtension:

        # Entry point URIs
        BASE = "http://xbrl.ird.gov.hk/taxonomy/2026-04-01/"
        validTc = frozenset([
            f"{BASE}ird_tc_entry_point_2026-04-01.xsd",
            f"{BASE}ird_tc-zh-hk_entry_point_2026-04-01.xsd",
        ])

        # Concepts that must NOT appear in a BIR51 (corporation) filing
        # per NVAD-E-0060.
        bir52Exclusive = frozenset([
            tcQn("BIR52ProprietorPartnerAllocationOfAssessableProfitsAdjustedLoss"),
            tcQn("BIR52ProprietorPartnerDateEntered"),
            tcQn("BIR52ProprietorPartnerDateLeft"),
            tcQn("BIR52ProprietorPartnerEmoluments"),
            tcQn("BIR52ProprietorPartnerEmolumentsAdjustment"),
            tcQn("BIR52ProprietorPartnerFullName"),
            tcQn("BIR52ProprietorPartnerHKIDOrBRNumber"),
            tcQn("BIR52ProprietorPartnerMPF"),
            tcQn("BIR52ProprietorPartnerPersonalAssessment"),
            tcQn("BIR52ProprietorPartnerPrecedentPartner"),
            tcQn("BIR52ProprietorPartnerProfitLossSharingRatio"),
            tcQn("BIR52PurchaseCBAIBA"),
            tcQn("BusinessCessationDeathOfProprietor"),
            tcQn("BusinessCessationProprietorDeathDate"),
            tcQn("BusinessCessationTransfereeBusinessNature"),
        ])

        # Concepts that must NOT appear in a BIR52 filing per NVAD-E-0070.
        bir51Exclusive = frozenset([
            tcQn("AccountsPreparedAtConsolidatedLevel"),
            tcQn("Amalgamation"),
            tcQn("BusinessCessationTransferredAssetsAssociated"),
            tcQn("DeductionClaimedInterestNonHongKongAssociatedCorporationsIntraGroupFinancingBusiness"),
            tcQn("DeductionRegulatoryCapitalSecurityDistribution"),
            tcQn("ElectToTreatOneOffAdjustmentAsYourIncomeOrLossBy5EqualAmounts"),
            tcQn("EligibleSingleFamilyOfficeOfAFamily"),
            tcQn("IncomeAmountOfOneOffAdjustmentArisingFromImplementationOfRBCRegime"),
            tcQn("InsuranceCorporationCommencingToImplementRiskBasedCapitalRegimeToDetermineCapitalRequirements"),
            tcQn("LossAmountOfOneOffAdjustmentArisingFromImplementationOfRBCRegime"),
            tcQn("PrivateCompany"),
            tcQn("ProcessingArrangementMainland"),
            tcQn("ShareBasedPaymentCashSettled"),
            tcQn("ShareBasedPaymentDetails"),
            tcQn("ShareBasedPaymentEquitySettledCompany"),
            tcQn("ShareBasedPaymentEquitySettledGroupCoNoRecharge"),
            tcQn("ShareBasedPaymentEquitySettledGroupCoRecharge"),
            tcQn("ShareholderChange"),
        ])

        # Mandatory TC element sets (NVAD-E-0010, NVAD-E-0050)
        # From the IRD List of Mandatory Items (Version 4.0, April 2026),
        # https://www.ird.gov.hk/eng/tax/ixbrl/list_of_mandatory_items.pdf
        # Tax Computations §§3–4. COMMON is the intersection; the extras
        # are form-specific.
        COMMON_MANDATORY = frozenset([
            tcQn("AccountingDateDifferentFromThatOfLastYear"),
            tcQn("AccountingPeriodEndDate"),
            tcQn("AccountingPeriodStartDate"),
            tcQn("AdvanceRuling"),
            tcQn("ApprovedCharitableDonationsTaxAdjustment"),
            tcQn("AssessableProfitsAdjustedLossOfThePeriodHKD"),
            tcQn("BasisPeriodEndDate"),
            tcQn("BasisPeriodStartDate"),
            tcQn("BusinessCessation"),
            tcQn("BusinessCommencement"),
            tcQn("ClosingInventories"),
            tcQn("Commission"),
            tcQn("CompanyName"),
            tcQn("ConsultancyFee"),
            tcQn("ContractorCharges"),
            tcQn("ConversionRate"),
            tcQn("CurrencyUsed"),
            tcQn("DebtTreatmentABSOriginatorBondIssuer"),
            tcQn("DeductionClaimedForLeasedPremisesReinstatementCosts"),
            tcQn("DeemedAssessableProfitsUnderSection20AE20AF20AXAndOr20AYOrSection22AndOr23OfSchedule16E"),
            tcQn("DividendIncome"),
            tcQn("ExemptBankInterestIncomeTaxAdjustment"),
            tcQn("ExpenditureOnComputerHardwareAndSoftwareTaxAdjustment"),
            tcQn("ExpenditureOnCopyrightsTaxAdjustment"),
            tcQn("ExpenditureOnEnvironmentFriendlyVehiclesTaxAdjustment"),
            tcQn("ExpenditureOnEnvironmentalProtectionInstallationTaxAdjustment"),
            tcQn("ExpenditureOnEnvironmentalProtectionMachineryTaxAdjustment"),
            tcQn("ExpenditureOnPatentRightsTaxAdjustment"),
            tcQn("ExpenditureOnPerformersEconomicRightsTaxAdjustment"),
            tcQn("ExpenditureOnPrescribedManufacturingMachineryOrPlantTaxAdjustment"),
            tcQn("ExpenditureOnProtectedLayoutDesignTopographyRightsTaxAdjustment"),
            tcQn("ExpenditureOnProtectedPlantVarietyRightsTaxAdjustment"),
            tcQn("ExpenditureOnRegisteredDesignsTaxAdjustment"),
            tcQn("ExpenditureOnRegisteredTrademarksTaxAdjustment"),
            tcQn("ExpenditureOnRightsToKnowHowTaxAdjustment"),
            tcQn("FamilyOwnedSpecialPurposeEntityInWhichAnEligibleFamilyOwnedInvestmentHoldingVehicleHasBeneficialInterest"),
            tcQn("ForeignTaxPaidClaimedAsAUnilateralTaxCredit"),
            tcQn("GrossIncome"),
            tcQn("GrossProfitLoss"),
            tcQn("HongKongStandardIndustrialClassificationCode"),
            tcQn("IRDFileNumber"),
            tcQn("IncludeAnyInterestProfitsLossArisingFromShortMediumTermDebtInstruments"),
            tcQn("IntellectualPropertyPayments"),
            tcQn("InterestExpenses"),
            tcQn("InterestIncomeHongKongBank"),
            tcQn("InterestIncomeNonHongKongBank"),
            tcQn("InterestProfitsGainsFromQualifyingDebtInstrumentsIssuedOnOrAfter1April2018ExemptedTaxAdjustment"),
            tcQn("LoanInterestIncome"),
            tcQn("ManagementFee"),
            tcQn("NonResidentRoyaltyPaymentS15"),
            tcQn("OffshoreProfitsExcluded"),
            tcQn("OffshoreProfitsFromBusinessAttributableToTheUseOfTheInternetToAcceptOrdersSellGoodsProvideServicesOrAcceptPayment"),
            tcQn("OpeningInventories"),
            tcQn("PermanentEstablishmentHongKongNonHongKongResidentPerson"),
            tcQn("PrincipalBusinessActivity"),
            tcQn("ProfitLossBeforeTax"),
            tcQn("ProfitsEarnedByAFamilyOwnedSpecialPurposeEntityFromTransactionsSpecified"),
            tcQn("ProfitsFromSaleOfCapitalAssetsOtherThanLandedPropertiesInHongKongExcludedFromTheAssessableProfitsOrAdjustedLossTaxAdjustment2024"),
            tcQn("ProfitsFromSaleOfLandPropertiesInHongKongExcludedFromAssessableProfitsTaxAdjustment"),
            tcQn("ProvisionGeneralBadDebt"),
            tcQn("ProvisionSpecificBadDebt"),
            tcQn("Purchases"),
            tcQn("Schedule16CAndIncidentalTransactionsExempted"),
            tcQn("SpecifiedSecuritiesExempted"),
            tcQn("StaffSalaries"),
            tcQn("SubContractorCharges"),
            tcQn("TaxReliefDTA"),
            tcQn("TaxTreatmentOfFinancialInstruments"),
            tcQn("TransactionWithNonResidentAgent"),
            tcQn("TransactionWithNonResidentHireCharges"),
            tcQn("TransactionWithNonResidentProfessionalServicesFee"),
            tcQn("TransactionWithNonResidentSellGoodsServices"),
            tcQn("Turnover"),
            tcQn("ValueCreationContributionsinHongKong"),
            tcQn("YearOfAssessment"),
        ])

        mandatoryBir51 = COMMON_MANDATORY | frozenset([
            tcQn("AccountsPreparedAtConsolidatedLevel"),
            tcQn("Amalgamation"),
            tcQn("AuditRequirement"),
            tcQn("CBAAnnualAllowance"),
            tcQn("CBABalancingAllowance"),
            tcQn("CBABalancingCharge"),
            tcQn("DeductionClaimedInterestNonHongKongAssociatedCorporationsIntraGroupFinancingBusiness"),
            tcQn("DeductionRegulatoryCapitalSecurityDistribution"),
            tcQn("DepreciationAllowancesPoolingTotalAnnualAllowance"),
            tcQn("DepreciationAllowancesPoolingTotalBalancingAllowance"),
            tcQn("DepreciationAllowancesPoolingTotalBalancingCharge"),
            tcQn("DepreciationAllowancesPoolingTotalInitialAllowance"),
            tcQn("DirectorRemuneration"),
            tcQn("EligibleSingleFamilyOfficeOfAFamily"),
            tcQn("ExpenditureOnBuildingRefurbishmentTaxAdjustment"),
            tcQn("IBAAnnualAllowance"),
            tcQn("IBABalancingAllowance"),
            tcQn("IBABalancingCharge"),
            tcQn("IBAInitalAllowance"),
            tcQn("InsuranceCorporationCommencingToImplementRiskBasedCapitalRegimeToDetermineCapitalRequirements"),
            tcQn("OffshoreProfitsFromBusinessAttributableToContractProcessingOrImportProcessingArrangementInTheChineseMainland"),
            tcQn("PrivateCompany"),
            tcQn("ProcessingArrangementMainland"),
            tcQn("ShareBasedPaymentCashSettled"),
            tcQn("ShareBasedPaymentEquitySettledCompany"),
            tcQn("ShareBasedPaymentEquitySettledGroupCoNoRecharge"),
            tcQn("ShareBasedPaymentEquitySettledGroupCoRecharge"),
        ])

        mandatoryBir52 = COMMON_MANDATORY | frozenset([
            tcQn("BIR52ProprietorPartnerAllocationOfAssessableProfitsAdjustedLoss"),
            tcQn("BIR52ProprietorPartnerEmoluments"),
            tcQn("BIR52ProprietorPartnerFullName"),
            tcQn("BIR52ProprietorPartnerMPF"),
            tcQn("BIR52ProprietorPartnerPersonalAssessment"),
            tcQn("BIR52ProprietorPartnerPrecedentPartner"),
            tcQn("BIR52ProprietorPartnerProfitLossSharingRatio"),
            tcQn("BIR52PurchaseCBAIBA"),
            tcQn("MandatoryContributionsMadeForProprietorOrPartners"),
        ])

        # hksic_codes.json sourced from "The IRD iXBRL Data Preparation Tools" Mac version source.
        # Download latest version from https://www.ird.gov.hk/eng/tax/bus_ixbrl_materials.htm
        # Locate file at "IRD iXBRL Data Preparation Tools.app/Contents/Resources/resources/HSID.json"
        # Last updated using version 4.1.0.0.
        # Alternatively, the values could be extracted from here:
        # https://www.censtatd.gov.hk/en/EIndexbySubject.html?pcode=B2XX0021&scode=452#statisticalReports1
        hksicPath = Path(__file__).parent / "resources" / "hksic_codes.json"
        validHksic: frozenset[str] = frozenset(
            json.loads(hksicPath.read_text(encoding="utf-8"))
        )

        return PluginValidationDataExtension(
            name=self.name,

            # entry points
            validTcEntryPoints=validTc,

            # mandatory element sets
            mandatoryTcBir51Qns=mandatoryBir51,
            mandatoryTcBir52Qns=mandatoryBir52,

            # form-type detection
            bir52ExclusiveQns=bir52Exclusive,
            bir51ExclusiveQns=bir51Exclusive,

            # identifiers & basis period
            basisPeriodStartDateQn=tcQn("BasisPeriodStartDate"),
            basisPeriodEndDateQn=tcQn("BasisPeriodEndDate"),

            # HKSIC
            hksicCodeQn=tcQn("HongKongStandardIndustrialClassificationCode"),
            hksicCodeRegex=re.compile(r"^\d{6}$"),
            validHksicCodes=validHksic,
        )
