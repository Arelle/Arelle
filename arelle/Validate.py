'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, sys, traceback
from collections import defaultdict
from arelle import (ModelXbrl, ModelVersReport, XbrlConst, ModelDocument,
               ValidateXbrl, ValidateFiling, ValidateHmrc, ValidateVersReport, ValidateFormula)
from arelle.ModelValue import (qname, QName)

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
        # sort test cases by uri
        if self.modelXbrl.modelDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY):
            testcases = []
            for referencedDocument in self.modelXbrl.modelDocument.referencesDocument.keys():
                testcases.append((referencedDocument.uri, referencedDocument.objectId()))
            testcases.sort()
            for testcaseTuple in testcases:
                self.validateTestcase(self.modelXbrl.modelObject(testcaseTuple[1]))
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
                self.instValidator.validate(self.modelXbrl)
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
                        modelTestcaseVariation.status = "not loadable"
                        modelXbrl.close()
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
                        if dtsName:
                            parameters[dtsName] = (None, inputDTS)
                    self.instValidator.validate(modelXbrl, parameters)
                    self.determineTestStatus(modelTestcaseVariation, modelXbrl)
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
                    if resultIsXbrlInstance and formulaOutputInstance and formulaOutputInstance.modelDocument:
                        expectedInstance = ModelXbrl.load(self.modelXbrl.modelManager, 
                                                   modelTestcaseVariation.resultXbrlInstanceUri,
                                                   _("loading expected result XBRL instance"), 
                                                   base=baseForElement)
                        if expectedInstance.modelDocument is None:
                            self.modelXbrl.error("arelle:notLoaded",
                                _("Testcase %(id)s %(name)s expected result instance not loaded: %(file)s"),
                                modelXbrl=testcase, id=modelTestcaseVariation.id, name=modelTestcaseVariation.name, 
                                file=os.path.basename(modelTestcaseVariation.resultXbrlInstance))
                            modelTestcaseVariation.status = "result not loadable"
                            expectedInstance.close()
                        else:   # compare facts
                            if len(expectedInstance.facts) != len(formulaOutputInstance.facts):
                                formulaOutputInstance.error("formula:resultFactCounts",
                                    _("Formula output %(countFacts)s facts, expected %(expectedFacts)s facts"),
                                    modelXbrl=modelXbrl, countFacts=len(formulaOutputInstance.facts),
                                         expectedFacts=len(expectedInstance.facts))
                            else:
                                for fact in expectedInstance.facts:
                                    if formulaOutputInstance.matchFact(fact) is None:
                                        formulaOutputInstance.error("formula:expectedFactMissing",
                                            _("Formula output missing expected fact %(fact)s"),
                                            modelXbrl=modelXbrl, fact=fact)
                        self.determineTestStatus(modelTestcaseVariation, formulaOutputInstance)
                        formulaOutputInstance.close()
                        formulaOutputInstance = None
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
                        (expected == "EFM.6.04.03" and (testErr.startswith("xmlSchema:") or testErr.startswith("utr:") or testErr.startswith("xbrl.") or testErr.startswith("xlink:"))) or
                        (expected == "EFM.6.05.35" and testErr.startswith("utr:"))):
                        status = "pass"
                        break
            if (not modelUnderTest.errors and status == "fail" and 
                modelTestcaseVariation.assertions and modelTestcaseVariation.assertions == expected):
                status = "pass" # passing was previously successful and no further errors 
        else:
            status = "fail"
        modelTestcaseVariation.status = status
        if numErrors > 0:
            modelTestcaseVariation.actual = []
            # put error codes first, sorted, then assertion result (dict's)
            for error in modelUnderTest.errors:
                if isinstance(error,dict):  # assertoin results
                    modelTestcaseVariation.assertions = error
                else:   # error code results
                    modelTestcaseVariation.actual.append(error)
            modelTestcaseVariation.actual.sort()
            for error in modelUnderTest.errors:
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
