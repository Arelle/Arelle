"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
from collections import defaultdict
from itertools import chain
from typing import Any, Iterable, cast

from arelle import XbrlConst
from arelle.Cntlr import Cntlr
from arelle.FileSource import FileSource
from arelle.LinkbaseType import LinkbaseType
from arelle.ModelDtsObject import ModelConcept
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XmlValidateConst import VALID
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..Constants import FINANCIAL_STATEMENT_CONTEXT_ID_PATTERN, CONTEXT_ID_PATTERN, INDIVIDUAL_CONTEXT_ID_PATTERN
from ..ContextRequirement import CONTEXT_REQUIREMENTS
from ..ControllerPluginData import ControllerPluginData
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..PluginValidationDataExtension import PluginValidationDataExtension
from ..ReportFolderType import ReportFolderType

_: TypeGetText


# Per "Framework Design of EDINET Taxonomy", ELR definitions contain a 6-digit
# can be used to categorize the ELR.
FINANCIAL_STATEMENT_ELR_PREFIXES = (
    '3', # Codes starting with 3 indicate "Japanese GAAP Financial Statement"
    '5', # Codes starting with 5 indicate "IFRS Financial Statement"
)


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8011W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8011W: The context ID must conform to the naming rules.
    """
    for contextId, context in val.modelXbrl.contexts.items():
        if not CONTEXT_ID_PATTERN.fullmatch(contextId):
            yield Validation.warning(
                codes='EDINET.EC8011W',
                msg=_("The context ID does not conform to the naming rules. "
                      "Context ID: '%(contextId)s'. "
                      "Please correct the relevant context ID in accordance with the naming rules. "
                      "* No action is required for warnings caused by setting \"FutureDate\" "
                      "for first portion of context ID. "
                      "* No action is required for warnings caused by tagging for disclosure beyond "
                      "the period specified in the naming convention for \"total greenhouse gas emissions.\""),
                contextId=contextId,
                modelObject=context,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8012W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8012W: If a main financial statement element is present, a calculation linkbase file must be present.
    """
    if not any(
            fact.qname.namespaceURI == pluginData.jppfsNamespace
            for fact in val.modelXbrl.facts
    ):
        return
    relSet = val.modelXbrl.relationshipSet(tuple(LinkbaseType.CALCULATION.getArcroles()))
    if relSet is None or len(relSet.modelRelationships) == 0:
        yield Validation.warning(
            codes='EDINET.EC8012W',
            msg=_("If a main financial statement element is present, a calculation linkbase "
                  "file must be present. "
                  "If you wish to tag the financial statements, please submit a "
                  "calculation linkbase file."),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8013W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8013W: The context ID of the element associated with the financial statement
    extended link role begins with one of the following strings:
    Prior?YearDuration
    CurrentYearDuration
    Prior?YearInstant
    CurrentYearInstant
    InterimDuration
    InterimInstant
    Prior?InterimDuration
    Prior?InterimInstant
    Where ? is a digit from 1 to 9.
    """
    financialStatementRoleTypes = set()
    for roleUri, roleTypes in val.modelXbrl.roleTypes.items():
        for roleType in roleTypes:
            definition = roleType.definition
            roleTypeCode = roleType.definition.split(' ')[0] if definition else None
            if roleTypeCode is None:
                continue
            if any(roleTypeCode.startswith(prefix) for prefix in FINANCIAL_STATEMENT_ELR_PREFIXES):
                financialStatementRoleTypes.add(roleType)

    financialStatementConcepts: set[ModelConcept] = set()
    labelsRelationshipSet = val.modelXbrl.relationshipSet(
        XbrlConst.parentChild,
        tuple(roleType.roleURI for roleType in financialStatementRoleTypes)
    )
    financialStatementConcepts.update(labelsRelationshipSet.fromModelObjects().keys())
    financialStatementConcepts.update(labelsRelationshipSet.toModelObjects().keys())

    invalidContextIdMap = defaultdict(list)
    for fact in val.modelXbrl.facts:
        if fact.concept not in financialStatementConcepts:
            continue
        if fact.contextID is None:
            continue
        if not FINANCIAL_STATEMENT_CONTEXT_ID_PATTERN.fullmatch(fact.contextID):
            invalidContextIdMap[fact.contextID].append(fact)
    for contextId, facts in invalidContextIdMap.items():
        yield Validation.warning(
            codes='EDINET.EC8013W',
            msg=_("The context ID (id=%(contextId)s) for the element related to the extended link role "
                  "in Financial Statement is not per convention. Please set the context ID of the element "
                  "related to the extended link role of financial statements according to the rules. For "
                  "the financial statements, please refer to \"3-4-2 Setting the Context\" in the "
                  "\"Validation Guidelines\"."),
            contextId=contextId,
            modelObject=facts,
        )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8014W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8014W: For individual (non-consolidated) reports, there must be a context that represents an individual.

    Individual reports identified by presence of WhetherConsolidatedFinancialStatementsArePreparedDEI with False value.
    Individual context identified by context ID matching pattern with "_NonConsolidatedMember".
    """
    if pluginData.isConsolidated() != False:
        return
    if not any(
            INDIVIDUAL_CONTEXT_ID_PATTERN.fullmatch(contextID)
            for modelXbrl in pluginData.loadedModelXbrls
            for contextID in modelXbrl.contexts
    ):
        yield Validation.warning(
            codes='EDINET.EC8014W',
            msg=_("There is no context ID in the inline XBRL file that represents an individual. "
                  "Please set a context ID that indicates individual financial "
                  "statements in the inline XBRL file. "
                  "If you are not including individual financial statements, "
                  "please check the \"WhetherConsolidatedFinancialStatementsArePreparedDEI\" "
                  "value of the DEI information."),
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
def rule_EC8054W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8054W: For any context with ID containing "NonConsolidatedMember",
    the scenario element within must be set to "NonConsolidatedMember".
    """
    allContexts = chain(val.modelXbrl.contexts.values(), val.modelXbrl.ixdsUnmappedContexts.values())
    for context in allContexts:
        if context.id is None or pluginData.nonConsolidatedMemberQn.localName not in context.id:
            continue
        member = context.dimMemberQname(
            pluginData.consolidatedOrNonConsolidatedAxisQn,
            includeDefaults=True
        )
        if member != pluginData.nonConsolidatedMemberQn:
            yield Validation.warning(
                codes='EDINET.EC8054W',
                msg=_("For the context ID (%(contextId)s), \"NonConsolidatedMember\" "
                      "is not set in the scenario element. Please correct the relevant "
                      "context ID and scenario element. For naming rules for context IDs, "
                      "refer to \"5-4-1 Naming Rules for Context IDs\" in the \"Guidelines "
                      "for Creating Report Instances.\""),
                contextId=context.id,
                modelObject=context,
            )
