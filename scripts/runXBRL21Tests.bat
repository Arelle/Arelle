rem Run XBRL 2.1 Conformance Suite tests

@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance\trunk

@set TESTCASESINDEXFILE=%TESTCASESROOT%\xbrl.xml

@set OUTPUTLOGFILE=c:\temp\XBRL21-test-log.txt

@set OUTPUTCSVFILE=c:\temp\XBRL21-test-report.csv

@set ARELLEDIR=C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\ArelleProject\arelle

@set PYTHONDIR=c:\python31
@set PYTHONPATH=..

"%PYTHONDIR%\python" -marelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --validate --calcDecimals --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
