"""
This script runs the conformance tests to validate the implementation.
"""
import os.path, gettext, nose
from nose.tools import eq_
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
         'XBRL' :  {    # XBRL 2.1
                    'url'  : 'http://www.xbrl.org/2008/XBRL-CONF-CR4-2008-07-02.zip',
                    'args' : ["xbrl.xml", False, False, False]
                    }, 
         
         'Formula' : {  # Formula
                      'url'  : 'http://www.xbrl.org/Specification/formula/REC-2009-06-22/conformance/Formula-CONF-REC-PER-Errata-2011-03-16.zip',
                      'args' : [ "index.xml", False, False, False],
                      },
         'XDT' : {      # XDT
                  'url'  : "http://www.xbrl.org/2009/XDT-CONF-CR4-2009-10-06.zip",
                  'args' : [ "xdt.xml", False, False, False ]
                  }, 
         'Edgar' : {    # Edgar
                    'url'  : 'http://www.sec.gov/info/edgar/ednews/efmtest/16-110225.zip',
                    'args' : [ "testcases.xml", True, False, False]
                    }
         }

class TestCntlr(Cntlr.Cntlr):
    """The function used to wrap tests."""
    def __init__(self):
        super(TestCntlr, self).__init__()
        self.messages = []
        self.filename = None
        self.outcomes = list()
        
    def run(self, testfn, efm, utr, dec):
        """The run method is invoked to make things happen."""
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

def check_variation(variation):
    assert variation.status == "pass", "%s != %s" % (variation.expected, variation.actual)
  
def conformance_test():
    dirpath=os.path.join(os.getcwd(), "tests", "conformance")
    for name in ["XBRL", "XDT", "Formula", "Edgar"]:
        test = tests[name]
        short_name = os.path.basename(test['url'])
        dir_name = os.path.join(dirpath, os.path.splitext(short_name)[0])
        args = test['args']
        args[0] = os.path.join(dir_name, args[0])
        for index, test, variation in TestCntlr().run(*args):
            tname = os.path.splitext(test)[0]
            z = partial(check_variation, variation)
            z.description = "%s [ %s ] %s %s" % (name, tname, variation.id, variation.name)
            setattr(z, "__module__", "%s %s" % (name, tname))
            setattr(z, "__name__", "%s %s" % (variation.id, variation.name))
            yield(z)
            
if __name__ == "__main__":
<<<<<<< HEAD
    import nose
    """Main program."""
=======
>>>>>>> herm/lxml
    argv = ["nosetests", "-v", "--with-xunit"]
    nose.main(argv=argv)
