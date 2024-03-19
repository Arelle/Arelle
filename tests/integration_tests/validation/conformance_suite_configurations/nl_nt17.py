from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT17-preview',
    ],
    cache_version_id='eOz6hLM64QEXb4MloAAx_kxm.iIkxb9L',
    file='index.xml',
    info_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT17%20-%2020220301__.pdf',
    local_filepath='nl_nt17',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    shards=4,
)
