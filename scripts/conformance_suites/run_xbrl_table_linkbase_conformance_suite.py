import os

from arelle.CntlrCmdLine import parseAndRun


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/table-linkbase-conf-2015-08-12.zip/table-linkbase-conf-2015-08-12/conf'
BASE_ARGS = [
    '--csvTestReport', './table-linkbase-conf-report.csv',
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'testcases-index.xml')),
    '--formula', 'run',
    '--logFile', './table-linkbase-conf-log.txt',
    '--testcaseResultsCaptureWarnings',
    '--validate'
]


def run_xbrl_table_linkbase_conformance_suite(args):
    """
    Kicks off the validation of the XBRL Table Linkbase conformance suite.

    :param args: The arguments to pass to Arelle in order to accurately validate the XBRL Table Linkbase conformance suite
    :param args: list of str
    :return: Returns the result of parseAndRun which in this case is the created controller object
    :rtype: ::class:: `~arelle.CntlrCmdLine.CntlrCmdLine`
    """
    return parseAndRun(args)


if __name__ == "__main__":
    print('Running XBRL Table Linkbase tests...')
    run_xbrl_table_linkbase_conformance_suite(BASE_ARGS)
