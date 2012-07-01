'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, sys, traceback
from collections import defaultdict
from arelle import (ModelXbrl, ModelVersReport, XbrlConst, ModelDocument,
               ValidateXbrl, ValidateFiling, ValidateHmrc, ValidateVersReport, ValidateFormula,
               ValidateInfoset)
from arelle.ModelValue import (qname, QName)
from arelle.PluginManager import pluginClassMethods

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
            if modelXbrl.modelManager.disclosureSystem.HMRC:
                self.instValidator = ValidateHmrc.ValidateHmrc(modelXbrl)
            else:
                self.instValidator = ValidateFiling.ValidateFiling(modelXbrl)
            self.formulaValidator = ValidateXbrl.ValidateXbrl(modelXbrl)
        else:
            self.instValidator = ValidateXbrl.ValidateXbrl(modelXbrl)
            self.formulaValidator = self.instValidator
        if hasattr(modelXbrl,"fileSource"):
            self.useFileSource = modelXbrl.fileSource
        else:
            self.useFileSource = None
            
    def close(self):
        self.instValidator.close(reusable=False)
        self.formulaValidator.close(reusable=False)
        self.__dict__.clear()   # dereference variables
        
    def validate(self):
        if self.modelXbrl.modelDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY):
            for doc in sorted(self.modelXbrl.modelDocument.referencesDocument.keys(), key=lambda doc: doc.uri):
                self.validateTestcase(doc)  # testcases doc's are sorted by their uri (file names), e.g., for formula
        elif self.modelXbrl.modelDocument.type in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
            try:
                self.validateTestcase(self.modelXbrl.modelDocument)
            except Exception as err:
                self.modelXbrl.error("exception",
                    _("Testcase validation exception: %(error)s, testcase: %(testcase)s"),
                    modelXbrl=self.modelXbrl,
                    testcase=self.modelXbrl.modelDocument.basename, error=err,
                    #traceback=traceback.format_tb(sys.exc_info()[2]),
                    exc_info=True)
        elif self.modelXbrl.modelDocument.type == ModelDocument.Type.VERSIONINGREPORT:
            try:
                ValidateVersReport.ValidateVersReport(self.modelXbrl).validate(self.modelXbrl)
            except Exception as err:
                self.modelXbrl.error("exception",
                    _("Versioning report exception: %(error)s, testcase: %(reportFile)s"),
                    modelXbrl=self.modelXbrl,
                    reportFile=self.modelXbrl.modelDocument.basename, error=err,
                    #traceback=traceback.format_tb(sys.exc_info()[2]),
                    exc_info=True)
        else:
            try:
                self.instValidator.validate(self.modelXbrl, self.modelXbrl.modelManager.formulaOptions.typedParameters())
                self.instValidator.close()
            except Exception as err:
                self.modelXbrl.error("exception",
                    _("Instance validation exception: %(error)s, instance: %(instance)s"),
                    modelXbrl=self.modelXbrl,
                    instance=self.modelXbrl.modelDocument.basename, error=err,
                    # traceback=traceback.format_tb(sys.exc_info()[2]),
                    exc_info=True)
        self.close()

    def validateTestcase(self, testcase):
        self.modelXbrl.info("info", "Testcase", modelDocument=testcase)
        self.modelXbrl.viewModelObject(testcase.objectId())
        if hasattr(testcase, "testcaseVariations"):
            for modelTestcaseVariation in testcase.testcaseVariations:
                # update ui thread via modelManager (running in background here)
                self.modelXbrl.modelManager.viewModelObject(self.modelXbrl, modelTestcaseVariation.objectId())
                # is this a versioning report?
                resultIsVersioningReport = modelTestcaseVariation.resultIsVersioningReport
                resultIsXbrlInstance = modelTestcaseVariation.resultIsXbrlInstance
                formulaOutputInstance = None
                inputDTSes = defaultdict(list)
                baseForElement = testcase.baseForElement(modelTestcaseVariation)
                # try to load instance document
                self.modelXbrl.info("info", _("Variation %(id)s %(name)s: %(expected)s"),
                    modelObject=modelTestcaseVariation, id=modelTestcaseVariation.id, name=modelTestcaseVariation.name, expected=modelTestcaseVariation.expected)
                for readMeFirstUri in modelTestcaseVariation.readMeFirstUris:
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
                                         ModelDocument.Type.DTSENTRIES,
                                         self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(readMeFirstUri[:-4] + ".dts", baseForElement),
                                         isEntry=True)
                        DTSdoc = modelXbrl.modelDocument
                        DTSdoc.inDTS = True
                        doc = ModelDocument.load(modelXbrl, readMeFirstUri, base=baseForElement)
                        if doc is not None:
                            DTSdoc.referencesDocument[doc] = "import"  #fake import
                            doc.inDTS = True
                    else: # not a multi-schemaRef versioning report
                        modelXbrl = ModelXbrl.load(self.modelXbrl.modelManager, 
                                                   readMeFirstUri,
                                                   _("validating"), 
                                                   base=baseForElement,
                                                   useFileSource=self.useFileSource)
                    if modelXbrl.modelDocument is None:
                        self.modelXbrl.error("arelle:notLoaded",
                             _("Testcase %(id)s %(name)s document not loaded: %(file)s"),
                             modelXbrl=testcase, id=modelTestcaseVariation.id, name=modelTestcaseVariation.name, file=os.path.basename(readMeFirstUri))
                        modelXbrl.close()
                        self.determineNotLoadedTestStatus(modelTestcaseVariation)
                    elif resultIsVersioningReport:
                        inputDTSes[dtsName] = modelXbrl
                    elif modelXbrl.modelDocument.type == ModelDocument.Type.VERSIONINGREPORT:
                        ValidateVersReport.ValidateVersReport(self.modelXbrl).validate(modelXbrl)
                        self.determineTestStatus(modelTestcaseVariation, modelXbrl)
                        modelXbrl.close()
                    elif testcase.type == ModelDocument.Type.REGISTRYTESTCASE:
                        self.instValidator.validate(modelXbrl)  # required to set up dimensions, etc
                        self.instValidator.executeCallTest(modelXbrl, modelTestcaseVariation.id, 
                                   modelTestcaseVariation.cfcnCall, modelTestcaseVariation.cfcnTest)
                        self.determineTestStatus(modelTestcaseVariation, modelXbrl)
                        self.instValidator.close()
                        modelXbrl.close()
                    else:
                        inputDTSes[dtsName].append(modelXbrl)
                if resultIsVersioningReport and modelXbrl.modelDocument:
                    versReportFile = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(
                        modelTestcaseVariation.versioningReportUri, baseForElement)
                    if os.path.exists(versReportFile): #validate existing
                        modelVersReport = ModelXbrl.load(self.modelXbrl.modelManager, versReportFile, _("validating existing version report"))
                        if modelVersReport and modelVersReport.modelDocument and modelVersReport.modelDocument.type == ModelDocument.Type.VERSIONINGREPORT:
                            ValidateVersReport.ValidateVersReport(self.modelXbrl).validate(modelVersReport)
                            self.determineTestStatus(modelTestcaseVariation, modelVersReport)
                            modelVersReport.close()
                    elif len(inputDTSes) == 2:
                        ModelVersReport.ModelVersReport(self.modelXbrl).diffDTSes(
                              versReportFile, inputDTSes["from"], inputDTSes["to"])
                        modelTestcaseVariation.status = "generated"
                    else:
                        self.modelXbrl.error("arelle:notLoaded",
                             _("Testcase %(id)s %(name)s DTSes not loaded, unable to generate versioning report: %(file)s"),
                             modelXbrl=testcase, id=modelTestcaseVariation.id, name=modelTestcaseVariation.name, file=os.path.basename(readMeFirstUri))
                        modelTestcaseVariation.status = "failed"
                    for inputDTS in inputDTSes.values():
                        inputDTS.close()
                    del inputDTSes # dereference
                elif inputDTSes:
                    # validate schema, linkbase, or instance
                    modelXbrl = inputDTSes[None][0]
                    parameters = modelTestcaseVariation.parameters.copy()
                    for dtsName, inputDTS in inputDTSes.items():  # input instances are also parameters
                        if dtsName: # named instance
                            parameters[dtsName] = (None, inputDTS) #inputDTS is a list of modelXbrl's (instance DTSes)
                        elif len(inputDTS) > 1: # standard-input-instance with multiple instance documents
                            parameters[XbrlConst.qnStandardInputInstance] = (None, inputDTS) # allow error detection in validateFormula
                    self.instValidator.validate(modelXbrl, parameters)
                    if modelTestcaseVariation.resultIsInfoset and self.modelXbrl.modelManager.validateInfoset:
                        for pluginXbrlMethod in pluginClassMethods("Validate.Infoset"):
                            pluginXbrlMethod(modelXbrl, modelTestcaseVariation.resultInfosetUri)
                        infoset = ModelXbrl.load(self.modelXbrl.modelManager, 
                                                 modelTestcaseVariation.resultInfosetUri,
                                                   _("loading result infoset"), 
                                                   base=baseForElement,
                                                   useFileSource=self.useFileSource)
                        if infoset.modelDocument is None:
                            self.modelXbrl.error("arelle:notLoaded",
                                _("Testcase %(id)s %(name)s result infoset not loaded: %(file)s"),
                                modelXbrl=testcase, id=modelTestcaseVariation.id, name=modelTestcaseVariation.name, 
                                file=os.path.basename(modelTestcaseVariation.resultXbrlInstance))
                            modelTestcaseVariation.status = "result infoset not loadable"
                        else:   # check infoset
                            ValidateInfoset.validate(self.instValidator, modelXbrl, infoset)
                        infoset.close()
                    self.determineTestStatus(modelTestcaseVariation, modelXbrl) # include infoset errors in status
                    self.instValidator.close()
                    if modelXbrl.formulaOutputInstance and self.noErrorCodes(modelTestcaseVariation.actual): 
                        # if an output instance is created, and no string error codes, ignoring dict of assertion results, validate it
                        modelXbrl.formulaOutputInstance.hasFormulae = False #  block formulae on output instance (so assertion of input is not lost)
                        self.instValidator.validate(modelXbrl.formulaOutputInstance, modelTestcaseVariation.parameters)
                        self.determineTestStatus(modelTestcaseVariation, modelXbrl.formulaOutputInstance)
                        if self.noErrorCodes(modelTestcaseVariation.actual): # if still 'clean' pass it forward for comparison to expected result instance
                            formulaOutputInstance = modelXbrl.formulaOutputInstance
                            modelXbrl.formulaOutputInstance = None # prevent it from being closed now
                        self.instValidator.close()
                    for inputDTSlist in inputDTSes.values():
                        for inputDTS in inputDTSlist:
                            inputDTS.close()
                    del inputDTSes # dereference
                    if resultIsXbrlInstance and formulaOutputInstance and formulaOutputInstance.modelDocument:
                        expectedInstance = ModelXbrl.load(self.modelXbrl.modelManager, 
                                                   modelTestcaseVariation.resultXbrlInstanceUri,
                                                   _("loading expected result XBRL instance"), 
                                                   base=baseForElement,
                                                   useFileSource=self.useFileSource)
                        if expectedInstance.modelDocument is None:
                            self.modelXbrl.error("arelle:notLoaded",
                                _("Testcase %(id)s %(name)s expected result instance not loaded: %(file)s"),
                                modelXbrl=testcase, id=modelTestcaseVariation.id, name=modelTestcaseVariation.name, 
                                file=os.path.basename(modelTestcaseVariation.resultXbrlInstance))
                            modelTestcaseVariation.status = "result not loadable"
                        else:   # compare facts
                            if len(expectedInstance.facts) != len(formulaOutputInstance.facts):
                                formulaOutputInstance.error("formula:resultFactCounts",
                                    _("Formula output %(countFacts)s facts, expected %(expectedFacts)s facts"),
                                    modelXbrl=modelXbrl, countFacts=len(formulaOutputInstance.facts),
                                         expectedFacts=len(expectedInstance.facts))
                            else:
                                for fact in expectedInstance.facts:
                                    unmatchedFactsStack = []
                                    if formulaOutputInstance.matchFact(fact, unmatchedFactsStack) is None:
                                        if unmatchedFactsStack: # get missing nested tuple fact, if possible
                                            missingFact = unmatchedFactsStack[-1]
                                        else:
                                            missingFact = fact
                                        formulaOutputInstance.error("formula:expectedFactMissing",
                                            _("Formula output missing expected fact %(fact)s"),
                                            modelXbrl=missingFact, fact=missingFact.qname)
                            # for debugging uncomment next line to save generated instance document
                            # formulaOutputInstance.saveInstance(r"c:\temp\test-out-inst.xml")
                        expectedInstance.close()
                        del expectedInstance # dereference
                        self.determineTestStatus(modelTestcaseVariation, formulaOutputInstance)
                        formulaOutputInstance.close()
                        del formulaOutputInstance
                # update ui thread via modelManager (running in background here)
                self.modelXbrl.modelManager.viewModelObject(self.modelXbrl, modelTestcaseVariation.objectId())
                    
            self.modelXbrl.modelManager.showStatus(_("ready"), 2000)
            
    def noErrorCodes(self, modelTestcaseVariation):
        return not any(not isinstance(actual,dict) for actual in modelTestcaseVariation)
                
    def determineTestStatus(self, modelTestcaseVariation, modelUnderTest):
        numErrors = len(modelUnderTest.errors)
        expected = modelTestcaseVariation.expected
        if expected == "valid":
            if numErrors == 0:
                status = "pass"
            else:
                status = "fail"
        elif expected == "invalid":
            if numErrors == 0:
                status = "fail"
            else:
                status = "pass"
        elif expected is None and numErrors == 0:
            status = "pass"
        elif isinstance(expected,(QName,str,dict)): # string or assertion id counts dict
            status = "fail"
            for testErr in modelUnderTest.errors:
                if isinstance(expected,QName) and isinstance(testErr,str):
                    errPrefix, sep, errLocalName = testErr.partition(":")
                    if ((not sep and errPrefix == expected.localName) or
                        (expected == qname(XbrlConst.errMsgPrefixNS.get(errPrefix), errLocalName)) or
                        # XDT xml schema tests expected results 
                        (expected.namespaceURI == XbrlConst.xdtSchemaErrorNS and errPrefix == "xmlSchema")):
                        status = "pass"
                        break
                elif type(testErr) == type(expected):
                    if (testErr == expected or
                        (isinstance(expected, _STR_BASE) and (
                         (expected == "EFM.6.03.04" and testErr.startswith("xmlSchema:")) or
                         (expected == "EFM.6.03.05" and (testErr.startswith("xmlSchema:") or testErr == "EFM.5.2.1.1")) or
                         (expected == "EFM.6.04.03" and (testErr.startswith("xmlSchema:") or testErr.startswith("utr:") or testErr.startswith("xbrl.") or testErr.startswith("xlink:"))) or
                         (expected == "EFM.6.05.35" and testErr.startswith("utr:")) or
                         (expected.startswith("EFM.") and testErr.startswith(expected))))):
                        status = "pass"
                        break
            if expected == "EFM.6.03.02" or expected == "EFM.6.03.08": # 6.03.02 is not testable
                status = "pass"
            if not modelUnderTest.errors and status == "fail":
                if modelTestcaseVariation.assertions:
                    if modelTestcaseVariation.assertions == expected:
                        status = "pass" # passing was previously successful and no further errors
                elif (isinstance(expected,dict) and # no assertions fired, are all the expected zero counts?
                      all(countSatisfied == 0 and countNotSatisfied == 0 for countSatisfied, countNotSatisfied in expected.values())):
                    status = "pass" # passes due to no counts expected
                         
        else:
            status = "fail"
        modelTestcaseVariation.status = status
        if numErrors > 0:
            modelTestcaseVariation.actual = []
            # put error codes first, sorted, then assertion result (dict's)
            for error in modelUnderTest.errors:
                if isinstance(error,dict):  # asserion results
                    modelTestcaseVariation.assertions = error
                else:   # error code results
                    modelTestcaseVariation.actual.append(error)
            modelTestcaseVariation.actual.sort(key=lambda d: str(d))
            for error in modelUnderTest.errors:
                if isinstance(error,dict):
                    modelTestcaseVariation.actual.append(error)
                
    def determineNotLoadedTestStatus(self, modelTestcaseVariation):
        expected = modelTestcaseVariation.expected
        status = "not loadable"
        if expected in ("EFM.6.03.04", "EFM.6.03.05"):
            status = "pass"
        modelTestcaseVariation.status = status
                
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
