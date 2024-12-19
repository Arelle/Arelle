from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

config = ConformanceSuiteConfig(
    args=[
        '--calc', 'xbrl21',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('XBRL-CONF-2014-12-10.zip'),
            entry_point=Path('XBRL-CONF-2014-12-10/xbrl.xml'),
            public_download_url='https://www.xbrl.org/2014/XBRL-CONF-2014-12-10.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    expected_failure_ids=frozenset(f'XBRL-CONF-2014-12-10/Common/{s}' for s in [
        # 202.02b in the absence of source/target constraints, an empty href doesn't pose a problem
        # 202-02b-HrefResolutionCounterExample-custom.xml Expected: valid, Actual: arelle:hrefWarning
        '200-linkbase/202-xlinkLocator.xml:V-02b',
    ]),
    info_url='https://specifications.xbrl.org/work-product-index-group-base-spec-base-spec.html',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    shards=3,
)
