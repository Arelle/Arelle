from pathlib import Path, PurePath

from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

ZIP_PATH = Path('esef_conformance_suite_2025.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'esef_conformance_suite_2025',
            entry_point=Path('index_inline_xbrl.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/2026-04/esef_conformance_suite_2025.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ] + [
        package for year in [2017, 2019, 2020, 2021, 2022, 2024, 2025] for package in ESEF_PACKAGES[year]
    ],
    base_taxonomy_validation='none',
    disclosure_system='esef-2025',
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2025',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF'}),
    shards=8,
    test_case_result_options='match-any',
)
