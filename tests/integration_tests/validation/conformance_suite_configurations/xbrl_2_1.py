from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig, CiConfig,
)

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('XBRL-CONF-2025-07-16.zip'),
            entry_point=Path('XBRL-CONF-2025-07-16/xbrl.xml'),
            public_download_url='https://www.xbrl.org/2025/XBRL-CONF-2025-07-16.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    ci_config=CiConfig(fast=False),
    expected_additional_testcase_errors={f"Common/{s}": val for s, val in {
        # 202.02b in the absence of source/target constraints, an empty href doesn't pose a problem
        # 202-02b-HrefResolutionCounterExample-custom.xml Expected: valid, Actual: arelle:hrefWarning
        '200-linkbase/202-xlinkLocator.xml:V-02b': {
            'arelle:hrefWarning': 1,
        },
    }.items()},
    info_url='https://specifications.xbrl.org/work-product-index-group-base-spec-base-spec.html',
    name=PurePath(__file__).stem,
    runtime_options={
        'calcs': 'xbrl21',
    },
)
