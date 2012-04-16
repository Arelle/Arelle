rem Report all tests including spec reference column

@set ARELLEDIR=C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\ArelleProject\arelle

@set PYTHONDIR=c:\python32
@set PYTHONPATH=..

@set OUTPUTLOGFILE=c:\temp\testcases-current-log.txt
@set CSVCOLS="Index Testcase ID Name Reference ReadMeFirst Expected"

rem 2.1 SVN checked out files (inferring decimals)
@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance\trunk
@set TESTCASESINDEXFILE=%TESTCASESROOT%\xbrl.xml
@set OUTPUTCSVFILE=c:\temp\testcases-base-spec.csv

"%PYTHONDIR%\python" -marelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --testReportCols %CSVCOLS% --testReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1

@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-dimensions\trunk\conf
@set TESTCASESINDEXFILE=%TESTCASESROOT%\xdt.xml
@set OUTPUTCSVFILE=c:\temp\testcases-XDT.csv

"%PYTHONDIR%\python" -marelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --testReportCols %CSVCOLS% --testReport "%OUTPUTCSVFILE%" 1>>  "%OUTPUTLOGFILE%" 2>>&1

@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-formula\trunk
@set TESTCASESINDEXFILE=%TESTCASESROOT%\index.xml
@set OUTPUTCSVFILE=c:\temp\testcases-formula.csv

"%PYTHONDIR%\python" -marelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --testReportCols %CSVCOLS% --testReport "%OUTPUTCSVFILE%" 1>>  "%OUTPUTLOGFILE%" 2>>&1

@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-formula\trunk\function-registry
@set TESTCASESINDEXFILE=%TESTCASESROOT%\functionregistry.xml
@set OUTPUTCSVFILE=c:\temp\testcases-function.csv

"%PYTHONDIR%\python" -marelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --testReportCols %CSVCOLS% --testReport "%OUTPUTCSVFILE%" 1>>  "%OUTPUTLOGFILE%" 2>>&1

@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\SEC\efm-18-120228\conf
@set TESTCASESINDEXFILE=%TESTCASESROOT%\testcases.xml
@set OUTPUTCSVFILE=c:\temp\testcases-EFM.csv

"%PYTHONDIR%\python" -marelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --testReportCols %CSVCOLS% --testReport "%OUTPUTCSVFILE%" 1>>  "%OUTPUTLOGFILE%" 2>>&1
