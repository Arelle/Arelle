from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-2021',
        '--formula', 'run',
    ],
    cache_version_id='RHyZFLHe3de9PM._A4y125qBI63Al17Z',
    file='esef_conformance_suite_2021/esef_conformance_suite_2021/index_inline_xbrl.xml',
    info_url='https://www.esma.europa.eu/document/conformance-suite-2021',
    local_filepath='esef_conformance_suite_2021.zip',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF'}),
    public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2021.zip',
    shards=8,
)
