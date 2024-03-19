from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT18-preview',
    ],
    cache_version_id='5FqxcEUcRYnqmuAVPDH1qOrdECSnoXgD',
    file='index.xml',
    info_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT18%20-%2020230301_.pdf',
    local_filepath='nl_nt18',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    shards=4,
)
