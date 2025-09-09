"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import zipfile
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from arelle.Cntlr import Cntlr
from arelle.FileSource import FileSource
from arelle.typing import TypeGetText
from arelle.utils.PluginData import PluginData
from . import Constants
from .ReportFolderType import ReportFolderType
from .UploadContents import UploadContents, UploadPathInfo

if TYPE_CHECKING:
    from .ManifestInstance import ManifestInstance

_: TypeGetText


@dataclass
class ControllerPluginData(PluginData):
    _manifestInstancesById: dict[str, ManifestInstance]
    _usedFilepaths: set[Path]

    def __init__(self, name: str):
        super().__init__(name)
        self._manifestInstancesById = {}
        self._usedFilepaths = set()

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

    @lru_cache(1)
    def getUploadContents(self, fileSource: FileSource) -> UploadContents:
        uploadFilepaths = self.getUploadFilepaths(fileSource)
        reports = defaultdict(list)
        uploadPaths = {}
        for path in uploadFilepaths:
            if len(path.parts) == 0:
                continue
            parents = list(reversed([p.name for p in path.parents if len(p.name) > 0]))
            reportFolderType = None
            isCorrection = True
            isDirectory = len(path.suffix) == 0
            isInSubdirectory = False
            reportPath = None
            if len(parents) > 0:
                isCorrection = parents[0] != 'XBRL'
                if not isCorrection:
                    if len(parents) > 1:
                        formName = parents[1]
                        isInSubdirectory = len(parents) > 2
                        reportFolderType = ReportFolderType.parse(formName)
                if reportFolderType is None:
                    formName = parents[0]
                    isInSubdirectory = len(parents) > 1
                    reportFolderType = ReportFolderType.parse(formName)
                if reportFolderType is not None:
                    reportPath = Path(reportFolderType.value) if isCorrection else Path("XBRL") / reportFolderType.value
                    if not isCorrection:
                        reports[reportFolderType].append(path)
            uploadPaths[path] = UploadPathInfo(
                isAttachment=reportFolderType is not None and reportFolderType.isAttachment,
                isCorrection=isCorrection,
                isCoverPage=not isDirectory and path.stem.startswith(Constants.COVER_PAGE_FILENAME_PREFIX),
                isDirectory=len(path.suffix) == 0,
                isRoot=len(path.parts) == 1,
                isSubdirectory=isInSubdirectory or (isDirectory and reportFolderType is not None),
                path=path,
                reportFolderType=reportFolderType,
                reportPath=reportPath,
            )
        return UploadContents(
            reports={k: frozenset(v) for k, v in reports.items() if len(v) > 0},
            uploadPaths=uploadPaths
        )

    @lru_cache(1)
    def getUploadFilepaths(self, fileSource: FileSource) -> list[Path]:
        if not self.isUpload(fileSource):
            return []
        paths = set()
        assert isinstance(fileSource.fs, zipfile.ZipFile)
        for name in fileSource.fs.namelist():
            path = Path(name)
            paths.add(path)
            paths.update(path.parents)
        return sorted(paths)

    @lru_cache(1)
    def getUploadFileSizes(self, fileSource: FileSource) -> dict[Path, int]:
        """
        Get the sizes of files in the upload directory.
        :param fileSource: The FileSource instance to get file sizes for.
        :return: A dictionary mapping file paths to their sizes.
        """
        if not self.isUpload(fileSource):
            return {}
        assert isinstance(fileSource.fs, zipfile.ZipFile)
        return {
            Path(i.filename): i.file_size
            for i in fileSource.fs.infolist()
            if not i.is_dir()
        }

    def getUsedFilepaths(self) -> frozenset[Path]:
        return frozenset(self._usedFilepaths)

    @lru_cache(1)
    def isUpload(self, fileSource: FileSource) -> bool:
        fileSource.open()  # Make sure file source is open
        if (fileSource.fs is None or
                not isinstance(fileSource.fs, zipfile.ZipFile)):
            if fileSource.cntlr is not None:
                fileSource.cntlr.error(
                    level="WARNING",
                    codes="EDINET.uploadNotValidated",
                    msg=_("The target file is not a zip file, so upload validation could not be performed.")
                )
            return False
        return True

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

    def addUsedFilepath(self, path: Path) -> None:
        self._usedFilepaths.add(path)

    @staticmethod
    def get(cntlr: Cntlr, name: str) -> ControllerPluginData:
        controllerPluginData = cntlr.getPluginData(name)
        if controllerPluginData is None:
            controllerPluginData = ControllerPluginData(name)
            cntlr.setPluginData(controllerPluginData)
        assert isinstance(controllerPluginData, ControllerPluginData), "Expected ControllerPluginData instance."
        return controllerPluginData
