import os

from arelle.CntlrCmdLine import parseAndRun

# from https://specifications.xbrl.org/release-history-formula-1.0-formula-conf.html
CONFORMANCE_SUITE = 'tests/resources/conformance_suites/formula.zip/formula/function-registry'
ARGS = [
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'registry-index.xml')),
    '--plugin', 'formulaXPathChecker|functionsMath',
    '--check-formula-restricted-XPath',
    '--noValidateTestcaseSchema',
    '--testcaseResultsCaptureWarnings',
    '--validate',

    '--csvTestReport', 'function-registry-report.csv',
    '--logFile', 'function-registry-log.txt',
]


if __name__ == "__main__":
    print('Running formula function registry tests...')
    parseAndRun(ARGS)
