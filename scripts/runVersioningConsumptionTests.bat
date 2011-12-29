@rem Run Versioning consumption tests

@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-versioning\trunk\versioningReport

@set TESTCASESINDEXFILE=%TESTCASESROOT%\conf\consumption-testcases-index.xml

@set OUTPUTLOGFILE=%TESTCASESROOT%\conf\log-consumption-messages.txt

@set OUTPUTCSVFILE=c:\temp\consumptionTestReport.csv

@set ARELLEDIR=C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\ArelleProject\arelle

@set PYTHONDIR=c:\python31
@set PYTHONPATH=..

"%PYTHONDIR%\python" -m arelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --validate --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
