@rem Run Versioning consumption tests

@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-versioning\trunk\versioningReport

rem uncomment for use-cases consumption test
rem @set TESTCASESINDEXFILE=%TESTCASESROOT%\conf\consumption-testcases-index.xml

rem uncomment for 1000-2000 consumption test
@set TESTCASESINDEXFILE=%TESTCASESROOT%\conf\creation\consumptionTestcasesIndex.xml

@set OUTPUTLOGFILE=%TESTCASESROOT%\conf\creation\logConsumptionMessages.txt

@set OUTPUTCSVFILE=c:\temp\consumptionTestReport.csv

@set ARELLEDIR=C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\ArelleProject\arelle

@set PYTHONDIR=c:\python31
@set PYTHONPATH=..

"%PYTHONDIR%\python" -m arelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --validate --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
