"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle import XbrlConst
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC5002E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5002E: A unit other than number of shares (xbrli:shares) has been set for the
    Number of Shares (xbrli:sharesItemType) item '{xxx}yyy'.
    Please check the units and enter the correct information.

    Similar to "xbrl.4.8.2:sharesFactUnit-notSharesMeasure" and "xbrl.4.8.2:sharesFactUnit-notSingleMeasure"
    TODO: Consolidate this rule with the above two rules if possible.
    """
    errorFacts = []
    for fact in val.modelXbrl.facts:
        concept = fact.concept
        if not concept.isShares:
            continue
        unit = fact.unit
        measures = unit.measures
        if (
                not measures or
                len(measures[0]) != 1 or
                len(measures[1]) != 0 or
                measures[0][0] != XbrlConst.qnXbrliShares
        ):
            errorFacts.append(fact)
    for fact in errorFacts:
        yield Validation.error(
            codes='EDINET.EC5002E',
            msg=_("A unit other than number of shares (xbrli:shares) has been set for "
                  "the Number of Shares (xbrli:sharesItemType) item '%(qname)s'. "
                  "Please check the units and enter the correct information."),
            qname=fact.qname.clarkNotation,
            modelObject=fact,
        )
