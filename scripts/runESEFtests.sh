#!/bin/bash

# Run ESMA ESEF conformance tests

TESTCASESROOT=/Users/hermf/Documents/mvsl/projects/ESMA/conf/esef_conformanceSuite_2020-10-02/index.xml

rm -f /users/hermf/temp/ESEF-conf-*
OUTPUTLOGFILE=/users/hermf/temp/ESEF-conf-log.txt
OUTPUTERRFILE=/users/hermf/temp/ESEF-conf-err.txt
OUTPUTCSVFILE=/users/hermf/temp/ESEF-conf-report.xlsx
TESTCASESINDEXFILE=$TESTCASESROOT
ARELLECMDLINESRC=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src/arelleCmdLine.py
PYTHON=python3.9
PLUGINS='validate/ESEF'
PACKAGES=/Users/hermf/Documents/mvsl/projects/ESMA/esef_taxonomy_2020.zip 
FILTER='(?!arelle:testcaseDataUnexpected)'
FORMULA=none
FORMULA=run

$PYTHON $ARELLECMDLINESRC --file "$TESTCASESINDEXFILE" --plugins $PLUGINS --packages $PACKAGES --disclosureSystem esef --logCodeFilter $FILTER --formula $FORMULA --validate --csvTestReport "$OUTPUTCSVFILE" --testcaseResultsCaptureWarnings --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
