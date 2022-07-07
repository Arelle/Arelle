import os

from arelle.CntlrCmdLine import parseAndRun


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/trr-3.0.1.zip'
BASE_ARGS = [
    '--csvTestReport', './transformation-registry-3-conf-report.csv',
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'testcase.xml')),
    '--formula', 'run',
    '--logFile', './transformation-registry-3-conf-log.txt',
    '--testcaseResultsCaptureWarnings',
    '--validate'
]


def run_xbrl_transformation_registry_3_conformance_suite(args):
    """
    Kicks off the validation of the XBRL Transformation Registry 3 conformance suite.

    :param args: The arguments to pass to Arelle in order to accurately validate the conformance suite
    :param args: list of str
    :return: Returns the result of parseAndRun which in this case is the created controller object
    :rtype: ::class:: `~arelle.CntlrCmdLine.CntlrCmdLine`
    """
    return parseAndRun(args)


if __name__ == "__main__":
    print('Running XBRL Transformation Registry 3 tests...')
    run_xbrl_transformation_registry_3_conformance_suite(BASE_ARGS)
