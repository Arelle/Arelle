#!/bin/bash

# Run ESMA ESEF conformance tests

TESTCASESROOT=/Users/hermf/Documents/mvsl/projects/ESMA/conf/esef_conformanceSuite_2020-02-09/index.xml

rm -f /users/hermf/temp/ESEF-conf-*
OUTPUTLOGFILE=/users/hermf/temp/ESEF-conf-log.txt
OUTPUTERRFILE=/users/hermf/temp/ESEF-conf-err.txt
OUTPUTCSVFILE=/users/hermf/temp/ESEF-conf-report.xlsx
TESTCASESINDEXFILE=$TESTCASESROOT
ARELLECMDLINESRC=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src/arelleCmdLine.py
PYTHON=python3.5
PLUGINS='validate/ESEF'
PACKAGES=/Users/hermf/Documents/mvsl/projects/ESMA/esef_taxonomy_2019.zip 
FILTER='(?!ESEF.3.2.1.extensionTaxonomyElementNameDoesNotFollowLc3Convention|ESEF.3.4.5.missingLabelForRoleInReportLanguage|arelle:testcaseDataUnexpected)'
FORMULA=none

$PYTHON $ARELLECMDLINESRC --file "$TESTCASESINDEXFILE" --plugins $PLUGINS --packages $PACKAGES --disclosureSystem esef --logCodeFilter $FILTER --formula $FORMULA --validate --csvTestReport "$OUTPUTCSVFILE" --testcaseResultsCaptureWarnings --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
