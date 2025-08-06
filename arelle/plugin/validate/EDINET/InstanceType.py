"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from enum import Enum
from functools import cached_property, lru_cache
from pathlib import Path


class InstanceType(Enum):
    ATTACH_DOC = "AttachDoc"
    AUDIT_DOC = "AuditDoc"
    ENGLISH_DOC = "EnglishDoc"
    PRIVATE_ATTACH = "PrivateAttach"
    PRIVATE_DOC = "PrivateDoc"
    PUBLIC_DOC = "PublicDoc"

    @classmethod
    def parse(cls, value: str) -> InstanceType | None:
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
    def getValidExtensions(self, isAmendment: bool, isSubdirectory: bool) -> frozenset[str] | None:
        if self.extensionCategory is None:
            return None
        return self.extensionCategory.getValidExtensions(isAmendment, isSubdirectory)


class ExtensionCategory(Enum):
    ATTACH = 'ATTACH'
    DOC = 'DOC'
    ENGLISH_DOC = 'ENGLISH_DOC'

    def getValidExtensions(self, isAmendment: bool, isSubdirectory: bool) -> frozenset[str] | None:
        amendmentMap = VALID_EXTENSIONS[isAmendment]
        categoryMap = amendmentMap.get(self, None)
        if categoryMap is None:
            return None
        return categoryMap.get(isSubdirectory, None)


FORM_TYPE_EXTENSION_CATEGORIES = {
    InstanceType.ATTACH_DOC: ExtensionCategory.ATTACH,
    InstanceType.AUDIT_DOC: ExtensionCategory.DOC,
    InstanceType.ENGLISH_DOC: ExtensionCategory.ENGLISH_DOC,
    InstanceType.PRIVATE_ATTACH: ExtensionCategory.ATTACH,
    InstanceType.PRIVATE_DOC: ExtensionCategory.DOC,
    InstanceType.PUBLIC_DOC: ExtensionCategory.DOC,
}


HTML_EXTENSIONS = frozenset({'.htm', '.html', '.xhtml'})
IMAGE_EXTENSIONS = frozenset({'.jpeg', '.jpg', '.gif', '.png'})
ASSET_EXTENSIONS = frozenset(HTML_EXTENSIONS | IMAGE_EXTENSIONS)
XBRL_EXTENSIONS = frozenset(HTML_EXTENSIONS | {'.xml', '.xsd'})
ATTACH_EXTENSIONS = frozenset(HTML_EXTENSIONS | {'.pdf', })
ENGLISH_DOC_EXTENSIONS = frozenset(ASSET_EXTENSIONS | frozenset({'.pdf', '.xml', '.txt'}))

# Is Amendment -> Category -> Is Subdirectory
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
