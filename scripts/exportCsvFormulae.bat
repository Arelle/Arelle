rem Export CSV Formulae 

@set XBRLINSTANCEROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\EuroFiling\CSV converter\taxonomy2\taxonomy\eu

@set INSTANCEFILE=%XBRLINSTANCEROOT%\instance.xbrl

@set OUTPUTLOGFILE=%XBRLINSTANCEROOT%\csv-formulae-log.txt

@set OUTPUTCSVFILE=%XBRLINSTANCEROOT%\csv-formulae.csv

rem to run from installer version use this
rem @set ARELLE=c:\Progra~1\Arelle\arelleCmdLine.exe

rem to run from source use this
@set ARELLE=c:\python32\python -marelle.CntlrCmdLine
@set PYTHONPATH=..

%ARELLE% --file "%INSTANCEFILE%" --csvFormulae "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
