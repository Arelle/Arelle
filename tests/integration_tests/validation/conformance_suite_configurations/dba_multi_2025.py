from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'arl-2025-multi-target-preview',
        '--baseTaxonomyValidation', 'none',
        '--formula', 'none',
    ],
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('dba_multi_2025'),
            entry_point=Path('index.xml'),
        ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(Path('ARL-XBRL20251001-20251120.zip')),
    ],
    info_url='https://erhvervsstyrelsen.dk/vejledning-teknisk-vejledning-og-dokumentation-regnskab-20-taksonomier-aktuelle',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/DBA'}),
    shards=4,
)
