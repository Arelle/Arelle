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
        ### Discovered during transition to Test Engine:
        # Related to EFM.FT.1.2.12.r424iEndDate not firing
        'filing-fee-exhibit/100-submissionTable/02-424ISubmissions/12-RptgFsclYrEndDt/12-RptgFsclYrEndDt-testcase.xml:0003ng',
        # Related to EFM.FT.3.8.8.dailyFeeRate not firing
        'filing-fee-exhibit/300-offeringTable/08-Rule0-11/08-FeeRate/08-FeeRate-testcase.xml:0002gw',
        'filing-fee-exhibit/300-offeringTable/08-Rule0-11/08-FeeRate/08-FeeRate-testcase.xml:0004gw',
        'filing-fee-exhibit/300-offeringTable/08-Rule0-11/08-FeeRate/08-FeeRate-testcase.xml:0006gw',
        'filing-fee-exhibit/300-offeringTable/08-Rule0-11/08-FeeRate/08-FeeRate-testcase.xml:0009gw',
    ]),
    info_url='https://www.sec.gov/structureddata/osdinteractivedatatestsuite',
    name=PurePath(__file__).stem,
    plugins=frozenset({
        'EDGAR/validate',
        'inlineXbrlDocumentSet',
        'xule',
    }),
    runtime_options={
        'pluginOptions': {
            'keepFilingOpen': True, # Edgar normally closes the model in CntlrCmdLine.Filing.End
        },
    },
    shards=40,
    test_case_result_options='match-any',
)
