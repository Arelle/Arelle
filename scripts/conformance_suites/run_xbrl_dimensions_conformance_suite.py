import os

from arelle.CntlrCmdLine import parseAndRun


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/xdt-conf-cr4-2009-10-06.zip'
BASE_ARGS = [
    '--csvTestReport', './xdt-conf-report.csv',
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'xdt.xml')),
    '--formula', 'run',
    '--logFile', './xdt-conf-log.txt',
    '--infoset',
    '--testcaseResultsCaptureWarnings',
    '--validate'
]


def run_xbrl_dimensions_conformance_suite(args):
    """
    Kicks off the validation of the XBRL Dimensions 1.0 conformance suite.

    :param args: The arguments to pass to Arelle in order to accurately validate the XBRL Dimensions 1.0 conformance suite
    :param args: list of str
    :return: Returns the result of parseAndRun which in this case is the created controller object
    :rtype: ::class:: `~arelle.CntlrCmdLine.CntlrCmdLine`
    """
    return parseAndRun(args)


if __name__ == "__main__":
    print('Running XBRL Dimensions 1.0 tests...')
    run_xbrl_dimensions_conformance_suite(BASE_ARGS)
