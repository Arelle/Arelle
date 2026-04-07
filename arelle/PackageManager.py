"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any, IO, TYPE_CHECKING

from lxml import etree

from arelle.packages._package_manager import PackageManager

if TYPE_CHECKING:
    from arelle.Cntlr import Cntlr
    from arelle.FileSource import FileSource


# ---------------------------------------------------------------------------
# Backward-compatible module-level API
#
# These wrappers delegate to a module-level PackageManager singleton so that
# existing callers (e.g. ``from arelle.PackageManager import isMappedUrl``)
# continue to work without modification.
# ---------------------------------------------------------------------------


_singleton: PackageManager = PackageManager()


def getInstance() -> PackageManager:
    return _singleton


_SINGLETON_ATTRS = frozenset({
    "packagesJsonFile", "packagesConfig", "packagesConfigChanged",
    "packagesMappings", "_cntlr",
})


def __getattr__(name: str) -> Any:
    if name in _SINGLETON_ATTRS:
        return getattr(_singleton, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def baseForElement(element: etree._Element) -> str:
    return PackageManager.baseForElement(element)


def xmlLang(element: etree._Element) -> str:
    return PackageManager.xmlLang(element)


def langCloseness(l1: str, l2: str) -> int:
    return PackageManager.langCloseness(l1, l2)


def _parseFile(
    cntlr: Cntlr,
    parser: etree.XMLParser,
    filepath: str,
    file: IO[Any],
    schemaUrl: str,
) -> etree._ElementTree:
    return PackageManager.parseFile(
        cntlr,
        parser,
        filepath,
        file,
        schemaUrl,
    )


def parsePackage(
    cntlr: Cntlr,
    filesource: FileSource,
    metadataFile: str,
    fileBase: str,
    errors: list[str] | None = None,
) -> dict[str, str | dict[str, str]]:
    return PackageManager.parsePackage(
        cntlr,
        filesource,
        metadataFile,
        fileBase,
        errors,
    )


def _parsePackageMetadata(
    cntlr: Cntlr,
    filesource: FileSource,
    parser: etree.XMLParser,
    metadataFile: str,
    remappings: dict[str, str],
    errors: list[str],
) -> dict[str, str | dict[str, str]]:
    return PackageManager.parsePackageMetadata(
        cntlr,
        filesource,
        parser,
        metadataFile,
        remappings,
        errors,
    )


def _parseCatalog(
    cntlr: Cntlr,
    filesource: FileSource,
    parser: etree.XMLParser,
    catalogFile: str,
    fileBase: str,
    errors: list[str],
) -> dict[str, str]:
    return PackageManager.parseCatalog(
        cntlr,
        filesource,
        parser,
        catalogFile,
        fileBase,
        errors,
    )


def init(cntlr: Cntlr, loadPackagesConfig: bool = True) -> None:
    return getInstance().init(cntlr, loadPackagesConfig)


def reset() -> None:
    return getInstance().reset()


def orderedPackagesConfig() -> dict[str, Any]:
    return getInstance().orderedPackagesConfig()


def save(cntlr: Cntlr) -> None:
    return getInstance().save(cntlr)


def close() -> None:
    return getInstance().close()


def packageNamesWithNewerFileDates() -> set[str]:
    return getInstance().packageNamesWithNewerFileDates()


def validateTaxonomyPackage(
    cntlr: Cntlr,
    filesource: FileSource,
    errors: list[str] | None = None,
) -> bool:
    return PackageManager.validateTaxonomyPackage(cntlr, filesource, errors)


def discoverPackageFiles(filesource: FileSource) -> list[str]:
    return PackageManager.discoverPackageFiles(filesource)


def packageInfo(
    cntlr: Cntlr,
    URL: str,
    reload: bool = False,
    packageManifestName: str | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any] | None:
    return getInstance().packageInfo(
        cntlr,
        URL,
        reload,
        packageManifestName,
        errors,
    )


def rebuildRemappings(cntlr: Cntlr) -> None:
    return getInstance().rebuildRemappings(cntlr)


def isMappedUrl(url: str | None) -> bool:
    return getInstance().isMappedUrl(url)


def mappedUrl(url: str | None) -> str | None:
    return getInstance().mappedUrl(url)


def addPackage(
    cntlr: Cntlr,
    url: str,
    packageManifestName: str | None = None,
) -> dict[str, Any] | None:
    return getInstance().addPackage(
        cntlr,
        url,
        packageManifestName,
    )


def reloadPackageModule(cntlr: Cntlr, name: str) -> bool:
    return getInstance().reloadPackageModule(cntlr, name)


def removePackageModule(cntlr: Cntlr, name: str) -> bool:
    return getInstance().removePackageModule(cntlr, name)
