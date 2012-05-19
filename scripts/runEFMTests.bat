rem Run SEC Edgar Filer Manual (EFM) Conformance Suite tests

rem @set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\SEC\efm-18-111122\conf
@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\SEC\efm-18-120228\conf

@set TESTCASESINDEXFILE=%TESTCASESROOT%\testcases.xml

@set OUTPUTLOGFILE=c:\temp\EFM-test-log.txt

@set OUTPUTERRFILE=c:\temp\EFM-test-err.txt

@set OUTPUTCSVFILE=c:\temp\EFM-test-report.csv

@set ARELLEDIR=C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\ArelleProject\arelle

@set PYTHONDIR=c:\python32
@set PYTHONPATH=..

"%PYTHONDIR%\python" -m arelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --efm --validate --csvTestReport "%OUTPUTCSVFILE%" --logFile "%OUTPUTLOGFILE%" 2>  "%OUTPUTERRFILE%"
