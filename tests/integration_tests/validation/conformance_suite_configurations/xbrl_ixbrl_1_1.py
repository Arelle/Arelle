import os
from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import (
    CONFORMANCE_SUITE_PATH_PREFIX, ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource
)

ZIP_PATH = Path('inlineXBRL-1.1-conformanceSuite-2020-04-08.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    args=[
        '--packages', os.path.join(CONFORMANCE_SUITE_PATH_PREFIX, EXTRACTED_PATH, 'inlineXBRL-1.1-conformanceSuite-2020-04-08/schemas/www.example.com.zip'),
    ],
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'inlineXBRL-1.1-conformanceSuite-2020-04-08',
            entry_point=Path('index.xml'),
            public_download_url='https://www.xbrl.org/2020/inlineXBRL-1.1-conformanceSuite-2020-04-08.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    capture_warnings=False,
    expected_additional_testcase_errors={f"*tests/{s}": val for s, val in {
        # test case references two distinct example schemas with the same target namespace and no includes.
        'baseURIs/PASS-baseURI-on-ix-references-multiRefs.xml:V-1003': {
            'xbrl:multipleTopLevelSchemasForNamespace': 1,
        },
    }.items()},
    info_url='https://specifications.xbrl.org/work-product-index-inline-xbrl-inline-xbrl-1.1.html',
    name=PurePath(__file__).stem,
    plugins=frozenset({'inlineXbrlDocumentSet', '../../tests/plugin/testcaseIxExpectedHtmlFixup.py'}),
    shards=4,
)
