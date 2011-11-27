rem Run SEC Edgar Filer Manual (EFM) Conformance Suite tests

rem Please edit to change the output log and output csv file locations

@set TESTCASESINDEXFILE=http://sec.gov/info/edgar/ednews/efmtest/efm-18-111021.zip/28-111021/conf/testcases.xml

@set OUTPUTLOGFILE=c:\temp\EFM-test-log.txt

@set OUTPUTCSVFILE=c:\temp\EFM-test-report.csv

@set ARELLE=c:\Program Files\Arelle\arelleCmdLine.exe

"%ARELLE%" --file "%TESTCASESINDEXFILE%" --efm --validate --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
