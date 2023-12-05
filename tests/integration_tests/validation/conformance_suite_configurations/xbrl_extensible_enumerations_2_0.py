from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    file='extensible-enumerations-2.0-2020-02-12/enumerations-index.xml',
    info_url='https://specifications.xbrl.org/work-product-index-extensible-enumerations-extensible-enumerations-2.0.html',
    local_filepath='extensible-enumerations-2.0-2020-02-12.zip',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
)
