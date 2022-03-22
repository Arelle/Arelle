#!/bin/bash
# Run XBRL Formula Conformance Suite tests

TESTCASESROOT="/Users/hermf/Documents/mvsl/projects/XBRL.org/tr4/trr-master-conformance-tests/conformance-tests"
TESTCASESINDEXFILE=$TESTCASESROOT/testcase.xml
OUTPUTLOGFILE=/Users/hermf/temp/TR4-test-log.txt
OUTPUTCSVFILE=/Users/hermf/temp/TR4-test-report.xlsx
ARELLEDIR=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src
PYTHONPATH=$ARELLEDIR

rm -fr "$OUTPUTCSVFILE" "$OUTPUTLOGFILE"

python3.9 -m arelle.CntlrCmdLine --file "$TESTCASESINDEXFILE" --validate --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE"
