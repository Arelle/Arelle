"""
Script to validate all conformance suite configs by attempting to preload their test cases.
"""
from __future__ import annotations

import json

from tests.integration_tests.validation.conformance_suite_configs import ALL_CONFORMANCE_SUITE_CONFIGS
from tests.integration_tests.validation.download_assets import download_assets
from tests.integration_tests.validation.run_conformance_suites import preload_testcase_set


errors: dict[str, list[str]] = {}
for config in ALL_CONFORMANCE_SUITE_CONFIGS:
    download_assets(
        assets=set(config.assets),
        overwrite=False,
        download_and_apply_cache=False,
        download_private=True,
    )
    try:
        testcase_set = preload_testcase_set(config)
        if testcase_set.load_errors:
            errors[config.name] = testcase_set.load_errors
    except Exception as e:
        errors[config.name].append(str(e))

if errors:
    print(json.dumps(errors, indent=4))
