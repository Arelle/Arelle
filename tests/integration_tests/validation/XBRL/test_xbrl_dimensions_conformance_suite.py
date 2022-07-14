import os
import pytest
from tests.integration_tests.validation.validation_util import get_test_data


CONFORMANCE_SUITE = 'tests/resources/conformance_suites/xdt-conf-cr4-2009-10-06.zip'
ARGS = [
    '--file', os.path.abspath(os.path.join(CONFORMANCE_SUITE, 'xdt.xml')),
    '--formula', 'run',
    '--keepOpen',
    '--testcaseResultsCaptureWarnings',
    '--infoset',
    '--validate'
]

if os.getenv('CONFORMANCE_SUITES_TEST_MODE') == 'OFFLINE':
    ARGS.extend(['--internetConnectivity', 'offline'])

EXPECTED_FAILURE_IDS = frozenset([
    # The value of the xbrldt:targetRole attribute is valid
    # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
    '001-Taxonomy/001-TestCase-Taxonomy.xml/V-03',
    # An all hypercube has an msdos path in the targetRole attribute to locate the domain - dimension arc network
    # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
    '001-Taxonomy/001-TestCase-Taxonomy.xml/V-08',
    # A dimension-domain relationship has an msdos path in targetRole attribute to locate the domain-member arc network
    # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
    '001-Taxonomy/001-TestCase-Taxonomy.xml/V-09',
    # A domain-member relationship has an msdos path in targetRole attribute to locate the domain-member arc network
    # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
    '001-Taxonomy/001-TestCase-Taxonomy.xml/V-10',
])

TEST_DATA = get_test_data(ARGS, expected_failure_ids=EXPECTED_FAILURE_IDS)


@pytest.mark.parametrize("result", TEST_DATA)
def test_xbrl_dimensions_conformance_suite(result):
    """
    Test the XBRL Dimensions 1.0 Conformance Suite
    """
    assert result.get('status') == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
