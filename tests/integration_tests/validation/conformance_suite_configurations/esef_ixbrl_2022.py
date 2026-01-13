from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource
)

ZIP_PATH = Path('esef_conformance_suite_2022.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'esef_conformance_suite_2022',
            entry_point=Path('index_inline_xbrl.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2022.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ] + [
        package for year in [2017, 2019, 2020, 2021, 2022] for package in ESEF_PACKAGES[year]
    ],
    base_taxonomy_validation='none',
    disclosure_system='esef-2022',
    expected_failure_ids=frozenset(f'tests/{s}' for s in [
        # The following test cases fail because of the `tech_duplicated_facts1` formula which fires
        # incorrectly because it does not take into account the language attribute on the fact.
        # A fact can not be a duplicate fact if the language attributes are different.
        'inline_xbrl/RTS_Annex_IV_Par_12_G2-2-4/index.xml:TC5_valid'
    ]),
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2022',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF'}),
    shards=8,
    test_case_result_options='match-any',
)
