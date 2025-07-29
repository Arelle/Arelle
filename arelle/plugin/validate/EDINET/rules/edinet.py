"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Iterable, cast

import regex

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


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8033W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8033W: The startDate of a context whose context ID starts with
    "CurrentYear" is not set to a date earlier than the endDate of a context
    whose context ID starts with "Prior1Year".
    """
    priorYearContexts = [
        context
        for contextId, context in val.modelXbrl.contexts.items()
        if contextId.startswith('Prior1Year')
           and context.endDatetime is not None
           and context.isStartEndPeriod
    ]
    latestPriorYearContext = None
    for priorYearContext in priorYearContexts:
        if latestPriorYearContext is None or \
                priorYearContext.endDatetime > latestPriorYearContext.endDatetime:
            latestPriorYearContext = priorYearContext
    if latestPriorYearContext is None:
        return
    currentYearContexts = [
        context
        for contextId, context in val.modelXbrl.contexts.items()
        if contextId.startswith('CurrentYear')
           and context.startDatetime is not None
           and context.isStartEndPeriod
    ]
    earliestCurrentYearContext = None
    for currentYearContext in currentYearContexts:
        if earliestCurrentYearContext is None or \
                currentYearContext.endDatetime > earliestCurrentYearContext.startDatetime:
            earliestCurrentYearContext = currentYearContext
    if earliestCurrentYearContext is None:
        return
    if latestPriorYearContext.endDatetime > earliestCurrentYearContext.startDatetime:
        yield Validation.warning(
            codes='EDINET.EC8033W',
            msg=_("The startDate element of the current year context (id=%(currentYearContextId)s) is "
                  "set to a date that is earlier than the endDate element of the prior year context "
                  "(id=%(priorYearContextId)s). Please check the corresponding context ID "
                  "%(currentYearContextId)s and %(priorYearContextId)s. Set the startDate element of "
                  "context ID %(currentYearContextId)s to a date that is later than or equal to the "
                  "endDate element of context ID %(priorYearContextId)s."),
            currentYearContextId=earliestCurrentYearContext.id,
            priorYearContextId=latestPriorYearContext.id,
            modelObject=priorYearContexts + currentYearContexts,
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
    contextIdPattern = regex.compile(r'^(Prior[1-9]Year|CurrentYear|Prior[1-9]Interim|Interim)(Duration|Instant)$')

    factsByContextId = defaultdict(list)
    for fact in deduplicatedFacts:
        if fact.concept.qname not in (pluginData.assetsIfrsQn, pluginData.liabilitiesAndEquityIfrsQn):
            continue
        if not contextIdPattern.match(fact.contextID):
            continue
        factsByContextId[fact.contextID].append(fact)

    for contextId, facts in factsByContextId.items():
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
