rem Export CSV from XBRL Instance with Dimensions 

@set XBRLINSTANCEROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\EuroFiling\CSV converter

@set INSTANCEFILE=%XBRLINSTANCEROOT%\combinationOfCubesCase1Segment.xbrl

@set OUTPUTLOGFILE=%XBRLINSTANCEROOT%\conversion-log.txt

@set OUTPUTCSVFILE=%XBRLINSTANCEROOT%\converted-instance.csv

@set ARELLE=c:\python32\python -marelle.CntlrCmdLine
@set PYTHONPATH=.
rem @set ARELLE=c:\Program Files\Arelle\arelleCmdLine.exe

%ARELLE% --file "%INSTANCEFILE%" --csvFactCols "Label unitRef Dec Value EntityScheme EntityIdentifier Period Dimensions" --csvFacts "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
