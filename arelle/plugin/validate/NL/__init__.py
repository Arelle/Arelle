"""
See COPYRIGHT.md for copyright information.

- [Filer Manual Guidelines](https://www.sbr-nl.nl/werken-met-sbr/taxonomie/documentatie-nederlandse-taxonomie)
- [Kamer van Koophandel Filing Rules - NT16](https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/20220101%20KvK%20Filing%20Rules%20NT%2016%20v1_0.pdf)
- [Kamer van Koophandel Filing Rules - NT17](https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/20230101%20KvK%20Filing%20Rules%20NT17%20v1_1.pdf)
- [SBR Filing Rules - NT16](https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT16%20-%2020210301_0.pdf)
- [SBR Filing Rules - NT17](https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT17%20-%2020220301__.pdf)
- [SBR Filing Rules - NT18](https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT18%20-%2020230301_.pdf)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from arelle.ModelDocument import LoadingException, ModelDocument
from arelle.Version import authorLabel, copyrightLabel
from .ValidationPluginExtension import ValidationPluginExtension
from .rules import br_kvk, fg_nl, fr_kvk, fr_nl

PLUGIN_NAME = "Validate NL"
DISCLOSURE_SYSTEM_VALIDATION_TYPE = "NL"


validationPlugin = ValidationPluginExtension(
    name=PLUGIN_NAME,
    disclosureSystemConfigUrl=Path(__file__).parent / "resources" / "config.xml",
    validationTypes=[DISCLOSURE_SYSTEM_VALIDATION_TYPE],
    validationRuleModules=[br_kvk, fg_nl, fr_kvk, fr_nl],
)


def disclosureSystemTypes(*args: Any, **kwargs: Any) -> tuple[tuple[str, str], ...]:
    return validationPlugin.disclosureSystemTypes


def disclosureSystemConfigURL(*args: Any, **kwargs: Any) -> str:
    return validationPlugin.disclosureSystemConfigURL


def validateXbrlFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlFinally(*args, **kwargs)


__pluginInfo__ = {
    "name": PLUGIN_NAME,
    "version": "0.0.1",
    "description": "Validation plugin for the Netherlands taxonomies.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "DisclosureSystem.Types": disclosureSystemTypes,
    "DisclosureSystem.ConfigURL": disclosureSystemConfigURL,
    "Validate.XBRL.Finally": validateXbrlFinally,
}
