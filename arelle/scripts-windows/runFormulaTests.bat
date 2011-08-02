rem Run XBRL Formula Conformance Suite tests

rem Please edit to change the output log and output csv file locations

@set TESTCASESINDEXFILE=http://www.xbrl.org/Specification/formula/REC-2009-06-22/conformance/Formula-CONF-REC-PER-Errata-2011-03-16.zip/index.xml

@set OUTPUTLOGFILE=c:\temp\Formula-test-log.txt

@set OUTPUTCSVFILE=c:\temp\Formula-test-report.csv

@set ARELLE=c:\Program Files\Arelle\arelleCmdLine.exe

"%ARELLE%" --file "%TESTCASESINDEXFILE%" --validate --csvTestReport "%OUTPUTCSVFILE%" --logFile "%OUTPUTLOGFILE%"
