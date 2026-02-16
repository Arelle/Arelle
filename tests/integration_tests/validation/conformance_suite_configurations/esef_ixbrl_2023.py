from pathlib import PurePath, Path

from arelle.testengine.TestcaseSet import TestcaseSet
from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource, CiConfig
)
from tests.integration_tests.validation.preprocessing_util import swap_read_first_uri

ZIP_PATH = Path('esef_conformance_suite_2023.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)


def _preprocessing_func(config: ConformanceSuiteConfig, testcase_set: TestcaseSet) -> TestcaseSet:
    read_first_uri_swaps: dict[tuple[str, tuple[str, ...]], tuple[str, ...]] = {
        ('tests/inline_xbrl/G2-6-1_3/index.xml:TC2_invalid', ('TC2_invalid.zip',)):  ('TC2_invalid.xbr',),
        ('tests/inline_xbrl/G2-6-1_3/index.xml:TC3_invalid', ('TC3_invalid.zip',)):  ('TC3_invalid.xbri',),
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
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH,
            entry_point=Path('index_inline_xbrl.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/2023-12/esef_conformance_suite_2023.zip',
            source=AssetSource.S3_PUBLIC,
        )
    ] + [
        package for year in [2017, 2019, 2020, 2021, 2022] for package in ESEF_PACKAGES[year]
    ],
    base_taxonomy_validation='none',
    ci_config=CiConfig(shard_count=2),
    custom_compare_patterns=[
        (r"^.*$", r"^ESEF\..*\.~$"),
    ],
    disclosure_system='esef-2023',
    expected_additional_testcase_errors={f'tests/inline_xbrl/{s}': val for s, val in {
        'G3-1-2/index.xml:TC2_valid': {
            'ESEF.3.2.2.domainMemberWrongDataType': 1,
        },
        'RTS_Annex_IV_Par_12_G2-2-4/index.xml:TC5_valid': {
            'message:tech_duplicated_facts1': 2,
        },
    }.items()},
    expected_failure_ids=frozenset(f'tests/inline_xbrl/{s}' for s in [
        # disallowedReportPackageFileExtension not firing
        'G2-6-1_3/index.xml:TC2_invalid',

        ### Discovered during transition to Test Engine:
        # Related to reportIncorrectlyPlacedInPackage not firing
        'G2-6-2/index.xml:TC2_invalid',
        # Related to missingOrInvalidTaxonomyPackage not firing
        'RTS_Annex_III_Par_3_G3-1-3/index.xml:TC3_invalid',
        'RTS_Annex_III_Par_3_G3-1-3/index.xml:TC5_invalid',
    ]),
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2023',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF'}),
    preprocessing_func=_preprocessing_func,
    test_case_result_options='match-any',
)
