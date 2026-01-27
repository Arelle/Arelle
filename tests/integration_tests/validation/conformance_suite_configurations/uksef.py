from pathlib import Path, PurePath

from arelle.testengine.TestcaseSet import TestcaseSet
from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource, ConformanceSuiteConfig, ConformanceSuiteAssetConfig, CiConfig
)
from tests.integration_tests.validation.preprocessing_util import swap_read_first_uri

ZIP_PATH = Path('uksef-conformance-suite-v2.0.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
EXTRACTED_ZIP_PATH = EXTRACTED_PATH / 'uksef-conformance-suite-v2.0' / 'uksef-conformance-suite-v2.0.zip'
EXTRACTED_EXTRACTED_PATH = Path(EXTRACTED_ZIP_PATH.parent) / EXTRACTED_ZIP_PATH.stem


def _preprocessing_func(config: ConformanceSuiteConfig, testcase_set: TestcaseSet) -> TestcaseSet:
    read_first_uri_swaps: dict[tuple[str, tuple[str, ...]], tuple[str, ...]] = {
        ('tests/FRC/FRC_09/index.xml:TC2_valid', ('TC2_valid.zip',)):  ('TC2_valid.xbri',),
        ('tests/FRC/FRC_09/index.xml:TC3_valid', ('TC3_valid.zip',)):  ('TC3_valid.xbri',),
    }
    testcases = [
        swap_read_first_uri(testcase, read_first_uri_swaps)
        for testcase in testcase_set.testcases
    ]
    assert not read_first_uri_swaps, \
        f'Some URI replacements were not applied: {read_first_uri_swaps}'
    return TestcaseSet(
        load_errors=testcase_set.load_errors,
        skipped_testcases=testcase_set.skipped_testcases,
        testcases=testcases,
    )


config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.extracted_conformance_suite(
            (
                (ZIP_PATH, EXTRACTED_PATH),
                (EXTRACTED_ZIP_PATH, EXTRACTED_EXTRACTED_PATH),
            ),
            entry_point_root=EXTRACTED_EXTRACTED_PATH / "uksef-conformance-suite",
            entry_point=Path('index.xml'),
            public_download_url='https://www.frc.org.uk/documents/8116/uksef-conformance-suite-v2.0.zip',
            source=AssetSource.S3_PUBLIC,
        ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('The_2023_Taxonomy_suite_v1.0.1.zip'),
            public_download_url='https://www.frc.org.uk/documents/372/The_2023_Taxonomy_suite_v1.0.1.zip',
        ),
       ConformanceSuiteAssetConfig.public_taxonomy_package(
           Path('FRC-2024-Taxonomy-v1.0.0_GJp67Do.zip'),
           public_download_url='https://www.frc.org.uk/documents/6566/FRC-2024-Taxonomy-v1.0.0_GJp67Do.zip',
       ),
        ConformanceSuiteAssetConfig.public_taxonomy_package(
            Path('FRC-2025-Taxonomy-v1.0.0_LK4mek8.zip'),
            public_download_url='https://www.frc.org.uk/documents/7759/FRC-2025-Taxonomy-v1.0.0_LK4mek8.zip',
        ),
    ] + [
        package for year in [2022, 2024] for package in ESEF_PACKAGES[year]
    ],
    base_taxonomy_validation='none',
    ci_config=CiConfig(fast=False),
    expected_additional_testcase_errors={f'tests/FRC/{s}': val for s, val in {
        # Invalid documentType https://xbrl.org/report-package/CR/2023-05-03/xbri
        'FRC_09/index.xml:TC2_valid': {
            'rpe:unsupportedReportPackageVersion': 1,
        },
        # Invalid documentType https://xbrl.org/report-package/CR/2023-05-03
        'FRC_09/index.xml:TC4_valid': {
            'rpe:unsupportedReportPackageVersion': 1,
        },
    }.items()},
    expected_failure_ids=frozenset({f'tests/FRC/{s}' for s in [
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
    preprocessing_func=_preprocessing_func,
    runtime_options={
        'formulaAction': 'none',
    },
)
