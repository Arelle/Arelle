from __future__ import annotations

import io
import os
import urllib.request
import zipfile
from pathlib import Path
from shutil import rmtree

import regex

from arelle.RuntimeOptions import RuntimeOptions
from arelle.api.Session import Session
from arelle.logging.handlers.StructuredMessageLogHandler import StructuredMessageLogHandler
from tests.integration_tests.integration_test_util import get_s3_uri
from tests.integration_tests.scripts.script_util import parse_args, assert_result, prepare_logfile, validate_log_xml, validate_log_file

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Extract and validate IXDS instance using Arelle's Python API.",
    arelle=False,
    cache='japan_ixds.zip',
    cache_version_id='PiPwS2lDqbtid8K3dbUlF0m.KIa5Jm8E',
)
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)
arelle_log_file1 = prepare_logfile(test_directory, this_file, name="save")
arelle_log_file2 = prepare_logfile(test_directory, this_file, name="validate")
report_zip_path = test_directory / 'report.zip'
manifest_path = report_zip_path / "manifest.xml"
extracted_zip_path = test_directory / "extracted.zip"
extracted_instance_path = test_directory / "tse-acedjpfr-19990-2023-06-30-01-2023-08-18_extracted.xbrl"
extracted_final_path = report_zip_path / "tse-acedjpfr-19990-2023-06-30-01-2023-08-18_extracted.xbrl"
report_zip_url = get_s3_uri(
    'ci/packages/JapaneseXBRLReport.zip',
    version_id='M7vTPhHhir1rOm7nSMPiCGcbCA0ksObh'
)

print(f"Downloading report: {report_zip_url}")
urllib.request.urlretrieve(report_zip_url, report_zip_path)

print(f"Extracting instance: {manifest_path}")
with io.BytesIO() as extracted_stream:
    with open(report_zip_path, 'rb') as stream:
        options = RuntimeOptions(
            entrypointFile=str(manifest_path),
            internetConnectivity='offline' if arelle_offline else 'online',
            keepOpen=True,
            logFile=str(arelle_log_file1),
            logFormat="[%(messageCode)s] %(message)s - %(file)s",
            pluginOptions={
                'deduplicateIxbrlFacts': 'consistent-pairs',
                'saveTargetFiling': True,
                'saveTargetInstance': True,
            },
            plugins='inlineXbrlDocumentSet',
            strictOptions=False,
        )
        with Session() as session:
            session.run(
                options,
                sourceZipStream=stream,
                responseZipStream=extracted_stream,
            )
            log_xml1 = session.get_logs('xml')
    print(f"Writing extracted stream to zip: {extracted_zip_path}")
    with open(extracted_zip_path, 'wb') as extracted_file:
        extracted_file.write(extracted_stream.getvalue())
print(f"Extracting instance document: {extracted_instance_path}")
with zipfile.ZipFile(extracted_zip_path, "r") as zip_ref:
    zip_ref.extractall(test_directory)
print(f"Copying instance document to report zip: {extracted_instance_path}")
with zipfile.ZipFile(report_zip_path, "a") as zip_ref:
    zip_ref.write(
        extracted_instance_path,
        arcname=extracted_instance_path.name
    )
with open(report_zip_path, 'rb') as stream:
    # Verify no schemaImportMissing errors in extracted doc
    print(f"Validating instance: {extracted_final_path}")
    options = RuntimeOptions(
        entrypointFile=str(extracted_final_path),
        internetConnectivity='offline' if arelle_offline else 'online',
        keepOpen=True,
        logFile=str(arelle_log_file2),
        logFormat="[%(messageCode)s] %(message)s - %(file)s",
        strictOptions=False,
        validate=True,
        validateDuplicateFacts='consistent',
    )
    with Session() as session:
        session.run(options, sourceZipStream=stream)
        log_xml2 = session.get_logs('xml')

print(f"Checking for log errors: {arelle_log_file1}")
expected_infos = {
    regex.compile(r'^\[info:deduplicatedFact] Duplicate fact was excluded'): 33,
}
errors += validate_log_xml(log_xml1, expected_results={"info": expected_infos})

print(f"Checking for log errors: {arelle_log_file2}")
expected_warnings = {
    regex.compile(r'^\[arelle:duplicateFacts] Duplicate fact set '): 0,
}
errors += validate_log_xml(log_xml2, expected_results={"warning": expected_warnings})

assert_result(errors)

print("Cleaning up")
try:
    os.unlink(working_directory / 'python_api_instance_extraction' / 'extracted.zip')
    os.unlink(working_directory / 'python_api_instance_extraction' / 'report.zip')
    os.unlink(working_directory / 'python_api_instance_extraction' / 'tse-acedjpfr-19990-2023-06-30-01-2023-08-18_extracted.xbrl')
except PermissionError as exc:
    print(f"Failed to cleanup test files: {exc}")
