"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
from collections import defaultdict

from dateutil.relativedelta import relativedelta
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
from arelle.utils.validate.Validation import Level, Validation
from ..Constants import FINANCIAL_STATEMENT_CONTEXT_ID_PATTERN, CONTEXT_ID_PATTERN, INDIVIDUAL_CONTEXT_ID_PATTERN
from ..ContextRequirement import CONTEXT_REQUIREMENTS
from ..ControllerPluginData import ControllerPluginData
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..FilingFormat import DocumentType
from ..FormType import FormType
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
            fact.qname.namespaceURI == pluginData.namespaces.jppfs
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
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8015W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8015W: For consolidated reports, there must not be a context that represents an individual.

    Consolidated reports identified by presence of WhetherConsolidatedFinancialStatementsArePreparedDEI with True value.
    Individual context identified by context ID matching pattern with "_NonConsolidatedMember".
    """
    if pluginData.isConsolidated() != True:
        return
    individualContexts = [
            context
            for modelXbrl in pluginData.loadedModelXbrls
            for contextId, context in modelXbrl.contexts.items()
            if INDIVIDUAL_CONTEXT_ID_PATTERN.fullmatch(contextId)
    ]
    if len(individualContexts) > 0:
        yield Validation.warning(
            codes='EDINET.EC8015W',
            msg=_("There is a context ID in the inline XBRL file that represents an individual. "
                  "If you do not want to enter information related to individual financial statements, "
                  "delete the context ID that indicates individual. "
                  "If you want to enter individual financial statements, "
                  "check the \"WhetherConsolidatedFinancialStatementsArePreparedDEI\" status in the DEI "
                  "information. "
                  "* If there is a change from non-consolidated to consolidated, even if the data content "
                  "is normal, it may be recognized as an exception and a warning may be displayed."),
            modelObject=individualContexts,
        )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_contextDeiRequirements(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8018W, EDINET.EC8019W, and EDINET.EC8020W assert that context instant, startDate, and endDate values
    (respectively) match certain DEI values based on the presence of DEI values and patterns in the context ID.
    See section 3-4-2 in the Validation Guidelines.
    """
    for modelXbrl in pluginData.loadedModelXbrls:
        for contextId, context in modelXbrl.contexts.items():
            for contextDeiRequirement in CONTEXT_REQUIREMENTS:
                if not contextId.startswith(contextDeiRequirement.contextId):
                    continue
                if contextDeiRequirement.elementDoesNotExist is not None:
                    if pluginData.getDeiValue(contextDeiRequirement.elementDoesNotExist) is not None:
                        continue
                if contextDeiRequirement.elementExists is not None:
                    if pluginData.getDeiValue(contextDeiRequirement.elementExists) is None:
                        continue

                if contextDeiRequirement.element == 'startDate':
                    contextValue = context.startDatetime
                    code = "EDINET.EC8019W"
                elif contextDeiRequirement.element == 'endDate':
                    contextValue = context.endDatetime
                    code = "EDINET.EC8020W"
                else:
                    assert contextDeiRequirement.element == 'instant'
                    contextValue = context.instantDatetime
                    code = "EDINET.EC8018W"

                deiValue = pluginData.getDeiValue(contextDeiRequirement.elementMatch)
                if deiValue is None:
                    continue
                deiValue = cast(datetime.datetime, deiValue)

                if contextDeiRequirement.element in ('instant', 'endDate'):
                    # Instant and end dates are parsed as the beginning of the day after the date specified by the value
                    # DEI values need to be adjusted by 1 day to match this.
                    deiValue = cast(datetime.datetime, deiValue) + datetime.timedelta(1)
                if contextDeiRequirement.dayAdjustment:
                    deiValue = cast(datetime.datetime, deiValue) + datetime.timedelta(contextDeiRequirement.dayAdjustment)

                if contextValue != deiValue:
                    yield Validation.warning(
                        codes=code,
                        msg=_("The context %(element)s element does not match the information in DEI "
                              "\"%(elementMatch)s\". "
                              "Context ID: '%(contextId)s'. "
                              "DEI value: '%(deiValue)s'. "
                              "Context value: '%(contextValue)s'. "
                              "Please set the same value for the %(element)s element value of the corresponding "
                              "context ID and the DEI information value."),
                        element=contextDeiRequirement.element,
                        elementMatch=contextDeiRequirement.elementMatch,
                        contextId=contextId,
                        deiValue=deiValue.date().isoformat(),
                        contextValue=contextValue.date().isoformat(),
                    )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8021W(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8021W: "EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI" or "CurrentPeriodEndDateDEI"
    must not be more than one year earlier than "FilingDateCoverPage".


    If the "EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI" of the DEI information is present,
    then its value must not be more than one year earlier than "FilingDateCoverPage".
    If "EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI" is not present, but "CurrentPeriodEndDateDEI"
    is present, then its value must not be more than one year earlier than "FilingDateCoverPage".
    """
    localName = 'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI'
    targetDate = pluginData.getDeiValue(localName)
    if not isinstance(targetDate, datetime.datetime):
        localName = 'CurrentPeriodEndDateDEI'
        targetDate = pluginData.getDeiValue(localName)
    if not isinstance(targetDate, datetime.datetime):
        return
    compareDate = cast(datetime.datetime, targetDate + relativedelta(years=1))
    for modelXbrl in pluginData.loadedModelXbrls:
        for fact in modelXbrl.factsByLocalName.get('FilingDateCoverPage', set()):
            if fact.isNil or fact.xValid < VALID:
                continue
            submissionDate = cast(datetime.datetime, fact.xValue)
            if compareDate < submissionDate:
                yield Validation.warning(
                    codes='EDINET.EC8021W',
                    msg=_("The DEI '%(localName)s' information is set to a date that is "
                          "more than one year earlier than 'FilingDateCoverPage'. "
                          "Please set the '%(localName)s' value to a value that is less "
                          "than one year earlier than the value of 'FilingDateCoverPage'. "
                          "%(localName)s: '%(targetDate)s'. "
                          "FilingDateCoverPage: '%(submissionDate)s'. "),
                    localName=localName,
                    targetDate=targetDate.date().isoformat(),
                    submissionDate=submissionDate.date().isoformat(),
                    modelObject=fact,
                )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8032E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8032E: The first six digits of each context identifier must match the "EDINET code"
    in the DEI information (or the "fund code" in the DEI information in the case of the Cabinet
    Office Ordinance on Specified Securities Disclosure).
    """
    localNames = ('EDINETCodeDEI', 'FundCodeDEI')
    codes = set()
    for localName in localNames:
        code = pluginData.getDeiValue(localName)
        if code is None:
            continue
        codes.add(str(code)[:6])
    if len(codes) == 0:
        # If neither code is present in the DEI, it will be caught by other validation(s).
        return
    for modelXbrl in pluginData.loadedModelXbrls:
        for context in modelXbrl.contexts.values():
            __, identifier = context.entityIdentifier
            identifier = identifier[:6]
            if identifier not in codes:
                yield Validation.error(
                    codes='EDINET.EC8032E',
                    msg=_("The context identifier must match the 'EDINETCodeDEI' information in the DEI. "
                          "Please set the identifier (first six digits) of the relevant context ID so "
                          "that it matches the EDINET code of the person submitting the disclosure "
                          "documents (or the fund code in the case of the Specified Securities Disclosure "
                          "Ordinance)."),
                    modelObject=context,
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


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8060E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8060E: A context's scenario element must not have an explicit default member.
    """
    # The error gets downgraded to a warning in the following scenarios:
    warningScenarios = {
        (FormType.FORM_2, DocumentType.SECURITIES_REGISTRATION_STATEMENT),
        (FormType.FORM_2_4, DocumentType.SECURITIES_REGISTRATION_STATEMENT),
        (FormType.FORM_2_5, DocumentType.SECURITIES_REGISTRATION_STATEMENT),
        (FormType.FORM_2_6, DocumentType.SECURITIES_REGISTRATION_STATEMENT),
        (FormType.FORM_2_7, DocumentType.SECURITIES_REGISTRATION_STATEMENT),
        (FormType.FORM_3, DocumentType.ANNUAL_SECURITIES_REPORT),
        (FormType.FORM_3_2, DocumentType.ANNUAL_SECURITIES_REPORT),
        (FormType.FORM_4, DocumentType.ANNUAL_SECURITIES_REPORT),
        (FormType.FORM_4_3, DocumentType.SEMI_ANNUAL_REPORT),
        (FormType.FORM_5, DocumentType.SEMI_ANNUAL_REPORT),
        (FormType.FORM_5_2, DocumentType.SEMI_ANNUAL_REPORT),
    }
    level = Level.ERROR
    code = 'EDINET.EC8060E'
    if (pluginData.getFormType(val.modelXbrl), pluginData.getDocumentType(val.modelXbrl)) in warningScenarios:
        level = Level.WARNING
        code = 'EDINET.EC8060W'
    allContexts = chain(val.modelXbrl.contexts.values(), val.modelXbrl.ixdsUnmappedContexts.values())
    for context in allContexts:
        for qname, dimensionValue in context.qnameDims.items():
            if dimensionValue.contextElement != 'scenario':
                continue
            if dimensionValue.xValid < VALID:
                continue
            explicitValue = dimensionValue.xValue
            dimensionQname = dimensionValue.dimensionQname
            defaultValue = val.modelXbrl.qnameDimensionDefaults.get(dimensionQname)
            if explicitValue == defaultValue:
                yield Validation.build(
                    level=level,
                    codes=code,
                    msg=_("The default member element is explicitly set in the scenario element of the context. "
                          "Context: '%(contextId)s'. "
                          "Please delete the default member (the element with the dimension default "
                          "arc role set) from the scenario element of the context. If deleting it "
                          "violates GFM 1.2.7, the context is unnecessary and cannot be set. "
                          "For details of GFM 1.2.7, please refer to 'Attachment 3 GFM Validation Item List'."),
                    contextId=context.id,
                    modelObject=context,
                )
