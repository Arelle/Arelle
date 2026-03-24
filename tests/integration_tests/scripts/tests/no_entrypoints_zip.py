from __future__ import annotations

import os
import zipfile
from pathlib import Path

import regex

from tests.integration_tests.scripts.script_util import (
    assert_result,
    parse_args,
    prepare_logfile,
    run_arelle,
    validate_log_file,
)

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Verify error message when loading a zip file with no XBRL entry points.",
)
arelle_command = args.arelle
arelle_offline = args.offline
test_directory = Path(args.test_directory)
arelle_log_file = prepare_logfile(test_directory, this_file)

no_entrypoints_zip_path = test_directory / "no_entrypoints.zip"
print(f"Creating zip file with no XBRL entry points: {no_entrypoints_zip_path}")
with zipfile.ZipFile(no_entrypoints_zip_path, "w") as zf:
    zf.writestr("readme.md", "This archive has no XBRL entry points.")

run_arelle(
    arelle_command,
    additional_args=[
        "--file",
        str(no_entrypoints_zip_path),
    ],
    offline=arelle_offline,
    logFile=arelle_log_file,
)

print(f"Checking for expected error in log: {arelle_log_file}")
errors += validate_log_file(
    arelle_log_file,
    expected_results={
        "error": {
            regex.compile(r".*No XBRL entry points could be loaded from provided file.*"): 1,
        },
    },
)
assert_result(errors)

print("Cleaning up")
os.unlink(no_entrypoints_zip_path)
