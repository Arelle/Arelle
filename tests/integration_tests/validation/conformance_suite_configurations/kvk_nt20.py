from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

ZIP_PATH = Path('NT20_KVK_20251210 Berichten.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT20',
        '--baseTaxonomyValidation', 'none',
    ],
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'berichten' / 'NT20_KVK_20251210 - Testsuite.zip',
            entry_point=Path('testcases.xml'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT20_KVK_20251210%20Berichten.zip',
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_PACKAGES['NT20'],
    ],
    expected_additional_testcase_errors={
        # Compares against today; they'll pass eventually.
        v: {
            'NL.BR-KVK-4.07': 1,
            'message:valueAssertion_DocumentInformation_PrtDateEarlierThanCurrent1': 1,
        }
        for v in [
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-10',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-11',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-12',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-13',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-14',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-15',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-16',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-17',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-18',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-19',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-20',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-21',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-22',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-23',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-25',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-26',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-27',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-28',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-29',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-30',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-31',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-32',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-4',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-5',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-6',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-7',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-8',
            'testcase-kvk-rpt-jaarverantwoording-2025-all-entrypoints-valid.xml:V-9',
            'testcase-kvk-rpt-jaarverantwoording-2025-nlgaap-klein.xml:V-1',
            'testcase-kvk-rpt-jaarverantwoording-2025-nlgaap-micro.xml:V-1',
        ]
    },
    info_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/20251119%20SBR%20Filing%20Rules%20NT20_v1_1.pdf',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    shards=8,
)
