from __future__ import annotations

import os
from pathlib import Path

import regex

from arelle.RuntimeOptions import RuntimeOptions
from arelle.api.Session import Session
from tests.integration_tests.integration_test_util import download_from_public_s3
from tests.integration_tests.scripts.script_util import parse_args, validate_log_xml, assert_result, prepare_logfile
from tests.integration_tests.validation.assets import ESEF_PACKAGES, UKFRC_PACKAGES
from tests.integration_tests.validation.download_assets import download_assets

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Confirm ESEF+UKSEF validation runs successfully using Arelle's Python API.",
    arelle=False,
)
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)
arelle_log_file = prepare_logfile(test_directory, this_file)
report_zip_path = test_directory / "report.zip"
target_path = report_zip_path
print(f"Downloading report: {report_zip_path}")
# Based on FRC_06:TC2 testcase from UKSEF conformance suite
download_from_public_s3(
    report_zip_path,
    "ci/packages/python_api_validate_uksef.zip",
    version_id="eZImYqnzxvgXJtmhE8qfjaTwc2S9Oqs0",
)

print("Downloading packages...")
package_assets = {
    package for year in [2022] for package in ESEF_PACKAGES[year]
} | set(UKFRC_PACKAGES.values())

download_assets(
    assets=package_assets,
    overwrite=False,
    download_and_apply_cache=False,
    download_private=False,
)
package_paths = [str(a.full_local_path) for a in package_assets]

print(f"Validating report: {target_path}")
options = RuntimeOptions(
    entrypointFile=str(report_zip_path),
    formulaAction="none",
    disclosureSystemName="esef-2022",
    internetConnectivity="offline",
    logFile=str(arelle_log_file),
    logFormat="[%(messageCode)s] %(message)s - %(file)s",
    packages=package_paths,
    plugins="validate/ESEF",
    validate=True,
    pluginOptions={
        "esefAuthority": "UKFRC",
    },
)
with Session() as session:
    session.run(options)
    log_xml = session.get_logs("xml")

print("Checking log XML for errors...")
errors += validate_log_xml(log_xml, expected_results={
    "error": {
        regex.compile(r"^\[ESEF.2.6.1.reportIncorrectlyPlacedInPackage] .*"): 1,
        regex.compile(r"^\[ESEF.2.1.4.multipleIdentifiers] .*"): 1,
        regex.compile(r"^\[ESEF.UKFRC6.invalidIdentifier] .*"): 1,
        regex.compile(r"^\[ESEF.UKFRC6.multipleIdentifiers] .*"): 1,
    },
})

assert_result(errors)

print("Cleaning up")
try:
    os.unlink(working_directory / "python_api_validate_uksef" / "report.zip")
except PermissionError as exc:
    print(f"Failed to cleanup test files: {exc}")
