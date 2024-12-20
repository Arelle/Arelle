"""
See COPYRIGHT.md for copyright information.

Filer Guidelines:
- [Technical Note](https://www.revenue.ie/en/online-services/support/documents/ixbrl/ixbrl-technical-note.pdf)
- [Error Messages](https://www.revenue.ie/en/online-services/support/documents/ixbrl/error-messages.pdf)
- [Style Guide](https://www.revenue.ie/en/online-services/support/documents/ixbrl/ixbrl-style-guide.pdf)
"""
from __future__ import annotations

from arelle.Version import authorLabel, copyrightLabel
from pathlib import Path
from typing import Any
from .ValidationPluginExtension import ValidationPluginExtension
from .rules import ros

PLUGIN_NAME = "Validate ROS"
DISCLOSURE_SYSTEM_VALIDATION_TYPE = "ROS"

validationPlugin = ValidationPluginExtension(
    name=PLUGIN_NAME,
    disclosureSystemConfigUrl=Path(__file__).parent / "resources" / "config.xml",
    validationTypes=[DISCLOSURE_SYSTEM_VALIDATION_TYPE],
    validationRuleModules=[ros],
)


def disclosureSystemTypes(*args: Any, **kwargs: Any) -> tuple[tuple[str, str], ...]:
    return validationPlugin.disclosureSystemTypes


def disclosureSystemConfigURL(*args: Any, **kwargs: Any) -> str:
    return validationPlugin.disclosureSystemConfigURL


def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateROSplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "ROSplugin", False)
    if not (val.validateROSplugin):
        return


def validateXbrlFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlFinally(*args, **kwargs)


__pluginInfo__ = {
    'name': PLUGIN_NAME,
    'version': '1.0',
    'description': '''ROS (Ireland) Validation.''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    'import': ('inlineXbrlDocumentSet', ), # import dependent modules
    # classes of mount points (required)
    'DisclosureSystem.Types': disclosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
}
