"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import zipfile
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginData import PluginData
from .FormType import FormType

_: TypeGetText


@dataclass(frozen=True)
class UploadContents:
    amendmentPaths: dict[FormType, frozenset[Path]]
    directories: frozenset[Path]
    forms: dict[FormType, frozenset[Path]]
    unknownPaths: frozenset[Path]


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

    def getUploadFileSizes(self, modelXbrl: ModelXbrl) -> dict[Path, int]:
        """
        Get the sizes of files in the upload directory.
        :param modelXbrl: The ModelXbrl instance to get file sizes for.
        :return: A dictionary mapping file paths to their sizes.
        """
        if not self.isUpload(modelXbrl):
            return {}
        assert isinstance(modelXbrl.fileSource.fs, zipfile.ZipFile)
        return {
            Path(i.filename): i.file_size
            for i in modelXbrl.fileSource.fs.infolist()
            if not i.is_dir()
        }

    @lru_cache(1)
    def getUploadContents(self, modelXbrl: ModelXbrl) -> UploadContents:
        uploadFilepaths = self.getUploadFilepaths(modelXbrl)
        amendmentPaths = defaultdict(list)
        unknownPaths = []
        directories = []
        forms = defaultdict(list)
        for path in uploadFilepaths:
            parents = list(reversed([p.name for p in path.parents if len(p.name) > 0]))
            if len(parents) == 0:
                continue
            if parents[0] == 'XBRL':
                if len(parents) > 1:
                    formName = parents[1]
                    formType = FormType.parse(formName)
                    if formType is not None:
                        forms[formType].append(path)
                        continue
            formName = parents[0]
            formType = FormType.parse(formName)
            if formType is not None:
                amendmentPaths[formType].append(path)
                continue
            if len(path.suffix) == 0:
                directories.append(path)
                continue
            unknownPaths.append(path)
        return UploadContents(
            amendmentPaths={k: frozenset(v) for k, v in amendmentPaths.items() if len(v) > 0},
            directories=frozenset(directories),
            forms={k: frozenset(v) for k, v in forms.items() if len(v) > 0},
            unknownPaths=frozenset(unknownPaths)
        )

    @lru_cache(1)
    def getUploadFilepaths(self, modelXbrl: ModelXbrl) -> list[Path]:
        if not self.isUpload(modelXbrl):
            return []
        paths = set()
        assert isinstance(modelXbrl.fileSource.fs, zipfile.ZipFile)
        for name in modelXbrl.fileSource.fs.namelist():
            path = Path(name)
            paths.add(path)
            paths.update(path.parents)
        return sorted(paths)

    @lru_cache(1)
    def isUpload(self, modelXbrl: ModelXbrl) -> bool:
        if not modelXbrl.fileSource.fs or \
                not isinstance(modelXbrl.fileSource.fs, zipfile.ZipFile):
            modelXbrl.warning(
                codes="EDINET.uploadNotValidated",
                msg=_("The target file is not a zip file, so upload validation could not be performed.")
            )
            return False
        return True

    def isStandardTaxonomyUrl(self, uri: str, modelXbrl: ModelXbrl) -> bool:
        return modelXbrl.modelManager.disclosureSystem.hrefValidForDisclosureSystem(uri)
