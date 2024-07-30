from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'ros',
    ],
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('ros'),
            entry_point=Path('index.xml'),
        ),
    ],
    cache_version_id='gPspBVScQHwC33yT88cQcOK7nR5u3IRx',
    info_url='https://www.revenue.ie/en/companies-and-charities/corporation-tax-for-companies/submitting-financial-statements/index.aspx',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ROS'}),
)
