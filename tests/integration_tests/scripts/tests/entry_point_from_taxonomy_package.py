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
    "Confirm unpublished entry point can be loaded from a taxonomy package on the command line.",
)
arelle_command = args.arelle
arelle_offline = args.offline
test_directory = Path(args.test_directory)
arelle_log_file = prepare_logfile(test_directory, this_file)
taxonomy_package_name = "entry_point_from_taxonomy_package.zip"
taxonomy_package_path = test_directory / taxonomy_package_name
taxonomy_package_zip_url = get_s3_uri(
    f"ci/packages/{taxonomy_package_name}", version_id="nbaiNmQvDfvRSZzmrFRsuhH5yS2RDVk."
)

print(f"Downloading taxonomy package: {taxonomy_package_name}")
urllib.request.urlretrieve(taxonomy_package_zip_url, taxonomy_package_path)

entry_point = "https://arelle.org/example/example.xsd"
print(f"Validating entry point: {entry_point}")
run_arelle(
    arelle_command,
    additional_args=[
        "--file",
        entry_point,
        "--packages",
        str(taxonomy_package_path),
        "--validate"
    ],
    offline=arelle_offline,
    logFile=arelle_log_file,
)

errors += validate_log_file(arelle_log_file)

assert_result(errors)

print("Cleaning up")
os.unlink(taxonomy_package_path)
