#!/bin/bash

# Run Inline XBRL 1.1 Conformance Suite tests

LOGDIR=~/temp

TESTSDIR=~/Documents/mvsl/projects/XBRL.org/conformance-rendering/trunk/inlineXBRL/nopub/Conformance/inlineXBRL-1.1/WGWD-YYYY-MM-DD/inlineXBRL-1.1-conformanceSuite-WGWD-YYYY-MM-DD
#TESTSDIR=/export/home/arelle/XBRL.org/conformance-rendering/trunk/inlineXBRL/nopub/Conformance/inlineXBRL-1.1/DRAFT-2017-10-03/inlineXBRL-1.1-conformanceSuite-DRAFT-2017-10-03
TESTCASESINDEXFILE=${TESTSDIR}/index.xml

PACKAGES=${TESTSDIR}/schemas/www.example.com.zip

rm -f ${LOGDIR}/Ix11-*

OUTPUTLOGFILE=${LOGDIR}/Ix11-log.txt
OUTPUTERRFILE=${LOGDIR}/Ix11-err.txt
OUTPUTCSVFILE=${LOGDIR}/Ix11-report.xlsx

python3.5 arelleCmdLine.py --file "$TESTCASESINDEXFILE" --packages=$PACKAGES --validate --plugins 'inlineXbrlDocumentSet.py|../examples/plugin/testcaseIxExpectedHtmlFixup.py' --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
#./runArelle.sh --file "$TESTCASESINDEXFILE" --packages=$PACKAGES --validate --plugins inlineXbrlDocumentSet.py --skipExpectedInstanceComparison --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
