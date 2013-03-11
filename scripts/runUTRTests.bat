@rem Run UTR units tests

@set CONFROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-lrr\trunk\conf\utr\2013-02-28

@set FILENAME=index.xml
@set UTR=..\..\..\schema\utr\2013-02-28\utr.xml

@set PYTHONDIR=c:\python32
@set PYTHONPATH=..

@set OUTPUTLOGFILE=c:\temp\UTR-units-log.txt
@set OUTPUTCSVFILE=c:\temp\UTR-units-report.csv

"%PYTHONDIR%\python" -marelle.CntlrCmdLine --file "%CONFROOT%\%FILENAME%" --validate --utr --utrUrl "%CONFROOT%\%UTR%" --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1

@rem Run UTR structure tests

@set CONFROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\XBRL.org\conformance-lrr\trunk\conf\utr-structure

@set FILENAME=index.xml
@set UTR=utr-for-structure-conformance-tests.xml

@set PYTHONDIR=c:\python32
@set PYTHONPATH=..

@set OUTPUTLOGFILE=c:\temp\UTR-str-log.txt
@set OUTPUTCSVFILE=c:\temp\UTR-str-report.csv

"%PYTHONDIR%\python" -marelle.CntlrCmdLine --file "%CONFROOT%\%FILENAME%" --validate --utr --utrUrl "%CONFROOT%\%UTR%" --csvTestReport "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1


  