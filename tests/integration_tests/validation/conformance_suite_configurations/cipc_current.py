from pathlib import PurePath, Path
from tests.integration_tests.validation.assets import LEI_2020_07_02
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('cipc'),
            entry_point=Path('index.xml'),
        ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('cipc_2024-05-29.zip'),
            public_download_url='https://www.cipc.co.za/wp-content/uploads/2024/06/cipc_2024-05-29.zip',
        ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('IFRSAT_2023_03_23.zip'),
            public_download_url='https://www.ifrs.org/content/dam/ifrs/standards/taxonomy/ifrs-taxonomies/IFRSAT_2023_03_23.zip',
        ),
        LEI_2020_07_02,
    ],
    base_taxonomy_validation='none',
    disclosure_system='cipc',
    info_url='https://www.cipc.co.za/?page_id=4400',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/CIPC'}),
)
