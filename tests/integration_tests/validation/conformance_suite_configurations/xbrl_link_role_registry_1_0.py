from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('lrr-conf-pwd-2005-06-21.zip'),
            entry_point=Path('lrr/conf/index.xml'),
        ),
    ],
    info_url='https://specifications.xbrl.org/work-product-index-registries-lrr-1.0.html',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    url_replace='file:///c:/temp/conf/',
)
