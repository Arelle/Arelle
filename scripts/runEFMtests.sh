#!/bin/bash

# Run SEC Edgar Filer Manual (EFM) Conformance Suite tests

TESTCASESINDEXFILE=/Users/hermf/Documents/mvsl/projects/SEC/efm/conf/testcases.xml
PLUGINS=EdgarRenderer
DISCLOSURE_SYSTEM=efm-pragmatic-preview

LOG_DIR=/users/hermf/temp
rm -f $LOG_DIR/EFM-conf-*
OUTPUTLOGFILE=$LOG_DIR/EFM-conf-log.txt
OUTPUTERRFILE=$LOG_DIR/EFM-conf-err.txt
OUTPUTCSVFILE=$LOG_DIR/EFM-conf-report.xlsx
ARELLECMDLINESRC=./arelleCmdLine.py
PYTHON=python3.9

$PYTHON $ARELLECMDLINESRC --noCertificateCheck --file "$TESTCASESINDEXFILE" --plugins $PLUGINS --disclosureSystem $DISCLOSURE_SYSTEM --validate --csvTestReport "$OUTPUTCSVFILE" --testcaseResultsCaptureWarnings --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
