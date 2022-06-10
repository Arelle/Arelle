import os

from arelle.CntlrCmdLine import parseAndRun


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/XBRL-CONF-2014-12-10.zip'
BASE_ARGS = [
    '--csvTestReport', './xbrl-conf-report.csv',
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'xbrl.xml')),
    '--formula', 'run',
    '--logFile', './xbrl-conf-log.txt',
    '--calcPrecision',
    '--testcaseResultsCaptureWarnings',
    '--validate'
]


def run_xbrl_conformance_suite(args):
    """
    Kicks off the validation of the XBRL 2.1 conformance suite.

    :param args: The arguments to pass to Arelle in order to accurately validate the XBRL 2.1 conformance suite
    :param args: list of str
    :return: Returns the result of parseAndRun which in this case is the created controller object
    :rtype: ::class:: `~arelle.CntlrCmdLine.CntlrCmdLine`
    """
    return parseAndRun(args)


if __name__ == "__main__":
    print('Running XBRL 2.1 tests...')
    run_xbrl_conformance_suite(BASE_ARGS)
