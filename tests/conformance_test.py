import sys
import os, os.path
import gettext
from functools import partial

from arelle import Cntlr, FileSource, ModelDocument
from arelle.Locale import format_string
from arelle.ModelFormulaObject import FormulaOptions

gettext.install("arelle")

# runEFMTests.bat                        - Done
# runFormulaTests.bat                    - Done
# runXBRL21Tests.bat                     - Done
# runXDTTests.bat                        - Done
# runUTRTests.bat                        - In possesion, but not implemented
# runFunctionTests.bat
# runUS-GFMTests.bat
# runGenerateVersioningTestcases.bat
# runVersioningConsumptionTests.bat
#
# Function arelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --validate --csvTestReport "%OUTPUTCSVFILE%" --logFile "%OUTPUTLOGFILE%"
# UTR      arelle.CntlrCmdLine --file  %CONFROOT%\%FILENAME% --validate --csvTestReport "%OUTPUTCSVFILE%" --logFile "%OUTPUTLOGFILE%" --utr 

verbose = True
tests = {
         'xbrl' :  {    # XBRL 2.1
                    'url'  : 'http://www.xbrl.org/2008/XBRL-CONF-CR4-2008-07-02.zip',
                    'args' : ["xbrl.xml", "xbrl.csv", "xbrl.log", False, False, False]
                    }, 
         
         'formula' : {  # Formula
                      'url'  : 'http://www.xbrl.org/Specification/formula/REC-2009-06-22/conformance/Formula-CONF-REC-PER-Errata-2011-03-16.zip',
                      'args' : [ "index.xml", "formula.csv", "formula.log", False, False, False],
                      },
         'xdt' : {      # XDT
                  'url'  : "http://www.xbrl.org/2009/XDT-CONF-CR4-2009-10-06.zip",
                  'args' : [ "xdt.xml", "xdt.csv", "xdt.log", False, False, False ]
                  }, 
         'edgar' : {    # Edgar
                    'url'  : 'http://www.sec.gov/info/edgar/ednews/efmtest/16-110225.zip',
                    'args' : [ "testcases.xml", "edgar.csv", "edgar.log", True, False, False]
                    }
         }

def check_variation(index, test, variation):
    assert variation.status == "pass"
    
class Tester(Cntlr.Cntlr):
    def run(self, testfn, csvfn, logfn, efm, utr, dec):
        self.messages = []
        self.filename = testfn
        filesource = FileSource.FileSource(self.filename, self)
        
        if efm:
            self.modelManager.validateDisclosureSystem = True
            self.modelManager.disclosureSystem.select("efm")
        else:
            self.modelManager.disclosureSystem.select(None)
        if utr:
            self.modelManager.validateUtr = True
        if dec:
            self.modelManager.validateInferDecimals = True
            self.modelManager.validateCalcLB = True
            
        self.modelManager.formulaOptions = FormulaOptions()

        modelXbrl = self.modelManager.load(filesource, gettext.gettext("validating"))

        self.modelManager.validate()

        modelDocument = modelXbrl.modelDocument

        self.outcomes = list()
        if modelDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY):
            index = os.path.basename(modelDocument.uri)
            for tci in modelDocument.referencesDocument.keys():
                tc = modelXbrl.modelObject(tci.objectId())
                test_case = os.path.basename(tc.uri)
                if hasattr(tc, "testcaseVariations"):
                    for mv in tc.testcaseVariations:
                        self.outcomes.append((index, test_case, mv))
        elif modelDocument.type in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
            tc = modelDocument
            test_case = os.path.basename(tc.uri)
            if hasattr(tc, "testcaseVariations"):
                for mv in tc.testcaseVariations:
                    self.outcomes.append((None, test_case, mv))

        for msg in self.messages:
            print(msg.rstrip())

        return self.outcomes
    
    def addToLog(self, message):
        self.messages.append(message + '\n')

    def showStatus(self, msg, clearAfter=None):
        pass

def conformance_test():
    dirpath=os.path.join(os.getcwd(), "tests", "conformance")

    # At the moment xbrl and xdt work, efm and formula fail with None.type error
    for test in [tests["xbrl"], tests["xdt"]]:
        short_name = os.path.basename(test['url'])
        local_name = os.path.join(dirpath, short_name)
        dir_name = os.path.join(dirpath, os.path.splitext(short_name)[0])

        args = test['args']
        args[0] = os.path.join(dir_name, args[0])
        args[1] = os.path.join(dir_name, args[1])
        args[2] = os.path.join(dir_name, args[2])

        for index, test, variation in Tester().run(*args):
            partial_fn = partial(check_variation, index, test, variation)
            base_message = "%(index)s %(test)s %(id)s %(name)s"
            partial_fn.description = base_message % { 'index' : index, 
                                                     'test' : test,
                                                     'id' : variation.id or "",
                                                     'name': variation.name }
            yield(partial_fn,)