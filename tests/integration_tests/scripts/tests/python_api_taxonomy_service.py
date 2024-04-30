from __future__ import annotations

import itertools
import json
import urllib.request
import zipfile
from pathlib import Path
from shutil import rmtree

from arelle.RuntimeOptions import RuntimeOptions
from arelle.api.Session import Session
from arelle.plugin.validate import FERC
from tests.integration_tests.integration_test_util import get_s3_uri
from tests.integration_tests.scripts.script_util import parse_args, prepare_logfile


this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Confirm taxonomy service API usage works as expected.",
    arelle=False,
)
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)
cache_directory = test_directory / 'cache'
arelle_log_file = prepare_logfile(test_directory, this_file, ext='json')
entry_point_url = 'https://eCollection.ferc.gov/taxonomy/form60/2024-04-01/form/form60/form-60_2024-04-01.xsd'
remove_file = cache_directory / 'http' / 'www.xbrl.org' / '2005' / 'xbrldt-2005.xsd'
cache_zip_url = get_s3_uri(
    'ci/caches/scripts/python_api_taxonomy_service.zip',
    version_id='rSYFEO6UrUHEHl4zaRnFiZZKgIcDFKkY'
)
cache_zip_path = test_directory / 'cache.zip'

print(f"Downloading cache with missing labels file: {cache_zip_path}")
urllib.request.urlretrieve(cache_zip_url, cache_zip_path)
with zipfile.ZipFile(cache_zip_path, "r") as zip_ref:
    zip_ref.extractall(cache_directory)

print(f"Loading model: {entry_point_url}")
options = RuntimeOptions(
    cacheDirectory=str(cache_directory),
    disclosureSystemName='FERC',
    entrypointFile=entry_point_url,
    internetConnectivity='offline',
    logFile='logToStructuredMessage',
    logLevel='DEBUG',
    logRefObjectProperties=True,
    plugins=FERC.__file__,
    strictOptions=False,
    utrValidate=True,
    validate=True,
)
with Session() as session:
    session.run(options)
    log_messages = session._cntlr.logHandler.messages
    with open(arelle_log_file, 'w') as f:
        json.dump(log_messages, f, ensure_ascii=False, indent=4)

print(f"Validating structured logs have errors for missing labels...")
message_code_groups = itertools.groupby(log_messages, key=lambda m: m['messageCode'])
expected_code_counts = {
    'info': 1,
    'IOerror': 1,
    'xbrl.5.2.4.2.1:preferredLabelMissing': 1910,
    'info:profileActivity': 1
}
for code, messages in message_code_groups:
    count = len(list(messages))
    assert expected_code_counts.get(code, []) == count, \
        f"Unexpected message count for {code}: {count}"

print("Cleaning up")
try:
    rmtree(working_directory / 'python_api_taxonomy_service' / 'cache')
    cache_zip_path.unlink()
except PermissionError as exc:
    print(f"Failed to cleanup test files: {exc}")
