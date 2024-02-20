import os
import urllib.request
import zipfile

from pathlib import Path
from shutil import rmtree

from tests.integration_tests.integration_test_util import get_s3_uri
from tests.integration_tests.scripts.script_util import run_arelle, parse_args, validate_log_file, assert_result, prepare_logfile

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Confirm ixbrl-viewer plugin runs successfully from the command line.",
    cache=this_file.with_suffix(".zip").name,
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

print(f"Generating IXBRL viewer: {viewer_path}")
run_arelle(
    arelle_command,
    plugins=["ixbrl-viewer"],
    additional_args=[
        "-f", str(target_path),
        "--save-viewer", str(viewer_path),
    ],
    offline=arelle_offline,
    logFile=arelle_log_file,
)

print(f"Checking for viewer: {viewer_path}")
if not viewer_path.exists():
    errors.append(f'Viewer not generated at "{viewer_path}"')

print(f"Checking for log errors: {arelle_log_file}")
errors += validate_log_file(arelle_log_file)

assert_result(errors)

print("Cleaning up")
rmtree(working_directory / 'ixbrl-viewer_cli' / 'samples')
os.unlink(working_directory / 'ixbrl-viewer_cli' / 'samples.zip')
os.unlink(working_directory / 'ixbrl-viewer_cli' / 'viewer.html')
os.unlink(working_directory / 'ixbrl-viewer_cli' / 'ixbrlviewer.js')
