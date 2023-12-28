import os
import urllib.request
import zipfile

from pathlib import Path
from shutil import rmtree

from tests.integration_tests.scripts.script_util import run_arelle, parse_args, validate_log_file, assert_result, prepare_logfile

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Extract and validate Japanese IXDS instance.",
    cache=this_file.with_suffix(".zip").name,
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
report_zip_url = "https://arelle-public.s3.amazonaws.com/ci/packages/JapaneseXBRLReport.zip"

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
        "--saveInstance"
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
        "--file", str(extracted_path),
    ],
    offline=arelle_offline,
    logFile=arelle_log_file2,
)

print(f"Checking for log errors: {arelle_log_file1}")
errors += validate_log_file(arelle_log_file1)
print(f"Checking for log errors: {arelle_log_file2}")
errors += validate_log_file(arelle_log_file2)

assert_result(errors)

print("Cleaning up")
rmtree(working_directory / 'japan_ixds' / 'report')
os.unlink(working_directory / 'japan_ixds' / 'report.zip')
