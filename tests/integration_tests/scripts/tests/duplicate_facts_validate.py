from __future__ import annotations

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
    "Confirm duplicate facts trigger warnings as expected.",
)
arelle_command = args.arelle
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)

report_zip_path = test_directory / 'report.zip'
report_directory = test_directory / 'report'
report_path = report_directory / "report.xbrl"
report_zip_url = get_s3_uri(
    'ci/packages/fact_deduplication.zip',
    version_id='.KKcbsQZQx5jLzXilkFZlQ3OdwTuFaoe'
)

print(f"Downloading report: {report_zip_url}")
urllib.request.urlretrieve(report_zip_url, report_zip_path)

print(f"Extracting report: {report_directory}")
with zipfile.ZipFile(report_zip_path, "r") as zip_ref:
    zip_ref.extractall(report_directory)

test_cases: dict[str, dict[regex.Pattern[str], int]] = {
    'none': {},
    'inconsistent': {
        regex.compile(r'^\[arelle:duplicateFacts].*with inconsistent duplicate.*mock:StringIncomplete'): 1,
        regex.compile(r'^\[arelle:duplicateFacts].*with inconsistent duplicate.*mock:MonetaryInconsistent'): 1,
    },
    'consistent': {
        regex.compile(r'^\[arelle:duplicateFacts].*with consistent duplicate.*mock:StringComplete'): 1,
        regex.compile(r'^\[arelle:duplicateFacts].*with consistent duplicate.*mock:MonetaryComplete'): 1,
        regex.compile(r'^\[arelle:duplicateFacts].*with consistent duplicate.*mock:MonetaryConsistent'): 1,
    },
    'incomplete': {
        regex.compile(r'^\[arelle:duplicateFacts].*with incomplete duplicate.*mock:StringIncomplete'): 1,
        regex.compile(r'^\[arelle:duplicateFacts].*with incomplete duplicate.*mock:MonetaryConsistent'): 1,
        regex.compile(r'^\[arelle:duplicateFacts].*with incomplete duplicate.*mock:MonetaryInconsistent'): 1,
    },
    'complete': {
        regex.compile(r'^\[arelle:duplicateFacts].*with complete duplicate.*mock:StringComplete'): 1,
        regex.compile(r'^\[arelle:duplicateFacts].*with complete duplicate.*mock:MonetaryComplete'): 1,
    },
    'all': {
        regex.compile(r'^\[arelle:duplicateFacts].*with inconsistent\|consistent duplicate.*mock:StringComplete'): 1,
        regex.compile(r'^\[arelle:duplicateFacts].*with inconsistent\|consistent duplicate.*mock:StringIncomplete'): 1,
        regex.compile(r'^\[arelle:duplicateFacts].*with inconsistent\|consistent duplicate.*mock:MonetaryComplete'): 1,
        regex.compile(r'^\[arelle:duplicateFacts].*with inconsistent\|consistent duplicate.*mock:MonetaryConsistent'): 1,
        regex.compile(r'^\[arelle:duplicateFacts].*with inconsistent\|consistent duplicate.*mock:MonetaryInconsistent'): 1,
    },
}
for arg, expected_errors in test_cases.items():
    print(f"Running with argument: {arg}")
    log_file = prepare_logfile(test_directory, this_file, name=arg)
    run_arelle(
        arelle_command,
        additional_args=[
            "--file", str(report_path),
            "--validate",
            "--validateDuplicateFacts", arg
        ],
        offline=arelle_offline,
        logFile=log_file,
    )
    errors += validate_log_file(log_file, expected_results={"warning": expected_errors})
    assert_result(errors)

assert_result(errors)

print("Cleaning up")
rmtree(working_directory / 'duplicate_facts_validate' / 'report')
os.unlink(working_directory / 'duplicate_facts_validate' / 'report.zip')
