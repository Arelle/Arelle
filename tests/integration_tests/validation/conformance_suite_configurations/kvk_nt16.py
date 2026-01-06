from pathlib import PurePath, Path

from arelle.testengine.ErrorLevel import ErrorLevel
from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

ZIP_PATH = Path('NT16_KVK_20211208 Berichten_0.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'berichten' / 'NT16_KVK_20211208 - Testsuite.zip',
            entry_point=Path('testcases.xml'),
            public_download_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT16_KVK_20211208%20Berichten_0.zip',
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_PACKAGES['NT16'],
    ],
    expected_failure_ids=frozenset([
        # message:valueAssertion_ConsolidatedCashFlowStatementInsurance_PrtFST1SumOfChildrenParentDebit6
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-30',
    ]),
    base_taxonomy_validation='none',
    disclosure_system='NT16',
    ignore_levels=frozenset({
        ErrorLevel.NOT_SATISFIED,
        ErrorLevel.OK,
        ErrorLevel.WARNING,
    }),
    info_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT16%20-%2020210301_0.pdf',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    shards=8,
)
