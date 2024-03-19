from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT16-preview',
    ],
    cache_version_id='ODcN7yG7UJb_W2ItTUCacjKNtwZc1oh6',
    file='index.xml',
    info_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT16%20-%2020210301_0.pdf',
    local_filepath='nl_nt16',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    shards=4,
)
