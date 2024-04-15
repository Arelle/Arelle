from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-unconsolidated-2023',
        '--formula', 'none',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('esef_conformance_suite_2023.zip'),
            entry_point=Path('index_pure_xhtml.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/2023-12/esef_conformance_suite_2023.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2023',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/ESEF'}),
    test_case_result_options='match-any',
)
