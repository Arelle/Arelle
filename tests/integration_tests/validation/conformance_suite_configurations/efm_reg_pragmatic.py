from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('efm_reg_pragmatic.zip'),
            entry_point=Path('index.xml'),
            source=AssetSource.S3_PUBLIC,
        )
    ],
    cache_version_id='F3BNGfVAc7XKtWIwszoxv3QWVsDPlail',
    ci_enabled=False,
    disclosure_system='efm-pragmatic',
    info_url='N/A',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/EFM', 'inlineXbrlDocumentSet'}),
    test_case_result_options='match-any',
)
