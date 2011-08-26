rem Export CSV from XBRL Instance with Dimensions 

@set XBRLINSTANCEROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\EuroFiling\CSV converter\taxonomy2\taxonomy\eu

@set INSTANCEFILE=%XBRLINSTANCEROOT%\instance.xbrl

@set OUTPUTLOGFILE=%XBRLINSTANCEROOT%\conversion-log.txt

@set OUTPUTCSVFILE=%XBRLINSTANCEROOT%\converted-instance.csv

rem to run from installer version use this
@set ARELLE=c:\Progra~1\Arelle\arelleCmdLine.exe

rem to run from source use this
rem @set ARELLE=c:\python32\python -marelle.CntlrCmdLine
rem @set PYTHONPATH=..

%ARELLE% --file "%INSTANCEFILE%" --csvFactCols "Label unitRef Dec Value EntityScheme EntityIdentifier Period Dimensions" --csvFacts "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1

rem %ARELLE% --file "%INSTANCEFILE%" --csvPre "%XBRLINSTANCEROOT%\converted-pre.csv" 1>  "%OUTPUTLOGFILE%" 2>&1