from pathlib import PurePath, Path

from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'EDINET',
    ],
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('edinet'),
            entry_point=Path('index.xml'),
        ),
    ],
    cache_version_id='MkGD3D8lKJN_y0a0fH75EeZHKAO7V.iJ',
    expected_additional_testcase_errors={f"*/{s}": val for s, val in {
        'valid/index.xml:valid01': {
            'EDINET.EC0121E': 48,
        },
        'EC0124E/index.xml:invalid01': {
            'EDINET.EC0121E': 48,
        },
    }.items()},
    expected_failure_ids=frozenset([]),
    info_url='https://disclosure2.edinet-fsa.go.jp/weee0020.aspx',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/EDINET', 'inlineXbrlDocumentSet'}),
    test_case_result_options='match-all',
)
