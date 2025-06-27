"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginData import PluginData


@dataclass
class PluginValidationDataExtension(PluginData):
    _primaryModelXbrl: ModelXbrl | None = None

    # Identity hash for caching.
    def __hash__(self) -> int:
        return id(self)

    @lru_cache(1)
    def shouldValidateUpload(self, val: ValidateXbrl) -> bool:
        """
        Determine if the upload validation should be performed on this model.

        Upload validation should not be performed if the target document is
        not a zipfile.

        Upload validation should only be performed once for the entire package,
        not duplicated for each model. To facilitate this with Arelle's validation
        system which largely prevents referencing other models, we can use `--keepOpen`
        and check if the given model is the first to be loaded.
        :param val: The ValidateXbrl instance with a model to check.
        :return: True if upload validation should be performed, False otherwise.
        """
        modelXbrl = val.modelXbrl
        if modelXbrl == val.testModelXbrl:
            # Not running within a testcase
            if modelXbrl != modelXbrl.modelManager.loadedModelXbrls[0]:
                return False
        if not modelXbrl.fileSource.fs:
            return False  # No stream
        if not isinstance(modelXbrl.fileSource.fs, zipfile.ZipFile):
            return False  # Not a zipfile
        return True

    @lru_cache(1)
    def getUploadFilepaths(self, modelXbrl: ModelXbrl) -> list[Path]:
        if not modelXbrl.fileSource.fs or \
                not isinstance(modelXbrl.fileSource.fs, zipfile.ZipFile):
            modelXbrl.warning(
                codes="EDINET.uploadNotValidated",
                msg=_("The target file is not a zip file, so upload validation could not be performed.")
            )
            return []
        paths = set()
        for name in modelXbrl.fileSource.fs.namelist():
            path = Path(name)
            paths.add(path)
            paths.update(path.parents)
        return sorted(paths)
