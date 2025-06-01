from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
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
    info_url='https://specifications.xbrl.org/work-product-index-table-linkbase-table-linkbase-1.0.html',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    shards=4,
    test_case_result_options='match-any',
)
