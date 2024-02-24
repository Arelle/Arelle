import os
import urllib.request
import zipfile
from pathlib import Path
from shutil import rmtree

import regex

from tests.integration_tests.integration_test_util import get_s3_uri
from tests.integration_tests.scripts.script_util import run_arelle, parse_args, validate_log_file, assert_result, prepare_logfile

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Extract and validate Japanese IXDS instance.",
    cache=this_file.with_suffix(".zip").name,
    cache_version_id='PiPwS2lDqbtid8K3dbUlF0m.KIa5Jm8E',
)
arelle_command = args.arelle
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)
arelle_log_file1 = prepare_logfile(test_directory, this_file, name="save")
arelle_log_file2 = prepare_logfile(test_directory, this_file, name="validate")
report_zip_path = test_directory / 'report.zip'
report_directory = test_directory / 'report'
manifest_path = report_directory / "manifest.xml"
extracted_path = report_directory / "tse-acedjpfr-19990-2023-06-30-01-2023-08-18_extracted.xbrl"
report_zip_url = get_s3_uri(
    'ci/packages/JapaneseXBRLReport.zip',
    version_id='M7vTPhHhir1rOm7nSMPiCGcbCA0ksObh'
)

print(f"Downloading report: {report_zip_url}")
urllib.request.urlretrieve(report_zip_url, report_zip_path)

print(f"Extracting report: {report_directory}")
with zipfile.ZipFile(report_zip_path, "r") as zip_ref:
    zip_ref.extractall(report_directory)

print(f"Extracting instance: {manifest_path}")
run_arelle(
    arelle_command,
    plugins=["inlineXbrlDocumentSet"],
    additional_args=[
        "--file", str(manifest_path),
        "--saveInstance",
        "--deduplicateIxbrlFacts", "consistent-pairs"
    ],
    offline=arelle_offline,
    logFile=arelle_log_file1,
)

# Verify no schemaImportMissing errors in extracted doc
print(f"Validating instance: {extracted_path}")
run_arelle(
    arelle_command,
    additional_args=[
        "--validate",
        "--validateDuplicateFacts", "consistent",
        "--file", str(extracted_path),
    ],
    offline=arelle_offline,
    logFile=arelle_log_file2,
)

print(f"Checking for log errors: {arelle_log_file1}")
expected_infos = {
    regex.compile(r'^\[info:deduplicatedFact] Duplicate fact was excluded'): 33,
}
errors += validate_log_file(arelle_log_file1, expected_results={"info": expected_infos})

print(f"Checking for log errors: {arelle_log_file2}")
expected_warnings = {
    regex.compile(r'^\[arelle:duplicateFacts] Duplicate fact set '): 0,
}
errors += validate_log_file(arelle_log_file2, expected_results={"warning": expected_warnings})

assert_result(errors)

print("Cleaning up")
rmtree(working_directory / 'japan_ixds' / 'report')
os.unlink(working_directory / 'japan_ixds' / 'report.zip')
