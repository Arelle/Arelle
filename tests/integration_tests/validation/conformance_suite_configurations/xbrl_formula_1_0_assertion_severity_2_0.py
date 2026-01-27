from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('60111 AssertionSeverity-2.0-Processing.zip'),
            entry_point=Path('60111 AssertionSeverity-2.0-Processing/60111 Assertion Severity 2.0 Processing.xml'),
        ),
    ],
    expected_load_errors=frozenset([
        'Could not load file from local filesystem. file: *tests/resources/conformance_suites/xsd/test.xsd',
    ]),
    info_url='https://specifications.xbrl.org/release-history-formula-1.0-formula-conf.html',
    name=PurePath(__file__).stem,
    test_case_result_options='match-any',
)
