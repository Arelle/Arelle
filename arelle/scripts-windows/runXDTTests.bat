rem Run XBRL Dimensions (XDT) Conformance Suite tests

rem Please edit to change the output log and output csv file locations

@set TESTCASESINDEXFILE=http://www.xbrl.org/2009/XDT-CONF-CR4-2009-10-06.zip/xdt.xml

@set OUTPUTLOGFILE=c:\temp\XDT-test-log.txt

@set OUTPUTCSVFILE=c:\temp\XDT-test-report.csv

@set ARELLE=c:\Program Files\Arelle\arelleCmdLine.exe

"%ARELLE%" --file "%TESTCASESINDEXFILE%" --validate --infoset --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
