from pathlib import PurePath, Path

from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--baseTaxonomyValidation', 'none',
        '--disclosureSystem', 'EDINET',
        '--testcaseResultsCaptureWarnings',
    ],
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('edinet'),
            entry_point=Path('index.xml'),
        ),
    ],
    cache_version_id='cs2wODrDheJqDIm1kEU4Qwk8jwd7DfQu',
    expected_additional_testcase_errors={f"*{s}": val for s, val in {
        # EDINET.EC8027W: Some of our "valid" documents define presentation and/or definition
        # links with multiple root elements. Keeping these out of the conformance suite
        # until we are more confident in our interpretation of the EDINET rule.
        "EC8024E/index.xml:invalid01": {
            "EDINET.EC8027W": 1,
        },
        "EC8062W/index.xml:invalid01": {
            "EDINET.EC8027W": 1,
        },
        "valid/index.xml:valid01": {
            "EDINET.EC8027W": 2,
        },
        "valid/index.xml:valid02": {
            "EDINET.EC8027W": 2,
        },
        "valid/index.xml:valid03": {
            "EDINET.EC8027W": 1,
        },
        "valid/index.xml:valid20": {
            "EDINET.EC8027W": 2,
        },
    }.items()},
    expected_failure_ids=frozenset([]),
    info_url='https://disclosure2.edinet-fsa.go.jp/weee0020.aspx',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/EDINET', 'inlineXbrlDocumentSet'}),
    shards=4,
    test_case_result_options='match-all',
)
