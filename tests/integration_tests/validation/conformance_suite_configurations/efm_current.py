from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    additional_plugins_by_prefix=[
        ('conf/612-presentation-syntax/612-09-presented-units-order', frozenset({'EdgarRenderer'})),
        ('conf/626-rendering-syntax', frozenset({'EdgarRenderer'})),
    ],
    args=[
        '--disclosureSystem', 'efm-pragmatic',
        '--formula', 'run',
    ],
    cache_version_id='EVHW_hgNxuwBw4aiKfksIBuqWJypQEZh',
    file='conf/testcases.xml',
    info_url='https://www.sec.gov/structureddata/osdinteractivedatatestsuite',
    local_filepath='efm-68-1-240129.zip',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/EFM', 'inlineXbrlDocumentSet'}),
    public_download_url='https://www.sec.gov/files/efm-68-1-240129.zip',
    shards=40,
    # efm-68-1-240129.zip test suite has case sensitive errors when referring to test case files.
    # 'OEF' and 'RXP' are uppercase in directory names and lowercase in test suite URIs.
    strict_testcase_index=False,
)
