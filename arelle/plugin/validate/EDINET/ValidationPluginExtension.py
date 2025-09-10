"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import logging
from typing import Any

from arelle.Cntlr import Cntlr
from arelle.FileSource import FileSource
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginData import PluginData
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
        filesource.cntlr.addToLog(
            _("EDINET manifest(s) detected (%(manifests)s). Loading %(count)s instances (%(instances)s)."),
            messageCode="info",
            messageArgs={
                "manifests": ', '.join(instance.type for instance in instances),
                "count": len(instances),
                "instances": ', '.join(instance.id for instance in instances),
            }, level=logging.INFO
        )
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

    def newPluginData(self, cntlr: Cntlr, validateXbrl: ValidateXbrl | None) -> PluginData:
        if validateXbrl is None:
            return ControllerPluginData.get(cntlr, self.name)
        disclosureSystem = DISCLOSURE_SYSTEM_EDINET
        if validateXbrl is not None:
            disclosureSystem = str(validateXbrl.disclosureSystem.name)
        if disclosureSystem == DISCLOSURE_SYSTEM_EDINET:
            pass
        else:
            raise ValueError(f'Invalid EDINET disclosure system: {disclosureSystem}')
        return PluginValidationDataExtension(
            self.name,
            validateXbrl
        )
