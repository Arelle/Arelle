'''
Separated on Jul 28, 2013 from DialogOpenArchive.py

See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
from typing import TYPE_CHECKING
import sys, os, io, time, json, logging, zipfile
from collections import defaultdict
from fnmatch import fnmatch
from lxml import etree
import regex as re
from urllib.parse import urljoin
openFileSource = None
from arelle import Locale, XmlUtil
from arelle.PythonUtil import flattenSequence
from arelle.UrlUtil import isAbsolute, isHttpUrl
from arelle.XmlValidate import lxmlResolvingParser
ArchiveFileIOError = None
try:
    from collections import OrderedDict
except ImportError:
    OrderedDict = dict # python 3.0 lacks OrderedDict, json file will be in weird order

TP_XSD = "http://www.xbrl.org/2016/taxonomy-package.xsd"
CAT_XSD = "http://www.xbrl.org/2016/taxonomy-package-catalog.xsd"

if TYPE_CHECKING:
    from arelle.Cntlr import Cntlr

EMPTYDICT = {}

TAXONOMY_PACKAGE_FILE_NAMES = ('.taxonomyPackage.xml', 'catalog.xml') # pre-PWD packages

# allow for future report packages which might have META-INF at root level
reportPackageExistencePattern = re.compile(r"^(?:[^/]+/)?META-INF/reportPackage.json$|^[^/]+/reports/")
reportPackageFilePattern = re.compile(r"^(?:([^/]+)/)?META-INF/reportPackage.json$")
reportPackageReportsPattern = re.compile(r"^(([^/]+)/reports/)")

reportPackageDocTypeExtensions = {
    "https://xbrl.org/report-package/2023/xbri": (".xbri",),
    "https://xbrl.org/report-package/2023/xbr":  (".xbr",),
    "https://xbrl.org/report-package/2023":      (".zip", ".ZIP")
    }

inlineExtensions = {".xhtml", ".html", ".htm"}
allExtensions = {".xbrl", ".xhtml", ".html", ".htm", ".json"}

UTF_7_16_Bytes_Pattern = re.compile(br"(?P<utf16>(^([\x00][^\x00])+$)|(^([^\x00][\x00])+$))|(?P<utf7>^\s*\+AHs-)")
EBCDIC_Bytes_Pattern = re.compile(b"^[\x40\x4a-\x4f\x50\x5a-\x5f\x60-\x61\x6a-\x6f\x79-\x7f\x81-\x89\x8f\x91-\x99\xa1-\xa9\xb0\xba-\xbb\xc1-\xc9\xd1-\xd9\xe0\xe2-\xe9\xf0-\xf9\xff\x0a\x0d]+$")
NEVER_EBCDIC_Bytes_Pattern = re.compile(b"[\x30-\x31\x3e\x41-\x49\x51-\x59\x62-\x69\x70-\x78\x80\x8a-\x8e\x90\x9a-\x9f\xa0\xaa-\xaf\xb1-\xb9\xbc-\xbf\xca-\xcf\xda-\xdf\xe1\xea-\xef\xfa-\xfe]")


def baseForElement(element):
    base = ""
    baseElt = element
    while baseElt is not None:
        baseAttr = baseElt.get("{http://www.w3.org/XML/1998/namespace}base")
        if baseAttr:
            if baseAttr.startswith("/"):
                base = baseAttr
            else:
                base = baseAttr + base
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


def parseTaxonomyPackage(cntlr, filesource, metadataFile, fileBase, errors=[]):
    global ArchiveFileIOError
    if ArchiveFileIOError is None:
        from arelle.FileSource import ArchiveFileIOError

    unNamedCounter = 1

    txmyPkgNSes = ("http://www.corefiling.com/xbrl/taxonomypackage/v1",
                   "http://xbrl.org/PWD/2014-01-15/taxonomy-package",
                   "http://xbrl.org/PWD/2015-01-14/taxonomy-package",
                   "http://xbrl.org/PR/2015-12-09/taxonomy-package",
                   "http://xbrl.org/2016/taxonomy-package",
                   "http://xbrl.org/WGWD/YYYY-MM-DD/taxonomy-package")
    catalogNSes = ("urn:oasis:names:tc:entity:xmlns:xml:catalog",)

    pkg = {}

    currentLang = Locale.getLanguageCode()
    _file = filesource.file(metadataFile)[0] # URL in zip, plain file in file system or web
    parser = lxmlResolvingParser(cntlr)
    try:
        tree = _parseFile(cntlr, parser, metadataFile, _file, TP_XSD)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as err:
        cntlr.addToLog(_("Taxonomy package file syntax error %(error)s"),
                       messageArgs={"error": str(err)},
                       messageCode="tpe:invalidMetaDataFile",
                       file=os.path.basename(metadataFile),
                       level=logging.ERROR)
        errors.append("tpe:invalidMetaDataFile")
        return pkg

    root = tree.getroot()
    ns = root.tag.partition("}")[0][1:]
    nsPrefix = "{{{}}}".format(ns)

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
            closestLen = 0
            for m in root.iterchildren(tag=nsPrefix + eltName):
                s = (m.text or "").strip()
                eltLang = xmlLang(m)
                l = langCloseness(eltLang, currentLang)
                if l > closestLen:
                    closestLen = l
                    closest = s
                elif closestLen == 0 and eltLang.startswith("en"):
                    closest = s   # pick english if nothing better
            if not closest and eltName == "name":  # assign default name when none in taxonomy package
                closest = os.path.splitext(os.path.basename(filesource.baseurl))[0]
            pkg[eltName] = closest
        for eltName in ("supersededTaxonomyPackages", "versioningReports"):
            pkg[eltName] = []
        for m in root.iterchildren(tag=nsPrefix + "supersededTaxonomyPackages"):
            pkg['supersededTaxonomyPackages'] = [
                r.text.strip()
                for r in m.iterchildren(tag=nsPrefix + "taxonomyPackageRef")]
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

    remappings = {}
    rewriteTree = tree
    catalogFile = metadataFile
    if ns in ("http://xbrl.org/PWD/2015-01-14/taxonomy-package",
              "http://xbrl.org/PR/2015-12-09/taxonomy-package",
              "http://xbrl.org/WGWD/YYYY-MM-DD/taxonomy-package",
              "http://xbrl.org/2016/taxonomy-package",
              "http://xbrl.org/REC/2016-04-19/taxonomy-package"):
        catalogFile = metadataFile.replace('taxonomyPackage.xml','catalog.xml')
        try:
            _file = filesource.file(catalogFile)[0]
            rewriteTree = _parseFile(cntlr, parser, catalogFile, _file, CAT_XSD)
        except (etree.XMLSyntaxError, etree.DocumentInvalid) as err:
            cntlr.addToLog(_("Catalog file syntax error %(error)s"),
                           messageArgs={"error": str(err)},
                           messageCode="tpe:invalidCatalogFile",
                           file=os.path.basename(metadataFile),
                           level=logging.ERROR)
            errors.append("tpe:invalidCatalogFile")
        except ArchiveFileIOError:
            pass
    for tag, prefixAttr, replaceAttr in (
         (nsPrefix + "remapping", "prefix", "replaceWith"), # taxonomy package
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
                    if replaceValue: # neither None nor ''
                        if not isAbsolute(replaceValue):
                            if not os.path.isabs(replaceValue):
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


    pkg["remappings"] = remappings

    entryPoints = defaultdict(list)
    pkg["entryPoints"] = entryPoints

    for entryPointSpec in tree.iter(tag=nsPrefix + "entryPoint"):
        name = None
        closestLen = 0

        # find closest match name node given xml:lang match to current language or no xml:lang
        for nameNode in entryPointSpec.iter(tag=nsPrefix + "name"):
            s = (nameNode.text or "").strip()
            nameLang = xmlLang(nameNode)
            l = langCloseness(nameLang, currentLang)
            if l > closestLen:
                closestLen = l
                name = s
            elif closestLen == 0 and nameLang.startswith("en"):
                name = s   # pick english if nothing better

        if not name:
            name = _("<unnamed {0}>").format(unNamedCounter)
            unNamedCounter += 1

        epDocCount = 0
        for epDoc in entryPointSpec.iterchildren(nsPrefix + "entryPointDocument"):
            epUrl = epDoc.get('href')
            base = epDoc.get('{http://www.w3.org/XML/1998/namespace}base') # cope with xml:base
            if base:
                resolvedUrl = urljoin(base, epUrl)
            else:
                resolvedUrl = epUrl

            epDocCount += 1

            #perform prefix remappings
            remappedUrl = resolvedUrl
            longestPrefix = 0
            for mapFrom, mapTo in remappings.items():
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
            closestLen = 0
            for m in entryPointSpec.iterchildren(tag=nsPrefix + "description"):
                s = (m.text or "").strip()
                eltLang = xmlLang(m)
                l = langCloseness(eltLang, currentLang)
                if l > closestLen:
                    closestLen = l
                    closest = s
                elif closestLen == 0 and eltLang.startswith("en"):
                    closest = s   # pick english if nothing better
            if not closest and name:  # assign default name when none in taxonomy package
                closest = name
            entryPoints[name].append( (remappedUrl, resolvedUrl, closest) )

    return pkg

# taxonomy package manager
# plugin control is static to correspond to statically loaded modules
packagesJsonFile = None
packagesConfig = None
packagesConfigChanged = False
packagesMappings = {}
_cntlr = None

def init(cntlr: Cntlr, loadPackagesConfig: bool = True) -> None:
    global packagesJsonFile, packagesConfig, packagesMappings, _cntlr
    if loadPackagesConfig:
        try:
            packagesJsonFile = cntlr.userAppDir + os.sep + "taxonomyPackages.json"
            with io.open(packagesJsonFile, 'rt', encoding='utf-8') as f:
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
         ('remappings',OrderedDict(sorted(packagesConfig['remappings'].items())))))

def save(cntlr: Cntlr) -> None:
    global packagesConfigChanged
    if packagesConfigChanged and cntlr.hasFileSystem:
        with io.open(packagesJsonFile, 'wt', encoding='utf-8') as f:
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

def validateTaxonomyPackage(cntlr, filesource, packageFiles=[], errors=[]) -> bool:
    numErrorsOnEntry = len(errors)
    # single top level directory
    _dir = filesource.dir
    topLevels = set(f.partition('/')[0] for f in _dir)
    topLevelFiles = set(f for f in topLevels if f in _dir) # have no trailing /, not a directory
    topLevelDirectories = topLevels - topLevelFiles
    if topLevelFiles:
        cntlr.addToLog(_("Taxonomy package contains %(count)s top level file(s):  %(topLevelFiles)s"),
                       messageArgs={"count": len(topLevelFiles),
                                    "topLevelFiles": ', '.join(sorted(topLevelFiles))},
                       messageCode="tpe:invalidDirectoryStructure",
                       file=os.path.basename(filesource.url),
                       level=logging.ERROR)
        errors.append("tpe:invalidDirectoryStructure")
    if len(topLevelDirectories) != 1:
        cntlr.addToLog(_("Taxonomy package contains %(count)s top level directories:  %(topLevelDirectories)s"),
                       messageArgs={"count": len(topLevelDirectories),
                                    "topLevelDirectories": ', '.join(sorted(topLevelDirectories))},
                       messageCode="tpe:invalidDirectoryStructure",
                       file=os.path.basename(filesource.url),
                       level=logging.ERROR)
        if not topLevelFiles:
            errors.append("tpe:invalidDirectoryStructure")
    if not any('META-INF' in f.split('/')[1:][:1] for f in _dir): # only check child of top level
        cntlr.addToLog(_("Taxonomy package top-level directory does not contain a subdirectory META-INF"),
                       messageCode="tpe:metadataDirectoryNotFound",
                       file=os.path.basename(filesource.baseurl),
                       level=logging.ERROR)
        errors.append("tpe:metadataDirectoryNotFound")
    elif any(f.endswith('/META-INF/taxonomyPackage.xml') for f in _dir):
        for f in _dir:
            if f.endswith('/META-INF/taxonomyPackage.xml'):
                packageFiles.append(f)
    else:
        cntlr.addToLog(_("Taxonomy package does not contain a metadata file */META-INF/taxonomyPackage.xml"),
                       messageCode="tpe:metadataFileNotFound",
                       file=os.path.basename(filesource.url),
                       level=logging.ERROR)
        errors.append("tpe:metadataFileNotFound")
    return len(errors) == numErrorsOnEntry

def validateReportPackage(filesource, errors=[]) -> bool:
    cntlr = filesource.cntlr
    def checkLoadJson(path):
        def loadDict(keyValuePairs):
            _dict = {}
            for key, value in keyValuePairs:
                if key not in _dict:
                    _dict[key] = value
                else:
                    cntlr.addToLog(_("JSON duplicated key %(key)s"),
                                   messageCode="rpe:invalidJSON",
                                   file=os.path.basename(path),
                                   messageArgs={"key": key},
                                   level=logging.ERROR)
                    errors.append("rpe:invalidJSON")
            return _dict
        _filePath = f"{filesource.basefile}/{path}"
        _file = filesource.file(_filePath, binary=True)[0]
        bytes = _file.read(16) # test encoding
        m = EBCDIC_Bytes_Pattern.match(bytes)
        if m and not NEVER_EBCDIC_Bytes_Pattern.findall(bytes):
            cntlr.addToLog(_("reportPackage.json file MUST use utf-8 encoding, appears to be EBCDIC"),
                           messageCode="rpe:invalidJSON",
                           file=os.path.basename(path),
                           level=logging.ERROR)
            errors.append("rpe:invalidJSON")
            return False
        m = UTF_7_16_Bytes_Pattern.match(bytes)
        if m:
            cntlr.addToLog(_("reportPackage.json file MUST use utf-8 encoding, appears to be %(encoding)s"),
                           messageCode="rpe:invalidJSON",
                           messageArgs={"encoding": m.lastgroup},
                           file=os.path.basename(filesource.baseurl),
                           level=logging.ERROR)
            errors.append("rpe:invalidJSON")
            return False
        _file.close()
        _file = filesource.file(_filePath, encoding='utf-8-sig')[0]
        try:
            return json.load(_file, object_pairs_hook=loadDict)
        except json.JSONDecodeError as ex:
            cntlr.addToLog(_("JSON syntax error %(error)s"),
                           messageCode="rpe:invalidJSON",
                           file=os.path.basename(filesource.baseurl),
                           messageArgs={"error": str(ex)},
                           level=logging.ERROR)
            errors.append("rpe:invalidJSON")
            return None
        except UnicodeDecodeError as ex:
            cntlr.addToLog(_("reportPackage.json file MUST use utf-8 encoding, appears to be %(encoding)s"),
                           messageCode="rpe:invalidJSON",
                           messageArgs={"encoding": m.lastgroup if m else "unknown"},
                           file=os.path.basename(filesource.baseurl),
                           level=logging.ERROR)
            errors.append("rpe:invalidJSON")
            return None
    numErrorsOnEntry = len(errors)
    dir = filesource.dir
    rptPkgExt = os.path.splitext(filesource.baseurl)[1]
    STLD = rptPkgFile = rptDir = None
    for f in (dir or []):
        m = reportPackageFilePattern.match(f)
        if m:
            rptPkgFile = f  # report package
            STLD = m.group(1)
            if STLD:
                rptDir = f"{STLD}/reports/"
            else:
                rptDir = "reports/" # future root-level reports directory
            break
    if rptDir is None:
        for f in (dir or []):
            m = reportPackageReportsPattern.match(f)
            if m:
                rptDir = m.group(1)
                STLD = m.group(2)
                break
    rptPkgObj = {"documentInfo":{"documentType":"https://xbrl.org/report-package/2023"}} #default doc type
    if rptPkgFile is not None:
        rptPkgObj = checkLoadJson(rptPkgFile)
        if rptPkgObj is None:
            return False
    if rptPkgFile:
        pkgFilePath = f"{filesource.basefile}/{rptPkgFile}"
    elif rptDir is None:
        if cntlr.modelManager.validateRptPkg:
            cntlr.addToLog(_("Zip file is not a report package and is not processed further"),
                           messageCode="arelle:notReportPackage",
                           file=os.path.basename(filesource.baseurl),
                           level=logging.INFO)
        return False # not a report package, might be a taxonomy package
    docTypeUri = rptPkgObj["documentInfo"].get("documentType") if isinstance(rptPkgObj,dict) and isinstance(rptPkgObj.get("documentInfo"),dict) else None
    if not isinstance(docTypeUri, str):
        cntlr.addToLog(_("Unsupported documentType type: %(docTypeType)s"),
                       messageCode="rpe:invalidJSONStructure",
                       file=os.path.basename(filesource.baseurl),
                       messageArgs={"docTypeType": type(docTypeUri).__name__},
                       level=logging.ERROR)
        errors.append("rpe:invalidJSONStructure")
    elif rptPkgExt in (".xbri", ".xbr") and rptPkgFile is None:
        cntlr.addToLog(_("The report package file extension %(extension)s MUST have a report package type specified, but it is absent."),
                       messageCode="rpe:documentTypeFileExtensionMismatch",
                       file=os.path.basename(filesource.baseurl),
                       messageArgs={"extension": rptPkgExt},
                       level=logging.ERROR)
        errors.append("rpe:documentTypeFileExtensionMismatch")
    elif STLD is None:
        cntlr.addToLog(_("Unsupported META-INF as STLD."),
                       messageCode="rpe:unsupportedReportPackageVersion",
                       file=os.path.basename(filesource.baseurl),
                       level=logging.ERROR)
        errors.append("rpe:unsupportedReportPackageVersion")
    elif docTypeUri not in reportPackageDocTypeExtensions:
        cntlr.addToLog(_("Unsupported report package document type: %(docTypeUri)s"),
                       messageCode="rpe:unsupportedReportPackageVersion",
                       file=os.path.basename(filesource.baseurl),
                       messageArgs={"docTypeUri": docTypeUri},
                       level=logging.ERROR)
        errors.append("rpe:unsupportedReportPackageVersion")
    elif rptPkgExt not in reportPackageDocTypeExtensions[docTypeUri]:
        cntlr.addToLog(_("The report package file extension MUST match the report package type specified by the report package document type URI, %(docTypeUri)s"),
                       messageCode="rpe:documentTypeFileExtensionMismatch",
                       file=os.path.basename(filesource.baseurl),
                       messageArgs={"docTypeUri": docTypeUri},
                       level=logging.ERROR)
        errors.append("rpe:documentTypeFileExtensionMismatch")
    # discover reports
    rpts = []
    if not rptDir:
        pass # no reports in this report package
    elif not any(f.startswith(rptDir) for f in dir):
        cntlr.addToLog(_("A report package MUST contain a directory called reports as a child of the STLD, %(STLD)s"),
                       messageCode="rpe:missingReportsDirectory",
                       file=os.path.basename(filesource.baseurl),
                       messageArgs={"STLD": STLD or "(root)"},
                       level=logging.ERROR)
        errors.append("rpe:missingReportsDirectory")
    else:
        rptInRptDirPtrn = re.compile(f"{rptDir}[^/.]*[.](xbrl|xhtml|html|htm|json)$")
        rptSubdirPtrn = re.compile(f"{rptDir}([^/]+)/")
        rpts = [f for f in dir if rptInRptDirPtrn.match(f)] # each file is separate report/IXDS even if inline
        if not rpts: # if no top level reports look in subdirectories
            subdirs = sorted(set(m.group(1) for f in dir for m in (rptSubdirPtrn.match(f),) if m is not None))
            for subdir in subdirs:
                rptInRptSubdirPtrn = re.compile(f"{rptDir}{subdir}/[^/.]*[.](xbrl|xhtml|html|jtm|json)$")
                rptsInSubdir = [f for f in dir if rptInRptSubdirPtrn.match(f)]
                if not (all(os.path.splitext(f)[1] in inlineExtensions for f in rptsInSubdir) or
                        0 <= sum(os.path.splitext(f)[1] in allExtensions for f in rptsInSubdir) <= 1):
                    cntlr.addToLog(_("A report package reports subdirectory MUST no more than one xbrl report, %(dir)s"),
                                   messageCode="rpe:multipleReportsInSubdirectory",
                                   file=os.path.basename(filesource.baseurl),
                                   messageArgs={"dir": subdir},
                                   level=logging.ERROR)
                    errors.append("rpe:multipleReportsInSubdirectory")
                ixRpt = [f for f in rptsInSubdir if  os.path.splitext(f)[1] in inlineExtensions]
                if ixRpt:
                    if len(ixRpt) > 1: # IXDS
                        rpts.append(ixRpt) # add report/IXDS to reports
                    else:
                        rpts.append(ixRpt[0]) # single-file inline report
                for f in rptsInSubdir:
                    if os.path.splitext(f)[1] in (allExtensions - inlineExtensions):
                        rpts.append(f)
        numRpts = len(rpts)
        if numRpts == 0:
            cntlr.addToLog(_("A report package MUST contain at least one xbrl report."),
                           messageCode="rpe:missingReport",
                           file=os.path.basename(filesource.baseurl),
                           level=logging.ERROR)
            errors.append("rpe:missingReport")
        elif rptPkgExt in (".xbri", ".xbr") and numRpts > 1:
            cntlr.addToLog(_("An inline or non-inline report package MUST contain only one xbrl report but %(count)s were found."),
                           messageCode="rpe:multipleReports",
                           file=os.path.basename(filesource.baseurl),
                           messageArgs={"count": str(numRpts)},
                           level=logging.ERROR)
            errors.append("rpe:multipleReports")
        if rptPkgExt == ".xbri" and not all (os.path.splitext(f)[1] in inlineExtensions for f in flattenSequence(rpts)):
            cntlr.addToLog(_("An inline report package MUST only contain only inline xbrl reports."),
                           messageCode="rpe:incorrectReportType",
                           file=os.path.basename(filesource.baseurl),
                           level=logging.ERROR)
            errors.append("rpe:incorrectReportType")
        elif rptPkgExt == ".xbr" and not all (os.path.splitext(f)[1] in (allExtensions - inlineExtensions) for f in flattenSequence(rpts)):
            cntlr.addToLog(_("An inline report package MUST only contain only non-inline xbrl reports."),
                           messageCode="rpe:incorrectReportType",
                           file=os.path.basename(filesource.baseurl),
                           level=logging.ERROR)
            errors.append("rpe:incorrectReportType")
    for f in rpts:
        if isinstance(f, str) and f.endswith(".json"):
            checkLoadJson(f)
    return len(errors) == numErrorsOnEntry

def packageInfo(cntlr, URL, reload=False, packageManifestName=None, errors=[]):
    #TODO several directories, eg User Application Data
    packageFilename = _cntlr.webCache.getfilename(URL, reload=reload, normalize=True)
    if packageFilename:
        from arelle.FileSource import TAXONOMY_PACKAGE_FILE_NAMES
        filesource = None
        try:
            global openFileSource
            if openFileSource is None:
                from arelle.FileSource import openFileSource
            from arelle.FileSource import archiveFilenameParts
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
            packageFiles = []
            if filesource.isZip:
                validateTaxonomyPackage(cntlr, filesource, packageFiles, errors)
                if not packageFiles:
                    # look for pre-PWD packages
                    _dir = filesource.dir
                    _metaInf = '{}/META-INF/'.format(
                                os.path.splitext(os.path.basename(packageFilename))[0])
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
                    raise IOError(_("Taxonomy package contained no metadata file: {0}.")
                                  .format(', '.join(packageFiles)))
                # if current package files found, remove any nonconforming package files
                if any(pf.startswith('_metaInf') for pf in packageFiles) and any(not pf.startswith(_metaInf) for pf in packageFiles):
                    packageFiles = [pf for pf in packageFiles if pf.startswith(_metaInf)]
                elif any(pf.startswith('META-INF/') for pf in packageFiles) and any(not pf.startswith('META-INF/') for pf in packageFiles):
                    packageFiles = [pf for pf in packageFiles if pf.startswith('META-INF/')]

                for packageFile in packageFiles:
                    packageFileUrl = filesource.url + os.sep + packageFile
                    packageFilePrefix = os.sep.join(os.path.split(packageFile)[:-1])
                    if packageFilePrefix:
                        packageFilePrefix += os.sep
                    packageFilePrefix = filesource.baseurl + os.sep +  packageFilePrefix
                    packages.append([packageFileUrl, packageFilePrefix, packageFile])
            else:
                cntlr.addToLog(_("Taxonomy package is not a zip file."),
                               messageCode="tpe:invalidArchiveFormat",
                               file=os.path.basename(packageFilename),
                               level=logging.ERROR)
                errors.append("tpe:invalidArchiveFormat")
                if (os.path.basename(filesource.url) in TAXONOMY_PACKAGE_FILE_NAMES or # individual manifest file
                      (os.path.basename(filesource.url) == "taxonomyPackage.xml" and
                       os.path.basename(os.path.dirname(filesource.url)) == "META-INF")):
                    packageFile = packageFileUrl = filesource.url
                    packageFilePrefix = os.path.dirname(packageFile)
                    if packageFilePrefix:
                        packageFilePrefix += os.sep
                    packages.append([packageFileUrl, packageFilePrefix, ""])
                else:
                    raise IOError(_("File must be a taxonomy package (zip file), catalog file, or manifest (): {0}.")
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
        except (EnvironmentError, etree.XMLSyntaxError):
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
                for mapFrom, mapTo in packagesConfig.get('remappings', EMPTYDICT).items()))

def mappedUrl(url):
    if packagesConfig is not None and url is not None:
        longestPrefix = 0
        for mapFrom, mapTo in packagesConfig.get('remappings', EMPTYDICT).items():
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

invalidZipDirEntryPattern = re.compile(r"^/|^.*\\")
topLevelDirPattern = re.compile(r"([^/]+)/")
forbiddenDirEntryPattern = re.compile(r"^..?$|^..?/|^.*/..?/|^.*//")
def validatePackageEntries(filesource, errors=None):
    result = False
    if filesource is not None and filesource.isArchive:
        filesource.setLogErrors(errors)
        pathCounts = {}
        try:
            _dir = filesource.dir
        except zipfile.BadZipFile:
            filesource.setLogErrors(None)
            return False
        for f in _dir:
            pathCounts[f] = pathCounts.get(f,0) + 1
        if not _dir:
            filesource.cntlr.addToLog(_("Archive has no files"),
                                      messageCode="rpe:invalidDirectoryStructure",
                                      level=logging.ERROR,
                                      file=filesource.url)
            if errors is not None: errors.append("rpe:invalidDirectoryStructure")
        elif len(set(topLevelDirPattern.match(f).group(1) for f in _dir if topLevelDirPattern.match(f))) > 1:
            filesource.cntlr.addToLog(_("Archive must not contain multiple top level directories but %(count)s were found"),
                                      messageCode="rpe:invalidDirectoryStructure",
                                      messageArgs={"count":len(set(topLevelDirPattern.match(f) for f in _dir))},
                                      level=logging.ERROR,
                                      file=filesource.url)
            if errors is not None: errors.append("rpe:invalidDirectoryStructure")
        elif any(invalidZipDirEntryPattern.match(f) for f in _dir):
            for f in filesource.dir:
                if invalidZipDirEntryPattern.match(f):
                    filesource.cntlr.addToLog(_("Archive must not contain absolute path references or backslashes \"%(name)s\""),
                                              messageCode="rpe:invalidArchiveFormat",
                                              messageArgs={"name":f},
                                              level=logging.ERROR,
                                              file=filesource.url)
                    if errors is not None: errors.append("rpe:invalidArchiveFormat")
        elif any (forbiddenDirEntryPattern.match(f) for f in _dir):
            for f in filesource.dir:
                if forbiddenDirEntryPattern.match(f):
                    filesource.cntlr.addToLog(_("Archive contains forbidden file name \"%(name)s\""),
                                              messageCode="rpe:invalidDirectoryStructure",
                                              messageArgs={"name":f},
                                              level=logging.ERROR,
                                              file=filesource.url)
                    if errors is not None: errors.append("rpe:invalidDirectoryStructure")
        elif sum("reportPackage.json" in f for f in _dir) > 1:
            filesource.cntlr.addToLog(_("Archive has duplicate reportPackage.json entries"),
                                      messageCode="rpe:invalidDirectoryStructure",
                                      level=logging.ERROR,
                                      file=filesource.url)
            if errors is not None: errors.append("rpe:invalidDirectoryStructure")
        elif any(c > 1 for c in pathCounts.values()):
            for f, c in pathCounts.items():
                filesource.cntlr.addToLog(_("Archive has %(count)s entries for %(name)s"),
                                          messageCode="rpe:invalidDirectoryStructure",
                                          level=logging.ERROR,
                                          messageArgs={"name":f, "count":c},
                                          file=filesource.url)
                if errors is not None: errors.append("rpe:invalidDirectoryStructure")
        else:
            result = True # valid
        filesource.setLogErrors(None)
    return result # invalid package entries
