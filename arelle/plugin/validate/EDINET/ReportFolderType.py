"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from enum import Enum
from functools import cached_property, lru_cache
from pathlib import Path

from regex import Pattern

from . import Constants


class ReportFolderType(Enum):
    ATTACH_DOC = "AttachDoc"
    AUDIT_DOC = "AuditDoc"
    PRIVATE_ATTACH = "PrivateAttach"
    PRIVATE_DOC = "PrivateDoc"
    PUBLIC_DOC = "PublicDoc"

    @classmethod
    def parse(cls, value: str) -> ReportFolderType | None:
        try:
            return cls(value)
        except ValueError:
            return None

    @cached_property
    def extensionCategory(self) -> ExtensionCategory | None:
        return FORM_TYPE_EXTENSION_CATEGORIES.get(self, None)

    @cached_property
    def isAttachment(self) -> bool:
        return "Attach" in self.value

    @cached_property
    def ixbrlFilenamePatterns(self) -> list[Pattern[str]]:
        return IXBRL_FILENAME_PATTERNS.get(self, [])

    @cached_property
    def manifestName(self) -> str:
        return f'manifest_{self.value}.xml'

    @cached_property
    def manifestPath(self) -> Path:
        return self.xbrlDirectory / self.manifestName

    @cached_property
    def namespaceUriPatterns(self) -> list[Pattern[str]]:
        return NAMESPACE_URI_PATTERNS.get(self, [])

    @cached_property
    def prefixPatterns(self) -> list[Pattern[str]]:
        return PREFIX_PATTERNS.get(self, [])

    @cached_property
    def xbrlDirectory(self) -> Path:
        return Path('XBRL') / str(self.value)

    @cached_property
    def xbrlFilenamePatterns(self) -> list[Pattern[str]]:
        return XBRL_FILENAME_PATTERNS.get(self, [])

    @lru_cache(1)
    def getValidExtensions(self, isAmendment: bool, isSubdirectory: bool) -> frozenset[str] | None:
        if self.extensionCategory is None:
            return None
        return self.extensionCategory.getValidExtensions(isAmendment, isSubdirectory)


class ExtensionCategory(Enum):
    ATTACH = 'ATTACH'
    DOC = 'DOC'

    def getValidExtensions(self, isAmendment: bool, isSubdirectory: bool) -> frozenset[str] | None:
        amendmentMap = VALID_EXTENSIONS[isAmendment]
        categoryMap = amendmentMap.get(self, None)
        if categoryMap is None:
            return None
        return categoryMap.get(isSubdirectory, None)


FORM_TYPE_EXTENSION_CATEGORIES = {
    ReportFolderType.ATTACH_DOC: ExtensionCategory.ATTACH,
    ReportFolderType.AUDIT_DOC: ExtensionCategory.DOC,
    ReportFolderType.PRIVATE_ATTACH: ExtensionCategory.ATTACH,
    ReportFolderType.PRIVATE_DOC: ExtensionCategory.DOC,
    ReportFolderType.PUBLIC_DOC: ExtensionCategory.DOC,
}


HTML_EXTENSIONS = frozenset({'.htm', '.html', '.xhtml'})
IMAGE_EXTENSIONS = frozenset({'.jpeg', '.jpg', '.gif', '.png'})
ASSET_EXTENSIONS = frozenset(HTML_EXTENSIONS | IMAGE_EXTENSIONS)
XBRL_EXTENSIONS = frozenset(HTML_EXTENSIONS | {'.xml', '.xsd'})
ATTACH_EXTENSIONS = frozenset(HTML_EXTENSIONS | {'.pdf', })

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
    },
}

IXBRL_FILENAME_PATTERNS = {
    ReportFolderType.AUDIT_DOC: [
        Constants.AUDIT_IXBRL_FILENAME_PATTERN,
        Constants.AUDIT_LINKBASE_FILENAME_PATTERN,
        Constants.AUDIT_SCHEMA_FILENAME_PATTERN,
    ],
    ReportFolderType.PUBLIC_DOC: [
        Constants.REPORT_COVER_FILENAME_PATTERN,
        Constants.REPORT_IXBRL_FILENAME_PATTERN,
        Constants.REPORT_LINKBASE_FILENAME_PATTERN,
        Constants.REPORT_SCHEMA_FILENAME_PATTERN,
    ]
}

NAMESPACE_URI_PATTERNS = {
    ReportFolderType.AUDIT_DOC: [
        Constants.AUDIT_NAMESPACE_PATTERN,
    ],
    ReportFolderType.PUBLIC_DOC: [
        Constants.REPORT_NAMESPACE_PATTERN,
    ],
}

PREFIX_PATTERNS = {
    ReportFolderType.AUDIT_DOC: [
        Constants.AUDIT_PREFIX_PATTERN,
    ],
    ReportFolderType.PUBLIC_DOC: [
        Constants.REPORT_PREFIX_PATTERN,
    ],
}

XBRL_FILENAME_PATTERNS = {
    ReportFolderType.AUDIT_DOC: [
        Constants.AUDIT_XBRL_FILENAME_PATTERN,
    ],
    ReportFolderType.PUBLIC_DOC: [
        Constants.REPORT_XBRL_FILENAME_PATTERN,
    ],
}
