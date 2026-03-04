import os
import urllib.request
import zipfile
from pathlib import Path
from shutil import rmtree

from tests.integration_tests.integration_test_util import get_s3_uri
from tests.integration_tests.scripts.script_util import (
    parse_args,
    assert_result,
    prepare_logfile,
    run_arelle_cmd,
    )

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Confirm the `--validationExitCode` option works as expected.",
    )

arelle_command = args.arelle
arelle_offline = args.offline
working_directory = args.working_directory
test_directory = args.test_directory
arelle_log_file = prepare_logfile(test_directory, this_file)
samples_zip_path = test_directory / 'samples.zip'
samples_directory = test_directory / 'samples'
warning_target_path = samples_directory / "warning.xbrl"
error_target_path = samples_directory / "error.xbri"
report_zip_url = get_s3_uri(
    'ci/packages/validation_exit_code.zip',
    version_id='0CXwl2Zj3yC5eEXohH_boOl0JfWBzy89'
    )

print(f"Downloading samples: {samples_zip_path}")
urllib.request.urlretrieve(report_zip_url, samples_zip_path)

print(f"Extracting samples: {samples_directory}")
with zipfile.ZipFile(samples_zip_path, "r") as zip_ref:
    zip_ref.extractall(samples_directory)

result = run_arelle_cmd(
    arelle_command,
    additional_args=[
        "-f", str(warning_target_path),
        "--validate",
        "--validationExitCode",
        "--captureWarnings",  # it does it by default in tests
        "--validateDuplicateFacts",
        "all",
        ],
    offline=arelle_offline,
    logFile=arelle_log_file,
    )

if result.returncode != 3:
    errors.append(f"Warnings found. Validation finished with exit code {result.returncode}. Expected 3.")

result = run_arelle_cmd(
    arelle_command,
    additional_args=[
        "-f", str(error_target_path),
        "--validate",
        "--validationExitCode",
        ],
    offline=arelle_offline,
    logFile=arelle_log_file,
    )

if result.returncode != 3:
    errors.append(f"Errors found. Validation finished with exit code {result.returncode}. Expected 3.")

result = run_arelle_cmd(
    arelle_command,
    additional_args=[
        "-f", str(warning_target_path),
        "--validate",
        "--validationExitCode",
        "--webserver",
        ],
    offline=arelle_offline,
    logFile=arelle_log_file,
    )

if result.returncode != 2:
    errors.append("--validationExitCode can't be used with --webserver")

print("Cleaning up")
rmtree(samples_directory)
os.unlink(samples_zip_path)

assert_result(errors)
