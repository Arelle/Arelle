from pathlib import PurePath, Path

from arelle.testengine.ErrorLevel import ErrorLevel
from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource, CiConfig

ZIP_PATH = Path('NT17_KVK_20221214 Berichten.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'berichten' / 'NT17_KVK_20221214 - Testsuite.zip',
            entry_point=Path('testcases.xml'),
            public_download_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT17_KVK_20221214%20Berichten.zip',
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_PACKAGES['NT17'],
    ],
    base_taxonomy_validation='none',
    ci_config=CiConfig(shard_count=2),
    disclosure_system='NT17',
    ignore_levels=frozenset({
        ErrorLevel.NOT_SATISFIED,
        ErrorLevel.OK,
        ErrorLevel.WARNING,
    }),
    info_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT17%20-%2020220301__.pdf',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
)
