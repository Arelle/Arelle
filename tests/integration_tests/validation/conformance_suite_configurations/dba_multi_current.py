from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('dba_multi'),
            entry_point=Path('index.xml'),
        ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(Path('ARL-XBRL20221001-20221117.zip')),
    ],
    base_taxonomy_validation='none',
    disclosure_system='arl-2024-multi-target-preview',
    info_url='https://erhvervsstyrelsen.dk/vejledning-teknisk-vejledning-og-dokumentation-regnskab-20-taksonomier-aktuelle',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/DBA'}),
)
