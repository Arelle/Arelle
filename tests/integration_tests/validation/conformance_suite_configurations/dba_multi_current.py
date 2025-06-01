from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'arl-2024-multi-target-preview',
        '--baseTaxonomyValidation', 'none',
    ],
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('dba_multi'),
            entry_point=Path('index.xml'),
        ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(Path('ARL-XBRL20221001-20221117.zip')),
    ],
    info_url='https://erhvervsstyrelsen.dk/vejledning-teknisk-vejledning-og-dokumentation-regnskab-20-taksonomier-aktuelle',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/DBA'}),
    shards=1,
)
