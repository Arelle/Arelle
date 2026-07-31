"""
See COPYRIGHT.md for copyright information.

UKSEF taxonomy validation rules (UKFRC1, UKFRC2).
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateXbrl import ValidateXbrl
from ...Const import AUTHORITY_UKFRC
from ...PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC1: UKSEF 2025 reports MUST have a reference (a schemaRef in a “UKFRS” targeted ix:references element)
    to one of the three possible FRC taxonomy entry-points for either FRS102 or IFRS. Companies House allow use
    of the current and last two annual versions of the FRC’s Taxonomy Suite. The 2025, 2024 or 2023 Taxonomy
    Suites all contain the relevant UKSEF entry-points:
    2025 Taxonomy Suite
    *	https://xbrl.frc.org.uk/FRS-102/2025-01-01/UKSEF/FRS-102-2025-01-01.xsd; or
    *	https://xbrl.frc.org.uk/IFRS/2025-01-01/UKSEF/IFRS-2025-01-01.xsd
    2024 Taxonomy Suite
    *	https://xbrl.frc.org.uk/FRS-102/2024-01-01/UKSEF/FRS-102-2024-01-01.xsd; or
    *	https://xbrl.frc.org.uk/IFRS/2024-01-01/UKSEF/IFRS-2024-01-01.xsd
    2023 Taxonomy Suite
    *	https://xbrl.frc.org.uk/FRS-102/2023-01-01/UKSEF/FRS-102-2023-01-01.xsd; or
    *	https://xbrl.frc.org.uk/IFRS/2023-01-01/UKSEF/IFRS-2023-01-01.xsd
    The reference must be in the report, NOT in the extension taxonomy.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC2: UKSEF 2025 reports MUST only be used in conjunction with ESEF 2022 or later
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None
