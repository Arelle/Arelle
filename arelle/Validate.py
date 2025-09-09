'''
See COPYRIGHT.md for copyright information.
'''
import bisect
import fnmatch
import os, sys, traceback, logging
import time
from urllib.parse import unquote
import zipfile

import regex as re
from collections import defaultdict, OrderedDict
from arelle import (FileSource, ModelXbrl, ModelDocument, ModelVersReport, XbrlConst,
               ValidateXbrl, ValidateVersReport,
               ValidateInfoset, ViewFileRenderedLayout, UrlUtil)
from arelle.PythonUtil import isLegacyAbs
from arelle.formula import ValidateFormula
from arelle.ModelDocument import Type, ModelDocumentReference, load as modelDocumentLoad
from arelle.ModelDtsObject import ModelResource
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelObject import ModelObject
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelTestcaseObject import testcaseVariationsByTarget, ModelTestcaseVariation
from arelle.ModelValue import (qname, QName)
from arelle.PluginManager import pluginClassMethods
from arelle.packages.report.DetectReportPackage import isReportPackageExtension
from arelle.packages.report.ReportPackageValidator import ReportPackageValidator
from arelle.rendering import RenderingEvaluator
from arelle.utils.EntryPointDetection import filesourceEntrypointFiles
from arelle.XmlUtil import collapseWhitespace, xmlstring

def validate(modelXbrl):
    validate = Validate(modelXbrl)
    validate.validate()

class ValidationException(Exception):
    def __init__(self, message, severity, code):
        self.message = message
        self.severity = severity
        self.code = code
    def __repr__(self):
        return "{0}({1})={2}".format(self.code,self.severity,self.message)

commaSpaceSplitPattern = re.compile(r",\s*")

class Validate:
    """Validation operations are separated from the objects that are validated, because the operations are
    complex, interwoven, and factored quite differently than the objects being validated.
    There are these validation modules at present: validation infrastructure, test suite and submission control,
    versioning report validation, XBRL base spec, dimensions, and formula linkbase validation,
    Edgar and Global Filer Manual validation.
    """
    def __init__(self, modelXbrl):
        self.modelXbrl = modelXbrl
        if modelXbrl.modelManager.validateDisclosureSystem:
            self.instValidator = ValidateXbrl.ValidateXbrl(modelXbrl)
            self.formulaValidator = ValidateXbrl.ValidateXbrl(modelXbrl)
        else:
            self.instValidator = ValidateXbrl.ValidateXbrl(modelXbrl)
            self.formulaValidator = self.instValidator
        if hasattr(modelXbrl,"fileSource"):
            self.useFileSource = modelXbrl.fileSource
        else:
            self.useFileSource = None

    def filterTestcaseVariation(self, modelTestcaseVariation: ModelTestcaseVariation):
        patterns = self.modelXbrl.modelManager.formulaOptions.testcaseFilters
        if not patterns:
            return True
        variationIdPath = f'{unquote(modelTestcaseVariation.base)}:{modelTestcaseVariation.id}'
        for pattern in patterns:
            if fnmatch.fnmatch(variationIdPath, pattern):
                return True
        return False

    def close(self):
        self.instValidator.close(reusable=False)
        self.formulaValidator.close(reusable=False)
        self.__dict__.clear()   # dereference variables

    def validate(self):
        if not self.modelXbrl.modelDocument:
            self.modelXbrl.info("arelle:notValidated",
                _("Validation skipped, document not successfully loaded: %(file)s"),
                modelXbrl=self.modelXbrl, file=self.modelXbrl.fileSource.url)
        elif self.modelXbrl.modelDocument.type in (Type.TESTCASESINDEX, Type.REGISTRY, Type.TESTCASE, Type.REGISTRYTESTCASE):
            try:
                _disclosureSystem = self.modelXbrl.modelManager.disclosureSystem
                if _disclosureSystem.name:
                    self.modelXbrl.info("info",
                        _("Disclosure system %(disclosureSystemName)s, version %(disclosureSystemVersion)s"),
                        modelXbrl=self.modelXbrl, disclosureSystemName=_disclosureSystem.name, disclosureSystemVersion=_disclosureSystem.version)
                if self.modelXbrl.modelDocument.type in (Type.TESTCASESINDEX, Type.REGISTRY):
                    _name = self.modelXbrl.modelDocument.basename
                    for testcasesElement in self.modelXbrl.modelDocument.xmlRootElement.iter():
                        if isinstance(testcasesElement,ModelObject) and testcasesElement.localName in ("testcases", "registries", "testSuite"):
                            if testcasesElement.get("name"):
                                _name = testcasesElement.get("name")
                            break
                    self.modelXbrl.info("info", _("Testcases - %(name)s"), modelXbrl=self.modelXbrl.modelDocument, name=_name)
                    _statusCounts = OrderedDict((("pass",0),("fail",0)))
                    for doc in sorted(self.modelXbrl.modelDocument.referencesDocument.keys(), key=lambda doc: doc.uri):
                        self.validateTestcase(doc)  # testcases doc's are sorted by their uri (file names), e.g., for formula
                        for tv in getattr(doc, "testcaseVariations", ()):
                            _statusCounts[tv.status] = _statusCounts.get(tv.status, 0) + 1
                    self.modelXbrl.info("arelle:testSuiteResults", ", ".join("{}={}".format(k,c) for k, c in _statusCounts.items() if k))
                elif self.modelXbrl.modelDocument.type in (Type.TESTCASE, Type.REGISTRYTESTCASE):
                    self.validateTestcase(self.modelXbrl.modelDocument)
            except Exception as err:
                self.modelXbrl.error("exception:" + type(err).__name__,
                    _("Testcase validation exception: %(error)s, testcase: %(testcase)s"),
                    modelXbrl=self.modelXbrl,
                    testcase=self.modelXbrl.modelDocument.basename, error=err,
                    #traceback=traceback.format_tb(sys.exc_info()[2]),
                    exc_info=True)
        elif self.modelXbrl.modelDocument.type == Type.VERSIONINGREPORT:
            try:
                ValidateVersReport.ValidateVersReport(self.modelXbrl).validate(self.modelXbrl)
            except Exception as err:
                self.modelXbrl.error("exception:" + type(err).__name__,
                    _("Versioning report exception: %(error)s, testcase: %(reportFile)s"),
                    modelXbrl=self.modelXbrl,
                    reportFile=self.modelXbrl.modelDocument.basename, error=err,
                    #traceback=traceback.format_tb(sys.exc_info()[2]),
                    exc_info=True)
        elif self.modelXbrl.modelDocument.type == Type.RSSFEED:
            self.validateRssFeed()
        else:
            if self.modelXbrl.fileSource.isReportPackage or self.modelXbrl.modelManager.validateAllFilesAsReportPackages:
                rpValidator = ReportPackageValidator(self.modelXbrl.fileSource)
                for val in rpValidator.validate():
                    self.modelXbrl.log(level=val.level.name, codes=val.codes, msg=val.msg, modelXbrl=self.modelXbrl, **val.args)
            try:
                self.instValidator.validate(self.modelXbrl, self.modelXbrl.modelManager.formulaOptions.typedParameters(self.modelXbrl.prefixedNamespaces))
                self.instValidator.close()
            except Exception as err:
                self.modelXbrl.error("exception:" + type(err).__name__,
                    _("Instance validation exception: %(error)s, instance: %(instance)s"),
                    modelXbrl=self.modelXbrl,
                    instance=self.modelXbrl.modelDocument.basename, error=err,
                    # traceback=traceback.format_tb(sys.exc_info()[2]),
                    exc_info=(type(err) is not AssertionError))
        self.close()

    def validateRssFeed(self):
        self.modelXbrl.info("info", "RSS Feed", modelDocument=self.modelXbrl)
        from arelle.FileSource import openFileSource
        reloadCache = getattr(self.modelXbrl, "reloadCache", False)
        if self.modelXbrl.modelManager.formulaOptions.testcaseResultsCaptureWarnings:
            errorCaptureLevel = logging._checkLevel("WARNING")
        else:
            errorCaptureLevel = logging._checkLevel("INCONSISTENCY")# default is INCONSISTENCY
        for rssItem in self.modelXbrl.modelDocument.rssItems:
            if getattr(rssItem, "skipRssItem", False):
                self.modelXbrl.info("info", _("skipping RSS Item %(accessionNumber)s %(formType)s %(companyName)s %(period)s"),
                    modelObject=rssItem, accessionNumber=rssItem.accessionNumber, formType=rssItem.formType, companyName=rssItem.companyName, period=rssItem.period)
                continue
            self.modelXbrl.info("info", _("RSS Item %(accessionNumber)s %(formType)s %(companyName)s %(period)s"),
                modelObject=rssItem, accessionNumber=rssItem.accessionNumber, formType=rssItem.formType, companyName=rssItem.companyName, period=rssItem.period)
            modelXbrl = None
            try:
                rssItemUrl = rssItem.zippedUrl
                if self.useFileSource.isArchive and (isLegacyAbs(rssItemUrl) or not rssItemUrl.endswith(".zip")):
                    modelXbrl = ModelXbrl.load(self.modelXbrl.modelManager,
                                               openFileSource(rssItemUrl, self.modelXbrl.modelManager.cntlr, reloadCache=reloadCache),
                                               _("validating"), rssItem=rssItem)
                else: # need own file source, may need instance discovery
                    filesource = FileSource.openFileSource(rssItemUrl, self.modelXbrl.modelManager.cntlr)
                    if filesource and not filesource.selection and filesource.isArchive:
                        try:
                            entrypoints = filesourceEntrypointFiles(filesource)
                            if entrypoints:
                                # resolve an IXDS in entrypoints
                                for pluginXbrlMethod in pluginClassMethods("ModelTestcaseVariation.ArchiveIxds"):
                                    pluginXbrlMethod(self, filesource,entrypoints)
                                filesource.select(entrypoints[0].get("file", None) )
                        except Exception as err:
                            self.modelXbrl.error("exception:" + type(err).__name__,
                                _("RSS item validation exception: %(error)s, entry URL: %(instance)s"),
                                modelXbrl=self.modelXbrl, instance=rssItemUrl, error=err)
                            continue # don't try to load this entry URL
                    modelXbrl = ModelXbrl.load(self.modelXbrl.modelManager, filesource, _("validating"), rssItem=rssItem, errorCaptureLevel=errorCaptureLevel)
                for pluginXbrlMethod in pluginClassMethods("RssItem.Xbrl.Loaded"):
                    pluginXbrlMethod(modelXbrl, {}, rssItem)
                if getattr(rssItem, "doNotProcessRSSitem", False) or modelXbrl.modelDocument is None:
                    modelXbrl.close()
                    continue # skip entry based on processing criteria
                self.instValidator.validate(modelXbrl, self.modelXbrl.modelManager.formulaOptions.typedParameters(self.modelXbrl.prefixedNamespaces))
                self.instValidator.close()
                rssItem.setResults(modelXbrl)
                self.modelXbrl.modelManager.viewModelObject(self.modelXbrl, rssItem.objectId())
                for pluginXbrlMethod in pluginClassMethods("Validate.RssItem"):
                    pluginXbrlMethod(self, modelXbrl, rssItem)
                modelXbrl.close()
            except Exception as err:
                self.modelXbrl.error("exception:" + type(err).__name__,
                    _("RSS item validation exception: %(error)s, instance: %(instance)s"),
                    modelXbrl=(self.modelXbrl, modelXbrl),
                    instance=rssItem.zippedUrl, error=err,
                    exc_info=True)
                try:
                    self.instValidator.close()
                    if modelXbrl is not None:
                        modelXbrl.close()
                except Exception as err:
                    pass
            del modelXbrl  # completely dereference

    def validateTestcase(self, testcase):
        self.modelXbrl.info("info", "Testcase", modelDocument=testcase)
        self.modelXbrl.viewModelObject(testcase.objectId())
        if testcase.type in (Type.TESTCASESINDEX, Type.REGISTRY):
            for doc in sorted(testcase.referencesDocument.keys(), key=lambda doc: doc.uri):
                self.validateTestcase(doc)  # testcases doc's are sorted by their uri (file names), e.g., for formula
        elif hasattr(testcase, "testcaseVariations"):
            testcaseVariations = []
            for testcaseVariation in testcaseVariationsByTarget(testcase.testcaseVariations):
                if self.filterTestcaseVariation(testcaseVariation):
                    testcaseVariations.append(testcaseVariation)
                else:
                    testcaseVariation.status = 'skip'
                    self.modelXbrl.info("info", "Skipped testcase variation %(variationId)s.",
                                        modelObject=testcaseVariation,
                                        variationId=testcaseVariation.id)
            for modelTestcaseVariation in testcaseVariations:
                self._validateTestcaseVariation(testcase, modelTestcaseVariation)

            _statusCounts = OrderedDict((("pass",0),("fail",0)))
            for tv in getattr(testcase, "testcaseVariations", ()):
                _statusCounts[tv.status] = _statusCounts.get(tv.status, 0) + 1
            self.modelXbrl.info("arelle:testCaseResults", ", ".join("{}={}".format(k,c) for k, c in _statusCounts.items() if k))

            self.modelXbrl.modelManager.showStatus(_("ready"), 2000)

    def _validateTestcaseVariation(self, testcase, modelTestcaseVariation):
        # update ui thread via modelManager (running in background here)
        startTime = time.perf_counter()
        self.modelXbrl.modelManager.viewModelObject(self.modelXbrl, modelTestcaseVariation.objectId())
        # is this a versioning report?
        resultIsVersioningReport = modelTestcaseVariation.resultIsVersioningReport
        resultIsXbrlInstance = modelTestcaseVariation.resultIsXbrlInstance
        resultIsTaxonomyPackage = modelTestcaseVariation.resultIsTaxonomyPackage
        inputDTSes = defaultdict(list)
        baseForElement = testcase.baseForElement(modelTestcaseVariation)
        # try to load instance document
        self.modelXbrl.info("info", _("Variation %(id)s%(name)s%(target)s: %(expected)s - %(description)s"),
                            modelObject=modelTestcaseVariation,
                            id=modelTestcaseVariation.id,
                            name=(" {}".format(modelTestcaseVariation.name) if modelTestcaseVariation.name else ""),
                            target=(" target {}".format(modelTestcaseVariation.ixdsTarget) if modelTestcaseVariation.ixdsTarget else ""),
                            expected=modelTestcaseVariation.expected,
                            description=modelTestcaseVariation.description)
        if self.modelXbrl.modelManager.formulaOptions.testcaseResultsCaptureWarnings:
            errorCaptureLevel = logging._checkLevel("WARNING")
        else:
            errorCaptureLevel = modelTestcaseVariation.severityLevel # default is INCONSISTENCY
        parameters = modelTestcaseVariation.parameters.copy()
        loadedModels = []
        for i, readMeFirstUri in enumerate(modelTestcaseVariation.readMeFirstUris):
            loadedModels.extend(self._testcaseLoadReadMeFirstUri(
                testcase=testcase,
                modelTestcaseVariation=modelTestcaseVariation,
                index=i,
                readMeFirstUri=readMeFirstUri,
                resultIsVersioningReport=resultIsVersioningReport,
                resultIsTaxonomyPackage=resultIsTaxonomyPackage,
                inputDTSes=inputDTSes,
                errorCaptureLevel=errorCaptureLevel,
                baseForElement=baseForElement,
                parameters=parameters,
            ))
        validateInputDTS = False
        for modelXbrl in loadedModels:
            if resultIsVersioningReport and modelXbrl.modelDocument:
                versReportFile = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(
                    modelTestcaseVariation.versioningReportUri, baseForElement)
                if os.path.exists(versReportFile): #validate existing
                    modelVersReport = ModelXbrl.load(self.modelXbrl.modelManager, versReportFile, _("validating existing version report"))
                    if modelVersReport and modelVersReport.modelDocument and modelVersReport.modelDocument.type == Type.VERSIONINGREPORT:
                        ValidateVersReport.ValidateVersReport(self.modelXbrl).validate(modelVersReport)
                        self.determineTestStatus(modelTestcaseVariation, modelVersReport.errors)
                        modelVersReport.close()
                elif len(inputDTSes) == 2:
                    ModelVersReport.ModelVersReport(self.modelXbrl).diffDTSes(
                            versReportFile, inputDTSes["from"], inputDTSes["to"])
                    modelTestcaseVariation.status = "generated"
                else:
                    modelXbrl.error("arelle:notLoaded",
                            _("Variation %(id)s %(name)s input DTSes not loaded, unable to generate versioning report: %(file)s"),
                            modelXbrl=testcase, id=modelTestcaseVariation.id, name=modelTestcaseVariation.name, file=os.path.basename(readMeFirstUri))
                    modelTestcaseVariation.status = "failed"
            elif resultIsTaxonomyPackage:
                self.determineTestStatus(modelTestcaseVariation, modelXbrl.errors)
                modelXbrl.close()
            elif inputDTSes:
                validateInputDTS = True
        if validateInputDTS:
            self._testcaseValidateInputDTS(testcase, modelTestcaseVariation, errorCaptureLevel, parameters, inputDTSes, baseForElement, resultIsXbrlInstance)
        # update ui thread via modelManager (running in background here)
        self.modelXbrl.modelManager.viewModelObject(self.modelXbrl, modelTestcaseVariation.objectId())
        self.modelXbrl.modelManager.cntlr.testcaseVariationReset()
        modelTestcaseVariation.duration = time.perf_counter() - startTime

    def _testcaseLoadReadMeFirstUri(self, testcase, modelTestcaseVariation, index, readMeFirstUri, resultIsVersioningReport, resultIsTaxonomyPackage, inputDTSes, errorCaptureLevel, baseForElement, parameters):
        preLoadingErrors = [] # accumulate pre-loading errors, such as during taxonomy package loading
        loadedModels = []
        filesource = None
        readMeFirstElements = modelTestcaseVariation.readMeFirstElements
        expectTaxonomyPackage = (index < len(readMeFirstElements) and
                                    readMeFirstElements[index] is not None and
                                    readMeFirstElements[index].qname.localName == "taxonomyPackage")
        if isinstance(readMeFirstUri,tuple):
            # dtsName is for formula instances, but is from/to dts if versioning
            dtsName, readMeFirstUri = readMeFirstUri
        elif resultIsVersioningReport:
            if inputDTSes: dtsName = "to"
            else: dtsName = "from"
        else:
            dtsName = None
        if resultIsVersioningReport and dtsName: # build multi-schemaRef containing document
            if dtsName in inputDTSes:
                dtsName = inputDTSes[dtsName]
            else:
                modelXbrl = ModelXbrl.create(self.modelXbrl.modelManager,
                                Type.DTSENTRIES,
                                self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(readMeFirstUri[:-4] + ".dts", baseForElement),
                                isEntry=True,
                                errorCaptureLevel=errorCaptureLevel)
                loadedModels.append(modelXbrl)
            DTSdoc = modelXbrl.modelDocument
            DTSdoc.inDTS = True
            doc = modelDocumentLoad(modelXbrl, readMeFirstUri, base=baseForElement)
            if doc is not None:
                DTSdoc.referencesDocument[doc] = ModelDocumentReference("import", DTSdoc.xmlRootElement)  #fake import
                doc.inDTS = True
        elif resultIsTaxonomyPackage:
            from arelle import PackageManager, PrototypeInstanceObject
            dtsName = readMeFirstUri
            modelXbrl = PrototypeInstanceObject.XbrlPrototype(self.modelXbrl.modelManager, readMeFirstUri)
            loadedModels.append(modelXbrl)
            PackageManager.packageInfo(self.modelXbrl.modelManager.cntlr, readMeFirstUri, reload=True, errors=modelXbrl.errors)
        else: # not a multi-schemaRef versioning report
            readMeFirstUriIsArchive = isReportPackageExtension(readMeFirstUri)
            readMeFirstUriIsEmbeddedZipFile = False
            if self.useFileSource.isArchive and not isLegacyAbs(readMeFirstUri):
                if readMeFirstUriIsArchive:
                    readMeFirstUriIsEmbeddedZipFile = True
                else:
                    normalizedReadMeFirstUri = self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(readMeFirstUri, baseForElement)
                    archivePath = FileSource.archiveFilenameParts(normalizedReadMeFirstUri)
                    if archivePath:
                        with self.useFileSource.fs.open(archivePath[1]) as embeddedFile:
                            readMeFirstUriIsArchive = readMeFirstUriIsEmbeddedZipFile = zipfile.is_zipfile(embeddedFile)
            if not readMeFirstUriIsArchive:
                modelXbrl = ModelXbrl.load(self.modelXbrl.modelManager,
                                            readMeFirstUri,
                                            _("validating"),
                                            base=baseForElement,
                                            useFileSource=self.useFileSource,
                                            errorCaptureLevel=errorCaptureLevel,
                                            ixdsTarget=modelTestcaseVariation.ixdsTarget)
                loadedModels.append(modelXbrl)
            else: # need own file source, may need instance discovery
                sourceFileSource = None
                newSourceFileSource = False
                if (
                    self.useFileSource
                    and not isLegacyAbs(readMeFirstUri)
                    and (readMeFirstUriIsEmbeddedZipFile or isReportPackageExtension(readMeFirstUri))
                ):
                    if self.useFileSource.isArchive:
                        sourceFileSource = self.useFileSource
                    elif expectTaxonomyPackage:
                        archiveFilenameParts = FileSource.archiveFilenameParts(baseForElement)
                        if archiveFilenameParts is not None:
                            sourceFileSource = FileSource.openFileSource(archiveFilenameParts[0], self.modelXbrl.modelManager.cntlr)
                            newSourceFileSource = True

                filesource = FileSource.openFileSource(readMeFirstUri, self.modelXbrl.modelManager.cntlr, base=baseForElement,
                                                        sourceFileSource=sourceFileSource)
                if filesource.isReportPackage:
                    expectTaxonomyPackage = filesource.isTaxonomyPackage

                if newSourceFileSource:
                    sourceFileSource.close()
                _rptPkgIxdsOptions = {}
                for pluginXbrlMethod in pluginClassMethods("ModelTestcaseVariation.ReportPackageIxdsOptions"):
                    pluginXbrlMethod(self, _rptPkgIxdsOptions)
                reportPackageErrors = False
                if (filesource.isReportPackage or self.modelXbrl.modelManager.validateAllFilesAsReportPackages) and not _rptPkgIxdsOptions:
                    rpValidator = ReportPackageValidator(filesource)
                    for val in rpValidator.validate():
                        reportPackageErrors = True
                        preLoadingErrors.append(val.codes)
                if filesource and not filesource.selection and filesource.isArchive:
                    try:
                        if filesource.isTaxonomyPackage or expectTaxonomyPackage:
                            filesource.loadTaxonomyPackageMappings(errors=preLoadingErrors, expectTaxonomyPackage=expectTaxonomyPackage)
                            filesource.select(None) # must select loadable reports (not the taxonomy package itself)
                        elif not filesource.isReportPackage:
                            entrypoints = filesourceEntrypointFiles(filesource)
                            for pluginXbrlMethod in pluginClassMethods("Validate.FileSource"):
                                pluginXbrlMethod(self.modelXbrl.modelManager.cntlr, filesource, entrypoints)
                            if entrypoints:
                                # resolve an IXDS in entrypoints
                                for pluginXbrlMethod in pluginClassMethods("ModelTestcaseVariation.ArchiveIxds"):
                                    pluginXbrlMethod(self, filesource,entrypoints)
                                for entrypoint in entrypoints:
                                    filesource.select(entrypoint.get("file", None))
                                    modelXbrl = ModelXbrl.load(self.modelXbrl.modelManager,
                                                               filesource,
                                                               _("validating"),
                                                               base=filesource.basefile + "/",
                                                               errorCaptureLevel=errorCaptureLevel,
                                                               ixdsTarget=modelTestcaseVariation.ixdsTarget,
                                                               errors=preLoadingErrors)
                                    loadedModels.append(modelXbrl)
                    except Exception as err:
                        self.modelXbrl.error("exception:" + type(err).__name__,
                            _("Testcase variation validation exception: %(error)s, entry URL: %(instance)s"),
                            modelXbrl=self.modelXbrl, instance=readMeFirstUri, error=err)
                        return [] # don't try to load this entry URL
                if filesource and filesource.isReportPackage and not _rptPkgIxdsOptions:
                    if not reportPackageErrors:
                        assert isinstance(filesource.basefile, str)
                        if entrypoints := filesourceEntrypointFiles(filesource):
                            for pluginXbrlMethod in pluginClassMethods("Validate.FileSource"):
                                pluginXbrlMethod(self.modelXbrl.modelManager.cntlr, filesource, entrypoints)
                            for pluginXbrlMethod in pluginClassMethods("ModelTestcaseVariation.ArchiveIxds"):
                                pluginXbrlMethod(self, filesource, entrypoints)
                            for entrypoint in entrypoints:
                                filesource.select(entrypoint.get("file", None))
                                modelXbrl = ModelXbrl.load(self.modelXbrl.modelManager,
                                                            filesource,
                                                            _("validating"),
                                                            base=filesource.basefile + "/",
                                                            errorCaptureLevel=errorCaptureLevel,
                                                            ixdsTarget=modelTestcaseVariation.ixdsTarget,
                                                            errors=preLoadingErrors)
                                loadedModels.append(modelXbrl)
                else:
                    if _rptPkgIxdsOptions and filesource.isTaxonomyPackage:
                        # Legacy ESEF conformance suite logic.
                        for pluginXbrlMethod in pluginClassMethods("ModelTestcaseVariation.ReportPackageIxds"):
                                filesource.select(pluginXbrlMethod(filesource, **_rptPkgIxdsOptions))
                    if len(loadedModels) == 0:
                        modelXbrl = ModelXbrl.load(self.modelXbrl.modelManager,
                                                    filesource,
                                                    _("validating"),
                                                    base=baseForElement,
                                                    errorCaptureLevel=errorCaptureLevel,
                                                    ixdsTarget=modelTestcaseVariation.ixdsTarget,
                                                    isLoadable=modelTestcaseVariation.variationDiscoversDTS or filesource.url,
                                                    errors=preLoadingErrors)
                        loadedModels.append(modelXbrl)

        for model in loadedModels:
            modelXbrl.isTestcaseVariation = True
            if model.modelDocument is None:
                if modelTestcaseVariation.expected not in ("EFM.6.03.04", "EFM.6.03.05"):
                    level = "ERROR" if modelTestcaseVariation.variationDiscoversDTS else "INFO"
                    model.log(
                        level,
                        "arelle:notLoaded",
                        _("Variation %(id)s %(name)s readMeFirst document not loaded: %(file)s"),
                        modelXbrl=testcase,
                        id=modelTestcaseVariation.id,
                        name=modelTestcaseVariation.name,
                        file=os.path.basename(readMeFirstUri),
                    )
            elif resultIsVersioningReport or resultIsTaxonomyPackage:
                inputDTSes['dtsName'].append(model)
            elif model.modelDocument.type == Type.VERSIONINGREPORT:
                ValidateVersReport.ValidateVersReport(self.modelXbrl).validate(model)
            elif testcase.type == Type.REGISTRYTESTCASE:
                self.instValidator.validate(model)  # required to set up dimensions, etc
                self.instValidator.executeCallTest(model, modelTestcaseVariation.id,
                            modelTestcaseVariation.cfcnCall, modelTestcaseVariation.cfcnTest)
                self.instValidator.close()
            else:
                inputDTSes[dtsName].append(model)
                # validate except for formulas
                _hasFormulae = model.hasFormulae
                model.hasFormulae = False
                try:
                    for pluginXbrlMethod in pluginClassMethods("TestcaseVariation.Xbrl.Loaded"):
                        pluginXbrlMethod(self.modelXbrl, model, modelTestcaseVariation)
                    self.instValidator.validate(model, parameters)
                    for pluginXbrlMethod in pluginClassMethods("TestcaseVariation.Xbrl.Validated"):
                        pluginXbrlMethod(self.modelXbrl, model)
                    for pluginXbrlMethod in pluginClassMethods("Validate.Complete"):
                        pluginXbrlMethod(self.modelXbrl.modelManager.cntlr, filesource)
                except Exception as err:
                    model.error("exception:" + type(err).__name__,
                        _("Testcase variation validation exception: %(error)s, instance: %(instance)s"),
                        modelXbrl=model, instance=model.modelDocument.basename, error=err, exc_info=(type(err) is not AssertionError))
                model.hasFormulae = _hasFormulae
        errors = [error for model in loadedModels for error in model.errors]
        for err in preLoadingErrors:
            if err not in errors:
                # include errors from models which failed to load.
                errors.append(err)
        reportModelCount = len([
            model for model in loadedModels
            if model.modelDocument is not None and (model.fileSource.isReportPackage or not model.fileSource.isTaxonomyPackage)
        ])
        self.determineTestStatus(modelTestcaseVariation, errors, validateModelCount=reportModelCount)
        if not inputDTSes:
            for model in loadedModels:
                model.close()
        return loadedModels

    def _testcaseValidateInputDTS(self, testcase, modelTestcaseVariation, errorCaptureLevel, parameters, inputDTSes, baseForElement, resultIsXbrlInstance):
        # validate schema, linkbase, or instance
        formulaOutputInstance = None
        modelXbrl = inputDTSes[None][0]
        expectedDataFiles = set()
        expectedTaxonomyPackages = []
        for localName, d in modelTestcaseVariation.dataUris.items():
            for uri in d:
                if not UrlUtil.isAbsolute(uri):
                    normalizedUri = self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(uri, baseForElement)
                    if localName == "taxonomyPackage":
                        expectedTaxonomyPackages.append(normalizedUri)
                    else:
                        expectedDataFiles.add(normalizedUri)
        expectedTaxonomyPackages.sort()
        foundDataFiles = set()
        variationBase = os.path.dirname(baseForElement)
        for dtsName, inputDTS in inputDTSes.items():  # input instances are also parameters
            if dtsName: # named instance
                parameters[dtsName] = (None, inputDTS) #inputDTS is a list of modelXbrl's (instance DTSes)
            elif len(inputDTS) > 1: # standard-input-instance with multiple instance documents
                parameters[XbrlConst.qnStandardInputInstance] = (None, inputDTS) # allow error detection in validateFormula
            for _inputDTS in inputDTS:
                for docUrl, doc in _inputDTS.urlDocs.items():
                    if docUrl.startswith(variationBase) and not doc.type == Type.INLINEXBRLDOCUMENTSET:
                        if getattr(doc,"loadedFromXbrlFormula", False): # may have been sourced from xf file
                            if docUrl.replace("-formula.xml", ".xf") in expectedDataFiles:
                                docUrl = docUrl.replace("-formula.xml", ".xf")
                        foundDataFiles.add(docUrl)

        foundDataFilesInTaxonomyPackages = set()
        foundTaxonomyPackages = set()
        for f in foundDataFiles:
            if i := bisect.bisect(expectedTaxonomyPackages, f):
                package = expectedTaxonomyPackages[i-1]
                if f.startswith(package + "/"):
                    foundDataFilesInTaxonomyPackages.add(f)
                    foundTaxonomyPackages.add(package)

        expectedNotFound = expectedDataFiles.union(expectedTaxonomyPackages) - foundDataFiles - foundTaxonomyPackages
        if expectedNotFound:
            modelXbrl.info("arelle:testcaseDataNotUsed",
                _("Variation %(id)s %(name)s data files not used: %(missingDataFiles)s"),
                modelObject=modelTestcaseVariation, name=modelTestcaseVariation.name, id=modelTestcaseVariation.id,
                missingDataFiles=", ".join(sorted(os.path.basename(f) for f in expectedNotFound)))
        foundNotExpected = foundDataFiles - expectedDataFiles - foundDataFilesInTaxonomyPackages
        if foundNotExpected:
            modelXbrl.info("arelle:testcaseDataUnexpected",
                _("Variation %(id)s %(name)s files not in variation data: %(unexpectedDataFiles)s"),
                modelObject=modelTestcaseVariation, name=modelTestcaseVariation.name, id=modelTestcaseVariation.id,
                unexpectedDataFiles=", ".join(sorted(os.path.basename(f) for f in foundNotExpected)))
        if modelXbrl.hasTableRendering or modelTestcaseVariation.resultIsTable:
            try:
                RenderingEvaluator.init(modelXbrl)
            except Exception as err:
                modelXbrl.error("exception:" + type(err).__name__,
                    _("Testcase RenderingEvaluator.init exception: %(error)s, instance: %(instance)s"),
                    modelXbrl=modelXbrl, instance=modelXbrl.modelDocument.basename, error=err, exc_info=True)
        modelXbrlHasFormulae = modelXbrl.hasFormulae
        if modelXbrlHasFormulae and self.modelXbrl.modelManager.formulaOptions.formulaAction != "none":
            try:
                # validate only formulae
                self.instValidator.parameters = parameters
                ValidateFormula.validate(self.instValidator)
            except Exception as err:
                modelXbrl.error("exception:" + type(err).__name__,
                    _("Testcase formula variation validation exception: %(error)s, instance: %(instance)s"),
                    modelXbrl=modelXbrl, instance=modelXbrl.modelDocument.basename, error=err, exc_info=(type(err) is not AssertionError))
        if modelTestcaseVariation.resultIsInfoset and self.modelXbrl.modelManager.validateInfoset:
            for pluginXbrlMethod in pluginClassMethods("Validate.Infoset"):
                pluginXbrlMethod(modelXbrl, modelTestcaseVariation.resultInfosetUri)
            infoset = ModelXbrl.load(self.modelXbrl.modelManager,
                                        modelTestcaseVariation.resultInfosetUri,
                                        _("loading result infoset"),
                                        base=baseForElement,
                                        useFileSource=self.useFileSource,
                                        errorCaptureLevel=errorCaptureLevel)
            if infoset.modelDocument is None:
                modelXbrl.error("arelle:notLoaded",
                    _("Variation %(id)s %(name)s result infoset not loaded: %(file)s"),
                    modelXbrl=testcase, id=modelTestcaseVariation.id, name=modelTestcaseVariation.name,
                    file=os.path.basename(modelTestcaseVariation.resultXbrlInstance))
                modelTestcaseVariation.status = "result infoset not loadable"
            else:   # check infoset
                ValidateInfoset.validate(self.instValidator, modelXbrl, infoset)
            infoset.close()
        if modelXbrl.hasTableRendering or modelTestcaseVariation.resultIsTable: # and self.modelXbrl.modelManager.validateInfoset:
            # diff (or generate) table infoset
            resultTableUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(modelTestcaseVariation.resultTableUri, baseForElement)
            if not any(alternativeValidation(modelXbrl, resultTableUri)
                        for alternativeValidation in pluginClassMethods("Validate.TableInfoset")):
                try:
                    ViewFileRenderedLayout.viewRenderedLayout(modelXbrl, resultTableUri, diffToFile=True)  # false to save infoset files
                except Exception as err:
                    modelXbrl.error("exception:" + type(err).__name__,
                        _("Testcase table linkbase validation exception: %(error)s, instance: %(instance)s"),
                        modelXbrl=modelXbrl, instance=modelXbrl.modelDocument.basename, error=err, exc_info=True)
        self.instValidator.close()
        extraErrors = []
        for pluginXbrlMethod in pluginClassMethods("TestcaseVariation.Validated"):
            pluginXbrlMethod(self.modelXbrl, modelXbrl, extraErrors, inputDTSes)
        self.determineTestStatus(modelTestcaseVariation, [e for inputDTSlist in inputDTSes.values() for inputDTS in inputDTSlist for e in inputDTS.errors] + extraErrors) # include infoset errors in status
        if modelXbrl.formulaOutputInstance and self.noErrorCodes(modelTestcaseVariation.actual):
            # if an output instance is created, and no string error codes, ignoring dict of assertion results, validate it
            modelXbrl.formulaOutputInstance.hasFormulae = False #  block formulae on output instance (so assertion of input is not lost)
            self.instValidator.validate(modelXbrl.formulaOutputInstance, modelTestcaseVariation.parameters)
            self.determineTestStatus(modelTestcaseVariation, modelXbrl.formulaOutputInstance.errors)
            if self.noErrorCodes(modelTestcaseVariation.actual): # if still 'clean' pass it forward for comparison to expected result instance
                formulaOutputInstance = modelXbrl.formulaOutputInstance
                modelXbrl.formulaOutputInstance = None # prevent it from being closed now
            self.instValidator.close()
        compareIxResultInstance = (modelXbrl.modelDocument.type in (Type.INLINEXBRL, Type.INLINEXBRLDOCUMENTSET) and
                                    modelTestcaseVariation.resultXbrlInstanceUri is not None)
        if compareIxResultInstance:
            formulaOutputInstance = modelXbrl # compare modelXbrl to generated output instance
            errMsgPrefix = "ix"
        else: # delete input instances before formula output comparision
            for inputDTSlist in inputDTSes.values():
                for inputDTS in inputDTSlist:
                    inputDTS.close()
            del inputDTSes # dereference
            errMsgPrefix = "formula"
        if resultIsXbrlInstance and formulaOutputInstance and formulaOutputInstance.modelDocument:
            _matchExpectedResultIDs = not modelXbrlHasFormulae # formula restuls have inconsistent IDs
            expectedInstance = ModelXbrl.load(self.modelXbrl.modelManager,
                                        modelTestcaseVariation.resultXbrlInstanceUri,
                                        _("loading expected result XBRL instance"),
                                        base=baseForElement,
                                        useFileSource=self.useFileSource,
                                        errorCaptureLevel=errorCaptureLevel)
            if expectedInstance.modelDocument is None:
                self.modelXbrl.error("{}:expectedResultNotLoaded".format(errMsgPrefix),
                    _("Testcase \"%(name)s\" %(id)s expected result instance not loaded: %(file)s"),
                    modelXbrl=testcase, id=modelTestcaseVariation.id, name=modelTestcaseVariation.name,
                    file=os.path.basename(modelTestcaseVariation.resultXbrlInstanceUri),
                    messageCodes=("formula:expectedResultNotLoaded","ix:expectedResultNotLoaded"))
                modelTestcaseVariation.status = "result not loadable"
            else:   # compare facts
                for pluginXbrlMethod in pluginClassMethods("TestcaseVariation.ExpectedInstance.Loaded"):
                    pluginXbrlMethod(expectedInstance, formulaOutputInstance)
                if len(expectedInstance.facts) != len(formulaOutputInstance.facts):
                    formulaOutputInstance.error("{}:resultFactCounts".format(errMsgPrefix),
                        _("Formula output %(countFacts)s facts, expected %(expectedFacts)s facts"),
                        modelXbrl=modelXbrl, countFacts=len(formulaOutputInstance.facts),
                        expectedFacts=len(expectedInstance.facts),
                        messageCodes=("formula:resultFactCounts","ix:resultFactCounts"))
                else:
                    formulaOutputFootnotesRelSet = ModelRelationshipSet(formulaOutputInstance, "XBRL-footnotes")
                    expectedFootnotesRelSet = ModelRelationshipSet(expectedInstance, "XBRL-footnotes")
                    def factFootnotes(fact, footnotesRelSet):
                        footnotes = {}
                        footnoteRels = footnotesRelSet.fromModelObject(fact)
                        if footnoteRels:
                            # most process rels in same order between two instances, use labels to sort
                            for i, footnoteRel in enumerate(sorted(footnoteRels,
                                                                    key=lambda r: (r.fromLabel,r.toLabel))):
                                modelObject = footnoteRel.toModelObject
                                if isinstance(modelObject, ModelResource):
                                    xml = collapseWhitespace(modelObject.viewText().strip())
                                    footnotes["Footnote {}".format(i+1)] = xml #re.sub(r'\s+', ' ', collapseWhitespace(modelObject.stringValue))
                                elif isinstance(modelObject, ModelFact):
                                    footnotes["Footnoted fact {}".format(i+1)] = \
                                        "{} context: {} value: {}".format(
                                        modelObject.qname,
                                        modelObject.contextID,
                                        collapseWhitespace(modelObject.value))
                        return footnotes
                    for expectedInstanceFact in expectedInstance.facts:
                        unmatchedFactsStack = []
                        formulaOutputFact = formulaOutputInstance.matchFact(expectedInstanceFact, unmatchedFactsStack, deemP0inf=True, matchId=_matchExpectedResultIDs, matchLang=False)
                        #formulaOutputFact = formulaOutputInstance.matchFact(expectedInstanceFact, unmatchedFactsStack, deemP0inf=True, matchId=True, matchLang=True)
                        if formulaOutputFact is None:
                            if unmatchedFactsStack: # get missing nested tuple fact, if possible
                                missingFact = unmatchedFactsStack[-1]
                            else:
                                missingFact = expectedInstanceFact
                            # is it possible to show value mismatches?
                            expectedFacts = formulaOutputInstance.factsByQname.get(missingFact.qname)
                            if expectedFacts and len(expectedFacts) == 1:
                                formulaOutputInstance.error("{}:expectedFactMissing".format(errMsgPrefix),
                                    _("Output missing expected fact %(fact)s, extracted value \"%(value1)s\", expected value  \"%(value2)s\""),
                                    modelXbrl=missingFact, fact=missingFact.qname, value1=missingFact.xValue, value2=next(iter(expectedFacts)).xValue,
                                    messageCodes=("formula:expectedFactMissing","ix:expectedFactMissing"))
                            else:
                                formulaOutputInstance.error("{}:expectedFactMissing".format(errMsgPrefix),
                                    _("Output missing expected fact %(fact)s"),
                                    modelXbrl=missingFact, fact=missingFact.qname,
                                    messageCodes=("formula:expectedFactMissing","ix:expectedFactMissing"))
                        else: # compare footnotes
                            expectedInstanceFactFootnotes = factFootnotes(expectedInstanceFact, expectedFootnotesRelSet)
                            formulaOutputFactFootnotes = factFootnotes(formulaOutputFact, formulaOutputFootnotesRelSet)
                            if (len(expectedInstanceFactFootnotes) != len(formulaOutputFactFootnotes) or
                                set(expectedInstanceFactFootnotes.values()) != set(formulaOutputFactFootnotes.values())):
                                formulaOutputInstance.error("{}:expectedFactFootnoteDifference".format(errMsgPrefix),
                                    _("Output expected fact %(fact)s expected footnotes %(footnotes1)s produced footnotes %(footnotes2)s"),
                                    modelXbrl=(formulaOutputFact,expectedInstanceFact), fact=expectedInstanceFact.qname, footnotes1=sorted(expectedInstanceFactFootnotes.items()), footnotes2=sorted(formulaOutputFactFootnotes.items()),
                                    messageCodes=("formula:expectedFactFootnoteDifference","ix:expectedFactFootnoteDifference"))

                # for debugging uncomment next line to save generated instance document
                # formulaOutputInstance.saveInstance(r"c:\temp\test-out-inst.xml")
            expectedInstance.close()
            del expectedInstance # dereference
            self.determineTestStatus(modelTestcaseVariation, formulaOutputInstance.errors)
            formulaOutputInstance.close()
            del formulaOutputInstance
        if compareIxResultInstance:
            for inputDTSlist in inputDTSes.values():
                for inputDTS in inputDTSlist:
                    inputDTS.close()
            del inputDTSes # dereference

    def noErrorCodes(self, modelTestcaseVariationActual):
        return not any(not isinstance(actual,dict) for actual in modelTestcaseVariationActual)

    def determineTestStatus(self, modelTestcaseVariation, errors, validateModelCount=None):
        testcaseResultOptions = self.modelXbrl.modelManager.formulaOptions.testcaseResultOptions
        testcaseExpectedErrors = self.modelXbrl.modelManager.formulaOptions.testcaseExpectedErrors or {}
        matchAllExpected = testcaseResultOptions == "match-all" or modelTestcaseVariation.match == 'all'
        expectedReportCount = modelTestcaseVariation.expectedReportCount
        expectedWarnings = modelTestcaseVariation.expectedWarnings if self.modelXbrl.modelManager.formulaOptions.testcaseResultsCaptureWarnings else []
        if expectedReportCount is not None and validateModelCount is not None and expectedReportCount != validateModelCount:
            errors.append("conf:testcaseExpectedReportCountError")
        _blockedMessageCodes = modelTestcaseVariation.blockedMessageCodes # restricts codes examined when provided
        if _blockedMessageCodes:
            _blockPattern = re.compile(_blockedMessageCodes)
            _errors = [e for e in errors if isinstance(e,str) and not _blockPattern.match(e)]
        else:
            _errors = errors
        _errors.extend(self.modelXbrl.modelManager.cntlr.errors)
        numErrors = sum(isinstance(e,(QName,str)) for e in _errors) # does not include asserton dict results
        hasAssertionResult = any(isinstance(e,dict) for e in _errors)
        expected = modelTestcaseVariation.expected
        expectedCount = modelTestcaseVariation.expectedCount
        indexPath = modelTestcaseVariation.document.filepath
        if self.useFileSource is not None and self.useFileSource.isZip:
            baseZipFile = self.useFileSource.basefile
            if indexPath.startswith(baseZipFile):
                indexPath = indexPath[len(baseZipFile) + 1:]
            indexPath = indexPath.replace("\\", "/")
        variationIdPath = f'{indexPath}:{modelTestcaseVariation.id}'
        userExpectedErrors = []
        for userPattern, userErrors in testcaseExpectedErrors.items():
            if fnmatch.fnmatch(variationIdPath, userPattern):
                userExpectedErrors.extend(userErrors)
        if userExpectedErrors:
            if expected is None:
                expected = []
            if isinstance(expected, str):
                assert expected in {"valid", "invalid"}, f"unhandled expected value string '{expected}'"
                expected = []
            expected.extend(userExpectedErrors)
            if expectedCount is not None:
                expectedCount += len(userExpectedErrors)
        if matchAllExpected:
            if isinstance(expected, list):
                if not expectedCount:
                    expectedCount = len(expected)
            elif expectedCount is None:
                expectedCount = 0
        if expected == "valid":
            status = "pass" if numErrors == 0 else "fail"
        elif expected == "invalid":
            status = "fail" if numErrors == 0 else "pass"
        elif expected in (None, []) and numErrors == 0 and not expectedWarnings:
            status = "pass"
        elif isinstance(expected, (QName, str, dict, list)) or expectedWarnings:
            status = "fail"
            _passCount = 0
            if isinstance(expected, list):
                _expectedList = expected.copy()
            elif not expected:
                _expectedList = []
            else:
                _expectedList = [expected]
            if expectedWarnings:
                _expectedList.extend(expectedWarnings)
                if expectedCount is not None:
                    expectedCount += len(expectedWarnings)
                else:
                    expectedCount = len(expectedWarnings)
            if not isinstance(expected, list):
                expected = [expected]
            for testErr in _errors:
                if isinstance(testErr, str) and testErr.startswith(("ESEF.", "NL.NL-KVK")): # compared as list of strings to QName localname
                    testErr = testErr.rpartition(".")[2]
                for _exp in _expectedList:
                    _expMatched = False
                    if isinstance(_exp,QName) and isinstance(testErr,str):
                        errPrefix, sep, errLocalName = testErr.rpartition(":")
                        if ((not sep and errLocalName in commaSpaceSplitPattern.split(_exp.localName.strip())) or # ESEF has comma separated list of localnames of errors
                            (_exp == qname(XbrlConst.errMsgPrefixNS.get(errPrefix) or
                                           (errPrefix == _exp.prefix and _exp.namespaceURI),
                                           errLocalName)) or
                            # XDT xml schema tests expected results
                            (_exp.namespaceURI == XbrlConst.xdtSchemaErrorNS and errPrefix == "xmlSchema")):
                            _expMatched = True
                    elif type(testErr) is type(_exp):
                        if isinstance(testErr,dict):
                            if len(testErr) == len(_exp) and all(
                                k in testErr and counts == testErr[k][:len(counts)]
                                for k, counts in _exp.items()):
                                _expMatched = True
                        elif (testErr == _exp or
                            (isinstance(_exp, str) and (
                             (_exp == "html:syntaxError" and testErr.startswith("lxml.SCHEMA")) or
                             (_exp == "EFM.6.03.04" and testErr.startswith("xmlSchema:")) or
                             (_exp == "EFM.6.03.05" and (testErr.startswith("xmlSchema:") or testErr == "EFM.5.02.01.01")) or
                             (_exp == "EFM.6.04.03" and (testErr.startswith("xmlSchema:") or testErr.startswith("utr:") or testErr.startswith("xbrl.") or testErr.startswith("xlink:"))) or
                             (_exp == "EFM.6.05.35" and testErr.startswith("utre:")) or
                             (_exp.startswith("EFM.") and testErr.startswith(_exp)) or
                             (_exp.startswith("EXG.") and testErr.startswith(_exp)) or
                             (_exp == "vere:invalidDTSIdentifier" and testErr.startswith("xbrl"))
                             ))):
                            _expMatched = True
                    if _expMatched:
                        _passCount += 1
                        if matchAllExpected:
                            _expectedList.remove(_exp)
                        break
            if _passCount > 0:
                if expectedCount is not None and (expectedCount != _passCount or
                                                  (matchAllExpected and expectedCount != numErrors)):
                    status = "fail"
                else:
                    status = "pass"
            #if expected == "EFM.6.03.02" or expected == "EFM.6.03.08": # 6.03.02 is not testable
            #    status = "pass"
            # check if expected is a whitespace separated list of error tokens
            if status == "fail" and isinstance(expected,str) and ' ' in expected:
                if all(any(testErr == e for testErr in _errors)
                       for e in expected.split()):
                        status = "pass"
            if not _errors and status == "fail":
                if modelTestcaseVariation.assertions:
                    priorAsserResults = modelTestcaseVariation.assertions
                    _expected = expected[0] if isinstance(expected, list) else expected
                    if len(priorAsserResults) == len(_expected) and all(
                            k in priorAsserResults and counts == priorAsserResults[k][:len(counts)]
                            for k, counts in _expected.items()):
                        status = "pass" # passing was previously successful and no further errors
                elif (isinstance(expected,dict) and # no assertions fired, are all the expected zero counts?
                      all(countSatisfied == 0 and countNotSatisfied == 0 for countSatisfied, countNotSatisfied in expected.values())):
                    status = "pass" # passes due to no counts expected

        else:
            status = "fail"
        modelTestcaseVariation.status = status
        _actual = {} # code and quantity
        if numErrors > 0 or hasAssertionResult: # either coded errors or assertions (in errors list)
            # put error codes first, sorted, then assertion result (dict's)
            for error in _errors:
                if isinstance(error,dict):  # asserion results
                    modelTestcaseVariation.assertions = error
                else:   # error code results
                    _actual[error] = _actual.get(error, 0) + 1
            modelTestcaseVariation.actual = [error if qty == 1 else "{} ({})".format(error,qty)
                                             for error, qty in sorted(_actual.items(), key=lambda i:i[0])]
            for error in _errors:
                if isinstance(error,dict):
                    modelTestcaseVariation.actual.append(error)

import logging
class ValidationLogListener(logging.Handler):
    def __init__(self, logView):
        self.logView = logView
        self.level = logging.DEBUG
    def flush(self):
        ''' Nothing to flush '''
    def emit(self, logRecord):
        # add to logView
        msg = self.format(logRecord)
        try:
            self.logView.append(msg)
        except:
            pass
