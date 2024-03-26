from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT18-preview',
    ],
    cache_version_id='Ufq07WyHgZTKEgKBQhvar1z8Tf.HfDAX',
    file='index.xml',
    info_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT18%20-%2020230301_.pdf',
    local_filepath='nl_nt18',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    shards=4,
    test_case_result_options='match-any',
)
