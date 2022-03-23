#!/bin/bash
# Run XBRL Formula Conformance Suite tests

TESTCASESROOT="/Users/hermf/Documents/mvsl/projects/SEC/19.2/conformance-tests"
TESTCASESINDEXFILE=$TESTCASESROOT/testcase.xml
OUTPUTLOGFILE=/Users/hermf/temp/TR-SEC-test-log.txt
OUTPUTCSVFILE=/Users/hermf/temp/TR-SEC-test-report.xlsx
ARELLEDIR=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src
PYTHONPATH=$ARELLEDIR

rm -fr "$OUTPUTCSVFILE" "$OUTPUTLOGFILE"

python3.9 -m arelle.CntlrCmdLine --file "$TESTCASESINDEXFILE" --validate --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" --plugin transforms/SEC
