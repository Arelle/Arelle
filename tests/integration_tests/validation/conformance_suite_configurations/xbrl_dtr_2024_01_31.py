from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--formula', 'run',
    ],
    file='data-type-registry-1.11.0-REC+registry+2024-01-31/conf/dtr/testcase-index.xml',
    info_url='https://gitlab.xbrl.org/base-spec/data-type-registry/-/tree/1.11.0-REC+registry+2024-01-31/conf',
    local_filepath='data-type-registry-1.11.0-REC+registry+2024-01-31.zip',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
)
