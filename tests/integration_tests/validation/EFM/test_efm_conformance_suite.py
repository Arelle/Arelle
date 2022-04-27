import os
import pytest


from tests.integration_tests.validation.validation_util import get_test_data


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/efm_conformance_suite_2022.zip/conf'
TAXONOMY_PACKAGE = 'tests/resources/taxonomy_packages/edgarTaxonomiesPackage-22.1.zip'
EFM_PLUGIN = 'validate/EFM'
IXDS_PLUGIN = 'inlineXbrlDocumentSet'
ARGS = [
    '--disclosureSystem', 'efm-pragmatic',
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'testcases.xml')),
    '--formula', 'run',
    '--keepOpen',
    '--packages', '{}'.format(os.path.abspath(TAXONOMY_PACKAGE)),
    '--plugins', '{}|{}'.format(EFM_PLUGIN, IXDS_PLUGIN),
    '--testcaseResultsCaptureWarnings',
    '--validate'
]


TEST_DATA = get_test_data(ARGS)


@pytest.mark.parametrize("result", TEST_DATA)
def test_efm_ixbrl_conformance_suite(result):
    """
    Test the EFM Conformance Suite
    """
    assert result.get('status') == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
