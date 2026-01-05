from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

ZIP_PATH = Path('NT20_KVK_20251210 Berichten.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT20',
        '--baseTaxonomyValidation', 'none',
    ],
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'berichten' / 'NT20_KVK_20251210 - Testsuite.zip',
            entry_point=Path('testcases.xml'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT20_KVK_20251210%20Berichten.zip',
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_PACKAGES['NT20'],
    ],
    info_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/20251119%20SBR%20Filing%20Rules%20NT20_v1_1.pdf',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    shards=8,
)
