from pathlib import PurePath, Path

from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--baseTaxonomyValidation', 'none',
        '--disclosureSystem', 'EDINET',
    ],
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('edinet'),
            entry_point=Path('index.xml'),
        ),
    ],
    cache_version_id='cs2wODrDheJqDIm1kEU4Qwk8jwd7DfQu',
    expected_additional_testcase_errors={f"*{s}": val for s, val in {
        # Duplicate errors: Running EDINET validations in a testcase context
        # prevents us from detecting when two models are being validated
        # from the same variation, so `shouldValidateUpload` always returns `True`.
        # This leads to any rule that validates at the package level (rather than the
        # instance level) firing once for each instance. Normal validation runs
        # do not have this issue. We can expect this to be resolved at some point.
        # Until then, if you construct a test case zip from a valid package that has multiple instances
        # (e.g. PublicDoc + AuditDoc) you'll need to add expected additional testcases here
        # for the duplicate errors.
        # TODO: Prevent duplicate runs in testcase context.
        "EC5806E/index.xml:invalid01": {
            # The duplicated instance needed to trigger the duplicated "preferredFilename"
            # error also causes the validation to fire an additional time in the conformance
            # suite context.
            "EDINET.EC5806E": 1,
        }
    }.items()},
    expected_failure_ids=frozenset([]),
    info_url='https://disclosure2.edinet-fsa.go.jp/weee0020.aspx',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/EDINET', 'inlineXbrlDocumentSet'}),
    shards=4,
    test_case_result_options='match-all',
)
