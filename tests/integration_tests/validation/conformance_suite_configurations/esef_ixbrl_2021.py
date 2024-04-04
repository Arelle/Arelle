from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import ESEF_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteConfig, ConformanceSuiteAssetConfig, ESEF_PACKAGES as ESEF_PACKAGE_NAMES
)

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-2021',
        '--formula', 'run',
    ],
    file='esef_conformance_suite_2021/esef_conformance_suite_2021/index_inline_xbrl.xml',
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('esef_conformance_suite_2021.zip'),
            entry_point=Path('esef_conformance_suite_2021/esef_conformance_suite_2021/index_inline_xbrl.xml'),
            public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2021.zip',
        ),
    ] + [
        package for year in [2017, 2019, 2020, 2021] for package in ESEF_PACKAGES[year]
    ],
    info_url='https://www.esma.europa.eu/document/conformance-suite-2021',
    local_filepath='esef_conformance_suite_2021.zip',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    packages=[package for year in [2017, 2019, 2020, 2021] for package in ESEF_PACKAGE_NAMES[year]],
    plugins=frozenset({'validate/ESEF'}),
    public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2021.zip',
    shards=8,
    test_case_result_options='match-any',
)
