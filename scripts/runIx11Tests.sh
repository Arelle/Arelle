#!/bin/bash

# Run Inline XBRL 1.1 Conformance Suite tests

LOGDIR=~/temp

TESTSDIR=~/Documents/mvsl/projects/XBRL.org/ix11/inlineXBRL-1.1-conformanceSuite-WGWD-YYYY-MM-DD
TESTSDIR=~/Documents/mvsl/projects/XBRL.org/ix11/inlineXBRL-1.1-conformanceSuite-2020-04-08

TESTCASESINDEXFILE=${TESTSDIR}/index.xml

PACKAGES=${TESTSDIR}/schemas/www.example.com.zip

rm -f ${LOGDIR}/Ix11-*

OUTPUTLOGFILE=${LOGDIR}/Ix11-log.txt
OUTPUTERRFILE=${LOGDIR}/Ix11-err.txt
OUTPUTCSVFILE=${LOGDIR}/Ix11-report.xlsx

PLUGINS='inlineXbrlDocumentSet.py'
PLUGINS='inlineXbrlDocumentSet.py|../examples/plugin/testcaseIxExpectedHtmlFixup.py'

python3.9 arelleCmdLine.py --file "$TESTCASESINDEXFILE" --packages=$PACKAGES --validate --plugins $PLUGINS --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
#./runArelle.sh --file "$TESTCASESINDEXFILE" --packages=$PACKAGES --validate --plugins inlineXbrlDocumentSet.py --skipExpectedInstanceComparison --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
