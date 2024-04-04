from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    additional_plugins_by_prefix=[(f'conf/{t}', frozenset({'EdgarRenderer'})) for t in [
        '612-presentation-syntax/612-09-presented-units-order',
        '626-rendering-syntax',
    ]],
    args=[
        '--disclosureSystem', 'efm-pragmatic',
        '--formula', 'run',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('efm-69-240318.zip'),
            entry_point=Path('conf/testcases.xml'),
            public_download_url='https://www.sec.gov/files/edgar/efm-69-240318.zip',
        )
    ],
    cache_version_id='p7LKRmAEYKJ8jIxUUWMpYFzZjH2DD78u',
    file='conf/testcases.xml',
    info_url='https://www.sec.gov/structureddata/osdinteractivedatatestsuite',
    local_filepath='efm-69-240318.zip',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/EFM', 'inlineXbrlDocumentSet'}),
    public_download_url='https://www.sec.gov/files/edgar/efm-69-240318.zip',
    shards=40,
    test_case_result_options='match-any',
)
