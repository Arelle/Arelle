"""
See COPYRIGHT.md for copyright information.

Hong Kong IRD Profits Tax iXBRL validation for BIR51 and BIR52 filings.

The IRD brands this edition 2025 (Year of Assessment 2025/26). Taxonomy
package filenames are dated 1 April of the following calendar year, so
the current package is 2026-04-01.

- [IRD iXBRL materials](https://www.ird.gov.hk/eng/tax/bus_ixbrl_materials.htm)

Plugin entry point — loaded by Arelle via --plugin plugin/validate/IRD.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from arelle.Version import authorLabel, copyrightLabel

from .ValidationPluginExtension import ValidationPluginExtension
from .rules import (
    ixbrl_technical,
    nvad_accounting_period,
    nvad_bir51_corporate,
    nvad_bir51_sbp,
    nvad_bir52_partners,
    nvad_combined_fs,
    nvad_currency,
    nvad_environmental,
    nvad_expense_deductions,
    nvad_expense_misc,
    nvad_form_type,
    nvad_identifiers,
    nvad_income_paired,
    nvad_integrity,
    nvad_lifecycle,
    nvad_special_flags,
    nvad_structural,
)

PLUGIN_NAME = "Validate IRD"
DISCLOSURE_SYSTEM_VALIDATION_TYPE = "IRD"

CONFIG_PATH = Path(__file__).parent / "resources" / "config.xml"
validationPlugin = ValidationPluginExtension(
    name=PLUGIN_NAME,
    disclosureSystemConfigUrl=CONFIG_PATH,
    validationTypes=[DISCLOSURE_SYSTEM_VALIDATION_TYPE],
    validationRuleModules=[
        ixbrl_technical,
        nvad_accounting_period,
        nvad_bir51_corporate,
        nvad_bir51_sbp,
        nvad_bir52_partners,
        nvad_combined_fs,
        nvad_currency,
        nvad_environmental,
        nvad_expense_deductions,
        nvad_expense_misc,
        nvad_form_type,
        nvad_identifiers,
        nvad_income_paired,
        nvad_integrity,
        nvad_lifecycle,
        nvad_special_flags,
        nvad_structural,
    ],
)


def disclosureSystemTypes(
    *args: Any, **kwargs: Any
) -> tuple[tuple[str, str], ...]:
    return validationPlugin.disclosureSystemTypes


def disclosureSystemConfigURL(*args: Any, **kwargs: Any) -> str:
    return validationPlugin.disclosureSystemConfigURL


def validateXbrlFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlFinally(*args, **kwargs)


__pluginInfo__ = {
    "name": PLUGIN_NAME,
    "version": "0.1.0",
    "description": (
        "Validation plugin for Hong Kong IRD Profits Tax iXBRL filings "
        "(BIR51/BIR52)."
    ),
    "import": ("inlineXbrlDocumentSet",),
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "DisclosureSystem.Types": disclosureSystemTypes,
    "DisclosureSystem.ConfigURL": disclosureSystemConfigURL,
    "Validate.XBRL.Finally": validateXbrlFinally,
}
