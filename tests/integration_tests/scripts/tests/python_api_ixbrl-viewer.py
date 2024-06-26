from __future__ import annotations

import os
import urllib.request
import zipfile
from pathlib import Path
from shutil import rmtree

from arelle.RuntimeOptions import RuntimeOptions
# include import start
from arelle.api.Session import Session
# include import end
from tests.integration_tests.integration_test_util import get_s3_uri
from tests.integration_tests.scripts.script_util import parse_args, validate_log_xml, assert_result, prepare_logfile

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Confirm ixbrl-viewer plugin runs successfully using Arelle's Python API.",
    arelle=False,
    cache='ixbrl-viewer_cli.zip',
    cache_version_id='P.uruiqpYrdNHGzX.XuJPGS3QS6_qY9g',
)
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)
samples_zip_path = test_directory / 'samples.zip'
target_path = samples_zip_path / "samples/src/ixds-test/document1.html"
viewer_path = test_directory / "viewer.html"
report_zip_url = get_s3_uri(
    'ci/packages/IXBRLViewerSamples.zip',
    version_id='6eS7qUUoWLeM9JSSTXOfANkHoLz1Zv5o'
)

print(f"Downloading samples: {samples_zip_path}")
urllib.request.urlretrieve(report_zip_url, samples_zip_path)

print(f"Generating IXBRL viewer: {viewer_path}")
# include start
with open(samples_zip_path, 'rb') as stream:
    options = RuntimeOptions(
        sourceZipStream=stream,
        entrypointFile=str(target_path),
        internetConnectivity='offline' if arelle_offline else 'online',
        keepOpen=True,
        logFile='logToStructuredMessage',
        logFormat="[%(messageCode)s] %(message)s - %(file)s",
        pluginOptions={
            'saveViewerDest': str(viewer_path),
            'viewer_feature_review': True,
        },
        plugins='ixbrl-viewer',
        strictOptions=False,
    )
    with Session() as session:
        session.run(options)
        log_xml = session.get_logs('xml')
# include end

print(f"Checking for viewer: {viewer_path}")
if not viewer_path.exists():
    errors.append(f'Viewer not generated at "{viewer_path}"')

print(f"Checking log XML for errors...")
errors += validate_log_xml(log_xml)

assert_result(errors)

print("Cleaning up")
try:
    os.unlink(working_directory / 'python_api_ixbrl-viewer' / 'samples.zip')
    os.unlink(working_directory / 'python_api_ixbrl-viewer' / 'viewer.html')
    os.unlink(working_directory / 'python_api_ixbrl-viewer' / 'ixbrlviewer.js')
except PermissionError as exc:
    print(f"Failed to cleanup test files: {exc}")
