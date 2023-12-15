@REM Download report:
curl "-LOs" "https://arelle-public.s3.amazonaws.com/ci/packages/JapaneseXBRLReport.zip"
@REM Unzip report:
7z x JapaneseXBRLReport.zip -o"JapaneseXBRLReport" -aoa
set ARELLE_CMD=%~1
@REM Extract instance:
%ARELLE_CMD%^
    "--internetConnectivity=offline"^
    "--plugin" "inlineXbrlDocumentSet"^
    "--saveInstance" "--file" "JapaneseXBRLReport\manifest.xml"^
    "--logFile" "japan_ixds.testlog.xml"
@REM Validate instance
%ARELLE_CMD%^
    "--internetConnectivity=offline"^
    "--validate"^
    "--file" "JapaneseXBRLReport\tse-acedjpfr-19990-2023-06-30-01-2023-08-18_extracted.xbrl"^
    "--logFile" "japan_ixds.testlog.xml"

IF NOT EXIST "japan_ixds.testlog.xml" (
  echo "Output log was not generated" 1>&2
  EXIT "1"
)
>nul find "level=""error""" "japan_ixds.testlog.xml" && (
  echo "Output log contains errors" 1>&2
  EXIT "1"
)

@REM Cleanup
DEL /S /Q "JapaneseXBRLReport"
DEL  "JapaneseXBRLReport.zip"
DEL  "japan_ixds.testlog.xml"
