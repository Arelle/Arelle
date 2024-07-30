"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.validate.ValidationPlugin import ValidationPlugin
from .PluginValidationDataExtension import PluginValidationDataExtension


_: TypeGetText

IE_GAAP_PROFIT_LOSS = 'ProfitLossOnOrdinaryActivitiesBeforeTax'
IE_IFRS_PROFIT_LOSS = 'ProfitLossBeforeTax'
NAMESPACE_IE_FRS_101 = 'https://xbrl.frc.org.uk/ireland/FRS-101/'
NAMESPACE_IE_FRS_102 = 'https://xbrl.frc.org.uk/ireland/FRS-102/'
NAMESPACE_IE_IFRS = 'https://xbrl.frc.org.uk/ireland/IFRS/'


class ValidationPluginExtension(ValidationPlugin):
    def newPluginData(self, validateXbrl: ValidateXbrl) -> PluginValidationDataExtension:
        return PluginValidationDataExtension(
            self.name
        )
