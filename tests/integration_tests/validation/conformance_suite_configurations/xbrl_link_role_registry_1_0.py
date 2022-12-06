from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    file='lrr/conf/index.xml',
    info_url='https://specifications.xbrl.org/work-product-index-registries-lrr-1.0.html',
    local_filepath='lrr-conf-pwd-2005-06-21.zip',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    url_replace='file:///c:/temp/conf/'
)
