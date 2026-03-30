"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from typing import TYPE_CHECKING, Any

from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.plugin_system._plugin_manager import PluginManager


_: TypeGetText


_entryPointRefSearchTermEndings = [
    '/__init__.py',
    '.py',
    '/',
]


@dataclass
class EntryPointRef:
    aliases: set[str]
    entryPoint: EntryPoint | None
    moduleFilename: str | None
    moduleInfo: dict[str, Any] | None

    def createModuleInfo(self, plugin_manager: PluginManager | None = None) -> dict[str, Any] | None:
        """
        Creates a module information dictionary from the entry point ref.
        :param plugin_manager: PluginManager instance. If not provided, uses the global PluginManager instance.
        :return: A module information dictionary
        """
        from arelle.PluginManager import getInstance
        pm = plugin_manager or getInstance()
        assert pm is not None
        if self.entryPoint is not None:
            return pm.moduleModuleInfo(entryPoint=self.entryPoint)
        return pm.moduleModuleInfo(moduleURL=self.moduleFilename)

    @staticmethod
    def fromEntryPoint(entryPoint: EntryPoint, plugin_manager: PluginManager | None = None) -> EntryPointRef | None:
        """
        Given an entry point, retrieves the subset of information from __pluginInfo__ necessary to
        determine if the entry point should be imported as a plugin.
        :param entryPoint:
        :param plugin_manager: PluginManager instance. If not provided, uses the global PluginManager instance.
        :return:
        """
        pluginUrlFunc = entryPoint.load()
        pluginUrl = pluginUrlFunc()
        return EntryPointRef.fromFilepath(pluginUrl, entryPoint, plugin_manager=plugin_manager)

    @staticmethod
    def fromFilepath(filepath: str, entryPoint: EntryPoint | None = None, plugin_manager: PluginManager | None = None) -> EntryPointRef | None:
        """
        Given a filepath, retrieves a subset of information from __pluginInfo__ necessary to
        determine if the entry point should be imported as a plugin.
        :param filepath: Path to plugin, can be a directory or .py filepath
        :param entryPoint: Optional entry point information to include in aliases/moduleInfo
        :param plugin_manager: PluginManager instance. If not provided, uses the global PluginManager instance.
        :return:
        """
        from arelle.PluginManager import getInstance
        pm = plugin_manager or getInstance()
        assert pm is not None
        moduleFilename = pm._cntlr.webCache.getfilename(filepath)
        if moduleFilename:
            moduleFilename = pm.normalizeModuleFilename(moduleFilename)
        aliases = set()
        if entryPoint:
            aliases.add(entryPoint.name)
        moduleInfo: dict[str, Any] | None = None
        if moduleFilename:
            moduleInfo = pm.parsePluginInfo(moduleFilename, moduleFilename, entryPoint)
            if moduleInfo is None:
                return None
            if "name" in moduleInfo:
                aliases.add(moduleInfo["name"])
            if "aliases" in moduleInfo:
                aliases |= set(moduleInfo["aliases"])
        return EntryPointRef(
            aliases={EntryPointRef._normalizePluginSearchTerm(a) for a in aliases},
            entryPoint=entryPoint,
            moduleFilename=moduleFilename,
            moduleInfo=moduleInfo,
        )

    @staticmethod
    def discoverAll(plugin_manager: PluginManager | None = None) -> list[EntryPointRef]:
        """
        Retrieve all plugin entry points, cached on first run.
        :param plugin_manager: PluginManager instance. If not provided, uses the global PluginManager instance.
        :return: List of all discovered entry points.
        """
        from arelle.PluginManager import getInstance
        pm = plugin_manager or getInstance()
        assert pm is not None
        if pm._entryPointRefCache is None:
            pm._entryPointRefCache = EntryPointRef._discoverBuiltIn([], pm._pluginBase, plugin_manager=pm) + EntryPointRef._discoverInstalled(plugin_manager=pm)
        return pm._entryPointRefCache

    @staticmethod
    def _discoverBuiltIn(entryPointRefs: list[EntryPointRef], directory: str, plugin_manager: PluginManager | None = None) -> list[EntryPointRef]:
        """
        Recursively retrieve all plugin entry points in the given directory.
        :param entryPointRefs: Working list of entry point refs to append to.
        :param directory: Directory to search for entry points within.
        :param plugin_manager: PluginManager instance. If not provided, uses the global PluginManager instance.
        :return: List of discovered entry points.
        """
        for fileName in sorted(os.listdir(directory)):
            if fileName in (".", "..", "__pycache__", "__init__.py", ".DS_Store", "site-packages"):
                continue  # Ignore these entries
            filePath = os.path.join(directory, fileName)
            if os.path.isdir(filePath):
                EntryPointRef._discoverBuiltIn(entryPointRefs, filePath, plugin_manager=plugin_manager)
            if os.path.isfile(filePath) and os.path.basename(filePath).endswith(".py"):
                # If `filePath` references .py file directly, use it
                moduleFilePath = filePath
            elif os.path.isdir(filePath) and os.path.exists(initFilePath := os.path.join(filePath, "__init__.py")):
                # Otherwise, if `filePath` is a directory containing `__init__.py`, use that
                moduleFilePath = initFilePath
            else:
                continue
            entryPointRef = EntryPointRef.fromFilepath(moduleFilePath, plugin_manager=plugin_manager)
            if entryPointRef is not None:
                entryPointRefs.append(entryPointRef)
        return entryPointRefs

    @staticmethod
    def _discoverInstalled(plugin_manager: PluginManager | None = None) -> list[EntryPointRef]:
        """
        Retrieve all installed plugin entry points.
        :param plugin_manager: PluginManager instance. If not provided, uses the global PluginManager instance.
        :return: List of all discovered entry points.
        """
        entryPoints = list(entry_points(group='arelle.plugin'))
        entryPointRefs = []
        for entryPoint in entryPoints:
            entryPointRef = EntryPointRef.fromEntryPoint(entryPoint, plugin_manager=plugin_manager)
            if entryPointRef is not None:
                entryPointRefs.append(entryPointRef)
        return entryPointRefs

    @staticmethod
    def get(search: str, plugin_manager: PluginManager | None = None) -> EntryPointRef | None:
        """
        Retrieve an entry point ref with a matching name or alias.
        May return None of no matches are found.
        Throws an exception if multiple entry point refs match the search term.
        :param search: Only retrieve entry point matching the given search text.
        :param plugin_manager: PluginManager instance. If not provided, uses the global PluginManager instance.
        :return: Matching entry point ref, if found.
        """
        entryPointRefs = EntryPointRef.search(search, plugin_manager=plugin_manager)
        if entryPointRefs is None:
            return None
        elif len(entryPointRefs) == 0:
            return None
        elif len(entryPointRefs) > 1:
            paths = [r.moduleFilename for r in entryPointRefs]
            raise Exception(_('Multiple entry points matched search term "{}": {}').format(search, paths))
        return entryPointRefs[0]

    @staticmethod
    def _normalizePluginSearchTerm(search: str) -> str:
        """
        Normalizes the given search term or searchable text by:
          Making slashes consistent
          Removing common endings
        :param search: Search term or searchable text
        :return: Normalized string
        """
        search = search.replace('\\', '/')
        while True:
            for ending in _entryPointRefSearchTermEndings:
                if search.endswith(ending):
                    search = search[:-len(ending)]
                    break
            return search.lower()

    @staticmethod
    def search(search: str, plugin_manager: PluginManager | None = None) -> list[EntryPointRef] | None:
        """
        Retrieve entry point module information matching provided search text.
        A map of aliases to matching entry points is cached on the first run.
        :param search: Only retrieve entry points matching the given search text.
        :param plugin_manager: PluginManager instance. If not provided, uses the global PluginManager instance.
        :return: List of matching module infos.
        """
        from arelle.PluginManager import getInstance
        pm = plugin_manager or getInstance()
        assert pm is not None
        if pm._entryPointRefAliasCache is None:
            entryPointRefAliasCache: dict[str, list[EntryPointRef]] = defaultdict(list)
            entryPointRefs = EntryPointRef.discoverAll(plugin_manager=pm)
            for entryPointRef in entryPointRefs:
                for alias in entryPointRef.aliases:
                    entryPointRefAliasCache[alias].append(entryPointRef)
            pm._entryPointRefAliasCache = entryPointRefAliasCache
        search = EntryPointRef._normalizePluginSearchTerm(search)
        return pm._entryPointRefAliasCache.get(search, [])
