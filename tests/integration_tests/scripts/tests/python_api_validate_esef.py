from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import regex

from arelle.RuntimeOptions import RuntimeOptions
from arelle.api.Session import Session
from tests.integration_tests.integration_test_util import get_s3_uri
from tests.integration_tests.scripts.script_util import parse_args, validate_log_xml, assert_result, prepare_logfile
from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.download_assets import download_assets

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Confirm ESEF validation runs successfully using Arelle's Python API.",
    arelle=False,
)
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)
arelle_log_file = prepare_logfile(test_directory, this_file)
report_zip_path = test_directory / 'TC2_invalid.zip'
target_path = report_zip_path
report_zip_url = get_s3_uri(
    'ci/packages/python_api_validate_esef.zip',
    version_id='U3sEz.B8kjUWw0l6momz87EndK05cxFZ'
)

print(f"Downloading report: {report_zip_path}")
urllib.request.urlretrieve(report_zip_url, report_zip_path)

print(f"Downloading packages...")
package_assets = {
    package for year in [2017, 2019, 2020, 2021, 2022] for package in ESEF_PACKAGES[year]
}
download_assets(
    assets=package_assets,
    overwrite=False,
    download_and_apply_cache=False,
    download_private=False,
)
package_paths = [str(a.full_local_path) for a in package_assets]

print(f"Validating report: {target_path}")
# include start
options = RuntimeOptions(
    entrypointFile=str(report_zip_path),
    disclosureSystemName='esef',
    internetConnectivity='offline',
    logFile=str(arelle_log_file),
    logFormat="[%(messageCode)s] %(message)s - %(file)s",
    packages=package_paths,
    plugins='validate/ESEF',
    strictOptions=False,
    validate=True,
)
with Session() as session:
    session.run(options)
    log_xml = session.get_logs('xml')
# include end

print(f"Checking log XML for errors...")
errors += validate_log_xml(log_xml, expected_results={
    'error': {
        regex.compile(r'^\[ESEF.2.2.1.precisionAttributeUsed] .*'): 1
    },
})

assert_result(errors)

print("Cleaning up")
try:
    os.unlink(working_directory / 'python_api_validate_esef' / 'TC2_invalid.zip')
except PermissionError as exc:
    print(f"Failed to cleanup test files: {exc}")
