"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from arelle.Cntlr import Cntlr
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.validate.ValidationPlugin import ValidationPlugin
from .PluginValidationDataExtension import PluginValidationDataExtension


_: TypeGetText

EQUITY = 'Equity'
IE_PROFIT_LOSS = 'ProfitLossBeforeTax'
IE_PROFIT_LOSS_ORDINARY = 'ProfitLossOnOrdinaryActivitiesBeforeTax'
PRINCIPAL_CURRENCY = 'PrincipalCurrencyUsedInBusinessReport'
TURNOVER_REVENUE = 'DPLTurnoverRevenue'


class ValidationPluginExtension(ValidationPlugin):
    def newPluginData(self, cntlr: Cntlr, validateXbrl: ValidateXbrl | None) -> PluginValidationDataExtension:
        return PluginValidationDataExtension(
            self.name
        )
