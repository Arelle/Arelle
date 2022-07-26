#!/bin/bash
# Run XBRL Formula Conformance Suite tests

LOGDIR=~/temp

TESTCASESROOT=~/Documents/mvsl/projects/XBRL.org/formula/tests
TESTCASESINDEXFILE=$TESTCASESROOT/index.xml
OUTPUTLOGFILE=$LOGDIR/Formula-test-log.txt
OUTPUTCSVFILE=$LOGDIR/Formula-test-report.xlsx
PYTHONPATH=$ARELLEDIR

rm -fr "$OUTPUTCSVFILE" "$OUTPUTLOGFILE"

python3.9 arelleCmdLine.py --file "$TESTCASESINDEXFILE" --validate --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" --plugin formulaXPathChecker --check-formula-restricted-XPath

TESTCASESROOT=~/Documents/mvsl/projects/XBRL.org/formula/function-registry
TESTCASESINDEXFILE=$TESTCASESROOT/registry-index.xml
OUTPUTLOGFILE=$LOGDIR/Function-test-log.txt
OUTPUTCSVFILE=$LOGDIR/Function-test-report.xlsx

rm -fr "$OUTPUTCSVFILE" "$OUTPUTLOGFILE"

python3.9 arelleCmdLine.py --file "$TESTCASESINDEXFILE" --validate --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" --plugin formulaXPathChecker --check-formula-restricted-XPath
