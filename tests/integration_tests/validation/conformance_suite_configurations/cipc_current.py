from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('cipc'),
            entry_point=Path('index.xml'),
        ),
    ],
    base_taxonomy_validation='none',
    cache_version_id='..Az6BmYC3hVWE.2nH2SYPTWkPMFJYa_',
    disclosure_system='cipc',
    info_url='https://www.cipc.co.za/?page_id=4400',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/CIPC'}),
)
