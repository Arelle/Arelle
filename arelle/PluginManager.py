"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from importlib.metadata import EntryPoint
from pathlib import Path
from typing import TYPE_CHECKING, Any

from arelle.plugin_system._plugin_manager import PluginManager

if TYPE_CHECKING:
    # Prevent potential circular import error
    from arelle.Cntlr import Cntlr


# ---------------------------------------------------------------------------
# Backward-compatible module-level API
#
# These wrappers delegate to a module-level PluginManager singleton so that
# existing callers (e.g. ``from arelle.PluginManager import pluginClassMethods``)
# continue to work without modification.
# ---------------------------------------------------------------------------

_singleton: PluginManager = PluginManager()

def getInstance() -> PluginManager:
    return _singleton

_SINGLETON_ATTRS = frozenset({
    "pluginJsonFile", "pluginConfig", "pluginConfigChanged",
    "pluginTraceFileLogger", "modulePluginInfos", "pluginMethodsForClasses",
    "_cntlr", "_pluginBase",
    "_entryPointRefCache", "_entryPointRefAliasCache",
})


def __getattr__(name: str) -> Any:
    if name in _SINGLETON_ATTRS and _singleton is not None:
        return getattr(_singleton, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def init(cntlr: Cntlr, loadPluginConfig: bool = True) -> None:
    _singleton.init(cntlr, loadPluginConfig)


def reset() -> None:
    if _singleton is not None:
        _singleton.reset()


def orderedPluginConfig() -> dict[str, Any]:
    assert _singleton is not None
    return _singleton.orderedPluginConfig()


def save(cntlr: Cntlr) -> None:
    assert _singleton is not None
    _singleton.save(cntlr)


def close() -> None:
    if _singleton is not None:
        _singleton.close()


def logPluginTrace(message: str, level: int) -> None:
    if _singleton is None:
        logging.log(level, message)
        return
    _singleton.logPluginTrace(message, level)


def modulesWithNewerFileDates() -> set[str]:
    assert _singleton is not None
    return _singleton.modulesWithNewerFileDates()


def freshenModuleInfos() -> None:
    assert _singleton is not None
    _singleton.freshenModuleInfos()


def normalizeModuleFilename(moduleFilename: str) -> str | None:
    return PluginManager.normalizeModuleFilename(moduleFilename)


def getModuleFilename(moduleURL: str, reload: bool, normalize: bool, base: str | None) -> tuple[str | None, EntryPoint | None]:
    assert _singleton is not None
    return _singleton.getModuleFilename(moduleURL, reload, normalize, base)


def parsePluginInfo(moduleURL: str, moduleFilename: str, entryPoint: EntryPoint | None) -> dict[str, Any] | None:
    assert _singleton is not None
    return _singleton.parsePluginInfo(moduleURL, moduleFilename, entryPoint)


def moduleModuleInfo(
        moduleURL: str | None = None,
        entryPoint: EntryPoint | None = None,
        reload: bool = False,
        parentImportsSubtree: bool = False) -> dict[str, Any] | None:
    assert _singleton is not None
    return _singleton.moduleModuleInfo(moduleURL=moduleURL, entryPoint=entryPoint, reload=reload, parentImportsSubtree=parentImportsSubtree)


def moduleInfo(pluginInfo: Any) -> None:
    PluginManager.moduleInfo(pluginInfo)


def pluginClassMethods(className: str) -> Iterator[Callable[..., Any]]:
    assert _singleton is not None
    yield from _singleton.pluginClassMethods(className)


def hasPluginWithHook(name: str) -> bool:
    if _singleton is not None:
        return _singleton.hasPluginWithHook(name)
    return False


def addPluginModule(name: str) -> dict[str, Any] | None:
    assert _singleton is not None
    return _singleton.addPluginModule(name)


def reloadPluginModule(name: str) -> bool:
    assert _singleton is not None
    return _singleton.reloadPluginModule(name)


def removePluginModule(name: str) -> bool:
    assert _singleton is not None
    return _singleton.removePluginModule(name)


def addPluginModuleInfo(plugin_module_info: dict[str, Any] | None) -> dict[str, Any] | None:
    assert _singleton is not None
    return _singleton.addPluginModuleInfo(plugin_module_info)


def loadModule(moduleInfo: dict[str, Any], packagePrefix: str = "") -> None:
    assert _singleton is not None
    _singleton.loadModule(moduleInfo, packagePrefix)


def _get_name_dir_prefix(modulePath: Path, packagePrefix: str = "") -> tuple[str | None, str | None, str | None]:
    return PluginManager._get_name_dir_prefix(modulePath, packagePrefix)
