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

$ py.test --tests ~/Desktop/custom_tests.ini

c:arelleSrcTopDirectory> \python32\scripts\py.test 

The default test suites are specified in test_conformance.ini .
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

logging.basicConfig(level=logging.DEBUG)

def test_checker(name, test, variation):
    logging.info("Name: %s Test: %s Variation: %s" %
                 ( name, test, variation['id']))
    logging.info("\tVariation Details: %s %s %s %s" %
                 (variation['name'], variation['status'],
                  variation['expected'], variation['actual']))
    assert variation['status'] == "pass", ("%s (%s != %s)" %
                                           (variation['status'],
                                            variation['expected'],
                                            variation['actual']))

# Pytest test parameter generator
def pytest_generate_tests(metafunc):
    print ("gen tests") # ?? print does not come out to console or log, want to show progress
    config = configparser.ConfigParser(allow_no_value=True) # allow no value
    if not os.path.exists(metafunc.config.option.tests):
        raise IOError('--test file does not exist: %s' %
                      metafunc.config.option.tests)
    config.read(metafunc.config.option.tests)
    for i, section in enumerate(config.sections()):
        arelleRunArgs = ['--keepOpen']  # don't close, so we can inspect results below
        for optionName, optionValue in config.items(section):
            if not optionName.startswith('_'):
                arelleRunArgs.append('--' + optionName)
                if optionValue:
                    arelleRunArgs.append(optionValue)
        print("section {0} run arguments {1}".format(section, " ".join(arelleRunArgs)))
        cntlr_run = runTest(arelleRunArgs)
        for index, test, variation in cntlr_run:
            metafunc.addcall(funcargs=dict(name=section,
                                           test=test,
                                           variation=variation))
        if i == 1: break # stop on first test
    
def runTest(args):
    print ("run tests") # ?? print does not come out to console or log, want to show progress
    
    # something locks garbage collection during run, not freeing up same way as when running from shell
    cntlr = parseAndRun(args, logger=logging.getLogger()) # use root logger
        
    outcomes = []
    if '--validate' in args:
        modelDocument = cntlr.modelManager.modelXbrl.modelDocument

        if modelDocument is not None:
            if modelDocument.type in (ModelDocument.Type.TESTCASESINDEX,
                                      ModelDocument.Type.REGISTRY):
                index = os.path.basename(modelDocument.uri)
                for tci in modelDocument.referencesDocument.keys():
                    tc = cntlr.modelManager.modelXbrl.modelObject(tci.objectId())
                    test_case = os.path.basename(tc.uri)
                    if hasattr(tc, "testcaseVariations"):
                        for mv in tc.testcaseVariations:
                            outcomes.append((index, test_case,
                                             {'id': mv.id, 
                                              'name': mv.name, 
                                              'status': mv.status, 
                                              'expected': mv.expected, 
                                              'actual': mv.actual}))
            elif modelDocument.type in (ModelDocument.Type.TESTCASE,
                                        ModelDocument.Type.REGISTRYTESTCASE):
                tc = modelDocument
                test_case = os.path.basename(tc.uri)
                if hasattr(tc, "testcaseVariations"):
                    for mv in tc.testcaseVariations:
                        outcomes.append((None, test_case,
                                             {'id': mv.id, 
                                              'name': mv.name, 
                                              'status': mv.status, 
                                              'expected': mv.expected, 
                                              'actual': mv.actual}))

    cntlr.modelManager.close()
    return outcomes        
            
