from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

ZIP_PATH = Path('NT18_KVK_20231213 Berichten.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT18-preview',
        '--logCodeFilter', '(?!({})$)'.format('|'.join([
            'xbrlte:closedDefinitionNodeZeroCardinality',
            'xbrlte:constraintSetAspectMismatch',
            'xbrlte:invalidDimensionRelationshipSource',
            'xbrlte:missingAspectValue',
            'xbrlte:multipleValuesForAspect',
        ])),
    ],
    extract_path=str(EXTRACTED_PATH),
    file='testcases.xml',
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'berichten' / 'NT18_KVK_20231213 - Test-suite.zip',
            entry_point=Path('testcases.xml'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT18_KVK_20231213%20Berichten.zip',
        ),
        *NL_PACKAGES['NT18'],
    ],
    info_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT18%20-%2020230301_.pdf',
    local_filepath=str(ZIP_PATH),
    name=PurePath(__file__).stem,
    nested_filepath=(PurePath(EXTRACTED_PATH) / 'berichten' / 'NT18_KVK_20231213 - Test-suite.zip').as_posix(),
    network_or_cache_required=False,
    packages=[
        # https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT18_20240126%20Taxonomie%20%28SBRLight%29.zip
        'NT18_20240126_Taxonomie_SBRLight.zip',
        'nltaxonomie-nl-20240326.zip',
    ],
    plugins=frozenset({'validate/NL'}),
    public_download_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT18_KVK_20231213%20Berichten.zip',
    shards=8,
)
