from __future__ import annotations

import os
from pathlib import Path

from tests.integration_tests.integration_test_util import download_from_public_s3
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
    "Smoke test load from Excel plugin.",
    cache='load_from_excel.zip',
    cache_version_id='oGRKSXanaohN6PKnXckFFpzNPhIr.Yq9',
)
arelle_command = args.arelle
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)
arelle_log_file = prepare_logfile(test_directory, this_file)

excel_taxonomy_path = test_directory / 'XII_Taxonomy.xlsx'
print(f"Downloading Excel file: {excel_taxonomy_path}")
download_from_public_s3(
    excel_taxonomy_path,
    "ci/packages/XII_Taxonomy.xlsx",
    version_id="c5mjDshdqpmu8CvVt37Ur9yhh06fO1BB",
)

run_arelle(
    arelle_command,
    additional_args=[
        "--file",
        str(excel_taxonomy_path),
    ],
    offline=arelle_offline,
    logFile=arelle_log_file,
    plugins=["loadFromExcel"],
)

print(f"Checking for log errors: {arelle_log_file}")
errors += validate_log_file(arelle_log_file)
assert_result(errors)

print("Cleaning up")
os.unlink(excel_taxonomy_path)
