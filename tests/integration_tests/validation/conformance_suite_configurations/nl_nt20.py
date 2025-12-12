from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NT20',
        '--baseTaxonomyValidation', 'none',
    ],
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('nl_nt20'),
            entry_point=Path('index.xml'),
        ),
        *NL_PACKAGES['NT20'],
    ],
    info_url='https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/20251119%20SBR%20Filing%20Rules%20NT20_v1_1.pdf',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    shards=4,
    test_case_result_options='match-any',
)
