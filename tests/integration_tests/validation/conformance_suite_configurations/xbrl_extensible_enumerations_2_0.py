from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('extensible-enumerations-2.0-2020-02-12.zip'),
            entry_point=Path('extensible-enumerations-2.0-2020-02-12/enumerations-index.xml'),
        ),
    ],
    info_url='https://specifications.xbrl.org/work-product-index-extensible-enumerations-extensible-enumerations-2.0.html',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
)
