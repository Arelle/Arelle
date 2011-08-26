rem Run XBRL Dimensions (XDT) Conformance Suite tests

@set TESTCASEROOT=C:\temp\editaxonomy20110314

@set TESTCASEFILE=%TESTCASEROOT%\testcase.xml

@set OUTPUTLOGFILE=%TESTCASEROOT%\test-log.txt

@set OUTPUTCSVFILE=%TESTCASEROOT%\test-report.csv

@set ARELLEPROG="C:\Program Files\Arelle\arelleCmdLine.exe"

%ARELLEPROG% --file "%TESTCASEFILE%" --validate --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
