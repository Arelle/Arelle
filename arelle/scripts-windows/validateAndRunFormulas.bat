rem Example script for validation and formula

rem Validate 2.1, XDT, and calculation linkbase inferring decimals

"c:\Progra~1\Arelle\arelleCmdLine.exe" --file "http://www.xbrlsite.com/Demos/HR2883/CFS-101-FY2008-Hawaii_Auto.xml"  --validate --calcDecimals --logFile "c:\temp\test-log1.txt" 2>  "c:\temp\test-err1.txt"

rem same, but import the formulas linkbase and trace
rem     Expression Results, Assertion Counts
rem     Variable expression results and filter winnowing

"c:\Progra~1\Arelle\arelleCmdLine.exe" --file "http://www.xbrlsite.com/Demos/HR2883/CFS-101-FY2008-Hawaii_Auto.xml"  --import "http://www.xbrlsite.com/Demos/HR2883/CFS-101-formula.xml" --validate --calcDecimals --formulaVarSetExprResult --formulaAsserResultCounts --formulaVarExpressionResult --formulaVarFiltersResult --logFile "c:\temp\test-log2.txt" 2>  "c:\temp\test-err2.txt"
