'''
Use this module to start Arelle in py.test modes

See COPYRIGHT.md for copyright information.

This module supports the conformance tests to validate that Arelle is
working properly.  See arelle_test.py.

'''

import os

def pytest_addoption(parser):
    tests_default = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 os.path.join('arelle',
                                              os.path.join('config',
                                                           'arelle_test.ini')))
    parser.addoption('--tests', default=tests_default,
                     help='.ini file to load test suites from (default is arelle/confi/arelle_test.ini)')

