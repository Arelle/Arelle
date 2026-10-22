from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

ZIP_PATH = Path("NT19_KVK_20241211 Berichten.zip")
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            ZIP_PATH,
            entry_point=Path("berichten/NT19_KVK_20241211 - Testsuite.zip/testcases.xml"),
            public_download_url="https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT19_KVK_20241211%20Berichten.zip",
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_PACKAGES["NT19"],
    ],
    base_taxonomy_validation="none",
    disclosure_system="NT19",
    info_url="https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/20240301%20SBR%20Filing%20Rules%20NT19.pdf",
    name=PurePath(__file__).stem,
    plugins=frozenset({"validate/NL"}),
    shards=8,
)
