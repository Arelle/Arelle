from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('data-type-registry-1.11.0-REC+registry+2024-01-31.zip'),
            entry_point=Path('data-type-registry-1.11.0-REC+registry+2024-01-31/conf/dtr/testcase-index.xml'),
        ),
    ],
    info_url='https://gitlab.xbrl.org/base-spec/data-type-registry/-/tree/1.11.0-REC+registry+2024-01-31/conf',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
)
