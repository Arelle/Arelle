from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

config = ConformanceSuiteConfig(
    args=[
        '--calc', 'xbrl21',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('XBRL-CONF-2024-12-17.zip'),
            entry_point=Path('XBRL-CONF-2024-12-17/xbrl.xml'),
            public_download_url='https://www.xbrl.org/2014/XBRL-CONF-2024-12-17.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    expected_additional_testcase_errors={f"XBRL-CONF-2024-12-17/Common/{s}": val for s, val in {
        # 202.02b in the absence of source/target constraints, an empty href doesn't pose a problem
        # 202-02b-HrefResolutionCounterExample-custom.xml Expected: valid, Actual: arelle:hrefWarning
        '200-linkbase/202-xlinkLocator.xml:V-02b': frozenset({'arelle:hrefWarning'}),
    }.items()},
    expected_missing_testcases=frozenset([f"XBRL-CONF-2024-12-17/Common/{s}" for s in [
        "related-standards/xlink/arc-duplication/arc-duplication-testcase.xml",
        "related-standards/xml-schema/uniqueParticleAttribution/uniqueParticleAttribution-testcase.xml",
    ]]),
    info_url='https://specifications.xbrl.org/work-product-index-group-base-spec-base-spec.html',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    strict_testcase_index=False,
    shards=3,
)
