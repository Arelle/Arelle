from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

CONFORMANCE_SUITE_ZIP_NAME = 'efm-71d-240816.zip'

config = ConformanceSuiteConfig(
    additional_plugins_by_prefix=[(f'conf/{t}', frozenset({'EDGAR/render'})) for t in [
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
    cache_version_id='LlFh0Bj7is.HV8nO2FmINd30wMJPyYEs',
    expected_failure_ids=frozenset([
        # Failures expected to be resolved when EFM 24.3 conformance suite is published.
        'conf/605-instance-syntax/605-61-cybersecurity-incident-disclosure/605-61-cybersecurity-incident-disclosure-testcase.xml:_001gd',
        'conf/622-only-supported-locations/622-01-all-supported-locations/622-01-all-supported-locations-testcase.xml:_029gd',
    ]),
    info_url='https://www.sec.gov/structureddata/osdinteractivedatatestsuite',
    name=PurePath(__file__).stem,
    plugins=frozenset({'EDGAR/validate', 'inlineXbrlDocumentSet'}),
    shards=40,
    test_case_result_options='match-any',
)
