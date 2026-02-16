from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, CiConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('nl_nt19'),
            entry_point=Path('index.xml'),
        ),
        *NL_PACKAGES['NT19'],
    ],
    base_taxonomy_validation='none',
    ci_config=CiConfig(fast=False),
    disclosure_system='NT19',
    info_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/20240301%20SBR%20Filing%20Rules%20NT19.pdf',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    test_case_result_options='match-any',
)
