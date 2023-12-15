#!/bin/sh

# Download samples:
curl -LOs https://arelle-public.s3.amazonaws.com/ci/packages/IXBRLViewerSamples.zip
# Unzip report:
unzip -d IXBRLViewerSamples IXBRLViewerSamples.zip
# Generate ixbrl viewer
$1 \
  --internetConnectivity=offline \
  --plugins="ixbrl-viewer" \
  -f IXBRLViewerSamples/samples/src/ixds-test/document1.html \
  --save-viewer viewer.html \
  --logFile ixbrl-viewer_cli.testlog.xml

if [[ ! -f ixbrl-viewer_cli.testlog.xml ]] ; then
    >&2 echo "Output log was not generated"
    exit 1
fi
if grep -q "level=\"error\"" ixbrl-viewer_cli.testlog.xml; then
    >&2 echo "Output log contains errors"
    exit 1
fi
if [[ ! -f viewer.html ]] ; then
    >&2 echo "Viewer was not generated"
    exit 1
fi

# Cleanup
rm -f viewer.html
rm -f ixbrlviewer.js
rm -f IXBRLViewerSamples.zip
rm -r IXBRLViewerSamples
rm -f ixbrl-viewer_cli.testlog.xml
