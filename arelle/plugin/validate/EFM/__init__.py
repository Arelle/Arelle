'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.

Input file parameters may be in JSON (without newlines for pretty printing as below):


[ {# current fields in JSON structure from Arelle Wrapper, per instance
   "file": "file path to instance or html",
   "cik": "1234567890",
   "cikNameList": { "cik1": "name1", "cik2":"name2", "cik3":"name3"...},
   "submissionType" : "SDR-A",
   "exhibitType": "EX-99.K", 
   "accessionNumber":"0001125840-15-000159" ,
   # new fields
   "periodOfReport": "mm-dd-yyyy",
   "entity.fyEnd": "mm/dd",
   "voluntaryFilerFlag": true/false, # JSON Boolean or absent
   "wellKnownSeasonedIssuerFlag": true/false, # JSON Boolean or absent
   "shellCompanyFlag": true/false, true/false, # JSON Boolean or absent
   "acceleratedFilerStatus": true/false, # JSON Boolean or absent
   "smallBusinessFlag": true/false, # JSON Boolean or absent
   "emergingGrowthCompanyFlag": true/false, # JSON Boolean or absent
   "exTransitionPeriodFlag": true/false, # JSON Boolean or absent
   # filer - use "cik" above
   "invCompanyType": "N-1A" # from table of investment company types
   "rptIncludeAllSeriesFlag": true/false, # JSON Boolean or absent
   "rptSeriesClassInfo.seriesIds": ["S0000990666", ...] # list of EDGAR seriesId values
   "newClass2.seriesIds": [] # //seriesId xpath result on submission headers
   },
 {"file": "file 2"...
]

For test case operation, the above fields accepted from testcase variation:
  <data>
     <conf:parameter name="cikName" datatype="xs:string" value="cik1:name1" xmlns="" xmlns:conf="http://edgar/2009/conformance" />
     <conf:parameter name="cikName" datatype="xs:string" value="cik2:name2" xmlns="" xmlns:conf="http://edgar/2009/conformance" />
     <conf:parameter name="cikName" datatype="xs:string" value="cik3:name3" xmlns="" xmlns:conf="http://edgar/2009/conformance" />
     <conf:parameter name="submissionType" datatype="xs:string" value="8-K" xmlns="" xmlns:conf="http://edgar/2009/conformance" />
     <conf:parameter name="periodOfReport" datatype="xs:string" value="12-31-2017" xmlns="" xmlns:conf="http://edgar/2009/conformance" />
     <conf:parameter name="voluntaryFilerFlag" datatype="xs:boolean" value="true" xmlns="" xmlns:conf="http://edgar/2009/conformance" />
     <conf:parameter name="coregCikFileNumber" datatype="xs:string" value="cik1:fileNbr1" xmlns="" xmlns:conf="http://edgar/2009/conformance" />
     <conf:parameter name="coregCikFileNumber" datatype="xs:string" value="cik2:fileNbr2" xmlns="" xmlns:conf="http://edgar/2009/conformance" />
     <conf:parameter name="coregCikFileNumber" datatype="xs:string" value="cik3:fileNbr3" xmlns="" xmlns:conf="http://edgar/2009/conformance" />
     <conf:parameter name="sroId" datatype="xs:string" value="NASD" xmlns="" xmlns:conf="http://edgar/2009/conformance" />
     <conf:parameter name="sroId" datatype="xs:string" value="NYSE" xmlns="" xmlns:conf="http://edgar/2009/conformance" />
     ...
     <instance readMeFirst="true">e9999999ng-20081231.xml</instance>
   <data>

(Accession number is only needed for those EdgarRenderer output transformations of 
FilingSummary.xml which require it as a parameter (such as EDGAR's internal workstations, 
which have a database that requires accession number as part of the query string to retrieve 
a file of a submission.)

On Windows, the input file argument must be specially quoted if passed in via Java
due to a Java bug on Windows shell interface (without the newlines for pretty printing below):

"[{\"file\":\"z:\\Documents\\dir\\gpc_gd1-20130930.htm\", 
    \"cik\": \"0000350001\", 
    \"cikNameList\": {\"0000350001\":\"BIG FUND TRUST CO\"},
    \"submissionType\":\"SDR-A\", \"exhibitType\":\"EX-99.K SDR.INS\"}]" 

To build cached deprecated concepts files (requires internet access):
   --buildDeprecatedConceptsFiles 
'''
import os, io, json, zipfile, logging
jsonIndent = 1  # None for most compact, 0 for left aligned
from decimal import Decimal
from lxml.etree import XML, XMLSyntaxError
from arelle import ModelDocument, ModelValue, XmlUtil, FileSource
from arelle.ModelValue import qname
from arelle.PluginManager import pluginClassMethods  # , pluginMethodsForClasses, modulePluginInfos
from arelle.UrlUtil import authority, relativeUri
from arelle.ValidateFilingText import referencedFiles
from .Document import checkDTSdocument
from .Filing import validateFiling
try:
    import regex as re
except ImportError:
    import re
from collections import defaultdict


def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("EFM", "EFMplugin"),)

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateEFMplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "EFMplugin", False)
    if not (val.validateEFMplugin):
        return

    val.params = {}
    parameterNames = ("CIK", "cik", "cikList", "cikNameList", "submissionType", "exhibitType", # CIK or cik both allowed
                      "periodOfReport", "entity.fyEnd", "voluntaryFilerFlag", 
                      "wellKnownSeasonedIssuerFlag", "shellCompanyFlag", "acceleratedFilerStatus", "smallBusinessFlag",
                      "emergingGrowthCompanyFlag", "exTransitionPeriodFlag", "invCompanyType",
                      "rptIncludeAllSeriesFlag", "rptSeriesClassInfo.seriesIds", "newClass2.seriesIds")
    if parameters: # parameter-provided CIKs and registrant names
        for paramName in parameterNames:
            p = parameters.get(ModelValue.qname(paramName,noPrefixIsNoNamespace=True))
            if p and len(p) == 2 and p[1] not in ("null", "None", None):
                val.params[paramName] = p[1]
        if "CIK" in val.params: # change to lower case key
            val.params["cik"] = val.params["CIK"]
            del val.params["CIK"]
        p = parameters.get(ModelValue.qname("ELOparams",noPrefixIsNoNamespace=True))
        if p and len(p) == 2 and p[1] not in ("null", "None", None):
            try:
                for key, value in json.loads(p[1]).items():
                    val.params[{"CIK":"cik"}.get(key,key)] = value # change upper case CIK to lower case
            except (ValueError, AttributeError, TypeError):
                val.modelXbrl.error("arelle.testcaseVariationParameters",
                    _("parameter ELOparam has malformed JSON %(json)s object"),
                    modelXbrl=val.modelXbrl, json=p[1][:100])
    # parameters may also come from report entryPoint (such as exhibitType for SDR)
    if hasattr(val.modelXbrl.modelManager, "efmFiling"):
        efmFiling = val.modelXbrl.modelManager.efmFiling
        if efmFiling.reports: # possible that there are no reports
            entryPoint = efmFiling.reports[-1].entryPoint
            for paramName in parameterNames: # cik is lower case here
                if paramName in entryPoint and entryPoint[paramName] not in (None, ""):
                    val.params[paramName] = entryPoint[paramName] # if not set uses prior value

    # exhibitType may be an attachmentType, if so remove ".INS"
    if val.params.get("exhibitType", "").endswith(".INS"):
        val.params["exhibitType"] = val.params["exhibitType"][:-4]
    
    if isinstance(val.params.get("cikNameList", None), str):
        # cik1, cik2, cik3 in cikList and name1|Edgar|name2|Edgar|name3 in cikNameList strings
        _filerIdentifiers = val.params["cikList"].split(",") if "cikList" in val.params else []
        _filerNames = val.params["cikNameList"].split("|Edgar|") if "cikNameList" in val.params else []
        if _filerIdentifiers:
            if len(_filerNames) not in (0, len(_filerIdentifiers)):
                val.modelXbrl.error(("EFM.6.05.24.parameters", "GFM.3.02.02"),
                    _("parameters for cikList and cikNameList different list entry counts: %(cikList)s, %(cikNameList)s"),
                    modelXbrl=val.modelXbrl, cikList=_filerIdentifiers, cikNameList=_filerNames)
            if _filerNames:
                val.params["cikNameList"]=dict((_cik,_filerNames[i] if i < len(_filerNames) else None)
                                                for i, _cik in enumerate(_filerIdentifiers))
            else:
                val.params["cikNameList"]=dict((_cik,None) for _cik in _filerIdentifiers)
            del val.params["cikList"]
        elif _filerNames:
            val.modelXbrl.error(("EFM.6.05.24.parameters", "GFM.3.02.02"),
                _("parameters for cikNameList provided but missing corresponding cikList: %(cikNameList)s"),
                modelXbrl=val.modelXbrl, cikNameList=_filerNames)
            del val.params["cikNameList"] # can't process without cik's as keys

    if val.params.get("exhibitType", "") == "EX-2.01": # only applicable for edgar production and parameterized testcases
        val.EFM60303 = "EFM.6.23.01"
    else:
        val.EFM60303 = "EFM.6.03.03"
                
    if any((concept.qname.namespaceURI in val.disclosureSystem.standardTaxonomiesDict and concept.modelDocument.inDTS) 
           for concept in val.modelXbrl.nameConcepts.get("UTR",())):
        val.validateUTR = True
        
    modelManager = val.modelXbrl.modelManager
    if hasattr(modelManager, "efmFiling"):
        efmFiling = modelManager.efmFiling
        efmFiling.submissionType = val.params.get("submissionType")


def validateXbrlFinally(val, *args, **kwargs):
    if not (val.validateEFMplugin):
        return

    modelXbrl = val.modelXbrl

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)
    
    validateFiling(val, modelXbrl, isEFM=True)

    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)
    
def validateXbrlDtsDocument(val, modelDocument, isFilingDocument, *args, **kwargs):
    if not (val.validateEFMplugin):
        return

    checkDTSdocument(val, modelDocument, isFilingDocument)
    
def filingStart(cntlr, options, filesource, entrypointFiles, sourceZipStream=None, responseZipStream=None, *args, **kwargs):
    modelManager = cntlr.modelManager
    # cntlr.addToLog("TRACE EFM filing start val={} plugin={}".format(modelManager.validateDisclosureSystem, getattr(modelManager.disclosureSystem, "EFMplugin", False)))
    if modelManager.validateDisclosureSystem and getattr(modelManager.disclosureSystem, "EFMplugin", False):
        # cntlr.addToLog("TRACE EFM filing start 2 classes={} moduleInfos={}".format(pluginMethodsForClasses, modulePluginInfos))
        modelManager.efmFiling = Filing(cntlr, options, filesource, entrypointFiles, sourceZipStream, responseZipStream)
        # this event is called for filings (of instances) as well as test cases, for test case it just keeps options accessible
        for pluginXbrlMethod in pluginClassMethods("EdgarRenderer.Filing.Start"):
            pluginXbrlMethod(cntlr, options, entrypointFiles, modelManager.efmFiling)
        # check if any entrypointFiles have an encryption is specified
        if isinstance(entrypointFiles, list):
            for pluginXbrlMethod in pluginClassMethods("Security.Crypt.Filing.Start"):
                pluginXbrlMethod(modelManager.efmFiling, options, filesource, entrypointFiles, sourceZipStream)
        
            
def guiTestcasesStart(cntlr, modelXbrl, *args, **kwargs):
    modelManager = cntlr.modelManager
    if (cntlr.hasGui and modelXbrl.modelDocument.type in ModelDocument.Type.TESTCASETYPES and
         modelManager.validateDisclosureSystem and getattr(modelManager.disclosureSystem, "EFMplugin", False)):
        modelManager.efmFiling = Filing(cntlr)
            
def testcasesStart(cntlr, options, modelXbrl, *args, **kwargs):
    # a test or RSS cases run is starting, in which case testcaseVariation... events have unique efmFilings
    modelManager = cntlr.modelManager
    if (hasattr(modelManager, "efmFiling") and
        modelXbrl.modelDocument.type in ModelDocument.Type.TESTCASETYPES):
        efmFiling = modelManager.efmFiling
        efmFiling.close() # not needed, dereference
        del modelManager.efmFiling
        if not hasattr(modelXbrl, "efmOptions") and options: # may have already been set by EdgarRenderer in gui startup
            modelXbrl.efmOptions = options  # save options in testcase's modelXbrl
               
def xbrlLoaded(cntlr, options, modelXbrl, entryPoint, *args, **kwargs):
    # cntlr.addToLog("TRACE EFM xbrl loaded")
    modelManager = cntlr.modelManager
    if hasattr(modelManager, "efmFiling"):
        if (modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or 
            modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL):
            efmFiling = modelManager.efmFiling
            efmFiling.addReport(modelXbrl)
            _report = efmFiling.reports[-1]
            _report.entryPoint = entryPoint
            if "accessionNumber" in entryPoint and not hasattr(efmFiling, "accessionNumber"):
                efmFiling.accessionNumber = entryPoint["accessionNumber"]
            if "exhibitType" in entryPoint and not hasattr(_report, "exhibitType"):
                _report.exhibitType = entryPoint["exhibitType"]
            efmFiling.arelleUnitTests = modelXbrl.arelleUnitTests.copy() # allow unit tests to be used after instance processing finished
        elif modelXbrl.modelDocument.type == ModelDocument.Type.RSSFEED:
            testcasesStart(cntlr, options, modelXbrl)

def xbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
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

def filingValidate(cntlr, options, filesource, entrypointFiles, sourceZipStream=None, responseZipStream=None, *args, **kwargs):
    # cntlr.addToLog("TRACE EFM xbrl validate")
    modelManager = cntlr.modelManager
    if hasattr(modelManager, "efmFiling"):
        efmFiling = modelManager.efmFiling
        reports = efmFiling.reports
        # check for dup inline and regular instances
        # SDR checks
        if any(report.documentType and report.documentType.endswith(" SDR") 
               for report in reports):
            _kSdrs = [r for r in reports if r.documentType == "K SDR"]
            if not _kSdrs and efmFiling.submissionType in ("SDR", "SDR-A"):
                efmFiling.error("EFM.6.03.08.sdrHasNoKreports",
                                _("SDR filing has no K SDR reports"))
            elif len(_kSdrs) > 1:
                efmFiling.error("EFM.6.03.08.sdrHasMultipleKreports",
                                _("SDR filing has multiple K SDR reports for %(entities)s"),
                                {"entities": ", ".join(r.entityRegistrantName for r in _kSdrs)}, 
                                (r.url for r in _kSdrs))
            _lSdrEntityReports = defaultdict(list)
            for r in reports:
                if r.documentType == "L SDR":
                    _lSdrEntityReports[r.entityCentralIndexKey if r.entityCentralIndexKey != "0000000000" 
                                       else r.entityRegistrantName].append(r)
            for lSdrEntity, lSdrEntityReports in _lSdrEntityReports.items():
                if len(lSdrEntityReports) > 1:
                    efmFiling.error("EFM.6.05.24.multipleLSdrReportsForEntity",
                                    _("Filing entity has multiple L SDR reports: %(entity)s"),
                                    {"entity": lSdrEntity},
                                    (r.url for r in lSdrEntityReports))
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
                    efmFiling.error("EFM.6.03.02.sdrMissingFiles",
                                    _("%(docType)s report missing files: %(missingFiles)s"),
                                    {"docType": r.documentType, "missingFiles": missingFiles[2:]},
                                    r.url)
                if not r.hasUsGaapTaxonomy:
                    efmFiling.error("EFM.6.03.02.sdrMissingStandardSchema",
                                    _("%(documentType)s submission must use a US GAAP standard schema"),
                                    {"documentType": r.documentType},
                                    r.url)
                if hasattr(r, "exhibitType") and r.exhibitType not in ("EX-99.K SDR", "EX-99.L SDR", "EX-99.K SDR.INS", "EX-99.L SDR.INS"):
                    efmFiling.error("EFM.6.03.02.sdrHasNonSdrExhibit",
                                    _("An SDR filling contains non-SDR exhibit type %(exhibitType)s document type %(documentType)s"),
                                    {"documentType": r.documentType, "exhibitType": r.exhibitType},
                                    r.url)
        _exhibitTypeReports = defaultdict(list)
        for r in reports:
            if hasattr(r, "exhibitType") and r.exhibitType:
                _exhibitTypeReports[r.exhibitType.partition(".")[0]].append(r)
        if len(_exhibitTypeReports) > 1:
            efmFiling.error("EFM.6.03.08",
                            _("A filling contains multiple exhibit types %(exhibitTypes)s."),
                            {"exhibitTypes": ", ".join(_exhibitTypeReports.keys())},
                            [r.url for r in reports])
        for _exhibitType, _exhibitReports in _exhibitTypeReports.items():
            if _exhibitType not in ("EX-99",) and len(_exhibitReports) > 1:
                efmFiling.error("EFM.6.03.08.moreThanOneIns",
                                _("A filing contains more than one instance for exhibit type %(exhibitType)s."),
                                {"exhibitType": _exhibitType},
                                [r.url for r in _exhibitReports])
        
def roleTypeName(modelXbrl, roleURI, *args, **kwargs):
    modelManager = modelXbrl.modelManager
    if hasattr(modelManager, "efmFiling"):
        modelRoles = modelXbrl.roleTypes.get(roleURI, ())
        if modelRoles and modelRoles[0].definition:
            return re.sub(r"\{\s*(transposed|unlabeled|elements)\s*\}","", modelRoles[0].definition.rpartition('-')[2], flags=re.I).strip()
        return roleURI
    return None
    
def filingEnd(cntlr, options, filesource, entrypointFiles, sourceZipStream=None, responseZipStream=None, *args, **kwargs):
    #cntlr.addToLog("TRACE EFM filing end")
    modelManager = cntlr.modelManager
    if hasattr(modelManager, "efmFiling"):
        for pluginXbrlMethod in pluginClassMethods("EdgarRenderer.Filing.End"):
            pluginXbrlMethod(cntlr, options, filesource, modelManager.efmFiling, sourceZipStream=sourceZipStream)
        #cntlr.addToLog("TRACE EdgarRenderer end")
        # save JSON file of instances and referenced documents
        filingReferences = dict((report.url, report)
                                for report in modelManager.efmFiling.reports)

        modelManager.efmFiling.close()
        del modelManager.efmFiling
        #cntlr.addToLog("TRACE EFN filing end complete")
        
def rssItemXbrlLoaded(modelXbrl, rssWatchOptions, rssItem, *args, **kwargs):
    # Validate of RSS feed item (simulates filing & cmd line load events
    if hasattr(rssItem.modelXbrl, "efmOptions"):
        testcaseVariationXbrlLoaded(rssItem.modelXbrl, modelXbrl)
    
def rssItemValidated(val, modelXbrl, rssItem, *args, **kwargs):
    # After validate of RSS feed item (simulates report and end of filing events)
    if hasattr(rssItem.modelXbrl, "efmOptions"):
        testcaseVariationValidated(rssItem.modelXbrl, modelXbrl)
        
def testcaseVariationXbrlLoaded(testcaseModelXbrl, instanceModelXbrl, modelTestcaseVariation, *args, **kwargs):
    # Validate of RSS feed item or testcase variation (simulates filing & cmd line load events
    modelManager = instanceModelXbrl.modelManager
    if (hasattr(testcaseModelXbrl, "efmOptions") and 
        modelManager.validateDisclosureSystem and getattr(modelManager.disclosureSystem, "EFMplugin", False) and 
        (instanceModelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or 
        instanceModelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL)):
        cntlr = modelManager.cntlr
        options = testcaseModelXbrl.efmOptions
        entrypointFiles = [{"file":instanceModelXbrl.modelDocument.uri}]
        if not hasattr(modelManager, "efmFiling"): # first instance of filing
            modelManager.efmFiling = Filing(cntlr, options, instanceModelXbrl.fileSource, entrypointFiles, None, None, instanceModelXbrl.errorCaptureLevel)
            # this event is called for filings (of instances) as well as test cases, for test case it just keeps options accessible
            for pluginXbrlMethod in pluginClassMethods("EdgarRenderer.Filing.Start"):
                pluginXbrlMethod(cntlr, options, entrypointFiles, modelManager.efmFiling)
        modelManager.efmFiling.addReport(instanceModelXbrl)
        _report = modelManager.efmFiling.reports[-1]
        _report.entryPoint = entrypointFiles[0]
        modelManager.efmFiling.arelleUnitTests = instanceModelXbrl.arelleUnitTests.copy() # allow unit tests to be used after instance processing finished
        # check for parameters on instance
        for _instanceElt in XmlUtil.descendants(modelTestcaseVariation, "*", "instance", "readMeFirst", "true", False):
            if instanceModelXbrl.modelDocument.uri.endswith(_instanceElt.text):
                if _instanceElt.get("exhibitType"):
                    _report.entryPoint["exhibitType"] = _report.exhibitType = _instanceElt.get("exhibitType")
                break
    
def testcaseVariationXbrlValidated(testcaseModelXbrl, instanceModelXbrl, *args, **kwargs): 
    modelManager = instanceModelXbrl.modelManager
    if (hasattr(modelManager, "efmFiling") and 
        (instanceModelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or 
        instanceModelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL)):
        efmFiling = modelManager.efmFiling
        _report = modelManager.efmFiling.reports[-1]
        for pluginXbrlMethod in pluginClassMethods("EdgarRenderer.Xbrl.Run"):
            pluginXbrlMethod(modelManager.cntlr, efmFiling.options, instanceModelXbrl, efmFiling, _report)

def testcaseVariationValidated(testcaseModelXbrl, instanceModelXbrl, errors=None, *args, **kwargs): 
    modelManager = instanceModelXbrl.modelManager
    if (hasattr(modelManager, "efmFiling") and 
        (instanceModelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or 
        instanceModelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL)):
        efmFiling = modelManager.efmFiling
        if isinstance(errors, list):
            del efmFiling.errors[:]
        # validate report types
        filingValidate(efmFiling.cntlr, efmFiling.options, efmFiling.filesource, efmFiling.entrypointfiles, efmFiling.sourceZipStream, efmFiling.responseZipStream)        # validate each report
        if isinstance(errors, list):
            errors.extend(efmFiling.errors)
        # simulate filingEnd
        filingEnd(modelManager.cntlr, efmFiling.options, modelManager.filesource, [])
        # flush logfile (assumed to be buffered, empty the buffer for next filing)
        testcaseModelXbrl.modelManager.cntlr.logHandler.flush()
        
def fileSourceFile(cntlr, filepath, binary, stripDeclaration):
    modelManager = cntlr.modelManager
    if hasattr(modelManager, "efmFiling"):
        for pluginXbrlMethod in pluginClassMethods("Security.Crypt.FileSource.File"):
            _file = pluginXbrlMethod(cntlr, modelManager.efmFiling, filepath, binary, stripDeclaration)
            if _file is not None:
                return _file
    return None
        
def fileSourceExists(cntlr, filepath):
    modelManager = cntlr.modelManager
    if hasattr(modelManager, "efmFiling"):
        for pluginXbrlMethod in pluginClassMethods("Security.Crypt.FileSource.Exists"):
            _existence = pluginXbrlMethod(modelManager.efmFiling, filepath)
            if _existence is not None:
                return _existence
    return None

def commandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options to store to database
    parser.add_option("--build-deprecated-concepts-file", 
                      action="store_true", 
                      dest="buildDeprecatedConceptsFile", 
                      help=_("Build EFM Validation deprecated concepts file (pre-cache before use)"))

def utilityRun(self, options, *args, **kwargs):
    if options.buildDeprecatedConceptsFile:
        from .Util import buildDeprecatedConceptDatesFiles
        buildDeprecatedConceptDatesFiles(self)
    
class Filing:
    def __init__(self, cntlr, options=None, filesource=None, entrypointfiles=None, sourceZipStream=None, responseZipStream=None, errorCaptureLevel=None):
        self.cntlr = cntlr
        self.options = options
        self.filesource = filesource
        self.entrypointfiles = entrypointfiles
        self.sourceZipStream = sourceZipStream
        self.responseZipStream = responseZipStream
        self.submissionType = None
        self.reports = []
        self.renderedFiles = set() # filing-level rendered files
        self.reportZip = None
        if responseZipStream:
            self.setReportZipStreamMode('w')
        else:
            try: #zipOutputFile only present with EdgarRenderer plugin options
                if options and options.zipOutputFile:
                    if not os.path.isabs(options.zipOutputFile):
                        zipOutDir = os.path.dirname(filesource.basefile)
                        zipOutFile = os.path.join(zipOutDir,options.zipOutputFile)
                    else:
                        zipOutFile = options.zipOutputFile
                    self.reportZip = zipfile.ZipFile(zipOutFile, 'w', zipfile.ZIP_DEFLATED, True)
            except AttributeError:
                self.reportZip = None
        self.errorCaptureLevel = errorCaptureLevel or logging._checkLevel("INCONSISTENCY")
        self.errors = []
        self.arelleUnitTests = {} # copied from each instance loaded
        for pluginXbrlMethod in pluginClassMethods("Security.Crypt.Init"):
            pluginXbrlMethod(self, options, filesource, entrypointfiles, sourceZipStream)
                
    def setReportZipStreamMode(self, mode): # mode is 'w', 'r', 'a'
        # required to switch in-memory zip stream between write, read, and append modes
        if self.responseZipStream:
            if self.reportZip: # already open, close and reseek underlying stream
                self.reportZip.close()
                self.responseZipStream.seek(0)
            self.reportZip = zipfile.ZipFile(self.responseZipStream, mode, zipfile.ZIP_DEFLATED, True)
        
    def close(self):
        ''' MetaFiling.json (not needed?) list of all files written out
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
        '''
        if self.options and self.options.logFile:
            if self.reportZip and self.reportZip.fp is not None:  # open zipfile
                _logFile = self.options.logFile
                _logFileExt = os.path.splitext(_logFile)[1]
                if _logFileExt == ".xml":
                    _logStr = self.cntlr.logHandler.getXml(clearLogBuffer=False)  # may be saved to file later or flushed in web interface
                elif _logFileExt == ".json":
                    _logStr = self.cntlr.logHandler.getJson(clearLogBuffer=False)
                else:  # no ext or  _logFileExt == ".txt":
                    _logStr = self.cntlr.logHandler.getText(clearLogBuffer=False)
                self.reportZip.writestr(_logFile, _logStr)
            #else:
            #    with open(_logFile, "wt", encoding="utf-8") as fh:
            #        fh.write(_logStr)
        if self.reportZip:  # ok to close if already closed
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
            if isinstance(self.entrypointfiles[0], dict):
                _baseFile = self.entrypointfiles[0].get("file", ".")
            else:
                _baseFile = self.entrypointfiles[0]
            relFiles = [relativeUri(_baseFile, f) for f in file]
        else:
            relFiles = None
        self.cntlr.addToLog(message, messageCode=messageCode, messageArgs=messageArgs, file=relFiles, level="ERROR")
        self.errors.append(messageCode)
        
    @property
    def hasInlineReport(self):
        return any(getattr(report, "isInline", False) for report in self.reports)
    
    def writeFile(self, filepath, data):
        # write the data (string or binary)
        for pluginXbrlMethod in pluginClassMethods("Security.Crypt.Write"):
            if pluginXbrlMethod(self, filepath, data):
                return
        with io.open(filepath, "wt" if isinstance(data, str) else "wb") as fh:
            fh.write(data)
        
class Report:
    REPORT_ATTRS = {"DocumentType", "DocumentPeriodEndDate", "EntityRegistrantName",
                    "EntityCentralIndexKey", "CurrentFiscalYearEndDate", "DocumentFiscalYearFocus"}
    def lc(self, name):
        return name[0].lower() + name[1:]
    
    def __init__(self, modelXbrl):
        self.isInline = modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL
        self.url = modelXbrl.modelDocument.uri
        self.basename = modelXbrl.modelDocument.basename
        self.filepath = modelXbrl.modelDocument.filepath
        for attrName in Report.REPORT_ATTRS:
            setattr(self, self.lc(attrName), None)
        self.instanceName = modelXbrl.modelDocument.basename
        for f in modelXbrl.facts:
            cntx = f.context
            if cntx is not None and cntx.isStartEndPeriod and not cntx.hasSegment:
                if f.qname is not None and f.qname.localName in Report.REPORT_ATTRS and f.xValue:
                    setattr(self, self.lc(f.qname.localName), f.xValue)
        self.reportedFiles = {modelXbrl.modelDocument.basename} | referencedFiles(modelXbrl)
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
                        self.reportedFiles.add(refDoc.filepath[len(sourceDir)+1:]) # add file name within source directory
                    addRefDocs(refDoc)
                if refDoc.type == ModelDocument.Type.SCHEMA and refDoc.targetNamespace:
                    nsAuthority = authority(refDoc.targetNamespace, includeScheme=False)
                    nsPath = refDoc.targetNamespace.split('/')
                    if len(nsPath) > 2:
                        if nsAuthority in ("fasb.org", "xbrl.us") and nsPath[-2] == "us-gaap":
                            self.hasUsGaapTaxonomy = True
        addRefDocs(modelXbrl.modelDocument)
            
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
    'version': '1.18.3', # SEC EDGAR release 18.3
    'description': '''EFM Validation.''',
    'license': 'Apache-2',
    'import': ('transforms/SEC',), # SEC inline can use SEC transformations
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2013-15 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
    'Validate.XBRL.DTS.document': validateXbrlDtsDocument,
    'ModelXbrl.RoleTypeName': roleTypeName,
    'CntlrCmdLine.Filing.Start': filingStart,
    'CntlrWinMain.Xbrl.Loaded': guiTestcasesStart,
    'Testcases.Start': testcasesStart,
    'CntlrCmdLine.Options': commandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': utilityRun,
    'CntlrCmdLine.Xbrl.Loaded': xbrlLoaded,
    'CntlrCmdLine.Xbrl.Run': xbrlRun,
    'CntlrCmdLine.Filing.Validate': filingValidate,
    'CntlrCmdLine.Filing.End': filingEnd,
    'RssItem.Xbrl.Loaded': rssItemXbrlLoaded,
    'Validate.RssItem': rssItemValidated,
    'TestcaseVariation.Xbrl.Loaded': testcaseVariationXbrlLoaded,
    'TestcaseVariation.Xbrl.Validated': testcaseVariationXbrlValidated,
    'TestcaseVariation.Validated': testcaseVariationValidated,
    'FileSource.File': fileSourceFile,
    'FileSource.Exists': fileSourceExists
}
