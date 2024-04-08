from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--formula', 'run',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('trr-3.0.1.zip'),
            entry_point=Path('testcase.xml'),
        ),
    ],
    info_url='https://specifications.xbrl.org/work-product-index-inline-xbrl-transformation-registry-3.html',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
)
