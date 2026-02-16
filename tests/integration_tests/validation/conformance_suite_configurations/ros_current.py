from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, CiConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('ros'),
            entry_point=Path('index.xml'),
        ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('FRC-2022-Taxonomy.zip'),
            public_download_url='https://www.frc.org.uk/documents/969/FRC-2022-Taxonomy.zip',
        ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('Irish_Extension_Taxonomy_2022_Zip_file.zip'),
            public_download_url='https://www.frc.org.uk/documents/1051/Irish_Extension_Taxonomy_2022_Zip_file.zip',
        ),
    ],
    base_taxonomy_validation='none',
    ci_config=CiConfig(fast=False),
    disclosure_system='ros',
    info_url='https://www.revenue.ie/en/companies-and-charities/corporation-tax-for-companies/submitting-financial-statements/index.aspx',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ROS'}),
)
