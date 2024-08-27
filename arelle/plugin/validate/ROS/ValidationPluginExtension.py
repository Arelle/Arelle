"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.validate.ValidationPlugin import ValidationPlugin
from .PluginValidationDataExtension import PluginValidationDataExtension


_: TypeGetText

IE_PROFIT_LOSS = 'ProfitLossBeforeTax'
IE_PROFIT_LOSS_ORDINARY = 'ProfitLossOnOrdinaryActivitiesBeforeTax'
PRINCIPAL_CURRENCY = 'PrincipalCurrencyUsedInBusinessReport'
TURNOVER_REVENUE = 'DPLTurnoverRevenue'


class ValidationPluginExtension(ValidationPlugin):
    def newPluginData(self, validateXbrl: ValidateXbrl) -> PluginValidationDataExtension:
        return PluginValidationDataExtension(
            self.name
        )
