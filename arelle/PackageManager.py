"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from fnmatch import fnmatch
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from lxml import etree

from arelle import Locale
from arelle.PythonUtil import isLegacyAbs
from arelle.packages import PackageValidation
from arelle.packages.PackageType import PackageType
from arelle.typing import TypeGetText
from arelle.UrlUtil import isAbsolute, isHttpUrl
from arelle.XmlValidate import lxmlResolvingParser

if TYPE_CHECKING:
    from arelle.Cntlr import Cntlr
    from arelle.FileSource import FileSource

TP_XSD = "http://www.xbrl.org/2016/taxonomy-package.xsd"
CAT_XSD = "http://www.xbrl.org/2016/taxonomy-package-catalog.xsd"

_: TypeGetText

TAXONOMY_PACKAGE_TYPE = PackageType("Taxonomy", "tpe")

TAXONOMY_PACKAGE_ABORTING_VALIDATIONS = (
    PackageValidation.validatePackageZipFormat,
    PackageValidation.validateZipFileSeparators,
    PackageValidation.validatePackageNotEncrypted,
    PackageValidation.validateTopLevelFiles,
    PackageValidation.validateTopLevelDirectories,
    PackageValidation.validateDuplicateEntries,
    PackageValidation.validateConflictingEntries,
    PackageValidation.validateEntries,
)

TAXONOMY_PACKAGE_NON_ABORTING_VALIDATIONS = (
    PackageValidation.validateMetadataDirectory,
)

def baseForElement(element):
    base = ""
    baseElt = element
    while baseElt is not None:
        if baseAttr := baseElt.get("{http://www.w3.org/XML/1998/namespace}base"):
            base = baseAttr if baseAttr.startswith("/") else baseAttr + base
        baseElt = baseElt.getparent()
    return base

def xmlLang(element):
    return (element.xpath('@xml:lang') + element.xpath('ancestor::*/@xml:lang') + [''])[0]

def langCloseness(l1, l2):
    _len = min(len(l1), len(l2))
    for i in range(0, _len):
        if l1[i] != l2[i]:
            return i
    return _len


def _parseFile(cntlr, parser, filepath, file, schemaUrl):
    """
    Returns tree from `file`, parsed with `parser`, and validated against the provided schema at `schemaUrl`.
    :return: Tree if parsed and validated, None if `schemaUrl` could not be loaded.
    """
    tree = etree.parse(file, parser=parser)
    # schema validate tp xml
    if cntlr.workingOnlineOrInCache(schemaUrl):
        xsdTree = etree.parse(schemaUrl, parser=parser)
        etree.XMLSchema(xsdTree).assertValid(tree)
    else:
        cntlr.addToLog(_("File could not be validated against the schema (%(schemaUrl)s) because the schema was not "
                         "found in the cache and Arelle is configured to work offline."),
                       messageArgs={"schemaUrl": schemaUrl},
                       messageCode="tpe:workingOffline",
                       file=filepath,
                       level=logging.ERROR)
    return tree


def parsePackage(
    cntlr: Cntlr,
    filesource: FileSource,
    metadataFile: str,
    fileBase: str,
    errors: list[str] | None = None,
) -> dict[str, str | dict[str, str]]:
    if errors is None:
        errors = []
    parser = lxmlResolvingParser(cntlr)
    catalogFile = metadataFile.replace('taxonomyPackage.xml','catalog.xml')
    remappings = _parseCatalog(cntlr, filesource, parser, catalogFile, fileBase, errors)
    pkg = _parsePackageMetadata(cntlr, filesource, parser, metadataFile, remappings, errors)
    return pkg


def _parsePackageMetadata(
    cntlr: Cntlr,
    filesource: FileSource,
    parser: etree.XMLParser,
    metadataFile: str,
    remappings: dict[str, str],
    errors: list[str],
) -> dict[str, str | dict[str, str]]:
    from arelle.FileSource import ArchiveFileIOError

    unNamedCounter = 1

    txmyPkgNSes = ("http://www.corefiling.com/xbrl/taxonomypackage/v1",
                   "http://xbrl.org/PWD/2014-01-15/taxonomy-package",
                   "http://xbrl.org/PWD/2015-01-14/taxonomy-package",
                   "http://xbrl.org/PR/2015-12-09/taxonomy-package",
                   "http://xbrl.org/2016/taxonomy-package",
                   "http://xbrl.org/WGWD/YYYY-MM-DD/taxonomy-package")

    pkg = {"remappings": remappings}

    currentLang = Locale.getLanguageCode()
    parser = lxmlResolvingParser(cntlr)
    try:
        metadataFileContent = filesource.file(metadataFile)[0] # URL in zip, plain file in file system or web
        tree = _parseFile(cntlr, parser, metadataFile, metadataFileContent, TP_XSD)
    except (etree.XMLSyntaxError, etree.DocumentInvalid, etree.XMLSchemaError) as err:
        cntlr.addToLog(_("Taxonomy package file syntax error %(error)s"),
                       messageArgs={"error": str(err)},
                       messageCode="tpe:invalidMetaDataFile",
                       file=os.path.basename(metadataFile),
                       level=logging.ERROR)
        errors.append("tpe:invalidMetaDataFile")
        return pkg
    except ArchiveFileIOError:
        return pkg

    root = tree.getroot()
    ns = root.tag.partition("}")[0][1:]
    nsPrefix = f"{{{ns}}}"

    if ns in  txmyPkgNSes:  # package file
        for eltName in ("identifier", "version", "license", "publisher", "publisherURL", "publisherCountry", "publicationDate"):
            pkg[eltName] = ''
            for m in root.iterchildren(tag=nsPrefix + eltName):
                if eltName == "license":
                    pkg[eltName] = m.get("name")
                else:
                    pkg[eltName] = (m.text or "").strip()
                break # take first entry if several
        for eltName in ("name", "description"):
            closest = ''
            closestLen = -1
            for m in root.iterchildren(tag=nsPrefix + eltName):
                s = (m.text or "").strip()
                eltLang = xmlLang(m)
                l = langCloseness(eltLang, currentLang)
                if l > closestLen:
                    closestLen = l
                    closest = s
                elif closestLen <= 0 and isinstance(eltLang, str) and eltLang.startswith("en"):
                    closest = s   # pick english if nothing better
            if not closest and eltName == "name":  # assign default name when none in taxonomy package
                assert isinstance(filesource.baseurl, str)
                closest = os.path.splitext(os.path.basename(filesource.baseurl))[0]
            pkg[eltName] = closest
        for eltName in ("supersededTaxonomyPackages", "versioningReports"):
            pkg[eltName] = []
        for m in root.iterchildren(tag=nsPrefix + "supersededTaxonomyPackages"):
            pkg['supersededTaxonomyPackages'] = [
                r.text.strip()
                for r in m.iterchildren(tag=nsPrefix + "taxonomyPackageRef")
                if isinstance(r.text, str)
            ]
        for m in root.iterchildren(tag=nsPrefix + "versioningReports"):
            pkg['versioningReports'] = [
                r.get("href")
                for r in m.iterchildren(tag=nsPrefix + "versioningReport")]
        # check for duplicate multi-lingual elements (among children of nodes)
        langElts = defaultdict(list)
        for n in root.iter(tag=nsPrefix + "*"):
            for eltName in ("name", "description", "publisher"):
                langElts.clear()
                for m in n.iterchildren(tag=nsPrefix + eltName):
                    langElts[xmlLang(m)].append(m)
                for lang, elts in langElts.items():
                    if not lang:
                        cntlr.addToLog(_("Multi-lingual element %(element)s has no in-scope xml:lang attribute"),
                                       messageArgs={"element": eltName},
                                       messageCode="tpe:missingLanguageAttribute",
                                       refs=[{"href":os.path.basename(metadataFile), "sourceLine":m.sourceline} for m in elts],
                                       level=logging.ERROR)
                        errors.append("tpe:missingLanguageAttribute")
                    elif len(elts) > 1:
                        cntlr.addToLog(_("Multi-lingual element %(element)s has multiple (%(count)s) in-scope xml:lang %(lang)s elements"),
                                       messageArgs={"element": eltName, "lang": lang, "count": len(elts)},
                                       messageCode="tpe:duplicateLanguagesForElement",
                                       refs=[{"href":os.path.basename(metadataFile), "sourceLine":m.sourceline} for m in elts],
                                       level=logging.ERROR)
                        errors.append("tpe:duplicateLanguagesForElement")
        del langElts # dereference

    else: # oasis catalog, use dirname as the package name
        # metadataFile may be a File object (with name) or string filename
        fileName = getattr(metadataFile, 'fileName',      # for FileSource named objects
                           getattr(metadataFile, 'name',  # for io.file named objects
                                   metadataFile))         # for string
        pkg["name"] = os.path.basename(os.path.dirname(fileName))
        pkg["description"] = "oasis catalog"
        pkg["version"] = "(none)"

    entryPoints = defaultdict(list)
    pkg["entryPoints"] = entryPoints

    for entryPointSpec in tree.iter(tag=nsPrefix + "entryPoint"):
        name = None
        closestLen = -1

        # find closest match name node given xml:lang match to current language or no xml:lang
        for nameNode in entryPointSpec.iter(tag=nsPrefix + "name"):
            s = (nameNode.text or "").strip()
            nameLang = xmlLang(nameNode)
            l = langCloseness(nameLang, currentLang)
            if l > closestLen:
                closestLen = l
                name = s
            elif closestLen <= 0 and isinstance(nameLang, str) and nameLang.startswith("en"):
                name = s   # pick english if nothing better

        if not name:
            name = _("<unnamed {0}>").format(unNamedCounter)
            unNamedCounter += 1

        for epDoc in entryPointSpec.iterchildren(nsPrefix + "entryPointDocument"):
            epUrl = epDoc.get('href')
            base = epDoc.get('{http://www.w3.org/XML/1998/namespace}base') # cope with xml:base
            resolvedUrl = urljoin(base, epUrl) if base else epUrl

            #perform prefix remappings
            remappedUrl = resolvedUrl
            longestPrefix = 0
            for mapFrom, mapTo in remappings.items():
                assert isinstance(remappedUrl, str)
                if remappedUrl.startswith(mapFrom):
                    prefixLength = len(mapFrom)
                    if prefixLength > longestPrefix:
                        _remappedUrl = remappedUrl[prefixLength:]
                        if len(_remappedUrl) > 0 and not _remappedUrl.startswith((os.sep, '/')) and not mapTo.endswith((os.sep, '/')):
                            _remappedUrl = mapTo + os.sep + _remappedUrl
                        else:
                            _remappedUrl = mapTo + _remappedUrl
                        longestPrefix = prefixLength
            if longestPrefix:
                remappedUrl = _remappedUrl.replace(os.sep, "/")  # always used as FileSource select

            # find closest language description
            closest = ''
            closestLen = -1
            for m in entryPointSpec.iterchildren(tag=nsPrefix + "description"):
                s = (m.text or "").strip()
                eltLang = xmlLang(m)
                l = langCloseness(eltLang, currentLang)
                if l > closestLen:
                    closestLen = l
                    closest = s
                elif closestLen <= 0 and isinstance(eltLang, str) and eltLang.startswith("en"):
                    closest = s   # pick english if nothing better
            if not closest and name:  # assign default name when none in taxonomy package
                closest = name
            entryPoints[name].append( (remappedUrl, resolvedUrl, closest) )

    return pkg


def _parseCatalog(
    cntlr: Cntlr,
    filesource: FileSource,
    parser: etree.XMLParser,
    catalogFile: str,
    fileBase: str,
    errors: list[str],
) -> dict[str, str]:
    from arelle.FileSource import ArchiveFileIOError
    remappings = {}
    rewriteTree = None
    try:
        _file = filesource.file(catalogFile)[0]
        rewriteTree = _parseFile(cntlr, parser, catalogFile, _file, CAT_XSD)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as err:
        cntlr.addToLog(_("Catalog file syntax error %(error)s"),
                        messageArgs={"error": str(err)},
                        messageCode="tpe:invalidCatalogFile",
                        file=os.path.basename(catalogFile),
                        level=logging.ERROR)
        errors.append("tpe:invalidCatalogFile")
    except ArchiveFileIOError:
        pass
    if rewriteTree is not None:
        for tag, prefixAttr, replaceAttr in (
            ("{urn:oasis:names:tc:entity:xmlns:xml:catalog}rewriteSystem", "systemIdStartString", "rewritePrefix"),
            ("{urn:oasis:names:tc:entity:xmlns:xml:catalog}rewriteURI", "uriStartString", "rewritePrefix")): # oasis catalog
            for m in rewriteTree.iter(tag=tag):
                prefixValue = m.get(prefixAttr)
                replaceValue = m.get(replaceAttr)
                if prefixValue and replaceValue is not None:
                    if prefixValue not in remappings:
                        base = baseForElement(m)
                        if base:
                            replaceValue = os.path.join(base, replaceValue)
                        if replaceValue and not isAbsolute(replaceValue):
                            # neither None nor ''
                            if not isLegacyAbs(replaceValue):
                                replaceValue = fileBase + replaceValue
                            if not isHttpUrl(replaceValue):
                                replaceValue = replaceValue.replace("/", os.sep)
                        _normedValue = cntlr.webCache.normalizeUrl(replaceValue)
                        if replaceValue.endswith(os.sep) and not _normedValue.endswith(os.sep):
                            _normedValue += os.sep
                        remappings[prefixValue] = _normedValue
                    else:
                        cntlr.addToLog(_("Package catalog duplicate rewrite start string %(rewriteStartString)s"),
                                    messageArgs={"rewriteStartString": prefixValue},
                                    messageCode="tpe:multipleRewriteURIsForStartString",
                                    file=os.path.basename(catalogFile),
                                    level=logging.ERROR)
                        errors.append("tpe:multipleRewriteURIsForStartString")

    return remappings


# taxonomy package manager
# plugin control is static to correspond to statically loaded modules
packagesJsonFile = None
packagesConfig = None
packagesConfigChanged = False
packagesMappings = {}
_cntlr = None

def init(cntlr: Cntlr, loadPackagesConfig: bool = True) -> None:
    global packagesJsonFile, packagesConfig, _cntlr
    if loadPackagesConfig:
        try:
            packagesJsonFile = cntlr.userAppDir + os.sep + "taxonomyPackages.json"
            with open(packagesJsonFile, encoding='utf-8') as f:
                packagesConfig = json.load(f)
            packagesConfigChanged = False
        except Exception:
            pass # on GAE no userAppDir, will always come here
    if not packagesConfig:
        packagesConfig = {  # savable/reloadable plug in configuration
            "packages": [], # list taxonomy packages loaded and their remappings
            "remappings": {}  # dict by prefix of remappings in effect
        }
        packagesConfigChanged = False # don't save until something is added to pluginConfig
    pluginMethodsForClasses = {} # dict by class of list of ordered callable function objects
    _cntlr = cntlr

def reset() -> None:  # force reloading modules and plugin infos
    if packagesConfig:
        packagesConfig.clear()  # dict of loaded module pluginInfo objects by module names
    if packagesMappings:
        packagesMappings.clear() # dict by class of list of ordered callable function objects

def orderedPackagesConfig():
    return dict(
        (('packages', [dict(sorted(_packageInfo.items(),
                                          key=lambda k: {'name': '01',
                                                         'status': '02',
                                                         'version': '03',
                                                         'fileDate': '04',
                                                         'license': '05',
                                                         'URL': '06',
                                                         'description': '07',
                                                         "publisher": '08',
                                                         "publisherURL": '09',
                                                         "publisherCountry": '10',
                                                         "publicationDate": '11',
                                                         "supersededTaxonomyPackages": '12',
                                                         "versioningReports": '13',
                                                         'remappings': '14',
                                                         }.get(k[0],k[0])))
                       for _packageInfo in packagesConfig['packages']]),
         ('remappings',dict(sorted(packagesConfig['remappings'].items())))))

def save(cntlr: Cntlr) -> None:
    global packagesConfigChanged
    if packagesConfigChanged and cntlr.hasFileSystem:
        with open(packagesJsonFile, "w", encoding='utf-8') as f:
            jsonStr = str(json.dumps(orderedPackagesConfig(), ensure_ascii=False, indent=2)) # might not be unicode in 2.7
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

def validateTaxonomyPackage(cntlr, filesource, errors=[]) -> bool:
        numErrorsOnEntry = len(errors)
        for validator in TAXONOMY_PACKAGE_ABORTING_VALIDATIONS:
            if validation := validator(TAXONOMY_PACKAGE_TYPE, filesource):
                cntlr.addToLog(
                    validation.msg,
                    messageCode=validation.codes,
                    messageArgs=validation.args,
                    file=filesource.urlBasename,
                    level=validation.level.name,
                )
                errors.append(validation.codes)
                return False
        for validator in TAXONOMY_PACKAGE_NON_ABORTING_VALIDATIONS:
            if validation := validator(TAXONOMY_PACKAGE_TYPE, filesource):
                cntlr.addToLog(
                    validation.msg,
                    messageCode=validation.codes,
                    messageArgs=validation.args,
                    file=filesource.urlBasename,
                    level=validation.level.name,
                )
                errors.append(validation.codes)

        _dir = filesource.dir or []
        if not any(f.endswith('/META-INF/taxonomyPackage.xml') for f in _dir):
            messageCode = "tpe:metadataFileNotFound"
            cntlr.addToLog(_("Taxonomy package does not contain a metadata file */META-INF/taxonomyPackage.xml"),
                           messageCode=messageCode,
                           file=filesource.urlBasename,
                           level=logging.ERROR)
            errors.append(messageCode)
        return len(errors) == numErrorsOnEntry


def discoverPackageFiles(filesource: FileSource) -> list[str]:
    return [e for e in filesource.dir or [] if e.endswith("/META-INF/taxonomyPackage.xml")]


def packageInfo(cntlr, URL, reload=False, packageManifestName=None, errors=[]):
    #TODO several directories, eg User Application Data
    packageFilename = _cntlr.webCache.getfilename(URL, reload=reload, normalize=True)
    if packageFilename:
        from arelle.FileSource import TAXONOMY_PACKAGE_FILE_NAMES, archiveFilenameParts, openFileSource
        filesource = None
        try:
            parts = archiveFilenameParts(packageFilename)
            if parts is not None:
                sourceFileSource = openFileSource(parts[0], _cntlr)
                sourceFileSource.open()
                fileDateTuple = sourceFileSource.fs.getinfo(parts[1]).date_time + (0,0,0)
            else:
                sourceFileSource = None
                fileDateTuple = time.gmtime(os.path.getmtime(packageFilename))
            filesource = openFileSource(packageFilename, _cntlr, sourceFileSource=sourceFileSource)
            if sourceFileSource:
                sourceFileSource.close()
            # allow multiple manifests [[metadata, prefix]...] for multiple catalogs
            packages = []
            if filesource.isZip:
                validateTaxonomyPackage(cntlr, filesource, errors)
                packageFiles = discoverPackageFiles(filesource)
                if not packageFiles:
                    # look for pre-PWD packages
                    _dir = filesource.dir or []
                    _metaInf = f'{os.path.splitext(os.path.basename(packageFilename))[0]}/META-INF/'
                    if packageManifestName:
                        # pre-pwd
                        packageFiles = [fileName
                                        for fileName in _dir
                                        if fnmatch(fileName, packageManifestName)]
                    elif _metaInf + 'taxonomyPackage.xml' in _dir:
                        # PWD taxonomy packages
                        packageFiles = [_metaInf + 'taxonomyPackage.xml']
                    elif 'META-INF/taxonomyPackage.xml' in _dir:
                        # root-level META-INF taxonomy packages
                        packageFiles = ['META-INF/taxonomyPackage.xml']
                if len(packageFiles) < 1:
                    raise OSError(_("Taxonomy package contained no metadata file: {0}.")
                                  .format(', '.join(packageFiles)))
                # if current package files found, remove any nonconforming package files
                if any(pf.startswith('_metaInf') for pf in packageFiles) and any(not pf.startswith(_metaInf) for pf in packageFiles):
                    packageFiles = [pf for pf in packageFiles if pf.startswith(_metaInf)]
                elif any(pf.startswith('META-INF/') for pf in packageFiles) and any(not pf.startswith('META-INF/') for pf in packageFiles):
                    packageFiles = [pf for pf in packageFiles if pf.startswith('META-INF/')]

                for packageFile in packageFiles:
                    assert isinstance(filesource.url, str)
                    packageFileUrl = filesource.url + os.sep + packageFile
                    packageFilePrefix = os.sep.join(os.path.split(packageFile)[:-1])
                    if packageFilePrefix:
                        packageFilePrefix += os.sep
                    assert isinstance(filesource.baseurl, str)
                    packageFilePrefix = filesource.baseurl + os.sep +  packageFilePrefix
                    packages.append([packageFileUrl, packageFilePrefix, packageFile])
            else:
                cntlr.addToLog(_("Taxonomy package is not a zip file."),
                               messageCode="tpe:invalidArchiveFormat",
                               file=os.path.basename(packageFilename),
                               level=logging.ERROR)
                errors.append("tpe:invalidArchiveFormat")
                assert isinstance(filesource.url, str)
                if (os.path.basename(filesource.url) in TAXONOMY_PACKAGE_FILE_NAMES or # individual manifest file
                      (os.path.basename(filesource.url) == "taxonomyPackage.xml" and
                       os.path.basename(os.path.dirname(filesource.url)) == "META-INF")):
                    packageFile = packageFileUrl = filesource.url
                    packageFilePrefix = os.path.dirname(packageFile)
                    if packageFilePrefix:
                        packageFilePrefix += os.sep
                    packages.append([packageFileUrl, packageFilePrefix, ""])
                else:
                    raise OSError(_("File must be a taxonomy package (zip file), catalog file, or manifest (): {0}.")
                                  .format(packageFilename, ', '.join(TAXONOMY_PACKAGE_FILE_NAMES)))
            remappings = {}
            packageNames = []
            descriptions = []
            for packageFileUrl, packageFilePrefix, packageFile in packages:
                parsedPackage = parsePackage(_cntlr, filesource, packageFileUrl, packageFilePrefix, errors)
                if parsedPackage:
                    packageNames.append(parsedPackage['name'])
                    if parsedPackage.get('description'):
                        descriptions.append(parsedPackage['description'])
                    for prefix, remapping in parsedPackage["remappings"].items():
                        if prefix not in remappings:
                            remappings[prefix] = remapping
                        else:
                            cntlr.addToLog("Package mapping duplicate rewrite start string %(rewriteStartString)s",
                                           messageArgs={"rewriteStartString": prefix},
                                           messageCode="arelle.packageDuplicateMapping",
                                           file=os.path.basename(URL),
                                           level=logging.ERROR)
                            errors.append("arelle.packageDuplicateMapping")
            if not parsedPackage:
                return None
            package = {'name': ", ".join(packageNames),
                       'status': 'enabled',
                       'identifier': parsedPackage.get('identifier'),
                       'version': parsedPackage.get('version'),
                       'license': parsedPackage.get('license'),
                       'fileDate': time.strftime('%Y-%m-%dT%H:%M:%S UTC', fileDateTuple),
                       'URL': URL,
                       'entryPoints': parsedPackage.get('entryPoints', {}),
                       'manifestName': packageManifestName,
                       'description': "; ".join(descriptions),
                       'publisher': parsedPackage.get('publisher'),
                       'publisherURL': parsedPackage.get('publisherURL'),
                       'publisherCountry': parsedPackage.get('publisherCountry'),
                       'publicationDate': parsedPackage.get('publicationDate'),
                       'supersededTaxonomyPackages': parsedPackage.get('supersededTaxonomyPackages'),
                       'versioningReports': parsedPackage.get('versioningReports'),
                       'remappings': remappings,
                       }
            filesource.close()
            return package
        except (OSError, etree.XMLSyntaxError):
            pass
        if filesource:
            filesource.close()
    return None

def rebuildRemappings(cntlr):
    remappings = packagesConfig["remappings"]
    remappings.clear()
    remapOverlapUrls = [] # (prefix, packageURL, rewriteString)
    for _packageInfo in packagesConfig["packages"]:
        _packageInfoURL = _packageInfo['URL']
        if _packageInfo['status'] == 'enabled':
            for prefix, remapping in _packageInfo['remappings'].items():
                remappings[prefix] = remapping
                remapOverlapUrls.append( (prefix, _packageInfoURL, remapping) )
    remapOverlapUrls.sort()
    for i, _remap in enumerate(remapOverlapUrls):
        _prefix, _packageURL, _rewrite = _remap
        for j in range(i-1, -1, -1):
            _prefix2, _packageURL2, _rewrite2 = remapOverlapUrls[j]
            if (_packageURL != _packageURL2 and _prefix and _prefix2 and
                (_prefix.startswith(_prefix2) or _prefix2.startswith(_prefix))):
                _url1 = os.path.basename(_packageURL)
                _url2 = os.path.basename(_packageURL2)
                if _url1 == _url2: # use full file names
                    _url1 = _packageURL
                    _url2 = _packageURL2
                cntlr.addToLog(_("Packages overlap the same rewrite start string %(rewriteStartString)s")
                               if _prefix == _prefix2 else
                               _("Packages overlap rewrite start strings %(rewriteStartString)s and %(rewriteStartString2)s"),
                               messageArgs={"rewriteStartString": _prefix, "rewriteStartString2": _prefix2},
                               messageCode="arelle.packageRewriteOverlap",
                               file=(_url1, _url2),
                               level=logging.WARNING)


def isMappedUrl(url):
    return (packagesConfig is not None and url is not None and
            any(url.startswith(mapFrom) and not url.startswith(mapTo) # prevent recursion in mapping for url hosted Packages
                for mapFrom, mapTo in packagesConfig.get('remappings', {}).items()))

def mappedUrl(url):
    if packagesConfig is not None and url is not None:
        longestPrefix = 0
        for mapFrom, mapTo in packagesConfig.get('remappings', {}).items():
            if url.startswith(mapFrom):
                if url.startswith(mapTo):
                    return url # recursive mapping, this is already mapped
                prefixLength = len(mapFrom)
                if prefixLength > longestPrefix:
                    mappedUrl = mapTo + url[prefixLength:]
                    longestPrefix = prefixLength
        if longestPrefix:
            return mappedUrl
    return url

def addPackage(cntlr, url, packageManifestName=None):
    newPackageInfo = packageInfo(cntlr, url, packageManifestName=packageManifestName)
    if newPackageInfo and newPackageInfo.get("identifier"):
        identifier = newPackageInfo.get("identifier")
        j = -1
        packagesList = packagesConfig["packages"]
        for i, _packageInfo in enumerate(packagesList):
            if _packageInfo['identifier'] == identifier:
                j = i
                break
        if 0 <= j < len(packagesList): # replace entry
            packagesList[j] = newPackageInfo
        else:
            packagesList.append(newPackageInfo)
        global packagesConfigChanged
        packagesConfigChanged = True
        return newPackageInfo
    return None

def reloadPackageModule(cntlr, name):
    packageUrls = []
    packagesList = packagesConfig["packages"]
    for _packageInfo in packagesList:
        if _packageInfo.get('name') == name:
            packageUrls.append(_packageInfo['URL'])
    result = False
    for url in packageUrls:
        addPackage(cntlr, url)
        result = True
    return result

def removePackageModule(cntlr, name):
    packageIndices = []
    packagesList = packagesConfig["packages"]
    for i, _packageInfo in enumerate(packagesList):
        if _packageInfo.get('name') == name:
            packageIndices.insert(0, i) # must remove in reverse index order
    result = False
    for i in packageIndices:
        del packagesList[i]
        result = True
    if result:
        global packagesConfigChanged
        packagesConfigChanged = True
    return result
