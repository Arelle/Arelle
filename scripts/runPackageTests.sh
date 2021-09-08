#!/bin/bash

# Run Taxonomy Package tests

TESTCASESROOT=/Users/hermf/Documents/mvsl/projects/XBRL.org/taxonomy-package-conformance
rm -fr /users/hermf/temp/Package-test-*
OUTPUTLOGFILE=/users/hermf/temp/Package-test-log.txt
OUTPUTERRFILE=/users/hermf/temp/Package-test-err.txt
OUTPUTCSVFILE=/users/hermf/temp/Package-test-report.csv
TESTCASESINDEXFILE="$TESTCASESROOT/index.xml"

ARELLEDIR=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src

# standard approach doesn't work because plugins load differently from instances

# python3.9 ${ARELLEDIR}/arelleCmdLine.py --file "$TESTCASESINDEXFILE" --validate --csvTestReport "$OUTPUTCSVFILE"  --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"

PACKAGES=`ls -1 ${TESTCASESROOT}/*.zip`

for PACKAGE in $PACKAGES
  do
  PACKAGEFILE=$(basename $PACKAGE)
  echo Package: $PACKAGEFILE >> $OUTPUTLOGFILE
  python3.9 ${ARELLEDIR}/arelleCmdLine.py --file "[]" --packages ${PACKAGE} --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
  echo "" >> $OUTPUTLOGFILE
  done
