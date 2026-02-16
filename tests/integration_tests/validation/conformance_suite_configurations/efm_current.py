from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig, CiConfig,
)

CONFORMANCE_SUITE_ZIP_NAME = 'efm-76-251010.zip'

config = ConformanceSuiteConfig(
    additional_plugins_by_prefix=[(p, frozenset({'EDGAR/render'})) for p in [
        '612-presentation-syntax/612-09-presented-units-order/',
        '624-rendering/15-equity-changes/',
        '624-rendering/17-uncategorized-facts/',
        '626-rendering-syntax/',
        # Not actually included in conformance suite testcases index
        # '902-sdr/efm/62421-sdr-multiple/',
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
    ci_config=CiConfig(shard_count=15),
    custom_compare_patterns=[
        (r"^EFM\.6\.03\.04$", r"^xmlSchema:.*$"),
        (r"^EFM\.6\.03\.05$", r"^(xmlSchema:.*|EFM\.5\.02\.01\.01)$"),
        (r"^EFM\.6\.04\.03$", r"^(xmlSchema:.*|utr:.*|xbrl\..*|xlink:.*)$"),
        (r"^EFM\.6\.05\.35$", r"^utre:.*$"),
        (r"^EFM\..*$", r"^~.*$"),
        (r"^EXG\..*$", r"^~.*$"),
        (r"^html:syntaxError$", r"^lxml\.SCHEMA.*$"),
    ],
    disclosure_system='efm-pragmatic',
    expected_additional_testcase_errors={
        ### Discovered during transition to Test Engine:
        "525-ix-syntax/efm/19-multiio/19-multiio-efm-testcase.xml:_204gd": {
            "arelle:nonIxdsDocument": 2,
        },
    },
    expected_load_errors=frozenset([
        "Testcase document contained no testcases: */conf/605-instance-syntax/605-45-cover-page-facts-general-case/605-45-cover-page-facts-general-case-testcase.xml",
        "Testcase document contained no testcases: */conf/609-linkbase-syntax/609-10-general-namespace-specific-custom-arc-restrictions/609-10-general-namespace-specific-custom-arc-restrictions-testcase.xml",
        "Testcase document contained no testcases: */conf/612-presentation-syntax/612-06-presentation-single-root/612-06-presentation-single-root-testcase.xml",
        "Testcase document contained no testcases: */conf/612-presentation-syntax/612-07-period-type-preferred-label-mismatch/612-07-period-type-preferred-label-mismatch-testcase.xml",
        "Testcase document contained no testcases: */conf/612-presentation-syntax/612-08-axis-requires-domain-child/612-08-axis-requires-domain-child-testcase.xml",
        "Testcase document contained no testcases: */conf/625-rr-rendering/01-embedding-commands/gd/01-embedding-commands-gd-testcase.xml",
        "Testcase document contained no testcases: */conf/626-rendering-syntax/626-04-embedding-command-syntax/626-04-embedding-command-syntax-testcase.xml",
        "Testcase document contained no testcases: */conf/626-rendering-syntax/626-05-embedding-missing-rows-or-columns/626-05-embedding-missing-rows-or-columns-testcase.xml",
        "Testcase document contained no testcases: */conf/626-rendering-syntax/626-06-embedding-incomplete-ordering-axes/626-06-embedding-incomplete-ordering-axes-testcase.xml",
        "Testcase document contained no testcases: */conf/626-rendering-syntax/626-08-too-many-annual-return-facts/626-08-too-many-annual-return-facts-testcase.xml",
        "Testcase document contained no testcases: */conf/626-rendering-syntax/626-09-Primary-Axis-On-Rows/626-09-primary-axis-on-rows-testcase.xml"
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
    test_case_result_options='match-any',
)
