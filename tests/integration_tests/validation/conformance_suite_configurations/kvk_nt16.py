from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

ZIP_PATH = 'NT16_KVK_20211208 Berichten_0.zip'
# needs to be extracted because arelle can't load a taxonomy package ZIP from within a ZIP
EXTRACTED_PATH = ZIP_PATH.replace('.zip', '')
config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT16-preview',
    ],
    cache_version_id='kyDQkIWIysyp05vDIoPeLHAZqqcJMlPV',
    extract_path=EXTRACTED_PATH,
    expected_failure_ids=frozenset([
        # Actual
        # xbrldie:PrimaryItemDimensionallyInvalidError,
        # xbrlte:closedDefinitionNodeZeroCardinality,
        # xbrlte:constraintSetAspectMismatch,
        # xbrlte:invalidDimensionRelationshipSource,
        # xbrlte:missingAspectValue,
        # xbrlte:multipleValuesForAspect,
        # xmlSchema:syntax,
        # Expected: Valid
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-1',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-2',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-3',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-4',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-5',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-6',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-7',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-8',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-9',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-10',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-11',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-12',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-13',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-14',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-15',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-16',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-17',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-18',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-19',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-20',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-21',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-22',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-23',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-25',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-26',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-27',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-28',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-29',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-30',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-31',
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-32',

        # Expected: Valid
        'testcase-kvk-rpt-jaarverantwoording-2021-nlgaap-klein.xml:V-1',

        # Expected: Valid
        'testcase-kvk-rpt-jaarverantwoording-2021-nlgaap-micro.xml:V-1',

    ]),
    file='testcases.xml',
    info_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT16%20-%2020210301_0.pdf',
    local_filepath=ZIP_PATH,
    name=PurePath(__file__).stem,
    nested_filepath=(PurePath(EXTRACTED_PATH) / 'berichten' / 'NT16_KVK_20211208 - Testsuite.zip').as_posix(),
    plugins=frozenset({'validate/NL'}),
    public_download_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT16_KVK_20211208%20Berichten_0.zip',
    shards=3,  # Only 3 testcases in conformance suite
)
