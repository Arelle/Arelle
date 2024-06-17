'''
See COPYRIGHT.md for copyright information.
'''
import os, logging, json
import regex as re
from collections import defaultdict
from lxml import etree
from arelle import UrlUtil
from arelle.PluginManager import pluginClassMethods
from arelle.UrlUtil import isHttpUrl

def compileAttrPattern(elt, attrName, flags=None, patternIfNoAttr=""):
    attr = elt.get(attrName)
    if attr is None:
        # pattern to match if no attribute provided
        if patternIfNoAttr is None:
            return None # if None, then there is no pattern if attribute missing
        attr = patternIfNoAttr # use default pattern
    if flags is not None:
        return re.compile(attr, flags)
    else:
        return re.compile(attr)

class ErxlLoc:
    def __init__(self, family, version, href, attType, elements, namespace):
        self.family = family
        self.version = version
        self.href = href
        self.attType = attType
        self.elements = elements
        self.namespace = namespace

class DisclosureSystem:
    def __init__(self, modelManager):
        self.modelManager = modelManager
        self.clear()

    def clear(self):
        self.selection = None
        self.standardTaxonomiesDict = {}
        self.familyHrefs = {}
        self.standardLocalHrefs = set()
        self.standardAuthorities = set()
        self.baseTaxonomyNamespaces = set()
        self.standardPrefixes = {}
        self.names = []
        self.name = None
        self.validationType = None
        self.exclusiveTypesPattern = None # regex of type matches exclusive with validationType
        # previously built-in types (intent to replace with plugin defined types)
        self.EFM = False
        self.GFM = False
        self.EFMorGFM = False
        self.HMRC = False
        self.SBRNL = False
        self.pluginTypes = set()
        for pluginXbrlMethod in pluginClassMethods("DisclosureSystem.Types"):
            for typeName, typeTestVariable in pluginXbrlMethod(self):
                setattr(self, typeTestVariable, False)
                self.pluginTypes.add(typeName)
        self.validateFileText = False
        self.validateEntryText = False
        self.allowedExternalHrefPattern = None
        self.allowedImageTypes = None
        self.schemaValidateSchema = None
        self.blockDisallowedReferences = False
        self.maxSubmissionSubdirectoryEntryNesting = 0
        self.defaultXmlLang = None
        self.defaultXmlEncoding = "utf-8"
        self.xmlLangPattern = None
        self.xmlLangIsInheritable = True # for label and footnote, spec sections 4.11.1.2.1 and 5.2.2.2.1
        self.defaultLanguage = None
        self.language = None
        self.standardTaxonomiesUrl = None
        self.mappingsUrl = os.path.join(self.modelManager.cntlr.configDir, "mappings.xml")
        self.mappedFiles = {}
        self.mappedPaths = []
        self.utrUrl = ["http://www.xbrl.org/utr/utr.xml"]
        self.utrStatusFilters = None
        self.utrTypeEntries = None
        self.identifierSchemePattern = None
        self.identifierValuePattern = None
        self.identifierValueName = None
        self.contextElement = None
        self.roleDefinitionPattern = None
        self.labelCheckPattern = None
        self.labelTrimPattern = None
        self.deiNamespacePattern = None
        self.deiAmendmentFlagElement = None
        self.deiCurrentFiscalYearEndDateElement = None
        self.deiDocumentFiscalYearFocusElement = None
        self.deiDocumentPeriodEndDateElement = None
        self.deiFilerIdentifierElement = None
        self.deiFilerNameElement = None
        self.logLevelFilter = None
        self.logCodeFilter = None
        self.standardTaxonomyDatabase = None
        self.standardTaxonomyUrlPattern = None
        self.options = None
        self.version = (0,0,0)

    @property
    def dir(self):
        return self.dirlist("dir")

    @property
    def urls(self):
        _urls = [os.path.join(self.modelManager.cntlr.configDir, "disclosuresystems.xml")]
        # get custom config xml file url, insert before main url in reverse order
        for pluginXbrlMethod in pluginClassMethods("DisclosureSystem.ConfigURL"):
            _urls.insert(0, pluginXbrlMethod(self))
        return _urls

    @property
    def url(self): # needed for status messages (not used in this module)
        return ", ".join(os.path.basename(url) for url in self.urls)

    def dirlist(self, listFormat):
        self.modelManager.cntlr.showStatus(_("parsing disclosuresystems.xml"))
        namepaths = []
        namesDefined = set()
        try:
            for url in self.urls: # urls in reverse order, last plugin is first
                xmldoc = etree.parse(url)
                for dsElt in xmldoc.iter(tag="DisclosureSystem"):
                    if dsElt.get("names"):
                        names = dsElt.get("names").split("|")
                        entryName = names[-1]
                        if entryName not in namesDefined: # last plugin is taken first, rest ignored
                            if listFormat == "help": # terse help
                                namepaths.append('{0}: {1}'.format(entryName,names[0]))
                            elif listFormat == "help-verbose":
                                namepaths.append('{0}: {1}\n{2}\n'.format(entryName,
                                                                          names[0],
                                                                          dsElt.get("description").replace('\\n','\n')))
                            elif listFormat == "dir":
                                namepaths.append((names[0],
                                                  dsElt.get("description")))
                            namesDefined.add(entryName)
        except (EnvironmentError,
                etree.LxmlError) as err:
            self.modelManager.cntlr.addToLog(_("Disclosure System listing, import error: %(error)s"),
                                             messageCode="arelle:disclosureSystemListingError",
                                             messageArgs={"error": str(err)},
                                             level=logging.ERROR)
        self.modelManager.cntlr.showStatus("")
        return namepaths

    def select(self, name):
        self.clear()
        if not name:
            return True # nothing to load
        result = False
        status = _("loading disclosure system and mappings")
        try:
            if name:
                isSelected = False
                for url in self.urls: # urls in revese order, last plugin first
                    xmldoc = etree.parse(url)
                    for dsElt in xmldoc.iter(tag="DisclosureSystem"):
                        namesStr = dsElt.get("names")
                        if namesStr:
                            names = namesStr.split("|")
                            if name in names:
                                self.names = names
                                self.name = self.names[0]
                                self.validationType = dsElt.get("validationType")
                                self.exclusiveTypesPattern = compileAttrPattern(dsElt,"exclusiveTypesPattern", patternIfNoAttr=None)
                                if self.validationType not in self.pluginTypes:
                                    self.EFM = self.validationType == "EFM"
                                    self.GFM = self.validationType == "GFM"
                                    self.EFMorGFM = self.EFM or self.GFM
                                    self.HMRC = self.validationType == "HMRC"
                                    self.SBRNL = self.validationType == "SBR.NL"
                                for pluginXbrlMethod in pluginClassMethods("DisclosureSystem.Types"):
                                    for typeName, typeTestVariable in pluginXbrlMethod(self):
                                        setattr(self, typeTestVariable, self.validationType == typeName)
                                self.validateFileText = dsElt.get("validateFileText") == "true"
                                self.validateEntryText = dsElt.get("validateEntryText") == "true"
                                if dsElt.get("allowedExternalHrefPattern"):
                                    self.allowedExternalHrefPattern = re.compile(dsElt.get("allowedExternalHrefPattern"))
                                if dsElt.get("allowedImageTypes"):
                                    self.allowedImageTypes = json.loads(dsElt.get("allowedImageTypes"))
                                self.blockDisallowedReferences = dsElt.get("blockDisallowedReferences") == "true"
                                try:
                                    self.maxSubmissionSubdirectoryEntryNesting = int(dsElt.get("maxSubmissionSubdirectoryEntryNesting"))
                                except (ValueError, TypeError):
                                    self.maxSubmissionSubdirectoryEntryNesting = 0
                                self.defaultXmlLang = dsElt.get("defaultXmlLang")
                                if dsElt.get("defaultXmlEncoding", default=None) is not None: # don't reset from utf-8 unless supplied with a value
                                    self.defaultXmlEncoding = dsElt.get("defaultXmlEncoding") # may be an empty string
                                self.xmlLangPattern = compileAttrPattern(dsElt,"xmlLangPattern")
                                self.xmlLangIsInheritable = dsElt.get("xmlLangIsInheritable", "true") == "true"
                                self.defaultLanguage = dsElt.get("defaultLanguage")
                                if dsElt.get("standardTaxonomiesUrl"):
                                    self.standardTaxonomiesUrl = self.modelManager.cntlr.webCache.normalizeUrl(
                                                     dsElt.get("standardTaxonomiesUrl"),
                                                     url)
                                if dsElt.get("mappingsUrl"):
                                    self.mappingsUrl = self.modelManager.cntlr.webCache.normalizeUrl(
                                                 dsElt.get("mappingsUrl"),
                                                 url)
                                if dsElt.get("utrUrl") is not None: # may be mapped by mappingsUrl entries, see below
                                    self.utrUrl = [self.modelManager.cntlr.webCache.normalizeUrl(u, url)
                                                   for u in dsElt.get("utrUrl").split()]
                                self.utrStatusFilters = dsElt.get("utrStatusFilters")
                                self.identifierSchemePattern = compileAttrPattern(dsElt,"identifierSchemePattern")
                                self.identifierValuePattern = compileAttrPattern(dsElt,"identifierValuePattern")
                                self.identifierValueName = dsElt.get("identifierValueName")
                                self.contextElement = dsElt.get("contextElement")
                                self.roleDefinitionPattern = compileAttrPattern(dsElt,"roleDefinitionPattern")
                                self.labelCheckPattern = compileAttrPattern(dsElt,"labelCheckPattern", re.DOTALL)
                                self.labelTrimPattern = compileAttrPattern(dsElt,"labelTrimPattern", re.DOTALL)
                                self.deiNamespacePattern = compileAttrPattern(dsElt,"deiNamespacePattern")
                                self.deiAmendmentFlagElement = dsElt.get("deiAmendmentFlagElement")
                                self.deiCurrentFiscalYearEndDateElement = dsElt.get("deiCurrentFiscalYearEndDateElement")
                                self.deiDocumentFiscalYearFocusElement = dsElt.get("deiDocumentFiscalYearFocusElement")
                                self.deiDocumentPeriodEndDateElement = dsElt.get("deiDocumentPeriodEndDateElement")
                                self.deiFilerIdentifierElement = dsElt.get("deiFilerIdentifierElement")
                                self.deiFilerNameElement = dsElt.get("deiFilerNameElement")
                                self.logLevelFilter = dsElt.get("logLevelFilter")
                                self.logCodeFilter = dsElt.get("logCodeFilter")
                                self.standardTaxonomyDatabase = dsElt.get("standardTaxonomyDatabase")
                                self.standardTaxonomyUrlPattern = compileAttrPattern(dsElt, "standardTaxonomyUrlPattern")
                                self.options = dsElt.get("options")

                                self.selection = self.name
                                isSelected = True
                                result = True
                                break
                    if isSelected:
                        break
            self.loadMappings()
            self.utrUrl = [self.mappedUrl(u) for u in self.utrUrl] # utr may be mapped, change to its mapped entry
            self.loadStandardTaxonomiesDict()
            self.utrTypeEntries = None # clear any prior loaded entries
            # set log level filters (including resetting prior disclosure systems values if no such filter)
            self.modelManager.cntlr.setLogLevelFilter(self.logLevelFilter)  # None or "" clears out prior filter if any
            self.modelManager.cntlr.setLogCodeFilter(self.logCodeFilter)
            if result:
                status = _("loaded")
            else:
                status = _("unable to load disclosure system {}").format(name)
                self.modelManager.cntlr.addToLog(_("Disclosure System \"%(name)s\" not recognized (a plug-in may be needed)."),
                                                 messageCode="arelle:disclosureSystemName",
                                                 messageArgs={"name": name}, level=logging.ERROR)

        except (EnvironmentError,
                etree.LxmlError) as err:
            status = _("exception during loading")
            result = False
            self.modelManager.cntlr.addToLog(_("Disclosure System \"%(name)s\" loading error: %(error)s"),
                                             messageCode="arelle:disclosureSystemLoadingError",
                                             messageArgs={"error": str(err), "name": name}, level=logging.ERROR)
            etree.clear_error_log()
        self.modelManager.cntlr.showStatus(_("Disclosure system and mappings {0}: {1}").format(status,name), 3500)
        return result

    def loadStandardTaxonomiesDict(self):
        if self.selection:
            self.standardTaxonomiesDict = defaultdict(set)
            self.familyHrefs = defaultdict(set)
            self.standardLocalHrefs = defaultdict(set)
            self.standardAuthorities = set()
            self.standardPrefixes = {}
            if not self.standardTaxonomiesUrl:
                return
            basename = os.path.basename(self.standardTaxonomiesUrl)
            self.modelManager.cntlr.showStatus(_("parsing {0}").format(basename))
            try:
                from arelle.FileSource import openXmlFileStream
                for filepath in (self.standardTaxonomiesUrl,
                                 os.path.join(self.modelManager.cntlr.configDir,"xbrlschemafiles.xml")):
                    xmldoc = etree.parse(filepath) # must open with file path for xinclude to know base of file
                    xmldoc.xinclude() # to include elements below root use xpointer(/*/*)
                    for erxlElt in xmldoc.iter(tag="Erxl"):
                        v = erxlElt.get("version")
                        if v and re.match(r"[0-9]+([.][0-9]+)*$", v):
                            vSplit = v.split('.') # at least 3 digits always!
                            self.version = tuple(int(n) for n in vSplit) + tuple(0 for n in range(3 - len(vSplit)))
                        break
                    for locElt in xmldoc.iter(tag="Loc"):
                        href = None
                        localHref = None
                        namespaceUri = None
                        prefix = None
                        attType = None
                        family = None
                        elements = None
                        version = None
                        for childElt in locElt.iterchildren():
                            ln = childElt.tag
                            value = childElt.text.strip()
                            if ln == "Href":
                                href = value
                            elif ln == "LocalHref":
                                localHref = value
                            elif ln == "Namespace":
                                namespaceUri = value
                            elif ln == "Prefix":
                                prefix = value
                            elif ln == "AttType":
                                attType = value
                            elif ln == "Family":
                                family = value
                            elif ln == "Elements":
                                elements = value
                            elif ln == "Version":
                                version = value
                        if href:
                            if namespaceUri and (attType == "SCH" or attType == "ENT"):
                                self.standardTaxonomiesDict[namespaceUri].add(href)
                                if localHref:
                                    self.standardLocalHrefs[namespaceUri].add(localHref)
                                authority = UrlUtil.authority(namespaceUri)
                                self.standardAuthorities.add(authority)
                                if family == "BASE":
                                    self.baseTaxonomyNamespaces.add(namespaceUri)
                                if prefix:
                                    self.standardPrefixes[namespaceUri] = prefix
                            if href not in self.standardTaxonomiesDict:
                                self.standardTaxonomiesDict[href] = "Allowed" + attType
                            if family:
                                self.familyHrefs[family].add(ErxlLoc(family, version, href, attType, elements, namespaceUri))
                        elif attType == "SCH" and family == "BASE":
                            self.baseTaxonomyNamespaces.add(namespaceUri)

            except (EnvironmentError,
                    etree.LxmlError) as err:
                self.modelManager.cntlr.addToLog(_("Disclosure System \"%(name)s\" import %(importFile)s, error: %(error)s"),
                                                 messageCode="arelle:disclosureSystemImportError",
                                                 messageArgs={"error": str(err), "name": self.name, "importFile": basename},
                                                 level=logging.ERROR)
                etree.clear_error_log()

    def loadMappings(self):
        basename = os.path.basename(self.mappingsUrl)
        self.modelManager.cntlr.showStatus(_("parsing {0}").format(basename))
        try:
            xmldoc = etree.parse(self.mappingsUrl)
            xmldoc.xinclude()
            for elt in xmldoc.iter(tag="mapFile"):
                self.mappedFiles[elt.get("from")] = elt.get("to")
            for elt in xmldoc.iter(tag="mapPath"):
                self.mappedPaths.append((elt.get("from"), elt.get("to")))
        except (EnvironmentError,
                etree.LxmlError) as err:
            self.modelManager.cntlr.addToLog(_("Disclosure System \"%(name)s\" import %(importFile)s, error: %(error)s"),
                                             messageCode="arelle:disclosureSystemImportError",
                                             messageArgs={"error": str(err), "name": self.name, "importFile": basename},
                                             level=logging.ERROR)
            etree.clear_error_log()

    def mappedUrl(self, url):
        if url in self.mappedFiles:
            mappedUrl = self.mappedFiles[url]
        else:  # handle mapped paths
            mappedUrl = url
            for mapFrom, mapTo in self.mappedPaths:
                if url.startswith(mapFrom):
                    mappedUrl = mapTo + url[len(mapFrom):]
                    break
        return mappedUrl

    def uriAuthorityValid(self, uri):
        if self.standardTaxonomiesUrl:
            return UrlUtil.authority(uri) in self.standardAuthorities
        return True # no standard authorities to test

    def disallowedHrefOfNamespace(self, href, namespaceUri):
        if self.standardTaxonomiesUrl:
            if namespaceUri in self.standardTaxonomiesDict:
                if href in self.standardTaxonomiesDict[namespaceUri]:
                    return False
            if namespaceUri in self.standardLocalHrefs and not isHttpUrl(href):
                normalizedHref = href.replace("\\","/")
                if any(normalizedHref.endswith(localHref)
                       for localHref in self.standardLocalHrefs[namespaceUri]):
                    return False
        return False

    def hrefValid(self, href):
        if self.standardTaxonomiesUrl:
            return href in self.standardTaxonomiesDict
        return True # no standard taxonomies to test
