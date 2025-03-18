from __future__ import annotations

import html.parser
import os
import urllib.request
import zipfile
from pathlib import Path
from shutil import rmtree

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
args = parse_args(this_file.stem, "Confirm EBA Tablesets report runs successfully from the command line.")
arelle_command = args.arelle
arelle_offline = args.offline
working_directory = Path(args.working_directory)
test_directory = Path(args.test_directory)
arelle_log_file = prepare_logfile(test_directory, this_file)
samples_zip_path = test_directory / "eba_samples.zip"
samples_directory = test_directory / "eba_samples"
target_path = samples_directory / "DUMMYLEI123456789012_GB_COREP030000_COREPLECON_2021-06-30_20201218154732000.xbrl"
tablesets_report_path = test_directory / "index.html"
sample_report_zip_url = get_s3_uri("ci/packages/eba-samples.zip", version_id="iDJU3nFy6_rQ289k.mosenHjUFrXCmCM")

samples_url = get_s3_uri("ci/packages/eba_samples.zip", version_id="O7uYHbSYmxe_20nBhWWoXMfjGpquNMMj")

print(f"Downloading EBA sample files: {samples_zip_path}")
urllib.request.urlretrieve(samples_url, samples_zip_path)

print(f"Extracting EBA sample files: {samples_directory}")
with zipfile.ZipFile(samples_zip_path, "r") as zip_ref:
    zip_ref.extractall(samples_directory)

print(f"Generating EBA Tablesets report: {tablesets_report_path}")
run_arelle(
    arelle_command,
    plugins=["saveHtmlEBAtables"],
    additional_args=[
        "-f",
        str(target_path),
        "--package",
        str(samples_directory / "TP-Eurofiling2.1.zip"),
        "--package",
        str(samples_directory / "EBA_CRD_IV_XBRL_3.0_Dictionary_3.0.1.0.Errata3.zip"),
        "--package",
        str(samples_directory / "EBA_CRD_IV_XBRL_3.0_Reporting_COREP_FINREP_Frameworks_hotfix.Errata3.zip"),
        "--save-EBA-tablesets",
        str(tablesets_report_path),
    ],
    offline=arelle_offline,
    logFile=arelle_log_file,
)

print(f"Checking for EBA Tablesets report: {tablesets_report_path}")
if not tablesets_report_path.exists():
    errors.append(f'EBA Tablesets report not generated at "{tablesets_report_path}"')

eba_table_files = [
    "eba_tC_00.01.html",
    "eba_tC_26.00.html",
    "eba_tC_27.00.html",
    "eba_tC_28.00.html",
    "eba_tC_29.00.html",
]

eba_tablesets_report_files = [
    test_directory / f for f in ("index.html", "indexCenterLanding.html", "indexFormsFrame.html", *eba_table_files)
]

for report_file in eba_tablesets_report_files:
    if not report_file.exists():
        errors.append(f'EBA Tablesets report file not generated at "{report_file}"')


class ButtonParser(html.parser.HTMLParser):
    def __init__(self, table_files):
        super().__init__()
        self.table_files = table_files
        self.found_buttons = {table_file: False for table_file in table_files}

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "button":
            attrs_dict = dict(attrs)
            onclick = attrs_dict.get("onclick", "")
            if onclick is not None:
                for table_file in self.table_files:
                    expected_onclick = f"javascript:parent.loadContent('{table_file}');"
                    if expected_onclick in onclick:
                        self.found_buttons[table_file] = True


forms_frame_path = test_directory / "indexFormsFrame.html"
print("Checking for proper button elements in indexFormsFrame.html")
with open(forms_frame_path, encoding="utf-8") as fh:
    html_content = fh.read()
    parser = ButtonParser(eba_table_files)
    parser.feed(html_content)
    for table_file, found in parser.found_buttons.items():
        if not found:
            errors.append(f"Button for table {table_file} not found in indexFormsFrame.html")

print(f"Checking for log errors: {arelle_log_file}")
errors += validate_log_file(arelle_log_file)

assert_result(errors)

print("Cleaning up")
rmtree(samples_directory)
os.unlink(samples_zip_path)
for report_file in eba_tablesets_report_files:
    os.unlink(report_file)
