"""
See COPYRIGHT.md for copyright information.
- [Operation Guides](https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WEEK0060.html)
- [Document Search](https://disclosure2.edinet-fsa.go.jp/week0020.aspx)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from arelle.ModelXbrl import ModelXbrl
from arelle.Version import authorLabel, copyrightLabel
from . import Constants
from .ValidationPluginExtension import ValidationPluginExtension
from .rules import contexts, edinet, frta, gfm, manifests, upload

PLUGIN_NAME = "Validate EDINET"
DISCLOSURE_SYSTEM_VALIDATION_TYPE = "EDINET"
RELEVELER_MAP: dict[str, dict[str, tuple[str, str | None]]] = {
    "ERROR": {
        # Silence, duplicated by EDINET.EC5002E
        "xbrl.4.8.2:sharesFactUnit-notSharesMeasure": ("ERROR", None),
        # Silence, duplicated by EDINET.EC5002E
        "xbrl.4.8.2:sharesFactUnit-notSingleMeasure": ("ERROR", None),
    },
}


validationPlugin = ValidationPluginExtension(
    name=PLUGIN_NAME,
    disclosureSystemConfigUrl=Path(__file__).parent / "resources" / "config.xml",
    validationTypes=[DISCLOSURE_SYSTEM_VALIDATION_TYPE],
    validationRuleModules=[
        contexts,
        edinet,
        frta,
        gfm,
        manifests,
        upload,
    ],
)


def disclosureSystemTypes(*args: Any, **kwargs: Any) -> tuple[tuple[str, str], ...]:
    return validationPlugin.disclosureSystemTypes


def disclosureSystemConfigURL(*args: Any, **kwargs: Any) -> str:
    return validationPlugin.disclosureSystemConfigURL


def fileSourceEntrypointFiles(*args: Any, **kwargs: Any) -> list[dict[str, Any]] | None:
    return validationPlugin.fileSourceEntrypointFiles(*args, **kwargs)


def loggingSeverityReleveler(modelXbrl: ModelXbrl, level: str, messageCode: str, args: Any, **kwargs: Any) -> tuple[str | None, str | None]:
    if level in RELEVELER_MAP:
        return RELEVELER_MAP[level].get(messageCode, (level, messageCode))
    return level, messageCode


def validateComplete(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateComplete(*args, **kwargs)


def validateFileSource(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateFileSource(*args, **kwargs)


def validateFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateFinally(*args, **kwargs)


def validateXbrlFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlFinally(*args, **kwargs)


__pluginInfo__ = {
    "name": PLUGIN_NAME,
    "version": "0.0.1",
    "description": "Validation plugin for the EDINET taxonomies.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "import": ("inlineXbrlDocumentSet",),
    "DisclosureSystem.Types": disclosureSystemTypes,
    "DisclosureSystem.ConfigURL": disclosureSystemConfigURL,
    "FileSource.EntrypointFiles": fileSourceEntrypointFiles,
    "Logging.Severity.Releveler": loggingSeverityReleveler,
    "Validate.Complete": validateComplete,
    "Validate.FileSource": validateFileSource,
    "Validate.XBRL.Finally": validateXbrlFinally,
    "ValidateFormula.Finished": validateFinally,
}
