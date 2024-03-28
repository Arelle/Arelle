from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig


config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'arl-2022-preview',
    ],
    file='index.xml',
    info_url='https://danishbusinessauthority.dk/sites/default/files/2023-10/xbrl-taxonomy-framework-architecture-01102015_wa.pdf',
    local_filepath='dba',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    packages=[
        'ARL-XBRL20221001-20221117.zip',
    ],
    plugins=frozenset({'validate/DBA'}),
)
