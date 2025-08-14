from pathlib import Path, PurePath

from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource, ConformanceSuiteConfig, ConformanceSuiteAssetConfig
)


ZIP_PATH = Path('uksef-conformance-suite-v2.0.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    args=[
        '--baseTaxonomyValidation', 'none',
        '--formula', 'none',
    ],
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'uksef-conformance-suite-v2.0' / 'uksef-conformance-suite-v2.0.zip',
            entry_point=Path('uksef-conformance-suite/index.xml'),
            public_download_url='https://www.frc.org.uk/documents/8116/uksef-conformance-suite-v2.0.zip',
            source=AssetSource.S3_PUBLIC,
        ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('The_2023_Taxonomy_suite_v1.0.1.zip'),
            public_download_url='https://www.frc.org.uk/documents/372/The_2023_Taxonomy_suite_v1.0.1.zip',
        ),
    ] + [
        package for year in [2022, 2024] for package in ESEF_PACKAGES[year]
    ],
    expected_additional_testcase_errors={f'uksef-conformance-suite/tests/FRC/{s}': val for s, val in {
        # Test case references TC2_valid.zip, but actual file in suite has .xbri extension.
        'FRC_09/index.xml:TC2_valid': {'IOerror': 1},
        # Test case references TC3_valid.zip, but actual file in suite has .xbri extension.
        'FRC_09/index.xml:TC3_valid': {'IOerror': 1},
        # Report package uses CR document type URI instead of rec URI.
        'FRC_09/index.xml:TC4_valid': {'rpe:unsupportedReportPackageVersion': 1},
    }.items()},
    expected_failure_ids=frozenset({f'uksef-conformance-suite/tests/FRC/{s}' for s in [
        # FRC XBRL Tagging Guide not yet implemented.
        'FRC_01/index.xml:TC6_invalid',
        'FRC_01/index.xml:TC7_invalid',
        'FRC_01/index.xml:TC8_invalid',
        'FRC_01/index.xml:TC9_invalid',
        'FRC_02/index.xml:TC3_invalid',
        'FRC_03/index.xml:TC2_invalid',
        'FRC_03/index.xml:TC3_invalid',
        'FRC_03/index.xml:TC4_invalid',
        'FRC_04/index.xml:TC2_invalid',
        'FRC_05/index.xml:TC4_invalid',
        'FRC_05/index.xml:TC5_invalid',
        'FRC_05/index.xml:TC6_invalid',
        'FRC_06/index.xml:TC2_invalid',
        'FRC_06/index.xml:TC3_invalid',
        'FRC_07/index.xml:TC2_invalid',
        'FRC_07/index.xml:TC3_invalid',
        'FRC_07/index.xml:TC4_invalid',
        'FRC_08/index.xml:TC2_invalid',
        'FRC_08/index.xml:TC3_invalid',
        'FRC_09/index.xml:TC6_invalid',
        'FRC_10/index.xml:TC3_invalid',
        'FRC_10/index.xml:TC4_invalid',
        'FRC_10/index.xml:TC5_invalid',
        'FRC_10/index.xml:TC6_invalid',
        'FRC_11/index.xml:TC2_invalid',
        'FRC_11/index.xml:TC3_invalid',
        'FRC_12/index.xml:TC3_invalid',
        'FRC_13/index.xml:TC2_invalid',
        'FRC_13/index.xml:TC3_invalid',
        'FRC_14/index.xml:TC4_invalid',
        'FRC_14/index.xml:TC5_invalid',
        'FRC_14/index.xml:TC6_invalid',
        'FRC_14/index.xml:TC7_invalid',
        'FRC_15/index.xml:TC2_invalid',
        'FRC_15/index.xml:TC3_invalid',
        'FRC_15/index.xml:TC4_invalid',
        'FRC_16/index.xml:TC2_invalid',
        'FRC_17/index.xml:TC2_invalid',
        'FRC_17/index.xml:TC3_invalid',
        'FRC_18/index.xml:TC3_invalid',
        'FRC_18/index.xml:TC4_invalid',
        'FRC_19/index.xml:TC2_invalid',
        'FRC_20/index.xml:TC3_invalid',
        'FRC_21/index.xml:TC2_invalid',
        'FRC_21/index.xml:TC3_invalid',
    ]}),
    info_url='https://www.frc.org.uk/library/standards-codes-policy/accounting-and-reporting/frc-taxonomies/frc-taxonomies-documentation-and-guidance/',
    name=PurePath(__file__).stem,
    plugins=frozenset({'inlineXbrlDocumentSet'}),
    shards=4,
)
