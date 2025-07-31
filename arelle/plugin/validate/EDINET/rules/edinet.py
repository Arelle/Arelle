"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Iterable, cast

import regex

from arelle import XbrlConst, ValidateDuplicateFacts
from arelle.ValidateDuplicateFacts import DuplicateType
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


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8024E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8024E: Instance values of the same element, context, and unit may not
    have different values or different decimals attributes.
    Correct the element with the relevant context ID. For elements in an inline XBRL file that have
    duplicate elements, context IDs, and unit IDs, set the same values for the value and
    decimals attribute.
    """
    duplicateFactSets = ValidateDuplicateFacts.getDuplicateFactSetsWithType(val.modelXbrl.facts, DuplicateType.INCOMPLETE)
    for duplicateFactSet in duplicateFactSets:
        fact = duplicateFactSet.facts[0]
        yield Validation.error(
            codes='EDINET.EC8024E',
            msg=_("Instance values of the same element, context, and unit may not "
                  "have different values or different decimals attributes. <element=%(concept)s> "
                  "<contextID=%(context)s> <unit=%(unit)s>. Correct the element with the relevant "
                  "context ID. For elements in an inline XBRL file that have duplicate "
                  "elements, context IDs, and unit IDs, set the same values for the value and "
                  "decimals attribute."),
            concept=fact.qname,
            context=fact.contextID,
            unit=fact.unitID,
            modelObject=duplicateFactSet.facts,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8062W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8062W: The sum of all liabilities and equity must equal the sum of all assets.
    """
    deduplicatedFacts = pluginData.getDeduplicatedFacts(val.modelXbrl)

    factsByContextId = defaultdict(list)
    for fact in deduplicatedFacts:
        if fact.qname not in (pluginData.assetsIfrsQn, pluginData.liabilitiesAndEquityIfrsQn):
            continue
        if fact.contextID is None or not pluginData.contextIdPattern.fullmatch(fact.contextID):
            continue
        factsByContextId[fact.contextID].append(fact)

    for facts in factsByContextId.values():
        assetSum = Decimal(0)
        liabilitiesAndEquitySum = Decimal(0)
        for fact in facts:
            if isinstance(fact.xValue, float):
                value = Decimal(fact.xValue)
            else:
                value = cast(Decimal, fact.xValue)
            if fact.qname == pluginData.assetsIfrsQn:
                assetSum += value
            elif fact.qname == pluginData.liabilitiesAndEquityIfrsQn:
                liabilitiesAndEquitySum += value
        if assetSum != liabilitiesAndEquitySum:
            yield Validation.warning(
                codes='EDINET.EC8062W',
                msg=_("The consolidated statement of financial position is not reconciled. "
                      "The sum of all liabilities and equity must equal the sum of all assets. "
                      "Please correct the debit (%(liabilitiesAndEquitySum)s) and credit (%(assetSum)s) "
                      "values so that they match."),
                liabilitiesAndEquitySum=f"{liabilitiesAndEquitySum:,}",
                assetSum=f"{assetSum:,}",
                modelObject=facts,
            )
