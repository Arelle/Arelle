from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

CONFORMANCE_SUITE_ZIP_NAME = 'efm-70-240701.zip'

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
            Path(CONFORMANCE_SUITE_ZIP_NAME),
            entry_point=Path('conf/testcases.xml'),
            public_download_url=f'https://www.sec.gov/files/edgar/{CONFORMANCE_SUITE_ZIP_NAME}',
            source=AssetSource.S3_PUBLIC,
        )
    ],
    cache_version_id='C5EhkW8aZ5CzXQ6Lvj8K8ezEYGYGoHUK',
    expected_failure_ids=frozenset([
        # Duplicated schema error. Extensible Enumerations 2.0 schema is accessed over http and https.
        'conf/622-only-supported-locations/622-01-all-supported-locations/622-01-all-supported-locations-testcase.xml:_010gd'
    ]),
    info_url='https://www.sec.gov/structureddata/osdinteractivedatatestsuite',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/EFM', 'inlineXbrlDocumentSet'}),
    shards=40,
    test_case_result_options='match-any',
)
