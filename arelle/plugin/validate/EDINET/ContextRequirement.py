"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ContextRequirement:
    """
    If {elementExists} is set, and {elementDoesNotExist} is not set,
    any context with ID starting with {contextId} must have {element} value
    matching the {elementMatch} DEI value (adjusted by {dayAdjustment} days).
    """
    contextId: str
    element: Literal['endDate', 'instant', 'startDate']
    elementExists: str | None
    elementDoesNotExist: str | None
    elementMatch: str
    dayAdjustment: int = 0  # days to adjust by (e.g. -1 for "day before")


# See section 3-4-2 in the Validation Guidelines.
CONTEXT_REQUIREMENTS = [
    ContextRequirement('CurrentYearInstant', 'instant', None, None, 'CurrentFiscalYearEndDateDEI'),
    ContextRequirement('Prior1YearInstant', 'instant', 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', None, 'CurrentFiscalYearEndDateDEI'),
    ContextRequirement('Prior1YearInstant', 'instant', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', 'PreviousFiscalYearEndDateDEI'),
    ContextRequirement('Prior2YearInstant', 'instant', 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', None, 'PreviousFiscalYearEndDateDEI'),
    ContextRequirement('Prior2YearInstant', 'instant', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', 'PreviousFiscalYearStartDateDEI', -1),
    ContextRequirement('CurrentQuarterInstant', 'instant', 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI'),
    ContextRequirement('CurrentQuarterInstant', 'instant', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', 'CurrentPeriodEndDateDEI'),
    ContextRequirement('Prior1QuarterInstant', 'instant', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', 'ComparativePeriodEndDateDEI'),
    ContextRequirement('InterimInstant', 'instant', 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI'),
    ContextRequirement('InterimInstant', 'instant', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', 'CurrentPeriodEndDateDEI'),
    ContextRequirement('Prior1InterimInstant', 'instant', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', 'ComparativePeriodEndDateDEI'),
    ContextRequirement('CurrentYearDuration', 'startDate', None, None, 'CurrentFiscalYearStartDateDEI'),
    ContextRequirement('Prior1YearDuration', 'startDate', 'NextFiscalYearStartDateDEI', None, 'CurrentFiscalYearStartDateDEI'),
    ContextRequirement('Prior1YearDuration', 'startDate', None, 'NextFiscalYearStartDateDEI', 'PreviousFiscalYearStartDateDEI'),
    ContextRequirement('Prior2YearDuration', 'startDate', 'NextFiscalYearStartDateDEI', None, 'PreviousFiscalYearStartDateDEI'),
    ContextRequirement('CurrentYTDDuration', 'startDate', 'NextFiscalYearStartDateDEI', None, 'NextFiscalYearStartDateDEI'),
    ContextRequirement('CurrentYTDDuration', 'startDate', None, 'NextFiscalYearStartDateDEI', 'CurrentFiscalYearStartDateDEI'),
    ContextRequirement('Prior1YTDDuration', 'startDate', None, 'NextFiscalYearStartDateDEI', 'PreviousFiscalYearStartDateDEI'),
    ContextRequirement('InterimDuration', 'startDate', 'NextFiscalYearStartDateDEI', None, 'NextFiscalYearStartDateDEI'),
    ContextRequirement('InterimDuration', 'startDate', None, 'NextFiscalYearStartDateDEI', 'CurrentFiscalYearStartDateDEI'),
    ContextRequirement('Prior1InterimDuration', 'startDate', None, 'NextFiscalYearStartDateDEI', 'PreviousFiscalYearStartDateDEI'),
    ContextRequirement('CurrentYearDuration', 'endDate', None, None, 'CurrentFiscalYearEndDateDEI'),
    ContextRequirement('Prior1YearDuration', 'endDate', 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', None, 'CurrentFiscalYearEndDateDEI'),
    ContextRequirement('Prior1YearDuration', 'endDate', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', 'PreviousFiscalYearEndDateDEI'),
    ContextRequirement('Prior2YearDuration', 'endDate', 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', None, 'PreviousFiscalYearEndDateDEI'),
    ContextRequirement('CurrentYTDDuration', 'endDate', 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI'),
    ContextRequirement('CurrentYTDDuration', 'endDate', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', 'CurrentPeriodEndDateDEI'),
    ContextRequirement('Prior1YTDDuration', 'endDate', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', 'ComparativePeriodEndDateDEI'),
    ContextRequirement('InterimDuration', 'endDate', 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI'),
    ContextRequirement('InterimDuration', 'endDate', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', 'CurrentPeriodEndDateDEI'),
    ContextRequirement('Prior1InterimDuration', 'endDate', None, 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI', 'ComparativePeriodEndDateDEI'),
]
