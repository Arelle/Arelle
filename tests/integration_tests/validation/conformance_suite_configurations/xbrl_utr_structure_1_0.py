import os
from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import (
    CONFORMANCE_SUITE_PATH_PREFIX, ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource
)

ZIP_PATH = 'utr/structure/utr-structure-conf-cr-2013-11-18.zip'
config = ConformanceSuiteConfig(
    args=[
        '--utrUrl', os.path.join(CONFORMANCE_SUITE_PATH_PREFIX, ZIP_PATH, 'conf/utr-structure/utr-for-structure-conformance-tests.xml'),
        '--utr',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path(ZIP_PATH),
            entry_point=Path('conf/utr-structure/index.xml'),
            public_download_url='https://www.xbrl.org/2013/utr-structure-conf-cr-2013-11-18.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    info_url='https://specifications.xbrl.org/work-product-index-registries-units-registry-1.0.html',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
)
