import os

from arelle.CntlrCmdLine import parseAndRun

# from https://specifications.xbrl.org/release-history-formula-1.0-formula-conf.html
TEST_SUITE = 'tests/resources/conformance_suites/formula.zip/formula/tests'
ARGS = [
    '--file', os.path.abspath(os.path.join(TEST_SUITE, 'index.xml')),
    '--testcaseResultsCaptureWarnings',
    '--validate',

    '--csvTestReport', 'Formula-test-report.csv',
    '--logFile', 'Formula-test-log.txt',
]


if __name__ == "__main__":
    print('Running formula tests...')
    parseAndRun(ARGS)
