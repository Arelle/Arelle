from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-unconsolidated-2022',
        '--formula', 'none',
    ],
    file='esef_conformance_suite_2022/index_pure_xhtml.xml',
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('esef_conformance_suite_2022.zip'),
            entry_point=Path('esef_conformance_suite_2022/index_pure_xhtml.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2022.zip',
        ),
    ],
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2022',
    local_filepath='esef_conformance_suite_2022.zip',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/ESEF'}),
    public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2022.zip',
    test_case_result_options='match-any',
)
