from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--formula', 'run',
    ],
    file='index.xml',
    info_url='https://specifications.xbrl.org/work-product-index-taxonomy-packages-taxonomy-packages-1.0.html',
    local_filepath='taxonomy-package-conformance.zip',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
)
