import os

from arelle.CntlrCmdLine import parseAndRun


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/esef_conformance_suite_2021.zip/esef_conformance_suite_2021/esef_conformance_suite_2021'
PLUGIN = 'validate/ESEF'
FILTER = '(?!arelle:testcaseDataUnexpected)'

BASE_ARGS = [
    '--logCodeFilter', FILTER,
    '--plugins', PLUGIN,
    '--testcaseResultsCaptureWarnings',
    '--validate'
]

IXBRL_ARGS = [
    '--disclosureSystem', 'esef',
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'index_inline_xbrl.xml')),
    '--formula', 'run',
    '--logFile', './ESEF-conf-ixbrl-log.txt',
    '--csvTestReport', './ESEF-conf-ixbrl-report.xlsx',
]

XHTML_ARGS = [
    '--disclosureSystem', 'esef-unconsolidated',
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'index_pure_xhtml.xml')),
    '--formula', 'none',
    '--logFile', './ESEF-conf-xhtml-log.txt',
    '--csvTestReport', './ESEF-conf-xhtml-report.xlsx',
]


def run_esef_conformance_suite(args):
    """
    Kicks off the validation of the ESEF conformance suite.

    :param args: The arguments to pass to Arelle in order to accurately validate the ESEF conformance suite
    :param args: list of str
    :return: Returns the result of parseAndRun which in this case is the created controller object
    :rtype: ::class:: `~arelle.CntlrCmdLine.CntlrCmdLine`
    """
    return parseAndRun(args)


if __name__ == "__main__":
    print('Running ixbrl tests...')
    runtime_args = BASE_ARGS + IXBRL_ARGS
    run_esef_conformance_suite(runtime_args)

    print('Running xhtml tests...')
    runtime_args = BASE_ARGS + XHTML_ARGS
    run_esef_conformance_suite(runtime_args)
