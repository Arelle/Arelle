#!/bin/bash

# Run Taxonomy Package tests

TESTCASESROOT=/Users/hermf/Documents/mvsl/projects/XBRL.org/taxonomy-package-conformance
rm -fr /users/hermf/temp/Package-test-*
OUTPUTLOGFILE=/users/hermf/temp/Package-test-log.txt
OUTPUTERRFILE=/users/hermf/temp/Package-test-err.txt
OUTPUTCSVFILE=/users/hermf/temp/Package-test-report.xlsx
TESTCASESINDEXFILE="$TESTCASESROOT/index.xml"

ARELLEDIR=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src

python3.9 ${ARELLEDIR}/arelleCmdLine.py --file "$TESTCASESINDEXFILE" --validate --csvTestReport "$OUTPUTCSVFILE"  --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"

