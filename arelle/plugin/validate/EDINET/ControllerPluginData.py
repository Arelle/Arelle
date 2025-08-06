"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from arelle.Cntlr import Cntlr
from arelle.typing import TypeGetText
from arelle.utils.PluginData import PluginData

if TYPE_CHECKING:
    from .ManifestInstance import ManifestInstance

_: TypeGetText


@dataclass
class ControllerPluginData(PluginData):
    _manifestInstancesById: dict[str, ManifestInstance]

    def __init__(self, name: str):
        super().__init__(name)
        self._manifestInstancesById = {}

    def __hash__(self) -> int:
        return id(self)

    def addManifestInstance(self, manifestInstance: ManifestInstance) -> None:
        """
        Add a manifest instance with unique ID to the plugin data.
        """
        self._manifestInstancesById[manifestInstance.id] = manifestInstance

    def getManifestInstances(self) -> list[ManifestInstance]:
        """
        Retrieve all loaded manifest instances.
        """
        return list(self._manifestInstancesById.values())

    def matchManifestInstance(self, ixdsDocUrls: list[str]) -> ManifestInstance | None:
        """
        Match a manifest instance based on the provided ixdsDocUrls.
        A one-to-one mapping must exist between the model's IXDS document URLs and the manifest instance's IXBRL files.
        :param ixdsDocUrls: A model's list of IXDS document URLs.
        :return: A matching ManifestInstance if found, otherwise None.
        """
        modelUrls = set(ixdsDocUrls)
        matchedInstance = None
        for instance in self._manifestInstancesById.values():
            if len(instance.ixbrlFiles) != len(ixdsDocUrls):
                continue
            manifestUrls = {str(path) for path in instance.ixbrlFiles}
            unmatchedModelUrls = set(modelUrls)
            unmatchedManifestUrls = set(manifestUrls)
            for modelUrl in modelUrls:
                if modelUrl not in unmatchedModelUrls:
                    continue
                for manifestUrl in manifestUrls:
                    if modelUrl.endswith(manifestUrl):
                        unmatchedModelUrls.remove(modelUrl)
                        unmatchedManifestUrls.remove(manifestUrl)
                        break
            if len(unmatchedModelUrls) > 0:
                continue
            if len(unmatchedManifestUrls) > 0:
                continue
            matchedInstance = instance
            break
        return matchedInstance

    @staticmethod
    def get(cntlr: Cntlr, name: str) -> ControllerPluginData:
        controllerPluginData = cntlr.getPluginData(name)
        if controllerPluginData is None:
            controllerPluginData = ControllerPluginData(name)
            cntlr.setPluginData(controllerPluginData)
        assert isinstance(controllerPluginData, ControllerPluginData), "Expected ControllerPluginData instance."
        return controllerPluginData
