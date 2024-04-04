from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT18-preview',
    ],
    file='index.xml',
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('nl_nt18'),
            entry_point=Path('index.xml'),
        ),
        *NL_PACKAGES['NT18'],
    ],
    info_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT18%20-%2020230301_.pdf',
    local_filepath='nl_nt18',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    packages=[
        # https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT16_20220803%20Taxonomie%20%28SBRlight%29.zip
        'NT18_20240126_Taxonomie_SBRLight.zip',
        'nltaxonomie-nl-20240326.zip',
    ],
    plugins=frozenset({'validate/NL'}),
    shards=4,
    test_case_result_options='match-any',
)
