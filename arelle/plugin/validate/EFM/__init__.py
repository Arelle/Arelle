'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.

Input files may be in JSON:


[ {"file": "file path to instance or html",
   "cik": "1234567890",
   "cikNameList": { "cik1": "name1", "cik2":"name2", "cik3":"name3"...},
   "submissionType" : "SDR K",
   "exhibitType": "EX-99.K" },
 {"file": "file 2"...
]



'''
import os, json, zipfile
jsonIndent = 1  # None for most compact, 0 for left aligned
from decimal import Decimal
from lxml.etree import XML, XMLSyntaxError
from arelle import ModelDocument, ModelValue, XmlUtil
from arelle.ModelValue import qname
from arelle.PluginManager import pluginClassMethods  # , pluginMethodsForClasses, modulePluginInfos
from arelle.UrlUtil import authority, relativeUri, isHttpUrl
from arelle.ValidateFilingText import CDATApattern
from .Document import checkDTSdocument
from .Filing import validateFiling
try:
    import regex as re
except ImportError:
    import re
from collections import defaultdict


def dislosureSystemTypes(disclosureSystem):
    # return ((disclosure system name, variable name), ...)
    return (("EFM", "EFMplugin"),)

def disclosureSystemConfigURL(disclosureSystem):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None):
    val.validateEFMplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "EFMplugin", False)
    if not (val.validateEFMplugin):
        return

    val.paramExhibitType = None # e.g., EX-101, EX-201
    val.paramFilerIdentifier = None
    val.paramFilerIdentifierNames = None
    val.paramSubmissionType = None
    _cik = _cikList = _cikNameList = _exhibitType = _submissionType = None
    if parameters:
        # parameter-provided CIKs and registrant names
        p = parameters.get(ModelValue.qname("CIK",noPrefixIsNoNamespace=True))
        if p and len(p) == 2 and p[1] not in ("null", "None"):
            val.paramFilerIdentifier = p[1]
        p = parameters.get(ModelValue.qname("cikList",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:
            _filerIdentifiers = p[1].split(",")
        else:
            _filerIdentifiers = []
        p = parameters.get(ModelValue.qname("cikNameList",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:
            _filerNames = p[1].split("|Edgar|")
            if _filerIdentifiers and len(_filerIdentifiers) != len(_filerNames):
                val.modelXbrl.error(("EFM.6.05.24.parameters", "GFM.3.02.02"),
                    _("parameters for cikList and cikNameList different list entry counts: %(cikList)s, %(cikNameList)s"),
                    modelXbrl=val.modelXbrl, cikList=_FilerIdentifiers, cikNameList=_FilerNames)
            else:
                val.paramFilerIdentifierNames=dict((_cik,_filerNames[i])
                                                   for i, _cik in enumerate(_filerIdentifiers))
        p = parameters.get(ModelValue.qname("submissionType",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:
            val.paramSubmissionType = p[1]
        p = parameters.get(ModelValue.qname("exhibitType",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:
            val.paramExhibitType = p[1]
    elif hasattr(val.modelXbrl.modelManager, "efmFiling"):
        efmFiling = val.modelXbrl.modelManager.efmFiling
        if efmFiling.reports: # possible that there are no reports
            entryPoint = efmFiling.reports[-1].entryPoint
            _cik = entryPoint.get("cik", None)
            _cikList = entryPoint.get("cikList", None)
            _cikNameList = entryPoint.get("cikNameList",None)
            _exhibitType = entryPoint.get("exhibitType", None)
            _submissionType = entryPoint.get("submissionType", None)
    
    if _cik and _cik not in ("null", "None"):
        val.paramFilerIdentifier = _cik
    _filerIdentifiers = (_cikList or "").split(",")
    _filerNames = (_cikNameList or "").split("|Edgar|")
    if _filerIdentifiers and len(_filerIdentifiers) != len(_filerNames):
        val.modelXbrl.error(("EFM.6.05.24.parameters", "GFM.3.02.02"),
            _("parameters for cikList and cikNameList different list entry counts: %(cikList)s, %(cikNameList)s"),
            modelXbrl=val.modelXbrl, cikList=_FilerIdentifiers, cikNameList=_FilerNames)
    elif _filerNames:
        val.paramFilerIdentifierNames=dict((_cik,_filerNames[i])
                                           for i, _cik in enumerate(_filerIdentifiers))
    if _exhibitType:
        val.paramExhibitType = _exhibitType
    if _submissionType:
        val.paramSubmissionType = _submissionType

    if val.paramExhibitType == "EX-2.01": # only applicable for edgar production and parameterized testcases
        val.EFM60303 = "EFM.6.23.01"
    else:
        val.EFM60303 = "EFM.6.03.03"
                
    
    if any((concept.qname.namespaceURI in val.disclosureSystem.standardTaxonomiesDict) 
           for concept in val.modelXbrl.nameConcepts.get("UTR",())):
        val.validateUTR = True

def validateXbrlFinally(val):
    if not (val.validateEFMplugin):
        return

    modelXbrl = val.modelXbrl

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)
    
    validateFiling(val, modelXbrl, isEFM=True)

    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)
    
def validateXbrlDtsDocument(val, modelDocument, isFilingDocument):
    if not (val.validateEFMplugin):
        return

    checkDTSdocument(val, modelDocument, isFilingDocument)
    
def filingStart(cntlr, options, filesource, entrypointFiles, sourceZipStream=None, responseZipStream=None):
    modelManager = cntlr.modelManager
    # cntlr.addToLog("TRACE EFM filing start val={} plugin={}".format(modelManager.validateDisclosureSystem, getattr(modelManager.disclosureSystem, "EFMplugin", False)))
    if modelManager.validateDisclosureSystem and getattr(modelManager.disclosureSystem, "EFMplugin", False):
        # cntlr.addToLog("TRACE EFM filing start 2 classes={} moduleInfos={}".format(pluginMethodsForClasses, modulePluginInfos))
        modelManager.efmFiling = Filing(cntlr, options, filesource, entrypointFiles, sourceZipStream, responseZipStream)
        for pluginXbrlMethod in pluginClassMethods("EdgarRenderer.Filing.Start"):
            pluginXbrlMethod(cntlr, options, entrypointFiles, modelManager.efmFiling)
                
def xbrlLoaded(cntlr, options, modelXbrl, entryPoint, *args):
    # cntlr.addToLog("TRACE EFM xbrl loaded")
    modelManager = cntlr.modelManager
    if (hasattr(modelManager, "efmFiling") and
        (modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or 
        modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL)):
        efmFiling = modelManager.efmFiling
        efmFiling.addReport(modelXbrl)
        _report = efmFiling.reports[-1]
        _report.entryPoint = entryPoint

def xbrlRun(cntlr, options, modelXbrl, *args):
    # cntlr.addToLog("TRACE EFM xbrl run")
    modelManager = cntlr.modelManager
    if (hasattr(modelManager, "efmFiling") and
        (modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or 
        modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL)):
        efmFiling = modelManager.efmFiling
        _report = efmFiling.reports[-1]
        if True: # HF TESTING: not (options.abortOnMajorError and len(modelXbrl.errors) > 0):
            for pluginXbrlMethod in pluginClassMethods("EdgarRenderer.Xbrl.Run"):
                pluginXbrlMethod(cntlr, options, modelXbrl, modelManager.efmFiling, _report)

def filingValidate(cntlr, options, filesource, entrypointFiles, sourceZipStream=None, responseZipStream=None):
    # cntlr.addToLog("TRACE EFM xbrl validate")
    modelManager = cntlr.modelManager
    if hasattr(modelManager, "efmFiling"):
        efmFiling = modelManager.efmFiling
        reports = efmFiling.reports
        # check for dup inline and regular instances
        # SDR checks
        if any(report.documentType and report.documentType.startswith("SDR") 
               for report in reports):
            _sdrKs = [r for r in reports if r.documentType == "SDR K"]
            if not _sdrKs:
                efmFiling.error("EFM.SDR.1.1",
                                _("Filing has no SDR K reports"))
            elif len(_sdrKs) > 1:
                efmFiling.error("EFM.SDR.1.2",
                                _("Filing has multiple SDR K reports for %(entities)s"),
                                {"entities": ", ".join(r.entityRegistrantName for r in _sdrKs)}, 
                                (r.url for r in _sdrKs))
            _sdrLentityReports = defaultdict(list)
            for r in reports:
                if r.documentType == "SDR L":
                    _sdrLentityReports[r.entityRegistrantName].append(r)
            if not _sdrLentityReports:
                efmFiling.error("EFM.SDR.1.3",
                                _("Filing has no SDR L reports"))
            for sdrLentity, sdrLentityReports in _sdrLentityReports.items():
                if len(sdrLentityReports) > 1:
                    efmFiling.error("EFM.SDR.1.4",
                                    _("Filing entity has multiple SDR L reports: %(entity)s"),
                                    {"entity": sdrLentity},
                                    (r.url for r in sdrLentityReports))
            # check for required extension files (schema, pre, lbl)
            for r in reports:
                hasSch = hasPre = hasCal = hasLbl = False
                for f in r.reportedFiles:
                    if f.endswith(".xsd"): hasSch = True
                    elif f.endswith("_pre.xml"): hasPre = True
                    elif f.endswith("_cal.xml"): hasCal = True
                    elif f.endswith("_lab.xml"): hasLbl = True
                missingFiles = ""
                if not hasSch: missingFiles += ", schema"
                if not hasPre: missingFiles += ", presentation linkbase"
                if not hasLbl: missingFiles += ", label linkbase"
                if missingFiles:
                    efmFiling.error("EFM.SDR.1.5",
                                    _("%(docType)s report missing files: %(missingFiles)s"),
                                    {"docType": r.documentType, "missingFiles": missingFiles[2:]},
                                    r.url)
                if not r.hasUsGaapTaxonomy:
                    efmFiling.error("EFM.SDR.1.6",
                                    _("%(documentType)s submission must use a US GAAP standard schema"),
                                    {"documentType": r.documentType},
                                    r.url)

def filingEnd(cntlr, options, filesource, entrypointFiles, sourceZipStream=None, responseZipStream=None):
    #cntlr.addToLog("TRACE EFM filing end")
    modelManager = cntlr.modelManager
    if hasattr(modelManager, "efmFiling"):
        for pluginXbrlMethod in pluginClassMethods("EdgarRenderer.Filing.End"):
            pluginXbrlMethod(cntlr, options, modelManager.efmFiling)
        #cntlr.addToLog("TRACE EdgarRenderer end")
        # save JSON file of instances and referenced documents
        filingReferences = dict((report.url, report)
                                for report in modelManager.efmFiling.reports)

        modelManager.efmFiling.close()
        del modelManager.efmFiling
        #cntlr.addToLog("TRACE EFN filing end complete")
    
class Filing:
    def __init__(self, cntlr, options, filesource, entrypointfiles, sourceZipStream, responseZipStream):
        self.cntlr = cntlr
        self.options = options
        self.filesource = filesource
        self.entrypointfiles = entrypointfiles
        self.sourceZipStream = sourceZipStream
        self.responseZipStream = responseZipStream
        self.reports = []
        self.renderedFiles = set() # filing-level rendered files
        if responseZipStream:
            self.reportZip = zipfile.ZipFile(responseZipStream, 'w', zipfile.ZIP_DEFLATED, True)
        else:
            try: #zipOutputFile only present with EdgarRenderer plugin options
                if options.zipOutputFile:
                    self.reportZip = zipfile.ZipFile(options.zipOutputFile, 'w', zipfile.ZIP_DEFLATED, True)
                else:
                    self.reportZip = None
            except AttributeError:
                self.reportZip = None
        
    def close(self):
        _reports = dict((report.basename, report.json) for report in self.reports)
        _reports["filing"] = {"renderedFiles": sorted(self.renderedFiles)}
        if self.options.logFile:
            _reports["filing"]["logFile"] = self.options.logFile
        if self.reportZip:
            self.reportZip.writestr("MetaFiling.json", json.dumps(_reports, sort_keys=True, indent=jsonIndent))
        else:
            try:
                if self.options.reportsFolder:
                    with open(os.path.join(self.options.reportsFolder, "MetaFiling.json"), mode='w') as f:
                        json.dump(_reports, f, sort_keys=True, indent=jsonIndent)
            except AttributeError: # no reportsFolder attribute
                pass
        if self.options.logFile:
            if self.reportZip:
                _logFile = self.options.logFile
                _logFileExt = os.path.splitext(_logFile)[1]
                if _logFileExt == ".xml":
                    _logStr = self.cntlr.logHandler.getXml(clearLogBuffer=False)  # may be saved to file later or flushed in web interface
                elif _logFileExt == ".json":
                    _logStr = self.cntlr.logHandler.getJson(clearLogBuffer=False)
                else:  # no ext or  _logFileExt == ".txt":
                    _logStr = cntlr.logHandler.getText(clearLogBuffer=False)
                self.reportZip.writestr(_logFile, _logStr)
            #else:
            #    with open(_logFile, "wt", encoding="utf-8") as fh:
            #        fh.write(_logStr)
        if self.reportZip:
            self.reportZip.close()
        self.__dict__.clear() # dereference all contents
        
    def addReport(self, modelXbrl):
        _report = Report(modelXbrl)
        self.reports.append(_report)
        
    def error(self, messageCode, message, messageArgs=None, file=None):
        if file and len(self.entrypointfiles) > 0:
            # relativize file(s)
            if isinstance(file, _STR_BASE):
                file = (file,)
            relFiles = [relativeUri(self.entrypointfiles[0], f) for f in file]
        self.cntlr.addToLog(message, messageCode, messageArgs, relFiles, "ERROR")
        
class Report:
    REPORT_ATTRS = {"DocumentType", "DocumentPeriodEndDate", "EntityRegistrantName",
                    "EntityCentralIndexKey", "CurrentFiscalYearEndDate", "DocumentFiscalYearFocus"}
    def lc(self, name):
        return name[0].lower() + name[1:]
    
    def __init__(self, modelXbrl):
        self.url = modelXbrl.modelDocument.uri
        self.basename = modelXbrl.modelDocument.basename
        for attrName in Report.REPORT_ATTRS:
            setattr(self, self.lc(attrName), None)
        self.instanceName = modelXbrl.modelDocument.basename
        for f in modelXbrl.facts:
            cntx = f.context
            if cntx is not None and cntx.isStartEndPeriod and not cntx.hasSegment:
                if f.qname.localName in Report.REPORT_ATTRS and f.xValue:
                    setattr(self, self.lc(f.qname.localName), f.xValue)
        self.reportedFiles = set()
        self.renderedFiles = set()
        self.hasUsGaapTaxonomy = False
        sourceDir = os.path.dirname(modelXbrl.modelDocument.filepath)
        # add referenced files that are xbrl-referenced local documents
        refDocUris = set()
        def addRefDocs(doc):
            for refDoc in doc.referencesDocument.keys():
                _file = refDoc.filepath
                if refDoc.uri not in refDocUris:
                    refDocUris.add(refDoc.uri)
                    if refDoc.filepath and refDoc.filepath.startswith(sourceDir):
                        self.reportedFiles.add(refDoc.filepath[len(sourceDir)+1:])
                    addRefDocs(refDoc)
                if refDoc.type == ModelDocument.Type.SCHEMA:
                    nsAuthority = authority(refDoc.targetNamespace, includeScheme=False)
                    nsPath = refDoc.targetNamespace.split('/')
                    if len(nsPath) > 2:
                        if nsAuthority in ("fasb.org", "xbrl.us") and nsPath[-2] == "us-gaap":
                            self.hasUsGaapTaxonomy = True
        addRefDocs(modelXbrl.modelDocument)
        # add referenced files that are html-referenced image and other files
        def addLocallyReferencedFile(elt):
            if elt.tag in ("a", "img", "{http://www.w3.org/1999/xhtml}a", "{http://www.w3.org/1999/xhtml}img"):
                for attrTag, attrValue in elt.items():
                    if attrTag in ("href", "src") and not isHttpUrl(attrValue) and not os.path.isabs(attrValue):
                        file = os.path.join(sourceDir,attrValue)
                        if os.path.exists(file):
                            self.reportedFiles.add(os.path.join(sourceDir,attrValue))
        for fact in modelXbrl.facts:
            if fact.isItem and fact.concept is not None and fact.concept.isTextBlock:
                # check for img and other filing references so that referenced files are included in the zip.
                text = fact.textValue
                for xmltext in [text] + CDATApattern.findall(text):
                    try:
                        for elt in XML("<body>\n{0}\n</body>\n".format(xmltext)).iter():
                            addLocallyReferencedFile(elt)
                    except (XMLSyntaxError, UnicodeDecodeError):
                        pass  # TODO: Why ignore UnicodeDecodeError?
        # footnote or other elements
        for elt in modelXbrl.modelDocument.xmlRootElement.iter("{http://www.w3.org/1999/xhtml}a", "{http://www.w3.org/1999/xhtml}img"):
            addLocallyReferencedFile(elt)
            
    def close(self):
        self.__dict__.clear() # dereference all contents
        
    @property
    def json(self): # stringify un-jsonable attributes
        return dict((name, value if isinstance(value,(str,int,float,Decimal,list,dict))
                           else sorted(value) if isinstance(value, set)
                           else str(value)) 
                    for name, value in self.__dict__.items())

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate EFM',
    'version': '1.0.0.32',
    'description': '''EFM Validation.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2013-15 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
    'Validate.XBRL.DTS.document': validateXbrlDtsDocument,
    'CntlrCmdLine.Filing.Start': filingStart,
    'CntlrCmdLine.Xbrl.Loaded': xbrlLoaded,
    'CntlrCmdLine.Xbrl.Run': xbrlRun,
    'CntlrCmdLine.Filing.Validate': filingValidate,
    'CntlrCmdLine.Filing.End': filingEnd,
}
