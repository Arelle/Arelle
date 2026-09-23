"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.DuplicateFacts import validateDuplicateFacts
from arelle.utils.validate.Validation import Validation
from arelle.ValidateDuplicateFactsConst import DuplicateType
from arelle.ValidateXbrl import ValidateXbrl

from ...Const import AUTHORITY_FI_PRH
from ...PluginValidationDataExtension import PluginValidationDataExtension
from ...Util import isEsefExcludedInstance

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_duplicateFact(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """PRH: Inconsistent duplicate facts MUST NOT appear in the non-ESEF report."""
    if val.authority != AUTHORITY_FI_PRH or not isEsefExcludedInstance(val):
        return
    yield from validateDuplicateFacts(
        val.modelXbrl.facts,
        DuplicateType.INCONSISTENT,
        codes="FINLAND-PRH.duplicateFact",
    )
