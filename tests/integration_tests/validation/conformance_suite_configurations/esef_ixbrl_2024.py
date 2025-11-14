from pathlib import Path, PurePath

from tests.integration_tests.validation.assets import ESEF_PACKAGES, LEI_2020_07_02
from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

# needs to be extracted because arelle can't load a taxonomy package ZIP from within a ZIP
ZIP_PATH = Path('esef_conformance_suite_2024.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH,
            entry_point=Path('esef_conformance_suite_2024/index_inline_xbrl.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/2025-01/esef_conformance_suite_2024.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ] + [
        package for year in [2017, 2019, 2020, 2021, 2022, 2024] for package in ESEF_PACKAGES[year]
    ],
    base_taxonomy_validation='none',
    disclosure_system='esef-2024',
    expected_additional_testcase_errors={f"esef_conformance_suite_2024/tests/inline_xbrl/{s}": val for s, val in {
        # Typo in the test case namespace declaration: incorrectly uses the Extensible Enumeration 1 namespace with the
        # commonly used Extensible Enumeration 2 prefix: xmlns:enum2="http://xbrl.org/2014/extensible-enumerations"
        'G2-4-1_1/index.xml:TC2_valid': {
            'differentExtensionDataType': 1,
        },
    }.items()},
    expected_failure_ids=frozenset(f'tests/inline_xbrl/{s}' for s in [
        ### Discovered during transition to Test Engine:
        'G2-5-4_2/index.xml:TC2_invalid',
    ]),
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2024',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF'}),
    shards=8,
    test_case_result_options='match-any',
)
