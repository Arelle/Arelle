rem Run XBRL Function Registry Conformance Suite tests

rem Please edit to change the output log and output csv file locations

@set TESTCASESINDEXFILE=http://xbrl.org/functionregistry/functionregistry.xml

@set OUTPUTLOGFILE=c:\temp\Function-test-log.txt

@set OUTPUTCSVFILE=c:\temp\Function-test-report.csv

@set ARELLE=c:\Program Files\Arelle\arelleCmdLine.exe

"%ARELLE%" --file "%TESTCASESINDEXFILE%" --validate --csvTestReport "%OUTPUTCSVFILE%" --logFile "%OUTPUTLOGFILE%"
