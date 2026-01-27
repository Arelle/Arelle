from pathlib import Path, PurePath

from tests.integration_tests.validation.assets import ESEF_PACKAGES, LEI_2020_07_02
from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig, CiConfig,
)

ZIP_PATH = Path('esef_conformance_suite_2024.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'esef_conformance_suite_2024',
            entry_point=Path('index_inline_xbrl.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/2025-01/esef_conformance_suite_2024.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ] + [
        package for year in [2017, 2019, 2020, 2021, 2022, 2024] for package in ESEF_PACKAGES[year]
    ],
    base_taxonomy_validation='none',
    ci_config=CiConfig(shard_count=2),
    custom_compare_patterns=[
        (r"^.*$", r"^ESEF\..*\.~$"),
    ],
    disclosure_system='esef-2024',
    expected_additional_testcase_errors={f"tests/inline_xbrl/{s}": val for s, val in {
        # Typo in the test case namespace declaration: incorrectly uses the Extensible Enumeration 1 namespace with the
        # commonly used Extensible Enumeration 2 prefix: xmlns:enum2="http://xbrl.org/2014/extensible-enumerations"
        'G2-4-1_1/index.xml:TC2_valid': {
            'differentExtensionDataType': 1,
        },
        # Passed due to special logic in the old testcase variation runner
        'G2-5-4_2/index.xml:TC1_valid': {
            'ESEF.2.5.4.externalCssFileForSingleIXbrlDocument': 1,
            'ESEF.2.7.1.targetXBRLDocumentWithFormulaWarnings': 1,
            'ESEF.3.4.6.UsableConceptsNotAppliedByTaggedFacts': 1,
            'ESEF.RTS.Annex.III.Par.1.invalidInlineXBRL': 1,
            'ESEF.RTS.ifrsRequired': 1,
            'ix11.12.1.2:missingReferenceTargets': 1,
            'ix11.12.1.2:missingReferences': 46,
            'ix11.14.1.2:missingResources': 1,
            'ix11.8.1.3:headerMissing': 1,
            'ix11.8.1.3:missingHeader': 1,
            'message:con_ComparativeReportingPeriodMustBePresentDuration': 1,
            'message:con_ComparativeReportingPeriodMustBePresentInstant': 1,
            'rpe:multipleReports': 1,
        }
    }.items()},
    expected_failure_ids=frozenset(f'tests/inline_xbrl/{s}' for s in [
        ### Discovered during transition to Test Engine:
        'G2-5-4_2/index.xml:TC2_invalid',
    ]),
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2024',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF'}),
    test_case_result_options='match-any',
)
