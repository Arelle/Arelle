from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

ZIP_PATH = 'NT16_KVK_20211208 Berichten_0.zip'
# needs to be extracted because arelle can't load a taxonomy package ZIP from within a ZIP
EXTRACTED_PATH = ZIP_PATH.replace('.zip', '')
config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT16-preview',
        '--logCodeFilter', '(?!({})$)'.format('|'.join([
            'xbrlte:closedDefinitionNodeZeroCardinality',
            'xbrlte:constraintSetAspectMismatch',
            'xbrlte:invalidDimensionRelationshipSource',
            'xbrlte:missingAspectValue',
            'xbrlte:multipleValuesForAspect',
        ])),
    ],
    extract_path=EXTRACTED_PATH,
    expected_failure_ids=frozenset([
        # message:valueAssertion_ConsolidatedCashFlowStatementInsurance_PrtFST1SumOfChildrenParentDebit6
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-30',
    ]),
    file='testcases.xml',
    info_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT16%20-%2020210301_0.pdf',
    local_filepath=ZIP_PATH,
    name=PurePath(__file__).stem,
    nested_filepath=(PurePath(EXTRACTED_PATH) / 'berichten' / 'NT16_KVK_20211208 - Testsuite.zip').as_posix(),
    network_or_cache_required=False,
    packages=[
        # https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT16_20220803%20Taxonomie%20%28SBRlight%29.zip
        'NT16_20220803_Taxonomie_SBRlight.zip',
        'nltaxonomie-nl-20240326.zip',
    ],
    plugins=frozenset({'validate/NL'}),
    public_download_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT16_KVK_20211208%20Berichten_0.zip',
    shards=8,
)
