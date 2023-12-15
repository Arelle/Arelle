#!/bin/sh

# Download report:
curl -LOs https://arelle-public.s3.amazonaws.com/ci/packages/JapaneseXBRLReport.zip
# Unzip report:
unzip -d JapaneseXBRLReport JapaneseXBRLReport.zip
# Extract instance:
$1 \
  --internetConnectivity=offline \
  --plugins="inlineXbrlDocumentSet" \
  --saveInstance --file JapaneseXBRLReport/manifest.xml \
  --logFile japan_ixds.testlog.xml
# Verify no schemaImportMissing errors in extracted doc:
$1 \
  --internetConnectivity=offline \
  --validate \
  --file JapaneseXBRLReport/tse-acedjpfr-19990-2023-06-30-01-2023-08-18_extracted.xbrl \
  --logFile japan_ixds.testlog.xml

if [[ ! -f japan_ixds.testlog.xml ]] ; then
    >&2 echo "Output log was not generated"
    exit 1
fi
if grep -q "level=\"error\"" japan_ixds.testlog.xml; then
    >&2 echo "Output log contains errors"
    exit 1
fi

# Cleanup
rm -r JapaneseXBRLReport
rm -f JapaneseXBRLReport.zip
rm -f japan_ixds.testlog.xml
