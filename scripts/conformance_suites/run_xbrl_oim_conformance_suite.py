import os

from arelle.CntlrCmdLine import parseAndRun


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/oim-conf-2021-10-13.zip'
BASE_ARGS = [
    '--csvTestReport', './oim-conf-report.csv',
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'oim-index.xml')),
    '--formula', 'run',
    '--logFile', './oim-conf-log.txt',
    '--plugins', 'loadFromOIM',
    '--testcaseResultsCaptureWarnings',
    '--validate'
]


def run_xbrl_oim_conformance_suite(args):
    """
    Kicks off the validation of the XBRL Open Information Model 1.0 conformance suite.

    :param args: The arguments to pass to Arelle in order to accurately validate the XBRL Open Information Model 1.0 conformance suite
    :param args: list of str
    :return: Returns the result of parseAndRun which in this case is the created controller object
    :rtype: ::class:: `~arelle.CntlrCmdLine.CntlrCmdLine`
    """
    return parseAndRun(args)


if __name__ == "__main__":
    print('Running XBRL Open Information Model 1.0 tests...')
    run_xbrl_oim_conformance_suite(BASE_ARGS)
