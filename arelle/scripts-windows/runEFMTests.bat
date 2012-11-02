rem Run SEC Edgar Filer Manual (EFM) Conformance Suite tests


@set TESTCASESINDEXFILE=http://sec.gov/info/edgar/ednews/efmtest/efm-19-120614.zip/efm-19-120614/conf/testcases.xml

@set OUTPUTLOGFILE=c:\temp\EFM-test-log.txt

@set OUTPUTCSVFILE=c:\temp\EFM-test-report.csv

@set ARELLE=c:\Program Files\Arelle\arelleCmdLine.exe

"%ARELLE%" --file "%TESTCASESINDEXFILE%" --efm --validate --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
