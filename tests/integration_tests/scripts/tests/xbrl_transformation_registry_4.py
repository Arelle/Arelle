from __future__ import annotations

import os
import zipfile
from pathlib import Path
from shutil import rmtree

import regex

from tests.integration_tests.scripts.script_util import run_arelle, parse_args, validate_log_text, assert_result, prepare_logfile
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteAssetConfig
from tests.integration_tests.validation.download_assets import download_assets

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
arelle_log_file = prepare_logfile(test_directory, this_file)
arelle_report_file = prepare_logfile(test_directory, this_file, ext='csv')

asset = ConformanceSuiteAssetConfig.conformance_suite(
    Path('trr-4.0.zip'),
    entry_point=Path('testcase.xml'),
)
suite_zip_path = asset.full_local_path
print(f"Downloading suite: {suite_zip_path}")
download_assets(
    assets={asset},
    overwrite=False,
    download_and_apply_cache=False,
    download_private=True
)

suite_directory = test_directory / 'suite'
print(f"Extracting suite: {suite_directory}")
with zipfile.ZipFile(suite_zip_path, "r") as zip_ref:
    zip_ref.extractall(suite_directory)

index_path = suite_directory / 'testcase.xml'

expected_results = {
    regex.compile(r'.*,pass'): 8596,
    regex.compile(r'.*,fail'): 0,
}

run_arelle(
    arelle_command,
    additional_args=[
        "--file", str(index_path),
        "--testReport", str(arelle_report_file),
        "--testReportCols", "Testcase,Id,Status",
        "--validate",
    ],
    offline=arelle_offline,
    logFile=arelle_log_file,
)

errors += validate_log_text(arelle_report_file, expected_results=expected_results)
assert_result(errors)

print("Cleaning up")
os.unlink(suite_zip_path)
rmtree(working_directory / 'xbrl_transformation_registry_4' / 'suite')
