'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

import ast
import gettext
from glob import glob
import importlib.util
import json
import logging
import os
import sys
import time
import traceback
import types
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points, Distribution
from numbers import Number
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast, Union

import arelle.FileSource
from arelle.Locale import getLanguageCodes
from arelle.PythonUtil import isLegacyAbs
from arelle.typing import TypeGetText
from arelle.UrlUtil import isAbsolute

if TYPE_CHECKING:
    # Prevent potential circular import error
    from .Cntlr import Cntlr


_: TypeGetText

PLUGIN_TRACE_FILE: str | None = None
# PLUGIN_TRACE_FILE = "c:/temp/pluginerr.txt"
PLUGIN_TRACE_LEVEL = logging.WARNING

# plugin control is static to correspond to statically loaded modules
pluginJsonFile = None
pluginConfig: dict[str, Any] | None = None
pluginConfigChanged = False
pluginTraceFileLogger = None
modulePluginInfos: dict[str, Any] = {}
pluginMethodsForClasses: dict[str, Any] = {}
_cntlr: Cntlr | None = None
_pluginBase = None
EMPTYLIST: list[Any] = []
_ERROR_MESSAGE_IMPORT_TEMPLATE = "Unable to load module {}"


def _getPluginConfig() -> dict[str, Any]:
    assert pluginConfig is not None, "PluginManager.init() must be called before use"
    return pluginConfig


def _getCntlr() -> Cntlr:
    assert _cntlr is not None, "PluginManager.init() must be called before use"
    return _cntlr



class PluginManager:

    def __init__(self, cntlr: Cntlr, loadPluginConfig: bool = True) -> None:
        global pluginJsonFile, pluginConfig, pluginTraceFileLogger, modulePluginInfos, pluginMethodsForClasses, pluginConfigChanged, _cntlr, _pluginBase
        if PLUGIN_TRACE_FILE:
            pluginTraceFileLogger = logging.getLogger(__name__)
            pluginTraceFileLogger.propagate = False
            handler = logging.FileHandler(PLUGIN_TRACE_FILE)
            formatter = logging.Formatter('%(asctime)s.%(msecs)03dz [%(levelname)s] %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')
            handler.setFormatter(formatter)
            handler.setLevel(PLUGIN_TRACE_LEVEL)
            pluginTraceFileLogger.addHandler(handler)
        pluginConfigChanged = False
        _cntlr = cntlr
        _pluginBase = cntlr.pluginDir + os.sep
        if loadPluginConfig:
            try:
                pluginJsonFile = cntlr.userAppDir + os.sep + "plugins.json"
                with open(pluginJsonFile, encoding='utf-8') as f:
                    pluginConfig = json.load(f)
                self.freshenModuleInfos()
            except Exception:
                pass # on GAE no userAppDir, will always come here
        if not pluginConfig:
            pluginConfig = {  # savable/reloadable plug in configuration
                "modules": {}, # dict of moduleInfos by module name
                "classes": {}  # dict by class name of list of class modules in execution order
            }
            pluginConfigChanged = False # don't save until something is added to pluginConfig
        modulePluginInfos = {}  # dict of loaded module pluginInfo objects by module names
        pluginMethodsForClasses = {} # dict by class of list of ordered callable function objects

    def reset(self) -> None:  # force reloading modules and plugin infos
        if modulePluginInfos:
            modulePluginInfos.clear()  # dict of loaded module pluginInfo objects by module names
        if pluginMethodsForClasses:
            pluginMethodsForClasses.clear() # dict by class of list of ordered callable function objects

    def orderedPluginConfig(self) -> dict[str, Any]:
        fieldOrder: list[str] = [
            'name',
            'status',
            'fileDate',
            'version',
            'description',
            'moduleURL',
            'localeURL',
            'localeDomain',
            'license',
            'author',
            'copyright',
            'classMethods',
        ]
        priorityIndex = {k: i for i, k in enumerate(fieldOrder)}

        def sortModuleInfo(moduleInfo: dict[str, Any]) -> dict[str, Any]:
            # Prioritize known fields by the index in fieldOrder; sort others alphabetically
            orderedKeys = sorted(
                moduleInfo.keys(),
                key=lambda k: (priorityIndex.get(k, len(priorityIndex)), k)
            )
            return {k: moduleInfo[k] for k in orderedKeys}

        _pluginConfig = _getPluginConfig()
        orderedModules = {
            moduleName: sortModuleInfo(_pluginConfig['modules'][moduleName])
            for moduleName in sorted(_pluginConfig['modules'].keys())
        }

        return {
            'modules': orderedModules,
            'classes': dict(sorted(_pluginConfig['classes'].items()))
        }

    def save(self, cntlr: Cntlr) -> None:
        global pluginConfigChanged
        if pluginConfigChanged and cntlr.hasFileSystem and not cntlr.disablePersistentConfig:
            pluginJsonFile = cntlr.userAppDir + os.sep + "plugins.json"
            with open(pluginJsonFile, 'w', encoding='utf-8') as f:
                jsonStr = str(json.dumps(self.orderedPluginConfig(), ensure_ascii=False, indent=2)) # might not be unicode in 2.7
                f.write(jsonStr)
            pluginConfigChanged = False

    def close(self) -> None:  # close all loaded methods
        if pluginConfig is not None:
            pluginConfig.clear()
        if modulePluginInfos is not None:
            modulePluginInfos.clear()
        if pluginMethodsForClasses is not None:
            pluginMethodsForClasses.clear()

    ''' pluginInfo structure:

    __pluginInfo__ = {
        'name': (required)
        'version': (required)
        'description': (optional)
        'moduleURL': (required) # added by plug in manager, not in source file
        'localeURL': (optional) # L10N internationalization for this module (subdirectory if relative)
        'localeDomain': (optional) # domain for L10N internationalization (e.g., 'arelle')
        'license': (optional)
        'author': (optional)
        'copyright': (optional)
        # classes of mount points (required)
        'a.b.c': method (function) to do something
        'a.b.c.d' : method (function) to do something
        # import (plugins to be loaded for this package) (may be multiple imports like in python)
        'import': [string, list or tuple of URLs or relative file names of imported plug-ins]
    }

    moduleInfo = {
        'name': (required)
        'status': enabled | disabled
        'version': (required)
        'fileDate': 2000-01-01
        'description': (optional)
        'moduleURL': (required) # same as file path, can be a URL (of a non-package .py file or a package directory)
        'localeURL': (optional) # for L10N internationalization within module
        'localeDomain': (optional) # domain for L10N internationalization
        'license': (optional)
        'author': (optional)
        'copyright': (optional)
        'classMethods': [list of class names that have methods in module]
        'imports': [list of imported plug-in moduleInfos]
        'isImported': True if module was imported by a parent plug-in module
    }


    '''

    def logPluginTrace(self, message: str, level: int) -> None:
        """
        If plugin trace file logging is configured, logs `message` to it.
        Only logs to controller logger if log is an error.
        :param message: Message to be logged
        :param level: Log level of message (e.g. logging.INFO)
        """
        if pluginTraceFileLogger:
            pluginTraceFileLogger.log(level, message)
        if level >= logging.ERROR:
            _getCntlr().addToLog(message=message, level=level, messageCode='arelle:pluginLoadingError')


    def modulesWithNewerFileDates(self) -> set[str]:
        names = set()
        for moduleName, moduleInfo in _getPluginConfig()["modules"].items():
            freshenedFilename = _getCntlr().webCache.getfilename(moduleInfo["moduleURL"], checkModifiedTime=True, normalize=True, base=_pluginBase)
            if freshenedFilename is None:
                _msg = _("Module URL could not be mapped to a filepath: {moduleURL}").format(moduleURL=moduleInfo["moduleURL"])
                self.logPluginTrace(_msg, logging.ERROR)
                continue
            try:
                if os.path.isdir(freshenedFilename): # if freshenedFilename is a directory containing an __init__.py file, open that instead
                    if os.path.isfile(os.path.join(freshenedFilename, "__init__.py")):
                        freshenedFilename = os.path.join(freshenedFilename, "__init__.py")
                elif not freshenedFilename.endswith(".py") and not os.path.exists(freshenedFilename) and os.path.exists(freshenedFilename + ".py"):
                    freshenedFilename += ".py" # extension module without .py suffix
                if os.path.exists(freshenedFilename):
                    if moduleInfo["fileDate"] < time.strftime('%Y-%m-%dT%H:%M:%S UTC', time.gmtime(os.path.getmtime(freshenedFilename))):
                        names.add(moduleInfo["name"])
                else:
                    _msg = _("File not found for '{name}' plug-in when checking for updated module info. Path: '{path}'") \
                        .format(name=moduleName, path=freshenedFilename)
                    self.logPluginTrace(_msg, logging.ERROR)
            except Exception as err:
                _msg = _("Exception at plug-in method modulesWithNewerFileDates: {error}").format(error=err)
                self.logPluginTrace(_msg, logging.ERROR)

        return names

    def freshenModuleInfos(self) -> None:
        # for modules with different date-times, re-load module info
        missingEnabledModules = []
        _pluginConfig = _getPluginConfig()
        for moduleName, moduleInfo in _pluginConfig["modules"].items():
            moduleEnabled = moduleInfo["status"] == "enabled"
            freshenedFilename = _getCntlr().webCache.getfilename(moduleInfo["moduleURL"], checkModifiedTime=True, normalize=True, base=_pluginBase)
            if freshenedFilename is None:
                _msg = _("Module URL could not be mapped to a filepath: {moduleURL}").format(moduleURL=moduleInfo["moduleURL"])
                self.logPluginTrace(_msg, logging.ERROR)
                continue
            try: # check if moduleInfo cached may differ from referenced moduleInfo
                if os.path.isdir(freshenedFilename): # if freshenedFilename is a directory containing an __ini__.py file, open that instead
                    if os.path.isfile(os.path.join(freshenedFilename, "__init__.py")):
                        freshenedFilename = os.path.join(freshenedFilename, "__init__.py")
                elif not freshenedFilename.endswith(".py") and not os.path.exists(freshenedFilename) and os.path.exists(freshenedFilename + ".py"):
                    freshenedFilename += ".py" # extension module without .py suffix
                if os.path.exists(freshenedFilename):
                    if moduleInfo["fileDate"] != time.strftime('%Y-%m-%dT%H:%M:%S UTC', time.gmtime(os.path.getmtime(freshenedFilename))):
                        freshenedModuleInfo = self.moduleModuleInfo(moduleURL=moduleInfo["moduleURL"], reload=True)
                        if freshenedModuleInfo is not None:
                            if freshenedModuleInfo["name"] == moduleName:
                                _pluginConfig["modules"][moduleName] = freshenedModuleInfo
                            else:
                                # Module has been re-named
                                if moduleEnabled:
                                    missingEnabledModules.append(moduleName)
                # User can avoid pruning by disabling plugin
                elif moduleEnabled:
                    missingEnabledModules.append(moduleName)
                else:
                    _msg = _("File not found for '{name}' plug-in when attempting to update module info. Path: '{path}'")\
                        .format(name=moduleName, path=freshenedFilename)
                    self.logPluginTrace(_msg, logging.ERROR)
            except Exception as err:
                _msg = _("Exception at plug-in method freshenModuleInfos: {error}").format(error=err)
                self.logPluginTrace(_msg, logging.ERROR)
        for moduleName in missingEnabledModules:
            self.removePluginModule(moduleName)
            # Try re-adding plugin modules by name (for plugins that moved from built-in to pip installed)
            moduleInfo = self.addPluginModule(moduleName)
            if moduleInfo:
                _pluginConfig["modules"][moduleInfo["name"]] = moduleInfo
                self.loadModule(moduleInfo)
                self.logPluginTrace(_("Reloaded plugin that failed loading: {} {}").format(moduleName, moduleInfo), logging.INFO)
            else:
                self.logPluginTrace(_("Removed plugin that failed loading (plugin may have been archived): {}").format(moduleName), logging.ERROR)
        self.save(_getCntlr())


    @staticmethod
    def normalizeModuleFilename(moduleFilename: str) -> str | None:
        """
        Attempts to find python script as plugin entry point.
        A value will be returned
          if `moduleFilename` exists as-is,
          if `moduleFilename` is a directory containing __init__.py, or
          if `moduleFilename` with .py extension added exists
        :param moduleFilename:
        :return: Normalized filename, if exists
        """
        if os.path.isfile(moduleFilename):
            # moduleFilename exists as-is, use it
            return moduleFilename
        if os.path.isdir(moduleFilename):
            # moduleFilename is a directory, only valid script is __init__.py contained inside
            initPath = os.path.join(moduleFilename, "__init__.py")
            if os.path.isfile(initPath):
                return initPath
            else:
                return None
        if not moduleFilename.endswith(".py"):
            # moduleFilename is not a file or directory, try adding .py
            pyPath = moduleFilename + ".py"
            if os.path.exists(pyPath):
                return pyPath
        return None


    def getModuleFilename(self, moduleURL: str, reload: bool, normalize: bool, base: str | None) -> tuple[str | None, EntryPoint | None]:
        #TODO several directories, eg User Application Data
        moduleFilename = _getCntlr().webCache.getfilename(moduleURL, reload=reload, normalize=normalize, base=base)
        if moduleFilename:
            # `moduleURL` was mapped to a local filepath
            moduleFilename = self.normalizeModuleFilename(moduleFilename)
            if moduleFilename:
                # `moduleFilename` normalized to an existing script
                return moduleFilename, None
        if base and not self._isAbsoluteModuleURL(moduleURL):
            # Search for a matching plugin deeper in the plugin directory tree.
            # Handles cases where a plugin exists in a nested structure, such as
            # when a developer clones an entire repository into the plugin directory.
            # Example: arelle/plugin/xule/plugin/xule/__init__.py
            for path in glob("**/" + moduleURL.replace('\\', '/'), recursive=True):
                if normalizedPath := self.normalizeModuleFilename(path):
                    return normalizedPath, None
        # `moduleFilename` did not map to a local filepath or did not normalize to a script
        # Try using `moduleURL` to search for pip-installed entry point
        entryPointRef = EntryPointRef.get(moduleURL)
        if entryPointRef is not None:
            return entryPointRef.moduleFilename, entryPointRef.entryPoint
        return None, None


    def parsePluginInfo(self, moduleURL: str, moduleFilename: str, entryPoint: EntryPoint | None) -> dict[str, Any] | None:
        moduleDir, moduleName = os.path.split(moduleFilename)
        with arelle.FileSource.openFileStream(_cntlr, moduleFilename) as f:
            contents = f.read()
            if '__pluginInfo__' not in contents:
                return None
            tree = ast.parse(contents, filename=moduleFilename)
        constantStrings: dict[str, Any] = {}
        functionDefNames = set()
        methodDefNamesByClass: dict[str, set[str]] = defaultdict(set)
        moduleImports = []
        moduleInfo: dict[str, Any] = {"name":None}
        isPlugin = False
        for item in tree.body:
            if isinstance(item, ast.Assign):
                try:
                    _name = cast(ast.Name, item.targets[0])
                    attr = _name.id
                except AttributeError:
                    # Not plugininfo
                    continue
                if attr == "__pluginInfo__":
                    isPlugin = True
                    classMethods = []
                    importURLs = []
                    _dict = cast(ast.Dict, item.value)
                    for i, key in enumerate(_dict.keys):
                        _key = cast(ast.Constant, key).value
                        if _key is None:
                            continue
                        assert isinstance(_key, str), \
                            (f"Plugin info keys must be strings. "
                             f"Found key of type {_key.__class__.__name__} "
                             f"in module {moduleFilename}")

                        _value = _dict.values[i]
                        _valueType = _value.__class__.__name__
                        if _key == "import":
                            if _valueType == 'Constant':
                                importURLs.append(cast(ast.Constant, _value).value)
                            elif _valueType in ("List", "Tuple"):
                                for elt in cast(ast.Tuple | ast.List, _value).elts:
                                    importURLs.append(cast(ast.Constant, elt).value)
                        elif _valueType == 'Constant':
                            _constantValue = cast(ast.Constant, _value)
                            moduleInfo[_key] = _constantValue.value
                        elif _valueType == 'Name':
                            _nameValue = cast(ast.Name, _value)
                            if _nameValue.id in constantStrings:
                                moduleInfo[_key] = constantStrings[_nameValue.id]
                            elif _nameValue.id in functionDefNames:
                                classMethods.append(_key)
                        elif _valueType == 'Attribute':
                            _attributeValue = cast(ast.Attribute, _value)
                            if _attributeValue.attr in methodDefNamesByClass[cast(ast.Name, _attributeValue.value).id]:
                                classMethods.append(_key)
                        elif _valueType in ("List", "Tuple"):
                            _listValue = cast(ast.Tuple | ast.List, _value)
                            values = [cast(ast.Constant, elt).value for elt in _listValue.elts]
                            if _key == "imports":
                                importURLs = values
                            else:
                                moduleInfo[_key] = values

                    moduleInfo['classMethods'] = classMethods
                    moduleInfo['importURLs'] = importURLs
                    moduleInfo["moduleURL"] = moduleURL
                    moduleInfo["path"] = moduleFilename
                    moduleInfo["status"] = 'enabled'
                    moduleInfo["fileDate"] = time.strftime('%Y-%m-%dT%H:%M:%S UTC', time.gmtime(os.path.getmtime(moduleFilename)))
                    if entryPoint:
                        distribution =  cast(Distribution, entryPoint.dist) if getattr(entryPoint, 'dist', None) else None
                        version = distribution.version if distribution else None
                        moduleInfo["moduleURL"] = moduleFilename  # pip-installed plugins need absolute filepath
                        moduleInfo["entryPoint"] = {
                            "module": entryPoint.module,
                            "name": entryPoint.name,
                            "version": version,
                        }
                        if not moduleInfo.get("version"):
                            moduleInfo["version"] = version # If no explicit version, retrieve from entry point
                elif isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):  # possible constant used in plugininfo, such as VERSION
                    for assignmentName in item.targets:
                        constantStrings[cast(ast.Name, assignmentName).id] = item.value.value
            elif isinstance(item, ast.ImportFrom):
                if item.level == 1: # starts with .
                    if item.module is None:  # from . import module1, module2, ...
                        for importee in item.names:
                            if importee.name == '*': #import all submodules
                                for _file in os.listdir(moduleDir):
                                    if _file != moduleName and os.path.isfile(_file) and _file.endswith(".py"):
                                        moduleImports.append(_file)
                            elif (os.path.isfile(os.path.join(moduleDir, importee.name + ".py"))
                                  and importee.name not in moduleImports):
                                moduleImports.append(importee.name)
                    else:
                        modulePkgs = item.module.split('.')
                        modulePath = os.path.join(*modulePkgs)
                        if (os.path.isfile(os.path.join(moduleDir, modulePath) + ".py")
                                and modulePath not in moduleImports):
                            moduleImports.append(modulePath)
                        for importee in item.names:
                            _importeePfxName = os.path.join(modulePath, importee.name)
                            if (os.path.isfile(os.path.join(moduleDir, _importeePfxName) + ".py")
                                    and _importeePfxName not in moduleImports):
                                moduleImports.append(_importeePfxName)
            elif isinstance(item, ast.FunctionDef): # possible functionDef used in plugininfo
                functionDefNames.add(item.name)
            elif isinstance(item, ast.ClassDef):  # possible ClassDef used in plugininfo
                for classItem in item.body:
                    if isinstance(classItem, ast.FunctionDef):
                        methodDefNamesByClass[item.name].add(classItem.name)
        moduleInfo["moduleImports"] = moduleImports
        return moduleInfo if isPlugin else None


    def moduleModuleInfo(
            self,
            moduleURL: str | None = None,
            entryPoint: EntryPoint | None = None,
            reload: bool = False,
            parentImportsSubtree: bool = False) -> dict[str, Any] | None:
        """
        Generates a module info dict based on the provided `moduleURL` or `entryPoint`
        Exactly one of "moduleURL" or "entryPoint" must be provided, otherwise a RuntimeError will be thrown.

        When `moduleURL` is provided, it will be treated as a file path and will attempt to be normalized and
        mapped to an existing plugin based on file location. If `moduleURL` fails to be mapped to an existing
        plugin on its own, it will instead be used to search for an entry point. If found, this function will
        proceed as if that entry point was provided for `entryPoint`.

        When `entryPoint` is provided, it's location and other details will be used to generate the module info
        dictionary.

        :param moduleURL: A URL that loosely maps to the file location of a plugin (may be transformed)
        :param entryPoint: An `EntryPoint` instance
        :param reload:
        :param parentImportsSubtree:
        :return:s
        """
        if (moduleURL is None) == (entryPoint is None):
            raise RuntimeError('Exactly one of "moduleURL" or "entryPoint" must be provided')
        if entryPoint:
            # If entry point is provided, use it to retrieve `moduleFilename`
            moduleFilename = moduleURL = entryPoint.load()()
        else:
            assert moduleURL is not None
            # Otherwise, we will verify the path before continuing
            moduleFilename, entryPoint = self.getModuleFilename(moduleURL, reload=reload, normalize=True, base=_pluginBase)

        if moduleFilename:
            try:
                self.logPluginTrace(f"Scanning module for plug-in info: {moduleFilename}", logging.INFO)
                moduleInfo = self.parsePluginInfo(moduleURL, moduleFilename, entryPoint)
                if moduleInfo is None:
                    return None

                moduleDir, moduleName = os.path.split(moduleFilename)
                importURLs = moduleInfo["importURLs"]
                del moduleInfo["importURLs"]
                moduleImports = moduleInfo["moduleImports"]
                del moduleInfo["moduleImports"]
                moduleImportsSubtree = False
                mergedImportURLs = []

                for url in importURLs:
                    if url.startswith("module_import"):
                        for moduleImport in moduleImports:
                            mergedImportURLs.append(moduleImport + ".py")
                        if url == "module_import_subtree":
                            moduleImportsSubtree = True
                    elif url == "module_subtree":
                        for _dir in os.listdir(moduleDir):
                            subtreeModule = os.path.join(moduleDir,_dir)
                            if os.path.isdir(subtreeModule) and _dir != "__pycache__":
                                mergedImportURLs.append(subtreeModule)
                    else:
                        mergedImportURLs.append(url)
                if parentImportsSubtree and not moduleImportsSubtree:
                    moduleImportsSubtree = True
                    for moduleImport in moduleImports:
                        mergedImportURLs.append(moduleImport + ".py")
                imports = []
                for url in mergedImportURLs:
                    importURL = url
                    if not self._isAbsoluteModuleURL(url):
                        # Handle relative imports when plugin is loaded from external directory.
                        # When EDGAR/render imports EDGAR/validate, this works if EDGAR is in the plugin directory
                        # but fails if loaded externally (e.g., dev repo clone at /dev/path/to/EDGAR/).
                        # Solution: Find common path segments to resolve /dev/path/to/EDGAR/validate
                        # from the importing module at /dev/path/to/EDGAR/render.
                        modulePath = Path(moduleFilename)
                        importPath = Path(url)
                        if importPath.parts:
                            importFirstPart = importPath.parts[0]
                            for i, modulePathPart in enumerate(reversed(modulePath.parts)):
                                if modulePathPart != importFirstPart:
                                    continue
                                # Found a potential branching point, construct and check a new path
                                candidateImportURL = str(modulePath.parents[i] / importPath)
                                if self.normalizeModuleFilename(candidateImportURL):
                                    importURL = candidateImportURL
                    importModuleInfo = self.moduleModuleInfo(moduleURL=importURL, reload=reload, parentImportsSubtree=moduleImportsSubtree)
                    if importModuleInfo:
                        importModuleInfo["isImported"] = True
                        imports.append(importModuleInfo)
                moduleInfo["imports"] = imports
                self.logPluginTrace(f"Successful module plug-in info: {moduleFilename}", logging.INFO)
                return moduleInfo
            except Exception as err:
                _msg = _("Exception obtaining plug-in module info: {moduleFilename}\n{error}\n{traceback}").format(
                        error=err, moduleFilename=moduleFilename, traceback=traceback.format_exc())
                self.logPluginTrace(_msg, logging.ERROR)
        return None


    @staticmethod
    def moduleInfo(pluginInfo: Any) -> None:
        """
        This is an empty function in place for backwards compatability.
        Will be removed in future release.
        """
        pass


    @staticmethod
    def _isAbsoluteModuleURL(moduleURL: str) -> bool:
        return isAbsolute(moduleURL) or isLegacyAbs(moduleURL)


    @staticmethod
    def _get_name_dir_prefix(modulePath: Path, packagePrefix: str = "") -> tuple[str | None, str | None, str | None]:
        """Get the name, directory and prefix of a module."""
        moduleName = None
        moduleDir = None
        packageImportPrefix = None
        initFileName = "__init__.py"

        if modulePath.is_file() and modulePath.name == initFileName:
            modulePath = modulePath.parent

        if modulePath.is_dir() and (modulePath / initFileName).is_file():
            moduleName = modulePath.name
            moduleDir = str(modulePath.parent)
            packageImportPrefix = moduleName + "."
        elif modulePath.is_file() and modulePath.suffix == ".py":
            moduleName = modulePath.stem
            moduleDir = str(modulePath.parent)
            packageImportPrefix = packagePrefix

        return (moduleName, moduleDir, packageImportPrefix)

    @staticmethod
    def _get_location(moduleDir: str, moduleName: str) -> Path:
        """Get the file name of a plugin."""
        module_name_path = Path(f"{moduleDir}/{moduleName}.py")
        if os.path.isfile(module_name_path):
            return module_name_path

        return Path(f"{moduleDir}/{moduleName}/__init__.py")

    @staticmethod
    def _find_and_load_module(moduleDir: str, moduleName: str) -> ModuleType:
        """Load a module based on name and directory."""
        location = PluginManager._get_location(moduleDir=moduleDir, moduleName=moduleName)
        spec = importlib.util.spec_from_file_location(name=moduleName, location=location)

        # spec_from_file_location returns ModuleSpec or None.
        # spec.loader returns Loader or None.
        # We want to make sure neither of them are None before proceeding
        if spec is None or spec.loader is None:
            raise ModuleNotFoundError("Unable to load module")

        module = importlib.util.module_from_spec(spec)
        sys.modules[moduleName] = module # This line is required before exec_module
        spec.loader.exec_module(sys.modules[moduleName])

        return sys.modules[moduleName]

    def loadModule(self, moduleInfo: dict[str, Any], packagePrefix: str="") -> None:
        name = moduleInfo['name']
        moduleURL = moduleInfo['moduleURL']
        modulePath = Path(moduleInfo['path'])
        _pluginConfig = _getPluginConfig()

        moduleName, moduleDir, packageImportPrefix = self._get_name_dir_prefix(modulePath, packagePrefix)
        if all(p is None for p in [moduleName, moduleDir, packageImportPrefix]):
            _getCntlr().addToLog(message=_ERROR_MESSAGE_IMPORT_TEMPLATE.format(name), level=logging.ERROR)
        else:
            try:
                if moduleDir is None or moduleName is None:
                    raise ModuleNotFoundError("Unable to load module")
                module = self._find_and_load_module(moduleDir=moduleDir, moduleName=moduleName)
                pluginInfo = module.__pluginInfo__.copy()
                elementSubstitutionClasses = None
                if name == pluginInfo.get('name'):
                    pluginInfo["moduleURL"] = moduleURL
                    modulePluginInfos[name] = pluginInfo
                    if 'localeURL' in pluginInfo and module.__file__ is not None:
                        # set L10N internationalization in loaded module
                        localeDir = os.path.dirname(module.__file__) + os.sep + pluginInfo['localeURL']
                        try:
                            _gettext = gettext.translation(pluginInfo['localeDomain'], localeDir, getLanguageCodes())
                        except OSError:
                            def _gettext(x: Any) -> Any: # type: ignore[misc]
                                return x # no translation
                    else:
                        def _gettext(x: Any) -> Any: # type: ignore[misc]
                            return x
                    for key, value in pluginInfo.items():
                        if key == 'name':
                            if name:
                                _pluginConfig['modules'][name] = moduleInfo
                        elif isinstance(value, types.FunctionType):
                            classModuleNames = _pluginConfig['classes'].setdefault(key, [])
                            if name and name not in classModuleNames:
                                classModuleNames.append(name)
                        if key == 'ModelObjectFactory.ElementSubstitutionClasses':
                            elementSubstitutionClasses = value
                    module._ = _gettext # type: ignore[attr-defined]
                    global pluginConfigChanged
                    pluginConfigChanged = True
                if elementSubstitutionClasses:
                    try:
                        from arelle.ModelObjectFactory import elementSubstitutionModelClass
                        elementSubstitutionModelClass.update(elementSubstitutionClasses)
                    except Exception as err:
                        _msg = _("Exception loading plug-in {name}: processing ModelObjectFactory.ElementSubstitutionClasses").format(
                                name=name, error=err)
                        self.logPluginTrace(_msg, logging.ERROR)
                if packageImportPrefix is not None:
                    for importModuleInfo in moduleInfo.get('imports', EMPTYLIST):
                        self.loadModule(importModuleInfo, packageImportPrefix)
            except (AttributeError, ImportError, FileNotFoundError, ModuleNotFoundError, TypeError, SystemError) as err:
                # Send a summary of the error to the logger and retain the stacktrace for stderr
                _getCntlr().addToLog(message=_ERROR_MESSAGE_IMPORT_TEMPLATE.format(name), level=logging.ERROR)

                _msg = _("Exception loading plug-in {name}: {error}\n{traceback}").format(
                        name=name, error=err, traceback=traceback.format_exc())
                self.logPluginTrace(_msg, logging.ERROR)


    def hasPluginWithHook(self, name: str) -> bool:
        return next(self.pluginClassMethods(name), None) is not None


    def pluginClassMethods(self, className: str) -> Iterator[Callable[..., Any]]:
        if pluginConfig:
            try:
                pluginMethodsForClass = pluginMethodsForClasses[className]
            except KeyError:
                # load all modules for class
                pluginMethodsForClass = []
                modulesNamesLoaded = set()
                _pluginConfig = _getPluginConfig()
                if className in _pluginConfig["classes"]:
                    for moduleName in _pluginConfig["classes"].get(className):
                        if moduleName and moduleName in _pluginConfig["modules"] and moduleName not in modulesNamesLoaded:
                            modulesNamesLoaded.add(moduleName) # prevent multiply executing same class
                            moduleInfo = _pluginConfig["modules"][moduleName]
                            if moduleInfo["status"] == "enabled":
                                if moduleName not in modulePluginInfos:
                                    self.loadModule(moduleInfo)
                                if moduleName in modulePluginInfos:
                                    pluginInfo = modulePluginInfos[moduleName]
                                    if className in pluginInfo:
                                        pluginMethodsForClass.append(pluginInfo[className])
                pluginMethodsForClasses[className] = pluginMethodsForClass
            yield from pluginMethodsForClass


    def addPluginModule(self, name: str) -> dict[str, Any] | None:
        """
        Discover plugin entry points with given name.
        :param name: The name to search for
        :return: The module information dictionary, if added. Otherwise, None.
        """
        entryPointRef = EntryPointRef.get(name)
        pluginModuleInfo = None
        if entryPointRef:
            pluginModuleInfo = entryPointRef.createModuleInfo()
        if not pluginModuleInfo or not pluginModuleInfo.get("name"):
            pluginModuleInfo = self.moduleModuleInfo(moduleURL=name)
        return self.addPluginModuleInfo(pluginModuleInfo)


    def reloadPluginModule(self, name: str) -> bool:
        _pluginConfig = _getPluginConfig()
        if name in _pluginConfig["modules"]:
            url = _pluginConfig["modules"][name].get("moduleURL")
            if url:
                moduleInfo = self.moduleModuleInfo(moduleURL=url, reload=True)
                if moduleInfo:
                    self.addPluginModule(url)
                    return True
        return False

    def removePluginModule(self, name: str) -> bool:
        _pluginConfig = _getPluginConfig()
        moduleInfo = _pluginConfig["modules"].get(name)
        if moduleInfo and name:
            def _removePluginModule(moduleInfo: dict[str, Any]) -> None:
                _name = moduleInfo.get("name")
                if _name:
                    for classMethod in moduleInfo["classMethods"]:
                        classMethods = _pluginConfig["classes"].get(classMethod)
                        if classMethods and _name and _name in classMethods:
                            classMethods.remove(_name)
                            if not classMethods: # list has become unused
                                del _pluginConfig["classes"][classMethod] # remove class
                    for importModuleInfo in moduleInfo.get('imports', EMPTYLIST):
                        _removePluginModule(importModuleInfo)
                    _pluginConfig["modules"].pop(_name, None)
            _removePluginModule(moduleInfo)
            global pluginConfigChanged
            pluginConfigChanged = True
            return True
        return False # unable to remove


    def addPluginModuleInfo(self, plugin_module_info: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        Given a dictionary containing module information, loads plugin info into `pluginConfig`
        :param plugin_module_info: Dictionary of module info fields. See comment block in PluginManager.py for structure.
        :return: The module information dictionary, if added. Otherwise, None.
        """
        if not plugin_module_info or not plugin_module_info.get("name"):
            return None
        name = plugin_module_info["name"]
        self.removePluginModule(name)  # remove any prior entry for this module

        def _addPluginSubModule(subModuleInfo: dict[str, Any]) -> None:
            """
            Inline function for recursively exploring module imports
            :param subModuleInfo: Module information to add.
            :return:
            """
            _pluginConfig = _getPluginConfig()
            _name = subModuleInfo.get("name")
            if not _name:
                return
            # add classes
            for classMethod in subModuleInfo["classMethods"]:
                classMethods = _pluginConfig["classes"].setdefault(classMethod, [])
                _name = subModuleInfo["name"]
                if _name and _name not in classMethods:
                    classMethods.append(_name)
            for importModuleInfo in subModuleInfo.get('imports', EMPTYLIST):
                _addPluginSubModule(importModuleInfo)
            _pluginConfig["modules"][_name] = subModuleInfo

        _addPluginSubModule(plugin_module_info)
        global pluginConfigChanged
        pluginConfigChanged = True
        return plugin_module_info


_entryPointRefCache: list[EntryPointRef] | None = None
_entryPointRefAliasCache: dict[str, list[EntryPointRef]] | None = None
_entryPointRefSearchTermEndings = [
    '/__init__.py',
    '.py'
    '/'
]


@dataclass
class EntryPointRef:
    aliases: set[str]
    entryPoint: EntryPoint | None
    moduleFilename: str | None
    moduleInfo: dict[str, Any] | None

    def createModuleInfo(self) -> dict[str, Any] | None:
        """
        Creates a module information dictionary from the entry point ref.
        :return: A module inforomation dictionary
        """
        if self.entryPoint is not None:
            return moduleModuleInfo(entryPoint=self.entryPoint)
        return moduleModuleInfo(moduleURL=self.moduleFilename)

    @staticmethod
    def fromEntryPoint(entryPoint: EntryPoint) -> EntryPointRef | None:
        """
        Given an entry point, retrieves the subset of information from __pluginInfo__ necessary to
        determine if the entry point should be imported as a plugin.
        :param entryPoint:
        :return:
        """
        pluginUrlFunc = entryPoint.load()
        pluginUrl = pluginUrlFunc()
        return EntryPointRef.fromFilepath(pluginUrl, entryPoint)

    @staticmethod
    def fromFilepath(filepath: str, entryPoint: EntryPoint | None = None) -> EntryPointRef | None:
        """
        Given a filepath, retrieves a subset of information from __pluginInfo__ necessary to
        determine if the entry point should be imported as a plugin.
        :param filepath: Path to plugin, can be a directory or .py filepath
        :param entryPoint: Optional entry point information to include in aliases/moduleInfo
        :return:
        """
        moduleFilename = _getCntlr().webCache.getfilename(filepath)
        if moduleFilename:
            moduleFilename = normalizeModuleFilename(moduleFilename)
        aliases = set()
        if entryPoint:
            aliases.add(entryPoint.name)
        moduleInfo: dict[str, Any] | None = None
        if moduleFilename:
            moduleInfo = parsePluginInfo(moduleFilename, moduleFilename, entryPoint)
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
    def discoverAll() -> list[EntryPointRef]:
        """
        Retrieve all plugin entry points, cached on first run.
        :return: List of all discovered entry points.
        """
        global _entryPointRefCache
        if _entryPointRefCache is None:
            assert _pluginBase is not None
            _entryPointRefCache = EntryPointRef._discoverBuiltIn([], _pluginBase) + EntryPointRef._discoverInstalled()
        return _entryPointRefCache

    @staticmethod
    def _discoverBuiltIn(entryPointRefs: list[EntryPointRef], directory: str) -> list[EntryPointRef]:
        """
        Recursively retrieve all plugin entry points in the given directory.
        :param entryPointRefs: Working list of entry point refs to append to.
        :param directory: Directory to search for entry points within.
        :return: List of discovered entry points.
        """
        for fileName in sorted(os.listdir(directory)):
            if fileName in (".", "..", "__pycache__", "__init__.py", ".DS_Store", "site-packages"):
                continue  # Ignore these entries
            filePath = os.path.join(directory, fileName)
            if os.path.isdir(filePath):
                EntryPointRef._discoverBuiltIn(entryPointRefs, filePath)
            if os.path.isfile(filePath) and os.path.basename(filePath).endswith(".py"):
                # If `filePath` references .py file directly, use it
                moduleFilePath = filePath
            elif os.path.isdir(filePath) and os.path.exists(initFilePath := os.path.join(filePath, "__init__.py")):
                # Otherwise, if `filePath` is a directory containing `__init__.py`, use that
                moduleFilePath = initFilePath
            else:
                continue
            entryPointRef = EntryPointRef.fromFilepath(moduleFilePath)
            if entryPointRef is not None:
                entryPointRefs.append(entryPointRef)
        return entryPointRefs

    @staticmethod
    def _discoverInstalled() -> list[EntryPointRef]:
        """
        Retrieve all installed plugin entry points.
        :return: List of all discovered entry points.
        """
        entryPoints = list(entry_points(group='arelle.plugin'))
        entryPointRefs = []
        for entryPoint in entryPoints:
            entryPointRef = EntryPointRef.fromEntryPoint(entryPoint)
            if entryPointRef is not None:
                entryPointRefs.append(entryPointRef)
        return entryPointRefs

    @staticmethod
    def get(search: str) -> EntryPointRef | None:
        """
        Retrieve an entry point ref with a matching name or alias.
        May return None of no matches are found.
        Throws an exception if multiple entry point refs match the search term.
        :param search: Only retrieve entry point matching the given search text.
        :return: Matching entry point ref, if found.
        """
        entryPointRefs = EntryPointRef.search(search)
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
    def search(search: str) -> list[EntryPointRef] | None:
        """
        Retrieve entry point module information matching provided search text.
        A map of aliases to matching entry points is cached on the first run.
        :param search: Only retrieve entry points matching the given search text.
        :return: List of matching module infos.
        """
        global _entryPointRefAliasCache
        if _entryPointRefAliasCache is None:
            entryPointRefAliasCache = defaultdict(list)
            entryPointRefs = EntryPointRef.discoverAll()
            for entryPointRef in entryPointRefs:
                for alias in entryPointRef.aliases:
                    entryPointRefAliasCache[alias].append(entryPointRef)
            _entryPointRefAliasCache = entryPointRefAliasCache
        search = EntryPointRef._normalizePluginSearchTerm(search)
        return _entryPointRefAliasCache.get(search, [])


# ---------------------------------------------------------------------------
# Backward-compatible module-level API
#
# These wrappers delegate to a module-level PluginManager singleton so that
# existing callers (e.g. ``from arelle.PluginManager import pluginClassMethods``)
# continue to work without modification.
# ---------------------------------------------------------------------------

_singleton: PluginManager | None = None


def init(cntlr: Cntlr, loadPluginConfig: bool = True) -> None:
    global _singleton
    _singleton = PluginManager(cntlr, loadPluginConfig)


def reset() -> None:
    if _singleton is not None:
        _singleton.reset()


def orderedPluginConfig() -> dict[str, Any]:
    assert _singleton is not None
    return _singleton.orderedPluginConfig()


def save(cntlr: Cntlr) -> None:
    if _singleton is not None:
        _singleton.save(cntlr)


def close() -> None:
    if _singleton is not None:
        _singleton.close()


def logPluginTrace(message: str, level: int) -> None:
    if _singleton is not None:
        _singleton.logPluginTrace(message, level)


def modulesWithNewerFileDates() -> set[str]:
    assert _singleton is not None
    return _singleton.modulesWithNewerFileDates()


def freshenModuleInfos() -> None:
    if _singleton is not None:
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
    if _singleton is not None:
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
