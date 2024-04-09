"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from arelle.ModelValue import qname, QName
from arelle.utils.PluginData import PluginData


NAMESPACE_FSA = 'http://xbrl.dcca.dk/fsa'
NAMESPACE_GSD = 'http://xbrl.dcca.dk/gsd'
NAMESPACE_SOB = 'http://xbrl.dcca.dk/sob'


class PluginValidationDataExtension(PluginData):
    dateOfApprovalOfAnnualReportQn: QName = qname(f'{{{NAMESPACE_SOB}}}DateOfApprovalOfAnnualReport')
    dateOfExtraordinaryDividendDistributedAfterEndOfReportingPeriod: QName = \
        qname(f'{{{NAMESPACE_FSA}}}DateOfExtraordinaryDividendDistributedAfterEndOfReportingPeriod')
    dateOfGeneralMeetingQn: QName = qname(f'{{{NAMESPACE_GSD}}}DateOfGeneralMeeting')
    reportingPeriodEndDateQn: QName = qname(f'{{{NAMESPACE_GSD}}}ReportingPeriodEndDate')
    reportingPeriodStartDateQn: QName = qname(f'{{{NAMESPACE_GSD}}}ReportingPeriodStartDate')
    typeOfReportingPeriodDimensionQn: QName = qname(f'{{{NAMESPACE_GSD}}}TypeOfReportingPeriodDimension')
