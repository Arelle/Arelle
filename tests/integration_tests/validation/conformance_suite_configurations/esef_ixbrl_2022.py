from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource, CiConfig
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
    ci_config=CiConfig(shard_count=2),
    custom_compare_patterns=[
        (r"^.*$", r"^ESEF\..*\.~$"),
    ],
    disclosure_system='esef-2022',
    expected_additional_testcase_errors={f'tests/{s}': val for s, val in {
        'inline_xbrl/RTS_Annex_IV_Par_12_G2-2-4/index.xml:TC5_valid': {
            'message:tech_duplicated_facts1': 2,
        },
    }.items()},
    expected_failure_ids=frozenset(f'tests/{s}' for s in [
        ### Discovered during transition to Test Engine:
        # Related to reportIncorrectlyPlacedInPackage not firing
        'inline_xbrl/G2-6-2/index.xml:TC2_invalid',
        # Related to missingOrInvalidTaxonomyPackage not firing
        'inline_xbrl/RTS_Annex_III_Par_3_G3-1-3/index.xml:TC3_invalid',
        'inline_xbrl/RTS_Annex_III_Par_3_G3-1-3/index.xml:TC5_invalid',
    ]),
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2022',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF'}),
    test_case_result_options='match-any',
)
