from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

ZIP_PATH = Path('NT16_KVK_20211208 Berichten_0.zip')
# needs to be extracted because arelle can't load a taxonomy package ZIP from within a ZIP
EXTRACTED_PATH = Path(ZIP_PATH.stem)
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
    extract_path=str(EXTRACTED_PATH),
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'berichten' / 'NT16_KVK_20211208 - Testsuite.zip',
            entry_point=Path('testcases.xml'),
            public_download_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT16_KVK_20211208%20Berichten_0.zip',
        ),
        *NL_PACKAGES['NT16'],
    ],
    expected_failure_ids=frozenset([
        # message:valueAssertion_ConsolidatedCashFlowStatementInsurance_PrtFST1SumOfChildrenParentDebit6
        'testcase-kvk-rpt-jaarverantwoording-2021-all-entrypoints-valid.xml:V-30',
    ]),
    file='testcases.xml',
    info_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT16%20-%2020210301_0.pdf',
    local_filepath=str(ZIP_PATH),
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
