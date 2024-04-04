import os
from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import (
    CONFORMANCE_SUITE_PATH_PREFIX, ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetType, AssetSource
)

UTR_PATH = os.path.join(CONFORMANCE_SUITE_PATH_PREFIX, 'utr/registry/utr.xml')

config = ConformanceSuiteConfig(
    additional_downloads={
        'https://www.xbrl.org/utr/utr.xml': UTR_PATH
    },
    args=[
        '--utrUrl', os.path.join(CONFORMANCE_SUITE_PATH_PREFIX, 'utr/registry/utr.xml'),
        '--utr',
    ],
    file='utr-conf-cr-2013-05-17/2013-05-17/index.xml',
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('utr/registry/utr-conf-cr-2013-05-17.zip'),
            entry_point=Path('utr-conf-cr-2013-05-17/2013-05-17/index.xml'),
            public_download_url='https://www.xbrl.org/utr/utr-conf-cr-2013-05-17.zip',
        ),
        ConformanceSuiteAssetConfig(
            local_filename=Path('utr/registry/utr.xml'),
            source=AssetSource.S3_PRIVATE,
            type=AssetType.CONFORMANCE_SUITE,
            public_download_url='https://www.xbrl.org/utr/utr.xml',
            s3_key='utr/registry/utr.xml',
        )
    ],
    info_url='https://specifications.xbrl.org/work-product-index-registries-units-registry-1.0.html',
    local_filepath='utr/registry/utr-conf-cr-2013-05-17.zip',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    public_download_url='https://www.xbrl.org/utr/utr-conf-cr-2013-05-17.zip',
)
