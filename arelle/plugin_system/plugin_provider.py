"""
See COPYRIGHT.md for copyright information.
"""
from typing import Iterator, Callable, Any

from arelle.plugin_system._plugin_manager import PluginManager
from arelle.plugin_system.plugin_handle import PluginHandle


class PluginProvider:

    def __init__(self, plugin_manager: PluginManager) -> None:
        self._plugin_manager = plugin_manager

    @staticmethod
    def _parse_module_info(module_info: dict[str, Any]) -> PluginHandle:
        return PluginHandle(
            aliases=frozenset(module_info.get("aliases", set())),
            author=str(module_info.get("author", "")),
            description=str(module_info.get("description", "")),
            entry_point=dict(module_info.get("entryPoint", {})).copy(),
            file_date=str(module_info.get("fileDate", "")),
            hook_names=frozenset(module_info.get("classMethods", set())),
            import_urls=frozenset(module_info.get("importURLs", set())),
            imports=tuple(
                PluginProvider._parse_module_info(i)
                for i in module_info.get("imports", [])
            ),
            is_imported=bool(module_info.get("isImported")),
            license=str(module_info.get("license", "")),
            module_imports=frozenset(module_info.get("moduleImports", set())),
            module_url=str(module_info.get("moduleURL", "")),
            name=str(module_info.get("name", "")),
            path=str(module_info.get("path", "")),
            status=str(module_info.get("status", "")),
            version=str(module_info.get("version", "")),
        )

    def hooks(self, hook_name: str) -> Iterator[Callable[..., Any]]:
        yield from self._plugin_manager.pluginClassMethods(hook_name)

    def get_plugin_handles(self) -> dict[str, PluginHandle]:
        plugin_infos = {}
        for name, module_info in self._plugin_manager.pluginConfig.get("modules", {}).items():
            plugin_infos[name] = PluginProvider._parse_module_info(module_info)
        return plugin_infos
