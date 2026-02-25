from __future__ import annotations

import multiprocessing
import os
import urllib.request
from pathlib import Path

import regex

from arelle.RuntimeOptions import RuntimeOptions
from arelle.api.Session import Session
from arelle.api.SessionPool import SessionPool
from tests.integration_tests.integration_test_util import get_s3_uri
from tests.integration_tests.scripts.script_util import parse_args, prepare_logfile, validate_log_xml, assert_result
from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.download_assets import download_assets


def _result_callback(session: Session) -> str:
    return session.get_logs('xml')


if __name__ == "__main__":
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

    run_count = multiprocessing.cpu_count() * 2
    log_files = [
        str(prepare_logfile(test_directory, Path(f'logs_{i}')))
        for i in range(run_count)
    ]
    options = [
        RuntimeOptions(
            entrypointFile=str(report_zip_path),
            disclosureSystemName='esef',
            internetConnectivity='offline',
            logFile=log_file,
            logFormat="[%(messageCode)s] %(message)s - %(file)s",
            packages=package_paths,
            parameters="authority=SE",
            plugins='validate/ESEF',
            validate=True,
        )
        for log_file in log_files
    ]

    print(f"Validating report: {target_path}")
    with SessionPool() as pool:
        results = pool.map(_result_callback, options)

    for runtime_options, log_xml in results:
        print("Checking log XML for errors...")
        assert runtime_options.logFile is not None
        with open(Path(runtime_options.logFile), 'r') as file:
            log_content = file.read().partition('\n')[2]
            assert abs(float(len(log_content))/len(log_xml) - 1) < 0.01, \
                "Log file content length does not match XML content length from session API."
        errors += validate_log_xml(log_xml, expected_results={
            'error': {
                regex.compile(r'^\[ESEF.2.2.1.precisionAttributeUsed] .*'): 1
            },
            'info': {
                # This message appears near the end of the file, so this helps confirm the entire file
                # was written.
                regex.compile(r'^\[info] validated in .*'): 1
            },
        })
        assert_result(errors)

    print("Cleaning up")
    try:
        os.unlink(working_directory / 'python_api_session_pool' / 'TC2_invalid.zip')
    except PermissionError as exc:
        print(f"Failed to cleanup test files: {exc}")
