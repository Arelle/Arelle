import os
from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import (
    CONFORMANCE_SUITE_PATH_PREFIX, ConformanceSuiteConfig
)

ZIP_PATH = 'utr/structure/utr-structure-conf-cr-2013-11-18.zip'
config = ConformanceSuiteConfig(
    args=[
        '--utrUrl', os.path.join(CONFORMANCE_SUITE_PATH_PREFIX, ZIP_PATH, 'conf/utr-structure/utr-for-structure-conformance-tests.xml'),
        '--utr',
    ],
    file='conf/utr-structure/index.xml',
    info_url='https://specifications.xbrl.org/work-product-index-registries-units-registry-1.0.html',
    local_filepath=ZIP_PATH,
    name=PurePath(__file__).stem,
    public_download_url='https://www.xbrl.org/2013/utr-structure-conf-cr-2013-11-18.zip'
)
