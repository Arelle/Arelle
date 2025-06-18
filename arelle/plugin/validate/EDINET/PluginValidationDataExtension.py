"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from arelle.ModelXbrl import ModelXbrl
from arelle.utils.PluginData import PluginData


@dataclass
class PluginValidationDataExtension(PluginData):
    _primaryModelXbrl: ModelXbrl | None = None

    # Identity hash for caching.
    def __hash__(self) -> int:
        return id(self)

    @lru_cache(1)
    def getManifestDirectoryPaths(self, modelXbrl: ModelXbrl) -> list[Path]:
        """
        Get all paths and directories beneath the directory that the given
        model's manifest is located in.
        :param modelXbrl: The model loaded from a manifest document.
        :return: All paths and directories beneath the manifest directory.
        """
        manifestDir = Path(modelXbrl.uri).parent
        manifestPaths = set()
        if modelXbrl.fileSource.filesDir is not None:
            # For archives, retrieve paths from the file source.
            base = Path(modelXbrl.fileSource.basefile)
            for file in modelXbrl.fileSource.filesDir:
                path = base / file
                if manifestDir in path.parents:
                    manifestPaths.add(path)
        else:
            # For directories, glob paths from manifest directory.
            for file in manifestDir.rglob("*"):
                manifestPaths.add(file)
        manifestRelPaths = set()
        for path in manifestPaths:
            relPath = path.relative_to(manifestDir)
            manifestRelPaths.add(relPath)
            manifestRelPaths.update(relPath.parents)
        results = sorted(
            manifestDir / manifestRelPath
            for manifestRelPath in manifestRelPaths
        )
        return results
