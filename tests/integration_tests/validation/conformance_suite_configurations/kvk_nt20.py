from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

ZIP_PATH = Path("NT20_KVK_20251210 Berichten.zip")
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            ZIP_PATH,
            entry_point=Path("berichten/NT20_KVK_20251210 - Testsuite.zip/testcases.xml"),
            public_download_url="https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT20_KVK_20251210%20Berichten.zip",
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_PACKAGES["NT20"],
    ],
    base_taxonomy_validation="none",
    disclosure_system="NT20",
    info_url="https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/20251119%20SBR%20Filing%20Rules%20NT20_v1_1.pdf",
    name=PurePath(__file__).stem,
    plugins=frozenset({"validate/NL"}),
    shards=8,
)
