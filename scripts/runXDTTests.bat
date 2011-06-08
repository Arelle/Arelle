rem Run XBRL Dimensions (XDT) Conformance Suite tests

@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-dimensions\trunk\conf

@set TESTCASESINDEXFILE=%TESTCASESROOT%\xdt.xml

@set OUTPUTLOGFILE=c:\temp\XDT-test-log.txt

@set OUTPUTCSVFILE=c:\temp\XDT-test-report.csv

@set ARELLEDIR=C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\ArelleProject\arelle

@set PYTHONDIR=c:\python31
@set PYTHONPATH=..

"%PYTHONDIR%\python" -m arelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --validate --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
