from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('esef_conformance_suite_2021.zip'),
            entry_point=Path('esef_conformance_suite_2021/esef_conformance_suite_2021/index_pure_xhtml.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2021.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    base_taxonomy_validation='none',
    custom_compare_patterns=[
        (r"^.*$", r"^ESEF\..*\.~$"),
    ],
    disclosure_system='esef-unconsolidated-2021',
    info_url='https://www.esma.europa.eu/document/conformance-suite-2021',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF'}),
    test_case_result_options='match-any',
)
