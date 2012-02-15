rem Run XBRL Dimensions (XDT) Conformance Suite tests

rem work off local SVN checked out files (inferring decimals)
@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-dimensions\trunk\conf
@set TESTCASESINDEXFILE=%TESTCASESROOT%\xdt.xml
@set OUTPUTLOGFILE=c:\temp\XDT-current-log.txt
@set OUTPUTCSVFILE=c:\temp\XDT-current-report.csv

@set ARELLEDIR=C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\ArelleProject\arelle

@set PYTHONDIR=c:\python27
@set PYTHONPATH=..\build\svr-2.7

"%PYTHONDIR%\python" -m arelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --validate --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1

rem work off published XDT files
@set TESTCASESINDEXFILE=http://www.xbrl.org/2009/XDT-CONF-CR4-2009-10-06.zip/xdt.xml
@set OUTPUTLOGFILE=c:\temp\XDT-CR4-log.txt
@set OUTPUTCSVFILE=c:\temp\XDT-CR4-report.csv

"%PYTHONDIR%\python" -m arelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --validate --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
