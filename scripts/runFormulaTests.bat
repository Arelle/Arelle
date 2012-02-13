rem Run XBRL Formula Conformance Suite tests

@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-formula\trunk

@set TESTCASESINDEXFILE=%TESTCASESROOT%\index.xml

@set OUTPUTLOGFILE=c:\temp\Formula-test-log.txt

@set OUTPUTCSVFILE=c:\temp\Formula-test-report.csv

@set ARELLEDIR=C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\ArelleProject\arelle

@set PYTHONDIR=c:\python32
@set PYTHONPATH=..

"%PYTHONDIR%\python" -marelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --validate --csvTestReport "%OUTPUTCSVFILE%" --logFile "%OUTPUTLOGFILE%"
