"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from multiprocessing.context import BaseContext
from types import ModuleType


def _loadPluginModules(pluginModuleLocationsByName: dict[str, str | None]) -> None:
    for pluginModuleName, pluginModuleLocation in pluginModuleLocationsByName.items():
        spec = importlib.util.spec_from_file_location(name=pluginModuleName, location=pluginModuleLocation)
        if spec is None or spec.loader is None:
            raise ModuleNotFoundError(f"Unable to import plugin module '{pluginModuleName}' from {pluginModuleLocation} in plugin subprocess.")
        module = importlib.util.module_from_spec(spec)
        sys.modules[pluginModuleName] = module
        spec.loader.exec_module(module)


class PluginProcessPoolExecutor(ProcessPoolExecutor):
    """
    Wrapper class for ProcessPoolExecutor which loads a plugin module before
    executing any other code. This is necessary for dynamically loaded Arelle
    plugins, as any functions defined within plugin modules are not imported
    by newly spawned processes.
    """

    def __init__(
            self,
            pluginModules: Sequence[ModuleType] | ModuleType,
            maxWorkers: int | None = None,
            mpContext: BaseContext | None = None,
    ) -> None:
        if getattr(sys, 'frozen', False):
            # Revisit this when cx_Freeze is upgraded to 6.16
            # https://github.com/marcelotduarte/cx_Freeze/pull/1956
            raise RuntimeError("Multiprocessing plugins aren't supported in frozen builds. Run Arelle from source.")
        modules = pluginModules if isinstance(pluginModules, Sequence) else [pluginModules]
        pluginModuleLocationsByName = {}
        for pluginModule in modules:
            pluginModuleSpec = pluginModule.__spec__
            if pluginModuleSpec is None:
                raise ValueError(f"Unable to create PluginProcessPoolExecutor for plugin '{pluginModule.__name__}' without ModuleSpec.")
            pluginModuleLocationsByName[pluginModuleSpec.name] = pluginModuleSpec.origin
        super().__init__(
            initializer=_loadPluginModules,
            initargs=(pluginModuleLocationsByName,),
            max_workers=maxWorkers,
            mp_context=mpContext,
        )
