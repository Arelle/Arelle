from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('extensible-enumerations-CONF-2014-10-29.zip'),
            entry_point=Path('extensible-enumerations-CONF-2014-10-29/enumerations-index.xml'),
            public_download_url='https://www.xbrl.org/2014/extensible-enumerations-CONF-2014-10-29.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    info_url='https://specifications.xbrl.org/work-product-index-extensible-enumerations-extensible-enumerations-1.0.html',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
)
