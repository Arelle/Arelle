"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from arelle.ModelValue import qname, QName
from arelle.utils.PluginData import PluginData


NAMESPACE_GSD = 'http://xbrl.dcca.dk/gsd'


class PluginValidationDataExtension(PluginData):
    reportingPeriodEndDateQn: QName = qname(f'{{{NAMESPACE_GSD}}}ReportingPeriodEndDate')
    reportingPeriodStartDateQn: QName = qname(f'{{{NAMESPACE_GSD}}}ReportingPeriodStartDate')
