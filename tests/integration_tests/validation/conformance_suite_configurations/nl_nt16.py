from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, CiConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('nl_nt16'),
            entry_point=Path('index.xml'),
        ),
        *NL_PACKAGES['NT16'],
    ],
    base_taxonomy_validation='none',
    ci_config=CiConfig(fast=False),
    disclosure_system='NT16',
    info_url='https://sbr-nl.nl/sites/default/files/bestanden/taxonomie/SBR%20Filing%20Rules%20NT16%20-%2020210301_0.pdf',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    test_case_result_options='match-any',
)
