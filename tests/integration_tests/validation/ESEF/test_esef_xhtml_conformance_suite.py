import os
import pytest

from tests.integration_tests.validation.validation_util import get_test_data


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/esef_conformance_suite_2021.zip/esef_conformance_suite_2021/esef_conformance_suite_2021'
TAXONOMY_PACKAGE = 'tests/resources/taxonomy_packages/esef_taxonomy_2021.zip'
PLUGIN = 'validate/ESEF'
ARGS = [
    '--disclosureSystem', 'esef-unconsolidated',
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'index_pure_xhtml.xml')),
    '--formula', 'none',
    '--keepOpen',
    '--packages', os.path.abspath(TAXONOMY_PACKAGE),
    '--plugins', PLUGIN,
    '--testcaseResultsCaptureWarnings',
    '--validate'
]


TEST_DATA = get_test_data(ARGS)


@pytest.mark.parametrize("result", TEST_DATA)
def test_esef_xhtml_conformance_suite(result):
    """
    Test the ESEF XHTML Conformance Suite
    """
    assert result.get('status') == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
