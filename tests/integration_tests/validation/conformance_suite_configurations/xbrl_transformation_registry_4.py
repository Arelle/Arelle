from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--formula', 'run',
    ],
    file='testcase.xml',
    info_url='https://specifications.xbrl.org/work-product-index-inline-xbrl-transformation-registry-4.html',
    local_filepath='trr-4.0.zip',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
)
