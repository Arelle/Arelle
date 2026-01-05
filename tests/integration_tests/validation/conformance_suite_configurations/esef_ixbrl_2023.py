from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource, CONFORMANCE_SUITE_PATH_PREFIX
)

# needs to be extracted because arelle can't load a taxonomy package ZIP from within a ZIP
ZIP_PATH = Path('esef_conformance_suite_2023.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)


def _preprocessing_func(config: ConformanceSuiteConfig) -> None:
    with open(
            Path(CONFORMANCE_SUITE_PATH_PREFIX) /
            EXTRACTED_PATH /
            'tests/inline_xbrl/G2-6-1_3/index.xml',
            'r+'
    ) as f:
        content = f.read()
        # Test case references TC2_invalid.zip, but actual file in suite has .xbr extension.
        content = content.replace('TC2_invalid.zip', 'TC2_invalid.xbr')
        # Test case references TC3_invalid.zip, but actual file in suite has .xbri extension.
        content = content.replace('TC3_invalid.zip', 'TC3_invalid.xbri')
        f.seek(0)
        f.write(content)
        f.truncate()


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
    shards=8,
    test_case_result_options='match-any',
)
