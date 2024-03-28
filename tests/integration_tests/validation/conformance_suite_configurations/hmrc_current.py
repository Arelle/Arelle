from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig


config = ConformanceSuiteConfig(
    args=[
        '--hmrc',
    ],
    file='index.xml',
    info_url='https://www.gov.uk/government/organisations/hm-revenue-customs',
    local_filepath='HMRC',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    packages=[
        # https://www.frc.org.uk/library/standards-codes-policy/accounting-and-reporting/frc-taxonomies/historical-frc-taxonomy-suites/2021-frc-taxonomy-suite/
        # https://www.frc.org.uk/documents/3923/FRC_2021_Taxonomy_v1-0-0_Zip_File.zip
        'FRC_2021_Taxonomy_v1-0-0_Zip_File.zip',
        # https://www.frc.org.uk/library/standards-codes-policy/accounting-and-reporting/frc-taxonomies/current-frc-taxonomy-suites/2023-frc-taxonomy-suite/
        # https://www.frc.org.uk/documents/372/The_2023_Taxonomy_suite_v1.0.1.zip
        'The_2023_Taxonomy_suite_v1.0.1.zip',
        # https://www.frc.org.uk/library/standards-codes-policy/accounting-and-reporting/frc-taxonomies/current-frc-taxonomy-suites/2023-frc-taxonomy-suite/
        # https://www.frc.org.uk/documents/3421/Charities_2023_Taxonomies_2023.zip
        'Charities_2023_Taxonomies_2023.zip',
    ],
    plugins=frozenset({'validate/HMRC'}),
    shards=4,
    test_case_result_options='match-any',
)
