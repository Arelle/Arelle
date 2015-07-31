'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import ModelDocument, ModelValue, XmlUtil
from arelle.ModelValue import qname
from arelle.UrlUtil import authority, relativeUri
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
    val.paramFilerIdentifiers = None
    val.paramFilerNames = None
    val.paramSubmissionType = None
    if parameters:
        # parameter-provided CIKs and registrant names
        p = parameters.get(ModelValue.qname("CIK",noPrefixIsNoNamespace=True))
        if p and len(p) == 2 and p[1] not in ("null", "None"):
            val.paramFilerIdentifier = p[1]
        p = parameters.get(ModelValue.qname("cikList",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:
            val.paramFilerIdentifiers = p[1].split(",")
        p = parameters.get(ModelValue.qname("cikNameList",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:
            val.paramFilerNames = p[1].split("|Edgar|")
            if val.paramFilerIdentifiers and len(val.paramFilerIdentifiers) != len(val.paramFilerNames):
                val.modelXbrl.error(("EFM.6.05.24.parameters", "GFM.3.02.02"),
                    _("parameters for cikList and cikNameList different list entry counts: %(cikList)s, %(cikNameList)s"),
                    modelXbrl=val.modelXbrl, cikList=val.paramFilerIdentifiers, cikNameList=val.paramFilerNames)
        p = parameters.get(ModelValue.qname("submissionType",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:
            val.paramSubmissionType = p[1]
        p = parameters.get(ModelValue.qname("exhibitType",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:
            val.paramExhibitType = p[1]

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
    if modelManager.validateDisclosureSystem and getattr(modelManager.disclosureSystem, "EFMplugin", False):
        modelManager.efmFiling = Filing(cntlr, options, filesource, entrypointFiles, sourceZipStream, responseZipStream)
                
def xbrlLoaded(cntlr, options, modelXbrl):
    modelManager = cntlr.modelManager
    if (hasattr(modelManager, "efmFiling") and
        (modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or 
        modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL)):
        efmFiling = modelManager.efmFiling
        efmFiling.addReport(modelXbrl)



def filingEnd(cntlr, options, filesource, entrypointFiles, sourceZipStream=None, responseZipStream=None):
    modelManager = cntlr.modelManager
    if hasattr(modelManager, "efmFiling"):
        efmFiling = modelManager.efmFiling
        reports = efmFiling.reports
        # check for dup inline and regular instances
        # SDR checks
        if any(report.DocumentType.startswith("SDR") for report in reports):
            _sdrKs = [r for r in reports if r.DocumentType == "SDR K"]
            if not _sdrKs:
                efmFiling.error("EFM.SDR.1.1",
                                _("Filing has no SDR K reports"))
            elif len(_sdrKs) > 1:
                efmFiling.error("EFM.SDR.1.2",
                                _("Filing has multiple SDR K reports for %(entities)s"),
                                {"entities": ", ".join(r.EntityRegistrantName for r in _sdrKs)}, 
                                (r.uri for r in _sdrKs))
            _sdrLentityReports = defaultdict(list)
            for r in reports:
                if r.DocumentType == "SDR L":
                    _sdrLentityReports[r.EntityRegistrantName].append(r)
            if not _sdrLentityReports:
                efmFiling.error("EFM.SDR.1.3",
                                _("Filing has no SDR L reports"))
            for sdrLentity, sdrLentityReports in _sdrLentityReports.items():
                if len(sdrLentityReports) > 1:
                    efmFiling.error("EFM.SDR.1.4",
                                    _("Filing entity has multiple SDR L reports: %(entity)s"),
                                    {"entity": sdrLentity},
                                    (r.uri for r in sdrLentityReports))
            # check for required extension files (schema, pre, lbl)
            for r in reports:
                hasSch = hasPre = hasCal = hasLbl = False
                for f in r.reportSubmissionFiles:
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
                                    {"docType": r.DocumentType, "missingFiles": missingFiles[2:]},
                                    r.uri)
                if not r.hasUsGaapTaxonomy:
                    efmFiling.error("EFM.SDR.1.6",
                                    _("%(documentType)s submission must use a US GAAP standard schema"),
                                    {"documentType": r.DocumentType},
                                    r.uri)
        modelManager.efmFiling.close()
        del modelManager.efmFiling
    
class Filing:
    def __init__(self, cntlr, options, filesource, entrypointfiles, sourceZipStream, responseZipStream):
        self.cntlr = cntlr
        self.options = options
        self.filesource = filesource
        self.entrypointfiles = entrypointfiles
        self.sourceZipStream = sourceZipStream
        self.responseZipStream = responseZipStream
        self.reports = []
        
    def close(self):
        self.__dict__.clear() # dereference all contents
        
    def addReport(self, modelXbrl):
        self.reports.append(Report(modelXbrl))
        
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
    def __init__(self, modelXbrl):
        self.uri = modelXbrl.modelDocument.uri
        for attrName in Report.REPORT_ATTRS:
            setattr(self, attrName, None)
        self.documentType = None
        self.instanceName = modelXbrl.modelDocument.basename
        for f in modelXbrl.facts:
            cntx = f.context
            if cntx is not None and cntx.isStartEndPeriod and not cntx.hasSegment:
                if f.qname.localName in Report.REPORT_ATTRS and f.xValue:
                    setattr(self, f.qname.localName, f.xValue)
        self.reportSubmissionFiles = set()
        self.standardTaxonomyFiles = set()
        self.hasUsGaapTaxonomy = False
        reportDir = os.path.dirname(modelXbrl.modelDocument.uri)
        def addRefDocs(doc):
            for refDoc in doc.referencesDocument.keys():
                if refDoc.uri not in self.reportSubmissionFiles:
                    if refDoc.uri.startswith(reportDir):
                        self.reportSubmissionFiles.add(refDoc.uri)
                    addRefDocs(refDoc)
                if refDoc.type == ModelDocument.Type.SCHEMA:
                    nsAuthority = authority(refDoc.targetNamespace, includeScheme=False)
                    nsPath = refDoc.targetNamespace.split('/')
                    if len(nsPath) > 2:
                        if nsAuthority in ("fasb.org", "xbrl.us") and nsPath[-2] == "us-gaap":
                            self.hasUsGaapTaxonomy = True
        addRefDocs(modelXbrl.modelDocument)

    def close(self):
        self.__dict__.clear() # dereference all contents

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate EFM',
    'version': '0.9',
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
    'CntlrCmdLine.Batch.Start': filingStart,
    'CntlrCmdLine.Xbrl.Loaded': xbrlLoaded,
    'CntlrCmdLine.Batch.End': filingEnd,
}
