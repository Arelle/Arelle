rem Run ESMA ESEF conformance tests

@set TESTCASESINDEX=Z:\Documents\mvsl\projects\ESMA\conf\esef_conformanceSuite_2020-02-09\index.xml

del/q Z:\temp\ESEF-conf-*

@set OUTPUTLOGFILE=Z:\temp\ESEF-conf-log.txt

@set OUTPUTERRFILE=Z:\temp\ESEF-conf-err.txt

@set OUTPUTCSVFILE=Z:\temp\ESEF-conf-report.xlsx

@set ARELLEDIR=Z:\Documents\mvsl\projects\Arelle\ArelleProject\src

@set PYTHONDIR=c:\python35
@set PYTHONPATH=$ARELLEDIR

@set PLUGINS='validate/ESEF'
@set PACKAGES=/Users/hermf/Documents/mvsl/projects/ESMA/esef_taxonomy_2019.zip 
@set FILTER='(?!ESEF.3.2.1.extensionTaxonomyElementNameDoesNotFollowLc3Convention|ESEF.3.4.5.missingLabelForRoleInReportLanguage|arelle:testcaseDataUnexpected)'
@set FORMULA=none


"%PYTHONDIR%\python" arelleCmdLine.py  --file "%TESTCASESINDEX%" --plugins %PLUGINS% --packages %PACKAGES% --disclosureSystem esef  --logCodeFilter %FILTER% --formula %FORMULA% --validate --csvTestReport "%OUTPUTCSVFILE%" --logFile "%OUTPUTLOGFILE%" 2>  "%OUTPUTERRFILE%"



