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
    'ci/packages/duplicate_facts_deduplication.zip',
    version_id='1NplyThuJkNOmSNITHdVuqE4MYtvDGOq'
)

print(f"Downloading report: {report_zip_url}")
urllib.request.urlretrieve(report_zip_url, report_zip_path)

print(f"Extracting report: {report_directory}")
with zipfile.ZipFile(report_zip_path, "r") as zip_ref:
    zip_ref.extractall(report_directory)

ALL_TESTCASES = {
    regex.compile(r'^\[info:deduplicatedFact].*mock:NonNumeric, value=COMPLETE, decimals=\(none\)'): 2,
    regex.compile(r'^\[info:deduplicatedFact].*mock:NonNumeric, value=COMPLETE 1, decimals=\(none\)'): 1,
    regex.compile(r'^\[info:deduplicatedFact].*mock:NonNumeric, value=COMPLETE 2, decimals=\(none\)'): 1,
    regex.compile(r'^\[info:deduplicatedFact].*mock:Numeric, value=100\.000000, decimals=INF'): 3,
    regex.compile(r'^\[info:deduplicatedFact].*mock:Numeric, value=200\.000000, decimals=INF'): 1,
    regex.compile(r'^\[info:deduplicatedFact].*mock:Date, value=2001-01-01, decimals=\(none\)'): 2,
    regex.compile(r'^\[info:deduplicatedFact].*mock:Date, value=2001-02-01, decimals=\(none\)'): 1,
    regex.compile(r'^\[info:deduplicatedFact].*mock:Day, value=---01, decimals=\(none\)'): 2,
    regex.compile(r'^\[info:deduplicatedFact].*mock:Day, value=---02, decimals=\(none\)'): 1,
    regex.compile(r'^\[info:deduplicatedFact].*mock:Month, value=--01, decimals=\(none\)'): 2,
    regex.compile(r'^\[info:deduplicatedFact].*mock:Month, value=--02, decimals=\(none\)'): 1,
    regex.compile(r'^\[info:deduplicatedFact].*mock:Year, value=2001, decimals=\(none\)'): 2,
    regex.compile(r'^\[info:deduplicatedFact].*mock:Year, value=2002, decimals=\(none\)'): 1,
    regex.compile(r'^\[info:deduplicatedFact].*mock:MonthDay, value=--01-01, decimals=\(none\)'): 2,
    regex.compile(r'^\[info:deduplicatedFact].*mock:MonthDay, value=--02-01, decimals=\(none\)'): 1,
    regex.compile(r'^\[info:deduplicatedFact].*mock:YearMonth, value=2001-01, decimals=\(none\)'): 2,
    regex.compile(r'^\[info:deduplicatedFact].*mock:YearMonth, value=2002-01, decimals=\(none\)'): 1,
}

test_cases: dict[str, dict[regex.Pattern[str], int]] = {
    'complete': {
        regex.compile(r'^\[info:deduplicatedInstance].*removing 26 fact'): 1,
    },
    'consistent-pairs': {
        regex.compile(r'^\[info:deduplicatedFact].*mock:Numeric, value=100\.000000, decimals=0'): 2,
        regex.compile(r'^\[info:deduplicatedFact].*mock:Numeric, value=100\.100000, decimals=1'): 2,
        regex.compile(r'^\[info:deduplicatedFact].*mock:Numeric, value=200\.000000, decimals=0'): 1,
        regex.compile(r'^\[info:deduplicatedInstance].*removing 31 fact'): 1,
    },
    'consistent-sets': {
        regex.compile(r'^\[info:deduplicatedFact].*mock:Numeric, value=100\.000000, decimals=0'): 1,
        regex.compile(r'^\[info:deduplicatedFact].*mock:Numeric, value=100\.100000, decimals=1'): 1,
        regex.compile(r'^\[info:deduplicatedInstance].*removing 28 fact'): 1,
    },
}
for arg, expected_infos in test_cases.items():
    print(f"Running with argument: {arg}")
    log_file = prepare_logfile(test_directory, this_file, name=arg)
    output_path = report_path.with_name(f"deduplicated-{arg}.xbrl")
    run_arelle(
        arelle_command,
        additional_args=[
            "--file", str(report_path),
            "--deduplicateFacts", arg,
            "--saveDeduplicatedInstance", str(output_path),
        ],
        offline=arelle_offline,
        logFile=log_file,
    )
    for pattern, count in ALL_TESTCASES.items():
        expected_infos[pattern] = expected_infos.get(pattern, 0) + count
    errors += validate_log_file(log_file, expected_results={"info": expected_infos})
    assert_result(errors)

assert_result(errors)

print("Cleaning up")
rmtree(working_directory / 'duplicate_facts_deduplication' / 'report')
os.unlink(working_directory / 'duplicate_facts_deduplication' / 'report.zip')
