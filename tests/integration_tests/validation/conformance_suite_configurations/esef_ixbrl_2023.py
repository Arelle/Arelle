from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource
)

ZIP_PATH = Path('esef_conformance_suite_2023.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
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
    expected_failure_ids=frozenset(f'tests/inline_xbrl/{s}' for s in [
        # Test report uses older domain item type (http://www.xbrl.org/dtr/type/non-numeric) forbidden by ESEF.3.2.2.
        'G3-1-2/index.xml:TC2_valid',
        # These tests reference zip files, which do not exist in the conformance suite.
        'G2-6-1_3/index.xml:TC2_invalid',
        'G2-6-1_3/index.xml:TC3_invalid',
        # The following test case fails because of the `tech_duplicated_facts1` formula, which incorrectly fires.
        # It does not take into account the language attribute on the fact.
        # Facts are not duplicates if their language attributes are different.
        'RTS_Annex_IV_Par_12_G2-2-4/index.xml:TC5_valid',
    ]),
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2023',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF'}),
    shards=8,
    test_case_result_options='match-any',
)
