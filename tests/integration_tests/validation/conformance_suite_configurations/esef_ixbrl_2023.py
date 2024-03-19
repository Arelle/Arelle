from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'esef-2023',
        '--formula', 'run',
    ],
    cache_version_id='yBVmKR4WMHVcHEp.SDUNO1zxTwQwkRhD',
    expected_failure_ids=frozenset(f'tests/inline_xbrl/{s}' for s in [
        # Test report uses older domain item type (http://www.xbrl.org/dtr/type/non-numeric) forbidden by ESEF.3.2.2.
        'G3-1-2/index.xml:TC2_valid',
        # These tests reference zip files, which do not exist in the conformance suite.
        'G2-6-1_3/index.xml:TC2_invalid',
        'G2-6-1_3/index.xml:TC3_invalid',
        # The following test case fails because of the `tech_duplicated_facts1` formula, which incorrectly fires.
        # It does not take into account the language attribute on the fact.
        # Facts are not duplicates if their language attributes are different.
        'RTS_Annex_IV_Par_12_G2-2-4/index.xml:TC5_valid',
    ]),
    file='index_inline_xbrl.xml',
    info_url='https://www.esma.europa.eu/document/esef-conformance-suite-2023',
    local_filepath='esef_conformance_suite_2023.zip',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF'}),
    public_download_url='https://www.esma.europa.eu/sites/default/files/2023-12/esef_conformance_suite_2023.zip',
    shards=8,
)
