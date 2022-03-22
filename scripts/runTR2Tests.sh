#!/bin/bash
# Run XBRL Formula Conformance Suite tests

TESTCASESROOT="/Users/hermf/Documents/mvsl/projects/XBRL.org/conformance-rendering/trunk/inlineXBRL/xii-transformationRegistry-v2/conformance-tests"
TESTCASESINDEXFILE=$TESTCASESROOT/testcase.xml
OUTPUTLOGFILE=/Users/hermf/temp/TR2-test-log.txt
OUTPUTCSVFILE=/Users/hermf/temp/TR2-test-report.xlsx
ARELLEDIR=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src
PYTHONPATH=$ARELLEDIR

rm -fr "$OUTPUTCSVFILE" "$OUTPUTLOGFILE"

python3.9 -m arelle.CntlrCmdLine --file "$TESTCASESINDEXFILE" --validate --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE"
