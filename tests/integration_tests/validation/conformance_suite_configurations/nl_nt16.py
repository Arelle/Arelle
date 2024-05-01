from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT16',
    ],
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('nl_nt16'),
            entry_point=Path('index.xml'),
        ),
        *NL_PACKAGES['NT16'],
    ],
    info_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT16%20-%2020210301_0.pdf',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/NL'}),
    shards=4,
    test_case_result_options='match-any',
)
