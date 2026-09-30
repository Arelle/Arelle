"""
See COPYRIGHT.md for copyright information.

NVAD BIR51 Corporate rules — private company flags, insurance RBC
regime, and family office SPE. BIR51 (corporation) filings only.

Rules implemented here:
  NVAD-E-1090  ShareholderChange must be tagged when PrivateCompany
               is true
  NVAD-E-1093  InsuranceRBCFlag must be true when either RBC
               adjustment amount is non-zero
  NVAD-E-1094  At least one RBC adjustment amount required when
               InsuranceRBCFlag is true
  NVAD-E-1095  IncomeRBCAmount and LossRBCAmount must not both be
               non-zero simultaneously
  NVAD-E-1096  ElectToTreatOneOffAdjustment required when
               InsuranceRBCFlag is true
  NVAD-E-1098  ProfitsEarnedByFamilyOwnedSPE must be zero when
               FamilyOwnedSPE flag is false

All rules in this module apply to BIR51 filings only; the private
company and related concepts are BIR51-exclusive (see NVAD-E-0070),
so each rule is additionally guarded with ``isBir51`` to skip
cleanly on BIR52 filings.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Facts import hasValidNonNilFactByQname, hasTrueValueFactByQname, getValidNonNilFactsByQname, hasFalseValueFactByQname
from arelle.utils.validate.Validation import Validation
from . import isZeroOrAbsent
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1090(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1090: ShareholderChange must be tagged when
    PrivateCompany is true.

    BIR51 (corporation) filings must tag ShareholderChange — even if
    its value is false — whenever PrivateCompany is true. Skips
    entirely on BIR52 filings, where this concept is not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir51(modelXbrl):
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.privateCompanyQn):
        return

    if not hasValidNonNilFactByQname(modelXbrl, pluginData.shareholderChangeQn):
        yield Validation.error(
            codes="IRD.NVAD-E-1090",
            msg=_(
                "ShareholderChange must be tagged when PrivateCompany "
                "is true in a BIR51 filing."
            ),
            modelObject=getValidNonNilFactsByQname(modelXbrl, pluginData.privateCompanyQn),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1093(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1093: InsuranceRBCFlag must be true when either RBC
    adjustment amount is non-zero.

    BIR51 (corporation) filings must tag
    InsuranceCorporationCommencingToImplementRiskBasedCapitalRegimeToDetermineCapitalRequirements
    as true whenever either one-off RBC adjustment amount is tagged
    and non-zero. Skips entirely on BIR52 filings, where these
    concepts are not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir51(modelXbrl):
        return

    anyRbcAmountNonzero = any(
        not isZeroOrAbsent(modelXbrl, qn)
        for qn in (
            pluginData.incomeRbcAmountQn,
            pluginData.lossRbcAmountQn,
        )
    )
    if not anyRbcAmountNonzero:
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.insuranceRbcFlagQn):
        yield Validation.error(
            codes="IRD.NVAD-E-1093",
            msg=_(
                "InsuranceCorporationCommencingToImplementRiskBasedCapitalRegimeToDetermineCapitalRequirements "
                "must be true when either "
                "IncomeAmountOfOneOffAdjustmentArisingFromImplementationOfRBCRegime "
                "or "
                "LossAmountOfOneOffAdjustmentArisingFromImplementationOfRBCRegime "
                "is non-zero in a BIR51 filing."
            ),
            modelObject=(
                getValidNonNilFactsByQname(modelXbrl, pluginData.incomeRbcAmountQn)
                | getValidNonNilFactsByQname(modelXbrl, pluginData.lossRbcAmountQn)
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1094(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1094: At least one RBC adjustment amount required when
    InsuranceRBCFlag is true.

    BIR51 (corporation) filings must tag at least one of
    IncomeAmountOfOneOffAdjustmentArisingFromImplementationOfRBCRegime
    or
    LossAmountOfOneOffAdjustmentArisingFromImplementationOfRBCRegime
    whenever the RBC regime flag is true. Skips entirely on BIR52
    filings, where these concepts are not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir51(modelXbrl):
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.insuranceRbcFlagQn):
        return

    if not (
        hasValidNonNilFactByQname(modelXbrl, pluginData.incomeRbcAmountQn)
        or hasValidNonNilFactByQname(modelXbrl, pluginData.lossRbcAmountQn)
    ):
        yield Validation.error(
            codes="IRD.NVAD-E-1094",
            msg=_(
                "At least one of "
                "IncomeAmountOfOneOffAdjustmentArisingFromImplementationOfRBCRegime "
                "or "
                "LossAmountOfOneOffAdjustmentArisingFromImplementationOfRBCRegime "
                "must be tagged when "
                "InsuranceCorporationCommencingToImplementRiskBasedCapitalRegimeToDetermineCapitalRequirements "
                "is true in a BIR51 filing."
            ),
            modelObject=getValidNonNilFactsByQname(modelXbrl, pluginData.insuranceRbcFlagQn),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1095(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1095: IncomeRBCAmount and LossRBCAmount must not both
    be non-zero simultaneously.

    A single RBC regime transition cannot yield both a net income
    and a net loss adjustment, so at most one of the two amounts
    may be non-zero. Skips entirely on BIR52 filings, where these
    concepts are not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir51(modelXbrl):
        return

    incomeNonzero = not isZeroOrAbsent(
        modelXbrl, pluginData.incomeRbcAmountQn
    )
    lossNonzero = not isZeroOrAbsent(
        modelXbrl, pluginData.lossRbcAmountQn
    )
    if incomeNonzero and lossNonzero:
        yield Validation.error(
            codes="IRD.NVAD-E-1095",
            msg=_(
                "IncomeAmountOfOneOffAdjustmentArisingFromImplementationOfRBCRegime "
                "and "
                "LossAmountOfOneOffAdjustmentArisingFromImplementationOfRBCRegime "
                "must not both be non-zero in a BIR51 filing."
            ),
            modelObject=(
                getValidNonNilFactsByQname(modelXbrl, pluginData.incomeRbcAmountQn)
                | getValidNonNilFactsByQname(modelXbrl, pluginData.lossRbcAmountQn)
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1096(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1096: ElectToTreatOneOffAdjustment required when
    InsuranceRBCFlag is true.

    BIR51 (corporation) filings must tag
    ElectToTreatOneOffAdjustmentAsYourIncomeOrLossBy5EqualAmounts —
    even if its value is false — whenever the RBC regime flag is
    true. Skips entirely on BIR52 filings, where these concepts are
    not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir51(modelXbrl):
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.insuranceRbcFlagQn):
        return

    if not hasValidNonNilFactByQname(modelXbrl, pluginData.electToTreatOneOffAdjustmentQn):
        yield Validation.error(
            codes="IRD.NVAD-E-1096",
            msg=_(
                "ElectToTreatOneOffAdjustmentAsYourIncomeOrLossBy5EqualAmounts "
                "must be tagged when "
                "InsuranceCorporationCommencingToImplementRiskBasedCapitalRegimeToDetermineCapitalRequirements "
                "is true in a BIR51 filing."
            ),
            modelObject=getValidNonNilFactsByQname(modelXbrl, pluginData.insuranceRbcFlagQn),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1098(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1098: ProfitsEarnedByFamilyOwnedSPE must be zero when
    FamilyOwnedSPE flag is false.

    BIR51 (corporation) filings must tag
    ProfitsEarnedByAFamilyOwnedSpecialPurposeEntityFromTransactionsSpecified
    as zero whenever
    FamilyOwnedSpecialPurposeEntityInWhichAnEligibleFamilyOwnedInvestmentHoldingVehicleHasBeneficialInterest
    is false.
    Skips entirely if ProfitsEarnedByFamilyOwnedSPE is absent,
    covered by NVAD-E-0050
    Skips entirely on BIR52 filings, where these concepts
    are not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir51(modelXbrl):
        return

    if not hasFalseValueFactByQname(modelXbrl, pluginData.familyOwnedSpeQn):
        return

    if not isZeroOrAbsent(
        modelXbrl, pluginData.profitsEarnedByFamilyOwnedSpeQn
    ):
        yield Validation.error(
            codes="IRD.NVAD-E-1098",
            msg=_(
                "ProfitsEarnedByAFamilyOwnedSpecialPurposeEntityFromTransactionsSpecified "
                "must be zero when "
                "FamilyOwnedSpecialPurposeEntityInWhichAnEligibleFamilyOwnedInvestmentHoldingVehicleHasBeneficialInterest "
                "is false in a BIR51 filing."
            ),
            modelObject=(
                getValidNonNilFactsByQname(modelXbrl, pluginData.familyOwnedSpeQn)
                | getValidNonNilFactsByQname(
                    modelXbrl, pluginData.profitsEarnedByFamilyOwnedSpeQn
                )
            ),
        )
