import os

from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

ZIP_PATH = 'NT17_KVK_20221214 Berichten.zip'
# needs to be extracted because arelle can't load a taxonomy package ZIP from within a ZIP
EXTRACTED_PATH = ZIP_PATH.replace('.zip', '')
config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT17-preview',
    ],
    cache_version_id='8zcmafXcIBBJEljJfFibLgYmB1uCdgQo',
    extract_path=EXTRACTED_PATH,
    expected_failure_ids=frozenset([
        # Actual: dtre:noDecimalsItemType,
        # xbrldie:PrimaryItemDimensionallyInvalidError,
        # xbrlte:closedDefinitionNodeZeroCardinality,
        # xbrlte:constraintSetAspectMismatch,
        # xbrlte:invalidDimensionRelationshipSource,
        # xbrlte:missingAspectValue,
        # xbrlte:multipleValuesForAspect,
        # Expected: Valid
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-1',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-2',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-3',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-4',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-5',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-6',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-7',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-8',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-9',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-10',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-11',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-12',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-13',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-14',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-15',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-16',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-17',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-18',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-19',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-20',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-21',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-22',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-23',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-25',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-26',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-27',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-28',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-29',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-30',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-31',
        'testcase-kvk-rpt-jaarverantwoording-2022-all-entrypoints-valid.xml:V-32',
        'testcase-kvk-rpt-jaarverantwoording-2022-nlgaap-klein.xml:V-1',
        'testcase-kvk-rpt-jaarverantwoording-2022-nlgaap-micro.xml:V-1'
    ]),
    file='testcases.xml',
    info_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT17%20-%2020220301__.pdf',
    local_filepath=ZIP_PATH,
    name=PurePath(__file__).stem,
    nested_filepath=(PurePath(EXTRACTED_PATH) / 'berichten' / 'NT17_KVK_20221214 - Testsuite.zip').as_posix(),
    plugins=frozenset({'validate/NL'}),
    public_download_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT17_KVK_20221214%20Berichten.zip',
    shards=8,
)
