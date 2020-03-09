#!/bin/bash

# Run Inline XBRL 1.1 Conformance Suite tests

LOGDIR=~/temp

TESTSDIR=~/Documents/mvsl/projects/XBRL.org/conformance-rendering/trunk/inlineXBRL/pub/Conformance/inlineXBRL-1.1/FINAL-2017-10-11/inlineXBRL-1.1-conformanceSuite-2017-10-11
#TESTSDIR=/export/home/arelle/XBRL.org/conformance-rendering/trunk/inlineXBRL/nopub/Conformance/inlineXBRL-1.1/DRAFT-2017-10-03/inlineXBRL-1.1-conformanceSuite-DRAFT-2017-10-03
TESTSDIR=~/Documents/mvsl/projects/XBRL.org/ix11/inlineXBRL-1.1-conformanceSuite-WGWD-YYYY-MM-DD

TESTCASESINDEXFILE=${TESTSDIR}/index.xml

PACKAGES=${TESTSDIR}/schemas/www.example.com.zip

rm -f ${LOGDIR}/Ix11-*

OUTPUTLOGFILE=${LOGDIR}/Ix11-log.txt
OUTPUTERRFILE=${LOGDIR}/Ix11-err.txt
OUTPUTCSVFILE=${LOGDIR}/Ix11-report.xlsx

PLUGINS='inlineXbrlDocumentSet.py|../examples/plugin/testcaseIxExpectedHtmlFixup.py'
PLUGINS='inlineXbrlDocumentSet.py'

python3.5 arelleCmdLine.py --file "$TESTCASESINDEXFILE" --packages=$PACKAGES --validate --plugins $PLUGINS --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
#./runArelle.sh --file "$TESTCASESINDEXFILE" --packages=$PACKAGES --validate --plugins inlineXbrlDocumentSet.py --skipExpectedInstanceComparison --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
