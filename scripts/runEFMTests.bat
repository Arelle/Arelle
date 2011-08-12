rem Run SEC Edgar Filer Manual (EFM) Conformance Suite tests

@set TESTCASESROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\SEC\Local.Conformance\conformance\Private\Formula\Extension-Conformance\root\efm-16-110225\conf

@set TESTCASESINDEXFILE=%TESTCASESROOT%\testcases.xml

@set OUTPUTLOGFILE=c:\temp\EFM-test-log.txt

@set OUTPUTCSVFILE=c:\temp\EFM-test-report.csv

@set ARELLEDIR=C:\Users\Herm Fischer\Documents\mvsl\projects\Arelle\ArelleProject\arelle

@set PYTHONDIR=c:\python31
@set PYTHONPATH=..

"%PYTHONDIR%\python" -m arelle.CntlrCmdLine --file "%TESTCASESINDEXFILE%" --efm --utr --validate --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
