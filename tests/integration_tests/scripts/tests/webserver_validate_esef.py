from __future__ import annotations

import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

import requests

from tests.integration_tests.integration_test_util import get_s3_uri
from tests.integration_tests.scripts.script_util import parse_args, assert_result, prepare_logfile, run_arelle_webserver, validate_log_xml
from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.download_assets import download_assets

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Confirm ESEF validation runs successfully using the webserver.",
    arelle=False,
)
arelle_command = args.arelle
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)
report_zip_path = test_directory / 'TC2_invalid.zip'
arelle_log_file = prepare_logfile(test_directory, this_file)
report_zip_url = get_s3_uri(
    'ci/packages/python_api_validate_esef.zip',
    version_id='U3sEz.B8kjUWw0l6momz87EndK05cxFZ'
)

print(f"Downloading report: {report_zip_path}")
urllib.request.urlretrieve(report_zip_url, report_zip_path)

print("Downloading packages...")
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

contents = ''
port = 8100
log_xml_bytes = None
with run_arelle_webserver(arelle_command, port) as proc:
    url = f"http://localhost:{port}/rest/xbrl/validation?media=xml"
    url += "&plugins=validate/ESEF"
    url += "&disclosureSystemName=esef"
    url += f"&internetConnectivity={'false' if arelle_offline else 'true'}"
    url += f"&logFile={urllib.parse.quote_plus(str(arelle_log_file))}"
    url += f"&packages=" + '|'.join(urllib.parse.quote_plus(str(p)) for p in package_paths)
    url += f"&parameters=authority=SE"
    print(f"Validating: {url}")
    with open(report_zip_path, "rb") as f:
        files = {"upload": f}
        response = requests.post(url, files=files)
    response.raise_for_status()
    contents = response.content
    with open(arelle_log_file, 'x') as file:
        log_xml_bytes = contents
        file.write(log_xml_bytes.decode())

if "[info] Activation of plug-in Validate ESMA ESEF successful" not in contents.decode():
    errors.append("Plugin activation failed with response: \n" + contents.decode())

print("Checking log XML for errors...")
errors += validate_log_xml(log_xml_bytes, expected_results={
    'error': {
        re.compile(r'.*\[ESEF\.2\.2\.1\.precisionAttributeUsed] .*'): 1
    },
    'info': {
        re.compile(r'.*\[arelle\.ESEF\.reportPackageSize] The exact report package zipped .*'): 1
    }
})

assert_result(errors)

print("Cleaning up")
try:
    os.unlink(working_directory / 'webserver_validate_esef' / 'TC2_invalid.zip')
except PermissionError as exc:
    print(f"Failed to cleanup test files: {exc}")
