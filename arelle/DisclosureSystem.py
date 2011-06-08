'''
Created on Dec 16, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import xml.dom.minidom, xml.parsers.expat, os, re
from arelle import (UrlUtil, XmlUtil)

class DisclosureSystem:
    def __init__(self, modelManager):
        self.modelManager = modelManager
        self.url = os.path.join(modelManager.cntlr.configDir, "disclosuresystems.xml")
        self.clear()
        
    def clear(self):
        self.selection = None
        self.standardTaxonomiesDict = {}
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
        self.blockDisallowedReferences = False
        self.maxSubmissionSubdirectoryEntryNesting = 0
        self.defaultXmlLang = None
        self.xmlLangPattern = None
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
            xmldoc = xml.dom.minidom.parse(self.url)
            for dsElt in xmldoc.getElementsByTagName("DisclosureSystem"):
                if dsElt.hasAttribute("names"):
                    namepaths.append(
                         (dsElt.getAttribute("names").partition("|")[0],
                          dsElt.getAttribute("description")))
        except (EnvironmentError,
                xml.parsers.expat.ExpatError,
                xml.dom.DOMException) as err:
            self.modelManager.cntlr.addToLog("disclosuresystems.xml: import error: {0}".format(err))
        self.modelManager.cntlr.showStatus("")
        return namepaths

    def select(self, name):
        self.clear()
        status = _("loading disclosure system and mappings")
        try:
            if name:
                xmldoc = xml.dom.minidom.parse(self.url)
                for dsElt in xmldoc.getElementsByTagName("DisclosureSystem"):
                    names = dsElt.getAttribute("names").split("|")
                    if name in names:
                        self.names = names
                        self.name = self.names[0]
                        self.validationType = dsElt.getAttribute("validationType")
                        self.EFM = self.validationType == "EFM"
                        self.GFM = self.validationType == "GFM"
                        self.EFMorGFM = self.EFM or self.GFM
                        self.HMRC = self.validationType == "HMRC"
                        self.SBRNL = self.validationType == "SBR-NL"
                        self.blockDisallowedReferences = dsElt.getAttribute("blockDisallowedReferences") == "true"
                        try:
                            self.maxSubmissionSubdirectoryEntryNesting = int(dsElt.getAttribute("maxSubmissionSubdirectoryEntryNesting"))
                        except ValueError:
                            self.maxSubmissionSubdirectoryEntryNesting = 0
                        self.defaultXmlLang = dsElt.getAttribute("defaultXmlLang")
                        if dsElt.hasAttribute("xmlLangPattern"):
                            self.xmlLangPattern = re.compile(dsElt.getAttribute("xmlLangPattern"))
                        self.defaultLanguage = dsElt.getAttribute("defaultLanguage")
                        self.standardTaxonomiesUrl = self.modelManager.cntlr.webCache.normalizeUrl(
                                         dsElt.getAttribute("standardTaxonomiesUrl"),
                                         self.url)
                        if dsElt.hasAttribute("mappingsUrl"):
                            self.mappingsUrl = self.modelManager.cntlr.webCache.normalizeUrl(
                                         dsElt.getAttribute("mappingsUrl"),
                                         self.url)
                        self.identifierSchemePattern = re.compile(dsElt.getAttribute("identifierSchemePattern"))
                        self.identifierValuePattern = re.compile(dsElt.getAttribute("identifierValuePattern"))
                        self.identifierValueName = dsElt.getAttribute("identifierValueName")
                        self.contextElement = dsElt.getAttribute("contextElement")
                        self.roleDefinitionPattern = re.compile(dsElt.getAttribute("roleDefinitionPattern"))
                        self.labelCheckPattern = re.compile(dsElt.getAttribute("labelCheckPattern"), re.DOTALL)
                        self.labelTrimPattern = re.compile(dsElt.getAttribute("labelTrimPattern"), re.DOTALL)
                        self.deiNamespacePattern = re.compile(dsElt.getAttribute("deiNamespacePattern"))
                        self.deiAmendmentFlagElement = dsElt.getAttribute("deiAmendmentFlagElement")
                        self.deiCurrentFiscalYearEndDateElement = dsElt.getAttribute("deiCurrentFiscalYearEndDateElement")
                        self.deiDocumentFiscalYearFocusElement = dsElt.getAttribute("deiDocumentFiscalYearFocusElement")
                        self.deiDocumentPeriodEndDateElement = dsElt.getAttribute("deiDocumentPeriodEndDateElement")
                        self.deiFilerIdentifierElement = dsElt.getAttribute("deiFilerIdentifierElement")
                        self.deiFilerNameElement = dsElt.getAttribute("deiFilerNameElement")
                        self.selection = self.name
                        break
            self.loadMappings()
            self.loadStandardTaxonomiesDict()
            status = _("loaded")
            result = True
        except (EnvironmentError,
                xml.parsers.expat.ExpatError,
                xml.dom.DOMException) as err:
            status = _("exception during loading")
            result = False
            self.modelManager.cntlr.addToLog("disclosuresystems.xml: import error: {0}".format(err))
        self.modelManager.cntlr.showStatus(_("Disclosure system and mappings {0}: {1}").format(status,name), 3500)
        return result

    def loadStandardTaxonomiesDict(self):
        if self.selection:
            self.standardTaxonomiesDict = {}
            self.standardAuthorities = set()
            if not self.standardTaxonomiesUrl:
                return
            basename = os.path.basename(self.standardTaxonomiesUrl)
            self.modelManager.cntlr.showStatus(_("parsing {0}").format(basename))
            try:
                for file in (self.modelManager.cntlr.webCache.getfilename(self.standardTaxonomiesUrl), 
                            os.path.join(self.modelManager.cntlr.configDir,"xbrlschemafiles.xml")):
                    xmldoc = xml.dom.minidom.parse(file)
                    for locElt in xmldoc.getElementsByTagName("Loc"):
                        href = None
                        localHref = None
                        namespaceUri = None
                        attType = None
                        family = None
                        for childElt in locElt.childNodes:
                            if childElt.nodeType == 1: #element
                                ln = childElt.localName
                                value = XmlUtil.innerText(childElt)
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
            except (EnvironmentError,
                    xml.parsers.expat.ExpatError,
                    xml.dom.DOMException) as err:
                self.modelManager.cntlr.addToLog("{0}: import error: {1}".format(basename,err))

    def loadMappings(self):
            basename = os.path.basename(self.mappingsUrl)
            self.modelManager.cntlr.showStatus(_("parsing {0}").format(basename))
            try:
                xmldoc = xml.dom.minidom.parse(self.mappingsUrl)
                for elt in xmldoc.getElementsByTagName("mapFile"):
                    self.mappedFiles[elt.getAttribute("from")] = elt.getAttribute("to")
                for elt in xmldoc.getElementsByTagName("mapPath"):
                    self.mappedPaths.append((elt.getAttribute("from"), elt.getAttribute("to")))
            except (EnvironmentError,
                    xml.parsers.expat.ExpatError,
                    xml.dom.DOMException) as err:
                self.modelManager.cntlr.addToLog("{0}: import error: {1}".format(basename,err))

    def uriAuthorityValid(self, uri):
        return UrlUtil.authority(uri) in self.standardAuthorities
    
    def disallowedHrefOfNamespace(self, href, namespaceUri):
        if namespaceUri in self.standardTaxonomiesDict:
            stdHref, localHref = self.standardTaxonomiesDict[namespaceUri]
            return not (href == stdHref or
                        (localHref and not href.startswith("http://") and href.endswith(localHref)))
        return False

    def hrefValid(self, href):
        return href in self.standardTaxonomiesDict
    
