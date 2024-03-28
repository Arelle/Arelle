import os

from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

ZIP_PATH = 'NT17_KVK_20221214 Berichten.zip'
# needs to be extracted because arelle can't load a taxonomy package ZIP from within a ZIP
EXTRACTED_PATH = ZIP_PATH.replace('.zip', '')
config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT17-preview',
        '--logCodeFilter', '(?!({})$)'.format('|'.join([
            'xbrlte:closedDefinitionNodeZeroCardinality',
            'xbrlte:constraintSetAspectMismatch',
            'xbrlte:invalidDimensionRelationshipSource',
            'xbrlte:missingAspectValue',
            'xbrlte:multipleValuesForAspect',
        ])),
    ],
    extract_path=EXTRACTED_PATH,
    file='testcases.xml',
    info_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT17%20-%2020220301__.pdf',
    local_filepath=ZIP_PATH,
    name=PurePath(__file__).stem,
    nested_filepath=(PurePath(EXTRACTED_PATH) / 'berichten' / 'NT17_KVK_20221214 - Testsuite.zip').as_posix(),
    network_or_cache_required=False,
    packages=[
        # https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT17_20230811%20Taxonomie%20SBRLight.zip
        'NT17_20230811_Taxonomie_SBRLight.zip',
        'nltaxonomie-nl-20240326.zip',
    ],
    plugins=frozenset({'validate/NL'}),
    public_download_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT17_KVK_20221214%20Berichten.zip',
    shards=8,
)
