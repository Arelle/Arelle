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
                self.modelXbrl.error(
                    _("Testcase validation exception: {0}, testcase: {1}, at {2}").format(
                         err,
                         self.modelXbrl.modelDocument.basename,
                         traceback.format_tb(sys.exc_info()[2])), 
                    "err", "exception")
        elif self.modelXbrl.modelDocument.type == ModelDocument.Type.VERSIONINGREPORT:
            try:
                ValidateVersReport.ValidateVersReport(self.modelXbrl) \
                    .validate(self.modelXbrl)
            except Exception as err:
                self.modelXbrl.error(
                    _("Version report exception: {0}, testcase: {1}, at {2}").format(
                         err,
                         self.modelXbrl.modelDocument.basename,
                         traceback.format_tb(sys.exc_info()[2])), 
                    "err", "exception")
        elif self.modelXbrl.modelDocument.type != ModelDocument.Type.Unknown:
            try:
                self.instValidator.validate(self.modelXbrl)
            except Exception as err:
                self.modelXbrl.error(
                    _("Instance validation exception: {0}, instance: {1}, at {2}").format(
                         err, 
                         self.modelXbrl.modelDocument.basename if self.modelXbrl and self.modelXbrl.modelDocument else _("(not available)"),
                         traceback.format_tb(sys.exc_info()[2])), 
                    "err", "exception")

    def validateTestcase(self, testcase):
        self.modelXbrl.error(_("testcase {0}").format(os.path.basename(testcase.uri)))
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
                self.modelXbrl.error(_("variation {0} {1}: {2}").format(modelTestcaseVariation.id, modelTestcaseVariation.name, modelTestcaseVariation.expected))
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
                                         self.modelXbrl.cntlr.webCache.normalizeUrl(readMeFirstUri[:-4] + ".dts", baseForElement),
                                         isEntry=True)
                        DTSdoc = modelXbrl.modelDocument
                        DTSdoc.inDTS = True
                        doc = ModelDocument.load(modelXbrl, readMeFirstUri, base=baseForElement)
                        DTSdoc.referencesDocument[doc] = "import"  #fake import
                        doc.inDTS = True
                    else: # not a multi-schemaRef versioning report
                        modelXbrl = ModelXbrl.load(self.modelXbrl.modelManager, 
                                                   readMeFirstUri,
                                                   _("validating"), 
                                                   base=baseForElement)
                    if modelXbrl.modelDocument is None:
                        self.modelXbrl.error(_("Testcase {0} {1} document not loaded: {2}").format(
                            modelTestcaseVariation.id, modelTestcaseVariation.name, os.path.basename(readMeFirstUri)))
                        modelTestcaseVariation.status = "not loadable"
                        modelXbrl.close()
                    elif resultIsVersioningReport:
                        inputDTSes[dtsName] = modelXbrl
                    elif modelXbrl.modelDocument.type == ModelDocument.Type.VERSIONINGREPORT:
                        ValidateVersReport.ValidateVersReport(self.modelXbrl) \
                            .validate(modelXbrl)
                        self.determineTestStatus(modelTestcaseVariation, modelXbrl)
                        modelXbrl.close()
                    elif testcase.type == ModelDocument.Type.REGISTRYTESTCASE:
                        self.instValidator.validate(modelXbrl)  # required to set up dimensions, etc
                        self.instValidator.executeCallTest(modelXbrl, modelTestcaseVariation.id, 
                                   modelTestcaseVariation.cfcnCall, modelTestcaseVariation.cfcnTest)
                        self.determineTestStatus(modelTestcaseVariation, modelXbrl)
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
                        self.modelXbrl.error(_("Testcase {0} {1} DTSes not loaded, unable to generate versioning report").format(
                            modelTestcaseVariation.id, modelTestcaseVariation.name, os.path.basename(readMeFirstUri)))
                        modelTestcaseVariation.status = "failed"
                    for inputDTS in inputDTSes:
                        inputDTS.close()
                elif inputDTSes:
                    # validate schema, linkbase, or instance
                    modelXbrl = inputDTSes[None][0]
                    parameters = modelTestcaseVariation.parameters.copy()
                    for dtsName, inputDTS in inputDTSes.items():  # input instances are also parameters
                        if dtsName:
                            parameters[dtsName] = (None, inputDTS)
                    self.instValidator.validate(modelXbrl, parameters)
                    self.determineTestStatus(modelTestcaseVariation, modelXbrl)
                    if modelXbrl.formulaOutputInstance and len(modelTestcaseVariation.actual) == 0: 
                        # if an output instance is created, validate it
                        self.instValidator.validate(modelXbrl.formulaOutputInstance, modelTestcaseVariation.parameters)
                        self.determineTestStatus(modelTestcaseVariation, modelXbrl.formulaOutputInstance)
                        if len(modelTestcaseVariation.actual) == 0: # if still 'clean' pass it forward for comparison to expected result instance
                            formulaOutputInstance = modelXbrl.formulaOutputInstance
                            modelXbrl.formulaOutputInstance = None # prevent it from being closed now
                    for inputDTSlist in inputDTSes.values():
                        for inputDTS in inputDTSlist:
                            inputDTS.close()
                    if resultIsXbrlInstance and formulaOutputInstance and formulaOutputInstance.modelDocument:
                        expectedInstance = ModelXbrl.load(self.modelXbrl.modelManager, 
                                                   modelTestcaseVariation.resultXbrlInstanceUri,
                                                   _("loading expected result XBRL instance"), 
                                                   base=baseForElement)
                        if expectedInstance.modelDocument is None:
                            self.modelXbrl.error(_("Testcase {0} {1} expected result instance not loaded: {2}").format(
                                modelTestcaseVariation.id, modelTestcaseVariation.name, os.path.basename(modelTestcaseVariation.resultXbrlInstance)))
                            modelTestcaseVariation.status = "result not loadable"
                            expectedInstance.close()
                        else:   # compare facts
                            if len(expectedInstance.facts) != len(formulaOutputInstance.facts):
                                formulaOutputInstance.error(
                                    _("Formula output {0} facts, expected {1} facts").format(
                                         len(formulaOutputInstance.facts),
                                         len(expectedInstance.facts)), 
                                    "err", "formula:resultFactCounts")
                            else:
                                for fact in expectedInstance.facts:
                                    if formulaOutputInstance.matchFact(fact) is None:
                                        formulaOutputInstance.error(
                                            _("Formula output missing expected fact {0}").format(
                                                 fact), 
                                            "err", "formula:expectedFactMissing")
                        self.determineTestStatus(modelTestcaseVariation, formulaOutputInstance)
                        formulaOutputInstance.close()
                        formulaOutputInstance = None
                # update ui thread via modelManager (running in background here)
                self.modelXbrl.modelManager.viewModelObject(self.modelXbrl, modelTestcaseVariation.objectId())
                    
            self.modelXbrl.modelManager.showStatus(_("ready"), 2000)
            
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
                        (expected == qname(XbrlConst.errMsgPrefixNS.get(errPrefix), errLocalName))):
                        status = "pass"
                        break
                elif type(testErr) == type(expected) and testErr == expected:
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
                
                