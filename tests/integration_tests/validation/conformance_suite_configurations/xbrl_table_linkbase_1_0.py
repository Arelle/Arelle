from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig, CiConfig,
)

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('table-linkbase-conformance-2024-12-17.zip'),
            entry_point=Path('table-linkbase-conformance-2024-12-17/testcases-index.xml'),
            public_download_url='https://www.xbrl.org/2015/table-linkbase-conformance-2024-12-17.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    ci_config=CiConfig(fast=False),
    expected_additional_testcase_errors={
        # xfie:invalidExplicitDimensionQName was previously silenced by the previous testcase variation runner
        'tests/6000-aspect-node/6640-aspect-node-explicit-dimension-filter/6640-aspect-node-explicit-dimension-filter-testcase.xml:v-03': {
            'xfie:invalidExplicitDimensionQName': 1,
        },
    },
    info_url='https://specifications.xbrl.org/work-product-index-table-linkbase-table-linkbase-1.0.html',
    name=PurePath(__file__).stem,
    plugins=frozenset({"tests/plugin/renderTable.py"}),
    test_case_result_options='match-any',
)
