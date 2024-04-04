from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'arl-2022-preview',
    ],
    file='index.xml',
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('dba'),
            entry_point=Path('index.xml'),
        ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(Path('ARL-XBRL20221001-20221117.zip')),
    ],
    info_url='https://erhvervsstyrelsen.dk/vejledning-teknisk-vejledning-og-dokumentation-regnskab-20-taksonomier-aktuelle',
    local_filepath='dba',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    packages=[
        # https://erhvervsstyrelsen.dk/sites/default/files/2022-11/XBRL20221001-20221117.zip
        'ARL-XBRL20221001-20221117.zip',
    ],
    plugins=frozenset({'validate/DBA'}),
)
