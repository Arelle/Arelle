from pathlib import PurePath, Path

from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_utr_structure_1_0 import config as structure_config

ENTRY_POINT_ROOT = structure_config.entry_point_asset.entry_point_root
assert ENTRY_POINT_ROOT is not None
FULL_ENTRY_POINT_ROOT = structure_config.entry_point_root
MALFORMED_UTR_FILES = {
    '01-unit-id-and-status-not-unique.xml': ['arelleUtrLoader:entryDuplication'],
    '02-simple-unit-item-type-missing.xml': ['arelleUtrLoader:simpleDefMissingField'],
    '03-complex-unit-with-symbol.xml': ['arelleUtrLoader:complexDefSymbol'],
    '04-numerator-item-type-namespace-but-no-numerator-item-type.xml': ['arelleUtrLoader:complexDefMissingField'],
    '05-simple-unit-with-numerator-item-type.xml': ['arelleUtrLoader:complexDefMissingField'],
    '06-denominator-item-type-namespace-but-no-denominator-item-type.xml': ['arelleUtrLoader:complexDefMissingField'],
    '07-simple-unit-with-denominator-item-type.xml': ['arelleUtrLoader:complexDefMissingField', 'utre:error-NumericFactUtrInvalid'],
}

configs = [
    ConformanceSuiteConfig(
        args=[
            '--utrUrl', str(FULL_ENTRY_POINT_ROOT / 'conf/utr-structure/malformed-utrs' / malformed_utr_file),
            '--utr',
        ],
        assets=[
            ConformanceSuiteAssetConfig.conformance_suite(
                ENTRY_POINT_ROOT,
                entry_point=Path('conf/utr-structure/tests/01-simple/simpleValid.xml'),
                public_download_url=structure_config.entry_point_asset.public_download_url,
                source=AssetSource.S3_PUBLIC,
            ),
        ],
        expected_model_errors=frozenset(expected_model_errors),
        info_url='https://specifications.xbrl.org/work-product-index-registries-units-registry-1.0.html',
        name=PurePath(__file__).stem,
        network_or_cache_required=False,
    )
    for malformed_utr_file, expected_model_errors in MALFORMED_UTR_FILES.items()
]
