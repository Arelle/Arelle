from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource
)

# needs to be extracted because arelle can't load a taxonomy package ZIP from within a ZIP
ZIP_PATH = Path('esef_conformance_suite_2021.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH,
            entry_point=Path('esef_conformance_suite_2021/esef_conformance_suite_2021/index_inline_xbrl.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2021.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ] + [
        package for year in [2017, 2019, 2020, 2021] for package in ESEF_PACKAGES[year]
    ],
    base_taxonomy_validation='none',
    disclosure_system='esef-2021',
    expected_failure_ids=frozenset(f'esef_conformance_suite_2021/esef_conformance_suite_2021/tests/{s}' for s in [
        ### Discovered during transition to Test Engine:
        # Related to reportIncorrectlyPlacedInPackage not firing
        'inline_xbrl/G2-6-2/index.xml:TC2_invalid',
        # Related to missingOrInvalidTaxonomyPackage not firing
        'inline_xbrl/RTS_Annex_III_Par_3_G3-1-3/index.xml:TC3_invalid',
        'inline_xbrl/RTS_Annex_III_Par_3_G3-1-3/index.xml:TC5_invalid',
    ]),
    info_url='https://www.esma.europa.eu/document/conformance-suite-2021',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF'}),
    shards=8,
    test_case_result_options='match-any',
)
