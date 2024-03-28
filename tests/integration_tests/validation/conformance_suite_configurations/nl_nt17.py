from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT17-preview',
    ],
    file='index.xml',
    info_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT17%20-%2020220301__.pdf',
    local_filepath='nl_nt17',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    packages=[
        # https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT17_20230811%20Taxonomie%20SBRLight.zip
        'NT17_20230811_Taxonomie_SBRLight.zip',
        'nltaxonomie-nl-20240326.zip',
    ],
    plugins=frozenset({'validate/NL'}),
    shards=4,
    test_case_result_options='match-any',
)
