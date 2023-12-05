import os
from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_utr_structure_1_0 import config as structure_config


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
            '--utrUrl', os.path.join(structure_config.prefixed_local_filepath, 'conf/utr-structure/malformed-utrs', malformed_utr_file),
            '--utr',
        ],
        expected_model_errors=frozenset(expected_model_errors),
        file='conf/utr-structure/tests/01-simple/simpleValid.xml',
        info_url='https://specifications.xbrl.org/work-product-index-registries-units-registry-1.0.html',
        local_filepath=structure_config.local_filepath,
        name=PurePath(__file__).stem,
        network_or_cache_required=False,
        public_download_url=structure_config.public_download_url,
    )
    for malformed_utr_file, expected_model_errors in MALFORMED_UTR_FILES.items()
]
