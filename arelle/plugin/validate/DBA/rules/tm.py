"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
import decimal
import itertools
from collections.abc import Iterable
from typing import Any, cast

from arelle.typing import TypeGetText
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.XmlValidateConst import VALID
from . import errorOnRequiredFact, errorOnMultipleFacts
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm12(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM12: gsd:IdentificationNumberCvrOfReportingEntity must be specified
    """
    return errorOnRequiredFact(
        val.modelXbrl,
        pluginData.identificationNumberCvrOfReportingEntityQn,
        'DBA.TM12',
        _('{} must be tagged in the document.').format(pluginData.identificationNumberCvrOfReportingEntityQn.localName)
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm13(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM13: gsd:IdentificationNumberCvrOfReportingEntity must only be tagged once if tagged
    """
    return errorOnMultipleFacts(val.modelXbrl, pluginData.identificationNumberCvrOfReportingEntityQn, 'DBA.TM13')


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm16(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM16: gsd:InformationOnTypeOfSubmittedReport must only be tagged once if tagged
    """
    return errorOnMultipleFacts(val.modelXbrl, pluginData.informationOnTypeOfSubmittedReportQn, 'DBA.TM16')


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm18(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM18: ReportingPeriodStartDate with either no dimensionality or with the default dimension of
    TypeOfReportingPeriodDimension:AllReportingPeriodsMember must only be tagged once.
    """
    modelXbrl = val.modelXbrl
    valid_facts = []
    start_date_facts = modelXbrl.factsByQname.get(pluginData.reportingPeriodStartDateQn, set())
    for fact in start_date_facts:
        if not fact.context.scenDimValues:
            valid_facts.append(fact)
    if len(valid_facts) > 1:
        yield Validation.error(
            'DBA.TM18',
            _('ReportingPeriodStartDate with either no dimensionality or with the default dimension of '
              'TypeOfReportingPeriodDimension:AllReportingPeriodsMember must only be tagged once. {} facts '
              'were found.').format(len(valid_facts)),
            modelObject=valid_facts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm20(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM20: ReportingPeriodEndDate with either no dimensionality or with the default dimension of
    TypeOfReportingPeriodDimension:AllReportingPeriodsMember must only be tagged once.
    """
    modelXbrl = val.modelXbrl
    valid_facts = []
    end_date_facts = modelXbrl.factsByQname.get(pluginData.reportingPeriodEndDateQn, set())
    for fact in end_date_facts:
        if not fact.context.scenDimValues:
            valid_facts.append(fact)
    if len(valid_facts) > 1:
        yield Validation.error(
            'DBA.TM20',
            _('ReportingPeriodEndDate with either no dimensionality or with the default dimension of '
              'TypeOfReportingPeriodDimension:AllReportingPeriodsMember must only be tagged once. {} facts '
              'were found.').format(len(valid_facts)),
            modelObject=valid_facts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm22(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM22: gsd:NameOfReportingEntity must only be tagged once if tagged
    """
    return errorOnMultipleFacts(val.modelXbrl, pluginData.nameOfReportingEntityQn, 'DBA.TM22')


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm24(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM24: gsd:NameOfSubmittingEnterprise must only be tagged once if tagged
    """
    return errorOnMultipleFacts(val.modelXbrl, pluginData.nameOfSubmittingEnterpriseQn, 'DBA.TM24')


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm25(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM25: gsd:AddressOfSubmittingEnterpriseStreetAndNumber must be specified
    """
    return errorOnRequiredFact(
        val.modelXbrl,
        pluginData.addressOfSubmittingEnterpriseStreetAndNumberQn,
        'DBA.TM25',
        _('{} must be tagged in the document.').format(pluginData.addressOfSubmittingEnterpriseStreetAndNumberQn.localName)
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm26(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM26: gsd:AddressOfSubmittingEnterpriseStreetAndNumber must only be tagged once if tagged
    """
    return errorOnMultipleFacts(val.modelXbrl, pluginData.addressOfSubmittingEnterpriseStreetAndNumberQn, 'DBA.TM26')


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm27(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM27: gsd:AddressOfSubmittingEnterprisePostcodeAndTown must be specified
    """
    return errorOnRequiredFact(
        val.modelXbrl,
        pluginData.addressOfSubmittingEnterprisePostcodeAndTownQn,
        'DBA.TM27',
        _('{} must be tagged in the document.').format(pluginData.addressOfSubmittingEnterprisePostcodeAndTownQn.localName)
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm28(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM28: gsd:AddressOfSubmittingEnterprisePostcodeAndTown must only be tagged once if tagged
    """
    return errorOnMultipleFacts(val.modelXbrl, pluginData.addressOfSubmittingEnterprisePostcodeAndTownQn, 'DBA.TM28')


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm29(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM29: Either gsd:DateOfGeneralMeeting or gsd:DateOfApprovalOfReport must be specified
    """
    modelXbrl = val.modelXbrl
    meeting_facts = modelXbrl.factsByQname.get(pluginData.dateOfGeneralMeetingQn, set())
    approval_facts = modelXbrl.factsByQname.get(pluginData.dateOfApprovalOfReportQn, set())
    if len(meeting_facts) == 0 and len(approval_facts) == 0:
        yield Validation.error(
            'DBA.TM29',
            _('Either DateOfGeneralMeeting or DateOfApprovalOfReport must be tagged in the document.')
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm30(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM30: gsd:DateOfGeneralMeeting must only be tagged once if tagged
    """
    return errorOnMultipleFacts(val.modelXbrl, pluginData.dateOfGeneralMeetingQn, 'DBA.TM30')


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm31(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM31: gsd:DateOfApprovalOfReport must only be tagged once if tagged
    """
    return errorOnMultipleFacts(val.modelXbrl, pluginData.dateOfApprovalOfReportQn, 'DBA.TM31')


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm32(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM33: ReportingPeriodStartDate with the dimension of
    TypeOfReportingPeriodDimension:RegisteredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMember
    must only be tagged once.
    """
    modelXbrl = val.modelXbrl
    valid_facts = []
    start_date_facts = modelXbrl.factsByQname.get(pluginData.reportingPeriodStartDateQn, set())
    for fact in start_date_facts:
        member = fact.context.qnameDims.get(pluginData.typeOfReportingPeriodDimensionQn)
        if member is not None and member.memberQname == pluginData.registeredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMemberQn:
            valid_facts.append(fact)
    if len(valid_facts) > 1:
        yield Validation.error(
            'DBA.TM32',
            _('ReportingPeriodStartDate with the dimension of TypeOfReportingPeriodDimension:RegisteredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMember '
              'must only be tagged once. {} facts were found.').format(len(valid_facts)),
            modelObject=valid_facts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm33(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM33: ReportingPeriodEndDate with the dimension of
    TypeOfReportingPeriodDimension:RegisteredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMember
    must only be tagged once.
    """
    modelXbrl = val.modelXbrl
    valid_facts = []
    end_date_facts = modelXbrl.factsByQname.get(pluginData.reportingPeriodEndDateQn, set())
    for fact in end_date_facts:
        member = fact.context.qnameDims.get(pluginData.typeOfReportingPeriodDimensionQn)
        if member is not None and member.memberQname == pluginData.registeredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMemberQn:
            valid_facts.append(fact)
    if len(valid_facts) > 1:
        yield Validation.error(
            'DBA.TM33',
            _('ReportingPeriodEndDate with the dimension of TypeOfReportingPeriodDimension:RegisteredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMember '
              'must only be tagged once. {} facts were found.').format(len(valid_facts)),
            modelObject=valid_facts
        )
