from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('XBRL-XDT-CONF-2025-09-09.zip'),
            entry_point=Path('XBRL-XDT-CONF-2025-09-09/xdt.xml'),
            public_download_url='https://www.xbrl.org/2025/XBRL-XDT-CONF-2025-09-09.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    info_url='https://specifications.xbrl.org/work-product-index-group-dimensions-dimensions.html',
    name=PurePath(__file__).stem,
    runtime_options={
        'infosetValidate': True,
    },
    test_case_result_options='match-any',
)
