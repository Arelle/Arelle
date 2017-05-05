#!/bin/bash

rm -f /users/hermf/temp/UTRunit* /users/hermf/temp/UTRstr*
ARELLEDIR=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src
PYTHONPATH=$ARELLEDIR

# Run UTR Units tests

TESTCASESROOT=/Users/hermf/Documents/mvsl/projects/XBRL.org/conformance-lrr/trunk/conf/utr/2013-05-17
OUTPUTLOGFILE=/users/hermf/temp/UTRunit-log.txt
OUTPUTERRFILE=/users/hermf/temp/UTRunit-err.txt
OUTPUTCSVFILE=/users/hermf/temp/UTRunit-report.csv
TESTCASESINDEXFILE=$TESTCASESROOT/100-utr.xml

python3.5 -m arelle.CntlrCmdLine --file "$TESTCASESINDEXFILE" --validate --utr --utrUrl $TESTCASESROOT/../../../schema/utr/utr.xml --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"

# Run UTR Structure tests

TESTCASESROOT=/users/hermf/Documents/mvsl/projects/XBRL.org/conformance-lrr/trunk/conf/utr-structure
OUTPUTLOGFILE=/users/hermf/temp/UTRstr-log
OUTPUTERRFILE=/users/hermf/temp/UTRstr-err
OUTPUTCSVFILE=/users/hermf/temp/UTRstr-report
TESTCASESINDEXFILE=$TESTCASESROOT/index.xml

python3.5 -m arelle.CntlrCmdLine --file "$TESTCASESINDEXFILE" --validate --utr --utrUrl $TESTCASESROOT/utr-for-structure-conformance-tests.xml --csvTestReport "${OUTPUTCSVFILE}.csv" --logFile "${OUTPUTLOGFILE}.txt" 2>  "${OUTPUTERRFILE}.txt"

MalformedUTRs=`find ${TESTCASESROOT}/malformed-utrs -name \*.xml -exec basename -s .xml {} \;`
for f in $MalformedUTRs 
do
  python3.5 -m arelle.CntlrCmdLine --file $TESTCASESROOT/tests/05-malformed-utrs/${f}.xml --validate --utr --utrUrl $TESTCASESROOT/malformed-utrs/${f}.xml --csvTestReport "${OUTPUTCSVFILE}-${f}.csv" --logFile "${OUTPUTLOGFILE}_${f}.txt" 2>  "${OUTPUTERRFILE}_${f}.txt"
done
