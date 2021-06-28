#!/bin/bash

LOGDIR=/Users/hermf/temp

ARELLEDIR=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src
PYTHON=python3.9


TESTSDIR=/Users/hermf/Documents/mvsl/projects/XBRL.org/conformance-lrr/trunk/conf

rm -f ${LOGDIR}/UTRunit* ${LOGDIR}/UTRstr*

# Run UTR Units tests

TESTCASESROOT=${TESTSDIR}/utr/2013-05-17
OUTPUTLOGFILE=${LOGDIR}/UTRunit-log.txt
OUTPUTERRFILE=${LOGDIR}/UTRunit-err.txt
OUTPUTCSVFILE=${LOGDIR}/UTRunit-report.csv
TESTCASESINDEXFILE=$TESTCASESROOT/100-utr.xml

$PYTHON ${ARELLEDIR}/arelleCmdLine.py --file "$TESTCASESINDEXFILE" --validate --utr --utrUrl ${TESTCASESROOT}/../../../schema/utr/utr.xml --csvTestReport "$OUTPUTCSVFILE" --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"

# Run UTR Structure tests

TESTCASESROOT=${TESTSDIR}/utr-structure
OUTPUTLOGFILE=${LOGDIR}/UTRstr-log
OUTPUTERRFILE=${LOGDIR}/UTRstr-err
OUTPUTCSVFILE=${LOGDIR}/UTRstr-report
TESTCASESINDEXFILE=$TESTCASESROOT/index.xml

$PYTHON ${ARELLEDIR}/arelleCmdLine.py --file "$TESTCASESINDEXFILE" --validate --utr --utrUrl $TESTCASESROOT/utr-for-structure-conformance-tests.xml --csvTestReport "${OUTPUTCSVFILE}.csv" --logFile "${OUTPUTLOGFILE}.txt" 2>  "${OUTPUTERRFILE}.txt"

MalformedUTRs=`find ${TESTCASESROOT}/malformed-utrs -name \*.xml -exec basename -s .xml {} \;`
for f in $MalformedUTRs 
do
  $PYTHON ${ARELLEDIR}/arelleCmdLine.py --file ${TESTCASESROOT}/tests/05-malformed-utrs/${f}.xml --validate --utr --utrUrl $TESTCASESROOT/malformed-utrs/${f}.xml --csvTestReport "${OUTPUTCSVFILE}-${f}.csv" --logFile "${OUTPUTLOGFILE}_${f}.txt" 2>  "${OUTPUTERRFILE}_${f}.txt"
done
