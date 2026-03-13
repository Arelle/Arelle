from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

CONFORMANCE_SUITE_ZIP_NAME = 'efm-76-251010.zip'

config = ConformanceSuiteConfig(
    additional_plugins_by_prefix=[(f'conf/{t}', frozenset({'EDGAR/render'})) for t in [
        '612-presentation-syntax/612-09-presented-units-order/',
        '624-rendering/15-equity-changes/',
        '624-rendering/17-uncategorized-facts/',
        '626-rendering-syntax/',
        '902-sdr/efm/62421-sdr-multiple/',
    ]],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path(CONFORMANCE_SUITE_ZIP_NAME),
            entry_point=Path('conf/testcases.xml'),
            public_download_url=f'https://www.sec.gov/files/edgar/{CONFORMANCE_SUITE_ZIP_NAME}',
            source=AssetSource.S3_PUBLIC,
        )
    ],
    cache_version_id='ShpWxxspdHtuQbCApZ2bwkO7.t66OMa3',
    disclosure_system='efm-pragmatic',
    # Failures expected to be resolved when EFM 26.1 conformance suite is published.
    expected_additional_testcase_errors={
        'conf/622-only-supported-locations/622-01-all-supported-locations/622-01-all-supported-locations-testcase.xml:_046gd': {
            'DQC.US.0159.10081': 1,
        },
        'conf/624-rendering/09-start-end-labels/gd/09-start-end-labels-gd-testcase.xml:_002gd': {
            'DQC.US.0159.10081': 1,
        },
    },
    info_url='https://www.sec.gov/structureddata/osdinteractivedatatestsuite',
    name=PurePath(__file__).stem,
    plugins=frozenset({
        'EDGAR/validate',
        'inlineXbrlDocumentSet',
        'xule',
    }),
    shards=40,
    test_case_result_options='match-any',
)
