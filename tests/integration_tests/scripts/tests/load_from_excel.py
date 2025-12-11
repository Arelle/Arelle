from __future__ import annotations

import os
import urllib.request
from pathlib import Path

from tests.integration_tests.integration_test_util import get_s3_uri
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
excel_taxonomy_url = get_s3_uri(
    'ci/packages/XII_Taxonomy.xlsx',
    version_id='c5mjDshdqpmu8CvVt37Ur9yhh06fO1BB'
)

print(f"Downloading Excel file: {excel_taxonomy_url}")
urllib.request.urlretrieve(excel_taxonomy_url, excel_taxonomy_path)

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
