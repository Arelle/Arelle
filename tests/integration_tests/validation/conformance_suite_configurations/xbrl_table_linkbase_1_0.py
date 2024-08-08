from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('table-linkbase-conf-2015-08-12.zip'),
            entry_point=Path('table-linkbase-conf-2015-08-12/conf/testcases-index.xml'),
            public_download_url='https://www.xbrl.org/2015/table-linkbase-conf-2015-08-12.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    expected_additional_testcase_errors={f'table-linkbase-conf-2015-08-12/conf/tests/{s}': errors for s, errors in {
        '6000-aspect-node/6660-aspect-node-aspect-cover-filter/6660-aspect-node-aspect-cover-filter-testcase.xml:v-01': frozenset(['xmlSchema:elementUnexpected']),
    }.items()},
    info_url='https://specifications.xbrl.org/work-product-index-table-linkbase-table-linkbase-1.0.html',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    shards=4,
    test_case_result_options='match-any',
)
