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
    # Duplicate errors: Running EDINET validations in a testcase context
    # prevents us from detecting when two models are being validated
    # from the same variation, so `shouldValidateUpload` always returns `True`.
    # This leads to any rule that validates at the package level (rather than the
    # instance level) firing once for each instance. Normal validation runs
    # do not have this issue.
    # TODO: Prevent duplicate runs in testcase context.
    # EC0121E: 31-character limit is violated by every example we've seen. Likely
    # misunderstanding of the rule or the example filings we're working with. Expect
    # to be resolved at some point.
    expected_additional_testcase_errors={f"*/{s}": val for s, val in {
        'valid/index.xml:valid01': {
            # See "Duplicate errors", "EC0121E" notes above.
            'EDINET.EC0121E': 114,
        },
        'EC0121E/index.xml:invalid01': {
            # See "Duplicate errors", "EC0121E" notes above.
            # 38 expected, 2 sets of duplicates
            'EDINET.EC0121E': 76,
        },
        'EC0124E/index.xml:invalid01': {
            # See "Duplicate errors", "EC0121E" notes above.
            'EDINET.EC0121E': 114,
            'EDINET.EC0124E': 2,
        },
        'EC0132E/index.xml:invalid01': {
            # See "EC0121E" note above (single instance, not duplicated)
            'EDINET.EC0121E': 38,
        },
    }.items()},
    expected_failure_ids=frozenset([]),
    info_url='https://disclosure2.edinet-fsa.go.jp/weee0020.aspx',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/EDINET', 'inlineXbrlDocumentSet'}),
    test_case_result_options='match-all',
)
