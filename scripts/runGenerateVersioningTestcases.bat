@rem Run Versioning consumption and creation testcases and report generation

@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-versioning\trunk\versioningReport\conf\creation

@set EXCELINDEXFILE=%TESTCASESROOT%\0000-2000-index.xls

@set ARELLEDIR=C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\ArelleProject\arelle

@set PYTHONDIR=c:\python32
@set PYTHONPATH=..

"%PYTHONDIR%\python" -m arelle.CntlrGenVersReports --excelfile "%EXCELINDEXFILE%" --testfiledate "2011-03-01"
