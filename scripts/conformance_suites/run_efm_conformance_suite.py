import os

from arelle.CntlrCmdLine import parseAndRun


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/efm_conformance_suite_2022.zip/conf'
TAXONOMY_PACKAGE = 'tests/resources/taxonomy_packages/edgarTaxonomiesPackage-22.1.zip'
PLUGIN = 'validate/EFM'
FILTER = '(?!arelle:testcaseDataUnexpected)'

BASE_ARGS = [
    '--logCodeFilter', FILTER,
    '--packages', '{}'.format(os.path.abspath(TAXONOMY_PACKAGE)),
    '--plugins', PLUGIN,
    '--testcaseResultsCaptureWarnings',
    '--validate'
]

IXBRL_ARGS = [
    '--disclosureSystem', 'efm-pramatic',
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'testcases.xml')),
    '--formula', 'run',
    '--logFile', './EFM-conf-log.txt',
    '--csvTestReport', './EFM-conf-report.xlsx',
]


def run_efm_conformance_suite(args):
    """
    Kicks off the validation of the EFM conformance suite.

    :param args: The arguments to pass to Arelle in order to accurately validate the EFM conformance suite
    :param args: list of str
    :return: Returns the result of parseAndRun which in this case is the created controller object
    :rtype: ::class:: `~arelle.CntlrCmdLine.CntlrCmdLine`
    """
    return parseAndRun(args)


if __name__ == "__main__":
    print('Running EFM tests...')
    runtime_args = BASE_ARGS + IXBRL_ARGS
    run_efm_conformance_suite(runtime_args)
