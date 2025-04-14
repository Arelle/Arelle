from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

config = ConformanceSuiteConfig(
    args=[
        '--check-formula-restricted-XPath',
        '--noValidateTestcaseSchema',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('formula.zip'),
            entry_point=Path('formula/function-registry/registry-index.xml'),
        ),
    ],
    info_url='https://specifications.xbrl.org/release-history-formula-1.0-formula-conf.html',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'formulaXPathChecker', 'functionsMath'}),
    strict_testcase_index=False,
    test_case_result_options='match-any',
)
