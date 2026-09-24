"""
See COPYRIGHT.md for copyright information.

NVAD Accounting Period rules — accounting date change flag pairing and
accounting period ordering.

Rules implemented here:
  NVAD-E-0130  ReasonsForTheChangeOfAccountingDate required when
               AccountingDateDifferentFromThatOfLastYear is true
  NVAD-E-0140  AccountingDateDifferentFromThatOfLastYear must be true when
               reasons are present
  NVAD-E-0150  AccountingPeriodEndDate must not be earlier than
               AccountingPeriodStartDate
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Facts import hasValidNonNilFactByQname, hasTrueValueFactByQname, getValidNonNilFactsByQname
from arelle.utils.validate.Validation import Validation
from . import getFactsByDateValue
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0130(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0130: reasons required when the accounting date changed.

    Whenever AccountingDateDifferentFromThatOfLastYear is tagged true,
    ReasonsForTheChangeOfAccountingDate must also be tagged.
    """
    modelXbrl = val.modelXbrl
    if not hasTrueValueFactByQname(modelXbrl, pluginData.accountingDateDifferentQn):
        return

    if not hasValidNonNilFactByQname(modelXbrl, pluginData.reasonsForChangeOfAccountingDateQn):
        yield Validation.error(
            codes="IRD.NVAD-E-0130",
            msg=_(
                "ReasonsForTheChangeOfAccountingDate must be tagged when "
                "AccountingDateDifferentFromThatOfLastYear is true."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.accountingDateDifferentQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0140(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0140: the change flag must be true when reasons are present.

    Whenever ReasonsForTheChangeOfAccountingDate is tagged,
    AccountingDateDifferentFromThatOfLastYear must be tagged true;
    reasons present alongside a false (or absent) flag is inconsistent.
    """
    modelXbrl = val.modelXbrl
    if not hasValidNonNilFactByQname(modelXbrl, pluginData.reasonsForChangeOfAccountingDateQn):
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.accountingDateDifferentQn):
        yield Validation.error(
            codes="IRD.NVAD-E-0140",
            msg=_(
                "AccountingDateDifferentFromThatOfLastYear must be true "
                "when ReasonsForTheChangeOfAccountingDate is tagged."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.reasonsForChangeOfAccountingDateQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0150(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0150: accounting period end date must not precede the start date.

    Compares the tagged date values of AccountingPeriodStartDate and AccountingPeriodEndDate.
    Skips entirely if either date is not tagged (covered separately by NVAD-E-0050).
    """
    modelXbrl = val.modelXbrl

    startFactsByValue = getFactsByDateValue(modelXbrl, (pluginData.accountingPeriodStartDateQn,))
    endFactsByValue = getFactsByDateValue(modelXbrl, (pluginData.accountingPeriodEndDateQn,))
    if not startFactsByValue or not endFactsByValue:
        return

    for startValue, startFacts in startFactsByValue.items():
        for endValue, endFacts in endFactsByValue.items():
            if endValue < startValue:
                yield Validation.error(
                    codes="IRD.NVAD-E-0150",
                    msg=_(
                        "AccountingPeriodEndDate (%(endDate)s) must not be "
                        "earlier than AccountingPeriodStartDate (%(startDate)s)."
                    ),
                    modelObject=startFacts + endFacts,
                    endDate=endValue,
                    startDate=startValue,
                )
