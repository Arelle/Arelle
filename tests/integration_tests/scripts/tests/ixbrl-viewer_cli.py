import urllib.request
import zipfile

from pathlib import Path

from tests.integration_tests.scripts.script_util import run_arelle, parse_args, validate_log_file, assert_result, cleanup, prepare_logfile

errors = []
this_file = Path(__file__)
args = parse_args(
    this_file.stem,
    "Confirm ixbrl-viewer plugin runs successfully from the command line.",
    cache=this_file.with_suffix(".zip").name,
)
arelle_command = args.arelle
arelle_offline = args.offline
working_directory = Path(args.working_directory)
arelle_log_file = prepare_logfile(working_directory, this_file)
samples_zip_path = working_directory.joinpath('samples.zip')
samples_directory = working_directory.joinpath('samples')
target_path = samples_directory.joinpath("samples/src/ixds-test/document1.html")
viewer_path = working_directory.joinpath("viewer.html")


print(f"Downloading samples: {samples_zip_path}")
urllib.request.urlretrieve("https://arelle-public.s3.amazonaws.com/ci/packages/IXBRLViewerSamples.zip", samples_zip_path)

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

print(f"Cleaning up")
cleanup(
    working_directory,
    [
        samples_directory,
        samples_zip_path,
        viewer_path,
        working_directory.joinpath("ixbrlviewer.js")
    ]
)
