"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from arelle.packages._package_manager import PackageManager
from arelle.packages.package_meta import PackageMeta


class PackageRegistry:

    def __init__(self, package_manager: PackageManager) -> None:
        self._package_manager = package_manager

    def add(
            self,
            url: str,
            manifest_name: str | None = None,
    ) -> PackageMeta | None:
        package_config = self._package_manager.addPackage(
            cntlr=None,
            url=url,
            packageManifestName=manifest_name
        )
        if package_config is None:
            return None
        return PackageMeta.from_config(package_config)

    def get_mappings(self) -> dict[str, str]:
        config = self._package_manager.orderedPackagesConfig()
        return {
            prefix: remapping
            for prefix, remapping in config.get("remappings", {}).items()
            if isinstance(prefix, str) and isinstance(remapping, str)
        }

    def get_packages(self) -> tuple[PackageMeta, ...]:
        config = self._package_manager.orderedPackagesConfig()
        package_configs = config.get("packages", [])
        return tuple(
            PackageMeta.from_config(package_config)
            for package_config in package_configs
        )

    def is_mapped(self, url: str | None) -> bool:
        return self._package_manager.isMappedUrl(url)

    def map(self, url: str | None) -> str | None:
        return self._package_manager.mappedUrl(url)

    def rebuild(self) -> None:
        return self._package_manager.rebuildRemappings()
