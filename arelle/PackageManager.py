'''
Separated on Jul 28, 2013 from DialogOpenArchive.py

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import sys, os, io, time, json
from lxml import etree
if sys.version[0] >= '3':
    from urllib.parse import urljoin
else:
    from urlparse import urljoin
openFileSource = None
from arelle import Locale
from arelle.UrlUtil import isHttpUrl
try:
    from collections import OrderedDict
except ImportError:
    OrderedDict = dict # python 3.0 lacks OrderedDict, json file will be in weird order 

EMPTYDICT = {}

def parsePackage(mainWin, metadataFile):
    unNamedCounter = 1
    
    NS = "{http://www.corefiling.com/xbrl/taxonomypackage/v1}"
    
    pkg = {}

    currentLang = Locale.getLanguageCode()
    tree = etree.parse(metadataFile)
    root = tree.getroot()
    
    for eltName in ("name", "description", "version"):
        pkg[eltName] = ''
        for m in root.iterchildren(tag=NS + eltName):
            pkg[eltName] = m.text.strip()
            break # take first entry if several

    remappings = dict((m.get("prefix"),m.get("replaceWith"))
                      for m in tree.iter(tag=NS + "remapping"))
    pkg["remappings"] = remappings

    nameToUrls = {}
    pkg["nameToUrls"] = nameToUrls

    for entryPointSpec in tree.iter(tag=NS + "entryPoint"):
        name = None
        
        # find closest match name node given xml:lang match to current language or no xml:lang
        for nameNode in entryPointSpec.iter(tag=NS + "name"):
            xmlLang = nameNode.get('{http://www.w3.org/XML/1998/namespace}lang')
            if name is None or not xmlLang or currentLang == xmlLang:
                name = nameNode.text
                if currentLang == xmlLang: # most prefer one with the current locale's language
                    break

        if not name:
            name = _("<unnamed {0}>").format(unNamedCounter)
            unNamedCounter += 1

        epDocCount = 0
        for epDoc in entryPointSpec.iterchildren(NS + "entryPointDocument"):
            if epDocCount:
                mainWin.addToLog(_("WARNING: skipping multiple-document entry point (not supported)"))
                continue
            epDocCount += 1
            epUrl = epDoc.get('href')
            base = epDoc.get('{http://www.w3.org/XML/1998/namespace}base') # cope with xml:base
            if base:
                resolvedUrl = urljoin(base, epUrl)
            else:
                resolvedUrl = epUrl
    
            #perform prefix remappings
            remappedUrl = resolvedUrl
            for prefix, replace in remappings.items():
                remappedUrl = remappedUrl.replace(prefix, replace, 1)
            nameToUrls[name] = (remappedUrl, resolvedUrl)

    return pkg

# taxonomy package manager
# plugin control is static to correspond to statically loaded modules
packagesJsonFile = None
packagesConfig = None
packagesConfigChanged = False
packagesMappings = {}
_cntlr = None

def init(cntlr):
    global packagesJsonFile, packagesConfig, packagesMappings, _cntlr
    try:
        packagesJsonFile = cntlr.userAppDir + os.sep + "taxonomyPackages.json"
        with io.open(packagesJsonFile, 'rt', encoding='utf-8') as f:
            packagesConfig = json.load(f)
        packagesConfigChanged = False
    except Exception:
        # on GAE no userAppDir, will always come here
        packagesConfig = {  # savable/reloadable plug in configuration
            "packages": [], # list taxonomy packages loaded and their remappings
            "remappings": {}  # dict by prefix of remappings in effect
        }
        packagesConfigChanged = False # don't save until something is added to pluginConfig
    pluginMethodsForClasses = {} # dict by class of list of ordered callable function objects
    _cntlr = cntlr
    
def reset():  # force reloading modules and plugin infos
    packagesConfig.clear()  # dict of loaded module pluginInfo objects by module names
    packagesMappings.clear() # dict by class of list of ordered callable function objects
    
def orderedPackagesConfig():
    return OrderedDict(
        (('packages', [OrderedDict(sorted(_packageInfo.items(), 
                                          key=lambda k: {'name': '01',
                                                         'status': '02',
                                                         'version': '03',
                                                         'fileDate': '04',
                                                         'URL': '05',
                                                         'description': '06',
                                                         'remappings': '07'}.get(k[0],k[0])))
                       for _packageInfo in packagesConfig['packages']]),
         ('remappings',OrderedDict(sorted(packagesConfig['remappings'].items())))))
    
def save(cntlr):
    global packagesConfigChanged
    if packagesConfigChanged and cntlr.hasFileSystem:
        pluginJsonFile = cntlr.userAppDir + os.sep + "plugins.json"
        with io.open(packagesJsonFile, 'wt', encoding='utf-8') as f:
            jsonStr = _STR_UNICODE(json.dumps(orderedPackagesConfig(), ensure_ascii=False, indent=2)) # might not be unicode in 2.7
            f.write(jsonStr)
        packagesConfigChanged = False
    
def close():  # close all loaded methods
    packagesConfig.clear()
    packagesMappings.clear()
    global webCache
    webCache = None
    
''' packagesConfig structure

{
 'packages':  [list of package dicts in order of application],
 'remappings': dict of prefix:url remappings
}

package dict
{
    'name': package name
    'status': enabled | disabled
    'version': version (such as 2009)
    'fileDate': 2001-01-01
    'url': web http (before caching) or local file location
    'description': text
    'remappings': dict of prefix:url of each remapping
}

'''

def packageNamesWithNewerFileDates():
    names = set()
    for package in packagesConfig["packages"]:
        freshenedFilename = _cntlr.webCache.getfilename(package["URL"], checkModifiedTime=True, normalize=True)
        try:
            if package["fileDate"] < time.strftime('%Y-%m-%dT%H:%M:%S UTC', time.gmtime(os.path.getmtime(freshenedFilename))):
                names.add(package["name"])
        except Exception:
            pass
    return names

def packageInfo(URL, reload=False):
    #TODO several directories, eg User Application Data
    packageFilename = _cntlr.webCache.getfilename(URL, reload=reload, normalize=True)
    if packageFilename:
        filesource = None
        try:
            global openFileSource
            if openFileSource is None:
                from arelle.FileSource import openFileSource
            filesource = openFileSource(packageFilename, _cntlr)
            if filesource.isZip:
                metadataFiles = filesource.taxonomyPackageMetadataFiles
                if len(metadataFiles) != 1:
                    raise IOError(_("Taxonomy package contained more than one metadata file: {0}.")
                                  .format(', '.join(metadataFiles)))
                metadataFile = metadataFiles[0]
                metadata = filesource.file(filesource.url + os.sep + metadataFile)[0]
                metadataFilePrefix = os.sep.join(os.path.split(metadataFile)[:-1])
                if metadataFilePrefix:
                    metadataFilePrefix += os.sep
                metadataFilePrefix = filesource.baseurl + os.sep +  metadataFilePrefix
            elif os.path.basename(filesource.url) == ".taxonomyPackage.xml": # individual manifest file
                metadataFile = metadata = filesource.url
                metadataFilePrefix = os.sep.join(os.path.split(metadataFile)[:-1])
                if metadataFilePrefix:
                    metadataFilePrefix += os.sep
            else:
                raise IOError(_("File must be a taxonomy package (zip file) or manifest (.taxonomyPackage.xml): {0}.")
                              .format(metadataFile))
            parsedPackage = parsePackage(_cntlr, metadata)
            package = {'name': parsedPackage['name'],
                       'status': 'enabled',
                       'version': parsedPackage['version'],
                       'fileDate': time.strftime('%Y-%m-%dT%H:%M:%S UTC', time.gmtime(os.path.getmtime(packageFilename))),
                       'URL': URL,
                       'description': parsedPackage['description'],
                       'remappings': dict(
                            (prefix, 
                             remapping if isHttpUrl(remapping)
                             else (metadataFilePrefix +remapping.replace("/", os.sep)))
                            for prefix, remapping in parsedPackage["remappings"].items()),
                       }
            filesource.close()
            return package
        except EnvironmentError:
            pass
        if filesource:
            filesource.close()
    return None

def rebuildRemappings():
    remappings = packagesConfig["remappings"]
    remappings.clear()
    for _packageInfo in packagesConfig["packages"]:
        if _packageInfo['status'] == 'enabled':
            for prefix, remapping in _packageInfo['remappings'].items():
                if prefix not in remappings:
                    remappings[prefix] = remapping

def isMappedUrl(url):
    return (packagesConfig is not None and 
            any(url.startswith(mapFrom) 
                for mapFrom in packagesConfig.get('remappings', EMPTYDICT).keys()))

def mappedUrl(url):
    if packagesConfig is not None:
        for mapFrom, mapTo in packagesConfig.get('remappings', EMPTYDICT).items():
            if url.startswith(mapFrom):
                url = mapTo + url[len(mapFrom):]
                break
    return url

def addPackage(url):
    newPackageInfo = packageInfo(url)
    name = newPackageInfo.get("name")
    version = newPackageInfo.get("version")
    if newPackageInfo and name:
        j = -1
        packagesList = packagesConfig["packages"]
        for i, _packageInfo in enumerate(packagesList):
            if _packageInfo['name'] == name and _packageInfo['version'] == version:
                j = i
                break
        if 0 <= j < len(packagesList): # replace entry
            packagesList[j] = newPackageInfo
        else:
            packagesList.append(newPackageInfo)
        global packagesConfigChanged
        packagesConfigChanged = True
        rebuildRemappings()
        return newPackageInfo
    return None

def reloadPackageModule(name):
    packageUrls = []
    packagesList = packagesConfig["packages"]
    for _packageInfo in packagesList:
        if _packageInfo['name'] == name:
            packageUrls.append(_packageInfo['URL'])
    result = False
    for url in packageUrls:
        addPackage(url)
        result = True
    return result

def removePackageModule(name):
    packageIndices = []
    packagesList = packagesConfig["packages"]
    for i, _packageInfo in enumerate(packagesList):
        if _packageInfo['name'] == name:
            packageIndices.insert(0, i) # must remove in reverse index order
    result = False
    for i in packageIndices:
        del packagesList[i]
        result = True
    if result:
        global packagesConfigChanged
        packagesConfigChanged = True
        rebuildRemappings()
    return result
