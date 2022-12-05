import os
from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import (
    CONFORMANCE_SUITE_PATH_PREFIX, ConformanceSuiteConfig
)

UTR_PATH = os.path.join(CONFORMANCE_SUITE_PATH_PREFIX, 'utr/registry/utr.xml')

config = ConformanceSuiteConfig(
    additional_downloads={
        'https://www.xbrl.org/utr/utr.xml': UTR_PATH
    },
    args=[
        '--utrUrl', UTR_PATH,
        '--utr',
    ],
    file='utr-conf-cr-2013-05-17/2013-05-17/index.xml',
    info_url='https://specifications.xbrl.org/work-product-index-registries-units-registry-1.0.html',
    local_filepath='utr/registry/utr-conf-cr-2013-05-17.zip',
    name=PurePath(__file__).stem,
    public_download_url='https://www.xbrl.org/utr/utr-conf-cr-2013-05-17.zip'
)
