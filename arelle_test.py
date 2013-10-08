'''
Created on May 14,2012

Use this module to start Arelle in py.test modes

@author: Mark V Systems Limited
(c) Copyright 2012 Mark V Systems Limited, All rights reserved.

This module runs the conformance tests to validate that Arelle is
working properly.  It needs to be run through the package pytest which
can be installed via pip.

$ pip install pytest
  -or-
c:\python32\scripts> easy_install -U pytest

$ py.test test_conformance.py

It can take an optional parameter --tests to specify a .ini file for
loading additional test suites.

$ py.test --tests=~/Desktop/custom_tests.ini

c:arelleSrcTopDirectory> \python32\scripts\py.test 

The default test suites are specified in test_conformance.ini .

In order to use SVN tests, you will need an XII user name and password (in [DEFAULT] section of ini file)

To get a standard xml file out of the test run, add --junittests=foo.xml, e.g.:

c:arelleSrcTopDirectory> \python32\scripts\py.test --tests=myIniWithPassword.ini -junittests=foo.xml
 
'''

try:
    import pytest
except ImportError:
    print ('Please install pytest\neasy_install -U pytest')
    exit()
    
import os, configparser, logging
from collections import namedtuple
from arelle.CntlrCmdLine import parseAndRun
from arelle import ModelDocument
            
# clean out non-ansi characters in log
class TestLogHandler(logging.Handler):        
    def __init__(self):
        super(TestLogHandler, self).__init__()
        self.setFormatter(TestLogFormatter())
        
    def emit(self, logRecord):
        print(self.format(logRecord))
                
class TestLogFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None):
        super(TestLogFormatter, self).__init__(fmt, datefmt)
        
    def format(self, record):
        formattedMessage = super(TestLogFormatter, self).format(record)
        return ''.join(c if ord(c) < 128 else '*' for c in formattedMessage)

logging.basicConfig(level=logging.DEBUG)
testLogHandler = TestLogHandler()

def test(section, testcase, variation, name, status, expected, actual):
    assert status == "pass"

# assert status == "pass", ("[%s] %s:%s %s (%s != %s)" % (section, testcase, variation, name, expected, actual))

# Pytest test parameter generator
def pytest_generate_tests(metafunc):
    print ("gen tests") # ?? print does not come out to console or log, want to show progress
    config = configparser.ConfigParser(allow_no_value=True) # allow no value
    if not os.path.exists(metafunc.config.option.tests):
        raise IOError('--test file does not exist: %s' %
                      metafunc.config.option.tests)
    config.read(metafunc.config.option.tests)
    for i, section in enumerate(config.sections()):
        # don't close, so we can inspect results below; log to std err
        arelleRunArgs = ['--keepOpen', '--logFile', 'logToStdErr']  
        for optionName, optionValue in config.items(section):
            if not optionName.startswith('_'):
                arelleRunArgs.append('--' + optionName)
                if optionValue:
                    arelleRunArgs.append(optionValue)
        print("section {0} run arguments {1}".format(section, " ".join(arelleRunArgs)))
        cntlr_run = runTest(section, arelleRunArgs)
        for variation in cntlr_run:
            metafunc.addcall(funcargs=variation,
                             id="[{0}] {1}: {2}".format(variation["section"],
                                                       variation["testcase"].rpartition(".")[0],
                                                       variation["variation"]))
        # if i == 1: break # stop on first test  -- uncomment to do just counted number of tests
    
def runTest(section, args):
    print ("run tests") # ?? print does not come out to console or log, want to show progress
    
    cntlr = parseAndRun(args) # log to print (only failed assertions are captured)
        
    outcomes = []
    if '--validate' in args:
        modelDocument = cntlr.modelManager.modelXbrl.modelDocument

        if modelDocument is not None:
            if modelDocument.type in (ModelDocument.Type.TESTCASESINDEX,
                                      ModelDocument.Type.REGISTRY):
                index = os.path.basename(modelDocument.uri)
                for tc in sorted(modelDocument.referencesDocument.keys(), key=lambda doc: doc.uri):
                    test_case = os.path.basename(tc.uri)
                    if hasattr(tc, "testcaseVariations"):
                        for mv in tc.testcaseVariations:
                            outcomes.append({'section': section,
                                             'testcase': test_case,
                                             'variation': str(mv.id or mv.name), # copy string to dereference mv
                                             'name': str(mv.description or mv.name), 
                                             'status': str(mv.status), 
                                             'expected': str(mv.expected), 
                                             'actual': str(mv.actual)})
            elif modelDocument.type in (ModelDocument.Type.TESTCASE,
                                        ModelDocument.Type.REGISTRYTESTCASE):
                tc = modelDocument
                test_case = os.path.basename(tc.uri)
                if hasattr(tc, "testcaseVariations"):
                    for mv in tc.testcaseVariations:
                        outcomes.append({'section': section,
                                         'testcase': test_case,
                                         'variation': str(mv.id or mv.name), 
                                         'name': str(mv.description or mv.name), 
                                         'status': str(mv.status), 
                                         'expected': str(mv.expected), 
                                         'actual': str(mv.actual)})
            elif modelDocument.type == ModelDocument.Type.RSSFEED:
                tc = modelDocument
                if hasattr(tc, "rssItems"):
                    for rssItem in tc.rssItems:
                        outcomes.append({'section': section,
                                         'testcase': os.path.basename(rssItem.url),
                                         'variation': str(rssItem.accessionNumber), 
                                         'name': str(rssItem.formType + " " +
                                                     rssItem.cikNumber + " " +
                                                     rssItem.companyName + " " +
                                                     str(rssItem.period) + " " + 
                                                     str(rssItem.filingDate)), 
                                         'status': str(rssItem.status), 
                                         'expected': rssItem.url, 
                                         'actual': " ".join(str(result) for result in (rssItem.results or [])) +
                                                   ((" " + str(rssItem.assertions)) if rssItem.assertions else "")})
        del modelDocument # dereference
    cntlr.modelManager.close()
    del cntlr # dereference

    return outcomes        
            
