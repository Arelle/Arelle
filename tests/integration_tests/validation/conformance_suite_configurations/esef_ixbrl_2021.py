from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ESEF_PACKAGES

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-2021',
        '--formula', 'run',
    ],
    file='esef_conformance_suite_2021/esef_conformance_suite_2021/index_inline_xbrl.xml',
    info_url='https://www.esma.europa.eu/document/conformance-suite-2021',
    local_filepath='esef_conformance_suite_2021.zip',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    packages=[package for year in [2017, 2019, 2020, 2021] for package in ESEF_PACKAGES[year]],
    plugins=frozenset({'validate/ESEF'}),
    public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2021.zip',
    shards=8,
    test_case_result_options='match-any',
)
