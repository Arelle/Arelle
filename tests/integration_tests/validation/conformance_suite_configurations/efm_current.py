from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
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
