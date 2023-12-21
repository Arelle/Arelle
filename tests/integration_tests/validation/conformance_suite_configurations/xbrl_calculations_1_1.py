from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    file='calculation-1.1-conformance-2023-12-20/index.xml',
    info_url='https://specifications.xbrl.org/work-product-index-calculations-2-calculations-1-1.html',
    local_filepath='calculation-1.1-conformance-2023-12-20.zip',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'loadFromOIM', '../../tests/plugin/testcaseCalc11ValidateSetup.py'}),
)
