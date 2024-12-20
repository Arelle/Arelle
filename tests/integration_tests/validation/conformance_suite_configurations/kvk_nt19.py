from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

ZIP_PATH = Path('NT19_KVK_20241211 Berichten.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT19',
    ],
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'berichten' / 'NT19_KVK_20241211 - Testsuite.zip',
            entry_point=Path('testcases.xml'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT19_KVK_20241211%20Berichten.zip',
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_PACKAGES['NT19'],
    ],
    info_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/20240301%20SBR%20Filing%20Rules%20NT19.pdf',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/NL'}),
    shards=8,
)
