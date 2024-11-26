from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

CONFORMANCE_SUITE_ZIP_NAME = 'efm-72d-241118.zip'

config = ConformanceSuiteConfig(
    additional_plugins_by_prefix=[(f'conf/{t}', frozenset({'EDGAR/render'})) for t in [
        '612-presentation-syntax/612-09-presented-units-order',
        '624-rendering/15-equity-changes',
        '624-rendering/17-uncategorized-facts',
        '626-rendering-syntax',
        '902-sdr/efm/62421-sdr-multiple',
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
    cache_version_id='9Ca6hY9zrS6rB1G_YL32Ss6_Nlb9Mz2x',
    expected_failure_ids=frozenset(f'conf/{s}' for s in [
        # Expected to pass with EDGAR 24.4.
        '622-only-supported-locations/622-01-all-supported-locations/622-01-all-supported-locations-testcase.xml:_031gd',
        '622-only-supported-locations/622-03-consistent-locations/622-03-consistent-locations-testcase.xml:_119ng',
    ]),
    info_url='https://www.sec.gov/structureddata/osdinteractivedatatestsuite',
    name=PurePath(__file__).stem,
    plugins=frozenset({'EDGAR/validate', 'inlineXbrlDocumentSet'}),
    shards=40,
    test_case_result_options='match-any',
)
