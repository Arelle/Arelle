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
    Standard inconsistent duplicate fact check
    """
    for duplicateFactSet in getDuplicateFactSets(val.modelXbrl.facts, includeSingles=False):
        if duplicateFactSet.areNumeric and duplicateFactSet.areAnyInconsistent:
            fList = duplicateFactSet.facts
            f0: ModelFact = fList[0]
            if not any(f.isNil for f in fList) and f0.xValue is None:
                continue
            yield Validation.error(
                codes="FINLAND-PRH.duplicateFact",
                msg=_("Inconsistent duplicate numeric facts MUST NOT appear in the content of an inline XBRL "
                      "document. %(fact)s that was used more than once in contexts equivalent to %(contextID)s: "
                      "values %(values)s."),
                modelObject=fList,
                fact=f0.qname,
                contextID=f0.contextID,
                values=", ".join(f.value for f in fList)
            )
