from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

CONFORMANCE_SUITE_ZIP_NAME = 'efm-73-250317.zip'

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
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path(CONFORMANCE_SUITE_ZIP_NAME),
            entry_point=Path('conf/testcases.xml'),
            public_download_url=f'https://www.sec.gov/files/edgar/{CONFORMANCE_SUITE_ZIP_NAME}',
            source=AssetSource.S3_PUBLIC,
        )
    ],
    cache_version_id='D6XVsgj8noOk9wzCTX91wqwQFq68d0bi',
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
