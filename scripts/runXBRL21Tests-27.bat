rem Run XBRL 2.1 Conformance Suite tests

@set ARELLEDIR=C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\ArelleProject\arelle

@set PYTHONDIR=c:\python27
@set PYTHONPATH=..\build\svr-2.7

rem work off local SVN checked out files (inferring decimals)
@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance\trunk
@set TESTCASESINDEXFILE=%TESTCASESROOT%\xbrl.xml

@set OUTPUTLOGFILE=c:\temp\XBRL21-current-log.txt
@set OUTPUTCSVFILE=c:\temp\XBRL21-current-report.csv

"%PYTHONDIR%\python" -marelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --validate --calcDecimals --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1

rem work off published CR4 test suite (inferring precision)
@set TESTCASESINDEXFILE=http://www.xbrl.org/2008/XBRL-CONF-CR4-2008-07-02.zip/xbrl.xml

@set OUTPUTLOGFILE=c:\temp\XBRL21-CR4-log.txt
@set OUTPUTCSVFILE=c:\temp\XBRL21-CR4-report.csv

"%PYTHONDIR%\python" -marelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --validate --calcPrecision --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
