"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any

from arelle.ModelDocument import LoadingException, ModelDocument
from arelle.ModelXbrl import ModelXbrl
from arelle.Version import authorLabel, copyrightLabel
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import PluginHooks

_: TypeGetText


class DeprecatedESEF2022Plugin(PluginHooks):
    """
    The 'validate/ESEF_2022' plugin has been merged into the `validate/ESEF` plugin using disclosure systems to select the year.
    This implementation only exists to raise an error and inform users to migrate their configuration.
    """

    @staticmethod
    def modelDocumentPullLoader(
        modelXbrl: ModelXbrl,
        normalizedUri: str,
        filepath: str,
        isEntry: bool,
        namespace: str | None,
        *args: Any,
        **kwargs: Any,
    ) -> ModelDocument | LoadingException | None:
        message = _("The 'validate/ESEF_2022' plugin has been combined with the 'validate/ESEF' plugin. Please use the 'validate/ESEF' plugin with a 2022 disclosure system.")
        modelXbrl.error("plugin:deprecated", message)
        return LoadingException(message)


__pluginInfo__ = {
    "name": "Validate ESMA ESEF-2022",
    "version": "1.2023.00",
    "description": "Deprecated: use the 'validate/ESEF' plugin with a 2022 disclosure system instead.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "import": ("inlineXbrlDocumentSet",),
    "ModelDocument.PullLoader": DeprecatedESEF2022Plugin.modelDocumentPullLoader,
}
