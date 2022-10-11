'''
See COPYRIGHT.md for copyright information.

based on pull request 4

'''
from __future__ import annotations
import os, sys, types, time, ast, importlib, io, json, gettext, traceback
import importlib.util
import logging

from types import ModuleType
from typing import TYPE_CHECKING, Any, Iterator, Callable
from arelle.Locale import getLanguageCodes
import arelle.FileSource
from arelle.UrlUtil import isAbsolute
from pathlib import Path
try:
    from collections import OrderedDict
except ImportError:
    OrderedDict = dict # python 3.0 lacks OrderedDict, json file will be in weird order
from collections.abc import Generator, Callable


if TYPE_CHECKING:
    # Prevent potential circular import error
    from .Cntlr import Cntlr

PLUGIN_TRACE_FILE = None
# PLUGIN_TRACE_FILE = "c:/temp/pluginerr.txt"
PLUGIN_TRACE_LEVEL = logging.WARNING

# plugin control is static to correspond to statically loaded modules
pluginJsonFile = None
pluginConfig = None
pluginConfigChanged = False
pluginTraceFileLogger = None
modulePluginInfos = {}
pluginMethodsForClasses = {}
_cntlr = None
_pluginBase = None
EMPTYLIST = []
_ERROR_MESSAGE_IMPORT_TEMPLATE = "Unable to load module {}"

def init(cntlr: Cntlr, loadPluginConfig: bool = True) -> None:
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
            with io.open(pluginJsonFile, 'rt', encoding='utf-8') as f:
                pluginConfig = json.load(f)
            freshenModuleInfos()
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

def reset():  # force reloading modules and plugin infos
    modulePluginInfos.clear()  # dict of loaded module pluginInfo objects by module names
    pluginMethodsForClasses.clear() # dict by class of list of ordered callable function objects

def orderedPluginConfig():
    return OrderedDict(
        (('modules',OrderedDict((moduleName,
                                 OrderedDict(sorted(moduleInfo.items(),
                                                    key=lambda k: {'name': '01',
                                                                   'status': '02',
                                                                   'version': '03',
                                                                   'fileDate': '04',                                                             'version': '05',
                                                                   'description': '05',
                                                                   'moduleURL': '06',
                                                                   'localeURL': '07',
                                                                   'localeDomain': '08',
                                                                   'license': '09',
                                                                   'author': '10',
                                                                   'copyright': '11',
                                                                   'classMethods': '12'}.get(k[0],k[0]))))
                                for moduleName, moduleInfo in sorted(pluginConfig['modules'].items()))),
         ('classes',OrderedDict(sorted(pluginConfig['classes'].items())))))

def save(cntlr: Cntlr) -> None:
    global pluginConfigChanged
    if pluginConfigChanged and cntlr.hasFileSystem:
        pluginJsonFile = cntlr.userAppDir + os.sep + "plugins.json"
        with io.open(pluginJsonFile, 'wt', encoding='utf-8') as f:
            jsonStr = str(json.dumps(orderedPluginConfig(), ensure_ascii=False, indent=2)) # might not be unicode in 2.7
            f.write(jsonStr)
        pluginConfigChanged = False

def close():  # close all loaded methods
    pluginConfig.clear()
    modulePluginInfos.clear()
    pluginMethodsForClasses.clear()
    global webCache
    webCache = None

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


def logPluginTrace(message: str, level: Number) -> None:
    """
    If plugin trace file logging is configured, logs `message` to it.
    Only logs to controller logger if log is an error.
    :param message: Message to be logged
    :param level: Log level of message (e.g. logging.INFO)
    """
    global pluginTraceFileLogger
    if pluginTraceFileLogger:
        pluginTraceFileLogger.log(level, message)
    if level >= logging.ERROR:
        _cntlr.addToLog(message=message, level=level, messageCode='arelle:pluginLoadingError')


def modulesWithNewerFileDates():
    names = set()
    for moduleName, moduleInfo in pluginConfig["modules"].items():
        freshenedFilename = _cntlr.webCache.getfilename(moduleInfo["moduleURL"], checkModifiedTime=True, normalize=True, base=_pluginBase)
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
                logPluginTrace(_msg, logging.ERROR)
        except Exception as err:
            _msg = _("Exception at plug-in method modulesWithNewerFileDates: {error}").format(error=err)
            logPluginTrace(_msg, logging.ERROR)

    return names

def freshenModuleInfos():
    # for modules with different date-times, re-load module info
    for moduleName in pluginConfig["modules"].keys():
        moduleInfo = pluginConfig["modules"][moduleName]
        freshenedFilename = _cntlr.webCache.getfilename(moduleInfo["moduleURL"], checkModifiedTime=True, normalize=True, base=_pluginBase)
        try: # check if moduleInfo cached may differ from referenced moduleInfo
            if os.path.isdir(freshenedFilename): # if freshenedFilename is a directory containing an __ini__.py file, open that instead
                if os.path.isfile(os.path.join(freshenedFilename, "__init__.py")):
                    freshenedFilename = os.path.join(freshenedFilename, "__init__.py")
            elif not freshenedFilename.endswith(".py") and not os.path.exists(freshenedFilename) and os.path.exists(freshenedFilename + ".py"):
                freshenedFilename += ".py" # extension module without .py suffix
            if os.path.exists(freshenedFilename):
                if moduleInfo["fileDate"] != time.strftime('%Y-%m-%dT%H:%M:%S UTC', time.gmtime(os.path.getmtime(freshenedFilename))):
                    freshenedModuleInfo = moduleModuleInfo(moduleInfo["moduleURL"], reload=True)
                    if freshenedModuleInfo is not None:
                        pluginConfig["modules"][moduleName] = freshenedModuleInfo
            else:
                _msg = _("File not found for '{name}' plug-in when attempting to update module info. Path: '{path}'")\
                    .format(name=moduleName, path=freshenedFilename)
                logPluginTrace(_msg, logging.ERROR)
        except Exception as err:
            _msg = _("Exception at plug-in method freshenModuleInfos: {error}").format(error=err)
            logPluginTrace(_msg, logging.ERROR)

def moduleModuleInfo(moduleURL, reload=False, parentImportsSubtree=False):
    #TODO several directories, eg User Application Data
    moduleFilename = _cntlr.webCache.getfilename(moduleURL, reload=reload, normalize=True, base=_pluginBase)
    if moduleFilename:
        f = None
        try:
            # if moduleFilename is a directory containing an __ini__.py file, open that instead
            if os.path.isdir(moduleFilename):
                if os.path.isfile(os.path.join(moduleFilename, "__init__.py")):
                    moduleFilename = os.path.join(moduleFilename, "__init__.py")
                else: # impossible to get a moduleinfo from a directory without an __init__.py
                    return None
            elif not moduleFilename.endswith(".py") and not os.path.exists(moduleFilename) and os.path.exists(moduleFilename + ".py"):
                moduleFilename += ".py" # extension module without .py suffix
            moduleDir, moduleName = os.path.split(moduleFilename)
            logPluginTrace("Scanning module for plug-in info: {}".format(moduleFilename), logging.INFO)
            f = arelle.FileSource.openFileStream(_cntlr, moduleFilename)
            tree = ast.parse(f.read(), filename=moduleFilename)
            constantStrings = {}
            functionDefNames = set()
            moduleImports = []
            for item in tree.body:
                if isinstance(item, ast.Assign):
                    attr = item.targets[0].id
                    if attr == "__pluginInfo__":
                        f.close()
                        moduleInfo = {"name":None}
                        classMethods = []
                        importURLs = []
                        for i, key in enumerate(item.value.keys):
                            _key = key.s
                            _value = item.value.values[i]
                            _valueType = _value.__class__.__name__
                            if _key == "import":
                                if _valueType in ('Str', 'Constant'):
                                    importURLs.append(_value.s)
                                elif _valueType in ("List", "Tuple"):
                                    for elt in _value.elts:
                                        importURLs.append(elt.s)
                            elif _valueType in ('Str', 'Constant'): # Str < =python 3.7, Constant python 3.8+
                                moduleInfo[_key] = _value.s
                            elif _valueType == 'Name':
                                if _value.id in constantStrings:
                                    moduleInfo[_key] = constantStrings[_value.id]
                                elif _value.id in functionDefNames:
                                    classMethods.append(_key)
                            elif _key == "imports" and _valueType in ("List", "Tuple"):
                                importURLs = [elt.s for elt in _value.elts]
                        moduleInfo['classMethods'] = classMethods
                        moduleInfo["moduleURL"] = moduleURL
                        moduleInfo["status"] = 'enabled'
                        moduleInfo["fileDate"] = time.strftime('%Y-%m-%dT%H:%M:%S UTC', time.gmtime(os.path.getmtime(moduleFilename)))
                        mergedImportURLs = []
                        _moduleImportsSubtree = False
                        for _url in importURLs:
                            if _url.startswith("module_import"):
                                for moduleImport in moduleImports:
                                    mergedImportURLs.append(moduleImport + ".py")
                                if _url == "module_import_subtree":
                                    _moduleImportsSubtree = True
                            elif _url == "module_subtree":
                                for _dir in os.listdir(moduleDir):
                                    _subtreeModule = os.path.join(moduleDir,_dir)
                                    if os.path.isdir(_subtreeModule) and _dir != "__pycache__":
                                        mergedImportURLs.append(_subtreeModule)
                            else:
                                mergedImportURLs.append(_url)
                        if parentImportsSubtree and not _moduleImportsSubtree:
                            _moduleImportsSubtree = True
                            for moduleImport in moduleImports:
                                mergedImportURLs.append(moduleImport + ".py")
                        imports = []
                        for _url in mergedImportURLs:
                            if isAbsolute(_url) or os.path.isabs(_url):
                                _importURL = _url # URL is absolute http or local file system
                            else: # check if exists relative to this module's directory
                                _importURL = os.path.join(os.path.dirname(moduleURL), os.path.normpath(_url))
                                if not os.path.exists(_importURL): # not relative to this plugin, assume standard plugin base
                                    _importURL = _url # moduleModuleInfo adjusts relative URL to plugin base
                            _importModuleInfo = moduleModuleInfo(_importURL, reload, _moduleImportsSubtree)
                            if _importModuleInfo:
                                _importModuleInfo["isImported"] = True
                                imports.append(_importModuleInfo)
                        moduleInfo["imports"] =  imports
                        return moduleInfo
                    elif isinstance(item.value, ast.Str): # possible constant used in plugininfo, such as VERSION
                        for assignmentName in item.targets:
                            constantStrings[assignmentName.id] = item.value.s
                elif isinstance(item, ast.ImportFrom):
                    if item.level == 1: # starts with .
                        if item.module is None:  # from . import module1, module2, ...
                            for importee in item.names:
                                if importee.name == '*': #import all submodules
                                    for _file in os.listdir(moduleDir):
                                        if _file != moduleFile and os.path.isfile(_file) and _file.endswith(".py"):
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
            logPluginTrace(f"Successful module plug-in info: {moduleFilename}", logging.INFO)
        except Exception as err:
            _msg = _("Exception obtaining plug-in module info: {moduleFilename}\n{error}\n{traceback}").format(
                    error=err, moduleFilename=moduleFilename, traceback=traceback.format_tb(sys.exc_info()[2]))
            logPluginTrace(_msg, logging.ERROR)

        if f:
            f.close()
    return None


def moduleInfo(pluginInfo):
    moduleInfo = {}
    for name, value in pluginInfo.items():
        if isinstance(value, str):
            moduleInfo[name] = value
        elif isinstance(value, types.FunctionType):
            moduleInfo.getdefault('classes', []).append(name)


def _get_name_dir_prefix(
    controller: Cntlr,
    pluginBase: str,
    moduleURL: str,
    packagePrefix: str = "",
) -> tuple[str, str, str] | tuple[None, None, None]:
    """Get the name, directory and prefix of a module."""
    moduleFilename: str
    moduleDir: str
    packageImportPrefix: str

    moduleFilename = controller.webCache.getfilename(
        url=moduleURL, normalize=True, base=pluginBase
    )

    if moduleFilename:
        if os.path.basename(moduleFilename) == "__init__.py" and os.path.isfile(
            moduleFilename
        ):
            moduleFilename = os.path.dirname(
                moduleFilename
            )  # want just the dirpart of package

        if os.path.isdir(moduleFilename) and os.path.isfile(
            os.path.join(moduleFilename, "__init__.py")
        ):
            moduleDir = os.path.dirname(moduleFilename)
            moduleName = os.path.basename(moduleFilename)
            packageImportPrefix = moduleName + "."
        else:
            moduleName = os.path.basename(moduleFilename).partition(".")[0]
            moduleDir = os.path.dirname(moduleFilename)
            packageImportPrefix = packagePrefix

        return (moduleName, moduleDir, packageImportPrefix)

    return (None, None, None)

def _get_location(moduleDir: str, moduleName: str) -> str:
    """Get the file name of a plugin."""
    module_name_path = Path(f"{moduleDir}/{moduleName}.py")
    if os.path.isfile(module_name_path):
        return module_name_path

    return Path(f"{moduleDir}/{moduleName}/__init__.py")

def _find_and_load_module(moduleDir: str, moduleName: str) -> ModuleType | None:
    """Load a module based on name and directory."""
    location = _get_location(moduleDir=moduleDir, moduleName=moduleName)
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

def loadModule(moduleInfo: dict[str, Any], packagePrefix: str="") -> None:
    name = moduleInfo['name']
    moduleURL = moduleInfo['moduleURL']

    moduleName, moduleDir, packageImportPrefix = _get_name_dir_prefix(
        controller=_cntlr,
        pluginBase=_pluginBase,
        moduleURL=moduleURL,
        packagePrefix=packagePrefix,
    )

    if all(p is None for p in [moduleName, moduleDir, packageImportPrefix]):
        _cntlr.addToLog(message=_ERROR_MESSAGE_IMPORT_TEMPLATE.format(name), level=logging.ERROR)
    else:
        try:
            module = _find_and_load_module(moduleDir=moduleDir, moduleName=moduleName)
            pluginInfo = module.__pluginInfo__.copy()
            elementSubstitutionClasses = None
            if name == pluginInfo.get('name'):
                pluginInfo["moduleURL"] = moduleURL
                modulePluginInfos[name] = pluginInfo
                if 'localeURL' in pluginInfo:
                    # set L10N internationalization in loaded module
                    localeDir = os.path.dirname(module.__file__) + os.sep + pluginInfo['localeURL']
                    try:
                        _gettext = gettext.translation(pluginInfo['localeDomain'], localeDir, getLanguageCodes())
                    except IOError:
                        _gettext = lambda x: x # no translation
                else:
                    _gettext = lambda x: x
                for key, value in pluginInfo.items():
                    if key == 'name':
                        if name:
                            pluginConfig['modules'][name] = moduleInfo
                    elif isinstance(value, types.FunctionType):
                        classModuleNames = pluginConfig['classes'].setdefault(key, [])
                        if name and name not in classModuleNames:
                            classModuleNames.append(name)
                    if key == 'ModelObjectFactory.ElementSubstitutionClasses':
                        elementSubstitutionClasses = value
                module._ = _gettext
                global pluginConfigChanged
                pluginConfigChanged = True
            if elementSubstitutionClasses:
                try:
                    from arelle.ModelObjectFactory import elementSubstitutionModelClass
                    elementSubstitutionModelClass.update(elementSubstitutionClasses)
                except Exception as err:
                    _msg = _("Exception loading plug-in {name}: processing ModelObjectFactory.ElementSubstitutionClasses").format(
                            name=name, error=err)
                    logPluginTrace(_msg, logging.ERROR)
            for importModuleInfo in moduleInfo.get('imports', EMPTYLIST):
                loadModule(importModuleInfo, packageImportPrefix)
        except (AttributeError, ImportError, FileNotFoundError, ModuleNotFoundError, TypeError, SystemError) as err:
            # Send a summary of the error to the logger and retain the stacktrace for stderr
            _cntlr.addToLog(message=_ERROR_MESSAGE_IMPORT_TEMPLATE.format(name), level=logging.ERROR)

            _msg = _("Exception loading plug-in {name}: {error}\n{traceback}").format(
                    name=name, error=err, traceback=traceback.format_tb(sys.exc_info()[2]))
            logPluginTrace(_msg, logging.ERROR)

def pluginClassMethods(className: str) -> Iterator[Callable[..., Any]]:
    if pluginConfig:
        try:
            pluginMethodsForClass = pluginMethodsForClasses[className]
        except KeyError:
            # load all modules for class
            pluginMethodsForClass = []
            modulesNamesLoaded = set()
            if className in pluginConfig["classes"]:
                for moduleName in pluginConfig["classes"].get(className):
                    if moduleName and moduleName in pluginConfig["modules"] and moduleName not in modulesNamesLoaded:
                        modulesNamesLoaded.add(moduleName) # prevent multiply executing same class
                        moduleInfo = pluginConfig["modules"][moduleName]
                        if moduleInfo["status"] == "enabled":
                            if moduleName not in modulePluginInfos:
                                loadModule(moduleInfo)
                            if moduleName in modulePluginInfos:
                                pluginInfo = modulePluginInfos[moduleName]
                                if className in pluginInfo:
                                    pluginMethodsForClass.append(pluginInfo[className])
            pluginMethodsForClasses[className] = pluginMethodsForClass
        for method in pluginMethodsForClass:
            yield method

def addPluginModule(url):
    moduleInfo = moduleModuleInfo(url)
    if moduleInfo and moduleInfo.get("name"):
        name = moduleInfo["name"]
        removePluginModule(name)  # remove any prior entry for this module
        def _addPluginModule(moduleInfo):
            _name = moduleInfo.get("name")
            if _name:
                # add classes
                for classMethod in moduleInfo["classMethods"]:
                    classMethods = pluginConfig["classes"].setdefault(classMethod, [])
                    _name = moduleInfo["name"]
                    if _name and _name not in classMethods:
                        classMethods.append(_name)
                for importModuleInfo in moduleInfo.get('imports', EMPTYLIST):
                    _addPluginModule(importModuleInfo)
                pluginConfig["modules"][_name] = moduleInfo
        _addPluginModule(moduleInfo)
        global pluginConfigChanged
        pluginConfigChanged = True
        return moduleInfo
    return None

def reloadPluginModule(name):
    if name in pluginConfig["modules"]:
        url = pluginConfig["modules"][name].get("moduleURL")
        if url:
            moduleInfo = moduleModuleInfo(url, reload=True)
            if moduleInfo:
                addPluginModule(url)
                return True
    return False

def removePluginModule(name):
    moduleInfo = pluginConfig["modules"].get(name)
    if moduleInfo and name:
        def _removePluginModule(moduleInfo):
            _name = moduleInfo.get("name")
            if _name:
                for classMethod in moduleInfo["classMethods"]:
                    classMethods = pluginConfig["classes"].get(classMethod)
                    if classMethods and _name and _name in classMethods:
                        classMethods.remove(_name)
                        if not classMethods: # list has become unused
                            del pluginConfig["classes"][classMethod] # remove class
                for importModuleInfo in moduleInfo.get('imports', EMPTYLIST):
                    _removePluginModule(importModuleInfo)
                pluginConfig["modules"].pop(_name, None)
        _removePluginModule(moduleInfo)
        global pluginConfigChanged
        pluginConfigChanged = True
        return True
    return False # unable to remove
