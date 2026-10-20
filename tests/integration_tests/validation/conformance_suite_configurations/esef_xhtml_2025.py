from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

ZIP_PATH = Path("esef_conformance_suite_2025.zip")
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            ZIP_PATH,
            entry_point=Path("esef_conformance_suite_2025/index_pure_xhtml.xml"),
            public_download_url="https://www.esma.europa.eu/sites/default/files/2026-04/esef_conformance_suite_2025.zip",
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    base_taxonomy_validation="none",
    disclosure_system="esef-unconsolidated-2025",
    info_url="https://www.esma.europa.eu/document/esef-conformance-suite-2025",
    name=PurePath(__file__).stem,
    plugins=frozenset({"validate/ESEF"}),
    test_case_result_options="match-any",
)
