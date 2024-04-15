from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource
)
config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-2023',
        '--formula', 'run',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('esef_conformance_suite_2023.zip'),
            entry_point=Path('index_inline_xbrl.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/2023-12/esef_conformance_suite_2023.zip',
            source=AssetSource.S3_PUBLIC,
        )
    ] + [
        package for year in [2017, 2019, 2020, 2021, 2022] for package in ESEF_PACKAGES[year]
    ],
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
    network_or_cache_required=False,
    plugins=frozenset({'validate/ESEF'}),
    shards=8,
    test_case_result_options='match-any',
)
