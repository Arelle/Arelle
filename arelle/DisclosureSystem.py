'''
Created on Dec 16, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, re
from lxml import etree
from arelle import (UrlUtil)

def compileAttrPattern(elt, attrName, flags=None):
    attr = elt.get(attrName)
    if attr is None: attr = ""
    if flags is not None:
        return re.compile(attr, flags)
    else:
        return re.compile(attr)

class DisclosureSystem:
    def __init__(self, modelManager):
        self.modelManager = modelManager
        self.url = os.path.join(modelManager.cntlr.configDir, "disclosuresystems.xml")
        self.clear()
        
    def clear(self):
        self.selection = None
        self.standardTaxonomiesDict = {}
        self.standardLocalHrefs = set()
        self.standardAuthorities = set()
        self.baseTaxonomyNamespaces = set()
        self.names = None
        self.name = None
        self.validationType = None
        self.EFM = False
        self.GFM = False
        self.EFMorGFM = False
        self.HMRC = False
        self.SBRNL = False
        self.validateFileText = False
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

    @property
    def dir(self):
        self.modelManager.cntlr.showStatus(_("parsing disclosuresystems.xml"))
        namepaths = []
        try:
            xmldoc = etree.parse(self.url)
            for dsElt in xmldoc.iter(tag="DisclosureSystem"):
                if dsElt.get("names"):
                    namepaths.append(
                         (dsElt.get("names").partition("|")[0],
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
                            self.selection = self.name
                            break
            self.loadMappings()
            self.loadStandardTaxonomiesDict()
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
            self.standardTaxonomiesDict = {}
            self.standardLocalHrefs = set()
            self.standardAuthorities = set()
            if not self.standardTaxonomiesUrl:
                return
            basename = os.path.basename(self.standardTaxonomiesUrl)
            self.modelManager.cntlr.showStatus(_("parsing {0}").format(basename))
            try:
                for file in (self.modelManager.cntlr.webCache.getfilename(self.standardTaxonomiesUrl), 
                            os.path.join(self.modelManager.cntlr.configDir,"xbrlschemafiles.xml")):
                    xmldoc = etree.parse(file)
                    for locElt in xmldoc.iter(tag="Loc"):
                        href = None
                        localHref = None
                        namespaceUri = None
                        attType = None
                        family = None
                        for childElt in locElt.iterchildren():
                            ln = childElt.tag
                            value = childElt.text.strip()
                            if ln == "Href":
                                href = value
                            elif ln == "LocalHref":
                                localHref = value
                            elif ln == "Namespace":
                                namespaceUri = value
                            elif ln == "AttType":
                                attType = value
                            elif ln == "Family":
                                family = value
                        if href:
                            if namespaceUri and (attType == "SCH" or attType == "ENT"):
                                if namespaceUri not in self.standardTaxonomiesDict:
                                    self.standardTaxonomiesDict[namespaceUri] = (href, localHref)
                                authority = UrlUtil.authority(namespaceUri)
                                self.standardAuthorities.add(authority)
                                if family == "BASE":
                                    self.baseTaxonomyNamespaces.add(namespaceUri)
                            if href not in self.standardTaxonomiesDict:
                                self.standardTaxonomiesDict[href] = "Allowed" + attType
                            if localHref:
                                self.standardLocalHrefs.add(localHref)
                        elif attType == "SCH" and family == "BASE":
                            self.baseTaxonomyNamespaces.add(namespaceUri)

            except (EnvironmentError,
                    etree.LxmlError) as err:
                self.modelManager.cntlr.addToLog("{0}: import error: {1}".format(basename,err))
                etree.clear_error_log()

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

    def uriAuthorityValid(self, uri):
        return UrlUtil.authority(uri) in self.standardAuthorities
    
    def disallowedHrefOfNamespace(self, href, namespaceUri):
        if namespaceUri in self.standardTaxonomiesDict:
            stdHref, localHref = self.standardTaxonomiesDict[namespaceUri]
            return not (href == stdHref or
                        (localHref and not href.startswith("http://") and href.replace("\\","/").endswith(localHref)))
        return False

    def hrefValid(self, href):
        return href in self.standardTaxonomiesDict
    
