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

from ..DisclosureSystems import FINLAND_PRH
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[FINLAND_PRH],
)
def rule_finland_prh_duplicate_fact_check(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    Standard duplicate fact check for inconsistencies
    """
    yield from validateDuplicateFacts(
        val.modelXbrl.facts,
        DuplicateType.INCONSISTENT,
        codes="FINLAND-PRH.duplicateFact",
    )
