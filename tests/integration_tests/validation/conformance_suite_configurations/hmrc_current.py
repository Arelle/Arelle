from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'hmrc',
    ],
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('HMRC'),
            entry_point=Path('index.xml'),
        ),
    ] + [
        # https://www.frc.org.uk/library/standards-codes-policy/accounting-and-reporting/frc-taxonomies/historical-frc-taxonomy-suites/2021-frc-taxonomy-suite/
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('FRC_2021_Taxonomy_v1-0-0_Zip_File.zip'),
            public_download_url='https://www.frc.org.uk/documents/3923/FRC_2021_Taxonomy_v1-0-0_Zip_File.zip'
        ),
        # https://www.frc.org.uk/library/standards-codes-policy/accounting-and-reporting/frc-taxonomies/current-frc-taxonomy-suites/2023-frc-taxonomy-suite/
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('The_2023_Taxonomy_suite_v1.0.1.zip'),
            public_download_url='https://www.frc.org.uk/documents/372/The_2023_Taxonomy_suite_v1.0.1.zip'
        ),
        # https://www.frc.org.uk/library/standards-codes-policy/accounting-and-reporting/frc-taxonomies/current-frc-taxonomy-suites/2023-frc-taxonomy-suite/
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('Charities_2023_Taxonomies_2023.zip'),
            public_download_url='https://www.frc.org.uk/documents/3421/Charities_2023_Taxonomies_2023.zip'
        ),
    ],
    info_url='https://www.gov.uk/government/organisations/hm-revenue-customs',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/UK'}),
    shards=4,
    test_case_result_options='match-any',
)
