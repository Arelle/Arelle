"""
See COPYRIGHT.md for copyright information.

NVAD Income Paired rules — details/amount pairing for service income,
management fee income, and the offshore profits claim.

Rules implemented here:
  NVAD-E-0270  ServiceFeeIncome required when ServiceFeeReceivedDetails
               is present
  NVAD-E-0280  ServiceFeeReceivedDetails required when ServiceFeeIncome
               is non-zero
  NVAD-E-0290  ManagementFeeIncome required when
               ManagementFeeReceivedDetails is present
  NVAD-E-0300  ManagementFeeReceivedDetails required when
               ManagementFeeIncome is non-zero
  NVAD-E-0310  ReasonsForTheOffshoreClaim required when
               OffshoreProfitsExcluded is non-zero
  NVAD-E-1110  OffshoreProfitsExcluded required when
               ReasonsForTheOffshoreClaim is present
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
def rule_nvad_e_0270(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0270: ServiceFeeIncome required when ServiceFeeReceivedDetails
    is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.serviceFeeReceivedDetailsQn,
        amountQn=pluginData.serviceFeeIncomeQn,
        code="IRD.NVAD-E-0270",
        msg=_(
            "ServiceFeeIncome must be tagged when "
            "ServiceFeeReceivedDetails is tagged."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0280(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0280: ServiceFeeReceivedDetails required when ServiceFeeIncome
    is non-zero.
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.serviceFeeReceivedDetailsQn,
        amountQn=pluginData.serviceFeeIncomeQn,
        code="IRD.NVAD-E-0280",
        msg=_(
            "ServiceFeeReceivedDetails must be tagged when "
            "ServiceFeeIncome is non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0290(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0290: ManagementFeeIncome required when
    ManagementFeeReceivedDetails is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.managementFeeReceivedDetailsQn,
        amountQn=pluginData.managementFeeIncomeQn,
        code="IRD.NVAD-E-0290",
        msg=_(
            "ManagementFeeIncome must be tagged when "
            "ManagementFeeReceivedDetails is tagged."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0300(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0300: ManagementFeeReceivedDetails required when
    ManagementFeeIncome is non-zero.
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.managementFeeReceivedDetailsQn,
        amountQn=pluginData.managementFeeIncomeQn,
        code="IRD.NVAD-E-0300",
        msg=_(
            "ManagementFeeReceivedDetails must be tagged when "
            "ManagementFeeIncome is non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0310(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0310: ReasonsForTheOffshoreClaim required when
    OffshoreProfitsExcluded is non-zero.

    Note the amount/details roles are reversed relative to the other
    pairs in this module: here OffshoreProfitsExcluded is the "amount"
    and ReasonsForTheOffshoreClaim is the "details".
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.reasonsForOffshoreClaimQn,
        amountQn=pluginData.offshoreProfitsExcludedQn,
        code="IRD.NVAD-E-0310",
        msg=_(
            "ReasonsForTheOffshoreClaim must be tagged when "
            "OffshoreProfitsExcluded is non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1110(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1110: OffshoreProfitsExcluded required when
    ReasonsForTheOffshoreClaim is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.reasonsForOffshoreClaimQn,
        amountQn=pluginData.offshoreProfitsExcludedQn,
        code="IRD.NVAD-E-1110",
        msg=_(
            "OffshoreProfitsExcluded must be tagged when "
            "ReasonsForTheOffshoreClaim is tagged."
        ),
    )
