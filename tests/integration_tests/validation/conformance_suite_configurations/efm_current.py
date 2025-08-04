from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

CONFORMANCE_SUITE_ZIP_NAME = 'efm-74-250616.zip'

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
    cache_version_id='fQUkcdNcy7HZxP3bfwn1v3DnJkc4aKKp',
    # Expected additional errors until EFM conformance suite is updated to reflect 25.2.1.1 release.
    expected_additional_testcase_errors={f'conf/filing-fee-exhibit/{t}': errs for t, errs in {
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0001gd': {
            'EFM.FT.1.2.14.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0023gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0039gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0046gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0053gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0081gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0098gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0104gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0111gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0118gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0124gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0129gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0134gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0140gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0146gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0153gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0159gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0165gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0170gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0225gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0231gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0236gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0242gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0256gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0264gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0269gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0274gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0279gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0284gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0289gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0295gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0301gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0307gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0313gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0319gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0325gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0332gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0339gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0346gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0353gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0360gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0367gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0374gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0379gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-debt/00-other/00-debt/00-debt-testcase.xml:0385gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0001gd': {
            'EFM.FT.1.2.14.naFlagExpected': 1
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0004gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0008gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0011gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0015gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0018gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0021gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0025gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0029gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0033gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0036gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0040gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0044gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0047gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0051gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0055gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0059gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0063gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0067gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0071gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0075gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0079gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0083gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0087gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0091gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0095gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0099gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0103gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0107gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0111gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0115gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0119gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0123gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0127gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0131gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0168gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0173gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0178gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0183gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0188gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0193gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0198gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0203gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0208gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0213gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0218gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0222gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0226gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0230gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0234gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0238gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0242gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0246gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0250gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0254gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-filinglevel/00-other/00-filinglevel/00-filinglevel-testcase.xml:0258gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.2.3.3.ttlRqdFlds': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0006gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0019gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0023gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0025gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0028gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0030gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0032gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0034gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0037gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0039gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0041gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0047gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0050gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0051gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0095gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0100gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0105gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0110gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0115gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0120gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '000-multiline/00-other/00-multiline/00-multiline-testcase.xml:0125gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/01-Rule457(a)/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/01-Rule457(a)/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/01-Rule457(a)/00-good/00-good-testcase.xml:0003gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/01-Rule457(a)/00-good/00-good-testcase.xml:0004gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/01-Rule457(a)/00-good/00-good-testcase.xml:0005gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/01-Rule457(a)/00-good/00-good-testcase.xml:0006gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/01-Rule457(a)/00-good/00-good-testcase.xml:0007gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/01-Rule457(a)/00-good/00-good-testcase.xml:0008gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/00-flagIssues/00-flagIssues-testcase.xml:0005gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/00-good/00-good-testcase.xml:0003gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/00-good/00-good-testcase.xml:0004gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/00-good/00-good-testcase.xml:0005gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/00-good/00-good-testcase.xml:0006gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/00-good/00-good-testcase.xml:0007gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/00-good/00-good-testcase.xml:0008gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/04-AmtSctiesRegd/04-AmtSctiesRegd-testcase.xml:0002gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/04-AmtSctiesRegd/04-AmtSctiesRegd-testcase.xml:0004gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/04-AmtSctiesRegd/04-AmtSctiesRegd-testcase.xml:0007gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/05-MaxOfferingPricPerScty/05-MaxOfferingPricPerScty-testcase.xml:0003gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/05-MaxOfferingPricPerScty/05-MaxOfferingPricPerScty-testcase.xml:0007gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/02-Rule457(o)/05-MaxOfferingPricPerScty/05-MaxOfferingPricPerScty-testcase.xml:0013gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/03-Rule457(r)/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/03-Rule457(r)/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/03-Rule457(r)/00-good/00-good-testcase.xml:0003gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/04-Rule457(s)/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/04-Rule457(s)/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/04-Rule457(s)/00-good/00-good-testcase.xml:0003gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/04-Rule457(s)/00-good/00-good-testcase.xml:0004gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/04-Rule457(s)/00-good/00-good-testcase.xml:0005gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/05-Rule457(u)/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/05-Rule457(u)/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/05-Rule457(u)/00-good/00-good-testcase.xml:0003gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/06-Ruleother/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/06-Ruleother/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/06-Ruleother/00-good/00-good-testcase.xml:0003gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/06-Ruleother/00-good/00-good-testcase.xml:0004gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/06-Ruleother/00-good/00-good-testcase.xml:0005gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/06-Ruleother/00-good/00-good-testcase.xml:0006gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/06-Ruleother/00-good/00-good-testcase.xml:0007gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/06-Ruleother/00-good/00-good-testcase.xml:0008gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '300-offeringTable/07-Rule415(a)(6)/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/07-Rule415(a)(6)/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/07-Rule415(a)(6)/00-good/00-good-testcase.xml:0003gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/07-Rule415(a)(6)/00-good/00-good-testcase.xml:0004gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/08-Rule0-11/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '300-offeringTable/08-Rule0-11/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '300-offeringTable/08-Rule0-11/00-good/00-good-testcase.xml:0003gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '300-offeringTable/08-Rule0-11/00-good/00-good-testcase.xml:0004gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '300-offeringTable/09-Rule457(f)/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/09-Rule457(f)/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/09-Rule457(f)/00-good/00-good-testcase.xml:0003gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/09-Rule457(f)/00-good/00-good-testcase.xml:0004gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/09-Rule457(f)/00-good/00-good-testcase.xml:0005gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/09-Rule457(f)/00-good/00-good-testcase.xml:0006gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '300-offeringTable/09-Rule457(f)/00-good/00-good-testcase.xml:0007gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '400-offsetTable/01-Rule457(b)/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '400-offsetTable/01-Rule457(b)/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '400-offsetTable/01-Rule457(b)/00-good/00-good-testcase.xml:0003gd': {
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '400-offsetTable/01-Rule457(b)/00-good/00-good-testcase.xml:0004gd': {
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '400-offsetTable/02-Rule0-11(a)(2)/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.15.naFlagExpected': 1
        },
        '400-offsetTable/02-Rule0-11(a)(2)/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.15.naFlagExpected': 1
        },
        '400-offsetTable/02-Rule0-11(a)(2)/00-good/00-good-testcase.xml:0005gd': {
            'EFM.FT.1.1.15.naFlagExpected': 1
        },
        '400-offsetTable/02-Rule0-11(a)(2)/00-good/00-good-testcase.xml:0006gd': {
            'EFM.FT.1.1.15.naFlagExpected': 1
        },
        '400-offsetTable/03-Rule457(p)/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '400-offsetTable/03-Rule457(p)/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '400-offsetTable/03-Rule457(p)/00-good/00-good-testcase.xml:0003gd': {
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '400-offsetTable/03-Rule457(p)/00-good/00-good-testcase.xml:0004gd': {
            'EFM.FT.1.1.15.naFlagExpected': 1,
        },
        '500-cmbndPrspctsTable/01-Rule429/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '500-cmbndPrspctsTable/01-Rule429/00-good/00-good-testcase.xml:0002gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '500-cmbndPrspctsTable/01-Rule429/00-good/00-good-testcase.xml:0003gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '500-cmbndPrspctsTable/01-Rule429/00-good/00-good-testcase.xml:0004gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '500-cmbndPrspctsTable/01-Rule429/00-good/00-good-testcase.xml:0005gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '500-cmbndPrspctsTable/01-Rule429/00-good/00-good-testcase.xml:0006gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '500-cmbndPrspctsTable/01-Rule429/00-good/00-good-testcase.xml:0007gd': {
            'EFM.FT.1.1.14.naFlagExpected': 1,
        },
        '600-Scties424iTable/01-Rule424/00-good/00-good-testcase.xml:0001gd': {
            'EFM.FT.1.2.14.naFlagExpected': 1,
        },
    }.items()},
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
