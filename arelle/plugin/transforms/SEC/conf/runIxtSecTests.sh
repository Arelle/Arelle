#!/bin/bash

# re-generate arelle's formula-assertion-style testcase file from test.xml authoritative testcase file
java -jar saxon9.jar tests.xml extractTestcase.xsl  > testcase.xml

# to run from source
ARELLE="python3.9 ../../../../../arelleCmdLine.py"

# to run from cx-frozen build (prod)
#ARELLE=/xbrldata/deployment-arelle/release/arelleCmdLine

# remove old log files
rm -f ~/temp/ixt-sec*

# run test cases
$ARELLE --plugins transforms/SEC -f testcase.xml -v --logFile ~/temp/ixt-sec.log --csvTestReport ~/temp/ixt-sec.xlsx
