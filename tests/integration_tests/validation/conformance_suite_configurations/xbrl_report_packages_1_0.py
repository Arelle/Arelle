from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

config = ConformanceSuiteConfig(
    args=[
        "--reportPackage",
        "--skipPackageContentLoading",
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path("report-package-conformance.zip"),
            entry_point=Path("report-package-conformance/index.csv"),
        ),
    ],
    expected_additional_testcase_errors={f"report-package-conformance/index.csv:{s}": val for s, val in {
        # Invalid zip also fires FileSourceError.
        "V-000-invalid-zip": {
            "FileSourceError": 1,
        },
    }.items()},
    info_url="https://specifications.xbrl.org/work-product-index-taxonomy-packages-report-packages-1.0.html",
    membership_url="https://www.xbrl.org/join",
    name=PurePath(__file__).stem,
)
