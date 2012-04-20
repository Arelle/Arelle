'''
Created on March 1, 2012

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.

based on pull request 4

'''
import os, sys, types, time, ast, imp, io, json, gettext
from collections import OrderedDict
from arelle.Locale import getLanguageCodes

# plugin control is static to correspond to statically loaded modules
pluginJsonFile = None
pluginConfig = None
pluginConfigChanged = False
modulePluginInfos = {}
pluginMethodsForClasses = {}
webCache = None

def init(cntlr):
    global pluginJsonFile, pluginConfig, modulePluginInfos, pluginMethodsForClasses, pluginConfigChanged, webCache
    try:
        pluginJsonFile = cntlr.userAppDir + os.sep + "plugins.json"
        with io.open(pluginJsonFile, 'rt', encoding='utf-8') as f:
            pluginConfig = json.load(f)
        pluginConfigChanged = False
    except Exception:
        pluginConfig = {  # savable/reloadable plug in configuration
            "modules": {}, # dict of moduleInfos by module name
            "classes": {}  # dict by class name of list of class modules in execution order
        }
        pluginConfigChanged = False # don't save until something is added to pluginConfig
    modulePluginInfos = {}  # dict of loaded module pluginInfo objects by module names
    pluginMethodsForClasses = {} # dict by class of list of ordered callable function objects
    webCache = cntlr.webCache
    
def reset():  # force reloading modules and plugin infos
    modulePluginInfos = {}  # dict of loaded module pluginInfo objects by module names
    pluginMethodsForClasses = {} # dict by class of list of ordered callable function objects
    
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
    
def save(cntlr):
    global pluginConfigChanged
    if pluginConfigChanged:
        pluginJsonFile = cntlr.userAppDir + os.sep + "plugins.json"
        with io.open(pluginJsonFile, 'wt', encoding='utf-8') as f:
            json.dump(orderedPluginConfig(), f, indent=2)
        pluginConfigChanged = False
    
def close():  # close all loaded methods
    modulePluginInfos.clear()
    pluginMethodsForClasses.clear()
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
}

moduleInfo = {
    'name': (required)
    'status': enabled | disabled
    'version': (required)
    'fileDate': 2000-01-01
    'description': (optional)
    'moduleURL': (required) # same as file path, can be a URL
    'localeURL': (optional) # for L10N internationalization within module
    'localeDomain': (optional) # domain for L10N internationalization
    'license': (optional)
    'author': (optional)
    'copyright': (optional)
    'classMethods': [list of class names that have methods in module]
}


'''
    
def modulesWithNewerFileDates():
    names = set()
    for moduleInfo in pluginConfig["modules"].values():
        freshenedFilename = webCache.getfilename(moduleInfo["moduleURL"], checkModifiedTime=True)
        if moduleInfo["fileDate"] < time.strftime('%Y-%m-%dT%H:%M:%S UTC', time.gmtime(os.path.getmtime(freshenedFilename))):
            names.add(moduleInfo["name"])
    return names

def moduleModuleInfo(moduleURL, reload=False):
    #TODO several directories, eg User Application Data
    moduleFilename = webCache.getfilename(moduleURL, reload=reload, normalize=True)
    if moduleFilename:
        with open(moduleFilename) as f:
            tree = ast.parse(f.read(), filename=moduleFilename)
            for item in tree.body:
                if isinstance(item, ast.Assign):
                    attr = item.targets[0].id
                    if attr == "__pluginInfo__":
                        f.close()
                        moduleInfo = {}
                        classMethods = []
                        for i, key in enumerate(item.value.keys):
                            _key = key.s
                            _value = item.value.values[i]
                            _valueType = _value.__class__.__name__
                            if _valueType == 'Str':
                                moduleInfo[_key] = _value.s
                            elif _valueType == 'Name':
                                classMethods.append(_key)
                        moduleInfo['classMethods'] = classMethods
                        moduleInfo["moduleURL"] = moduleURL
                        moduleInfo["status"] = 'enabled'
                        moduleInfo["fileDate"] = time.strftime('%Y-%m-%dT%H:%M:%S UTC', time.gmtime(os.path.getmtime(moduleFilename)))
                        return moduleInfo
    return None

def moduleInfo(pluginInfo):
    moduleInfo = {}
    for name, value in pluginInfo.items():
        if isinstance(value, '_STR_UNICODE'):
            moduleInfo[name] = value
        elif isinstance(value, types.FunctionType):
            moduleInfo.getdefault('classes',[]).append(name)

def loadModule(moduleInfo):
    name = moduleInfo['name']
    moduleURL = moduleInfo['moduleURL']
    moduleFilename = webCache.getfilename(moduleURL, normalize=True)
    if moduleFilename:
        file, path, description = imp.find_module(os.path.basename(moduleFilename).partition('.')[0], [os.path.dirname(moduleFilename)])
        if file:
            try:
                module = imp.load_module(name, file, path, description)
                pluginInfo = module.__pluginInfo__.copy()
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
                    module._ = _gettext
                    global pluginConfigChanged
                    pluginConfigChanged = True
            except (ImportError, AttributeError):
                pass
            finally:
                file.close()

def pluginClassMethods(className):
    if pluginConfig:
        try:
            pluginMethodsForClass = pluginMethodsForClasses[className]
        except KeyError:
            # load all modules for class
            pluginMethodsForClass = []
            if className in pluginConfig["classes"]:
                for moduleName in pluginConfig["classes"].get(className):
                    if moduleName and moduleName in pluginConfig["modules"]:
                        moduleInfo = pluginConfig["modules"][moduleName]
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
        pluginConfig["modules"][name] = moduleInfo
        # add classes
        for classMethod in moduleInfo["classMethods"]:
            classMethods = pluginConfig["classes"].setdefault(classMethod, [])
            if name not in classMethods:
                classMethods.append(name)
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
    if moduleInfo:
        for classMethod in moduleInfo["classMethods"]:
            classMethods = pluginConfig["classes"].get(classMethod)
            if classMethods and name in classMethods:
                classMethods.remove(name)
                if not classMethods: # list has become unused
                    del pluginConfig["classes"][classMethod] # remove class
        del pluginConfig["modules"][name]
        global pluginConfigChanged
        pluginConfigChanged = True
        return True
    return False # unable to remove