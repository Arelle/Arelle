from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig, AssetSource,
)

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('xbrl-xsdtests_v2026-07-17-1656.zip'),
            entry_point=Path('index.xml'),
            public_download_url='https://github.com/Arelle/xbrl-xsdtests/releases/download/v2026.07.17-1656/xbrl-xsdtests_v2026-07-17-1656.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    expected_additional_testcase_errors={f"*{s}": val for s, val in {
        # Generated conformance suite doesn't report number of expected occurences,
        # so Arelle (with match-all) considers additional occurences as a failure.
        # The intent of the source testcase is that there are 2 invalid values,
        # and Arelle correctly fires 2 errors, so this "failure" is accepted.
        "anyURI/anyURI-21837395-testcase.xml:Microsoft_anyURI_b005_1355_anyURI_b005_1355.i": {
            "xmlSchema:valueError": 1
        },
    }.items()},
    info_url='https://github.com/Arelle/xbrl-xsdtests',
    name=PurePath(__file__).stem,
    test_case_result_options='match-all',
    shards=4,
)
