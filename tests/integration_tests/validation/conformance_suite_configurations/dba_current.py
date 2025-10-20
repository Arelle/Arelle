from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('dba'),
            entry_point=Path('index.xml'),
        ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(Path('ARL-XBRL20221001-20221117.zip')),
    ],
    base_taxonomy_validation='none',
    cache_version_id='gqg_wyX4Tx52sj4WljjDswZLJqH0zvaU',
    disclosure_system='arl-2022-preview',
    info_url='https://erhvervsstyrelsen.dk/vejledning-teknisk-vejledning-og-dokumentation-regnskab-20-taksonomier-aktuelle',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/DBA'}),
    shards=4,
)
