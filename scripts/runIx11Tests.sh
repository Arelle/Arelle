#!/bin/bash

# Run Inline XBRL 1.1 Conformance Suite tests

TESTCASESROOT=/users/hermf/Documents/mvsl/projects/XBRL.org/conformance-rendering/trunk/inlineXBRL/nopub/Conformance/inlineXBRL-1.1/WGWD-YYYY-MM-DD/inlineXBRL-1.1-conformanceSuite-WGWD-YYYY-MM-DD
OUTPUTLOGFILE=/users/hermf/temp/Ix11-log.txt
OUTPUTERRFILE=/users/hermf/temp/Ix11-err.txt
OUTPUTCSVFILE=/users/hermf/temp/Ix11-report.csv
TESTCASESINDEXFILE=$TESTCASESROOT/tests/index.xml
PACKAGES=$TESTCASESROOT/schemas/www.example.com.zip
ARELLEDIR=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src

PYTHONPATH=$ARELLEDIR

python3.5 -m arelle.CntlrCmdLine --file "$TESTCASESINDEXFILE" --packages=$PACKAGES --validate --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
