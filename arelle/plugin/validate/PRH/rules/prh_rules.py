"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.ModelInstanceObject import ModelFact
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateDuplicateFacts import getDuplicateFactSets
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
    for duplicateFactSet in getDuplicateFactSets(val.modelXbrl.facts, includeSingles=False):
        if duplicateFactSet.areAnyInconsistent:
            yield Validation.error(
                codes="FINLAND-PRH.duplicateFact",
                msg=_("Inconsistent duplicate numeric facts MUST NOT appear in the content of an inline XBRL "
                      "document. %(fact)s that was used more than once in contexts equivalent to %(contextID)s: "
                      "values %(values)s."),
                modelObject=duplicateFactSet.facts,
                fact=duplicateFactSet.facts[0].qname,
                contextID=duplicateFactSet.facts[0].contextID,
                values=", ".join(f.value for f in duplicateFactSet.facts)
            )
