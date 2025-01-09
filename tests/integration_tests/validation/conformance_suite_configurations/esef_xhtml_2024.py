from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-unconsolidated-2024',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('esef_conformance_suite_2024.zip'),
            entry_point=Path('esef_conformance_suite_2024/index_pure_xhtml.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/2025-01/esef_conformance_suite_2024.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2024',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/ESEF'}),
    test_case_result_options='match-any',
)
