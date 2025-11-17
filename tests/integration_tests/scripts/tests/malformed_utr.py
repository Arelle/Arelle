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
    "Confirm malformed UTR fires the expected errors.",
)
arelle_command = args.arelle
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)

suite_zip_path = test_directory / 'suite.zip'
suite_directory = test_directory / 'suite'
instance_path = suite_directory / 'conf/utr-structure/tests/01-simple/simpleValid.xml'
suite_zip_url = get_s3_uri(
    'ci/conformance_suites/utr-structure-conf-cr-2013-11-18.zip',
    version_id='ECn8HExI_mObgNG02YICSrDMCFg2vnzX'
)

print(f"Downloading suite: {suite_zip_url}")
urllib.request.urlretrieve(suite_zip_url, suite_zip_path)

print(f"Extracting suite: {suite_directory}")
with zipfile.ZipFile(suite_zip_path, "r") as zip_ref:
    zip_ref.extractall(suite_directory)

test_cases: dict[str, dict[regex.Pattern[str], int]] = {
    '01-unit-id-and-status-not-unique.xml': {
        regex.compile(r'^\[arelleUtrLoader:entryDuplication'): 1.
    },
    '02-simple-unit-item-type-missing.xml': {
        regex.compile(r'^\[arelleUtrLoader:simpleDefMissingField'): 1.
    },
    '03-complex-unit-with-symbol.xml': {
        regex.compile(r'^\[arelleUtrLoader:complexDefSymbol'): 1.
    },
    '04-numerator-item-type-namespace-but-no-numerator-item-type.xml': {
        regex.compile(r'^\[arelleUtrLoader:complexDefMissingField'): 1.
    },
    '05-simple-unit-with-numerator-item-type.xml': {
        regex.compile(r'^\[arelleUtrLoader:complexDefMissingField'): 1.
    },
    '06-denominator-item-type-namespace-but-no-denominator-item-type.xml': {
        regex.compile(r'^\[arelleUtrLoader:complexDefMissingField'): 1.
    },
    '07-simple-unit-with-denominator-item-type.xml': {
        regex.compile(r'^\[arelleUtrLoader:complexDefMissingField'): 1,
        regex.compile(r'^\[utre:error-NumericFactUtrInvalid'): 1,
    },
}

for utr_file, expected_errors in test_cases.items():
    print(f"Running with UTR file: {utr_file}")
    log_file = prepare_logfile(test_directory, this_file, name=utr_file)
    run_arelle(
        arelle_command,
        additional_args=[
            "--file", str(suite_directory / 'conf/utr-structure/tests/01-simple/simpleValid.xml'),
            '--utrUrl', str(suite_directory / 'conf/utr-structure/malformed-utrs' / utr_file),
            '--utr',
            "--validate",
        ],
        offline=arelle_offline,
        logFile=log_file,
    )
    errors += validate_log_file(log_file, expected_results={"error": expected_errors})
    assert_result(errors)

assert_result(errors)

print("Cleaning up")
rmtree(working_directory / 'malformed_utr' / 'suite')
os.unlink(working_directory / 'malformed_utr' / 'suite.zip')
