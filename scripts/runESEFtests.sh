#!/bin/bash

# Run ESMA ESEF conformance tests

ARELLECMDLINESRC=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src/arelleCmdLine.py
PYTHON=/opt/homebrew/bin/python3.9
PLUGINS='validate/ESEF'
PACKAGES=/Users/hermf/Documents/mvsl/projects/ESMA/esef_taxonomy_2021.zip 
FILTER='(?!arelle:testcaseDataUnexpected)'
FORMULA=none
FORMULA=run

# run from directory test case root
#TESTCASESROOT=/Users/hermf/Documents/mvsl/projects/ESMA/conf/esef_conformance_suite_2021
# zip file test case root
TESTCASESROOT=/Users/hermf/Documents/mvsl/projects/ESMA/conf/esef_conformance_suite_2021.zip/esef_conformance_suite_2021/esef_conformance_suite_2021

rm -f /users/hermf/temp/ESEF-conf-*

TESTCASESINDEXFILE=${TESTCASESROOT}/index_inline_xbrl.xml
OUTPUTLOGFILE=/users/hermf/temp/ESEF-conf-ixbrl-log.txt
OUTPUTERRFILE=/users/hermf/temp/ESEF-conf-ixbrl-err.txt
OUTPUTCSVFILE=/users/hermf/temp/ESEF-conf-ixbrl-report.xlsx

$PYTHON $ARELLECMDLINESRC --file "$TESTCASESINDEXFILE" --plugins $PLUGINS --packages $PACKAGES --disclosureSystem esef --logCodeFilter $FILTER --formula $FORMULA --validate --csvTestReport "$OUTPUTCSVFILE" --testcaseResultsCaptureWarnings --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"

TESTCASESINDEXFILE=${TESTCASESROOT}/index_pure_xhtml.xml
OUTPUTLOGFILE=/users/hermf/temp/ESEF-conf-xhtml-log.txt
OUTPUTERRFILE=/users/hermf/temp/ESEF-conf-xhtml-err.txt
OUTPUTCSVFILE=/users/hermf/temp/ESEF-conf-xhtml-report.xlsx

$PYTHON $ARELLECMDLINESRC --file "$TESTCASESINDEXFILE" --plugins $PLUGINS --packages $PACKAGES --disclosureSystem esef-unconsolidated --logCodeFilter $FILTER --formula $FORMULA --validate --csvTestReport "$OUTPUTCSVFILE" --testcaseResultsCaptureWarnings --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
