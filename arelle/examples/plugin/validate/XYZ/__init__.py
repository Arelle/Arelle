"""
See COPYRIGHT.md for copyright information.

Filer Manual Guidelines: https://www.example.com/fake-xyz-filer-manual-v0.0.1.pdf
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from arelle.ModelDocument import LoadingException, ModelDocument
from arelle.Version import authorLabel, copyrightLabel
from .ValidationPluginExtension import ValidationPluginExtension
from .rules import rules01, rules02

PLUGIN_NAME = "Validate XYZ"
DISCLOSURE_SYSTEM_VALIDATION_TYPE = "XYZ"


validationPlugin = ValidationPluginExtension(
    name=PLUGIN_NAME,
    disclosureSystemConfigUrl=Path(__file__).parent / "resources" / "config.xml",
    validationTypes=[DISCLOSURE_SYSTEM_VALIDATION_TYPE],
    validationRuleModules=[rules01, rules02],
)


def disclosureSystemTypes(*args: Any, **kwargs: Any) -> tuple[tuple[str, str], ...]:
    return validationPlugin.disclosureSystemTypes


def disclosureSystemConfigURL(*args: Any, **kwargs: Any) -> str:
    return validationPlugin.disclosureSystemConfigURL


def modelDocumentPullLoader(*args: Any, **kwargs: Any) -> ModelDocument | LoadingException | None:
    return validationPlugin.modelDocumentPullLoader(*args, **kwargs)


def modelXbrlLoadComplete(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.modelXbrlLoadComplete(*args, **kwargs)


def validateXbrlStart(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlStart(*args, **kwargs)


def validateXbrlFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlFinally(*args, **kwargs)


def validateXbrlDtsDocument(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlDtsDocument(*args, **kwargs)


def validateFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateFinally(*args, **kwargs)


__pluginInfo__ = {
    "name": PLUGIN_NAME,
    "version": "0.0.1",
    "description": "Example validation plugin for the fictitious XYZ taxonomy.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "DisclosureSystem.Types": disclosureSystemTypes,
    "DisclosureSystem.ConfigURL": disclosureSystemConfigURL,
    "ModelDocument.PullLoader": modelDocumentPullLoader,
    "ModelXbrl.LoadComplete": modelXbrlLoadComplete,
    "Validate.XBRL.Start": validateXbrlStart,
    "Validate.XBRL.Finally": validateXbrlFinally,
    "Validate.XBRL.DTS.document": validateXbrlDtsDocument,
    "Validate.Finally": validateFinally,
}
