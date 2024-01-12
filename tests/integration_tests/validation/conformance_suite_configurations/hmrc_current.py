from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--hmrc',
    ],
    file='index.xml',
    info_url='https://www.gov.uk/government/organisations/hm-revenue-customs',
    local_filepath='HMRC',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/HMRC'}),
)
