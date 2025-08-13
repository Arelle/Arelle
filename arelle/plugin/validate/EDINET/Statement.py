from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from regex import regex

from arelle.ModelInstanceObject import ModelFact

CONSOLIDATED_ROLE_URI_PATTERN = regex.compile(r'.*rol_[\w]*Consolidated')

STATEMENT_ROLE_URIS = frozenset([
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterPeriodConsolidatedStatementOfComprehensiveIncomeIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterPeriodConsolidatedStatementOfComprehensiveIncomeSingleStatementIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterPeriodConsolidatedStatementOfProfitOrLossIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterPeriodStatementOfComprehensiveIncomeIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterPeriodStatementOfComprehensiveIncomeSingleStatementIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterPeriodStatementOfProfitOrLossIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyConsolidatedStatementOfCashFlowsIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyConsolidatedStatementOfChangesInEquityIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyConsolidatedStatementOfComprehensiveIncomeIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyConsolidatedStatementOfComprehensiveIncomeSingleStatementIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyConsolidatedStatementOfFinancialPositionIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyConsolidatedStatementOfProfitOrLossIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyStatementOfCashFlowsIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyStatementOfChangesInEquityIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyStatementOfComprehensiveIncomeIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyStatementOfComprehensiveIncomeSingleStatementIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyStatementOfFinancialPositionIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedQuarterlyStatementOfProfitOrLossIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualConsolidatedStatementOfCashFlowsIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualConsolidatedStatementOfChangesInEquityIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualConsolidatedStatementOfComprehensiveIncomeIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualConsolidatedStatementOfComprehensiveIncomeSingleStatementIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualConsolidatedStatementOfFinancialPositionIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualConsolidatedStatementOfProfitOrLossIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualStatementOfCashFlowsIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualStatementOfChangesInEquityIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualStatementOfComprehensiveIncomeIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualStatementOfComprehensiveIncomeSingleStatementIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualStatementOfFinancialPositionIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedSemiAnnualStatementOfProfitOrLossIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedYearToQuarterEndConsolidatedStatementOfComprehensiveIncomeIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedYearToQuarterEndConsolidatedStatementOfComprehensiveIncomeSingleStatementIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedYearToQuarterEndConsolidatedStatementOfProfitOrLossIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedYearToQuarterEndStatementOfComprehensiveIncomeIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedYearToQuarterEndStatementOfComprehensiveIncomeSingleStatementIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_CondensedYearToQuarterEndStatementOfProfitOrLossIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_ConsolidatedStatementOfCashFlowsIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_ConsolidatedStatementOfChangesInEquityIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_ConsolidatedStatementOfComprehensiveIncomeIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_ConsolidatedStatementOfComprehensiveIncomeSingleStatementIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_ConsolidatedStatementOfFinancialPositionIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_ConsolidatedStatementOfProfitOrLossIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_StatementOfCashFlowsIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_StatementOfChangesInEquityIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_StatementOfComprehensiveIncomeIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_StatementOfComprehensiveIncomeSingleStatementIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_StatementOfFinancialPositionIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_StatementOfProfitOrLossIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_std_ConsolidatedStatementOfCashFlowsIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_std_ConsolidatedStatementOfChangesInEquityIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_std_ConsolidatedStatementOfComprehensiveIncomeIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_std_ConsolidatedStatementOfFinancialPositionIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_std_ConsolidatedStatementOfProfitOrLossIFRS',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_QuarterlyBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_QuarterlyConsolidatedBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_SemiAnnualConsolidatedBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_Type1SemiAnnualBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_Type1SemiAnnualConsolidatedBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_BalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_QuarterlyBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_QuarterlyConsolidatedBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualConsolidatedBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_Type1SemiAnnualBalanceSheet',
    'http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_Type1SemiAnnualConsolidatedBalanceSheet',
])


class StatementType(Enum):
    BALANCE_SHEET = 'BalanceSheet'
    CONSOLIDATED_BALANCE_SHEET = 'ConsolidatedBalanceSheetIFRS'
    STATEMENT_OF_CASH_FLOWS = 'StatementOfCashFlowsIFRS'
    STATEMENT_OF_CHANGES_IN_EQUITY = 'StatementOfChangesInEquityIFRS'
    STATEMENT_OF_COMPREHENSIVE_INCOME = 'StatementOfComprehensiveIncomeIFRS'
    STATEMENT_OF_COMPREHENSIVE_INCOME_SINGLE_STATEMENT = 'StatementOfComprehensiveIncomeSingleStatementIFRS'
    STATEMENT_OF_FINANCIAL_POSITION = 'StatementOfFinancialPositionIFRS'
    STATEMENT_OF_PROFIT_OR_LOSS = 'StatementOfProfitOrLossIFRS'


@dataclass(frozen=True)
class Statement:
    isConsolidated: bool
    roleUri: str
    statementType: StatementType


@dataclass(frozen=True)
class BalanceSheet:
    assetsTotal: Decimal
    contextId: str
    facts: list[ModelFact]
    liabilitiesAndEquityTotal: Decimal
    unitId: str


@dataclass(frozen=True)
class StatementInstance:
    balanceSheets: list[BalanceSheet]
    statement: Statement

def _buildStatements() -> frozenset[Statement]:
    """
    Build a frozenset of Statement objects from the STATEMENT_ROLE_URIS.
    This is done to avoid re-evaluating the set comprehension multiple times.
    """
    statements = []
    for roleUri in STATEMENT_ROLE_URIS:
        isConsolidated = bool(CONSOLIDATED_ROLE_URI_PATTERN.match(roleUri))
        statementType=next(
            statementType
            for statementType in StatementType
            if roleUri.endswith(statementType.value)
        )
        statements.append(
            Statement(
                isConsolidated=isConsolidated,
                roleUri=roleUri,
                statementType=statementType
            )
        )
    return frozenset(statements)


STATEMENTS = _buildStatements()
