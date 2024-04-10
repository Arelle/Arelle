"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict

from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import qname, QName
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.PluginData import PluginData


NAMESPACE_FSA = 'http://xbrl.dcca.dk/fsa'
NAMESPACE_GSD = 'http://xbrl.dcca.dk/gsd'
NAMESPACE_SOB = 'http://xbrl.dcca.dk/sob'


class PluginValidationDataExtension(PluginData):
    _contextFactMap: dict[str, dict[QName, ModelFact]] | None = None
    annualReportTypes: frozenset[str] = frozenset([
        'Årsrapport',
        'årsrapport',
        'Annual report'
    ])
    dateOfApprovalOfAnnualReportQn: QName = qname(f'{{{NAMESPACE_SOB}}}DateOfApprovalOfAnnualReport')
    dateOfExtraordinaryDividendDistributedAfterEndOfReportingPeriod: QName = \
        qname(f'{{{NAMESPACE_FSA}}}DateOfExtraordinaryDividendDistributedAfterEndOfReportingPeriod')
    dateOfGeneralMeetingQn: QName = qname(f'{{{NAMESPACE_GSD}}}DateOfGeneralMeeting')
    informationOnTypeOfSubmittedReportQn: QName = qname(f'{{{NAMESPACE_GSD}}}InformationOnTypeOfSubmittedReport')
    precedingReportingPeriodEndDateQn = qname(f'{{{NAMESPACE_GSD}}}PredingReportingPeriodEndDate')  # Typo in taxonomy
    precedingReportingPeriodStartDateQn = qname(f'{{{NAMESPACE_GSD}}}PrecedingReportingPeriodStartDate')
    reportingPeriodEndDateQn: QName = qname(f'{{{NAMESPACE_GSD}}}ReportingPeriodEndDate')
    reportingPeriodStartDateQn: QName = qname(f'{{{NAMESPACE_GSD}}}ReportingPeriodStartDate')
    typeOfReportingPeriodDimensionQn: QName = qname(f'{{{NAMESPACE_GSD}}}TypeOfReportingPeriodDimension')

    def contextFactMap(self, modelXbrl: ModelXbrl) -> dict[str, dict[QName, ModelFact]]:
        if self._contextFactMap is None:
            self._contextFactMap = defaultdict(dict)
            for fact in modelXbrl.facts:
                self._contextFactMap[fact.contextID][fact.qname] = fact
        return self._contextFactMap
