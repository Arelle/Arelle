from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

TIMING = {
    'fg_nl/04-testcase.xml': 0.019,
    'fg_nl/05-testcase.xml': 0.012,
    'fg_nl/09-testcase.xml': 0.011,
    'fg_nl/11-testcase.xml': 0.011,
    'fr_nl/1-01-testcase.xml': 0.002,
    'fr_nl/1-02-testcase.xml': 0.002,
    'fr_nl/1-03-testcase.xml': 0.001,
    'fr_nl/1-04-testcase.xml': 0.002,
    'fr_nl/1-05-testcase.xml': 0.001,
    'fr_nl/1-06-testcase.xml': 0.001,
    'fr_nl/2-03-testcase.xml': 0.001,
    'fr_nl/2-06-testcase.xml': 0.002,
    'fr_nl/3-04-testcase.xml': 2.350,
    'fr_nl/4-01-testcase.xml': 1.610,
    'fr_nl/5-01-testcase.xml': 1.594,
    'fr_nl/5-03-testcase.xml': 0.806,
    'fr_nl/5-11-testcase.xml': 0.025,
    'fr_nl/6-01-testcase.xml': 0.794,
}

config = ConformanceSuiteConfig(
    approximate_relative_timing=TIMING,
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
