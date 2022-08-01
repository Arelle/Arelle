import os

from arelle.CntlrCmdLine import parseAndRun

# part of https://specifications.xbrl.org/release-history-formula-1.0-formula-conf.html
CONFORMANCE_SUITE = 'tests/resources/conformance_suites/60111 AssertionSeverity-2.0-Processing.zip/60111 AssertionSeverity-2.0-Processing'
ARGS = [
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, '60111 Assertion Severity 2.0 Processing.xml')),
    '--testcaseResultsCaptureWarnings',
    '--validate',

    '--csvTestReport', 'assertion2-report.csv',
    '--logFile', 'assertion2-log.txt',
]


if __name__ == "__main__":
    print('Running Assertion Severity 2.0 tests...')
    parseAndRun(ARGS)
