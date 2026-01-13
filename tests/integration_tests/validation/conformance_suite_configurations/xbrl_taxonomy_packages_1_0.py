from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

ZIP_PATH = Path("taxonomy-package-conformance.zip")
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH,
            entry_point=Path("index.xml"),
        ),
    ],
    expected_additional_testcase_errors={f"index.xml:{s}": val for s, val in {
        "V-012-missing-catalog-file": {
            # Taxonomy package references non-existent "http://www.xbrl.org/sample-taxonomy/1.0/base.xsd"
            "IOerror": 1,
        },
    }.items()},
    info_url='https://specifications.xbrl.org/work-product-index-taxonomy-packages-taxonomy-packages-1.0.html',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    runtime_options={
        'taxonomyPackage': True,
    },
    test_case_result_options='match-any',
)
