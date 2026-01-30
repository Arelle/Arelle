from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, CiConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('formula.zip'),
            entry_point=Path('formula/tests/index.xml'),
        ),
    ],
    ci_config=CiConfig(fast=False),
    compare_formula_output=True,
    expected_additional_testcase_errors={f'{s}': val for s, val in {
        '30000 Assertions/31140-ConsistencyAssertion-StaticAnalysis-missingFormulae/31140 Consistency Assertion Missing Formulae.xml:V-01': {
            'compareInstance:targetInstanceNotLoaded': 1,
        },
    }.items()},
    expected_failure_ids=frozenset(f'{s}' for s in [
        '10000 Formula/12061-Formula-Processing-DimensionRules/12061 Dimension Rules.xml:V-13',
        '40000 Filters/48210-PeriodFilter-Processing-Period/48210 PeriodFilter Processing Period.xml:V-04',
    ]),
    info_url='https://specifications.xbrl.org/release-history-formula-1.0-formula-conf.html',
    name=PurePath(__file__).stem,
    test_case_result_options='match-any',
)
