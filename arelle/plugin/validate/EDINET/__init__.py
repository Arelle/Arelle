"""
See COPYRIGHT.md for copyright information.
- [Operation Guides](https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WEEK0060.html)
- [Document Search](https://disclosure2.edinet-fsa.go.jp/week0020.aspx)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.Version import authorLabel, copyrightLabel
from . import Constants
from .ControllerPluginData import ControllerPluginData
from .ValidationPluginExtension import ValidationPluginExtension
from .rules import contexts, edinet, frta, gfm, manifests, upload

PLUGIN_NAME = "Validate EDINET"
DISCLOSURE_SYSTEM_VALIDATION_TYPE = "EDINET"
RELEVELER_MAP: dict[str, dict[str, tuple[str, str | None]]] = {
    "ERROR": {
        # Re-code to EDINET version
        "GFM.1.1.3": ("WARNING", "EDINET.EC5700W.GFM.1.1.3"),
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
    if level not in RELEVELER_MAP:
        return level, messageCode
    messageCodes = list(args.get('messageCodes') or [])
    if messageCode is not None:
        messageCodes.append(messageCode)
    for code in messageCodes:
        result =  RELEVELER_MAP[level].get(code)
        if result is not None:
            return result
    return level, messageCode


def validateComplete(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateComplete(*args, **kwargs)


def validateFileSource(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateFileSource(*args, **kwargs)


def validateFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateFinally(*args, **kwargs)


def validateXbrlStart(val: ValidateXbrl, *args: Any, **kwargs: Any) -> None:
    # TODO: See ControllerPluginData.loadedModelXbrls comment
    controllerPluginData = ControllerPluginData.get(val.modelXbrl.modelManager.cntlr, PLUGIN_NAME)
    controllerPluginData.addModelXbrl(val.modelXbrl)
    return validationPlugin.validateXbrlStart(val, *args, **kwargs)


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
    'Validate.XBRL.Start': validateXbrlStart,
    "ValidateFormula.Finished": validateFinally,
}
