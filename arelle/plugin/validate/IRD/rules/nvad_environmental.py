"""
See COPYRIGHT.md for copyright information.

NVAD Environmental rules — details/amount pairing for building
refurbishment, environmental protection machinery/installation, and
environment-friendly vehicle allowances.

Rules implemented here:
  NVAD-E-0740  ExpenditureOnBuildingRefurbishmentTaxAdjustment required
               when ExpenditureOnBuildingRefurbishmentDetails is present
  NVAD-E-0750  ExpenditureOnBuildingRefurbishmentDetails required when
               ExpenditureOnBuildingRefurbishmentTaxAdjustment is
               non-zero
  NVAD-E-0760  ExpenditureOnEnvironmentalProtectionMachineryTaxAdjustment
               required when
               DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOfEnvironmentalProtectionMachinery
               is present
  NVAD-E-0770  DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOfEnvironmentalProtectionMachinery
               required when
               ExpenditureOnEnvironmentalProtectionMachineryTaxAdjustment
               is non-zero
  NVAD-E-0780  ExpenditureOnEnvironmentalProtectionInstallationTaxAdjustment
               required when
               DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOfEnvironmentalProtectionInstallation
               is present
  NVAD-E-0790  DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOfEnvironmentalProtectionInstallation
               required when
               ExpenditureOnEnvironmentalProtectionInstallationTaxAdjustment
               is non-zero
  NVAD-E-0800  ExpenditureOnEnvironmentFriendlyVehiclesTaxAdjustment
               required when
               DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOfEnvironmentFriendlyVehicles
               is present
  NVAD-E-0810  DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOfEnvironmentFriendlyVehicles
               required when
               ExpenditureOnEnvironmentFriendlyVehiclesTaxAdjustment is
               non-zero
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
def rule_nvad_e_0740(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0740: ExpenditureOnBuildingRefurbishmentTaxAdjustment
    required when ExpenditureOnBuildingRefurbishmentDetails is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.buildingRefurbDetailsQn,
        amountQn=pluginData.buildingRefurbTaxAdjQn,
        code="IRD.NVAD-E-0740",
        msg=_(
            "ExpenditureOnBuildingRefurbishmentTaxAdjustment must be "
            "tagged when ExpenditureOnBuildingRefurbishmentDetails is "
            "tagged."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0750(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0750: ExpenditureOnBuildingRefurbishmentDetails required
    when ExpenditureOnBuildingRefurbishmentTaxAdjustment is non-zero.
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.buildingRefurbDetailsQn,
        amountQn=pluginData.buildingRefurbTaxAdjQn,
        code="IRD.NVAD-E-0750",
        msg=_(
            "ExpenditureOnBuildingRefurbishmentDetails must be tagged "
            "when ExpenditureOnBuildingRefurbishmentTaxAdjustment is "
            "non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0760(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0760: ExpenditureOnEnvironmentalProtectionMachineryTaxAdjustment
    required when
    DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOfEnvironmentalProtectionMachinery
    is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.epMachineryDetailsQn,
        amountQn=pluginData.epMachineryTaxAdjQn,
        code="IRD.NVAD-E-0760",
        msg=_(
            "ExpenditureOnEnvironmentalProtectionMachineryTaxAdjustment "
            "must be tagged when "
            "DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOf"
            "EnvironmentalProtectionMachinery is tagged."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0770(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0770:
    DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOfEnvironmentalProtectionMachinery
    required when
    ExpenditureOnEnvironmentalProtectionMachineryTaxAdjustment is
    non-zero.
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.epMachineryDetailsQn,
        amountQn=pluginData.epMachineryTaxAdjQn,
        code="IRD.NVAD-E-0770",
        msg=_(
            "DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOf"
            "EnvironmentalProtectionMachinery must be tagged when "
            "ExpenditureOnEnvironmentalProtectionMachineryTaxAdjustment "
            "is non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0780(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0780: ExpenditureOnEnvironmentalProtectionInstallationTaxAdjustment
    required when
    DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOfEnvironmentalProtectionInstallation
    is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.epInstallationDetailsQn,
        amountQn=pluginData.epInstallationTaxAdjQn,
        code="IRD.NVAD-E-0780",
        msg=_(
            "ExpenditureOnEnvironmentalProtectionInstallationTaxAdjustment "
            "must be tagged when "
            "DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOf"
            "EnvironmentalProtectionInstallation is tagged."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0790(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0790:
    DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOfEnvironmentalProtectionInstallation
    required when
    ExpenditureOnEnvironmentalProtectionInstallationTaxAdjustment is
    non-zero.
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.epInstallationDetailsQn,
        amountQn=pluginData.epInstallationTaxAdjQn,
        code="IRD.NVAD-E-0790",
        msg=_(
            "DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOf"
            "EnvironmentalProtectionInstallation must be tagged when "
            "ExpenditureOnEnvironmentalProtectionInstallationTaxAdjustment "
            "is non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0800(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0800: ExpenditureOnEnvironmentFriendlyVehiclesTaxAdjustment
    required when
    DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOfEnvironmentFriendlyVehicles
    is present.
    """
    yield from detailsMissingAmountValidation(
        val.modelXbrl,
        detailsQn=pluginData.efVehiclesDetailsQn,
        amountQn=pluginData.efVehiclesTaxAdjQn,
        code="IRD.NVAD-E-0800",
        msg=_(
            "ExpenditureOnEnvironmentFriendlyVehiclesTaxAdjustment "
            "must be tagged when "
            "DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOf"
            "EnvironmentFriendlyVehicles is tagged."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0810(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0810:
    DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOfEnvironmentFriendlyVehicles
    required when
    ExpenditureOnEnvironmentFriendlyVehiclesTaxAdjustment is non-zero.
    """
    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.efVehiclesDetailsQn,
        amountQn=pluginData.efVehiclesTaxAdjQn,
        code="IRD.NVAD-E-0810",
        msg=_(
            "DetailsOfExpenditureIncurredOnAndProceedsFromTheSaleOf"
            "EnvironmentFriendlyVehicles must be tagged when "
            "ExpenditureOnEnvironmentFriendlyVehiclesTaxAdjustment is "
            "non-zero."
        ),
    )
