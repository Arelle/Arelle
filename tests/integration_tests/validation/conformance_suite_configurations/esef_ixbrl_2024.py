from pathlib import Path, PurePath

from tests.integration_tests.validation.assets import ESEF_PACKAGES, LEI_2020_07_02
from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-2024',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('esef_conformance_suite_2024.zip'),
            entry_point=Path('esef_conformance_suite_2024/index_inline_xbrl.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/2025-01/esef_conformance_suite_2024.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ] + [
        package for year in [2017, 2019, 2020, 2021, 2022, 2024] for package in ESEF_PACKAGES[year]
    ],
    expected_additional_testcase_errors={f"esef_conformance_suite_2024/tests/inline_xbrl/{s}": val for s, val in {
        # Typo in the test case namespace declaration: incorrectly uses the Extensible Enumeration 1 namespace with the
        # commonly used Extensible Enumeration 2 prefix: xmlns:enum2="http://xbrl.org/2014/extensible-enumerations"
        'G2-4-1_1/index.xml:TC2_valid': frozenset({'differentExtensionDataType'}),
    }.items()},
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2024',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/ESEF'}),
    shards=8,
    test_case_result_options='match-any',
)
