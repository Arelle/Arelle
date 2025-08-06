"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any

from arelle.FileSource import FileSource
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.validate.ValidationPlugin import ValidationPlugin
from .ControllerPluginData import ControllerPluginData
from .DisclosureSystems import DISCLOSURE_SYSTEM_EDINET
from .ManifestInstance import parseManifests
from .PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


class ValidationPluginExtension(ValidationPlugin):

    def fileSourceEntrypointFiles(self, filesource: FileSource, *args: Any, **kwargs: Any) -> list[dict[str, Any]] | None:
        instances = parseManifests(filesource)
        if len(instances) == 0:
            return None
        assert filesource.cntlr is not None
        pluginData = ControllerPluginData.get(filesource.cntlr, self.name)
        entrypointFiles = []
        for instance in instances:
            pluginData.addManifestInstance(instance)
            entrypoints = []
            for ixbrlFile in instance.ixbrlFiles:
                filesource.select(str(ixbrlFile))
                entrypoints.append({"file": filesource.url})
            entrypointFiles.append({'ixds': entrypoints, 'id': instance.id})
        return entrypointFiles

    def newPluginData(self, validateXbrl: ValidateXbrl) -> PluginValidationDataExtension:
        disclosureSystem = validateXbrl.disclosureSystem.name
        if disclosureSystem == DISCLOSURE_SYSTEM_EDINET:
            pass
        else:
            raise ValueError(f'Invalid EDINET disclosure system: {disclosureSystem}')
        return PluginValidationDataExtension(
            self.name,
        )
