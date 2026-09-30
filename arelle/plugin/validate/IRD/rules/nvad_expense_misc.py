"""
See COPYRIGHT.md for copyright information.

NVAD Expense Misc rules — details/amount pairing for management fees
(expense), contractor/subcontractor charges, and specific bad debt
provision.

Rules implemented here:
  NVAD-E-0400  ManagementFee required when ManagementFeePaymentsDetails
               is present
  NVAD-E-0410  ManagementFeePaymentsDetails required when ManagementFee
               is non-zero
  NVAD-E-0420  ContractorCharges or SubContractorCharges required when
               ContractorAndSubcontractorChargesDetails is present
  NVAD-E-0430  ContractorAndSubcontractorChargesDetails required when
               either ContractorCharges or SubContractorCharges is
               non-zero
  NVAD-E-0440  ProvisionSpecificBadDebt required when
               BadDebtProvisionDetails is present
  NVAD-E-0441  BadDebtProvisionDetails required when
               ProvisionSpecificBadDebt is non-zero
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Facts import hasValidNonNilFactByQname, getValidNonNilFactsByQname
from arelle.utils.validate.Validation import Validation
from . import nonzeroAmountMissingDetailsValidation, detailsMissingAmountValidation, isZeroOrAbsent
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


def _anyChargeNonzero(
        modelXbrl: ModelXbrl,
        pluginData: PluginValidationDataExtension,
) -> bool:
    """True if either ContractorCharges or SubContractorCharges is
    tagged with a non-zero value.
    """
    return not isZeroOrAbsent(
        modelXbrl, pluginData.contractorChargesQn
    ) or not isZeroOrAbsent(
        modelXbrl, pluginData.subContractorChargesQn
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0400(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0400: ManagementFee required when
    ManagementFeePaymentsDetails is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.managementFeePaymentsDetailsQn,
        amountQn=pluginData.managementFeeQn,
        code="IRD.NVAD-E-0400",
        msg=_(
            "ManagementFee must be tagged when "
            "ManagementFeePaymentsDetails is tagged."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0410(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0410: ManagementFeePaymentsDetails required when
    ManagementFee is non-zero.
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.managementFeePaymentsDetailsQn,
        amountQn=pluginData.managementFeeQn,
        code="IRD.NVAD-E-0410",
        msg=_(
            "ManagementFeePaymentsDetails must be tagged when "
            "ManagementFee is non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0420(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0420: ContractorCharges or SubContractorCharges required
    when ContractorAndSubcontractorChargesDetails is present.

    Unlike the simple 1:1 pairings elsewhere in this module, the
    details element here corresponds to *either* of two amount
    concepts, so ``detailsMissingAmountValidation`` (which only handles a single
    amount concept) is not used.
    """
    modelXbrl = val.modelXbrl
    detailsPresent = hasValidNonNilFactByQname(
        modelXbrl, pluginData.contractorAndSubcontractorChargesDetailsQn
    )
    if detailsPresent and not _anyChargeNonzero(modelXbrl, pluginData):
        yield Validation.error(
            codes="IRD.NVAD-E-0420",
            msg=_(
                "ContractorCharges or SubContractorCharges must be "
                "tagged and non-zero when "
                "ContractorAndSubcontractorChargesDetails is tagged."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl,
                pluginData.contractorAndSubcontractorChargesDetailsQn,
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0430(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0430: ContractorAndSubcontractorChargesDetails required
    when either ContractorCharges or SubContractorCharges is non-zero.
    """
    modelXbrl = val.modelXbrl
    detailsPresent = hasValidNonNilFactByQname(
        modelXbrl, pluginData.contractorAndSubcontractorChargesDetailsQn
    )
    if _anyChargeNonzero(modelXbrl, pluginData) and not detailsPresent:
        yield Validation.error(
            codes="IRD.NVAD-E-0430",
            msg=_(
                "ContractorAndSubcontractorChargesDetails must be "
                "tagged when either ContractorCharges or "
                "SubContractorCharges is non-zero."
            ),
            modelObject=(
                getValidNonNilFactsByQname(modelXbrl, pluginData.contractorChargesQn)
                | getValidNonNilFactsByQname(modelXbrl, pluginData.subContractorChargesQn)
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0440(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0440: ProvisionSpecificBadDebt required when
    BadDebtProvisionDetails is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.badDebtProvisionDetailsQn,
        amountQn=pluginData.provisionSpecificBadDebtQn,
        code="IRD.NVAD-E-0440",
        msg=_(
            "ProvisionSpecificBadDebt must be tagged when "
            "BadDebtProvisionDetails is tagged."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0441(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0441: BadDebtProvisionDetails required when
    ProvisionSpecificBadDebt is non-zero.
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.badDebtProvisionDetailsQn,
        amountQn=pluginData.provisionSpecificBadDebtQn,
        code="IRD.NVAD-E-0441",
        msg=_(
            "BadDebtProvisionDetails must be tagged when "
            "ProvisionSpecificBadDebt is non-zero."
        ),
    )
