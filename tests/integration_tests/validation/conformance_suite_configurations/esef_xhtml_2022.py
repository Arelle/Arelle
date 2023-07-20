from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-unconsolidated',
        '--formula', 'none',
    ],
    file='esef_conformance_suite_2022/index_pure_xhtml.xml',
    info_url='https://www.esma.europa.eu/document/conformance-suite-2022',
    local_filepath='esef_conformance_suite_2022.zip',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF_2022'}),
    public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2022.zip',
)
