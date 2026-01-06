from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('formula.zip'),
            entry_point=Path('formula/tests/index.xml'),
        ),
    ],
    compare_formula_output=True,
    info_url='https://specifications.xbrl.org/release-history-formula-1.0-formula-conf.html',
    name=PurePath(__file__).stem,
    shards=4,
    test_case_result_options='match-any',
)
