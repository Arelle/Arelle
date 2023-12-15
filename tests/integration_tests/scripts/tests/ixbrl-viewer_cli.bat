@REM Download samples:
curl "-LOs" "https://arelle-public.s3.amazonaws.com/ci/packages/IXBRLViewerSamples.zip"
@REM Unzip package:
7z x "IXBRLViewerSamples.zip" -o"IXBRLViewerSamples" -aoa
set ARELLE_CMD=%~1
@REM Generate ixbrl viewer
%ARELLE_CMD%^
    "--plugins=ixbrl-viewer"^
    "-f" "IXBRLViewerSamples\samples\src\ixds-test\document1.html"^
    "--save-viewer" "viewer.html"^
    "--logFile" "ixbrl-viewer_cli.testlog.xml"

IF NOT EXIST "ixbrl-viewer_cli.testlog.xml" (
  echo "Output log was not generated" 1>&2
  EXIT "1"
)
>nul find "level=""error""" "ixbrl-viewer_cli.testlog.xml" && (
  echo "Output log contains errors" 1>&2
  EXIT "1"
)
IF NOT EXIST "viewer.html" (
  echo "Viewer was not generated"
  exit "1"
)

@REM Cleanup
DEL  "viewer.html"
DEL  "ixbrlviewer.js"
DEL  "IXBRLViewerSamples.zip"
DEL /S /Q "IXBRLViewerSamples"
DEL  "ixbrl-viewer_cli.testlog.xml"
