"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import zipfile
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache, cached_property
from pathlib import Path

from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginData import PluginData

_: TypeGetText


class FormType(Enum):
    ATTACH_DOC = "AttachDoc"
    AUDIT_DOC = "AuditDoc"
    ENGLISH_DOC = "EnglishDoc"
    PRIVATE_ATTACH = "PrivateAttach"
    PRIVATE_DOC = "PrivateDoc"
    PUBLIC_DOC = "PublicDoc"

    @classmethod
    def parse(cls, value: str) -> FormType | None:
        try:
            return cls(value)
        except ValueError:
            return None

    @cached_property
    def extensionCategory(self) -> ExtensionCategory | None:
        return FORM_TYPE_EXTENSION_CATEGORIES.get(self, None)

    @cached_property
    def manifestName(self) -> str:
        return f'manifest_{self.value}.xml'

    @cached_property
    def manifestPath(self) -> Path:
        return self.xbrlDirectory / self.manifestName

    @cached_property
    def xbrlDirectory(self) -> Path:
        return Path('XBRL') / str(self.value)

    @lru_cache(1)
    def getValidExtensions(self, isAmmendment: bool, isSubdirectory: bool) -> frozenset[str] | None:
        if self.extensionCategory is None:
            return None
        return self.extensionCategory.getValidExtensions(isAmmendment, isSubdirectory)


@dataclass(frozen=True)
class UploadContents:
    ammendmentPaths: dict[FormType, frozenset[Path]]
    directories: frozenset[Path]
    forms: dict[FormType, frozenset[Path]]
    unknownPaths: frozenset[Path]


class ExtensionCategory(Enum):
    ATTACH = 'ATTACH'
    DOC = 'DOC'
    ENGLISH_DOC = 'ENGLISH_DOC'

    def getValidExtensions(self, isAmmendment: bool, isSubdirectory: bool) -> frozenset[str] | None:
        ammendmentMap = VALID_EXTENSIONS[isAmmendment]
        categoryMap = ammendmentMap.get(self, None)
        if categoryMap is None:
            return None
        return categoryMap.get(isSubdirectory, None)


FORM_TYPE_EXTENSION_CATEGORIES = {
    FormType.ATTACH_DOC: ExtensionCategory.ATTACH,
    FormType.AUDIT_DOC: ExtensionCategory.DOC,
    FormType.ENGLISH_DOC: ExtensionCategory.ENGLISH_DOC,
    FormType.PRIVATE_ATTACH: ExtensionCategory.ATTACH,
    FormType.PRIVATE_DOC: ExtensionCategory.DOC,
    FormType.PUBLIC_DOC: ExtensionCategory.DOC,
}
HTML_EXTENSIONS = frozenset({'.htm', '.html', '.xhtml'})
IMAGE_EXTENSIONS = frozenset({'.jpeg', '.jpg', '.gif', '.png'})
ASSET_EXTENSIONS = frozenset(HTML_EXTENSIONS | IMAGE_EXTENSIONS)
XBRL_EXTENSIONS = frozenset(HTML_EXTENSIONS | {'.xml', '.xsd'})
ATTACH_EXTENSIONS = frozenset(HTML_EXTENSIONS | {'.pdf', })
ENGLISH_DOC_EXTENSIONS = frozenset(ASSET_EXTENSIONS | frozenset({'.pdf', '.xml', '.txt'}))


# Is Ammendment -> Category -> Is Subdirectory
VALID_EXTENSIONS = {
    False: {
        ExtensionCategory.ATTACH: {
            False: ATTACH_EXTENSIONS,
            True: ASSET_EXTENSIONS,
        },
        ExtensionCategory.DOC: {
            False: XBRL_EXTENSIONS,
            True: ASSET_EXTENSIONS
        },
    },
    True: {
        ExtensionCategory.ATTACH: {
            False: ATTACH_EXTENSIONS,
            True: ASSET_EXTENSIONS,
        },
        ExtensionCategory.DOC: {
            False: HTML_EXTENSIONS,
            True: ASSET_EXTENSIONS,
        },
        ExtensionCategory.ENGLISH_DOC: {
            False: ENGLISH_DOC_EXTENSIONS,
            True: ENGLISH_DOC_EXTENSIONS,
        },
    },
}


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
    def getUploadContents(self, modelXbrl: ModelXbrl) -> UploadContents:
        uploadFilepaths = self.getUploadFilepaths(modelXbrl)
        ammendmentPaths = defaultdict(list)
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
                ammendmentPaths[formType].append(path)
                continue
            if len(path.suffix) == 0:
                directories.append(path)
                continue
            unknownPaths.append(path)
        return UploadContents(
            ammendmentPaths={k: frozenset(v) for k, v in ammendmentPaths.items() if len(v) > 0},
            directories=frozenset(directories),
            forms={k: frozenset(v) for k, v in forms.items() if len(v) > 0},
            unknownPaths=frozenset(unknownPaths)
        )

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
