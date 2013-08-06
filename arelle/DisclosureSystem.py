'''
Created on Dec 16, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, re
from collections import defaultdict
from lxml import etree
from arelle import UrlUtil
from arelle.UrlUtil import isHttpUrl

def compileAttrPattern(elt, attrName, flags=None):
    attr = elt.get(attrName)
    if attr is None: attr = ""
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
        self.url = os.path.join(modelManager.cntlr.configDir, "disclosuresystems.xml")
        self.clear()
        
    def clear(self):
        self.selection = None
        self.standardTaxonomiesDict = {}
        self.familyHrefs = {}
        self.standardLocalHrefs = set()
        self.standardAuthorities = set()
        self.baseTaxonomyNamespaces = set()
        self.standardPrefixes = {}
        self.names = None
        self.name = None
        self.validationType = None
        self.EFM = False
        self.GFM = False
        self.EFMorGFM = False
        self.HMRC = False
        self.SBRNL = False
        self.validateFileText = False
        self.schemaValidateSchema = None
        self.blockDisallowedReferences = False
        self.maxSubmissionSubdirectoryEntryNesting = 0
        self.defaultXmlLang = None
        self.xmlLangPattern = None
        self.defaultLanguage = None
        self.language = None
        self.standardTaxonomiesUrl = None
        self.mappingsUrl = os.path.join(self.modelManager.cntlr.configDir, "mappings.xml")
        self.mappedFiles = {}
        self.mappedPaths = []
        self.utrUrl = "http://www.xbrl.org/utr/utr.xml"
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

    @property
    def dir(self):
        return self.dirlist("dir")
    
    def dirlist(self, listFormat):
        self.modelManager.cntlr.showStatus(_("parsing disclosuresystems.xml"))
        namepaths = []
        try:
            xmldoc = etree.parse(self.url)
            for dsElt in xmldoc.iter(tag="DisclosureSystem"):
                if dsElt.get("names"):
                    names = dsElt.get("names").split("|")
                    if listFormat == "help": # terse help
                        namepaths.append('{0}: {1}'.format(names[-1],names[0]))
                    elif listFormat == "help-verbose":
                        namepaths.append('{0}: {1}\n{2}\n'.format(names[-1],
                                                                  names[0], 
                                                                  dsElt.get("description").replace('\\n','\n')))
                    elif listFormat == "dir":
                        namepaths.append((names[0],
                                          dsElt.get("description")))
        except (EnvironmentError,
                etree.LxmlError) as err:
            self.modelManager.cntlr.addToLog("disclosuresystems.xml: import error: {0}".format(err))
        self.modelManager.cntlr.showStatus("")
        return namepaths

    def select(self, name):
        self.clear()
        status = _("loading disclosure system and mappings")
        try:
            if name:
                xmldoc = etree.parse(self.url)
                for dsElt in xmldoc.iter(tag="DisclosureSystem"):
                    namesStr = dsElt.get("names")
                    if namesStr:
                        names = namesStr.split("|")
                        if name in names:
                            self.names = names
                            self.name = self.names[0]
                            self.validationType = dsElt.get("validationType")
                            self.EFM = self.validationType == "EFM"
                            self.GFM = self.validationType == "GFM"
                            self.EFMorGFM = self.EFM or self.GFM
                            self.HMRC = self.validationType == "HMRC"
                            self.SBRNL = self.validationType == "SBR-NL"
                            self.validateFileText = dsElt.get("validateFileText") == "true"
                            self.blockDisallowedReferences = dsElt.get("blockDisallowedReferences") == "true"
                            try:
                                self.maxSubmissionSubdirectoryEntryNesting = int(dsElt.get("maxSubmissionSubdirectoryEntryNesting"))
                            except (ValueError, TypeError):
                                self.maxSubmissionSubdirectoryEntryNesting = 0
                            self.defaultXmlLang = dsElt.get("defaultXmlLang")
                            self.xmlLangPattern = compileAttrPattern(dsElt,"xmlLangPattern")
                            self.defaultLanguage = dsElt.get("defaultLanguage")
                            self.standardTaxonomiesUrl = self.modelManager.cntlr.webCache.normalizeUrl(
                                             dsElt.get("standardTaxonomiesUrl"),
                                             self.url)
                            if dsElt.get("mappingsUrl"):
                                self.mappingsUrl = self.modelManager.cntlr.webCache.normalizeUrl(
                                             dsElt.get("mappingsUrl"),
                                             self.url)
                            if dsElt.get("utrUrl"): # may be mapped by mappingsUrl entries, see below
                                self.utrUrl = self.modelManager.cntlr.webCache.normalizeUrl(
                                             dsElt.get("utrUrl"),
                                             self.url)
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
                            self.selection = self.name
                            break
            self.loadMappings()
            self.utrUrl = self.mappedUrl(self.utrUrl) # utr may be mapped, change to its mapped entry
            self.loadStandardTaxonomiesDict()
            self.utrTypeEntries = None # clear any prior loaded entries
            # set log level filters (including resetting prior disclosure systems values if no such filter)
            self.modelManager.cntlr.setLogLevelFilter(self.logLevelFilter)  # None or "" clears out prior filter if any
            self.modelManager.cntlr.setLogCodeFilter(self.logCodeFilter)
            status = _("loaded")
            result = True
        except (EnvironmentError,
                etree.LxmlError) as err:
            status = _("exception during loading")
            result = False
            self.modelManager.cntlr.addToLog("disclosuresystems.xml: import error: {0}".format(err))
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
            file = None
            try:
                from arelle.FileSource import openXmlFileStream
                for filepath in (self.standardTaxonomiesUrl, 
                                 os.path.join(self.modelManager.cntlr.configDir,"xbrlschemafiles.xml")):
                    file = openXmlFileStream(self.modelManager.cntlr, filepath, stripDeclaration=True)[0]
                    xmldoc = etree.parse(file)
                    file.close()
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
                self.modelManager.cntlr.addToLog("{0}: import error: {1}".format(basename,err))
                etree.clear_error_log()
                if file:
                    file.close()

    def loadMappings(self):
        basename = os.path.basename(self.mappingsUrl)
        self.modelManager.cntlr.showStatus(_("parsing {0}").format(basename))
        try:
            xmldoc = etree.parse(self.mappingsUrl)
            for elt in xmldoc.iter(tag="mapFile"):
                self.mappedFiles[elt.get("from")] = elt.get("to")
            for elt in xmldoc.iter(tag="mapPath"):
                self.mappedPaths.append((elt.get("from"), elt.get("to")))
        except (EnvironmentError,
                etree.LxmlError) as err:
            self.modelManager.cntlr.addToLog("{0}: import error: {1}".format(basename,err))
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
        return UrlUtil.authority(uri) in self.standardAuthorities
    
    def disallowedHrefOfNamespace(self, href, namespaceUri):
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
        return href in self.standardTaxonomiesDict


