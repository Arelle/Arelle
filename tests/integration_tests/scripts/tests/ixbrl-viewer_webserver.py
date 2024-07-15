from __future__ import annotations

import os
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from shutil import rmtree

from tests.integration_tests.integration_test_util import get_s3_uri
from tests.integration_tests.scripts.script_util import parse_args, validate_log_file, assert_result, prepare_logfile, run_arelle_webserver

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Confirm ixbrl-viewer plugin runs successfully from the web server.",
    cache='ixbrl-viewer_cli.zip',
    cache_version_id='P.uruiqpYrdNHGzX.XuJPGS3QS6_qY9g',
)
arelle_command = args.arelle
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)
arelle_log_file = prepare_logfile(test_directory, this_file)
samples_zip_path = test_directory / 'samples.zip'
samples_directory = test_directory / 'samples'
target_path = samples_directory / "samples/src/ixds-test/document1.html"
viewer_path = test_directory / "viewer.html"
report_zip_url = get_s3_uri(
    'ci/packages/IXBRLViewerSamples.zip',
    version_id='6eS7qUUoWLeM9JSSTXOfANkHoLz1Zv5o'
)

print(f"Downloading samples: {samples_zip_path}")
urllib.request.urlretrieve(report_zip_url, samples_zip_path)

print(f"Extracting samples: {samples_directory}")
with zipfile.ZipFile(samples_zip_path, "r") as zip_ref:
    zip_ref.extractall(samples_directory)

contents = ''
port = 8100
with run_arelle_webserver(arelle_command, port) as proc:
    target_url = urllib.parse.quote_plus(str(target_path))
    url = f"http://localhost:{port}/rest/xbrl/{target_url}/open?media=xml"
    url += "&plugins=ixbrl-viewer"
    url += "&viewer_feature_review=true"
    url += f"&saveViewerDest={urllib.parse.quote_plus(str(viewer_path))}"
    url += f"&internetConnectivity={'false' if arelle_offline else 'true'}"
    url += f"&logFile={urllib.parse.quote_plus(str(arelle_log_file))}"
    print(f"Generating IXBRL viewer: {url}")
    contents = urllib.request.urlopen(url).read()
    with open(arelle_log_file, 'x') as file:
        file.write(contents.decode())

if "[info] Activation of plug-in ixbrl-viewer successful" not in contents.decode():
    errors.append("Plugin activation failed with response: \n" + contents.decode())

print(f"Checking for viewer: {viewer_path}")
if not viewer_path.exists():
    errors.append(f'Viewer not generated at "{viewer_path}"')

print(f"Checking for log errors: {arelle_log_file}")
errors += validate_log_file(arelle_log_file)

assert_result(errors)

print("Cleaning up")
rmtree(working_directory / 'ixbrl-viewer_webserver' / 'samples')
os.unlink(working_directory / 'ixbrl-viewer_webserver' / 'samples.zip')
os.unlink(working_directory / 'ixbrl-viewer_webserver' / 'viewer.html')
os.unlink(working_directory / 'ixbrl-viewer_webserver' / 'ixbrlviewer.js')
