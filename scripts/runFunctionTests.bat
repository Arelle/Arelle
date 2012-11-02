rem Run XBRL Function Registry Conformance Suite tests

@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-formula\trunk\function-registry

@set TESTCASESINDEXFILE=%TESTCASESROOT%\functionregistry.xml

@set OUTPUTLOGFILE=c:\temp\Function-test-log.txt

@set OUTPUTCSVFILE=c:\temp\Function-test-report.csv

@set ARELLEDIR=C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\ArelleProject\arelle

@set PYTHONDIR=c:\python32
@set PYTHONPATH=..

"%PYTHONDIR%\python" -marelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --validate --csvTestReport "%OUTPUTCSVFILE%" --logFile "%OUTPUTLOGFILE%"
