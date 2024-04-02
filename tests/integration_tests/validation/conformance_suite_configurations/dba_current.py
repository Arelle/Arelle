from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig


config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'arl-2022-preview',
    ],
    file='index.xml',
    info_url='https://erhvervsstyrelsen.dk/vejledning-teknisk-vejledning-og-dokumentation-regnskab-20-taksonomier-aktuelle',
    local_filepath='dba',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    packages=[
        # https://erhvervsstyrelsen.dk/sites/default/files/2022-11/XBRL20221001-20221117.zip
        'ARL-XBRL20221001-20221117.zip',
    ],
    plugins=frozenset({'validate/DBA'}),
)
