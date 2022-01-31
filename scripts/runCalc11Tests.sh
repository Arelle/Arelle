#!/bin/bash

# Run DQC Conformance Suite tests

TESTCASESINDEXFILE=/Users/hermf/Documents/mvsl/projects/XBRL.org/calculation-1.1-conformance-DRAFT-YYYY-MM-DD/index.xml
OUTPUTLOGFILE=/users/hermf/temp/Calc11-log.txt
OUTPUTERRFILE=/users/hermf/temp/Calc11-err.txt
OUTPUTCSVFILE=/users/hermf/temp/Calc11-report.xlsx
ARELLEDIR=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/hfdev
PYTHON=python3.9

rm -f $OUTPUTLOGFILE $OUTPUTERRFILE

PYTHONPATH=$ARELLEDIR

$PYTHON ${ARELLEDIR}/arelleCmdLine.py --file "$TESTCASESINDEXFILE" --calc11 --validate --plugins loadFromOIM --csvTestReport "$OUTPUTCSVFILE"  --logFile "$OUTPUTLOGFILE" --noCertificateCheck 2>  "$OUTPUTERRFILE"
