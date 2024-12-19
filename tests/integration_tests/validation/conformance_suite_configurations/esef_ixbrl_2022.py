from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource
)
config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-2022',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('esef_conformance_suite_2022.zip'),
            entry_point=Path('esef_conformance_suite_2022/index_inline_xbrl.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2022.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ] + [
        package for year in [2017, 2019, 2020, 2021, 2022] for package in ESEF_PACKAGES[year]
    ],
    expected_failure_ids=frozenset(f'esef_conformance_suite_2022/tests/{s}' for s in [
        # The following test cases fail because of the `tech_duplicated_facts1` formula which fires
        # incorrectly because it does not take into account the language attribute on the fact.
        # A fact can not be a duplicate fact if the language attributes are different.
        'inline_xbrl/RTS_Annex_IV_Par_12_G2-2-4/index.xml:TC5_valid'
    ]),
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2022',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/ESEF'}),
    shards=8,
    test_case_result_options='match-any',
)
