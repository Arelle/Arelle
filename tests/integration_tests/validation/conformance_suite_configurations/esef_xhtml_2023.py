from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-unconsolidated-2023',
        '--formula', 'none',
    ],
    file='index_pure_xhtml.xml',
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2023',
    local_filepath='esef_conformance_suite_2023.zip',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/ESEF'}),
    public_download_url='https://www.esma.europa.eu/sites/default/files/2023-12/esef_conformance_suite_2023.zip',
)
