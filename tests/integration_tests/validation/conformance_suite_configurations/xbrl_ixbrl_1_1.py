import os
from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import (
    CONFORMANCE_SUITE_PATH_PREFIX, ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource
)

ZIP_PATH = Path("inlineXBRL-1.1-conformanceSuite-2020-04-08.zip")
config = ConformanceSuiteConfig(
    args=[
        "--packages", os.path.join(CONFORMANCE_SUITE_PATH_PREFIX, ZIP_PATH, "inlineXBRL-1.1-conformanceSuite-2020-04-08/schemas/www.example.com.zip"),
        "--requireInlineXbrl",
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            ZIP_PATH,
            entry_point=Path("inlineXBRL-1.1-conformanceSuite-2020-04-08/index.xml"),
            public_download_url="https://www.xbrl.org/2020/inlineXBRL-1.1-conformanceSuite-2020-04-08.zip",
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    capture_warnings=False,
    expected_additional_testcase_errors={f"*tests/{s}": val for s, val in {
        # test case references two distinct example schemas with the same target namespace and no includes.
        "baseURIs/PASS-baseURI-on-ix-references-multiRefs.xml:V-1003": {
            "xbrl:multipleTopLevelSchemasForNamespace": 1,
        },
    }.items()},
    info_url="https://specifications.xbrl.org/work-product-index-inline-xbrl-inline-xbrl-1.1.html",
    name=PurePath(__file__).stem,
    plugins=frozenset({"inlineXbrlDocumentSet"}),
    shards=4,
)
