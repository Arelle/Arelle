"""
See COPYRIGHT.md for copyright information.

NVAD BIR51 Share-Based Payment rules — BIR51 (corporation) filings only.

Rules implemented here:
  NVAD-E-0450  At least one of the four SBP amount elements must be
               non-zero when ShareBasedPaymentDetails is present
  NVAD-E-0460  ShareBasedPaymentDetails required when
               ShareBasedPaymentCashSettled is non-zero
  NVAD-E-0470  ShareBasedPaymentDetails required when
               ShareBasedPaymentEquitySettledCompany is non-zero
  NVAD-E-0480  ShareBasedPaymentDetails required when
               ShareBasedPaymentEquitySettledGroupCoNoRecharge is
               non-zero
  NVAD-E-0490  ShareBasedPaymentDetails required when
               ShareBasedPaymentEquitySettledGroupCoRecharge is
               non-zero

All rules in this module apply to BIR51 filings only; the share-based
payment concepts are BIR51-exclusive (see NVAD-E-0070), so each rule
is additionally guarded with ``isBir51`` to skip cleanly on BIR52
filings.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Facts import hasValidNonNilFactByQname, getValidNonNilFactsByQname
from arelle.utils.validate.Validation import Validation
from . import nonzeroAmountMissingDetailsValidation, isZeroOrAbsent
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0450(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0450: At least one SBP amount element must be tagged and
    non-zero when ShareBasedPaymentDetails is present.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir51(modelXbrl):
        return

    if hasValidNonNilFactByQname(
        modelXbrl, pluginData.shareBasedPaymentDetailsQn
    ):
        anySbpAmountNonzero = any(
            not isZeroOrAbsent(modelXbrl, qn)
            for qn in (
                pluginData.shareBasedPaymentCashSettledQn,
                pluginData.shareBasedPaymentEquitySettledCompanyQn,
                pluginData.shareBasedPaymentEquitySettledGroupNoRechargeQn,
                pluginData.shareBasedPaymentEquitySettledGroupRechargeQn,
            )
        )
        if not anySbpAmountNonzero:
            yield Validation.error(
                codes="IRD.NVAD-E-0450",
                msg=_(
                    "At least one of ShareBasedPaymentCashSettled, "
                    "ShareBasedPaymentEquitySettledCompany, "
                    "ShareBasedPaymentEquitySettledGroupCoNoRecharge, or "
                    "ShareBasedPaymentEquitySettledGroupCoRecharge must be "
                    "tagged and non-zero when ShareBasedPaymentDetails is "
                    "tagged."
                ),
                modelObject=getValidNonNilFactsByQname(
                    modelXbrl, pluginData.shareBasedPaymentDetailsQn
                ),
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0460(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0460: ShareBasedPaymentDetails required when
    ShareBasedPaymentCashSettled is non-zero.
    """
    if not pluginData.isBir51(val.modelXbrl):
        return

    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.shareBasedPaymentDetailsQn,
        amountQn=pluginData.shareBasedPaymentCashSettledQn,
        code="IRD.NVAD-E-0460",
        msg=_(
            "ShareBasedPaymentDetails must be tagged when "
            "ShareBasedPaymentCashSettled is non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0470(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0470: ShareBasedPaymentDetails required when
    ShareBasedPaymentEquitySettledCompany is non-zero.
    """
    if not pluginData.isBir51(val.modelXbrl):
        return

    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.shareBasedPaymentDetailsQn,
        amountQn=pluginData.shareBasedPaymentEquitySettledCompanyQn,
        code="IRD.NVAD-E-0470",
        msg=_(
            "ShareBasedPaymentDetails must be tagged when "
            "ShareBasedPaymentEquitySettledCompany is non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0480(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0480: ShareBasedPaymentDetails required when
    ShareBasedPaymentEquitySettledGroupCoNoRecharge is non-zero.
    """
    if not pluginData.isBir51(val.modelXbrl):
        return

    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.shareBasedPaymentDetailsQn,
        amountQn=pluginData.shareBasedPaymentEquitySettledGroupNoRechargeQn,
        code="IRD.NVAD-E-0480",
        msg=_(
            "ShareBasedPaymentDetails must be tagged when "
            "ShareBasedPaymentEquitySettledGroupCoNoRecharge is "
            "non-zero."
        ),
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0490(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0490: ShareBasedPaymentDetails required when
    ShareBasedPaymentEquitySettledGroupCoRecharge is non-zero.
    """
    if not pluginData.isBir51(val.modelXbrl):
        return

    yield from nonzeroAmountMissingDetailsValidation(
        val.modelXbrl,
        detailsQn=pluginData.shareBasedPaymentDetailsQn,
        amountQn=pluginData.shareBasedPaymentEquitySettledGroupRechargeQn,
        code="IRD.NVAD-E-0490",
        msg=_(
            "ShareBasedPaymentDetails must be tagged when "
            "ShareBasedPaymentEquitySettledGroupCoRecharge is "
            "non-zero."
        ),
    )
