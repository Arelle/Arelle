"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from arelle.ModelValue import qname, QName
from arelle.utils.PluginData import PluginData


NAMESPACE_GSD = 'http://xbrl.dcca.dk/gsd'


class PluginValidationDataExtension(PluginData):
    dateOfGeneralMeetingQn: QName = qname(f'{{{NAMESPACE_GSD}}}DateOfGeneralMeeting')
    reportingPeriodEndDateQn: QName = qname(f'{{{NAMESPACE_GSD}}}ReportingPeriodEndDate')
    reportingPeriodStartDateQn: QName = qname(f'{{{NAMESPACE_GSD}}}ReportingPeriodStartDate')
    typeOfReportingPeriodDimensionQn: QName = qname(f'{{{NAMESPACE_GSD}}}TypeOfReportingPeriodDimension')
