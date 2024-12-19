from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-unconsolidated-2021',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('esef_conformance_suite_2021.zip'),
            entry_point=Path('esef_conformance_suite_2021/esef_conformance_suite_2021/index_pure_xhtml.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2021.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    info_url='https://www.esma.europa.eu/document/conformance-suite-2021',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/ESEF'}),
    test_case_result_options='match-any',
)
