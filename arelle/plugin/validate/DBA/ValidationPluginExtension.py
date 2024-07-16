"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from arelle.ModelValue import qname
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.validate.ValidationPlugin import ValidationPlugin
from .PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

NAMESPACE_CMN = 'http://xbrl.dcca.dk/cmn'
NAMESPACE_FSA = 'http://xbrl.dcca.dk/fsa'
NAMESPACE_GSD = 'http://xbrl.dcca.dk/gsd'
NAMESPACE_SOB = 'http://xbrl.dcca.dk/sob'


class ValidationPluginExtension(ValidationPlugin):
    def newPluginData(self, validateXbrl: ValidateXbrl) -> PluginValidationDataExtension:
        return PluginValidationDataExtension(
            self.name,
            annualReportTypes=frozenset([
                'Årsrapport',
                'årsrapport',
                'Annual report'
            ]),
            assetsQn=qname(f'{{{NAMESPACE_FSA}}}Assets'),
            classOfReportingEntityQn=qname(f'{{{NAMESPACE_FSA}}}ClassOfReportingEntity'),
            consolidatedMemberQn=qname(f'{{{NAMESPACE_CMN}}}ConsolidatedMember'),
            consolidatedSoloDimensionQn=qname(f'{{{NAMESPACE_CMN}}}ConsolidatedSoloDimension'),
            dateOfApprovalOfAnnualReportQn=qname(f'{{{NAMESPACE_SOB}}}DateOfApprovalOfAnnualReport'),
            dateOfExtraordinaryDividendDistributedAfterEndOfReportingPeriod=
            qname(f'{{{NAMESPACE_FSA}}}DateOfExtraordinaryDividendDistributedAfterEndOfReportingPeriod'),
            dateOfGeneralMeetingQn=qname(f'{{{NAMESPACE_GSD}}}DateOfGeneralMeeting'),
            distributionOfResultsQns=frozenset([
                qname(f'{{{NAMESPACE_FSA}}}DistributionsResultDistribution'),
                qname(f'{{{NAMESPACE_FSA}}}ExtraordinaryDistributions'),
                qname(f'{{{NAMESPACE_FSA}}}ProposedDividendRecognisedInEquity'),
                qname(f'{{{NAMESPACE_FSA}}}ProposedExtraordinaryDividendRecognisedInEquity'),
                qname(f'{{{NAMESPACE_FSA}}}ProposedExtraordinaryDividendRecognisedInLiabilities'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredFromToHedgeFund'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredFromToReserveFund'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredFromToReservesAvailable'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredToFromEquityAttributableToParent'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredToFromMinorityInterests'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredToFromOtherStatutoryReserves'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredToFromReserveAccordingToArticlesOfAssociation'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredToFromReserveForNetRevaluationAccordingToEquityMethod'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredToFromReserveForNetRevaluationOfInvestmentAssets'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredToFromRestOfOtherReserves'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredToFromRetainedEarnings'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredToReserveForCurrentValueAdjustmentsOfCurrencyGains'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredToReserveForCurrentValueOfHedging'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredToReserveForDevelopmentExpenditure'),
                qname(f'{{{NAMESPACE_FSA}}}TransferredToReserveForEntrepreneurialCompany'),
            ]),
            equityQn=qname(f'{{{NAMESPACE_FSA}}}Equity'),
            extraordinaryCostsQn=qname(f'{{{NAMESPACE_FSA}}}ExtraordinaryCosts'),
            extraordinaryIncomeQn=qname(f'{{{NAMESPACE_FSA}}}ExtraordinaryIncome'),
            extraordinaryResultBeforeTaxQn=qname(f'{{{NAMESPACE_FSA}}}ExtraordinaryResultBeforeTax'),
            informationOnTypeOfSubmittedReportQn=qname(f'{{{NAMESPACE_GSD}}}InformationOnTypeOfSubmittedReport'),
            liabilitiesQn=qname(f'{{{NAMESPACE_FSA}}}LiabilitiesAndEquity'),
            positiveProfitThreshold=1000,
            precedingReportingPeriodEndDateQn=qname(f'{{{NAMESPACE_GSD}}}PredingReportingPeriodEndDate'),  # Typo in taxonomy
            precedingReportingPeriodStartDateQn=qname(f'{{{NAMESPACE_GSD}}}PrecedingReportingPeriodStartDate'),
            profitLossQn=qname(f'{{{NAMESPACE_FSA}}}ProfitLoss'),
            proposedDividendRecognisedInEquityQn=qname(f'{{{NAMESPACE_FSA}}}ProposedDividendRecognisedInEquity'),
            reportingPeriodEndDateQn=qname(f'{{{NAMESPACE_GSD}}}ReportingPeriodEndDate'),
            reportingPeriodStartDateQn=qname(f'{{{NAMESPACE_GSD}}}ReportingPeriodStartDate'),
            taxExpenseOnOrdinaryActivitiesQn=qname(f'{{{NAMESPACE_FSA}}}TaxExpenseOnOrdinaryActivities'),
            taxExpenseQn=qname(f'{{{NAMESPACE_FSA}}}TaxExpense'),
            typeOfReportingPeriodDimensionQn=qname(f'{{{NAMESPACE_GSD}}}TypeOfReportingPeriodDimension'),
        )
