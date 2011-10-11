rem Run XBRL 2.1 Conformance Suite tests

rem Please edit to change the output log and output csv file locations

@set TESTCASESINDEXFILE=http://www.xbrl.org/2008/XBRL-CONF-CR4-2008-07-02.zip/xbrl.xml

@set OUTPUTLOGFILE=c:\temp\XBRL21-test-log.txt

@set OUTPUTCSVFILE=c:\temp\XBRL21-test-report.csv

@set ARELLE=c:\Program Files\Arelle\arelleCmdLine.exe

"%ARELLE%" --file "%TESTCASESINDEXFILE%" --validate --calcDecimals --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
