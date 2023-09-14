"""
See COPYRIGHT.md for copyright information.

Filer Manual Guidelines: https://www.example.com/fake-xyz-filer-manual-v0.0.1.pdf
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arelle.ModelDocument import LoadingException, ModelDocument
from arelle.Version import authorLabel, copyrightLabel
from . import rules
from .ValidationPluginExtension import ValidationPluginExtension

DISCLOSURE_SYSTEM_VALIDATION_TYPE = "XYZ"

DISCLOSURE_SYSTEM_2022 = "XYZ 2022"
DISCLOSURE_SYSTEM_2023 = "XYZ 2023"


validationPlugin = ValidationPluginExtension(
    disclosureSystemConfigUrl=Path(__file__).parent / "resources" / "config.xml",
    validationTypes=[DISCLOSURE_SYSTEM_VALIDATION_TYPE],
    validationRulesModule=rules,
)


def disclosureSystemTypes(*args: Any, **kwargs: Any) -> tuple[tuple[str, str], ...]:
    return validationPlugin.disclosureSystemTypes


def disclosureSystemConfigURL(*args: Any, **kwargs: Any) -> str:
    return validationPlugin.disclosureSystemConfigURL


def modelDocumentPullLoader(*args: Any, **kwargs: Any) -> ModelDocument | LoadingException | None:
    return validationPlugin.modelDocumentPullLoader(*args, **kwargs)


def modelXbrlLoadComplete(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.modelXbrlLoadComplete(*args, **kwargs)


def validateXbrlFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlFinally(*args, **kwargs)


def validateXbrlDtsDocument(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlDtsDocument(*args, **kwargs)


def validateFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateFinally(*args, **kwargs)


__pluginInfo__ = {
    "name": "Validate XYZ",
    "version": "0.0.1",
    "description": "Example validation plugin for the fictitious XYZ taxonomy.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "DisclosureSystem.Types": disclosureSystemTypes,
    "DisclosureSystem.ConfigURL": disclosureSystemConfigURL,
    "ModelDocument.PullLoader": modelDocumentPullLoader,
    "ModelXbrl.LoadComplete": modelXbrlLoadComplete,
    "Validate.XBRL.Finally": validateXbrlFinally,
    "Validate.XBRL.DTS.document": validateXbrlDtsDocument,
    "Validate.Finally": validateFinally,
}
