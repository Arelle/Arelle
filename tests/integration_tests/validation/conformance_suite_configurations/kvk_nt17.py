from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

ZIP_PATH = Path("NT17_KVK_20221214 Berichten.zip")
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            ZIP_PATH,
            entry_point=Path("berichten/NT17_KVK_20221214 - Testsuite.zip/testcases.xml"),
            public_download_url="https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT17_KVK_20221214%20Berichten.zip",
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_PACKAGES["NT17"],
    ],
    base_taxonomy_validation="none",
    disclosure_system="NT17",
    info_url="https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT17%20-%2020220301__.pdf",
    name=PurePath(__file__).stem,
    plugins=frozenset({"validate/NL"}),
    shards=8,
)
