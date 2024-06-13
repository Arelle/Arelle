"""
See COPYRIGHT.md for copyright information.
"""

from typing import Any

from arelle.oim.Validate import validateOIM
from arelle.ValidateXbrl import ValidateXbrl
from arelle.Version import authorLabel, copyrightLabel


def validateFinally(val: ValidateXbrl, *args: Any, **kwargs: Any) -> None:
    modelXbrl = val.modelXbrl
    if not modelXbrl.loadedFromOIM and not modelXbrl.modelManager.validateXmlOim:
        # Consistent legacy behavior. Always perform OIM validation if this plugin is enabled.
        validateOIM(modelXbrl)


__pluginInfo__ = {
    "name": "Load From OIM",
    "version": "1.3",
    "description": "(deprecated) this plugin is no longer required. Loading OIM reports no longer requires a plugin.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    # classes of mount points (required)
    "Validate.XBRL.Finally": validateFinally,
}
