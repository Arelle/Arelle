from pathlib import PurePath, Path

from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'EDINET',
        # '--baseTaxonomyValidation', 'none',
        # '--testcaseResultsCaptureWarnings',
    ],
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('edinet'),
            entry_point=Path('index.xml'),
        ),
        # ConformanceSuiteAssetConfig.public_taxonomy_package(Path('ARL-XBRL20221001-20221117.zip')),
    ],
    expected_additional_testcase_errors={f"conformance-suite-2024-sbr-domein-handelsregister/tests/{s}": val for s, val in {}.items()},
    expected_failure_ids=frozenset([]),
    info_url='https://disclosure2.edinet-fsa.go.jp/weee0020.aspx',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/EDINET'}),
    test_case_result_options='match-all',
)
