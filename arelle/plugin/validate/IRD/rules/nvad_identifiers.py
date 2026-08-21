"""
See COPYRIGHT.md for copyright information.

NVAD Identifier rules — IRD file number, year of assessment, and basis
period format/range validation.

Rules implemented here:
  NVAD-E-0100  IRDFileNumber must match {2-digit}/{8-digit}; YearOfAssessment
               must match 20XX/YY (YY = XX + 1) within a valid window
  NVAD-E-0110  Basis period start date must not be later than end date
  NVAD-E-0120  Basis period end date must fall within the year of
               assessment window
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Facts import iterValidNonNilFactsByQname
from arelle.utils.validate.Validation import Validation
from . import getFactsByDateValue
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

# Assessment-year window: the year of assessment's first calendar year
# must fall within this many years of the disclosure system's assessment
# year in either direction.
ASSESSMENT_YEAR_MINIMUM = 2022
ASSESSMENT_YEAR_WINDOW_PAST = 5
ASSESSMENT_YEAR_WINDOW_FUTURE = 1


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0100(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0100: IRDFileNumber and YearOfAssessment format/range checks.

    IRDFileNumber must match ``{2-digit}/{8-digit}``. YearOfAssessment
    must match ``20XX/YY`` where YY is exactly one greater than XX, and
    the first year must satisfy:

    - **hard floor** ``>= 2022`` (earliest e-filing year is 2022/23)
    - **lookback** ``>= current_YA − 5``
    - **lookahead** ``<= current_YA + 1``
    """
    modelXbrl = val.modelXbrl

    for fact in iterValidNonNilFactsByQname(modelXbrl, pluginData.irdFileNumberQn):
        value = (fact.value or "").strip()
        if not pluginData.irdFileNumberRegex.match(value):
            yield Validation.error(
                codes="IRD.NVAD-E-0100",
                msg=_(
                    "IRDFileNumber must match the format "
                    "{2-digit}/{8-digit}; found '%(value)s'."
                ),
                modelObject=fact,
                value=value,
            )

    for fact in iterValidNonNilFactsByQname(modelXbrl, pluginData.yearOfAssessmentQn):
        value = (fact.value or "").strip()
        match = pluginData.yearOfAssessmentRegex.match(value)
        if not match:
            yield Validation.error(
                codes="IRD.NVAD-E-0100",
                msg=_(
                    "YearOfAssessment must match the format 20XX/YY; "
                    "found '%(value)s'."
                ),
                modelObject=fact,
                value=value,
            )
            continue

        firstTwo, secondTwo = int(match.group(1)), int(match.group(2))
        if secondTwo != (firstTwo + 1) % 100:
            yield Validation.error(
                codes="IRD.NVAD-E-0100",
                msg=_(
                    "YearOfAssessment second part must be exactly one "
                    "year after the first (expected %(expected)s); "
                    "found '%(value)s'."
                ),
                modelObject=fact,
                expected=f"20{firstTwo:02d}/{(firstTwo + 1) % 100:02d}",
                value=value,
            )
            continue

        firstYear = 2000 + firstTwo
        currentYear = pluginData.assessmentYear
        windowLow = max(ASSESSMENT_YEAR_MINIMUM, currentYear - ASSESSMENT_YEAR_WINDOW_PAST)
        windowHigh = currentYear + ASSESSMENT_YEAR_WINDOW_FUTURE
        if not (windowLow <= firstYear <= windowHigh):
            yield Validation.error(
                codes="IRD.NVAD-E-0100",
                msg=_(
                    "YearOfAssessment '%(value)s' falls outside the "
                    "valid assessment window (%(windowLow)s to "
                    "%(windowHigh)s)."
                ),
                modelObject=fact,
                value=value,
                windowLow=f"{windowLow}/{(windowLow + 1) % 100:02d}",
                windowHigh=f"{windowHigh}/{(windowHigh + 1) % 100:02d}",
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0110(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0110: basis period start date must not be later than end date.

    Compares the tagged date values of BasisPeriodStartDate
    and BasisPeriodEndDate. Skips entirely if either date is not tagged
    (covered separately by NVAD-E-0050).
    """
    modelXbrl = val.modelXbrl

    startFactsByValue = getFactsByDateValue(modelXbrl, (pluginData.basisPeriodStartDateQn,))
    endFactsByValue = getFactsByDateValue(modelXbrl, (pluginData.basisPeriodEndDateQn,))
    if not startFactsByValue or not endFactsByValue:
        return

    for startValue, startFacts in startFactsByValue.items():
        for endValue, endFacts in endFactsByValue.items():
            if startValue > endValue:
                yield Validation.error(
                    codes="IRD.NVAD-E-0110",
                    msg=_(
                        "BasisPeriodStartDate (%(startDate)s) must not be "
                        "later than BasisPeriodEndDate (%(endDate)s)."
                    ),
                    modelObject=startFacts + endFacts,
                    startDate=startValue,
                    endDate=endValue,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_0120(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-0120: basis period end date must fall within the assessment window.

    Parses the assessment year from YearOfAssessment (``20XX/YY``) and
    requires BasisPeriodEndDate to fall within ``[1 April 20XX, 31 March
    20YY]`` inclusive. Skips if YearOfAssessment is malformed (reported
    separately by NVAD-E-0100) or either fact is untagged (NVAD-E-0050).
    """
    modelXbrl = val.modelXbrl

    endFactsByValue = getFactsByDateValue(modelXbrl, (pluginData.basisPeriodEndDateQn,))
    if not endFactsByValue:
        return

    for yearFact in iterValidNonNilFactsByQname(modelXbrl, pluginData.yearOfAssessmentQn):
        yearValue = (yearFact.value or "").strip()
        match = pluginData.yearOfAssessmentRegex.match(yearValue)
        if not match:
            return

        firstYear = 2000 + int(match.group(1))
        secondYear = 2000 + int(match.group(2))
        windowStart = date(firstYear, 4, 1)
        windowEnd = date(secondYear, 3, 31)
        for endValue, endFacts in endFactsByValue.items():
            if not (windowStart <= endValue <= windowEnd):
                yield Validation.error(
                    codes="IRD.NVAD-E-0120",
                    msg=_(
                        "BasisPeriodEndDate (%(endDate)s) must fall within the "
                        "year of assessment window (%(windowStart)s to "
                        "%(windowEnd)s) implied by YearOfAssessment "
                        "'%(yearOfAssessment)s'."
                    ),
                    modelObject=[yearFact] + endFacts,
                    endDate=endValue,
                    windowStart=windowStart,
                    windowEnd=windowEnd,
                    yearOfAssessment=yearValue,
                )
