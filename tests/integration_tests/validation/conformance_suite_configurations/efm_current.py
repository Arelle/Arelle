from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

CONFORMANCE_SUITE_ZIP_NAME = 'efm-76-251010.zip'

config = ConformanceSuiteConfig(
    additional_plugins_by_prefix=[(f'conf/{t}', frozenset({'EDGAR/render'})) for t in [
        '612-presentation-syntax/612-09-presented-units-order',
        '624-rendering/15-equity-changes',
        '624-rendering/17-uncategorized-facts',
        '626-rendering-syntax',
        '902-sdr/efm/62421-sdr-multiple',
    ]],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path(CONFORMANCE_SUITE_ZIP_NAME),
            entry_point=Path('conf/testcases.xml'),
            public_download_url=f'https://www.sec.gov/files/edgar/{CONFORMANCE_SUITE_ZIP_NAME}',
            source=AssetSource.S3_PUBLIC,
        )
    ],
    cache_version_id='bY6OmURBAtPB4UALKzz5aeeLlMSKxN9e',
    disclosure_system='efm-pragmatic',
    expected_failure_ids=frozenset(f'conf/{s}' for s in [
        # Next EFM update will resolve this by checking contexts not mapped to target documents.
        '605-instance-syntax/605-08-no-unused-contexts/605-08-no-unused-contexts-testcase.xml:_002ng',
        
        ### Discovered during transition to Test Engine:
        # Related to EFM.6.05.23.submissionIdentifier not firing
        'filing-fee-exhibit/000-userstories/00-other/00-userstories/00-userstories-testcase.xml:0016ng',
        'filing-fee-exhibit/000-userstories/00-other/00-userstories/00-userstories-testcase.xml:0008ng',
        'filing-fee-exhibit/000-userstories/00-other/00-userstories/00-userstories-testcase.xml:0044ng',
        'filing-fee-exhibit/000-userstories/00-other/00-userstories/00-userstories-testcase.xml:0024ng',
        'filing-fee-exhibit/000-userstories/00-other/00-userstories/00-userstories-testcase.xml:0041ng',
        'filing-fee-exhibit/000-userstories/00-other/00-userstories/00-userstories-testcase.xml:0049ng',
        # Related to EFM.FT.3.8.8.dailyFeeRate not firing
        'filing-fee-exhibit/300-offeringTable/08-Rule0-11/08-FeeRate/08-FeeRate-testcase.xml:0004gw',
    ]),
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
