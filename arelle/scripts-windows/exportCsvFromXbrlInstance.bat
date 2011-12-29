rem Export CSV from XBRL Instance with Dimensions 

rem Please edit or adapt to location of instance documents, output files, and Arelle installation

@set XBRLINSTANCEROOT=C:\Users\Herm Fischer\Documents\mvsl\projects\EuroFiling\CSV converter\taxonomy2\taxonomy\eu

@set INSTANCEFILE=%XBRLINSTANCEROOT%\instance.xbrl

@set OUTPUTLOGFILE=%XBRLINSTANCEROOT%\conversion-log.txt

@set OUTPUTCSVFILE=%XBRLINSTANCEROOT%\converted-instance.csv

@set ARELLE=c:\Program Files\Arelle\arelleCmdLine.exe


"%ARELLE%" --file "%INSTANCEFILE%" --csvFactCols "Label unitRef Dec Value EntityScheme EntityIdentifier Period Dimensions" --csvFacts "%OUTPUTCSVFILE%" 1>  "%OUTPUTLOGFILE%" 2>&1
