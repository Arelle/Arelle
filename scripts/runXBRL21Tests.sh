#!/bin/bash

# Run XBRL 2.1 Conformance Suite tests

TESTCASESROOT=/users/hermf/Documents/mvsl/projects/XBRL.org/conformance-svn/trunk
rm -f /users/hermf/temp/XBRL21-conf-*
OUTPUTLOGFILE=/users/hermf/temp/XBRL21-conf-log.txt
OUTPUTERRFILE=/users/hermf/temp/XBRL21-conf-err.txt
OUTPUTCSVFILE=/users/hermf/temp/XBRL21-conf-report.xlsx
TESTCASESINDEXFILE=$TESTCASESROOT/xbrl.xml
ARELLEDIR=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src

PYTHONPATH=$ARELLEDIR

python3.9 -m arelle.CntlrCmdLine --file "$TESTCASESINDEXFILE" --validate --calcDecimals --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
