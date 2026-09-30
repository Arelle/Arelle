"""
See COPYRIGHT.md for copyright information.

NVAD Expense Deductions rules — details/amount pairing for commission
expenses, approved charitable donations, interest expenses, and legal
and professional fees.

Rules implemented here:
  NVAD-E-0330  Commission required when CommissionPaymentsDetails is
               present
  NVAD-E-0340  CommissionPaymentsDetails required when Commission is
               non-zero
  NVAD-E-0350  ApprovedCharitableDonationsTaxAdjustment required when
               ApprovedCharitableDonationsDetails is present
  NVAD-E-0370  ApprovedCharitableDonationsDetails required when
               ApprovedCharitableDonationsTaxAdjustment is non-zero
  NVAD-E-0371  InterestExpenses required when InterestPaidOrPayableDetails
               is present
  NVAD-E-0372  InterestPaidOrPayableDetails required when
               InterestExpenses is non-zero
  NVAD-E-0380  LegalAndProfessionalFee required when
               LegalAndOtherProfessionalFeePaymentsDetails is present
  NVAD-E-0390  LegalAndOtherProfessionalFeePaymentsDetails required when
               LegalAndProfessionalFee is non-zero
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from . import nonzeroAmountMissingDetailsValidation, detailsMissingAmountValidation
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0330(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0330: Commission required when CommissionPaymentsDetails
    is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.commissionPaymentsDetailsQn,
        amountQn=pluginData.commissionQn,
        code="IRD.NVAD-E-0330",
        msg=_(
            "Commission must be tagged when "
            "CommissionPaymentsDetails is tagged."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0340(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0340: CommissionPaymentsDetails required when Commission
    is non-zero.
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.commissionPaymentsDetailsQn,
        amountQn=pluginData.commissionQn,
        code="IRD.NVAD-E-0340",
        msg=_(
            "CommissionPaymentsDetails must be tagged when "
            "Commission is non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0350(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0350: ApprovedCharitableDonationsTaxAdjustment required
    when ApprovedCharitableDonationsDetails is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.approvedCharitableDonationsDetailsQn,
        amountQn=pluginData.approvedCharitableDonationsTaxAdjQn,
        code="IRD.NVAD-E-0350",
        msg=_(
            "ApprovedCharitableDonationsTaxAdjustment must be tagged and "
            "non-zero when ApprovedCharitableDonationsDetails is tagged."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0370(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0370: ApprovedCharitableDonationsDetails required when
    ApprovedCharitableDonationsTaxAdjustment is non-zero.
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.approvedCharitableDonationsDetailsQn,
        amountQn=pluginData.approvedCharitableDonationsTaxAdjQn,
        code="IRD.NVAD-E-0370",
        msg=_(
            "ApprovedCharitableDonationsDetails must be tagged when "
            "ApprovedCharitableDonationsTaxAdjustment is non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0371(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0371: InterestExpenses required when
    InterestPaidOrPayableDetails is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.interestPaidOrPayableDetailsQn,
        amountQn=pluginData.interestExpensesQn,
        code="IRD.NVAD-E-0371",
        msg=_(
            "InterestExpenses must be tagged when "
            "InterestPaidOrPayableDetails is tagged."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0372(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0372: InterestPaidOrPayableDetails required when
    InterestExpenses is non-zero.
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.interestPaidOrPayableDetailsQn,
        amountQn=pluginData.interestExpensesQn,
        code="IRD.NVAD-E-0372",
        msg=_(
            "InterestPaidOrPayableDetails must be tagged when "
            "InterestExpenses is non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0380(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0380: LegalAndProfessionalFee required when
    LegalAndOtherProfessionalFeePaymentsDetails is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.legalAndProfessionalFeeDetailsQn,
        amountQn=pluginData.legalAndProfessionalFeeQn,
        code="IRD.NVAD-E-0380",
        msg=_(
            "LegalAndProfessionalFee must be tagged when "
            "LegalAndOtherProfessionalFeePaymentsDetails is tagged."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0390(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0390: LegalAndOtherProfessionalFeePaymentsDetails required
    when LegalAndProfessionalFee is non-zero.
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.legalAndProfessionalFeeDetailsQn,
        amountQn=pluginData.legalAndProfessionalFeeQn,
        code="IRD.NVAD-E-0390",
        msg=_(
            "LegalAndOtherProfessionalFeePaymentsDetails must be tagged "
            "when LegalAndProfessionalFee is non-zero."
        ),
    )
